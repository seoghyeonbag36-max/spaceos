"""LSTM 학습 누수 잠금 — 홀드아웃이 전처리·모델선택으로 새지 않게.

## 막는 것 두 가지 (2026-09-16 실측)

1. **전처리 누수** — `build_dataset` 이 표준화 통계(mu·sd·y_mu·y_sd)를 전체 행에서
   냈다. 분기 시계열에서 이건 미래를 보고 스케일을 맞추는 것이다. 방향 판정이
   `pred - prev` 의 부호라 `y_mu` 이동이 판정을 그대로 흔든다 — 불변이 아니다.
2. **선택 누수** — `train_lstm.main` 이 8개 조합을 **보고와 같은 홀드아웃**에서 고르고,
   방향정확도가 `0.70` 을 넘는 순간 멈췄다. KPI 임계값이 곧 멈춤 규칙이라 절차가
   목표 달성을 보장했다. 그렇게 나온 70.8% 는 같은 홀드아웃의 무정보 상수
   (항상 하락 78.5%)보다 낮다.

numpy·pandas 가 없는 환경(이 저장소의 기본 테스트 러너)에서도 ②는 잡을 수 있도록
소스 수준 가드를 함께 둔다 — 누수가 되돌아오는 경로가 대부분 그 두 줄이다.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TRAIN = ROOT / "ml" / "training" / "train_lstm.py"
DATASETS = ROOT / "ml" / "training" / "datasets.py"


# ─────────────── 소스 가드 (의존성 없이 언제나 돈다) ───────────────

def test_hyperparameter_search_does_not_stop_at_the_kpi_threshold() -> None:
    """임계값 조기중단 금지 — 멈춤 규칙이 KPI 면 지표가 KPI 를 증명하지 못한다."""
    src = TRAIN.read_text(encoding="utf-8")
    body = src.split('def main(')[-1]
    # 주석은 이 누수를 **설명**하므로 제외하고, 실행되는 줄만 본다.
    code = "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith("#"))
    assert not re.search(r"dir_acc.*>=\s*0\.7", code), (
        "test 방향정확도가 임계값을 넘으면 탐색을 멈추는 코드가 돌아왔다")
    assert "break" not in code, "trial 루프의 조기중단은 최댓값 편향을 만든다"


def test_selection_uses_val_and_reporting_uses_test() -> None:
    src = TRAIN.read_text(encoding="utf-8")
    body = src.split('def main(')[-1]
    assert 'best["val"]' in body, "하이퍼파라미터 선택은 val 로 해야 한다"
    assert 'best["test"]' in body or 'bt = ' in body or 'best["test"], best["val"]' in body


def test_protocol_block_declares_the_leak_free_contract() -> None:
    """산출물을 읽는 쪽이 규약을 알 수 있어야 한다 — 없으면 옛 값과 구분이 안 된다."""
    src = TRAIN.read_text(encoding="utf-8")
    tree = ast.parse(src)
    proto = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "_PROTOCOL":
            proto = ast.literal_eval(node.value)
    assert proto is not None, "_PROTOCOL 표기가 사라졌다"
    assert proto["scaling"] == "train_only"
    assert proto["selection"] == "val"
    assert proto["test_used_once"] is True
    assert "persistence" in proto["baselines"]


def test_dataset_fits_scaler_on_training_rows_only_in_source() -> None:
    src = DATASETS.read_text(encoding="utf-8")
    assert "feats[train_row]" in src, "표준화 통계가 다시 전체 행에서 계산되고 있다"
    assert "sample_is_val" in src, "val 분할이 사라졌다"
    assert "TEST_QUARTERS" in src and "VAL_QUARTERS" in src, "롤링 오리진 분할이 사라졌다"


def test_reported_metric_keys_exist_in_what_scoring_returns() -> None:
    """`main()` 이 꺼내 쓰는 지표 키가 `_score` 가 실제로 만드는 키인지 정적으로 맞춘다.

    이 저장소의 기본 러너에는 torch 가 없어 학습 경로를 실행해 볼 수 없다. 그러면
    오타 하나가 **재학습하는 날에야** 터진다 — 몇 시간짜리 작업을 걸어 두고 마지막에
    KeyError 로 죽는 자리다. 실행 대신 소스에서 두 집합을 대조한다.
    """
    tree = ast.parse(TRAIN.read_text(encoding="utf-8"))
    produced: set[str] = set()
    used: set[str] = set()

    for node in ast.walk(tree):
        # _score 안의 `return { ... }` 가 만드는 키
        if isinstance(node, ast.FunctionDef) and node.name == "_score":
            for inner in ast.walk(node):
                if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Dict):
                    produced |= {k.value for k in inner.value.keys
                                 if isinstance(k, ast.Constant)}
        # main() 안의 bt[...] / bv[...] 참조
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Subscript)
                        and isinstance(inner.value, ast.Name)
                        and inner.value.id in {"bt", "bv"}
                        and isinstance(inner.slice, ast.Constant)
                        and isinstance(inner.slice.value, str)):
                    used.add(inner.slice.value)

    assert produced, "_score 의 반환 딕셔너리를 못 찾았다"
    assert used, "main() 이 test/val 지표를 꺼내 쓰지 않는다"
    assert used <= produced, f"없는 키를 꺼내 쓴다: {sorted(used - produced)}"


def test_train_once_returns_both_splits() -> None:
    """`_train_once` 는 test 와 val 을 **둘 다** 돌려줘야 한다 — 하나면 선택 누수로 돌아간다."""
    tree = ast.parse(TRAIN.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_train_once")
    ret = next(n for n in ast.walk(fn)
               if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict))
    keys = {k.value for k in ret.value.keys if isinstance(k, ast.Constant)}
    assert {"test", "val"} <= keys, f"반환 키: {sorted(keys)}"


# ─────────────── 수치 가드 (numpy·pandas 있을 때) ───────────────

def _dataset_module():
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    sys.path.insert(0, str(ROOT))
    from ml.training import datasets as m
    return m


def _synthetic(n_districts: int = 3, n_quarters: int = 16):
    """마지막 2분기만 값이 튀는 표 — 누수가 있으면 통계가 눈에 띄게 달라진다."""
    pd = pytest.importorskip("pandas")
    rows = []
    for d in range(n_districts):
        for q in range(n_quarters):
            spike = 1000.0 if q >= n_quarters - 2 else 0.0
            rows.append({
                "district_id": f"d{d}", "quarter": f"20{20 + q // 4}{q % 4 + 1}",
                "stor_co": 100.0 + q, "clsbiz_rt": 2.0 + spike, "opbiz_rt": 1.0,
                "selng_amt": 1e6, "flpop": 1e4,
                "vac_small": 5.0 + spike, "vac_mid": 4.0, "rent_small": 3.0,
            })
    return pd.DataFrame(rows)


def test_scaler_excludes_the_holdout_quarters(monkeypatch) -> None:
    m = _dataset_module()
    np = pytest.importorskip("numpy")
    df = _synthetic()
    prepared = _prep(m, df)
    monkeypatch.setattr(m, "load_gold", lambda: prepared)
    ds = m.build_dataset(look_back=4)

    # 제외 폭은 분할 설정을 따라간다 — 숫자를 박으면 롤링 오리진을 바꿀 때 이 줄이
    # 먼저 낡는다(2026-09-16 에 실제로 그랬다: 2분기 고정 → 기본이 5분기로 바뀜).
    holdout_q = m.TEST_QUARTERS + m.VAL_QUARTERS
    feats = prepared[list(m.SEQ_FEATURES)].to_numpy(dtype=float)
    keep = np.ones(len(prepared), dtype=bool)
    for did in prepared["district_id"].unique():
        idx = np.flatnonzero((prepared["district_id"] == did).to_numpy())
        keep[idx[-holdout_q:]] = False

    assert np.allclose(ds.mu, np.nanmean(feats[keep], axis=0)), "train 행 통계와 달라졌다"
    # 전체 행 통계와는 **달라야** 한다 — 같으면 누수가 되돌아온 것이다.
    assert not np.allclose(ds.mu, np.nanmean(feats, axis=0))


def test_val_and_test_masks_are_disjoint_and_sized_by_the_split(monkeypatch) -> None:
    """겹치지 않고, 거점마다 설정한 원점 수만큼 나와야 한다(롤링 오리진)."""
    m = _dataset_module()
    np = pytest.importorskip("numpy")
    prepared = _prep(m, _synthetic())
    monkeypatch.setattr(m, "load_gold", lambda: prepared)
    ds = m.build_dataset(look_back=4)
    n_d = len(ds.district_ids)
    assert not (ds.sample_is_val & ds.sample_is_last).any(), "val 과 test 가 겹친다"
    assert int(ds.sample_is_last.sum()) == n_d * m.TEST_QUARTERS
    assert int(ds.sample_is_val.sum()) == n_d * m.VAL_QUARTERS
    # test 는 시간축에서 val 보다 **뒤**에 있어야 한다 — 뒤섞이면 미래로 고르게 된다.
    assert min(ds.sample_quarter[ds.sample_is_last]) > max(ds.sample_quarter[ds.sample_is_val])


def test_single_origin_split_is_still_available(monkeypatch) -> None:
    """대조군(1/1)은 그대로 돌아야 한다 — 재학습 때 롤링 오리진과 비교할 팔이다."""
    m = _dataset_module()
    prepared = _prep(m, _synthetic())
    monkeypatch.setattr(m, "load_gold", lambda: prepared)
    ds = m.build_dataset(look_back=4, test_quarters=1, val_quarters=1)
    n_d = len(ds.district_ids)
    assert int(ds.sample_is_last.sum()) == n_d
    assert int(ds.sample_is_val.sum()) == n_d


def test_zero_holdout_is_rejected(monkeypatch) -> None:
    """test 나 val 이 0 이면 선택과 보고가 다시 한 표본에서 난다 — 막는다."""
    m = _dataset_module()
    prepared = _prep(m, _synthetic())
    monkeypatch.setattr(m, "load_gold", lambda: prepared)
    for kw in ({"test_quarters": 0}, {"val_quarters": 0}):
        with pytest.raises(ValueError):
            m.build_dataset(look_back=4, **kw)


def test_target_scaling_excludes_holdout_targets(monkeypatch) -> None:
    m = _dataset_module()
    np = pytest.importorskip("numpy")
    prepared = _prep(m, _synthetic())
    monkeypatch.setattr(m, "load_gold", lambda: prepared)
    ds = m.build_dataset(look_back=4)
    y_raw = ds.y * ds.y_sd + ds.y_mu
    train = ~(ds.sample_is_last | ds.sample_is_val)
    assert ds.y_mu == pytest.approx(float(y_raw[train].mean()), abs=1e-3)


def _prep(m, df):
    """load_gold 의 파생 피처 계산만 떼어 적용한다(파일 I/O 없이)."""
    np = pytest.importorskip("numpy")
    df = df.sort_values(["district_id", "quarter"]).reset_index(drop=True)
    out = []
    for _, g in df.groupby("district_id"):
        g = g.copy()
        base = g["stor_co"].iloc[0] or 1.0
        g["stor_idx"] = g["stor_co"] / base * 100.0
        chg = g["stor_co"].pct_change().fillna(0.0) * 100.0
        g["vac_proxy"] = (g["clsbiz_rt"] - g["opbiz_rt"]) - chg
        g["log_selng"] = np.log1p(g["selng_amt"].fillna(0.0))
        g["log_flpop"] = np.log1p(g["flpop"].fillna(0.0))
        out.append(g)
    import pandas as pd
    return pd.concat(out, ignore_index=True)

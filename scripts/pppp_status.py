"""[PPPP] 전 트랙 진행률 — 손으로 세지 않고 산출물에서 계산한다.

`/pppp-status` 슬래시 커맨드가 부르는 스크립트다.

## 왜 스크립트인가

진행률을 문서에 손으로 적으면 **쿼터를 소진한 날마다 낡는다.** 실제로
`docs/spaceos-vibe-build-sequence.md` 는 두 번 낡았다 — 08-02 에 멈춰 Tier1 을 13거점으로,
08-09 에 멈춰 22거점으로 적고 있었다(실제 49). 숫자 하나가 아니라 **그 숫자에 기대는
진술이 같이** 낡는다는 게 문제라, 세는 일을 코드로 내렸다.

## 진행률을 정직하게 만드는 법

이 저장소는 추정치를 실측처럼 보이게 하는 것을 가장 나쁜 산출물로 본다(AGENTS.md §0).
진행률도 예외가 아니다 — "대충 70%" 는 근거가 없다. 그래서:

- 트랙 진행률 = **게이트 여러 개의 평균**이고, 게이트마다 값과 근거를 함께 찍는다.
  평균이 마음에 안 들면 게이트를 보고 직접 판단하면 된다.
- 게이트는 두 종류다. `[자동]` 은 산출물을 세어 계산한 값이고, `[선언]` 은 사람이
  적어 둔 값이다. **선언은 근거 경로를 반드시 달고, 화면에서 자동과 구분해 보인다.**
  선언 게이트가 늘어나면 그만큼 이 숫자를 믿을 이유가 줄어든다는 뜻이다.
- 가중치는 두지 않는다(전부 동일 가중). 가중치는 그 자체가 판단이라, 숨기느니
  균등하게 두고 게이트 목록을 드러내는 편이 낫다.

읽기만 한다. 네트워크를 타지 않고 아무 파일도 쓰지 않는다 — 언제 돌려도 안전하다.

실행: python scripts/pppp_status.py          (저장소 루트 spaceos/ 에서)
      python scripts/pppp_status.py --json   기계 판독용
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "gold"

# Windows 콘솔 기본 코드페이지(cp949)에서 한글·기호가 깨진다. 와이어가 아니라 표시만
# 깨지는 것이라 결과를 오독하기 쉬워서(2026-08-16 실제로 두 번 헛읽음) 여기서 고정한다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class Gate:
    """진행률 한 칸. value 는 0.0~1.0."""

    name: str
    value: float
    detail: str
    auto: bool = True          # False = 선언(사람이 적은 값)
    evidence: str = ""         # 선언 게이트의 근거 경로 — 자동이면 비워 둔다


@dataclass
class Track:
    name: str
    phase: str
    gates: list[Gate] = field(default_factory=list)

    @property
    def pct(self) -> float:
        if not self.gates:
            return 0.0
        return 100.0 * sum(g.value for g in self.gates) / len(self.gates)

    @property
    def declared(self) -> int:
        return sum(1 for g in self.gates if not g.auto)


# ─────────────────────────── 공통 로더 ───────────────────────────

def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _hubs() -> int:
    """전체 거점 수. page_hubs 를 못 읽으면 gold 디렉토리 수로 떨어진다."""
    try:
        sys.path.insert(0, str(ROOT))
        from data.config.page_hubs import HUBS

        return len(HUBS)
    except Exception:
        return sum(1 for p in GOLD.iterdir() if p.is_dir() and (p / "coverage.json").exists())


def _count_measured_foot_hubs() -> int | None:
    """거점 내 `foot` 서열이 **실측**으로 갈리는 거점 수. 못 세면 None.

    왜 산출물이 아니라 백엔드 함수를 부르나: 판정은 "유닛 좌표 → 최근접 상권 →
    유동총량이 2종 이상인가" 인데, 그 유닛 모집단이 `seoul_pages` 의 시드 270유닛이다
    (`vacant_units.json` 의 580유닛과 **다른 모집단**이다 — 그쪽을 세면 다른 수가 나온다).
    규칙을 여기 옮겨 적으면 한쪽만 고쳐졌을 때 조용히 어긋나므로, 권위 있는 함수를
    그대로 부른다. 0.2초면 끝나고 네트워크도 파일 쓰기도 없다.

    None 은 "못 셌다" 이고 호출부가 종전 0.5 가중으로 물러난다 — 0 으로 세면 실측이
    있는데도 진행률이 떨어져 보인다.
    """
    try:
        sys.path.insert(0, str(ROOT / "apps" / "backend"))
        from app.services import districts as _d
        from app.services import posting_inputs as _pi

        return sum(
            1 for d in _d.DISTRICTS
            if _pi._measured_offsets(
                _pi._unit_trdar_flpop(d["id"], _d.DISTRICTS_BY_ID[d["id"]]["units"])
            ) is not None)
    except Exception:
        return None


def _hourly_axis_note() -> str:
    """24시간 시간축(생활인구)의 **실제 적재 상태**를 세어 문장으로 만든다.

    이 자리에 "24시간 실측은 시간 축만 갈아끼우면 된다"고 적어 두었던 것이
    2026-08-24 에 배선되면서 곧바로 낡았다. 같은 일이 또 일어나지 않게, 진행 문구를
    손으로 적지 않고 **산출물을 세어** 만든다.
    """
    doc = _load(GOLD / "page_footfall_hourly.json")
    if not doc:
        return ("시간은 6구간으로 접힌다 — 24시간 축은 배선됐으나 산출물이 없다"
                "(`python -m data.collectors.living_population_hourly` → "
                "`build_page_footfall_hourly`)")
    d = doc.get("districts") or {}
    covered = sum(1 for v in d.values()
                  if (v.get("weekday") or {}).get("hours_covered") == 24)
    we = sum(1 for v in d.values()
             if (v.get("weekend") or {}).get("hours_covered") == 24)
    smp = doc.get("sample") or {}
    return (f"시간 축은 **6구간 → 24시간**으로 갈아끼웠다(08-24, 생활인구 행정동). "
            f"평일 24시간이 채워진 거점 {covered}개 · 주말 {we}개 "
            f"(표본 {smp.get('dates')}일: 평일 {smp.get('weekday_dates')} / "
            f"주말 {smp.get('weekend_dates')}). 나머지 거점은 응답이 "
            f"`time_source:\"trdar_band\"` 로 6구간임을 밝히고 물러난다")


def _coverages() -> list[dict]:
    out = []
    for p in sorted(GOLD.glob("*/coverage.json")):
        j = _load(p)
        if j:
            j["_slug"] = p.parent.name
            out.append(j)
    return out


# ─────────────────────────── Page ───────────────────────────

def page_track(total: int) -> Track:
    t = Track("Page", "Phase 1·4 (수집으로 재진입)")
    cov = _coverages()
    tier1 = [c for c in cov if str(c.get("tier", "")).startswith("Tier1")]
    t.gates.append(Gate(
        "Tier1 대장 실측 거점",
        len(tier1) / total if total else 0.0,
        f"{len(tier1)}/{total}거점 — 잔여 "
        + (", ".join(sorted(c["_slug"] for c in cov if c not in tier1)) or "없음"),
    ))

    # 티어는 통과/미통과이지 품질 등급이 아니다 — 대표 집계 커버리지를 따로 센다.
    good = [c for c in tier1 if (c.get("reference_coverage_pct") or 0) >= 90]
    low = sorted(((c.get("reference_coverage_pct") or 0), c["_slug"]) for c in tier1)[:3]
    t.gates.append(Gate(
        "대표 집계 커버리지 ≥90%",
        len(good) / total if total else 0.0,
        f"{len(good)}/{total}거점 — 최저 " + " · ".join(f"{s} {v:.1f}%" for v, s in low),
    ))

    anchored = [p for p in GOLD.glob("*/calibration.json")]
    t.gates.append(Gate(
        "R-ONE 앵커 대조 보유",
        len(anchored) / total if total else 0.0,
        f"{len(anchored)}/{total}거점 — 없으면 앵커 대조 자체가 불가(격차 0 이란 뜻이 아니다)",
    ))

    # 4대 레이어는 엔드포인트 유무로는 판정이 안 된다 — 유동인구는 라우트가 있어도
    # 프론트가 SAMPLE 상수를 그린다. 그래서 실데이터 여부는 선언으로 둔다.
    t.gates.append(Gate(
        "4대 히트맵 레이어 실데이터", 4 / 4,
        "공실 ✅ · 임대 ✅(R-ONE) · 유동 ✅ · 밀도 ✅ — 네 레이어가 같은 100m 격자 "
        "위에 선다. 유동·밀도는 08-23 배선(TRDAR 상권 190곳, 54/54거점). 재료는 "
        "`features/trdar_demand.parquet` 에 이미 있었다 — 문서가 '좌표가 없어 못 쓴다'고 "
        "적어 둔 것이 틀렸고(좌표 결측 0), 저장소 안의 재료를 못 찾고 있던 것이다. "
        "예전 유동 레이어는 Math.random() 점 120개였고 시간 슬라이더는 오버레이 "
        "effect 의존성에 hour 가 없어 **드래그해도 아무것도 안 바뀌는 장식**이었다. "
        "⚠ 100% 는 '네 레이어가 실데이터를 쓴다'는 뜻이지 격자 실측이라는 뜻이 아니다 — "
        "유동·밀도 값은 **상권 단위 집계**를 셀에 얹은 것이다(거점당 상권 1~9, 중앙 3). "
        "응답 `resolution:\"trdar\"` 와 범례 배지가 이걸 밝힌다. "
        + _hourly_axis_note()
        + " ⚠ 그래도 **격자 실측은 아니다** — 시간 축이 24시간이 되어도 값은 여전히 "
          "상권(공간)·행정동(시간) 집계이고, 거점 내부의 시간 차이는 알 수 없다",
        auto=False,
        evidence=("docs/feature-page.md §유동·밀도 · services/footfall_layer.py · "
                  "data/pipelines/build_page_footfall_hourly.py · "
                  "apps/backend/tests/test_footfall_layer.py (21건) · "
                  "data/tests/test_page_footfall_hourly.py (12건)"),
    ))
    t.gates.append(Gate(
        "지도·건물상세·3D 트윈 표면", 1.0,
        "MapShell 지도 + 건물 클릭 패널 + BuildingTwin 동작",
        auto=False,
        evidence="apps/frontend/src/pages/MapShell.tsx",
    ))
    return t


# ─────────────────────────── Platform ───────────────────────────

def platform_track() -> Track:
    t = Track("Platform", "Phase 5 (ML)")
    fc = _load(GOLD / "platform_vacancy_forecast.json")
    t.gates.append(Gate(
        "LSTM 공실예측 학습·서빙",
        1.0 if fc else 0.0,
        f"model={fc.get('model')} · 학습 {str(fc.get('trained_at'))[:10]}" if fc
        else "platform_vacancy_forecast.json 없음 → API 가 lstm-stub 으로 떨어진다",
    ))

    rec = _load(GOLD / "platform_industry_recommend.json")
    m = (rec or {}).get("metrics", {})
    t.gates.append(Gate(
        "GNN 업종추천 학습·서빙",
        1.0 if rec else 0.0,
        f"노드 {m.get('nodes')} · 피처 {m.get('features')} · "
        f"수요신호 {'반영' if m.get('demand_features') else '없음(58열로 되돌아감)'}"
        if rec else "platform_industry_recommend.json 없음",
    ))

    # KPI 는 목표 대비 비율로 부분점수를 준다 — 달성/미달만 찍으면 얼마나 남았는지 사라진다.
    #
    # 2026-08-17 KPI 재정의: **Top-1 게이트를 폐기하고 Top-3 + macro-F1 로 간다.**
    # Top-1 70% 는 가진 레버를 다 써서 못 닿는 것이 실측으로 확인됐다 —
    #   ① 세분 라벨(32클래스): Top-1 30.0% / Top-3 58.4% (Top-3 KPI 붕괴)
    #   ② 균형 손실(빈도 역수): Top-1 28.3% / lift -53.7% (사전분포 아래)
    # 게이트로 남겨두면 진행률이 '닿을 수 없는 목표에 대한 거리'가 되어 매번 오독된다.
    # 제품이 파는 것도 자리 하나당 업종 하나가 아니라 공실 유닛의 Top-3 후보다.
    top3, top1 = m.get("test_top3"), m.get("test_top1")
    f1 = m.get("test_macro_f1")
    if top3 is not None:
        # lift 는 Top-1 기준값이다. Top-3 사전분포 옆에 그냥 붙이면 'Top-3 의 lift'로
        # 읽히므로 어느 지표의 lift 인지 명시한다.
        t.gates.append(Gate(
            "KPI 업종추천 Top-3 ≥70%", min(1.0, top3 / 0.70),
            f"{top3:.1%} — 달성. 단 거점 사전분포가 이미 "
            f"{m.get('baseline_district_prior_top3', 0):.1%} 라 "
            f"Top-1 lift 는 {m.get('lift_vs_district_prior_pct')}% 다"
            + (f" · Top-1 {top1:.1%}(게이트 폐기, 관측만)" if top1 is not None else ""),
        ))
    # off-prior Top-3 회수율 — 거점 사전분포가 **원리적으로 못 맞히는** 자리에서의 회수율.
    # 이걸 게이트로 쓰는 이유(2026-08-17 분석):
    #   피처 95개 중 자리마다 값이 달라지는 것은 5개뿐이고 나머지 90개는 거점 상수라
    #   (원핫 54 + TRDAR 36), 집계 지표는 거의 전부 거점 평균으로 설명된다. 지표값 중
    #   거점 사전분포가 아닌 몫('순도')을 재면 Top-3 정확도 2.3% · macro-F1 50.3% ·
    #   off-prior 100% 다. 순도가 낮은 지표를 게이트로 걸면 Platform·Page 에 무엇을
    #   넣어도 숫자가 안 움직인다 — Top-1 70% 가 실패한 구조가 그것이다.
    #
    # 목표 0.50 은 **도출된 값**이다(macro-F1 0.50 이 잠정치였던 것과 다르다):
    #   방어 게이트(전체 Top-3 ≥70%)를 통과하면서 자리를 전혀 안 보는 값싼 규칙
    #   — 거점 순위 (1,2,4) 를 Top-3 으로 내놓기 — 이 off-prior 42.42% 를 낸다.
    #   따라서 목표는 42.42% 위여야 한다. 표본 877자리에서 표준오차 ≈1.7%p 이므로
    #   0.45 는 1.5σ, 0.50 은 4.5σ 로 잡아 0.50 을 택했다. 이론 천장은 75%
    #   ('off-prior 임을 알고' 남은 4종 중 3종을 고를 때)다.
    off = m.get("test_offprior_top3")
    obs = 0.2645   # 2026-08-17 저장 체크포인트로 test 분할 재측정(재학습 없음)
    if off is None:
        # 아직 학습 산출물에 이 필드가 없다(train_gnn 에 08-17 추가 → 다음 학습부터 채워짐).
        # 그때까지는 손으로 잰 값을 **선언**으로 둔다. 자동인 척하면 안 되는 자리다.
        t.gates.append(Gate(
            "KPI 업종추천 off-prior Top-3 ≥50%", min(1.0, obs / 0.50),
            f"{obs:.1%} — 서빙 체크포인트(95열) 실측. 값싼 규칙(거점 순위 1·2·4)이 "
            f"42.4% 라 **아직 그보다 낮다**. Page 건물 피처 10열을 넣은 105열은 "
            f"**35.9%** 로 올랐다(동일조건 ablation 28.05% → 35.92%, +28.1%) — "
            f"save 런 한 번이면 이 게이트가 자동 전환된다",
            auto=False,
            evidence="docs/finding-sequence-and-accuracy-2026-08-17.md §9 · "
                     "ml/training/train_gnn.py::_offprior_top3",
        ))
    else:
        t.gates.append(Gate(
            "KPI 업종추천 off-prior Top-3 ≥50%", min(1.0, off / 0.50),
            f"{off:.1%} — 거점 사전분포로는 정의상 0% 인 자리 "
            f"{m.get('offprior_nodes', '?')}개 기준. 값싼 규칙 하한 42.4%"
            + (f" · macro-F1 {f1:.4f}(관측)" if f1 is not None else "")
            + ". ⚠ 2026-08-23 **이웃 업종 분포 피처(8열) 시도 — 개선 없음.** "
              "§9 가 남긴 레버('약국↔병원 인접')를 `_neighbor_label_block` 으로 "
              "구현해 113열로 재학습했다(train 라벨만 집계·self 제외로 누출 차단). "
              "결과 off-prior 37.63% → **36.49%** · Top-3 91.86% → 91.40% · "
              "macro-F1 0.2622 → **0.2803**. 표본 877 에서 표준오차 ≈1.63%p 라 "
              "−1.14%p 는 **1σ 이내 — 유의하지 않다**(올리지도 내리지도 못했다). "
              "게이트 지표가 나아지지 않았으므로 산출물은 되돌렸고 피처는 기본 off "
              "(`--neighbor` 로만 켜진다). 코드와 음성 결과는 남겼다 — 지우면 다음 "
              "사람이 같은 것을 다시 시도한다. "
              "⚠ 2026-08-24 **조기 종료 기준 3종 ablation — 기각.** 위 항목이 "
              "'다음 후보' 로 지목했던 가설이다(val top1 은 거점 사전분포에 지배되는 "
              "지표라 off-prior 가 최적화되기 전에 멈춘다). `--select-by` 를 만들어 "
              "같은 조건(600ep·patience 80·동일 시드)으로 셋을 돌렸다: "
              "top1 **35.92%** · macro_f1 **37.17%** · offprior3 **37.17%** "
              "(Top-3 방어선은 셋 다 91.7~91.8% 유지). "
              "결정적인 것은 **게이트 지표를 val 에서 직접 최적화한 offprior3 가 "
              "macro_f1 과 소수점까지 같은 값에 멈췄다**는 것이다 — val 은 37.70% 까지 "
              "올랐는데 test 는 37.17% 였으므로 val 과잉적합도 아니다. 즉 이 피처 "
              "집합의 **천장**이 37% 대이고, 언제 멈추느냐로는 넘을 수 없다. "
              "top1 대비 +1.25%p 는 표준오차 ≈1.63%p 안이라 유의하지도 않다. "
              "기본값은 top1 그대로 두었다(종전 재현성 유지). "
              "⚠ 2026-08-24 **행정동 24시간 축 — 기각(천장 네 번째 확인).** 위 항목이 "
              "'다음 후보'로 지목했던 레버다: 거점 안에서 값이 변하는 피처를 늘린다. "
              "Page 24시간 축의 원천인 행정동 표(`build_adong_hourly_features`)를 "
              "`_adong_hour_block` 10열로 붙여 **115열** 재학습(600ep·patience 80·동일 "
              "시드). within-district 분산 0.221 짜리 10열을 실제로 늘렸는데도 "
              "off-prior 37.63 → **37.51%**(−0.12%p) · Top-3 91.86 → **92.05%** · "
              "macro-F1 0.2622 → 0.2611 로 전부 표준오차(≈1.63%p) 안이다. "
              "**진단이 좁혀졌다: 막는 것은 변동의 양이 아니라 종류다** — 시간·유동 "
              "계열로는 약국을 병원 옆에서 가릴 수 없다. 필요한 것은 업종 자체에 대한 "
              "정보(감성·인접 구조)이고 이는 막힘 6·17 을 그대로 가리킨다. 산출물은 "
              "되돌렸고 피처는 기본 off(`--adong`). → docs/feature-platform.md §0-J. "
              "천장 37%대는 이로써 네 번 확인됐다(기준 37.63 · 이웃 36.49 · 조기종료 "
              "35.92~37.17 · 행정동 37.51). "
              "⚠ 2026-08-25 이 문구가 갱신되지 않아 행정동 축이 계속 '다음 후보'로 "
              "읽혔고, 그대로 **같은 실험이 한 번 더 돌았다**(네 지표 소수점까지 재현 — "
              "reports/gnn_adong_2026-08-25.json). 결과가 커밋 메시지와 docs 에만 있고 "
              "게이트에 없으면 게이트를 읽는 사람이 다시 시도한다. "
              "→ 남은 레버는 **Platform 감성(막힘 6번)** 과 **집계구 입도**(막힘 5번 · "
              "SGIS 승인 대기, docs/prep-sgis-application.md)뿐이고 둘 다 선행이 "
              "코드가 아니다. "
              "실측표: reports/gnn_selectby_ablation.json · reports/gnn_adong_2026-08-25.json",
        ))
    return t


# ─────────────────────────── Posting ───────────────────────────

def posting_track(total: int) -> Track:
    t = Track("Posting", "Phase 6-1 (입점 솔루션)")
    inp = _load(GOLD / "platform_posting_inputs.json") or {}
    # 거점은 최상위가 아니라 "districts" 아래에 있다. 최상위를 훑으면 조용히 0/54 가
    # 나오고 "아직 안 붙였구나"로 오독된다 — 실제로 이 스크립트가 그렇게 틀렸다.
    hubs = {k: v for k, v in (inp.get("districts") or {}).items() if isinstance(v, dict)}

    t.gates.append(Gate(
        "3-Tier 폴백 계산", 1.0,
        "고급화/가성비/기능중심 3전략 + roi_months 산출",
        auto=False, evidence="apps/backend/app/services/districts.tier_scenarios",
    ))

    # 4입력(rent·foot·area·prem) 중 실데이터가 몇 개인가 — 거점별로 세어 평균낸다.
    # foot 은 2026-08-24 에 거점 내 서열까지 실측이 됐다(최근접 상권 유동총량).
    # 51/54거점·255/270유닛이 `flpop+trdar` 이고, 남은 3거점은 상권이 1곳이라
    # **원리적으로** 못 가른다 — 시드가 남아서가 아니라 데이터에 구조가 없어서다.
    # 그래서 0.5 가 아니라 실측 거점 비율로 센다.
    rent = sum(1 for v in hubs.values() if v.get("rent_per_m2_krw_thousand"))
    foot = sum(1 for v in hubs.values() if v.get("flpop"))
    # area 는 오랫동안 "0/54" 로 **하드코딩**돼 있었다(08-23 발견). 실제로는
    # vacant_units.json 의 모든 유닛에 채워져 있고, tier_scenarios 가 unit["area"] 로
    # 그걸 그대로 쓴다 — 게이트만 몰랐고 Posting 진행률을 과소평가했다.
    # 단 1.0 은 아니다: 값은 건축물대장 상업면적 ÷ capacity 라 **건물 단위는 실측,
    # 건물 안 유닛 간 서열은 균등분할**이다(build_vacant_units.area_pyeong).
    # foot 과 같은 성격이므로 같은 0.5 로 센다. 상가정보 flrNo 로 유닛별
    # 실면적을 특정하면 그때 1.0 이다.
    area = 0
    for d in sorted(GOLD.glob("*/vacant_units.json")):
        raw = _load(d)
        units = raw.get("units") if isinstance(raw, dict) else raw
        if units and all(u.get("area") for u in units):
            area += 1
    # 최근접 상권으로 거점 내 서열이 갈리는 거점 수 — 손으로 적지 않고 센다.
    # 못 세면(None) 종전 0.5 가중으로 물러난다.
    foot_measured = _count_measured_foot_hubs()
    foot_score = foot_measured if foot_measured is not None else 0.5 * foot
    # 분모가 4 → **3** 이다(2026-08-24 결정, docs/feature-posting.md §0-K).
    # `prem`(권리금)은 공개 통계가 없고 실제로도 임대인·기존 임차인과의 협상값이라
    # **수집으로는 영영 안 채워진다.** 0/54 를 계속 세면 "언젠가 수집하면 된다"로
    # 읽히는데 그게 사실이 아니다. 아래 '입력 계약' 게이트로 옮겼다.
    per_hub = ((rent + foot_score + 0.5 * area) / (3 * total)
               if total else 0.0)
    t.gates.append(Gate(
        "3-Tier 입력 3종 실데이터화 (수집 가능한 것)", per_hub,
        f"rent {rent}/{total} ✅(R-ONE) · foot {foot}/{total} "
        + (f"(거점 내 서열까지 실측 {foot_measured}/{total} ✅ — 최근접 상권 "
           f"유동총량. 나머지는 유닛이 전부 같은 상권에 배정돼 **원리적으로** 못 "
           f"가른다: nokdu·garak 은 상권 1곳, euljiro 는 유닛 5개가 300m 안) · "
           if foot_measured is not None else
           "◐(절대수준만 실측 — 서열 판정을 못 셌다) · ")
        + f"area {area}/{total} ◐(대장 상업면적÷capacity — 건물 실측, 유닛 서열은 "
        f"균등분할). ⚠ 2026-08-24 실 인벤토리 배선(§0-J): 이 셋이 이제 **시드 270유닛이 "
        f"아니라 실측 528유닛** 위에서 돈다. 그전까지 resolved_units 가 시드만 읽어 "
        f"Posting 화면이 손으로 적은 예시 위에서 돌고 있었다 — 수집이 아니라 배선 "
        f"문제였고, 게이트 문구의 '배선을 막는 것은 이제 없다'가 곧 '아직 안 했다'였다. "
        f"⚠ 실 인벤토리는 층이 **전부 1F 가정**이라 임대료가 계통적 상한이다(마진 중앙 "
        f"premium 0.4 / value −1.7 / factory 2.1% · 회수불가 13.6% — 시드 기준 §0-I 의 "
        f"2.4/0.7/4.2% · 10.0% 를 대체한다). 분해식 검증은 그대로 통과하므로 모델 고장이 "
        f"아니라 층 가정의 결과다. `prem` 은 분모에서 빠졌다 → 아래 입력 계약 게이트",
    ))

    # 권리금은 '못 얻는 데이터'가 아니라 '기업이 주는 값'이다. 수집 게이트로 세면
    # 영영 0% 이므로 계약 게이트로 옮겨 실제로 열렸는지를 센다.
    sim = (ROOT / "apps/backend/app/schemas/posting.py").read_text(encoding="utf-8")
    posting_svc = (ROOT / "apps/backend/app/services/posting.py").read_text(encoding="utf-8")
    # 스키마에 필드가 있는 것만으로는 부족하다 — 라우터가 서비스로 넘기고 서비스가
    # 유닛에 얹어야 실제로 계약이 열린 것이다. 세 지점을 모두 본다.
    router = (ROOT / "apps/backend/app/api/v1/ai.py").read_text(encoding="utf-8")
    prem_wired = ("prem: int | None" in sim
                  and "req.prem" in router
                  and '"prem": "contract"' in posting_svc)
    t.gates.append(Gate(
        "`prem` 입력 계약 (기업이 넣는다)", 1.0 if prem_wired else 0.0,
        "권리금은 공개 통계가 없고(bronze 전수 확인) 실제로도 임대인·기존 임차인과의 "
        "**협상값**이라 그 자리에 들어갈 기업만 안다 — Program 입력 계약 ③층(창업계획)과 "
        "같은 성격이라, 수집 과제가 아니라 계약 과제로 옮겼다(2026-08-24 결정 · 막힘 7). "
        "`POST /ai/simulate-revenue` 의 `prem`(만원)으로 받고, 안 주면 0 을 전제로 "
        "계산하며 `inputs_source['prem']` 이 `absent`(전제)/`contract`(받았다)를 밝힌다. "
        "⚠ 정하기 전에 감도를 쟀다(시드 270유닛 전수): prem→0 이면 **추천 5.2% 뒤집힘 · "
        "roi 중앙 1.6개월(p90 15.5) · 회수가부 변화 0건**. 무시할 수 없지만 제품의 핵심 "
        "판정은 안 건드린다 — 즉 §0-I 의 '회수불가' 결론은 prem 과 무관하게 성립한다"
        if prem_wired else
        "미배선 — SimulateRequest 에 prem 이 없다",
        auto=False,
        evidence="docs/feature-posting.md §0-K · apps/backend/app/schemas/posting.py · "
                 "apps/backend/tests/test_posting_marketing.py::"
                 "test_prem_is_an_input_contract_not_a_collected_field",
    ))

    # 주석 문구로 판정하면 주석만 고쳐도 "연동됨"이 된다. 어댑터라면 반드시 밖으로
    # 나가는 호출이 있어야 하므로, HTTP 클라이언트 사용 여부를 신호로 쓴다.
    # 2026-08-23: 호출이 services/posting_copilot 로 분리돼서 posting.py 만 보면
    # 영영 0% 로 남는다. **어댑터 모듈**을 보고, posting.py 가 실제로 그걸 부르는지도
    # 같이 본다 — 모듈만 있고 아무도 안 쓰면 연동이 아니다.
    cop = ROOT / "apps/backend/app/services/posting_copilot.py"
    posting_py = (ROOT / "apps/backend/app/services/posting.py").read_text(encoding="utf-8")
    cop_src = cop.read_text(encoding="utf-8") if cop.exists() else ""
    wired = (any(s in cop_src for s in ("requests.", "httpx.", "urllib.request"))
             and "posting_copilot" in posting_py)
    t.gates.append(Gate(
        "외부 AI 창업 코파일럿 어댑터", 1.0 if wired else 0.0,
        "계약 `spaceos.posting/1` 을 **우리가 발행**하고 어댑터를 그에 맞춰 구현했다 "
        "(services/posting_copilot). 공급자 미정이라 명세를 기다리는 동안 0% 로 남아 "
        "있던 자리다 — 이제 `POSTING_COPILOT_URL` 만 채우면 붙는다. 파생값(net·roi·"
        "recommended)은 공급자가 아니라 우리가 계산하고, 계약 위반 응답은 통째로 폴백한다"
        if wired else
        "미연동 — `_call_copilot` 이 항상 None 을 반환해 폴백만 돈다(입출력 명세 부재)",
    ))

    t.gates.append(Gate(
        "`rec` 추천 기준 정의", 1.0,
        "회수 최단으로 정의·계산(recommend_tier). 손으로 적은 값이 카드에 노출되던 것을 "
        "걷어냈고, rec 필드가 없는 실제 건물 유닛도 통과한다",
        auto=False, evidence="apps/backend/app/services/districts.recommend_tier",
    ))

    vu = list(GOLD.glob("*/vacant_units.json"))
    # 유닛 수는 **세어서** 적는다. 종전에는 "580유닛"이 문구에 박혀 있었는데 실측은
    # 528 이었다 — 선언이 낡는 이 저장소의 주된 실패 양식이 게이트 문구에서 났다.
    n_units = 0
    for _f in vu:
        _raw = _load(_f)
        _us = _raw.get("units") if isinstance(_raw, dict) else _raw
        n_units += len(_us or [])
    t.gates.append(Gate(
        "실제 공실 유닛 인벤토리", len(vu) / total if total else 0.0,
        f"{len(vu)}/{total}거점 · **{n_units}유닛** — 08-22 재실행으로 완주. 종전 잔여 5곳"
        "(hyehwa·kyunghee·sadang·sukmyung·wangsimni)은 막힘이 아니라 대기였고, 대장 완주로 "
        "상업면적이 채워져 그대로 풀렸다. 추적 예외(!data/gold/*/vacant_units.json)까지 "
        "걸려 54/54 가 git 에 올라가 있다. ⚠ **2026-08-24 배선 완료** — 그전까지 "
        "`districts.resolved_units` 가 시드 270유닛만 읽어 Posting API·화면이 손으로 적은 "
        "예시 위에서 돌았다. 이 게이트의 종전 문구 '배선을 막는 것은 이제 없다'가 정확히 "
        "'아직 안 했다'는 뜻이었는데 그렇게 읽히지 않았다 — 게이트가 100% 인 것과 그 "
        "산출물이 제품에 닿는 것은 다른 일이다. services/vacant_inventory 로 로더를 한 벌 "
        "두고 Program ①층과 함께 본다 → docs/feature-posting.md §0-J",
    ))

    t.gates.append(Gate(
        "3-Tier 비용 모델 보정", 4 / 4,
        "재보정 2026-08-23 오후 — 조건 넷 중 **셋**. 오전에는 A(평균 점포 면적)를 "
        "임차료에서 역산했고(premium 12.6 · value 7.1 · factory 7.1평), 그 함수 스스로 "
        "자기 값을 **하한**이라고 적어 두었다. 공정위 가맹사업 정보공개서(data.go.kr "
        "15110241, 12만 가맹점)로 갈아끼우니 A 는 **20.8 · 18.5 · 17.1평** — 2~3배 크다. "
        "한식집 7.1평은 실물이 아니었다. "
        "그런데 A 만 키우자 회수불가가 2.6% → **50%** 로 튀었다. 원인은 A 가 아니라 "
        "**분자**였다 — 상권분석 추정매출(카드 기반)이 KOSIS 전수 대비 1.2~2.3배 과소다. "
        "A 가 작아서 그 과소추정이 상쇄돼 보이고 있었을 뿐이고, 즉 **오전의 '회수불가 "
        "2.6%' 는 매출을 3배 부풀린 결과였다.** "
        "지금은 세 실측이 각자 잘하는 축을 맡는다: 거점 격차는 상권분석(비율로만) · "
        "절대수준은 KOSIS 점포당 · 면적은 공정위. 공정위와 KOSIS 는 서로 독립인데 "
        "짝지으면 평당매출이 **195/144/201만원/평**로 업계 통상(150~300)에 들어온다 — "
        "서로를 검증한 셈이다(오전 값 141, A 만 교체 시 85~121로 대역 밖이었다). "
        "결과: 회수불가 **10.0%** ✅ · factory **165승/270** ✅ · 평당매출 상식대역 ✅ · "
        "마진 중앙 premium 2.4 / value 0.7 / factory 4.2% ↔ KOSIS 5.8/7.0/8.8 — "
        "**셋 다 대역 밖** ❌. "
        "⚠ 다만 그 격차는 **산술로 닫힌다**: 마진 = KOSIS 이익률 − (rent/rev − KOSIS "
        "임차료율). 우리 유닛은 전부 프라임 54거점이라 임대료 비중이 서울 평균보다 "
        "3.5~6.6%p 높고, 딱 그만큼 마진이 깎인다. 즉 '마진이 대역 안'은 프라임 "
        "인벤토리에 대면 **애초에 틀린 기준**이었다 — 그래서 조건을 폐기하지 않고 "
        "❌ 로 남긴 채, 격차가 분해되는지를 넷째 조건으로 세워 ✅ 로 셌다. "
        "기준을 갈아 통과시킨 것으로 읽히지 않도록 둘 다 드러낸다. "
        "⚠ 남은 것: A 는 **전국 가맹점** 모집단이라 서울 실측 매출과 축이 완전히 같지 "
        "않다. "
        "⚠ **2026-08-25 재수립 — 위 시드 270유닛 수치를 실 인벤토리 528유닛이 대체한다.** "
        "08-24 배선 직후 값(회수불가 13.6% · 마진 0.4/−1.7/2.1%)은 층을 **전부 1F 로 "
        "가정**한 결과였고, 그 가정이 **96.2% 의 유닛에서 틀렸다**(상업층 중앙 4개). "
        "층별개요(bronze bldg_flr_raw)에서 상업층 **면적 비중**을 복원해 임대료를 층 "
        "가중평균으로 계산한다 — 528/528 확보, 층 집합은 silver `com_flr_nos` 와 전수 "
        "일치, 층별 면적 합은 `com_area_flr` 와 중앙비 1.000 이라 **새 가정을 들인 것이 "
        "아니라 이미 쓰던 면적을 쪼갠 것**이다. 층 가중계수 중앙 **0.549** → 종전 "
        "임대료가 중앙 **45% 과대계상**돼 있었다. "
        "결과 **넷 다 ✅**: 회수불가 **1.3%** · factory **417승/528** · 평당매출 "
        "195/144/201 · 마진 중앙 **5.5 / 4.3 / 7.0%** (KOSIS 대역 3.5~10.5% 안). "
        "⚠ **그러나 '닫혔다'고 읽지 말 것.** 마진이 대역 안에 든 대가로 프라임 "
        "프리미엄이 premium **3.5%p → 0.3%p** 로 내려앉았다 — 프라임 54거점 인벤토리가 "
        "서울 **평균**과 같은 임대료 부담을 진다는 뜻이라 그것대로 미심쩍다. 두 모델은 "
        "참값을 사이에 둔다: **1F 고정 = 상한 · 층 가중평균 = 하한**. 어느 쪽이 돌았는지 "
        "`inputs_source['floor']`(flr_ouln/assumed_1f)가 밝히고, 괄호 자체는 "
        "`test_weighted_floor_rent_is_a_lower_bound_than_1f` 가 고정한다. "
        "⚠ **2026-08-25 오후 그 다음 레버('공실 유닛이 실제로 어느 층인지')를 실행했다 "
        "— 괄호는 좁혀지지 않았고 층 축이 바닥을 쳤다.** 새로 받을 자료는 없었다: Page "
        "마스터가 `occ_floors`(상가정보 flrNo·인허가로 점유가 확인된 층)와 `unknown_n` 을 "
        "이미 싣고 있어 **수집이 아니라 배선**이었다(§0-J 와 같은 양식). 전수 프로브 "
        "528/528 PNU 매칭 · flrNo 보유 365/528 · floor_mix ⊂ com_floors 528/528 일치 · "
        "점유 층을 실제로 덜어낸 유닛 326/528. 계수 중앙은 1F 1.000 → 전체 층 **0.549** "
        "→ 빈 층 **0.487** → 하단 **0.401** 로 내려간다. **통과 조건 넷은 오히려 좋아졌는데"
        "**(회수불가 1.3→1.1% · factory 417→419승 · 마진 5.5/4.3/7.0 → 6.0/5.2/7.6) "
        "`test_margin_gap_is_exactly_the_prime_rent_premium` 이 걸렸다 — premium 프라임 "
        "프리미엄이 **+0.3%p → −0.23%p** 로 부호를 넘어, 프라임 54거점 인벤토리가 서울 "
        "평균보다 임대료 부담이 **낮다**는 성립 불가한 값이 된다. 임계값을 내리지 않고 "
        "**싣는 값을 `floor_mix` 로 되돌렸다.** 산출물에는 `vac_floor_mix`·"
        "`vac_floor_mix_lo`·`occ_floors`·`unknown_n` 을 남기되 `floor_basis` 는 승격하지 "
        "않는다(라벨이 올라가면 응답이 안 쓴 모델로 계산했다고 말한다). "
        "**층 축은 다 썼다** — 프리미엄을 층으로 두 번 고쳐 +5.3 → +0.3 → −0.2%p 이고, "
        "세 번째 수정은 0.5%p 만 움직이며 부호만 넘겼다. 남은 후보는 층이 아니라 **분모**"
        "다: 매출 절대수준이 KOSIS 서울 **평균**에 앵커돼 있고(`revenue_basis` "
        "= kosis-anchored) 프라임 보정이 없다. → docs/feature-posting.md §0-M. "
        "⚠ **2026-08-25 저녁 그 분모를 실행했다 — 버그는 있었고, 가설은 기각됐다"
        "**(§0-N). `_trdar_seoul_median()` 이 이름과 다른 것을 세고 있었다: "
        "`_revenue()` 는 산출물의 `districts`(= **우리 54거점**)만 돌려주는데 그 54개의 "
        "중앙을 '서울 중앙'이라 부르고 있었다 → 거점 매출배율이 **정의상 중앙 1.00** 이라 "
        "프라임 매출 프리미엄이 **구조적으로 지워져** 있었다. 제대로 된 기준점은 같은 "
        "파일의 `seoul` 키(서울 전체 상권 관측 **393** · 점포 **18,226**)로 **이미 있었고 "
        "서빙이 안 읽고 있었다** — §0-J·§0-M 과 세 번째로 같은 양식이다. 고치니 배율이 "
        "**1.05/1.07/1.16**, 평당매출 195/143/198 → **205/154/231**, 게이트 넷 유지·개선"
        "(회수불가 1.3 → **0.8%** · factory 417 → **432승** · 마진 5.5/4.3/7.0 → "
        "**5.8/4.8/7.8**), 상식대역 밖 35 → **27**(목표로 삼지 않은 독립 방증). "
        "**그런데 프라임 프리미엄은 +0.29 → +0.0185%p 로 오히려 내려갔다** — 배율이 오르면 "
        "분모가 커져 rent/rev 가 작아지므로 §0-M 이 적은 방향이 반대였다. 트립와이어 `>0` 을 "
        "통과하지만 **0.02%p 차이라 경계 위 통과**로 읽을 것(임계값은 안 건드렸다). "
        "**남은 자리는 층 기준의 비대칭이다**: 우리는 R-ONE(사실상 1층 기준)에 층별 **면적 "
        "비중**(중앙 0.549)을 곱하는데 KOSIS 임차료는 **점포가 실제 있는 층**의 실지불액이다. "
        "54거점 상가정보 137,880개 실측 층 분포(1F 42.9%·2F 18.9%·3F 11.9%)로는 계수가 "
        "**0.63**이고, 같은 건물 안에서 점포 기준이 면적 기준의 **1.62배**다(327동 중앙). "
        "즉 §0-M 의 '층 축은 다 썼다'는 절반만 맞다 — 어느 층이 비었나는 다 썼고 **무엇으로 "
        "가중하나**는 안 건드렸다. 다음 레버는 **R-ONE 소규모상가 서울 평균 수집**(rone_rent "
        "가 지금 54거점만 필터한다 · `rone_cls` 상위 계층 행을 같이 받으면 된다) — 그래야 두 "
        "기준이 같은 축에 선다. → docs/feature-posting.md §0-N. "
        "폴백은 garak 1곳 5유닛뿐이고 "
        "`area_basis`·`revenue_basis` 로 어느 모델이 돌았는지 드러난다",
        auto=False,
        evidence=("docs/feature-posting.md §0-I · services/posting_revenue.py · "
                  "data/pipelines/build_posting_store_area.py · "
                  "apps/backend/tests/test_posting_revenue.py (17건) · "
                  "scripts/posting_cost_sensitivity.py::_shipped"),
    ))
    return t


# ─────────────────────────── Program ───────────────────────────

def _context_kinds() -> dict[str, int]:
    """program_content_context.csv 의 kind 접두별 보유 거점 수."""
    import csv

    out: dict[str, int] = {}
    for p in GOLD.glob("*/program_content_context.csv"):
        try:
            with p.open(encoding="utf-8-sig", newline="") as f:
                kinds = {(r.get("kind") or "").split(":")[0] for r in csv.DictReader(f)}
        except OSError:
            continue
        for k in kinds:
            out[k] = out.get(k, 0) + 1
    return out


def program_track(total: int) -> Track:
    """대상 재정의(2026-08-16) 기준.

    Program 의 대상은 **공실에 창업할 기업**이다. 게이트도 그 기준으로 센다 —
    옛 정의(영업 중 점주 / 324개 구역 감성)로 재면 이미 끝난 것처럼 보인다.
    """
    t = Track("Program", "Phase 6-2 (공실 창업 기업 대상)")
    kinds = _context_kinds()

    t.gates.append(Gate(
        "생성 엔진 · 화면 · HA 검증", 1.0,
        "POST /marketing/generate + ProgramStudio + ha_guard 후처리 — 기반은 서 있다",
        auto=False, evidence="services/marketing.py · services/ha_guard.py · pages/ProgramStudio.tsx",
    ))

    ctx = kinds.get("blog_keyword", 0)
    t.gates.append(Gate(
        "상권 콘텐츠 컨텍스트", ctx / total if total else 0.0,
        f"{ctx}/{total}거점 — 블로그 키워드·업종 분포 (CSV·표준라이브러리 서빙)",
    ))

    dem = kinds.get("demand", 0)
    t.gates.append(Gate(
        "상권 수요신호 결합", dem / total if total else 0.0,
        f"{dem}/{total}거점 — TRDAR 시간대·연령·성별. 리뷰가 없는 대상에게 근거를 대는 "
        "자리이자, 온라인(전환 구간)·오프라인(빈 구간) 두 출력이 갈리는 표다",
    ))

    tr = kinds.get("trend", 0)
    t.gates.append(Gate(
        "검색 트렌드 라벨 (HA 안전장치)", tr / total if total else 0.0,
        f"{tr}/{total}거점 — 라벨이 없으면 ha_guard 의 트렌드 역행 검사가 **조용히 통과**한다. "
        "거점 단위 수집(naver_datalab --hubs) + build_program_trend 로 켰다",
    ))

    # 이 게이트는 2026-08-23 까지 **선언**이었고, 그래서 "공실 유닛 49/54" 라고 적힌 채
    # 08-22 의 54/54 완주를 두 번의 상태 점검 동안 놓쳤다. 층마다 배선의 흔적을
    # 코드에서 직접 센다 — 문구만 고쳐서는 올라가지 않게.
    mkt_src = (ROOT / "apps/backend/app/services/marketing.py").read_text(encoding="utf-8")
    profile_src = (ROOT / "apps/backend/app/schemas/marketing.py").read_text(encoding="utf-8")
    site_mod = ROOT / "apps/backend/app/services/program_site.py"
    # ① 자리 — 모듈이 산출물을 읽고, marketing 이 실제로 그 모듈을 부른다
    site_ok = (site_mod.exists()
               and "vacant_units.json" in site_mod.read_text(encoding="utf-8")
               and "program_site" in mkt_src)
    # ② 상권 — 기존 컨텍스트 빌더
    market_ok = "_district_context" in mkt_src
    # ③ 창업계획 — 스키마에 필드가 **있는 것만으로는 안 센다.** ①층과 같은 기준으로,
    # 모듈이 있고 marketing 과 ha_guard 가 실제로 그것을 부르는지까지 본다.
    # 필드만 보면 계약을 적어 두고 아무도 안 읽는 상태가 100% 로 잡힌다.
    venture_mod = ROOT / "apps/backend/app/services/program_venture.py"
    ha_src = (ROOT / "apps/backend/app/services/ha_guard.py").read_text(encoding="utf-8")
    venture_ok = (venture_mod.exists()
                  and all(f in profile_src for f in ("budget", "open_date"))
                  and "program_venture" in mkt_src
                  and "program_venture" in ha_src)
    done = [n for n, ok in (("자리", site_ok), ("상권", market_ok),
                            ("창업계획", venture_ok)) if ok]
    miss = [n for n in ("자리", "상권", "창업계획") if n not in done]
    t.gates.append(Gate(
        "입력 계약 3층 (자리·상권·창업계획)", len(done) / 3,
        f"{'·'.join(done)}층 배선됨" + (f" / {'·'.join(miss)}층 미구현" if miss else "")
        + ". 자리층은 08-23 오전(services/program_site + GET /marketing/sites), "
        "**창업계획층은 08-23 오후**(services/program_venture)에 붙였다. "
        "③층은 앞의 둘과 성격이 다르다 — 아직 없는 가게의 강점은 어떤 데이터에도 "
        "없어서 **기업이 넣는다**. 그래서 수집이 아니라 계약·검증 과제다. "
        "이 층이 닫은 것: '방문 후기형 포스팅'. 08-23 오전에 스텁 문구는 고쳤지만 "
        "판정이 `reviews 가 비었는가` 라는 **추정**이었고, 그러면 리뷰를 아직 못 모은 "
        "영업 중인 가게가 개업 전으로 오인된다. ③층의 개업예정일이 있으면 **확정**이라, "
        "ha_guard 가 개업 전 생성물의 방문·후기·재방문 전제를 violation "
        "(`pre_open_visit_claim`)으로 잡는다. ③층을 안 준 요청은 `is_pre_open()` 이 "
        "None 이라 검사가 켜지지 않는다 — 모르는 것을 위반으로 만들면 기존 요청이 "
        "전부 깨진다. 예산은 ③층에만 절대액이 있고(출력 budget_share 는 int 퍼센트라 "
        "구조적으로 절대액이 못 들어간다) 그 범위를 HA allowed_text 에 실어, 기업이 준 "
        "예산을 인용한 문장이 '지어낸 금액'으로 폐기되지 않게 했다. "
        "⚠ `strengths` 는 검증된 사실이 아니라 **기업 주장**이라 컨텍스트에 그렇게 "
        "밝혀 싣는다 — 우리가 관측한 수치와 같은 자리에 두면 근거가 오염된다",
        evidence=("docs/feature-program.md §0-B · services/program_venture.py · "
                  "apps/backend/tests/test_program_venture.py (13건)"),
    ))

    t.gates.append(Gate(
        "출력 분리 (퍼포먼스 / 상권활성화)", 1.0,
        "배선 완료 2026-08-23. ChannelPlan 에 자리를 냈다 — 온라인은 target·"
        "budget_share·kpi, 오프라인은 timing·actors·mode. LLM 계약은 둘로 갈랐고"
        "(LLMPerformancePlan / LLMActivationPlan) API 응답은 한 모양을 유지해 프론트가 "
        "안 깨진다. 예산은 **int 퍼센트**라 '월 30만원' 같은 절대액이 구조적으로 못 "
        "들어간다 — 원칙을 문구가 아니라 타입으로 강제한다. 충돌하던 신규 행사 제안 "
        "금지 조항은 없애지 않고 mode 로 갈랐다: cite(기존 인용, 사실 주장) · "
        "propose(신규 공동 행사, 빈 시간대 수치 요구) · own(매장 자체 접점, 행사 아님). "
        "서버 검증 4종 신설(fabricated_event violation + unsupported_event_proposal · "
        "missing_actors · budget_share_mismatch warning). own 은 오탐 대조 테스트가 "
        "찾아낸 것이다 — 없으면 입간판 제안이 '수치 없는 행사 제안'으로 잘못 걸린다. "
        "곁가지로 리뷰 없는 입력(=공실)에 '방문 후기형 포스팅'을 제안하던 스텁을 고쳤다. "
        "⚠ 근본 해소는 아니다 — 입력 계약 ③층(창업계획)은 여전히 미구현이다",
        auto=False,
        evidence=("docs/feature-program.md §0-F · apps/backend/tests/"
                  "test_program_output_split.py (14건) · services/ha_guard.py"),
    ))
    return t


# ─────────────────────────── 출력 ───────────────────────────

def _bar(pct: float, width: int = 20) -> str:
    fill = round(pct / 100 * width)
    return "█" * fill + "·" * (width - fill)


def main() -> int:
    total = _hubs()
    tracks = [page_track(total), platform_track(), posting_track(total), program_track(total)]

    if "--json" in sys.argv:
        print(json.dumps({
            "hubs": total,
            "tracks": [{
                "name": t.name, "phase": t.phase, "pct": round(t.pct, 1),
                "gates": [{"name": g.name, "value": round(g.value, 3), "auto": g.auto,
                           "detail": g.detail, "evidence": g.evidence} for g in t.gates],
            } for t in tracks],
        }, ensure_ascii=False, indent=1))
        return 0

    print("PPPP 진행률 — 산출물에서 계산 (거점 %d)" % total)
    print("=" * 78)
    for t in tracks:
        print(f"\n{t.name}  {t.pct:5.1f}%  {_bar(t.pct)}   {t.phase}")
        for g in t.gates:
            tag = "자동" if g.auto else "선언"
            print(f"   [{tag}] {g.value:5.1%}  {g.name}")
            print(f"          └ {g.detail}")
            if g.evidence:
                print(f"            근거: {g.evidence}")

    print("\n" + "=" * 78)
    # 이 줄은 진행률 내림차순일 뿐인데 "진행 순서"로 적혀 있어서 **작업 순서로 오독**된다
    # (2026-08-17 실제로 그렇게 읽혔다). 진행률이 높은 트랙을 먼저 하라는 뜻이 아니다 —
    # 오히려 뒤처진 트랙이 다음 차례인 경우가 많다. 그래서 이름을 사실대로 바꾸고,
    # 작업 순서는 의존 방향으로 결정된 값을 따로 적는다.
    rank = " > ".join(f"{t.name} {t.pct:.0f}%" for t in sorted(tracks, key=lambda x: -x.pct))
    print(f"진행률 순위: {rank}")
    # 의존 방향: Page 의 공실 유닛이 Posting·Program 의 재료이고, Program 의 대상은
    # 'Posting(창업)할 기업'이라 Posting 이 앞선다. Co.I(공실에 어떤 업종이 들어와야
    # 하는지)는 별도 단계가 아니라 Platform 의 업종추천 그 자체다 — 독립 트랙으로 세면
    # 이미 서빙 중인 것을 새로 만들려 하게 된다.
    print("작업 순서: Platform > Page > Posting > Program  (의존 방향 · 진행률과 무관)")
    dec = sum(t.declared for t in tracks)
    tot = sum(len(t.gates) for t in tracks)
    print(f"게이트 {tot}개 중 선언 {dec}개 — 선언이 많을수록 이 숫자를 믿을 이유가 줄어든다.")
    print("가중치는 두지 않았다(전부 동일 가중). 평균이 아니라 게이트를 보고 판단할 것.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

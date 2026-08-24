"""[Page] 행정동 24시간 생활인구 — 수집기·파이프라인이 **조용히 실패하지 않는지**.

실행: (레포 루트에서) python -m pytest data/tests/test_page_footfall_hourly.py -q

## 이 스위트가 지키는 것

이 배선의 위험은 예외가 아니라 **침묵**이다. 2026-08-24 에 실제로 셋 다 밟았다:

1. **코드 체계가 다르다** — 카카오는 10자리(`1168051000`), 서울 생활인구는
   8자리(`11680510`). 정규화가 없으면 필터가 한 행도 못 맞히면서 오류도 안 나고,
   날짜마다 "0행 저장" 으로 끝난다.
2. **결손이 0 명으로 새어든다** — 거점이 행정동 여러 개에 걸치는데 하나가 결측이면,
   가중치 합으로 나누지 않으면 "사람이 없는 시간대" 가 만들어진다.
3. **부분 매핑으로 받은 Bronze 가 영구화된다** — `hub_adong` 이 일부 거점만 담고
   있을 때 받은 파일을 존재만 보고 건너뛰면 결손이 굳는다.

셋 다 값이 그럴싸하게 나오므로 눈으로는 못 잡는다. 그래서 테스트로 잡는다.
"""
from __future__ import annotations

import json

from data.collectors import living_population_hourly as C
from data.pipelines import build_page_footfall_hourly as P


# ── ① 행정동 코드 정규화 ───────────────────────────────────────────
def test_adong8_truncates_kakao_10digit():
    """카카오 10자리는 뒤 '00' 을 떼고 서울 8자리가 된다 — 실측 대조로 확인한 규칙."""
    assert C.adong8("1168051000") == "11680510"   # 신사동
    assert C.adong8("1165054000") == "11650540"
    assert C.adong8("1168052100") == "11680521"


def test_adong8_passes_through_seoul_8digit():
    """이미 8자리면 그대로 — 양쪽에 같은 함수를 걸어도 안전해야 한다(멱등)."""
    assert C.adong8("11680510") == "11680510"
    assert C.adong8(C.adong8("1168051000")) == "11680510"


def test_adong8_does_not_mangle_unexpected_shapes():
    """예상 밖 모양은 **자르지 않는다.** 멋대로 자르면 틀린 동에 붙는다.

    호출부가 `len() != 8` 로 경고할 수 있어야 하므로 원형을 보존한다.
    """
    assert C.adong8("116805") == "116805"          # 너무 짧다
    assert C.adong8("1168051234") == "1168051234"  # 10자리지만 '00' 으로 안 끝난다


def test_hub_adong_codes_reads_hubs_key_only(monkeypatch):
    """문서 전체를 순회하면 `source`·`weight` 같은 주석 키까지 코드로 집는다."""
    monkeypatch.setattr(C, "load_hub_adong",
                        lambda: {"garosugil": {"1168051000": {"weight": 1.0}}})
    assert C.hub_adong_codes() == {"11680510"}


# ── ② 주말 판정 ────────────────────────────────────────────────────
def test_weekend_is_saturday_and_sunday_only():
    assert P._is_weekend("20260801") is True    # 토
    assert P._is_weekend("20260802") is True    # 일
    assert P._is_weekend("20260731") is False   # 금
    assert P._is_weekend("20260804") is False   # 화


# ── ③ 결손이 0 명으로 새지 않는다 ──────────────────────────────────
def _gold(monkeypatch, tmp_path, rows, hubs):
    """Bronze 한 날짜를 깔고 파이프라인을 돌려 산출물을 돌려준다."""
    bronze = tmp_path / "bronze"
    day = bronze / C.SLUG / "2026-07-31"
    day.mkdir(parents=True)
    (day / C.FILENAME).write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(P, "BRONZE", bronze)
    monkeypatch.setattr(P, "_OUT", tmp_path / "out.json")
    monkeypatch.setattr(P, "load_hub_adong", lambda: hubs)
    monkeypatch.setattr(P, "HUBS", list(hubs))
    return P.run()


def _rows(code: str, per_hour: float, date: str = "20260731") -> list[dict]:
    return [{"STDR_DE_ID": date, "TMZON_PD_SE": f"{h:02d}",
             "ADSTRD_CODE_SE": code, "TOT_LVPOP_CO": per_hour}
            for h in range(24)]


def test_missing_adong_does_not_dilute_to_zero(monkeypatch, tmp_path):
    """가중치 0.5 짜리 동 하나가 결측이어도 값은 **남은 동의 가중평균**이다.

    가중치 합으로 나누지 않으면 1000 × 0.5 = 500 이 되어, 실제로는 1000 명인
    시간대가 절반으로 보고된다 — '사람이 줄었다' 는 거짓 신호가 된다.
    """
    doc = _gold(
        monkeypatch, tmp_path,
        rows=_rows("11680510", 1000.0),        # 두 동 중 하나만 Bronze 에 있다
        hubs={"h": {"1168051000": {"weight": 0.5, "adm_nm": "신사동"},
                    "1168052100": {"weight": 0.5, "adm_nm": "논현1동"}}})
    by_hour = doc["districts"]["h"]["weekday"]["by_hour"]
    assert by_hour["12"] == 1000.0
    assert doc["districts"]["h"]["weekday"]["hours_covered"] == 24


def test_weighted_mean_across_two_adong(monkeypatch, tmp_path):
    """둘 다 있으면 가중평균 — 0.75×1000 + 0.25×2000 = 1250."""
    doc = _gold(
        monkeypatch, tmp_path,
        rows=_rows("11680510", 1000.0) + _rows("11680521", 2000.0),
        hubs={"h": {"1168051000": {"weight": 0.75},
                    "1168052100": {"weight": 0.25}}})
    assert doc["districts"]["h"]["weekday"]["by_hour"]["12"] == 1250.0


def test_absent_weekend_is_none_not_zero(monkeypatch, tmp_path):
    """금요일 하루만 있으면 주말은 **None** 이다. 0 으로 채우면 '아무도 없다'는 거짓."""
    doc = _gold(monkeypatch, tmp_path,
                rows=_rows("11680510", 1000.0, date="20260731"),
                hubs={"h": {"1168051000": {"weight": 1.0}}})
    we = doc["districts"]["h"]["weekend"]
    assert we["hours_covered"] == 0
    assert set(we["by_hour"].values()) == {None}
    assert we["peak"] is None          # 최번시를 지어내지 않는다
    assert we["hour_share"] == {}      # 구성비도 만들지 않는다


def test_bronze_rows_are_normalized_before_join(monkeypatch, tmp_path):
    """Bronze 가 8자리, 매핑이 10자리여도 조인이 성립해야 한다.

    이 테스트가 깨지면 ①의 정규화가 한쪽에서 빠진 것이다 — 그때 산출물은
    예외 없이 전부 None 이 되어 '데이터가 아직 없다' 처럼 읽힌다.
    """
    doc = _gold(monkeypatch, tmp_path,
                rows=_rows("11680510", 777.0),
                hubs={"h": {"1168051000": {"weight": 1.0}}})
    assert doc["districts"]["h"]["weekday"]["by_hour"]["00"] == 777.0


def test_peak_reports_trough_ratio(monkeypatch, tmp_path):
    """최번/최한 배수 — 1 에 가까우면 시간 축이 무의미한 거점이라는 신호."""
    rows = _rows("11680510", 100.0)
    for r in rows:
        if r["TMZON_PD_SE"] == "15":
            r["TOT_LVPOP_CO"] = 300.0
    doc = _gold(monkeypatch, tmp_path, rows=rows,
                hubs={"h": {"1168051000": {"weight": 1.0}}})
    peak = doc["districts"]["h"]["weekday"]["peak"]
    assert peak["hour"] == "15"
    assert peak["peak_trough_ratio"] == 3.0


# ── ④ 부분 매핑으로 받은 Bronze 는 다시 받는다 ────────────────────
def test_already_rejects_file_collected_with_fewer_codes(monkeypatch, tmp_path):
    """3동 시절 받은 파일(72행)은 150동 기준으로는 '있음' 이 아니다."""
    monkeypatch.setattr(C, "BRONZE", tmp_path)
    day = tmp_path / C.SLUG / "2026-07-31"
    day.mkdir(parents=True)
    (day / C.FILENAME).write_text(json.dumps([{}] * 72), encoding="utf-8")

    assert C._already("20260731", codes={f"{i:08d}" for i in range(3)}) is True
    assert C._already("20260731", codes={f"{i:08d}" for i in range(150)}) is False


def test_already_false_when_file_absent_or_broken(monkeypatch, tmp_path):
    """없거나 깨진 파일은 '없음' 으로 본다 — 깨진 JSON 을 완성으로 세면 안 된다."""
    monkeypatch.setattr(C, "BRONZE", tmp_path)
    assert C._already("20260731", codes={"11680510"}) is False

    day = tmp_path / C.SLUG / "2026-07-31"
    day.mkdir(parents=True)
    (day / C.FILENAME).write_text("{ 깨진", encoding="utf-8")
    assert C._already("20260731", codes={"11680510"}) is False

"""상권 행사가 생성 컨텍스트에 실리는지 (services/marketing._events_context).

## 왜 이 검사가 필요한가

행사 785건이 Gold 에 있는데 컨텍스트에 들어가지 않아, 오프라인 제안이 "상권
플리마켓/팝업 부스 참여" 같은 **어느 상권에나 해당하는 말**로 나왔다. 실데이터를
수집해 놓고 쓰지 않으면 수집하지 않은 것과 같다.

## 세 경우를 가르는 것이 요점이다

    None(Gold 미적재)   아무 말도 하지 않는다 — 모르는 것을 "없다"고 하면 안 된다
    [](예정 행사 없음)   **명시적으로 없다고 말하고 제안을 금지한다** — 침묵하면 LLM 이
                        일반론으로 행사를 지어낸다(고치려던 바로 그 증상)
    목록 있음            가까운 순 상위 N건 + **거리**

거리가 특히 중요하다. 이 API 는 공공·문화시설 행사 중심이라 가두 상권 커버리지가
낮아서, 가로수길 2건은 둘 다 800m 밖이다. 거리를 빼면 남의 동네 행사가 "우리 골목
행사"로 둔갑한다.
"""
from __future__ import annotations

from tests.conftest import _act, _perf

import pytest

from app.services import marketing as mkt


def test_missing_gold_says_nothing():
    """Gold 미적재(None)면 침묵한다 — '행사 없음'은 모르는 것을 안다고 주장하는 것이다."""
    assert mkt._events_context(None) is None


def test_empty_events_forbid_fabrication(monkeypatch):
    """예정 행사가 0건이면 없다고 **말하고** 제안을 금지한다.

    빈 목록에 침묵하면 LLM 이 "플리마켓 참여"를 지어낸다 — 이 함수를 만든 이유다.
    """
    from app.services import events
    monkeypatch.setattr(events, "for_district", lambda d: [])

    ctx = mkt._events_context("hongdae-yeonnam")
    assert ctx and "없다" in ctx
    assert "제안하지 말 것" in ctx, "없다고만 하면 LLM 이 일반론으로 채운다"


def test_none_from_service_is_silent(monkeypatch):
    """서비스가 None(미적재)을 주면 컨텍스트에 행사 줄 자체가 없다."""
    from app.services import events
    monkeypatch.setattr(events, "for_district", lambda d: None)
    assert mkt._events_context("garosugil") is None


def test_far_events_are_excluded_not_just_labelled(monkeypatch):
    """걸어갈 거리 밖 행사는 **싣지 않는다** — 거리만 붙여 싣던 것을 2026-08-16 에 바꿨다.

    예전에는 957m 행사를 거리와 함께 실었지만, 그래도 LLM 이 "우리 골목 행사"처럼 썼다.
    이제는 목록에서 빼고 "걸어갈 거리가 아니다"를 명시한다 — 없는 근거로 제안하는 것을
    막는 쪽이 정보를 조금 잃는 것보다 낫다.
    """
    from app.services import events
    monkeypatch.setattr(events, "for_district", lambda d: [
        {"n": "재즈 공연", "when": "2026-08-06~2026-08-20",
         "place": "재즈클럽그루브", "distance_m": 957},
    ])

    ctx = mkt._events_context("garosugil")
    assert "재즈 공연" not in ctx, "걸어갈 거리 밖 행사가 목록에 실렸다"
    assert "957m" in ctx, "가장 가까운 거리는 밝혀야 한다"
    assert "제안을 하지 말 것" in ctx


def test_nearest_events_first_and_capped(monkeypatch):
    """가까운 순 상위 N건만 — 도심 거점(ikseon 78건)이 컨텍스트를 잠식하면 안 된다."""
    from app.services import events
    rows = [{"n": f"행사{i}", "when": "2026-08-01~2026-08-31",
             "place": "장소", "distance_m": (20 - i) * 50} for i in range(20)]
    monkeypatch.setattr(events, "for_district", lambda d: rows)

    ctx = mkt._events_context("ikseon")
    assert ctx.count(";") == mkt._MAX_CONTEXT_EVENTS - 1, "행사 수 상한이 안 걸렸다"
    assert "행사19" in ctx, "가장 가까운 행사가 빠졌다"
    assert "행사0" not in ctx, "가장 먼 행사가 실렸다"


def test_missing_distance_does_not_crash(monkeypatch):
    """거리가 없는 행사(시드 잔재)도 죽지 않고 장소만 싣는다."""
    from app.services import events
    monkeypatch.setattr(events, "for_district", lambda d: [
        {"n": "행사", "when": "2026-08-01~2026-08-31", "place": "장소", "distance_m": None},
    ])
    ctx = mkt._events_context("garosugil")
    assert ctx and "장소" in ctx and "거점에서" not in ctx


def test_events_reach_district_context():
    """실제 Gold 에서도 행사 줄이 상권 컨텍스트에 합류한다 (통합)."""
    ctx = mkt._district_context("garosugil")
    if ctx is None:
        pytest.skip("gold/garosugil 미적재")
    assert "상권 행사" in ctx, "행사가 컨텍스트에 없다 — 오프라인 제안이 공허해진다"


def test_cache_key_covers_events_file():
    """캐시 키가 행사 Gold 의 mtime 을 포함한다.

    행사가 컨텍스트에 합류하면서 입력이 두 파일이 됐다. program_content_context 만
    보면 행사 파이프라인만 다시 돌린 경우 무효화가 안 돼 낡은 카피가 남는다.
    """
    from app.services import events

    if not events.is_available():
        pytest.skip("gold/platform_events.json 미적재")
    assert events.source_mtime() > 0
    # 행사 mtime 이 키에 섞여 있으므로, 컨텍스트 파일이 없는 거점이라도 0 이 아니다
    assert mkt._context_mtime("garosugil") >= events.source_mtime()


def test_event_fee_is_not_fabricated_price():
    """컨텍스트에 실린 금액을 인용한 것은 지어낸 가격이 아니다 (HA 검증기 연계).

    행사가 컨텍스트에 들어오면서 요금·기간의 숫자가 거기 실린다. 이걸 근거에서 빼면
    정상 인용이 violation 으로 폐기된다.
    """
    from app.schemas.marketing import (LLMActivationPlan, LLMPerformancePlan,
                                       LLMStoreMarketing)
    from app.services import ha_guard

    ctx = "상권 행사(공공 문화행사 실데이터, 가까운 순): 재즈 공연(참가비 5,000원, 거점에서 957m)"
    parsed = LLMStoreMarketing(
        tone_keywords=["재즈"],
        online=[_perf(channel="인스타그램", content="공연 연계 게시",
                               rationale="인근 행사와 시간대를 맞춘다")],
        offline=[_act(channel="입간판", content="참가비 5,000원 공연 안내 병기",
                                rationale="행사 관람객 동선을 잡는다")],
        ha_check="점검 통과")

    findings = ha_guard.check_store(parsed, {"name": "가게", "menu": [], "reviews": []}, ctx)
    assert "fabricated_price" not in {f.code for f in findings}


def test_context_reads_without_pandas(monkeypatch):
    """상권 컨텍스트가 **pandas 없이** 읽힌다 — 프로덕션 무동작 회귀 방지.

    2026-08-06 실사고: 서빙 코드가 `import pandas` 로 시작해 파케이를 읽었는데
    배포(Vercel 서버리스)에는 pandas 도 pyarrow 도 없다. import 실패가 폴백에
    삼켜져 컨텍스트가 **항상 None** 이었고, 상권 단위 LLM 경로는 프로덕션에서
    한 번도 돈 적이 없다. 화면은 시드 카피를 보여주므로 눈으로는 알 수 없었다.

    여기서는 pandas import 자체를 막아 배포 환경을 흉내 낸다.
    """
    import builtins

    real_import = builtins.__import__

    def no_pandas(name, *args, **kwargs):
        if name in ("pandas", "pyarrow"):
            raise ImportError(f"{name} 은 배포 환경에 없다 (테스트가 막았다)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_pandas)

    ctx = mkt._district_context("garosugil")
    if ctx is None:
        pytest.skip("gold/garosugil 컨텍스트 CSV 미적재")
    assert "키워드" in ctx or "업종" in ctx, "pandas 없이 컨텍스트를 못 읽었다"


def test_context_artifact_is_csv_not_parquet():
    """서빙 산출물이 CSV 로 존재한다 — 파케이로 되돌아가면 배포에서 조용히 죽는다."""
    from pathlib import Path

    gold = Path(__file__).resolve().parents[3] / "data" / "gold"
    if not (gold / "garosugil").exists():
        pytest.skip("gold 미적재")
    csvs = list(gold.glob("*/program_content_context.csv"))
    parquets = list(gold.glob("*/program_content_context.parquet"))
    assert csvs, "서빙용 CSV 가 없다"
    assert not parquets, (
        f"파케이가 남아 있다({len(parquets)}개) — 서빙 코드는 CSV 만 읽으므로 "
        "두 벌이 되면 반드시 어긋난다")


def test_runtime_gold_artifacts_are_not_gitignored():
    """Runtime Gold artifacts must stay deployable through git tracking rules."""
    import subprocess
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    gold = repo / "data" / "gold"
    if not gold.exists() or not any(gold.iterdir()):
        pytest.skip("data/gold is empty")

    patterns = (
        "*/program_content_context.csv",
        "*/page_building_master.geojson",
        "*/building_history.json",
        "*/coverage.json",
        # 2026-08-15 추가 — gold_vacancy.anchor_of 가 읽는데 목록에 없어서, 앵커가
        # 프로덕션에서 garosugil 말고는 전부 None 이던 것을 이 테스트가 놓쳤다.
        "*/calibration.json",
    )
    artifacts = [
        path
        for pattern in patterns
        for path in sorted(gold.glob(pattern))
        if path.is_file()
    ]
    if not artifacts:
        pytest.skip("runtime Gold artifacts are missing")

    for artifact in artifacts:
        rel = artifact.relative_to(repo).as_posix()
        try:
            result = subprocess.run(
                ["git", "check-ignore", "-q", rel],
                cwd=repo,
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            pytest.skip("git is not available")

        if result.returncode == 128:
            pytest.skip("not a git repository or git check-ignore failed")

        assert result.returncode == 1, (
            f"{rel} ignore 되면 프로덕션만 조용히 폴백한다"
        )


def test_gap_band_events_are_surfaced_first(monkeypatch):
    """빈 시간대에 열리는 행사가 있으면 그것만 싣고, 그 사실을 밝힌다.

    수요신호(유동-매출 격차)와 행사 시각이 맞물리는 것이 오프라인 제안의 근거다.
    교집합을 못 내면 "상권 플리마켓 참여" 같은 어느 상권에나 해당하는 말로 돌아간다.
    """
    from app.services import events
    monkeypatch.setattr(events, "for_district", lambda d: [
        {"n": "아침전시", "when": "2026-08-01~2026-08-31", "place": "A",
         "distance_m": 200, "time": "10:00 ~ 12:00", "tm": ["06_11", "11_14"]},
        {"n": "저녁공연", "when": "2026-08-01~2026-08-31", "place": "B",
         "distance_m": 100, "time": "19:30", "tm": ["17_21"]},
    ])

    ctx = mkt._events_context("garosugil", gap_band="06_11")
    assert "아침전시" in ctx
    assert "저녁공연" not in ctx, "빈 시간대와 무관한 행사가 섞였다"
    assert "6~11시" in ctx and "열리는" in ctx
    assert "10:00 ~ 12:00" in ctx, "운영 시각을 실어야 시간대 근거가 검증된다"


def test_no_gap_band_match_says_so(monkeypatch):
    """근처에 행사가 있어도 빈 시간대에 없으면 **없다고 밝힌다**.

    침묵하면 LLM 이 시간대를 맞춘 것처럼 쓴다 — 없는 근거를 주장하는 셈이다.
    """
    from app.services import events
    monkeypatch.setattr(events, "for_district", lambda d: [
        {"n": "저녁공연", "when": "2026-08-01~2026-08-31", "place": "B",
         "distance_m": 100, "time": "19:30", "tm": ["17_21"]},
    ])

    ctx = mkt._events_context("garosugil", gap_band="06_11")
    assert "저녁공연" in ctx, "가까운 행사는 실어야 한다"
    assert "열리는 행사는 없다" in ctx

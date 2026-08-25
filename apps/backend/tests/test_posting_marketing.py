"""Posting(코파일럿 어댑터) / Program(가게 단위 생성) API 테스트."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import _act, _perf

client = TestClient(app)
V1 = "/api/v1"


@pytest.fixture(autouse=True)
def _isolate_marketing_cache():
    """상권 콘텐츠 LLM 캐시를 테스트마다 비운다.

    캐시가 없으면 이 엔드포인트는 호출마다 LLM 을 치므로(실측 12~17초) 캐시는 필요하다.
    다만 테스트끼리는 격리돼야 한다 — 앞 테스트가 채운 캐시를 폴백 테스트가 물면
    "LLM 실패 시 시드로 떨어진다"를 검증하지 못한다(2026-08-01 실제로 발생).
    """
    from app.services import marketing as mkt
    mkt.clear_district_cache()
    yield
    mkt.clear_district_cache()


def test_simulate_revenue_fallback():
    """코파일럿 미설정 시 3-Tier 폴백으로 응답한다 (서울 13 Page 시드)."""
    r = client.post(f"{V1}/ai/simulate-revenue", json={"district_id": "garosugil"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "fallback-3tier"
    assert set(body["scenarios"].keys()) == {"premium", "value", "factory"}
    for sc in body["scenarios"].values():
        # 회수기간 = 초기투자(백만원)×100 ÷ 월순익(만원). 단위를 섞으면 100배 작아진다
        # (2026-08-01 이전 버그 — 화면에 "회수 0개월"로 찍혔다).
        #
        # 2026-08-22: roi 는 **반올림 전 원값**으로 계산하고 표시값만 반올림한다
        # (반올림이 추천을 뒤집던 것을 막는다 — districts.recommend_tier 참조).
        # 그래서 반올림된 invest_mn·month_net 으로 되짚으면 정확히 일치하지 않는다.
        # 여기서 지킬 불변식은 "단위가 맞는가"이므로 반올림 오차폭까지 허용한다.
        if sc["month_net"] > 0:
            approx = sc["invest_mn"] * 100 / sc["month_net"]
            assert sc["roi_months"] == pytest.approx(approx, rel=0.05), (
                f"{sc['tier']} roi {sc['roi_months']} vs 표시값 재계산 {approx:.2f}")
            assert sc["roi_months"] >= 0.5, (
                f"{sc['tier']} 회수 {sc['roi_months']}개월 — 단위 혼용 회귀 의심")
            assert sc["viable"] is True
        else:
            assert sc["roi_months"] == 99.0   # 적자 시나리오 표기
            assert sc["viable"] is False
        assert sc["basis"], "회수기간이 어떤 비용까지 넣고 계산됐는지 밝혀야 한다"


def test_simulate_revenue_strategy_filter():
    r = client.post(f"{V1}/ai/simulate-revenue",
                    json={"district_id": "garosugil", "strategy": "value"})
    assert r.status_code == 200
    assert set(r.json()["scenarios"].keys()) == {"value"}


def test_simulate_revenue_unknown_district_404():
    r = client.post(f"{V1}/ai/simulate-revenue", json={"district_id": "nope"})
    assert r.status_code == 404


# ── Posting 폴백 입력의 실데이터 배선 (2026-08-01) ────────────────────────────
# rent 는 R-ONE 임대료, foot 은 유동인구+시드 혼합. area·prem 은 소스가 없어 시드.


def _gold_loaded() -> bool:
    from app.services import posting_inputs
    return posting_inputs.is_available()


requires_gold = pytest.mark.skipif(
    not _gold_loaded(),
    reason="gold/platform_posting_inputs.json 미적재 — build_posting_inputs 실행 필요")


@requires_gold
def test_postings_declare_input_provenance():
    """유닛마다 필드별 입력 출처를 밝혀야 한다 — 프록시를 실측으로 오독하면 안 된다."""
    postings = client.get(f"{V1}/commercial-districts/garosugil/postings").json()
    assert postings
    for p in postings:
        src = p["inputs_source"]
        assert src["rent"] == "rone", "임대료가 R-ONE 실데이터가 아니다"
        # 2026-08-24: 거점 내 서열이 시드 → 최근접 상권 실측으로 바뀌었다.
        # 가로수길은 상권 3곳(신사·논현1·잠원)이라 실측으로 갈린다 — 여기가
        # `flpop+seed` 로 돌아갔다면 조용히 프록시로 후퇴한 것이다.
        # (거점별로 어느 쪽이 맞는지는 test_seed_fallback_only_where_trdar_
        #  cannot_differentiate 가 전 거점에 대해 지킨다.)
        assert src["foot"] == "flpop+trdar", f"거점 내 서열이 실측이 아니다: {src['foot']}"
        # 2026-08-24 실 인벤토리 배선: area 는 건축물대장(상업면적÷capacity),
        # prem 은 **값이 없다**. 둘 다 "있는 척"하면 안 되는 것은 그대로다 —
        # 다만 밝히는 내용이 달라졌다. "absent" 는 권리금 0 이 관측이 아니라
        # 전제라는 뜻이다(입력 계약으로 받으면 "contract" 가 된다).
        assert src["area"] == "gold-ledger", "면적이 대장 실측이 아니다"
        assert src["prem"] == "absent", "권리금 0 이 전제임을 밝히지 않는다"


@requires_gold
def test_simulate_carries_input_provenance():
    """시뮬레이션 응답도 입력 출처·기준분기를 함께 내려보낸다."""
    body = client.post(f"{V1}/ai/simulate-revenue", json={"district_id": "garosugil"}).json()
    assert body["inputs_source"]["rent"] == "rone"
    assert body["inputs_quarter"] and body["inputs_quarter"].isdigit()


@requires_gold
def test_rent_falls_with_floor():
    """같은 거점에서 상층 유닛의 평당 임대료는 1층보다 싸야 한다.

    R-ONE 소규모상가 임대료는 사실상 1층 기준이라, 층 계수 없이 그대로 곱하면
    3층이 1층과 같은 단가가 된다(2~8배 과대계상). 그 회귀를 막는다.
    """
    from app.services import districts as svc

    from app.services.posting_inputs import _floor_factor, _mixed_floor_factor

    base = _floor_factor("1F", None)
    checked = 0
    for floor in ("2F", "3F", "4F", "5F", "B1"):
        assert _floor_factor(floor, None) < base, f"{floor} 계수가 1F 이상이다"
        checked += 1
    assert checked == 5

    # ⚠ 2026-08-25: 실 인벤토리에 **실측 층 분포**(floor_mix)가 붙으면서 이 테스트의
    #   종전 형태가 틀린 것을 검사하게 됐다. 유닛의 `floor` 는 이제 한 층이 아니라
    #   범위 라벨("1~5F")이고, 임대료는 층 **면적 가중평균**으로 계산된다. 라벨로 정렬해
    #   비교하면 최빈층 2F 짜리 건물이 1F 짜리보다 비싸게 나올 수 있다(실제로 걸렸다:
    #   "myeongdong 2F 평당 26.7 >= 1F 24.0"). 라벨이 임대료를 정하지 않기 때문이고,
    #   그건 버그가 아니라 이 유닛이 **건물의 호실당 평균**이라는 뜻이다.
    #   그래서 모델이 실제로 주장하는 것을 검사한다 — 상층 비중이 큰 건물일수록 층
    #   가중계수가 낮다(= 평당 임대료가 싸다).
    mixed_checked = 0
    for did in ("garosugil", "myeongdong", "songridan"):
        for u in (svc.resolved_units(did) or []):
            mix = u.get("floor_mix")
            if not mix:
                continue
            factor, used_mix = _mixed_floor_factor(u, None)
            assert used_mix, f"{did} {u['id']} 가 floor_mix 를 들고도 안 썼다"
            # 1F 비중이 1.0 이 아닌 이상 계수는 1F 단독(1.00)보다 반드시 낮다.
            if float(mix.get("1F", 0.0)) < 0.999:
                assert factor < base, f"{did} {u['id']} 계수 {factor:.3f} >= 1F"
            mixed_checked += 1
    assert mixed_checked > 0, "실 인벤토리에 floor_mix 가 하나도 없다 — 배선이 풀렸다"


@requires_gold
def test_foot_keeps_within_district_structure():
    """유동인구 등급이 거점 안에서 평탄화되면 안 된다.

    flpop 은 거점 단위라 그대로 내리면 한 거점의 모든 유닛이 같은 등급이 된다
    (가로수길 고/고/중/저/중 → 전부 중). 그래서 ±1칸 보정을 한다.

    ⚠ 2026-08-24: 그 보정의 근거가 **시드 서열 → 최근접 상권 유동총량 실측** 으로
      바뀌었다. 거점당 상권이 1~9곳(중앙 3곳)이라 유닛 좌표로 상권을 잡으면 거점
      내부에서도 값이 갈린다. 아래 test_foot_ordering_is_measured_not_seeded 가
      그 전환을 지킨다.
    """
    from app.data.seoul_pages import DISTRICTS_BY_ID
    from app.services import districts as svc

    seed_feet = [u["foot"] for u in DISTRICTS_BY_ID["garosugil"]["units"]]
    live_feet = [u["foot"] for u in svc.resolved_units("garosugil")]
    assert len(set(seed_feet)) > 1, "시드 전제가 깨졌다 — 가로수길 foot 이 원래 균일하다"
    assert len(set(live_feet)) > 1, f"거점 내 등급이 평탄화됐다: {live_feet}"


@requires_gold
def test_resolve_does_not_mutate_seed():
    """실데이터 덮어쓰기가 시드 원본을 건드리면 안 된다(프로세스 전역 공유 dict)."""
    from app.data.seoul_pages import DISTRICTS_BY_ID
    from app.services import districts as svc

    before = [(u["rent"], u["foot"]) for u in DISTRICTS_BY_ID["garosugil"]["units"]]
    svc.resolved_units("garosugil")
    svc.resolved_units("garosugil")
    after = [(u["rent"], u["foot"]) for u in DISTRICTS_BY_ID["garosugil"]["units"]]
    assert before == after, "seoul_pages.DISTRICTS 가 변형됐다"


def test_falls_back_to_seed_when_gold_missing(monkeypatch):
    """Gold 미적재 환경(신규 클론 등)에서는 시드 프록시로 조용히 떨어진다."""
    from app.data.seoul_pages import DISTRICTS_BY_ID
    from app.services import districts as svc
    from app.services import posting_inputs

    monkeypatch.setattr(posting_inputs, "_cache", {})
    monkeypatch.setattr(posting_inputs, "_INPUTS_JSON",
                        posting_inputs._INPUTS_JSON.with_name("__absent__.json"))

    units = svc.resolved_units("garosugil")
    seed = DISTRICTS_BY_ID["garosugil"]["units"]
    assert [u["rent"] for u in units] == [u["rent"] for u in seed]
    assert all(u["inputs_source"]["rent"] == "seed" for u in units)
    monkeypatch.setattr(posting_inputs, "_cache", {})   # 뒤 테스트에 캐시 오염 방지


def test_generate_store_marketing_stub(monkeypatch):
    """LLM 키 미설정 시 규칙 기반 스텁이 StoreMarketing 스키마로 응답한다."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "")
    profile = {
        "name": "가로수 카페",
        "category": "카페",
        "district_id": "gangnam-garosugil",
        "reviews": ["분위기 좋은 카페", "커피 맛집 분위기 최고", "디저트 맛집"],
    }
    r = client.post(f"{V1}/marketing/generate", json=profile)
    assert r.status_code == 200
    body = r.json()
    assert body["store_name"] == "가로수 카페"
    assert body["source"] == "rule-stub"
    assert body["tone_keywords"]  # 리뷰에서 키워드 추출됨
    assert len(body["online"]) >= 1 and len(body["offline"]) >= 1
    assert all(p["kind"] == "online" for p in body["online"])
    assert all(p["kind"] == "offline" for p in body["offline"])


_PROFILE = {
    "name": "맡기다",
    "category": "F&B",
    "district_id": "hongdae-yeonnam",
    "reviews": ["사장님 손맛이 담긴 특제 소스", "우니 사시미가 인상적"],
}


def test_generate_store_marketing_llm(monkeypatch):
    """LLM 키 설정 시 _call_llm 결과가 StoreMarketing(source=llm)으로 매핑된다."""
    from app.core.config import settings
    from app.schemas.marketing import (LLMActivationPlan, LLMPerformancePlan,
                                       LLMStoreMarketing)
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    fake = LLMStoreMarketing(
        tone_keywords=["특제소스", "사시미"],
        online=[_perf(channel="인스타그램", content="릴스 게시", rationale="리뷰 근거")],
        offline=[_act(channel="전단", content="시식 이벤트", rationale="유동객 근거")],
        ha_check="균형·공생·공감 점검 통과",
    )
    monkeypatch.setattr(mkt, "_call_llm", lambda profile, tone, ctx, site=None, venture=None: fake)

    r = client.post(f"{V1}/marketing/generate", json=_PROFILE)
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "llm"
    assert body["tone_keywords"] == ["특제소스", "사시미"]
    assert body["online"][0]["kind"] == "online"
    assert body["offline"][0]["kind"] == "offline"


def test_generate_store_marketing_llm_error_falls_back(monkeypatch):
    """LLM 호출 실패 시 규칙 기반 스텁으로 폴백한다 (요청은 200 유지)."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    def boom(profile, tone, ctx):
        raise RuntimeError("api down")

    monkeypatch.setattr(mkt, "_call_llm", boom)

    r = client.post(f"{V1}/marketing/generate", json=_PROFILE)
    assert r.status_code == 200
    assert r.json()["source"] == "rule-stub"


def test_district_context_mapping():
    """gold 매핑에 있는 거점은 컨텍스트 문자열, 없는 거점은 None."""
    from app.services import marketing as mkt

    assert mkt._district_context("unknown-district") is None
    ctx = mkt._district_context("garosugil")
    # gold 적재 여부에 따라 None 또는 요약 문자열 — 적재된 경우 키워드 포함 검증
    if ctx is not None:
        assert "키워드" in ctx or "업종" in ctx or "트렌드" in ctx


def test_district_marketing_served(monkeypatch):
    """상권 단위 GET /marketing/{id} — LLM 키 없으면 시드 콘텐츠 + 시드 행사."""
    from app.core.config import settings

    # 키를 비워 네트워크 호출 없이 폴백 경로만 태운다(테스트는 외부 API 를 치지 않는다)
    monkeypatch.setattr(settings, "llm_api_key", "")

    r = client.get(f"{V1}/marketing/garosugil")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "seed"          # 온라인 콘텐츠는 LLM 키가 없어 시드
    assert body["online_contents"]
    # 행사는 별개 소스다 — 온라인 콘텐츠가 시드여도 행사는 실데이터일 수 있다
    assert body["events_source"] in {"seoul-open-data", "seed"}

    assert client.get(f"{V1}/marketing/nope").status_code == 404


def test_events_carry_real_fields_not_fabricated_metrics():
    """행사가 실데이터면 API 가 준 사실만 실려야 한다.

    시드는 좌표·일정과 함께 효과 지표(k2 "유입 +52%")·이해관계자 역할·HA 메모를
    달고 있었는데 셋 다 근거가 없다. 실데이터로 넘어오면서 버렸는지 확인한다.
    """
    from app.services import events as ev

    if not ev.is_available():
        pytest.skip("gold/platform_events.json 미적재 — build_events 실행 필요")

    body = client.get(f"{V1}/marketing/garosugil").json()
    assert body["events_source"] == "seoul-open-data"
    for e in body["events"]:
        assert e["n"] and e["lat"] and e["lng"] and e["when"], "실물 행사의 필수 필드 누락"
        assert e["place"], "장소가 없다 — 실데이터라면 있어야 한다"
        # 지어낸 값들은 넘어오면 안 된다
        assert e["k2"] is None, f"근거 없는 효과 지표가 실렸다: {e['k2']}"
        assert e["roles"] is None and e["ha"] is None


def test_district_marketing_llm_contents(monkeypatch):
    """Gold 컨텍스트가 있으면 온라인 콘텐츠는 LLM 생성분으로 교체된다(행사는 시드 유지)."""
    from app.core.config import settings
    from app.schemas.marketing import LLMDistrictContents
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(mkt, "_district_context", lambda d: "블로그 언급 키워드: 팝업(120건)")
    fake = LLMDistrictContents(
        online_contents=["가로수길 팝업 지도 #가로수길 #팝업"], ha_check="점검 통과")
    monkeypatch.setattr(mkt, "_call_district_llm", lambda name, sub, ctx: fake)

    body = client.get(f"{V1}/marketing/garosugil").json()
    assert body["source"] == "llm"
    assert body["online_contents"] == ["가로수길 팝업 지도 #가로수길 #팝업"]
    # 행사는 LLM 이 만들지 않는다 — 좌표·일정이 붙은 실물이라 별도 소스에서만 온다
    assert body["events_source"] in {"seoul-open-data", "seed"}
    assert all(e.get("lat") and e.get("lng") for e in body["events"])


def test_district_marketing_llm_error_falls_back(monkeypatch):
    """상권 콘텐츠 LLM 실패 시 시드 콘텐츠로 폴백한다 (요청은 200 유지)."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(mkt, "_district_context", lambda d: "블로그 언급 키워드: 팝업(120건)")

    def boom(name, sub, ctx):
        raise RuntimeError("api down")

    monkeypatch.setattr(mkt, "_call_district_llm", boom)

    r = client.get(f"{V1}/marketing/garosugil")
    assert r.status_code == 200
    assert r.json()["source"] == "seed"


def test_district_context_states_trend_direction():
    """상권 컨텍스트가 트렌드 **방향을 계산해** 넘기는지 — 트렌드 오독 회귀 방지.

    2026-08-01 사고: 컨텍스트가 원시 수치만 주자 LLM 이 하락 시계열을 보고
    "신사동을 찾는 발걸음이 다시 늘고 있는 요즘"이라고 썼다. 방향 판정을 서비스로
    옮겼으므로(`marketing._trend_summary`), 컨텍스트 문자열에 방향어가 박혀 있어야 한다.
    """
    from app.services import marketing as mkt

    ctx = mkt._district_context("garosugil")
    if not ctx or "검색 트렌드" not in ctx:
        pytest.skip("gold/garosugil 트렌드 미적재 — 방향을 검증할 입력이 없다")
    trend_line = next(ln for ln in ctx.splitlines() if ln.startswith("검색 트렌드"))
    assert any(w in trend_line for w in ("상승", "보합", "하락")), (
        f"트렌드에 방향 판정이 없다 — LLM 이 방향을 추측하게 된다: {trend_line!r}"
    )


def test_trend_summary_direction_rule():
    """방향 판정 규칙 — 최근 3개월 평균 vs 직전 3개월 평균, ±5% 밖이면 방향을 붙인다.

    2026-08-06: pandas 제거로 시그니처가 (name, [(key, value), …]) 로 바뀌었다.
    """
    from app.services import marketing as mkt

    def summarize(values: list[float]) -> str | None:
        return mkt._trend_summary("테스트", [
            (f"2026-{i + 1:02d}-01", v) for i, v in enumerate(values)
        ])

    assert "하락" in summarize([100, 100, 100, 50, 50, 50])
    assert "상승" in summarize([50, 50, 50, 100, 100, 100])
    assert "보합" in summarize([100, 100, 100, 101, 102, 101])
    # 6개 점이 없으면 방향을 만들지 않는다 — 근거 없는 방향보다 트렌드 생략이 낫다
    assert summarize([100, 90, 80, 70, 60]) is None


# ───────────── 메뉴 입력 + 가게 반자동 조회 (2026-08-03) ─────────────


def test_menu_reaches_llm_prompt(monkeypatch):
    """메뉴가 LLM 프롬프트에 실린다 — 스키마에만 있고 안 쓰이면 죽은 필드다."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    seen: dict = {}

    import app.services.marketing as m

    def spy(profile, tone, ctx, site=None, venture=None):
        seen["menu"] = profile.get("menu")
        seen["prompt"] = m._SYSTEM_PROMPT
        from app.schemas.marketing import (LLMActivationPlan, LLMPerformancePlan,
                                       LLMStoreMarketing)
        return LLMStoreMarketing(
            tone_keywords=["x"],
            online=[_perf(channel="a", content="b", rationale="c")],
            offline=[_act(channel="d", content="e", rationale="f")],
            ha_check="ok",
        )

    monkeypatch.setattr(mkt, "_call_llm", spy)
    r = client.post(f"{V1}/marketing/generate",
                    json={**_PROFILE, "menu": ["우니 사시미 32,000원", "맡김술상 55,000원"]})
    assert r.status_code == 200
    assert seen["menu"] == ["우니 사시미 32,000원", "맡김술상 55,000원"]
    assert "메뉴" in seen["prompt"], "시스템 프롬프트가 메뉴를 다루지 않는다"


def test_menu_quoted_verbatim_in_stub(monkeypatch):
    """스텁도 메뉴를 흘리지 않는다 — 첫 품목을 **적힌 그대로** 인용한다."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "")

    body = client.post(f"{V1}/marketing/generate", json={
        "name": "맡기다", "category": "이자카야", "menu": ["맡김술상 55,000원"],
    }).json()
    offline = " ".join(p["content"] for p in body["offline"])
    assert "맡김술상 55,000원" in offline


def test_lookup_routes_are_not_swallowed_by_district_route(monkeypatch):
    """/places·/reviews 가 /{district_id} 에 먹히지 않는다 (라우트 등록 순서).

    키를 비워 두는 이유는 네트워크를 타지 않기 위해서다 — 라우팅만 보면 되고,
    거점 라우트에 먹혔다면 404(unknown district)가 났을 것이다.
    """
    from app.core.config import settings
    monkeypatch.setattr(settings, "kakao_rest_api_key", "")
    monkeypatch.setattr(settings, "naver_client_id", "")

    r = client.get(f"{V1}/marketing/places", params={"query": "x"})
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "unavailable"
    r2 = client.get(f"{V1}/marketing/reviews", params={"name": "x"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["source"] == "unavailable"


def test_lookup_unavailable_when_keys_missing(monkeypatch):
    """키 미설정은 조용한 빈 목록이 아니라 source='unavailable' 로 드러난다."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "kakao_rest_api_key", "")
    monkeypatch.setattr(settings, "naver_client_id", "")
    monkeypatch.setattr(settings, "naver_client_secret", "")

    b = client.get(f"{V1}/marketing/places", params={"query": "맡기다"}).json()
    assert b["source"] == "unavailable" and b["note"]
    b2 = client.get(f"{V1}/marketing/reviews", params={"name": "맡기다"}).json()
    assert b2["source"] == "unavailable" and b2["note"]


def test_review_query_is_narrowed_by_dong(monkeypatch):
    """리뷰 질의에 주소의 동(洞)이 붙는다 — 동명이지 오염 방어의 1차선."""
    from app.core.config import settings
    from app.services import store_lookup as sl

    monkeypatch.setattr(settings, "naver_client_id", "id")
    monkeypatch.setattr(settings, "naver_client_secret", "secret")
    captured: dict = {}

    def fake_get(url, params, headers):
        captured["query"] = params["query"]
        return {"items": [{"title": "연남동 <b>맡기다</b> 후기",
                           "description": "오마카세가 좋았습니다 재방문 의사 있어요"}]}

    monkeypatch.setattr(sl, "_get_json", fake_get)
    out = sl.find_reviews("맡기다", "서울 마포구 연남동 260-2")
    assert captured["query"] == "연남동 맡기다"
    assert out["source"] == "naver-blog"
    # <b> 태그가 남으면 프롬프트에 마크업이 섞인다
    assert "<b>" not in out["reviews"][0]

    # 주소가 없으면 최소한 '서울'로는 좁힌다
    sl.find_reviews("맡기다", None)
    assert captured["query"] == "서울 맡기다"


def test_reviews_drop_posts_without_store_name(monkeypatch):
    """상호가 본문에 없는 글은 버린다 — 목록형 광고·타 지역 글이 이렇게 섞인다."""
    from app.core.config import settings
    from app.services import store_lookup as sl

    monkeypatch.setattr(settings, "naver_client_id", "id")
    monkeypatch.setattr(settings, "naver_client_secret", "secret")
    monkeypatch.setattr(sl, "_get_json", lambda *a, **k: {"items": [
        {"title": "연남동 맡기다 방문", "description": "오마카세 코스가 알찼습니다 추천해요"},
        {"title": "연남동 맛집 총정리", "description": "이번엔 다른 가게들을 모아봤습니다 참고하세요"},
    ]})
    out = sl.find_reviews("맡기다", "서울 마포구 연남동 260-2")
    assert len(out["reviews"]) == 1
    assert "제외했다" in (out["note"] or "")


def test_dong_extraction_handles_numbered_ga():
    """'을지로3가'처럼 숫자가 낀 주소도 뽑는다 (2026-08-03 회귀)."""
    from app.services.store_lookup import dong_of

    assert dong_of("서울 마포구 연남동 260-2") == "연남동"
    assert dong_of("서울 중구 을지로3가 1") == "을지로3가"
    assert dong_of(None) is None


# ── foot 거점 내 서열: 시드 → 최근접 상권 실측 (2026-08-24) ─────────────────
#
# `foot` 의 거점 **등급**은 처음부터 flpop 실측이었지만, 거점 **내부 서열**은 손으로
# 적은 시드였다(`_blend_foot` 의 seed_feet). 거점당 상권이 1~9곳이라 유닛 좌표에서
# 최근접 상권을 잡으면 그 서열도 실측으로 낼 수 있다. 이 묶음이 지키는 것:
#   1. 실측으로 가를 수 있으면 시드를 쓰지 않는다.
#   2. 못 가르면 **억지로 갈라 놓지 않고** 시드로 물러난다(없는 구조를 만들지 않는다).
#   3. 출처를 항상 밝힌다 — 프록시를 실측으로 오독하면 안 된다.

@requires_gold
def test_foot_ordering_is_measured_not_seeded():
    """대다수 유닛은 `flpop+trdar` 이어야 한다 — 시드가 기본이면 전환이 안 된 것이다."""
    from collections import Counter

    from app.services import districts as svc

    src = Counter()
    for d in svc.DISTRICTS:
        for u in svc.resolved_units(d["id"]) or []:
            src[u["inputs_source"]["foot"]] += 1
    assert src["flpop+trdar"] > src["flpop+seed"], dict(src)
    # 시드 잔존은 '상권으로 못 가르는 거점' 에 국한돼야 한다.
    assert src["flpop+seed"] / max(1, sum(src.values())) < 0.15, dict(src)


@requires_gold
def test_seed_fallback_only_where_trdar_cannot_differentiate():
    """시드로 물러난 거점은 **실제로** 최근접 상권이 하나여야 한다.

    이게 깨지면 가를 수 있는데도 시드를 쓰고 있다는 뜻이다 — 조용히 프록시로
    되돌아간 상태이므로 눈으로는 안 보인다.
    """
    from app.services import districts as svc
    from app.services import posting_inputs as pi

    for d in svc.DISTRICTS:
        units = svc.resolved_units(d["id"]) or []
        if not units or units[0]["inputs_source"]["foot"] != "flpop+seed":
            continue
        vals = pi._unit_trdar_flpop(d["id"], svc.DISTRICTS_BY_ID[d["id"]]["units"])
        known = {v for v in vals if v is not None}
        assert len(known) < 2, f"{d['id']}: 상권이 {len(known)}종인데 시드로 물러났다"


def test_measured_offsets_needs_two_distinct_values():
    """가를 수 없으면 None — 호출부가 시드로 물러나는 신호다."""
    from app.services import posting_inputs as pi

    assert pi._measured_offsets([]) is None
    assert pi._measured_offsets([100.0]) is None
    assert pi._measured_offsets([100.0, 100.0, 100.0]) is None   # 상권 1곳짜리 거점
    assert pi._measured_offsets([None, None]) is None


def test_measured_offsets_signs_follow_the_mean():
    """평균에서 ±15% 밖이면 한 칸, 안이면 제자리. 좌표 없는 유닛은 0(제자리)."""
    from app.services import posting_inputs as pi

    # 평균 200 → 100 은 -1, 300 은 +1, 205 는 밴드 안이라 0
    assert pi._measured_offsets([100.0, 300.0, 205.0, None]) == [-1, 1, 0, 0]


def test_apply_offset_clamps_at_grade_boundaries():
    """'고' 에서 +1, '저' 에서 -1 로 등급 밖으로 넘어가지 않는다."""
    from app.services import posting_inputs as pi

    assert pi._apply_offset("고", 1) == "고"
    assert pi._apply_offset("저", -1) == "저"
    assert pi._apply_offset("중", 1) == "고"
    assert pi._apply_offset("중", -1) == "저"


@requires_gold
def test_units_without_coords_do_not_crash():
    """좌표 결측 유닛이 섞여도 나머지 서열은 살아 있어야 한다."""
    from app.services import posting_inputs as pi

    units = [{"id": "a", "lat": None, "lng": None, "area": 10, "floor": "1F", "foot": "중"},
             {"id": "b", "lat": 37.5172, "lng": 127.0286, "area": 10, "floor": "1F", "foot": "고"}]
    vals = pi._unit_trdar_flpop("garosugil", units)
    assert vals[0] is None
    out = pi.resolve_units("garosugil", units)
    assert len(out) == 2 and all("foot" in u for u in out)


# ── 실 인벤토리 배선 (2026-08-24) ────────────────────────────────────────────
# 08-22 에 54/54거점 528유닛이 채워졌는데 resolved_units 가 시드만 읽어서 Posting
# 화면이 계속 손으로 적은 예시 위에서 돌았다. 배선 자체를 지키는 자리다.


@requires_gold
def test_postings_come_from_real_inventory_not_seed():
    """공실 유닛이 시드가 아니라 건축물대장 실측 인벤토리에서 와야 한다.

    유닛 id 로 판정한다 — 실 인벤토리는 `vu-{PNU 19자리}-{n}` 이고 시드는 그렇지
    않다. 건수·좌표로 보면 시드가 우연히 비슷해질 수 있지만 id 규칙은 안 겹친다.
    """
    from app.services import districts as svc

    units = svc.resolved_units("garosugil")
    assert units
    assert all(u["id"].startswith("vu-") for u in units), (
        f"시드 유닛이 섞였다: {[u['id'] for u in units if not u['id'].startswith('vu-')]}")


@requires_gold
def test_inventory_units_survive_tier_scenarios():
    """실 인벤토리 유닛에는 `prem` 이 **없다**(528/528 결측) — 계산이 죽으면 안 된다.

    `tier_scenarios` 가 `unit["prem"]` 을 첨자로 읽던 동안에는 배선하는 순간
    KeyError 였다. 0 을 전제로 돌되 그 사실이 출처에 드러나야 한다.
    """
    from app.services import districts as svc

    for did in ("garosugil", "myeongdong", "hongdae"):
        for u in (svc.resolved_units(did) or []):
            sc = svc.tier_scenarios(u, did)
            assert set(sc) == {"premium", "value", "factory"}
            assert u["inputs_source"]["prem"] == "absent"


@requires_gold
def test_prem_is_an_input_contract_not_a_collected_field():
    """권리금은 기업이 넣는다 — 주면 반영되고, 안 주면 0 전제임을 밝힌다.

    공개 통계가 없어(bronze 전수 확인) 수집으로 못 채우는 값이라, Program 입력
    계약 ③층(창업계획)과 같이 **계약**으로 받기로 했다(2026-08-24 결정).
    """
    base = client.post(f"{V1}/ai/simulate-revenue",
                       json={"district_id": "garosugil"}).json()
    assert base["inputs_source"]["prem"] == "absent"

    given = client.post(f"{V1}/ai/simulate-revenue",
                        json={"district_id": "garosugil", "unit_id": base["unit_id"],
                              "prem": 30000}).json()
    assert given["inputs_source"]["prem"] == "contract"
    # 권리금이 들어가면 초기투자가 커진다(prem/100 백만원). 세 전략 모두 오른다.
    for t in ("premium", "value", "factory"):
        assert given["scenarios"][t]["invest_mn"] > base["scenarios"][t]["invest_mn"], t

    # 음수는 0 으로 눕힌다 — 이 경로의 계약은 어떤 입력에도 같은 스키마를 주는 것이다.
    neg = client.post(f"{V1}/ai/simulate-revenue",
                      json={"district_id": "garosugil", "unit_id": base["unit_id"],
                            "prem": -5000}).json()
    assert neg["scenarios"]["value"]["invest_mn"] == base["scenarios"]["value"]["invest_mn"]


@requires_gold
def test_narrative_fields_are_absent_not_invented():
    """실 인벤토리 유닛에 시드 서술 문구(persona·note)를 지어 넣으면 안 된다."""
    postings = client.get(f"{V1}/commercial-districts/garosugil/postings").json()
    assert postings
    for p in postings:
        assert p.get("persona") in (None, ""), "실측 자리에 시드 페르소나가 붙었다"
        assert p.get("note") in (None, ""), "실측 자리에 시드 문구가 붙었다"

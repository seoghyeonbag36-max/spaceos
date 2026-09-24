"""Program(검증 프로그램) 스키마 — 아이템을 상권에서 **검증**하는 입력/출력 계약.

## 2026-09-17 대상 재정의 — 영업 중인 가게가 대상에서 빠졌다

종전 계약(`StoreProfile`)은 **영업 중인 가게의 리뷰·사진·메뉴**가 뼈대였다. 그 입력이
성립하려면 그 자리에서 이미 장사를 하고 있어야 한다. 지금 대상은 둘 다 그렇지 않다:

    예비창업자  아직 가게가 없다. 자기 아이템이 어느 상권에서 통할지 모른다.
    기창업자    사업은 하지만, **이 상권 이 아이템**은 아직 안 해 봤다.
                팝업스토어·가오픈·MVP 로 통하는지 확인하려 한다.

둘의 공통점은 **아직 검증되지 않은 아이템 + 아직 확정되지 않은 자리**다. 그래서 입력은
"이 가게가 어떤 가게인가"(과거의 축적)가 아니라 **"무엇을 어떻게 확인할 것인가"**(앞으로의
계획)이고, 산출물도 홍보안이 아니라 **검증 프로그램**이다.

리뷰·사진·메뉴·키워드 칸과 그것을 반자동으로 채우던 경로(카카오 로컬 상호검색·네이버
블로그 스니펫), 점주 제공 원문을 받던 상용 온보딩 계약은 전부 **삭제됐다** — 입력에서
그 원문이 사라지면 그 경계가 지킬 것이 없다. → docs/feature-program.md §0-V
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# 검증 방식. 셋을 가르는 이유는 **판정에 쓸 신호가 다르기 때문**이다.
#   popup     팝업스토어 — 짧고(며칠~몇 주) 자리를 빌린다. 신호는 유입·체류·구매전환
#   soft_open 가오픈 — 실제 운영을 축소해 연다. 신호는 객단가·회전·재료 소진·응대 부하
#   mvp       최소 실현 제품 — 매대·예약·사전주문처럼 점포 없이도 된다. 신호는 사전수요
ValidationMode = Literal["popup", "soft_open", "mvp"]

# 누가 묻는가. 같은 아이템이라도 예비창업자는 **자리부터** 찾고, 기창업자는 **옮길지**를
# 묻는다. 생성물의 어조와 오프라인 협업 주체가 갈린다.
FounderStage = Literal["pre_founder", "founder"]

MODE_LABEL: dict[str, str] = {
    "popup": "팝업스토어", "soft_open": "가오픈", "mvp": "MVP 테스트",
}
STAGE_LABEL: dict[str, str] = {
    "pre_founder": "예비창업자", "founder": "기창업자",
}


class ProgramBrief(BaseModel):
    """검증 브리프 — Program 의 유일한 입력 계약.

    종전에는 ①자리·②상권·③창업계획이 `StoreProfile` 과 중첩 `VenturePlan` 으로 갈려
    있었다. ③층이 뒤늦게 붙은 층이라 그랬는데, 이제 **③층이 계약의 본체**라 한 겹으로
    편다. ①자리는 `unit_id`, ②상권은 `district_id` 로 참조만 한다 — 그 둘은 우리가
    가진 데이터에서 자동으로 나오므로 기업이 적을 것이 아니다.

    ⚠ `differentiators` 는 검증된 사실이 아니라 **기업의 주장**이다. 그것이 사실인지를
    확인하려고 검증을 도는 것이므로, 컨텍스트에도 주장이라고 밝혀 싣는다.
    """

    # ── 무엇을, 어떻게 확인하나 (필수) ────────────────────────────────
    item: str = Field(min_length=1, max_length=200)      # 아이템 한 줄
    category: str = Field(min_length=1, max_length=120)  # 업종
    mode: ValidationMode
    stage: FounderStage

    # ── 어디서 (①자리·②상권 참조) ────────────────────────────────────
    district_id: str | None = None   # 거점 id — ②층 상권 컨텍스트가 붙는다
    unit_id: str | None = None       # `gold/{거점}/vacant_units.json` 의 공실 유닛 = 검증을 돌릴 자리
    address: str | None = Field(default=None, max_length=300)

    # ── 가설과 조건 (선택이지만 여기가 근거의 원천이다) ───────────────
    # 리뷰가 없는 대상이라 "무엇을 근거로 제안했나"의 절반이 이 칸들에서 온다.
    # 나머지 절반은 ①자리·②상권의 수치다(docs/feature-program.md §0-B 원칙 1).
    hypothesis: str | None = Field(default=None, max_length=500)   # 검증 가설
    target_customer: str | None = Field(default=None, max_length=200)
    start_date: str | None = None    # 검증 시작 예정일 YYYY-MM-DD
    run_days: int | None = Field(default=None, gt=0, le=365)       # 검증 기간(일)
    # 예산은 **구간**으로 받는다. 출력의 budget_share 는 int 퍼센트라 절대액이
    # 구조적으로 못 들어가고(§0-F), 실제 금액은 이 구간에서만 파생한다.
    budget_krw_min: int | None = Field(default=None, gt=0)
    budget_krw_max: int | None = Field(default=None, gt=0)
    differentiators: list[str] = Field(default_factory=list, max_length=8)  # 차별점 — 기업 주장
    tier: str | None = None          # Posting 3-Tier 선택(premium/value/factory)

    @model_validator(mode="after")
    def _budget_band_is_complete(self) -> "ProgramBrief":
        """한쪽만 준 예산은 구간이 아니다 — 반쪽짜리를 범위처럼 인용하게 두지 않는다."""
        lo, hi = self.budget_krw_min, self.budget_krw_max
        if (lo is None) != (hi is None):
            raise ValueError("예산은 하한·상한을 함께 주거나 둘 다 비워야 합니다")
        return self


class HAFinding(BaseModel):
    """Humanistic Authority 후처리 검증 결과 1건 (services/ha_guard.py).

    `ha_check` 가 **LLM 의 자기신고**인 것과 달리 이건 서버가 입력과 대조해 낸 판정이다.

    - `severity == "violation"`: 입력 대조로 거짓이 확정된 것(지어낸 금액, 확정된 트렌드
      방향 역행, 아직 없는 경험을 근거로 삼는 것). 이 findings 가 붙어 있고 `source` 가
      `"llm"` 이 아니면 **LLM 응답이 폐기되고 폴백으로 내려간 것**이다 — 키 미설정·호출
      실패와 구분되는 상태다.
    - `severity == "warning"`: 사전 매칭이라 오탐이 섞인다. 응답은 살리고 밝히기만 한다.
    """
    severity: str                     # "violation" | "warning"
    code: str                         # fabricated_price | unproven_experience_claim | ...
    message: str                      # 사람이 읽을 판정 문장
    evidence: str | None = None       # 걸린 실제 문자열 (사람이 오탐인지 보게 한다)


class VacantSite(BaseModel):
    """입력 계약 ①층(자리) 1건 — `gold/{거점}/vacant_units.json` 의 공실 유닛.

    아직 아무도 장사하지 않는 자리라 리뷰·평점·매출 실적이 존재하지 않는다. 여기 있는
    것은 전부 건축물대장과 건물 마스터에서 온 **사실**이다(services/program_site).
    팝업·가오픈은 바로 이런 자리를 짧게 빌려 도는 것이라, 이 층이 검증의 무대가 된다.
    """
    id: str
    n: str | None = None              # 소재 표기(지번 + 건물 용도/명칭)
    lat: float | None = None
    lng: float | None = None
    area: int | None = None           # 평 — 건물 상업면적 ÷ 호실 수(호실당 평균)
    floor: str | None = None          # 상가정보 flrNo 매칭 전이라 1F 가정
    was: str | None = None            # 직전 업종
    capacity: int | None = None       # 건물 호실 수
    active: int | None = None         # 그중 영업 중
    vacancy_rate: float | None = None  # 건물 공실률(%)
    bld_floors: int | None = None
    com_area_m2: float | None = None


class VacantSiteList(BaseModel):
    """GET /marketing/sites 응답. `site_source == "unavailable"` 이면 Gold 미적재다.

    `site_note` 를 반드시 함께 노출한다 — 면적이 호실당 평균이고 층이 1F 가정이라는
    한계가 빠지면 그 위에 얹힌 제안이 실측처럼 읽힌다.
    """
    district_id: str
    sites: list[VacantSite]
    site_source: str
    site_note: str | None = None
    site_built_at: str | None = None


class ChannelPlan(BaseModel):
    """제안 1건. **온라인과 오프라인은 대칭이 아니다 — 주체가 다르다**(§0-B).

    온라인은 창업자가 **단독 실행**하는 모객이고, 오프라인은 혼자 할 수 없는 **자리
    확보·상권 연계**다(행사 785건 중 57%가 공공·준공공 주최). 그래서 필요한 속성이
    갈린다. 하나의 모델에 담되 `kind` 로 어느 쪽 필드가 유효한지 가른다 — 프론트가
    online/offline 두 목록을 같은 모양으로 받는다.
    """
    channel: str                      # 온라인=채널명 / 오프라인=형식(팝업 부스·공동 프로모션)
    kind: str                         # online | offline
    content: str                      # 제안 문구/실행안
    rationale: str                    # 근거 (자리·상권 수치. 리뷰가 아니어도 된다)

    # ── 온라인(모객) 전용 ─────────────────────────────────────────────
    target: str | None = None         # 목표 고객 세그먼트 (TRDAR 연령·성별·시간대에서)
    # 예산 **배분 비율(%)**. 절대액을 담지 않는 것이 핵심이다 — "얼마를 쓸지는 창업자 몫"
    # 이라는 §0-B 원칙 2 를, 값을 int 퍼센트로 못 박아 **구조적으로** 강제한다.
    # 문자열이면 LLM 이 "월 30만원" 을 넣을 수 있지만 int 에는 넣을 수 없다.
    budget_share: int | None = None
    kpi: str | None = None            # 이 채널 하나의 목표 지표 (전체 판정은 signals 가 한다)

    # ── 오프라인(자리·상권 연계) 전용 ─────────────────────────────────
    timing: str | None = None         # 시기 — 빈 시간대(TRDAR 격차)·검증 기간 중 며칠째
    actors: list[str] = []            # 협업 주체 (건물주·상인회·구청·인근 점포)
    # 오프라인 제안의 성격. 셋을 가르는 이유는 규칙이 서로 다르기 때문이다.
    #   cite    = 컨텍스트에 실린 **기존 행사** 연계 → 사실 주장이라 인용만 허용
    #   propose = **신규 공동 행사** 제안 → 계획이라 허용하되 빈 시간대 수치 인용을 강제
    #   own     = 자체 접점(팝업 부스 운영·입간판·시식) → 행사가 아니다. 협업 주체도 필수가 아니다
    # own 이 없으면 입간판 같은 평범한 제안이 '수치 없는 행사 제안'으로 잘못 걸린다.
    mode: str | None = None


class ValidationSignal(BaseModel):
    """검증 지표 1건 — **이 트랙의 결론**이다 (2026-09-17 신설).

    팝업·가오픈·MVP 는 홍보가 목적이 아니라 **판정**이 목적이다. "통했는지 아닌지"를
    무엇으로 가를지 정하지 않고 도는 검증은 검증이 아니라 그냥 지출이다. 그래서
    채널안과 **같은 등급으로** 이 블록을 낸다.

    `decision` 이 이 모델의 요점이다. 목표선(`target`)만 있고 판정선이 없으면 결과를
    보고 사후에 말을 맞추게 된다 — 가설을 기각할 조건을 **미리** 적어야 검증이 된다.
    """
    name: str                         # 지표명 — "일 방문객 수"
    method: str                       # 측정 방법 — "입장 카운터 + POS 영수증 수"
    target: str                       # 목표선 — "일 60명"
    decision: str                     # 판정 — "7일 누적 300명 미만이면 가설 기각"


class LLMPerformancePlan(BaseModel):
    """LLM 구조화 출력 — 온라인(모객). 창업자 단독 실행."""
    channel: str
    content: str
    rationale: str
    target: str
    budget_share: int                 # % — 온라인 제안들의 합이 100 이 되게 한다
    kpi: str


class LLMActivationPlan(BaseModel):
    """LLM 구조화 출력 — 오프라인(자리·상권 연계). 창업자 + 상권 주체 협업.

    `channel` 은 채널이 아니라 **형식**이다(팝업 부스·공동 프로모션·야외 매대).
    `mode` 가 이 출력의 안전장치다 — 기존 행사 인용과 신규 제안을 가르지 않으면
    지어낸 행사가 사실처럼 나간다.
    """
    channel: str
    content: str
    rationale: str
    timing: str
    actors: list[str]
    mode: str                         # "cite" | "propose" | "own" — ChannelPlan 주석 참조


class LLMValidationSignal(BaseModel):
    """LLM 구조화 출력 — 검증 지표. 네 칸을 모두 요구해 판정선이 빠지지 않게 한다."""
    name: str
    method: str
    target: str
    decision: str


class LLMProgramPlan(BaseModel):
    """LLM 구조화 출력 계약 — generate_program 의 llm 경로 응답 스키마."""
    online: list[LLMPerformancePlan]
    offline: list[LLMActivationPlan]
    signals: list[LLMValidationSignal]
    ha_check: str                     # 균형·공생·공감 자체 점검 결과 서술


# 상권 단위 응답 모델(GET /marketing/{id})은 여기가 아니라 `schemas/district.py::Marketing`
# 이다. 예전에 이 파일에도 같은 뜻의 `DistrictMarketing` 이 있었지만 라우터가 쓰지 않는
# 죽은 사본이었고, 2026-08-06 실제로 이걸 고치고 응답이 안 바뀌어 한 번 헛짚었다. 지웠다.


class LLMDistrictContents(BaseModel):
    """LLM 구조화 출력 계약 — 상권 단위 온라인 콘텐츠(Program 2단계).

    online_contents 는 프론트가 그대로 노출하는 한 줄 카피(해시태그 포함) 목록이다.
    """
    online_contents: list[str]
    ha_check: str


class ProgramPlan(BaseModel):
    """검증 프로그램 한 벌 — 모객(online) · 자리·연계(offline) · **판정(signals)**.

    종전 `StoreMarketing` 을 대체한다. 빠진 것은 `store_name`(아직 가게가 아니다)과
    `tone_keywords`(리뷰 빈도에서 뽑던 값이라 리뷰가 사라지면 근거가 없다). 더해진 것은
    `mode`·`signals` 로, 이 산출물이 홍보안이 아니라 **검증안**임을 구조가 말한다.
    """
    item: str
    category: str
    mode: str                         # popup | soft_open | mvp
    stage: str                        # pre_founder | founder
    online: list[ChannelPlan]
    offline: list[ChannelPlan]
    signals: list[ValidationSignal]
    ha_check: str                     # LLM 자기신고 — 이것만으로는 검증이 아니다
    source: str                       # "llm" | "rule-stub"
    ha_findings: list[HAFinding] = []  # 서버 후처리 검증 결과 (ha_check 와 다르다)

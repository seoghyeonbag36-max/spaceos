"""서울 25개 구 거점 선정 점수 모델 설정 (config).

SpaceOS 진입 우선순위 산식의 단일 진실 공급원(Single Source of Truth).
- DISTRICTS: 25개 구의 자치구 코드 + 4기준 base 앵커(0~100) + 수집 키워드.
- SCORE_BANDS: base(0~100) → 1~4점 변환 임계 밴드 (대상별·기준별).
- TILT: 동점 시 연속 점수 정렬용 대상별 가중치.

4기준: SNS(SNS 업로드), VAC(공실), MAP(지도/IT 유입), FOOT(유동인구).
2대상: b2c(상권 방문 고객), b2b(상권 입주 업체).

⚠️ base 값은 1차 프록시(中신뢰: 공개 핫플/검색 순위 + 쿠시먼앤드웨이크필드 2025 공실률).
   수집기(collectors/*)가 실제 API/크롤링 값으로 base를 덮어쓰면 점수가 자동 갱신된다.
   실측 연동 지점은 각 수집기의 TODO 주석 참조.
"""
from __future__ import annotations

# 자치구 코드(통계청 행정구역) + 4기준 base 앵커값(0~100, 25구 상대 정규화) + 대표 상권/키워드
DISTRICTS: dict[str, dict] = {
    "강남구": {"code": "11230", "base": {"SNS": 85, "VAC": 95, "MAP": 100, "FOOT": 100},
              "hot": ["강남대로", "가로수길", "압구정로데오", "신사"], "keywords": ["강남맛집", "가로수길", "압구정"]},
    "마포구": {"code": "11140", "base": {"SNS": 95, "VAC": 62, "MAP": 88, "FOOT": 78},
              "hot": ["홍대", "연남동", "합정", "망원"], "keywords": ["홍대맛집", "연남동", "망원동"]},
    "종로구": {"code": "11010", "base": {"SNS": 72, "VAC": 60, "MAP": 74, "FOOT": 84},
              "hot": ["익선동", "삼청동", "광장시장", "서촌"], "keywords": ["익선동", "삼청동", "광장시장"]},
    "중구":  {"code": "11020", "base": {"SNS": 62, "VAC": 55, "MAP": 80, "FOOT": 92},
              "hot": ["명동", "을지로", "동대문"], "keywords": ["명동맛집", "을지로", "힙지로"]},
    "용산구": {"code": "11030", "base": {"SNS": 88, "VAC": 58, "MAP": 75, "FOOT": 66},
              "hot": ["이태원", "한남동", "용리단길", "경리단길"], "keywords": ["이태원", "한남동", "용리단길"]},
    "송파구": {"code": "11240", "base": {"SNS": 70, "VAC": 33, "MAP": 90, "FOOT": 76},
              "hot": ["잠실", "송리단길", "방이"], "keywords": ["잠실", "송리단길", "방이맛집"]},
    "성동구": {"code": "11040", "base": {"SNS": 100, "VAC": 15, "MAP": 80, "FOOT": 62},
              "hot": ["성수동", "서울숲", "뚝섬"], "keywords": ["성수동", "성수카페", "서울숲"]},
    "영등포구": {"code": "11190", "base": {"SNS": 50, "VAC": 53, "MAP": 70, "FOOT": 82},
              "hot": ["여의도", "문래동", "영등포역"], "keywords": ["여의도", "문래동", "영등포"]},
    "서초구": {"code": "11220", "base": {"SNS": 55, "VAC": 48, "MAP": 70, "FOOT": 74},
              "hot": ["고속터미널", "서초", "반포"], "keywords": ["고속터미널", "서래마을", "방배"]},
    "서대문구": {"code": "11130", "base": {"SNS": 50, "VAC": 75, "MAP": 56, "FOOT": 54},
              "hot": ["신촌", "이대", "연희동"], "keywords": ["신촌", "이대", "연희동"]},
    "광진구": {"code": "11050", "base": {"SNS": 60, "VAC": 52, "MAP": 62, "FOOT": 58},
              "hot": ["건대입구", "구의", "성수연계"], "keywords": ["건대맛집", "건대입구", "성수"]},
    "동대문구": {"code": "11060", "base": {"SNS": 42, "VAC": 56, "MAP": 55, "FOOT": 60},
              "hot": ["청량리", "DDP연계", "회기"], "keywords": ["청량리", "회기", "경희대"]},
    "관악구": {"code": "11210", "base": {"SNS": 45, "VAC": 50, "MAP": 48, "FOOT": 56},
              "hot": ["샤로수길", "서울대입구", "신림"], "keywords": ["샤로수길", "서울대입구", "신림"]},
    "동작구": {"code": "11200", "base": {"SNS": 35, "VAC": 56, "MAP": 44, "FOOT": 52},
              "hot": ["노량진", "사당", "흑석"], "keywords": ["노량진", "사당", "흑석동"]},
    "강서구": {"code": "11160", "base": {"SNS": 35, "VAC": 48, "MAP": 50, "FOOT": 52},
              "hot": ["마곡", "발산", "까치산"], "keywords": ["마곡", "발산역", "화곡"]},
    "구로구": {"code": "11170", "base": {"SNS": 28, "VAC": 50, "MAP": 40, "FOOT": 56},
              "hot": ["구로디지털", "신도림", "가산연계"], "keywords": ["구로디지털", "신도림", "구로"]},
    "금천구": {"code": "11180", "base": {"SNS": 30, "VAC": 52, "MAP": 38, "FOOT": 54},
              "hot": ["가산디지털", "독산"], "keywords": ["가산디지털", "독산동", "금천"]},
    "강동구": {"code": "11250", "base": {"SNS": 35, "VAC": 40, "MAP": 42, "FOOT": 52},
              "hot": ["천호", "강동역", "고덕"], "keywords": ["천호동", "고덕", "암사"]},
    "노원구": {"code": "11110", "base": {"SNS": 30, "VAC": 45, "MAP": 42, "FOOT": 50},
              "hot": ["노원역", "공릉", "중계"], "keywords": ["노원맛집", "공릉동", "중계동"]},
    "성북구": {"code": "11080", "base": {"SNS": 36, "VAC": 48, "MAP": 36, "FOOT": 46},
              "hot": ["성신여대", "안암", "길음"], "keywords": ["성신여대", "안암", "보문"]},
    "양천구": {"code": "11150", "base": {"SNS": 25, "VAC": 38, "MAP": 35, "FOOT": 44},
              "hot": ["목동", "오목교", "신정"], "keywords": ["목동", "오목교", "신정"]},
    "은평구": {"code": "11120", "base": {"SNS": 26, "VAC": 47, "MAP": 32, "FOOT": 42},
              "hot": ["연신내", "불광", "응암"], "keywords": ["연신내", "불광동", "은평"]},
    "강북구": {"code": "11090", "base": {"SNS": 24, "VAC": 52, "MAP": 28, "FOOT": 40},
              "hot": ["수유", "미아", "번동"], "keywords": ["수유역", "미아사거리", "강북"]},
    "중랑구": {"code": "11070", "base": {"SNS": 20, "VAC": 50, "MAP": 26, "FOOT": 38},
              "hot": ["상봉", "면목", "중화"], "keywords": ["상봉동", "면목동", "중랑"]},
    "도봉구": {"code": "11100", "base": {"SNS": 18, "VAC": 50, "MAP": 24, "FOOT": 34},
              "hot": ["창동", "쌍문", "방학"], "keywords": ["창동", "쌍문동", "도봉"]},
}

# base(0~100) → 1~4점 변환 밴드. (upper_bound_inclusive, score) 오름차순.
# 마지막 항목의 upper_bound=100 이 최고 점수. 대상별·기준별로 방향과 구간이 다르다.
# 핵심 원칙: 공실(VAC)은 'SpaceOS가 푸는 문제' → 입주업체(b2b)에겐 높을수록 高점수,
#           방문고객(b2c)에겐 약한 음(-) 신호라 만점 상한을 3으로 제한.
SCORE_BANDS: dict[str, dict[str, list[tuple[int, int]]]] = {
    "SNS": {
        "b2c": [(49, 2), (79, 3), (100, 4)],            # 방문고객: SNS 핫플일수록 방문 매력 ↑
        "b2b": [(43, 1), (67, 2), (99, 3), (100, 4)],   # 입주업체: 노출 자산이나 임대료 부담도 동반
    },
    "VAC": {
        "b2c": [(53, 1), (90, 2), (100, 3)],            # 방문고객: 공실 많으면 활기 ↓ (상한 3)
        "b2b": [(29, 2), (57, 3), (100, 4)],            # 입주업체: 공실 많을수록 솔루션 수요 ↑ (하한 2)
    },
    "MAP": {
        "b2c": [(30, 1), (52, 2), (78, 3), (100, 4)],
        "b2b": [(33, 1), (58, 2), (82, 3), (100, 4)],
    },
    "FOOT": {
        "b2c": [(35, 1), (59, 2), (80, 3), (100, 4)],
        "b2b": [(38, 1), (61, 2), (82, 3), (100, 4)],
    },
}

# 동점 시 연속 점수 정렬용 대상별 tilt 가중치(메모리 모델과 동일).
TILT: dict[str, dict[str, float]] = {
    "b2c": {"SNS": +0.5, "VAC": -1.0, "MAP": +0.3, "FOOT": +0.4},
    "b2b": {"SNS": -0.4, "VAC": +0.9, "MAP": +0.1, "FOOT": +0.3},
}

CRITERIA = ["SNS", "VAC", "MAP", "FOOT"]
TARGETS = ["b2c", "b2b"]

# ── 진입 Phase 계획 (확정 SSOT) ────────────────────────────────────────────────
# 점수순 자동배정이 아니라, 창업자가 확정한 25구 진입(배포) 순서의 단일 진실 공급원.
# - 키: Phase(1~4). 값: 해당 Phase 진입 순서대로 나열한 자치구 리스트.
# - 리스트 내 순서 = Phase 내 진입 순번(phaseSeq). 점수(rank)와는 독립적으로 운영된다.
#   (예: 점수상 동대문>서초여도, 계획상 서초를 먼저 진입하면 리스트 순서가 우선.)
# ⚠️ Phase를 바꾸려면 '오직 이 표'만 수정한다. 파생 맵·gold JSON·대시보드가 전부 이 표를 따른다.
# 표준 행정명 사용: '중랑구'(中浪, Jungnang). '중량구'는 흔한 오기 → 여기서 정규화.
PHASE_PLAN: dict[int, list[str]] = {
    1: ["강남구", "마포구", "종로구", "중구", "성동구"],
    2: ["용산구", "송파구", "광진구", "영등포구", "서초구", "서대문구", "동대문구"],
    3: ["관악구", "동작구", "강서구", "구로구", "금천구", "강동구", "노원구"],
    4: ["성북구", "양천구", "은평구", "강북구", "중랑구", "도봉구"],
}

# PHASE_PLAN에서 자동 파생되는 역참조 맵 — PHASE_PLAN만 고치면 아래는 전부 자동 갱신된다.
DISTRICT_PHASE: dict[str, int] = {            # 구 → Phase(1~4)
    gu: ph for ph, gus in PHASE_PLAN.items() for gu in gus}
DISTRICT_PHASE_SEQ: dict[str, int] = {        # 구 → Phase 내 진입 순번(1~)
    gu: i for gus in PHASE_PLAN.values() for i, gu in enumerate(gus, 1)}
DISTRICT_DEPLOY_ORDER: dict[str, int] = {     # 구 → 전체 진입 순번(1~25, Phase→순번 평탄화)
    gu: i for i, gu in enumerate(
        (gu for ph in sorted(PHASE_PLAN) for gu in PHASE_PLAN[ph]), 1)}


def validate_phase_plan() -> None:
    """PHASE_PLAN이 DISTRICTS 25구를 정확히 1회씩 덮는지 검증(누락·중복·오타 즉시 차단).

    SSOT 무결성 가드 — 계획이 깨진 채로 점수표가 생성되는 것을 방지한다.
    import 시 자동 호출되므로, 표가 어긋나면 파이프라인이 조용히 틀리지 않고 즉시 실패한다.
    """
    planned = [gu for gus in PHASE_PLAN.values() for gu in gus]
    planned_set, district_set = set(planned), set(DISTRICTS)
    errs: list[str] = []
    if len(planned) != len(planned_set):
        dups = sorted({gu for gu in planned if planned.count(gu) > 1})
        errs.append(f"중복 배정: {dups}")
    missing = district_set - planned_set      # DISTRICTS엔 있으나 PHASE_PLAN에 빠진 구
    unknown = planned_set - district_set      # PHASE_PLAN에만 있는 구(오타·미정의)
    if missing:
        errs.append(f"누락된 구: {sorted(missing)}")
    if unknown:
        errs.append(f"미정의 구(오타?): {sorted(unknown)}")
    if errs:
        raise ValueError("PHASE_PLAN 검증 실패 — " + " | ".join(errs))


validate_phase_plan()  # import 시 자동 무결성 검증 (계획 SSOT 보호)

# ── 진입 Phase 계획 (확정 SSOT) ────────────────────────────────────────────────
# 점수순 자동배정이 아니라, 창업자가 확정한 25구 진입(배포) 순서의 단일 진실 공급원.
# - 키: Phase(1~4). 값: 해당 Phase 진입 순서대로 나열한 자치구 리스트.
# - 리스트 내 순서 = Phase 내 진입 순번(phaseSeq). 점수(rank)와는 독립적으로 운영된다.
#   (예: 점수상 동대문>서초여도, 계획상 서초를 먼저 진입하면 리스트 순서가 우선.)
# ⚠️ Phase를 바꾸려면 '오직 이 표'만 수정한다. 파생 맵·gold JSON·대시보드가 전부 이 표를 따른다.
# 표준 행정명 사용: '중랑구'(中浪, Jungnang). '중량구'는 흔한 오기 → 여기서 정규화.
PHASE_PLAN: dict[int, list[str]] = {
    1: ["강남구", "마포구", "종로구", "중구", "성동구"],
    2: ["용산구", "송파구", "광진구", "영등포구", "서초구", "서대문구", "동대문구"],
    3: ["관악구", "동작구", "강서구", "구로구", "금천구", "강동구", "노원구"],
    4: ["성북구", "양천구", "은평구", "강북구", "중랑구", "도봉구"],
}

# PHASE_PLAN에서 자동 파생되는 역참조 맵 — PHASE_PLAN만 고치면 아래는 전부 자동 갱신된다.
DISTRICT_PHASE: dict[str, int] = {            # 구 → Phase(1~4)
    gu: ph for ph, gus in PHASE_PLAN.items() for gu in gus}
DISTRICT_PHASE_SEQ: dict[str, int] = {        # 구 → Phase 내 진입 순번(1~)
    gu: i for gus in PHASE_PLAN.values() for i, gu in enumerate(gus, 1)}
DISTRICT_DEPLOY_ORDER: dict[str, int] = {     # 구 → 전체 진입 순번(1~25, Phase→순번 평탄화)
    gu: i for i, gu in enumerate(
        (gu for ph in sorted(PHASE_PLAN) for gu in PHASE_PLAN[ph]), 1)}


def validate_phase_plan() -> None:
    """PHASE_PLAN이 DISTRICTS 25구를 정확히 1회씩 덮는지 검증(누락·중복·오타 즉시 차단).

    SSOT 무결성 가드 — 계획이 깨진 채로 점수표가 생성되는 것을 방지한다.
    import 시 자동 호출되므로, 표가 어긋나면 파이프라인이 조용히 틀리지 않고 즉시 실패한다.
    """
    planned = [gu for gus in PHASE_PLAN.values() for gu in gus]
    planned_set, district_set = set(planned), set(DISTRICTS)
    errs: list[str] = []
    if len(planned) != len(planned_set):
        dups = sorted({gu for gu in planned if planned.count(gu) > 1})
        errs.append(f"중복 배정: {dups}")
    missing = district_set - planned_set      # DISTRICTS엔 있으나 PHASE_PLAN에 빠진 구
    unknown = planned_set - district_set      # PHASE_PLAN에만 있는 구(오타·미정의)
    if missing:
        errs.append(f"누락된 구: {sorted(missing)}")
    if unknown:
        errs.append(f"미정의 구(오타?): {sorted(unknown)}")
    if errs:
        raise ValueError("PHASE_PLAN 검증 실패 — " + " | ".join(errs))


validate_phase_plan()  # import 시 자동 무결성 검증 (계획 SSOT 보호)

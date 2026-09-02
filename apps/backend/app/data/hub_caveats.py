"""계획상가 밀집 거점의 예외 처리 — 무엇을 밝히고 무엇을 내리는가.

## 무슨 문제인가

거점 대표 공실률의 분모(`capacity`)는 **일반건축물만** 싣는다. 집합건물(`expos_units`)은
상가정보가 집합상가 **내부** 점포를 그 건물 `bdMgtSn` 으로 귀속시키지 못해 분자가 구조적
으로 비고, 그대로 넣으면 공실률이 78~86% 로 튄다(services/gold_vacancy 모듈 상단 2번).
서울에서 2026-08-26 에 정량 조사 후 편입을 기각했다(docs/feature-posting.md §0-R).

그 결과 **집합상가가 밀집한 거점에서는 분모가 상업 재고의 일부만 덮는다.** 서울 54거점의
건물당 점포 수는 중앙 3.5 인데 셋만 10을 크게 넘고(yeouido 27.7 · banpo 25.2 · garak 14.1,
4위 gangnam 8.7 과 사이가 비어 있다), 그 셋에서 분모가 덮는 재고는 이렇다:

    banpo    266호실 / 5,096 =  5.2%
    yeouido  346호실 / 3,079 = 11.2%
    garak     86호실 /   348 = 24.7%
    (참고 gangnam 39.7% · garosugil 83.2%)

## 2026-09-02 판단 — 셋을 같게 다루지 않는다

`scripts/chain_status.py` 의 `점포` 단계가 이 셋을 BLOCKED 로 세워 두고 "거점을 내리거나
집합상가 비중을 명시한 채 진행"을 물었다. 답은 갈렸다:

* **garak · yeouido → 밝히고 싣는다**(`DISCLOSED`). 24.7% 와 11.2% 는 표기로 감당된다.
  yeouido 는 앵커 격차가 -3.0%p 로 오히려 잘 맞아 대표값이 헛돌지 않는다는 방증이 있다.
* **banpo → 대표 공실률만 내린다**(`WITHHELD`). 재고의 5.2% 위에서 낸 수를 표기 하나
  달아 "9.8%" 로 크게 띄우는 것은, 이 저장소가 `vacancy_source`·시드 배지로 지켜 온
  원칙(**합성값을 실측처럼 보이지 않게 한다**)과 같은 이유로 안 된다. 거점은 남긴다 —
  오염된 축은 공실 하나뿐이고 임대(R-ONE)·유동(집계구)·밀도·Posting 입력은 멀쩡하다.

거점을 목록에서 빼는 선택지도 있었으나 취하지 않았다. 여의도·고속터미널은 서울 최상급
오피스/유통 상권이고 KPI② B2B 파일럿의 표적이라, 잃는 것이 얻는 것보다 크다.

## 문구의 숫자를 손으로 적지 않는다

이 저장소의 주된 실패 양식은 **선언이 낡는 것**이다. 그래서 예외 문구의 비율은 상수가
아니라 서빙이 실제로 쓴 집계(`services/gold_vacancy.build_cells` 의
`inventory_coverage_pct`)에서 그때그때 만든다. 재수집으로 값이 움직이면 화면 문구도 같이
움직인다. 판단 자체(어느 거점을 어느 쪽으로 두는가)만 아래 두 집합에 적는다.

판단이 여전히 유효한지는 `tests/test_hub_caveats.py` 가 산출물로 감시한다.
"""
from __future__ import annotations

# 대표 공실률을 **내리는** 거점 — 값이 없는 것(미측정)과 다르다. 재고 커버가 너무 낮아
# 거점을 대표하지 못한다고 판정한 자리다. 위 머리말 참조.
WITHHELD: frozenset[str] = frozenset({"banpo"})

# 대표 공실률을 **싣되 예외를 밝히는** 거점.
DISCLOSED: frozenset[str] = frozenset({"garak", "yeouido"})

# 판단을 촉발한 축 — 건물당 점포 수 임계(계획상가 밀집). chain_status 와 같은 값을 쓴다.
# 여기 두 집합에 든 거점은 전부 이 선을 넘는다(테스트가 고정).
STORES_PER_BLDG_MAX = 10.0


def is_excepted(district_id: str) -> bool:
    """이 거점에 계획상가 예외 판단이 내려져 있는가.

    `scripts/chain_status.py` 의 `점포` 단계가 이것을 읽어 BLOCKED 를 푼다 — 판단이
    코드에 있는데 프로버가 계속 "정해라"를 물으면, 그것이 곧 낡은 선언이다.
    """
    return district_id in WITHHELD or district_id in DISCLOSED


def is_withheld(district_id: str) -> bool:
    """거점 대표 공실률을 내려보내지 않는 거점인가."""
    return district_id in WITHHELD


def _pct(v: float | None) -> str:
    return f"{v:.1f}%" if v is not None else "일부"


def caveat_of(district_id: str, cells: dict | None = None) -> str:
    """화면에 실을 예외 문구. 예외가 아니면 빈 문자열.

    `cells` 는 `services/districts.cells_for()` 의 반환(= 서빙이 실제로 쓴 집계)이다.
    비율·호실 수를 여기서 읽어 문구를 만든다 — 손으로 적은 수를 쓰지 않기 위해서다.
    """
    ci = cells or {}
    cov = ci.get("inventory_coverage_pct")
    cap = ci.get("capacity")

    if district_id in WITHHELD:
        # 앞머리 "대표값" 은 화면이 예외 종류를 가르는 데 쓴다
        # (components/DistrictPicker.tsx 의 caveatKind).
        head = "대표값 미제공 — 공실률 분모가 이 거점 상업 재고의 "
        body = f"{_pct(cov)}"
        if cap:
            body += f"({cap:,}호실)"
        return (
            head + body + "만 덮어 거점을 대표하지 못한다. 나머지는 집합상가 내부 호실이라 "
            "점포가 건물에 귀속되지 않는다(집합건물은 분모에서 뺀다). 건물별 공실은 그대로 "
            "싣되 거점 대표값과 앵커 격차·예측은 내렸다 — 임대·유동·밀도 축은 영향이 없다."
        )

    if district_id in DISCLOSED:
        return (
            "계획상가 밀집 — 공실률 분모가 이 거점 상업 재고의 "
            f"{_pct(cov)}" + (f"({cap:,}호실)" if cap else "") + "만 덮는다. 나머지는 "
            "집합상가 내부 호실이라 점포가 건물에 귀속되지 않아 분모에서 뺐다. "
            "다른 거점과 공실률을 직접 비교하지 말 것."
        )

    return ""

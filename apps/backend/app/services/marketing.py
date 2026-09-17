"""Program 생성 서비스 — 검증 프로그램(아이템 단위) → 상권 단위 콘텐츠.

## 2026-09-17 대상 재정의

1) **검증 프로그램**: 예비창업자·검증하려는 기창업자가 낸 브리프(`ProgramBrief`)로
   팝업스토어·가오픈·MVP 를 돌릴 온라인(모객)·오프라인(자리·연계)·**검증 지표(판정)**
   한 벌을 만든다. LLM 키(settings.llm_api_key) 설정 시 Claude 실호출, 실패·미설정 시
   규칙 기반 스텁 폴백 (source 필드로 구분).

   종전에는 **영업 중인 가게의 리뷰·사진·메뉴**가 입력이었다. 대상이 아직 그 자리에서
   장사한 적 없는 사람으로 바뀌면서 그 입력은 성립하지 않는다 — 근거는 리뷰가 아니라
   ①자리·②상권의 수치와 ③브리프의 가설이 맡는다(docs/feature-program.md §0-V).
   vision(사진 분석)도 함께 빠졌다. 아직 찍을 가게가 없다.

2) **상권 단위**: Platform 수집 정보(상권분석 시계열·감성·블로그 키워드) 기반 —
   gold/program_content_context 를 검증 프로그램 생성의 컨텍스트로 결합하고,
   GET /{district_id} 의 온라인 콘텐츠도 같은 Gold 로 생성한다(2026-08-01).
   행사(events)는 서울열린데이터광장 문화행사 실데이터 — services/events.py 가 서빙한다.

윤리 기준: Humanistic Authority(균형·공생·공감) — 과장·허위·특정 자본 편중 금지.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from app.core.config import settings
from app.data.seoul_pages import DISTRICTS_BY_ID
from app.schemas.marketing import MODE_LABEL, STAGE_LABEL, LLMDistrictContents, LLMProgramPlan
from app.services import districts as svc
from app.services import events, ha_guard, program_brief, program_site

# 규칙 기반 스텁이 검증 방식별로 무엇을 재는지 (LLM 폴백).
# 셋을 가르는 이유는 **판정에 쓸 신호가 다르기 때문**이다 — 팝업은 짧게 자리를 빌려
# 유입을 보고, 가오픈은 실제 운영을 축소해 돌려 회전·객단가를 보고, MVP 는 점포 없이
# 사전 수요만 본다. 같은 지표를 셋에 다 붙이면 셋 중 둘에서 잴 수 없는 값이 된다.
_MODE_SIGNAL = {
    "popup": ("일 방문객 수", "입장 카운터(또는 결제 건수) 일별 기록",
              "일 60명", "기간 누적이 목표선의 70% 미만이면 이 상권 가설을 기각한다"),
    "soft_open": ("객단가·좌석 회전", "POS 영수증 건당 금액과 시간대별 테이블 회전 기록",
                  "객단가 12,000원 · 피크 회전 2.0회", "둘 중 하나라도 70% 미만이면 운영안을 고친다"),
    "mvp": ("사전 예약·사전주문 전환율", "신청 폼 유입 대비 결제·예약 완료 비율",
            "전환율 8%", "전환율이 4% 미만이면 아이템 가설을 기각한다"),
}

# 상권 컨텍스트 결합용 district_id → gold 슬러그 매핑.
# 2026-08-01: 거점 id 와 gold 슬러그가 같은 54거점이 build_program13_context 로 모두
# 생성돼(garosugil 만 전용 Bronze), 표 대신 **동명 슬러그 + 파일 존재 확인**으로 푼다.
# 여기에는 id 가 슬러그와 다른 예외(별칭)만 남긴다. 새 거점을 추가하려면
# `python -m data.pipelines.build_gold --platform13` 로 Gold 만 만들면 자동 반영된다.
_DISTRICT_ALIAS: dict[str, str] = {
    "gangnam-garosugil": "garosugil",
}

# district_id 는 요청 본문에서 오므로 경로로 쓰기 전에 형태를 제한한다(경로 이탈 방지).
_SLUG_RE = re.compile(r"^[a-z0-9-]{1,40}$")

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"

_SYSTEM_PROMPT = """너는 PlaceOS의 Program(검증 프로그램 설계) 생성기다.

사용자는 **아직 이 자리에서 이 아이템으로 장사해 본 적이 없는 사람**이다. 둘 중 하나다:
- 예비창업자 — 아직 가게가 없고, 자기 아이템이 어느 상권에서 통할지 모른다.
- 기창업자 — 사업은 하지만 이 상권·이 아이템은 안 해 봤고, 팝업스토어·가오픈·MVP 로
  통하는지 확인하려 한다.

그래서 네가 만드는 것은 홍보안이 아니라 **검증 프로그램**이다. 목적은 매출이 아니라
**"이 아이템이 이 상권에서 통하는가"를 정해진 기간 안에 판정할 수 있게 만드는 것**이다.

입력은 셋이다. 사실의 등급이 다르니 섞어 인용하지 말 것:
- [자리] 공실 유닛의 건축물대장 사실(면적·층·직전 업종·건물 공실률) — 관측값
- [상권 컨텍스트] Platform 수집 데이터(업종 분포·블로그 키워드·검색 트렌드·시간대별
  유동/매출·행사) — 관측값
- [검증 브리프] 창업자가 적은 아이템·가설·기간·예산·차별점 — **주장과 계획**이다.
  차별점이 사실인지를 확인하려고 검증을 도는 것이므로, 사실로 단정해 쓰지 말 것.

원칙 (Humanistic Authority — 균형·공생·공감):
- **있지도 않은 경험을 근거로 삼지 않는다.** 단골·기존 고객·쌓인 방문 후기·입소문은
  이 자리에 존재하지 않는다. 다만 재방문율·후기 수집을 **앞으로 측정할 지표**로 적는
  것은 정상이다. 있다고 말하는 것과 재겠다고 말하는 것을 가른다.
- **입력에 없는 금액을 쓰지 않는다.** 객단가·할인액·쿠폰액을 임의로 정하지 말 것 —
  얼마를 쓸지·깎을지는 창업자가 정할 몫이다. 예산은 브리프에 적힌 구간에서만 끌어낸다.
- 과장·허위·검증 불가한 최상급 표현 금지. 상권 공동 활성화(공생)를 해치는 제안
  (이웃 가게 비방·출혈 경쟁 조장) 금지.
- **기존 행사의 "인용"과 신규 행사의 "제안"을 가른다.** 둘은 성격이 다르다 —
  인용은 사실 주장이고 제안은 계획이다. 섞으면 지어낸 행사가 사실처럼 나간다.
  - `mode="cite"` — 컨텍스트에 실린 행사만. 이름·기간·거리를 **그대로** 인용한다.
    컨텍스트에 없는 행사를 cite 로 적는 것은 거짓이다.
    "확인된 예정 행사가 없다"·"연계를 제안하지 말 것"이 적혀 있으면 cite 를 쓰지 않는다.
  - `mode="propose"` — **새로 열자고 제안**하는 공동 행사·연계. 아직 없는 것이므로 있는
    것처럼 쓰지 말고 제안임이 드러나게 적는다. rationale 에 **빈 시간대의 격차 수치를
    그대로 인용**해야 한다(예: "6~11시 유동 19.2 / 매출 10.7 = +8.5%p"). 수치 없이
    제안하면 "상권 플리마켓 참여" 같은 어느 상권에나 해당하는 말이 된다.
  - `mode="own"` — 행사가 아닌 **자체 접점**(팝업 부스 운영·입간판·시식·외부 사이니지).
    협업 주체가 없어도 된다. 행사가 아닌 것을 propose 로 적지 말 것.
- 특정 플랫폼·자본에 편중되지 않게 채널을 균형 있게 섞는다.
- 각 제안에는 반드시 근거(rationale)를 명시한다. 근거는 자리·상권의 수치(면적·층·직전
  업종·공실률·유동/매출 격차·업종 분포·검색 트렌드)와 브리프의 가설에서 끌어낸다.
- ha_check 필드에 위 기준으로 자체 점검한 결과를 1~2문장으로 기술한다.

## 세 출력은 성격이 다르다

**online (모객, 2~3건)**: 창업자가 **혼자 실행**해 검증 기간에 사람을 오게 하는 활동.
- 검증 기간이 짧다는 것을 전제로 쓴다. 몇 달에 걸쳐 쌓는 제안은 여기에 맞지 않는다.
- `target` 목표 고객 세그먼트. 상권 수요신호의 연령·성별·시간대에서 끌어낸다.
- `budget_share` 예산 **배분 비율(%)** 정수. **online 제안들의 합이 100 이 되게** 한다.
  절대 금액을 쓰지 않는다 — 얼마를 쓸지는 창업자가 정할 몫이다.
- `kpi` 이 채널 하나의 목표 지표(도달·저장·문의·방문 전환 등).

**offline (자리·상권 연계, 2~3건)**: 창업자 혼자 할 수 없는 일이다. 팝업은 자리를
빌려야 하고, 상권 행사의 57%가 공공·준공공 주최다. 그래서 "당신이 하세요"가 아니라
**"누구와 무엇을 제안하세요"**로 쓴다.
- `channel` 은 채널이 아니라 **형식**이다(팝업 부스·공동 프로모션·야외 매대·공동 배너).
- `timing` 시기. 검증 기간 **안**이어야 하고, 상권이 비어 있는 시간대(유동이 매출을
  앞서는 구간)를 우선한다. 3일짜리 검증에 "둘째 달부터"는 말이 안 된다.
- `actors` 함께할 주체를 **구체적으로**(건물주·상인회·구청·인근 점포·문화재단).
  공실을 짧게 빌리려면 건물주·관리인이 반드시 들어간다. 최소 1개.
- `mode` 위 규칙대로 "cite" · "propose" · "own" 중 하나.
- **offline 이 전부 own 이면 안 된다** — 최소 1건은 상권 주체와 함께하는 cite 또는 propose.

**signals (검증 지표, 2~4건)**: 이 출력의 결론이다. 무엇을 세면 "통했다"고 할 것인가.
- `name` 지표명 — 이 검증 방식으로 **실제로 잴 수 있는** 것만. 팝업에서 재구매율을
  재겠다고 하면 기간 안에 잴 수 없다.
- `method` 측정 방법을 구체적으로(입장 카운터·POS 영수증·신청 폼·설문 문항).
- `target` 목표선. **숫자를 반드시 넣는다** — "많이 오면"은 지표가 아니다.
- `decision` 가설을 **기각할** 조건. 검증을 시작하기 전에 적어야 한다. 이게 없으면
  결과를 보고 나서 성공이었다고 말을 맞추게 된다.
- 목표선의 숫자는 상권 컨텍스트의 유동·업종 분포에서 끌어내고, 그 출처를 method 나
  target 에 밝힌다. 금액 목표를 적을 때는 브리프 예산 밖의 금액을 지어내지 않는다.

한국어로 작성한다."""


def _context_path(slug: str) -> Path:
    """상권 컨텍스트 CSV 경로."""
    return _GOLD_DIR / slug / "program_content_context.csv"


def _load_context_rows(slug: str) -> list[tuple[str, str, float]] | None:
    """컨텍스트 CSV 를 (kind, key, value) 행 목록으로. 없거나 깨졌으면 None.

    **표준 라이브러리로만 읽는다 — pandas 를 쓰지 않는다.** 예전에는 파케이를
    `pd.read_parquet` 로 읽었는데, 배포(Vercel 서버리스)에는 pandas 도 pyarrow 도
    없어서 `import pandas` 가 그대로 실패했다. 그 실패는 아래 호출부의 except 에
    잡혀 컨텍스트가 **항상 None** 이 됐고, 결과적으로 상권 단위 LLM 경로가
    프로덕션에서 한 번도 돈 적이 없다(2026-08-06 발견). 화면은 시드 카피를
    보여주고 있었으므로 눈으로는 알 수 없었다.

    파케이를 되살리는 대신 산출물을 CSV 로 옮겼다 — 3열 80행짜리 표에 파케이는
    이득이 없고(실측 174KB → 116KB 로 **작아졌다**), 런타임에 읽히는 다른 Gold
    산출물은 이미 전부 JSON/GeoJSON 이라 이것만 예외였다.

    인코딩은 utf-8-sig 로 읽는다 — BOM 이 있으면 벗기고 없으면 그대로 읽으므로
    파이프라인이 어느 쪽으로 쓰든 안전하다.
    """
    path = _context_path(slug)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = []
            for r in csv.DictReader(f):
                try:
                    rows.append((r["kind"], r["key"], float(r["value"])))
                except (KeyError, TypeError, ValueError):
                    continue    # 값이 비거나 깨진 행은 건너뛴다 (전체를 버리지 않는다)
        return rows or None
    except OSError:
        return None


def context_rows(district_id: str | None) -> list[tuple[str, str, float]] | None:
    """상권 컨텍스트 CSV 를 (kind, key, value) 행으로 — **거점 id 로** 묻는 공개 입구.

    Platform(services/platform_profile)이 같은 파일을 읽되 파서를 두 벌 두지 않도록
    별칭 해석·슬러그 검증까지 여기서 한 번에 한다. 로더가 갈리면 인코딩·결측 규칙이
    조용히 달라져 두 화면이 같은 거점을 다르게 말하게 된다.
    """
    slug = _DISTRICT_ALIAS.get(district_id or "", district_id or "")
    if not _SLUG_RE.match(slug):
        return None
    return _load_context_rows(slug)


def _top_n(rows: list[tuple[str, str, float]], kind: str, n: int = 5) -> list[tuple[str, float]]:
    """해당 kind 의 상위 n건 (value 내림차순) — 예전 nlargest 대체."""
    hits = [(k, v) for kd, k, v in rows if kd == kind]
    return sorted(hits, key=lambda kv: kv[1], reverse=True)[:n]


def _district_context(district_id: str | None) -> str | None:
    """Platform Gold(program_content_context)에서 상권 컨텍스트 요약 텍스트 생성.

    거점 id 형식이 아니거나 Gold 미적재면 None (컨텍스트 없이 생성).
    """
    slug = _DISTRICT_ALIAS.get(district_id or "", district_id or "")
    if not _SLUG_RE.match(slug):
        return None
    rows = _load_context_rows(slug)
    if rows is None:
        return None

    parts: list[str] = []
    if (kw := _top_n(rows, "blog_keyword")):
        parts.append("블로그 언급 키워드: " + ", ".join(
            f"{k}({int(v)}건)" for k, v in kw))
    if (cat := _top_n(rows, "category")):
        parts.append("상권 업종 분포: " + ", ".join(
            f"{k} {int(v)}곳" for k, v in cat))

    # 트렌드는 kind 가 "trend:{이름}" 이라 이름별로 묶는다(예전 groupby 대체).
    trends: dict[str, list[tuple[str, float]]] = {}
    for kd, k, v in rows:
        if kd.startswith("trend:"):
            trends.setdefault(kd, []).append((k, v))
    summaries = [s for kd, pts in trends.items()
                 if (s := _trend_summary(kd.split(":", 1)[1], pts))]
    if summaries:
        parts.append("검색 트렌드(최근 6개월, 방향은 계산된 값이다): " + "; ".join(summaries))

    if (dm := _demand_context(rows)):
        parts.append(dm)

    # 행사는 수요신호의 **빈 시간대**를 알아야 고를 수 있다 — 두 축을 같은 눈금으로 맞춘다.
    if (ev := _events_context(district_id, _gap_band(rows))):
        parts.append(ev)
    return "\n".join(parts) or None


# 오프라인 제안이 겨냥할 수 있는 시간대 — 00~06 은 뺀다.
# 심야에 유동이 매출을 앞서는 건 상권의 빈틈이 아니라 가게가 닫혀 있어서다. 빼지 않으면
# 대다수 거점에서 00~06 이 '최대 격차'로 뽑히고 새벽 플리마켓 같은 제안이 나온다.
# data/pipelines/build_program_demand.ACTIONABLE_TMZONS 와 같은 값을 유지할 것.
_ACTIONABLE_TMZONS = ["06_11", "11_14", "14_17", "17_21", "21_24"]
_TMZON_LABEL = {"00_06": "0~6시", "06_11": "6~11시", "11_14": "11~14시",
                "14_17": "14~17시", "17_21": "17~21시", "21_24": "21~24시"}


def _gap_band(rows: list[tuple[str, str, float]]) -> str | None:
    """유동 대비 매출이 가장 빈 시간대(= 오프라인 유입 확대가 겨냥할 구간).

    매출이 결측인 거점은 격차를 만들 수 없으므로 None — 없는 근거를 지어내지 않는다.
    """
    d = {k: v for kd, k, v in rows if kd == "demand"}
    gaps = [(d[f"flpop_tmzon_{t}"] - d[f"selng_tmzon_{t}"], t) for t in _ACTIONABLE_TMZONS
            if f"flpop_tmzon_{t}" in d and f"selng_tmzon_{t}" in d]
    return max(gaps)[1] if gaps else None


def _demand_context(rows: list[tuple[str, str, float]]) -> str | None:
    """TRDAR 상권 수요신호를 컨텍스트 문장으로 (build_program_demand 산출 `demand` 행).

    Program 의 대상이 **아직 이 자리에서 장사해 본 적 없는 창업자**라 리뷰가 없다.
    제안의 근거를 리뷰 대신 이 수치가 맡는다 — 없으면 "상권 플리마켓 참여" 같은 어느
    상권에나 해당하는 말이 된다. 검증 지표의 목표선도 여기서 끌어낸다.

    두 출력이 같은 표에서 갈린다:
      - 매출이 유동을 앞서는 시간대 = **전환 구간** → 온라인(모객) 광고를 태울 곳
      - 유동이 매출을 앞서는 시간대 = **빈 구간** → 오프라인(자리·연계)이 칠 곳
    """
    d = {k: v for kd, k, v in rows if kd == "demand"}
    if not d:
        return None

    parts: list[str] = []

    pairs = [(t, d[f"flpop_tmzon_{t}"], d[f"selng_tmzon_{t}"]) for t in _ACTIONABLE_TMZONS
             if f"flpop_tmzon_{t}" in d and f"selng_tmzon_{t}" in d]
    if pairs:
        parts.append("시간대별 유동/매출 구성비(%): " + ", ".join(
            f"{_TMZON_LABEL[t]} 유동 {f:.1f}/매출 {s:.1f}" for t, f, s in pairs))
        gap = max(pairs, key=lambda p: p[1] - p[2])
        conv = min(pairs, key=lambda p: p[1] - p[2])
        parts.append(
            f"유동 대비 매출이 가장 빈 시간대는 {_TMZON_LABEL[gap[0]]}"
            f"(+{gap[1] - gap[2]:.1f}%p) — 오프라인 유입 확대 제안은 이 구간을 겨냥한다. "
            f"매출이 가장 앞서는 시간대는 {_TMZON_LABEL[conv[0]]}"
            f"({conv[1] - conv[2]:+.1f}%p) — 온라인 퍼포먼스 노출은 이 구간에 둔다.")
    elif any(k.startswith("flpop_tmzon") for k in d):
        # 유동만 있고 매출이 결측인 거점 — 격차를 지어내지 않는다.
        parts.append("시간대별 매출 구성비는 이 상권에서 결측이다 — 유동·매출 격차를 근거로 쓰지 말 것.")

    ages = [(a, d[f"agrde_{a}"]) for a in ("10", "20", "30", "40", "50", "60_above")
            if f"agrde_{a}" in d]
    if ages:
        top = sorted(ages, key=lambda x: -x[1])[:3]
        lab = {"60_above": "60대+"}
        parts.append("유동인구 구성: " + ", ".join(
            f"{lab.get(a, a + '대')} {v:.1f}%" for a, v in top)
            + (f", 여성 {d['fml_share']:.1f}%" if "fml_share" in d else ""))

    if "flpop_wkend" in d and "selng_wkend" in d:
        parts.append(f"주말 비중: 유동 {d['flpop_wkend']:.1f}% / 매출 {d['selng_wkend']:.1f}%")

    biz = []
    if "stor_co" in d:
        biz.append(f"점포 {int(d['stor_co'])}곳")
    if "frc_share" in d:
        biz.append(f"프랜차이즈 {d['frc_share']:.1f}%")
    if "clsbiz_rt" in d:
        biz.append(f"폐업률 {d['clsbiz_rt']:.2f}%")
    if biz:
        parts.append("상권 구성: " + " · ".join(biz))

    if "trdar_n" in d:
        n, sn = int(d["trdar_n"]), int(d.get("trdar_selng_n", d["trdar_n"]))
        note = f"(TRDAR 상권 {n}개 유동 가중평균"
        note += f", 매출은 {sn}개" if sn != n else ""
        parts.append(note + ")")

    return "\n".join(parts) or None


# 프롬프트에 실을 행사 수 상한. ikseon 78건처럼 도심 거점은 전부 실으면 컨텍스트를
# 행사가 잠식한다. 가까운 순으로 이만큼만 준다.
_MAX_CONTEXT_EVENTS = 5

# 관람객이 걸어서 넘어올 만한 거리. 이 밖의 행사는 "연계"의 근거가 되지 못한다 —
# 785건의 거리 중앙값이 989m 이고, 500m 안에 행사가 있는 거점은 54곳 중 28곳뿐이다.
# 남은 26곳에 먼 행사를 실으면 LLM 이 남의 동네 행사를 우리 골목 것처럼 쓴다.
_WALKABLE_M = 500


def _events_context(district_id: str | None, gap_band: str | None = None) -> str | None:
    """상권 행사를 컨텍스트 문장으로 — 오프라인 제안이 공허해지는 것을 막는다.

    이 함수 이전에는 컨텍스트에 행사가 없었고, 그래서 오프라인 제안이 "상권
    플리마켓/팝업 부스 참여" 같은 **어느 상권에나 해당하는 말**로 나왔다. 실제 행사
    785건이 이미 Gold 에 있는데 쓰지 않고 있었다.

    세 경우를 구분한다 — 이 구분이 이 함수의 요점이다:

      None(Gold 미적재)  행사를 아는 바가 없다 → 아무 말도 하지 않는다.
                         "행사 없음"이라고 쓰면 모르는 것을 안다고 주장하는 것이다.
      [](예정 행사 없음)  **명시적으로 없다고 말하고 제안을 금지한다.** 침묵하면 LLM 이
                         일반론으로 행사 참여를 지어낸다 — 고치려던 바로 그 증상이다.
      목록 있음           걸어갈 거리(_WALKABLE_M) 안의 것만, 가까운 순 상위 N건.

    **거리를 반드시 싣는다.** 이 API 는 공공·문화시설 행사 중심이라 가두 상권 커버리지가
    낮다 — 가로수길 2건은 둘 다 800m 밖이다. 거리를 빼면 LLM 이 남의 동네 행사를
    "우리 골목 행사"처럼 쓴다. 걸어갈 거리 안에 하나도 없으면 그 사실을 말하고
    연계 제안을 금지한다(네 번째 경우 — 2026-08-16 추가).

    ## 빈 시간대와의 교집합 (2026-08-16)

    `gap_band` 는 수요신호에서 온 "유동 대비 매출이 가장 빈 시간대"다. 그 시간에 실제로
    열리는 행사가 연계 후보이므로 먼저 보여주고, 하나도 없으면 **없다고 밝힌다** —
    시간대를 맞춘 것처럼 쓰는 것을 막는다.

    한때 "문화행사라 상권 상업이벤트와 종류가 다르다"고 판단해 외부 소스를 찾으려 했는데,
    거리로 걸러 열어보니 서울아트위크(59m)·DDP 뮤직페스티벌(107m)·서울야외도서관(158m)
    처럼 광장 활성화 그 자체인 행사들이었다. 종류가 아니라 **필터와 속성이 없던 것**이다.
    시각(`PRO_TIME`)도 원천에 785/785 있었는데 Gold 로 넘기지 않고 있었다.
    """
    if not district_id:
        return None
    rows = events.for_district(district_id)
    if rows is None:
        return None
    if not rows:
        return ("상권 행사: 확인된 예정 행사가 없다(공공 문화행사 기준). "
                "행사 참여·연계를 제안하지 말 것 — 없는 행사를 지어내는 셈이다.")

    # 거리 미상(시드 잔재)은 '멀다'도 '가깝다'도 아니다. 걸러내되 버리지는 않는다 —
    # 거리가 있는 것이 하나도 없을 때는 이들이라도 실어야 정보가 사라지지 않는다.
    known = [e for e in rows if e.get("distance_m") is not None]
    unknown = [e for e in rows if e.get("distance_m") is None]
    walkable = [e for e in known if e["distance_m"] <= _WALKABLE_M]

    if not walkable and not unknown:
        nearest = min(e["distance_m"] for e in known) if known else None
        far = f"(가장 가까운 것이 {nearest}m)" if nearest is not None else ""
        return (f"상권 행사: {_WALKABLE_M}m 안에 예정 행사가 없다{far}. "
                "걸어갈 거리가 아니므로 관람객 유입을 전제한 연계 제안을 하지 말 것 — "
                "매장 자체 접점을 제안한다.")
    if not walkable:
        items = "; ".join(f"{e.get('n')}({e.get('when')} · {e.get('place') or '장소 미상'})"
                          for e in unknown[:_MAX_CONTEXT_EVENTS])
        return ("상권 행사(거리 미상 — 걸어갈 거리인지 확인되지 않았다): " + items
                + " — 거리를 모르므로 관람객 유입 규모를 단정하지 말 것.")

    # 빈 시간대에 실제로 열리는 행사가 연계 후보다. 그 교집합을 먼저 보여준다.
    hit = [e for e in walkable if gap_band and gap_band in (e.get("tm") or [])]
    pick = (hit or walkable)
    pick = sorted(pick, key=lambda e: e.get("distance_m") or 10**9)[:_MAX_CONTEXT_EVENTS]

    items = []
    for e in pick:
        dist = e.get("distance_m")
        where = f"{e.get('place') or '장소 미상'}, {dist}m" if dist is not None \
            else (e.get("place") or "장소 미상")
        when = e.get("when")
        if e.get("time"):
            when = f"{when} {e['time']}"
        items.append(f"{e.get('n')}({when} · {where})")

    head = "상권 행사(공공 문화행사 실데이터, 걸어갈 거리 안)"
    if hit:
        head += f" — 아래는 **빈 시간대({_TMZON_LABEL.get(gap_band, gap_band)})에 열리는** 행사다"
    elif gap_band:
        head += (f" — 빈 시간대({_TMZON_LABEL.get(gap_band, gap_band)})에 열리는 행사는 없다. "
                 "시간대를 맞춰 연계했다고 쓰지 말 것")
    return (head + ": " + "; ".join(items)
            + " — 거리와 시각을 확인하고, 거점 밖 행사를 상권 안 행사처럼 쓰지 말 것.")


# 트렌드 방향 판정 임계 — 최근 3개월 평균이 직전 3개월 평균 대비 이만큼 벗어나야 방향을 붙인다.
# 5%는 검색량의 월별 잡음(계절·요일 구성)을 방향으로 오독하지 않을 정도로 잡은 값이다.
_TREND_FLAT_BAND = 0.05


def _trend_summary(name: str, points: list[tuple[str, float]]) -> str | None:
    """검색 트렌드 한 계열을 **방향이 붙은 한 문장**으로 요약.

    `points` 는 (기간키, 값) 쌍이고 정렬은 여기서 한다 — 호출부가 순서를 보장하지
    않아도 되게. (2026-08-06: pandas 제거로 DataFrame 대신 평범한 쌍을 받는다.)

    왜 숫자를 그대로 넘기지 않는가 — 2026-08-01 실사고. 이 함수 이전에는 최근 3개월의
    원시 수치만 프롬프트에 실었고(`신사동 2026-05=67.7; …`), LLM 이 하락 시계열을 보고
    "신사동을 찾는 발걸음이 다시 늘고 있는 요즘"이라고 썼다. 같은 실행에서 가게 단위는
    방향을 맞혔으므로 모델이 아니라 **해석을 LLM 에 맡긴 설계**가 원인이다.
    방향은 여기서 계산해 확정하고, LLM 에는 판정 결과를 문장으로 준다.

    판정: 최근 3개월 평균 vs 직전 3개월 평균의 상대 변화. ±5%(_TREND_FLAT_BAND) 안이면 보합.
    6개 점이 안 되면 방향을 만들지 않고 None — 근거 없는 방향을 주느니 트렌드를 빼는 게 낫다.
    (Gold 단계에서 미완성 달은 이미 잘려 있다 — data/pipelines/build_gold._complete_trend_points)
    """
    vals = [v for _, v in sorted(points, key=lambda kv: kv[0])][-6:]
    if len(vals) < 6:
        return None
    prior = sum(vals[:3]) / 3
    recent = sum(vals[3:]) / 3
    if prior <= 0:
        return None
    change = (recent - prior) / prior
    label = "보합" if abs(change) < _TREND_FLAT_BAND else ("상승" if change > 0 else "하락")
    return f"{name} {label}({prior:.1f}→{recent:.1f}, {change * 100:+.1f}%)"


def _site_context(brief: dict) -> str | None:
    """입력 계약 ①층(자리) — `unit_id` 를 준 요청에만 붙는다 (services/program_site).

    `unit_id` 가 없으면 None 이다. **거점만 주고 대표 유닛을 자동으로 끼워 넣지
    않는다** — 창업자가 아직 자리를 고르지 않았는데 엉뚱한 공실의 면적·직전 업종이
    섞이면, 생성물이 그 자리를 검증 무대의 사실인 양 인용한다.
    """
    if not brief.get("unit_id"):
        return None
    return program_site.site_context(brief.get("district_id"), brief["unit_id"])


def _call_llm(brief: dict, district_ctx: str | None,
              site_ctx: str | None = None,
              brief_ctx: str | None = None) -> LLMProgramPlan:
    """Claude 실호출 — 검증 브리프 + 자리 + 상권 → 구조화 검증 프로그램.

    세 층을 **따로** 싣는 이유는 사실의 등급이 다르기 때문이다: 상권층은 주변의 관측,
    자리층은 이 자리의 대장 사실, 브리프는 창업자의 계획과 주장이다. 한 덩어리로
    합치면 생성물이 근거를 뒤섞어 인용한다.

    vision(사진) 입력은 없다 — 아직 찍을 가게가 없다(2026-09-17 대상 재정의).
    """
    import anthropic

    mode = MODE_LABEL.get(str(brief.get("mode")), str(brief.get("mode") or ""))
    stage = STAGE_LABEL.get(str(brief.get("stage")), str(brief.get("stage") or ""))
    text = (
        f"아이템: {brief['item']} (업종: {brief['category']})\n"
        f"검증 방식: {mode} · 단계: {stage}\n"
        f"자리 주소: {brief.get('address') or '(미정)'}"
    )
    if brief_ctx:
        text += f"\n\n{brief_ctx}"
    if site_ctx:
        text += f"\n\n{site_ctx}"
    if district_ctx:
        text += f"\n\n[상권 컨텍스트 — Platform 수집 데이터]\n{district_ctx}"

    client = anthropic.Anthropic(api_key=settings.llm_api_key)
    response = client.messages.parse(
        model=settings.llm_model,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
        output_format=LLMProgramPlan,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise ValueError(f"LLM 구조화 출력 파싱 실패 (stop_reason={response.stop_reason})")
    return parsed


def generate_program(brief: dict) -> dict:
    """검증 프로그램(모객 · 자리·연계 · 검증 지표) 생성.

    LLM 키(settings.llm_api_key) 설정 시 LLM 생성, 미설정·실패 시 규칙 기반 스텁.

    생성 직후 **HA 후처리 검증**(services/ha_guard.py)을 통과해야 응답이 된다.
    `ha_check` 는 LLM 이 스스로 통과했다고 적은 문장이라 근거가 아니다 — 입력과 대조해
    거짓이 확정되는 위반(지어낸 금액, 확정 트렌드 역행, 있지도 않은 경험 주장)이면
    생성물을 버리고 스텁으로 내려간다. 경고 등급은 응답을 살리고 `ha_findings` 로 밝힌다.

    반환: ProgramPlan 스키마 dict.
    """
    if settings.llm_api_key:
        try:
            ctx = _district_context(brief.get("district_id"))
            site_ctx = _site_context(brief)
            brief_ctx = program_brief.brief_context(brief)
            parsed = _call_llm(brief, ctx, site_ctx, brief_ctx)
            # HA 검증에도 **자리층을 넣는다.** 빼면 자리의 수치(면적·공실률·직전 업종)를
            # 정상 인용한 문장이 근거 없는 주장으로 걸린다 — 행사 요금을 컨텍스트에
            # 넣어야 했던 것(2026-08-06)과 같은 이유다.
            findings = ha_guard.check_program(
                parsed, brief, "\n".join(c for c in (ctx, site_ctx) if c) or None)
            if ha_guard.has_violation(findings):
                print(f"[marketing] HA 검증 위반 → 생성물 폐기: {ha_guard.summarize(findings)}")
                return _rule_stub(brief, findings)
            return {
                **_identity(brief),
                "online": [{**p.model_dump(), "kind": "online"} for p in parsed.online],
                "offline": [{**p.model_dump(), "kind": "offline"} for p in parsed.offline],
                "signals": [s.model_dump() for s in parsed.signals],
                "ha_check": parsed.ha_check,
                "source": "llm",
                "ha_findings": [f.model_dump() for f in findings],
            }
        except Exception as exc:
            print(f"[marketing] LLM 생성 실패 → 규칙 기반 폴백: {exc}")

    return _rule_stub(brief)


def _identity(brief: dict) -> dict:
    """응답 머리의 네 칸 — 무엇을, 어떤 방식으로, 누가 검증하는가."""
    return {
        "item": brief["item"],
        "category": brief["category"],
        "mode": brief.get("mode") or "",
        "stage": brief.get("stage") or "",
    }


def _claim_rationale(brief: dict) -> str | None:
    """근거를 **창업자가 낸 차별점**에서 만든다 — 리뷰를 대신하는 원천이다.

    주장이라는 것을 문장 안에 남긴다. 스텁이라도 관측값과 주장을 섞어 적지 않는다.
    """
    xs = brief.get("differentiators") or []
    if not xs:
        return None
    return ("창업자가 제출한 차별점(" + " · ".join(str(x) for x in xs[:3])
            + ") 기반 — 검증 대상인 주장이지 확인된 사실이 아니다")


def _rule_stub(brief: dict, findings: list | None = None) -> dict:
    """규칙 기반 스텁 (LLM 미설정/실패/**HA 위반 폐기** 폴백).

    findings 를 받으면 그대로 실어 보낸다 — 스텁이 나온 이유가 "키가 없어서"인지
    "생성물이 검증에 걸려서"인지 화면이 구분할 수 있어야 한다.

    스텁도 **검증 프로그램의 모양**을 지킨다. 지표 없이 채널안만 내려보내면 화면이
    "지표는 원래 없는 것"으로 읽고, 이 트랙이 홍보 생성기로 되돌아간다.
    """
    mode = str(brief.get("mode") or "popup")
    mode_label = MODE_LABEL.get(mode, mode)
    window = program_brief.run_window(brief)
    period = (f"{window[0].isoformat()}~{window[1].isoformat()}" if window
              else f"{mode_label} 기간")
    target = brief.get("target_customer") or "상권 주 이용 연령대"

    online = [
        {"channel": "인스타그램", "kind": "online",
         "content": f"{mode_label} 예고 — '{brief['item']}'의 준비 과정과 운영 일정을 "
                    "릴스로 주 2회 올리고, 마지막 게시물에 위치·기간을 고정한다",
         "rationale": (_claim_rationale(brief)
                       or "아직 이 자리에서의 실적이 없다 — 준비 과정 자체를 소재로 삼는다"),
         "target": target, "budget_share": 60, "kpi": "저장 수·프로필 방문"},
        {"channel": "네이버 블로그·플레이스", "kind": "online",
         "content": f"'{brief['category']}' 지역 키워드로 {mode_label} 일정 안내 글을 올리고 "
                    "지도 검색 동선을 연다",
         "rationale": "네이버 지도 유입 동선(검색→플레이스) 확보 — 검증 기간이 짧아 "
                      "검색으로 들어오는 사람을 놓치면 표본이 줄어든다",
         "target": "지역 검색 유입", "budget_share": 40, "kpi": "검색 노출·클릭"},
    ]
    # 오프라인은 혼자 할 수 없으므로 **협업 주체(actors)가 비면 안 된다** — 스텁이라도
    # "당신이 알아서 하세요"로 내려보내지 않는다. 공실을 짧게 빌리는 일이라 건물주가
    # 첫 주체다. 스텁은 실제 행사를 모르므로 mode 는 "propose"·"own" 만 쓴다
    # (cite 는 컨텍스트에 실린 행사에만 쓴다).
    offline = [
        {"channel": "단기 임대 협의", "kind": "offline",
         "content": f"건물주·관리인에게 {mode_label} 단기 사용을 제안한다 — 기간·원상복구·"
                    "간판 노출 범위를 먼저 문서로 맞춘다",
         "rationale": "공실을 짧게 빌리는 일이라 소유자 동의 없이는 시작 자체가 안 된다",
         "timing": period, "actors": ["건물주", "건물 관리인"], "mode": "propose"},
        {"channel": "자리 앞 접점", "kind": "offline",
         "content": "입간판·시식(체험)으로 보행 유동을 안으로 들인다",
         "rationale": "보행 유동 전환 — 과장 없는 실체 기반 소구",
         "timing": "보행 유동이 많은 시간대", "actors": ["인근 점포"], "mode": "own"},
    ]
    name, method, goal, decision = _MODE_SIGNAL.get(mode, _MODE_SIGNAL["popup"])
    signals = [
        {"name": name, "method": method, "target": goal, "decision": decision},
        {"name": "가설 확인 응답", "method": "현장 설문 1문항 — 브리프의 가설을 그대로 묻는다",
         "target": "응답 50건", "decision": "긍정 응답이 절반 미만이면 가설을 다시 세운다"},
    ]
    return {
        **_identity(brief),
        "online": online,
        "offline": offline,
        "signals": signals,
        "ha_check": "균형·공생·공감 기준 자체 점검 통과 (규칙 기반 스텁)",
        "source": "rule-stub",
        "ha_findings": [f.model_dump() for f in (findings or [])],
    }


_DISTRICT_SYSTEM_PROMPT = """너는 PlaceOS의 Program(상권 단위 마케팅) 온라인 콘텐츠 생성기다.
입력된 상권 컨텍스트(블로그 언급 키워드 빈도·업종 분포·검색 트렌드)만을 근거로,
그 상권의 온라인 콘텐츠 소재를 한 줄 카피 형태로 제안한다.

형식: "{소재 문장} #{해시태그} #{해시태그}" — 한 줄에 해시태그 2개.

원칙 (Humanistic Authority — 균형·공생·공감):
- 컨텍스트에 실제로 나타난 키워드·업종만 소구한다. 데이터에 없는 점포명·행사·수치를 지어내지 않는다.
- **데이터가 말하지 않는 방향을 주장하지 않는다.** 검색 트렌드에는 이미 판정된 방향
  (상승/보합/하락)이 붙어 있다. 그 방향과 어긋나게 쓰지 말 것 — '하락'인데 "다시 늘고 있는",
  '보합'인데 "급증하는" 식의 서술은 금지다. 하락·보합이면 유입 증가를 전제하지 말고
  이미 있는 강점(키워드·업종)에 소구하거나, 트렌드를 언급하지 않는다.
- 특정 점포나 자본에 편중하지 않고 상권 전체의 활성화를 향한다.
- 과장·허위·검증 불가한 최상급 표현을 쓰지 않는다.
- **금액을 쓰지 않는다.** 상권 컨텍스트에는 가격 정보가 없으므로 어떤 금액을 적든 지어낸
  값이다("1만원대 점심" 같은 표현 금지).
- ha_check 에 위 기준으로 자체 점검한 결과를 1~2문장으로 쓴다.

출력: online_contents 2~4건. 한국어로 작성한다."""


def _call_district_llm(name: str, sub: str, ctx: str) -> LLMDistrictContents:
    """Claude 실호출 — 상권 컨텍스트(Gold) → 온라인 콘텐츠 한 줄 카피."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.llm_api_key)
    response = client.messages.parse(
        model=settings.llm_model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=_DISTRICT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content":
                   f"상권: {name} ({sub})\n\n[상권 컨텍스트 — Platform 수집 데이터]\n{ctx}"}],
        output_format=LLMDistrictContents,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise ValueError(f"LLM 구조화 출력 파싱 실패 (stop_reason={response.stop_reason})")
    return parsed


# 상권 콘텐츠 LLM 결과 캐시: district_id → (컨텍스트 파일 mtime, online_contents, ha_findings)
#
# 캐시가 없으면 이 엔드포인트는 **호출마다** LLM 을 친다 — 실측 12~14초 + 매번 크레딧이
# 나간다(2026-08-01). 거점 심층 뷰가 이 응답을 기다리므로 화면이 그만큼 멈춘다.
# 입력은 Gold 컨텍스트 파일 하나뿐이라 mtime 이 그대로면 결과도 그대로다. TTL 이 아니라
# mtime 으로 무효화하는 이유: 파이프라인을 다시 돌리면 즉시 반영돼야 하고, 안 돌렸다면
# 하루가 지나도 다시 칠 이유가 없다. 프로세스 재시작 시 비므로 코드·시드 변경도 반영된다.
#
# **HA 검증에 걸려 폐기된 결과도 캐시한다** (online_contents 를 빈 리스트로). 안 그러면
# 같은 컨텍스트로 같은 위반을 반복 생성하며 호출마다 크레딧을 태운다. 컨텍스트가 바뀌거나
# 프로세스가 재시작되면(프롬프트·검증기 수정이 반영되는 시점) 어차피 다시 친다.
_district_llm_cache: dict[str, tuple[float, list[str], list[dict]]] = {}


def clear_district_cache() -> None:
    """상권 콘텐츠 LLM 캐시 비우기.

    평소에는 컨텍스트 파일 mtime 이 바뀌면 알아서 무효화되므로 부를 일이 없다.
    같은 프로세스 안에서 캐시를 강제로 버려야 할 때 쓴다(테스트 격리, 프롬프트 수정 후 재생성).
    """
    _district_llm_cache.clear()


def _context_mtime(district_id: str) -> float:
    """상권 컨텍스트의 mtime. 없으면 0.0 (캐시 키로만 쓴다).

    ⚠ 컨텍스트 입력이 **두 파일**이다 — program_content_context 와 행사 Gold. 행사가
    컨텍스트에 합류(2026-08-06)하면서 앞의 것만 보면 행사 파이프라인만 다시 돌린 경우
    무효화가 안 돼 낡은 카피가 남는다. 둘을 합쳐 키로 쓴다.
    """
    slug = _DISTRICT_ALIAS.get(district_id, district_id)
    if not _SLUG_RE.match(slug):
        return 0.0
    path = _context_path(slug)
    base = path.stat().st_mtime if path.exists() else 0.0
    return base + events.source_mtime()


def get_district_events(district_id: str) -> dict | None:
    """상권 행사만 — **LLM 을 부르지 않는** 조회(2026-09-13).

    Program 화면이 지도 위에 오프라인 홍보 장소(공공 문화행사)를 찍으려고 필요해졌다.
    `get_district_marketing` 을 그대로 부르면 행사 몇 개를 얻자고 온라인 콘텐츠 LLM 생성까지
    돈다(거점마다 1회, 인스턴스가 새로 뜨면 다시). 지도를 옮길 때마다 크레딧을 쓰는 화면이
    되므로 행사 경로만 떼어 낸다. 출처 규칙은 아래 함수와 같다 — 적재됐는데 0건이면 빈 목록.
    """
    base = svc.get_marketing(district_id)
    if base is None:
        return None
    real_events = events.for_district(district_id)
    if real_events is None:
        return {"district_id": district_id, "events": base["events"], "events_source": "seed"}
    return {"district_id": district_id, "events": real_events, "events_source": "seoul-open-data"}


def get_district_marketing(district_id: str) -> dict | None:
    """상권 단위 마케팅(행사 + 온라인 콘텐츠) — Program 2단계.

    online_contents: Gold(program_content_context)의 블로그 키워드·업종 분포를 근거로
      LLM 생성. 키 미설정·Gold 미적재·호출 실패 시 시드 카피로 폴백(source 로 구분).
      생성 결과는 컨텍스트 파일 mtime 기준으로 캐시한다(위 주석 참조).
    events: 서울열린데이터광장 문화행사 실데이터(services/events.py). LLM 은 절대
      관여하지 않는다 — 좌표·일정이 붙은 실물이라 지어내면 없는 행사를 지도에 찍게 된다.
      Gold 미적재면 시드로 폴백하되 events_source 로 출처를 밝힌다.
    """
    base = svc.get_marketing(district_id)
    if base is None:
        return None

    # 행사: 서울열린데이터광장 문화행사 실데이터. Gold 미적재면 시드로 폴백하되
    # 출처를 밝힌다. 적재됐는데 그 거점에 예정 행사가 없으면 **빈 목록 그대로** —
    # 시드로 채우면 지어낸 행사를 지도에 다시 찍는 셈이다.
    real_events = events.for_district(district_id)
    if real_events is None:
        base = {**base, "events_source": "seed"}
    else:
        base = {**base, "events": real_events, "events_source": "seoul-open-data"}

    ctx = _district_context(district_id)
    if settings.llm_api_key and ctx:
        mtime = _context_mtime(district_id)
        hit = _district_llm_cache.get(district_id)
        if hit and hit[0] == mtime:
            # contents 가 비어 있으면 HA 검증에 걸려 폐기된 것이다 — 시드로 내려가되
            # 폐기 사유(findings)는 그대로 실어 왜 시드인지 밝힌다.
            if hit[1]:
                return {**base, "online_contents": hit[1], "source": "llm",
                        "ha_findings": hit[2]}
            return {**base, "source": "seed", "ha_findings": hit[2]}

        d = DISTRICTS_BY_ID.get(district_id, {})
        try:
            parsed = _call_district_llm(d.get("name", district_id), d.get("sub", ""), ctx)
            if parsed.online_contents:
                findings = ha_guard.check_district(parsed, ctx)
                dumped = [f.model_dump() for f in findings]
                if ha_guard.has_violation(findings):
                    print("[marketing] 상권 콘텐츠 HA 검증 위반 → 생성물 폐기: "
                          f"{ha_guard.summarize(findings)}")
                    _district_llm_cache[district_id] = (mtime, [], dumped)
                    return {**base, "source": "seed", "ha_findings": dumped}
                _district_llm_cache[district_id] = (mtime, parsed.online_contents, dumped)
                return {**base, "online_contents": parsed.online_contents,
                        "source": "llm", "ha_findings": dumped}
        except Exception as exc:
            print(f"[marketing] 상권 콘텐츠 LLM 생성 실패 → 시드 폴백: {exc}")
    return {**base, "source": "seed"}

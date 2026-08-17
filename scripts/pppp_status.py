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
        "4대 히트맵 레이어 실데이터", 2 / 4,
        "공실 ✅ · 임대 ✅(R-ONE) · 유동 ⬜ 샘플 · 밀도 ⬜ 미연동",
        auto=False,
        evidence="apps/frontend/src/pages/MapShell.tsx:91 (SAMPLE 상수) · api/v1/heatmap.py",
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
            + (f" · macro-F1 {f1:.4f}(관측)" if f1 is not None else ""),
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
    # foot 은 절대수준만 실데이터(flpop)이고 거점 내 서열은 시드라 0.5 로 센다.
    rent = sum(1 for v in hubs.values() if v.get("rent_per_m2_krw_thousand"))
    foot = sum(1 for v in hubs.values() if v.get("flpop"))
    per_hub = (rent + 0.5 * foot) / (4 * total) if total else 0.0
    t.gates.append(Gate(
        "3-Tier 입력 4종 실데이터화", per_hub,
        f"rent {rent}/{total} ✅(R-ONE) · foot {foot}/{total} ◐(flpop+seed, 서열은 시드) · "
        f"area 0/{total} ⬜ · prem 0/{total} ⬜(표본 밀도 부족)",
    ))

    # 주석 문구로 판정하면 주석만 고쳐도 "연동됨"이 된다. 어댑터라면 반드시 밖으로
    # 나가는 호출이 있어야 하므로, HTTP 클라이언트 사용 여부를 신호로 쓴다.
    posting_py = (ROOT / "apps/backend/app/services/posting.py").read_text(encoding="utf-8")
    wired = any(s in posting_py for s in ("requests.", "httpx.", "urllib.request"))
    t.gates.append(Gate(
        "외부 AI 창업 코파일럿 어댑터", 1.0 if wired else 0.0,
        "미연동 — `_call_copilot` 이 항상 None 을 반환해 폴백만 돈다(입출력 명세 부재)"
        if not wired else "연동됨",
    ))

    t.gates.append(Gate(
        "`rec` 추천 기준 정의", 1.0,
        "회수 최단으로 정의·계산(recommend_tier). 손으로 적은 값이 카드에 노출되던 것을 "
        "걷어냈고, rec 필드가 없는 실제 건물 유닛도 통과한다",
        auto=False, evidence="apps/backend/app/services/districts.recommend_tier",
    ))

    vu = list(GOLD.glob("*/vacant_units.json"))
    t.gates.append(Gate(
        "실제 공실 유닛 인벤토리", len(vu) / total if total else 0.0,
        f"{len(vu)}/{total}거점 — 잔여 5곳은 **막힘이 아니라 재실행 대기**다(08-17 확인). "
        "종전 사유 'Tier2라 대장이 없다'는 대장 완주로 무효가 됐고, 상업면적이 실재한다",
    ))

    t.gates.append(Gate(
        "3-Tier 비용 모델 보정", 0.0,
        "month_cost 에 원가·인건비가 없다 — 마진 51~73%(실제 외식업 10~20%), 회수 "
        "0.5~1.6개월. factory 는 전수 실측에서 한 번도 1위가 못 된다. rec 을 정의하자 "
        "병목이 여기로 옮겨왔다",
        auto=False, evidence="apps/backend/app/services/districts.tier_scenarios",
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

    t.gates.append(Gate(
        "입력 계약 3층 (자리·상권·창업계획)", 1 / 3,
        "상권층만 있다. 자리층은 재료(공실 유닛 49/54)가 있는데 Program 이 읽지 않는다 — "
        "수집이 아니라 배선 과제다. 창업계획층(기업 입력)은 미구현이고, "
        "StoreProfile 은 영업 중 전제라 공실을 넣으면 '방문 후기형 포스팅'이 나온다",
        auto=False, evidence="docs/feature-program.md §0-B",
    ))

    t.gates.append(Gate(
        "출력 분리 (퍼포먼스 / 상권활성화)", 0.0,
        "미착수 — ChannelPlan 4필드로는 타겟·예산배분·협업주체를 못 담는다. "
        "프롬프트의 신규 행사 제안 금지 조항도 새 출력과 충돌",
        auto=False, evidence="apps/backend/app/schemas/marketing.py::ChannelPlan",
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

"""거점 체인 상태 — 한 거점이 등록에서 서빙까지 어디까지 왔는지 **산출물로** 판정한다.

`/hub-chain`(선형 체인)과 `/loop-engine`(상태기반 루프)이 둘 다 이 스크립트를 읽는다.
별도 진행 원장을 두지 않는 이유는 이 저장소의 실패 양식이 **선언이 낡는 것**이기
때문이다(`scripts/pppp_status.py` 와 같은 원칙 — 산출물이 단일 기준이다).

읽기만 한다. 네트워크를 타지 않고 아무 파일도 쓰지 않는다.

실행:
    python scripts/chain_status.py hwajeong geumchon
    python scripts/chain_status.py --all --json
    python scripts/chain_status.py hwajeong --next    # 다음 명령 한 줄만
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

BRONZE = ROOT / "data" / "bronze"
GOLD = ROOT / "data" / "gold"

# 게이트 임계 — 근거는 각 skill 에 적혀 있다.
STORES_PER_BLDG_MAX = 10.0   # 초과 = 계획상가 밀집 (plan-gyeonggi §3-B)
PRECISE_COVERAGE_MIN = 80.0  # 미만 = floor_approx 잔여 많음 (build_page_master 경고선)
ANCHOR_GAP_MAX = 30.0        # 초과 = 앵커 가드레일 위반 (test_gold_anchor_comparison_attached)

OK, PARTIAL, TODO, BLOCKED = "ok", "partial", "todo", "blocked"
MARK = {OK: "[OK]", PARTIAL: "[~ ]", TODO: "[  ]", BLOCKED: "[!!]"}


def _hubs() -> dict:
    from data.config import page_hubs as ph
    hubs = dict(ph.HUBS)
    hubs.update(getattr(ph, "GYEONGGI_HUBS", {}))
    return hubs


def _latest(slug: str, name: str) -> Path | None:
    """bronze/{slug}/{날짜}/{name} 중 가장 최근 것."""
    found = sorted(BRONZE.glob(f"{slug}/*/{name}"))
    return found[-1] if found else None


def _load(p: Path | None):
    if not p or not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _served_ids() -> set[str]:
    """API 거점 목록(화면 노출)에 오른 id. 수집 등록과 다른 축이다.

    시드(`seoul_pages.DISTRICTS`)가 아니라 **서빙이 실제로 내려보내는 합본**을 본다
    (2026-08-30 `measured_pages` 도입 — Gold 만으로 서는 거점이 시드 없이 목록에 오른다).
    시드만 세면 화정처럼 실제로 서빙되는 거점을 '미등재'로 잘못 보고한다.
    """
    try:
        from app.services.districts import PAGES_BY_ID
        return set(PAGES_BY_ID)
    except Exception:
        try:
            from app.data.seoul_pages import DISTRICTS
            return {d["id"] for d in DISTRICTS}
        except Exception:
            return set()


def _city_of(hub) -> tuple[str, str]:
    """(page_hubs 의 city, 백엔드 레지스트리가 아는 city). 어긋나면 그 자리에서 드러난다."""
    declared = getattr(hub, "city", "seoul")
    try:
        from app.data import cities
        known = declared if declared in cities.CITIES else ""
    except Exception:
        known = "?"
    return declared, known


def _served_vac(cov: dict | None) -> float | None:
    """서빙과 **같은 기준**의 거점 대표 공실률 — `floor_ouln` 만 센다.

    coverage.json 의 `reference_vacancy_pct` 를 쓰면 안 된다. 그 값은 `expos_units`
    (집합건물)를 섞은 것이고, 서빙(`services/gold_vacancy._COUNTED_METHODS`)은 그것을
    뺀다 — 집합상가 내부 점포가 분자에 안 잡혀 공실률이 78~86% 로 튀기 때문이다.
    두 값을 섞어 말하면 화면과 이 표가 다른 수를 말하게 된다.

    ⚠ API 최종값과도 완전히 같지는 않다. `GET /heatmap/vacancy` 는 지번 중복 제거와
      셀 집계를 더 하므로 소수점 단위로 다르다. **최종 확인은 API 로** 한다.
    """
    m = ((cov or {}).get("by_capacity_method") or {}).get("floor_ouln") or {}
    return m.get("vacancy_pct")


def stages(slug: str) -> list[dict]:
    """단계별 (이름, 상태, 근거, 다음 명령)."""
    hubs = _hubs()
    out: list[dict] = []

    def add(name, status, evidence, nxt=""):
        out.append({"stage": name, "status": status, "evidence": evidence, "next": nxt})

    # S1 등록
    hub = hubs.get(slug)
    if not hub:
        add("등록", TODO, f"page_hubs 에 {slug} 없음",
            "data/config/page_hubs.py 의 HUBS/GYEONGGI_HUBS 에 PageHub 한 줄 추가")
        return out
    declared, known = _city_of(hub)
    if known == "":
        add("등록", BLOCKED, f"page_hubs.city={declared} 인데 app/data/cities 에 없음",
            "apps/backend/app/data/cities.py 의 CITIES 에 같은 슬러그 추가")
    else:
        add("등록", OK, f"{hub.name} · city={declared} · r={hub.radius_m}m/{hub.stores_radius_m}m")

    # S2 점포 (Page 분자) + 계획상가 프로브
    stores = _load(_latest(slug, "stores_raw.json"))
    if not stores:
        add("점포", TODO, "bronze stores_raw.json 없음",
            f"python -m data.collectors.building_vacancy {slug} --no-ledger")
    else:
        bldgs = {s.get("bldMngNo") for s in stores if s.get("bldMngNo")}
        ratio = round(len(stores) / len(bldgs), 1) if bldgs else 0.0
        ev = f"점포 {len(stores):,} · 건물 {len(bldgs):,} · 건물당 {ratio}"
        if ratio > STORES_PER_BLDG_MAX and hub.caveat:
            add("점포", OK,
                ev + f" (>{STORES_PER_BLDG_MAX} 계획상가 밀집 · 예외 승인: {hub.caveat})")
        elif ratio > STORES_PER_BLDG_MAX:
            add("점포", BLOCKED, ev + f" (>{STORES_PER_BLDG_MAX} 계획상가 밀집)",
                "거점을 내리거나 집합상가 비중을 명시한 채 진행 — plan-gyeonggi 3-B")
        else:
            add("점포", OK, ev)

    # S3 폴리곤
    pj = _load(_latest(slug, "bldg_polygons.geojson"))
    if not pj:
        add("폴리곤", TODO, "bronze bldg_polygons.geojson 없음",
            f"python -m data.collectors.vworld_bldg {slug}")
    else:
        add("폴리곤", OK, f"{len(pj.get('features', [])):,}동")

    # S4~S5 대장 + 정밀 분모
    bv = _load(GOLD / slug / "building_vacancy.json")
    if not bv:
        add("대장", TODO, "gold building_vacancy.json 없음",
            f"python -m data.collectors.building_vacancy {slug}   # 쿼터: scripts/quota_preflight.py")
        add("정밀분모", TODO, "대장 선행", "")
    else:
        methods: dict[str, int] = {}
        for b in bv:
            m = b.get("capacity_method", "?")
            methods[m] = methods.get(m, 0) + 1
        add("대장", OK, f"{len(bv):,}동 · " + " ".join(f"{k}={v}" for k, v in sorted(methods.items())))
        precise = methods.get("floor_ouln", 0) + methods.get("expos_units", 0)
        # 분모는 **상업 건물만**이다. 비상업(non_commercial)·대장 미확인(no_ledger)은
        # 애초에 capacity 를 매길 대상이 아니라, 분모에 넣으면 정밀도가 낮아 보인다
        # (화정 2026-08-30: 비상업 182동을 섞어 40.6% → 실제 대상 기준 95.2%).
        target = len(bv) - methods.get("non_commercial", 0) - methods.get("no_ledger", 0)
        pct = round(precise / target * 100, 1) if target else 0.0
        if methods.get("floor_approx"):
            enough = pct >= PRECISE_COVERAGE_MIN
            # 임계를 넘겼으면 **명령을 제안하지 않는다.** 잔여 floor_approx 에는 '미시도'와
            # '판정완료(상업층 0 확정)'가 섞여 있고, 후자에 콜을 태우면 회수 0 이다
            # (2026-08-19 에 672콜/22동으로 겪었고 quota_preflight 가 같은 구분을 한다).
            # 화정 잔여 2동도 재호출 결과 회수율 0.0% 였다.
            add("정밀분모", PARTIAL if enough else TODO,
                f"floor_ouln+expos {pct}% · floor_approx {methods['floor_approx']}동 잔여"
                + (" (임계 충족 — 잔여는 판정완료일 수 있다)" if enough else ""),
                "" if enough else f"python -m data.collectors.floor_capacity {slug} --only-approx")
        else:
            add("정밀분모", OK, f"floor_approx 잔여 0 · 정밀 {pct}%")

    # S6 Page 마스터
    cov = _load(GOLD / slug / "coverage.json")
    master = GOLD / slug / "page_building_master.geojson"
    if not cov or not master.exists():
        add("Page마스터", TODO, "coverage.json / page_building_master.geojson 없음",
            f"python -m data.pipelines.build_building_attrs {slug} && "
            f"python -m data.pipelines.build_page_master {slug}")
    else:
        tier = str(cov.get("tier", "?"))
        rc = cov.get("reference_coverage_pct")
        ev = (f"{tier} · 노출 {cov.get('shown')}동 · 대표공실 {_served_vac(cov)}% "
              f"· 정밀커버리지 {rc}%")
        ok = tier.startswith("Tier1") and (rc or 0) >= PRECISE_COVERAGE_MIN
        add("Page마스터", OK if ok else PARTIAL, ev,
            "" if ok else f"python -m data.collectors.floor_capacity {slug} --only-approx  → 재빌드")

    # S7 앵커 대조
    cal = _load(GOLD / slug / "calibration.json")
    if not cal:
        add("앵커", TODO, "calibration.json 없음", "python -m data.pipelines.calibrate_vacancy")
    else:
        anchor = cal.get("anchor_pct") or (cal.get("combined") or {}).get("anchor_pct")
        ref = _served_vac(cov)
        if anchor is None:
            add("앵커", PARTIAL, "R-ONE 앵커 없음 (표본 미매핑)",
                "data/config/rone_districts.py 에 매핑 추가 — 공유면 rone-shared 로 표기")
        elif ref is None:
            add("앵커", PARTIAL, f"앵커 {anchor}% · 대표값 미산출", "")
        else:
            gap = round(ref - anchor, 2)
            add("앵커", BLOCKED if abs(gap) > ANCHOR_GAP_MAX else OK,
                f"대표 {ref}% vs 앵커 {anchor}% = {gap:+}%p",
                "" if abs(gap) <= ANCHOR_GAP_MAX else "가드레일 30%p 초과 — 원인 규명 전 서빙 등재 금지")

    # S8 공실 유닛
    vu = GOLD / slug / "vacant_units.json"
    if vu.exists():
        add("공실유닛", OK, "vacant_units.json 있음")
    else:
        # ⚠ 이 단계는 **미실행과 후보 부재를 구분하지 못한다.** 파이프라인이 0유닛을 내면
        #   파일을 쓰지 않기 때문이다. 화정(2026-08-30)이 후자였다 — 정밀 분모(floor_ouln)
        #   공실 후보가 덕양구청 1동뿐이었고 호당 442평이라 면적 상한(200평)에서 걸렸다.
        #   집합건물이 유닛 대상에서 빠지는 거점은 이 상태가 정상일 수 있다.
        add("공실유닛", TODO,
            "없음 — 미실행이거나 후보 0(파이프라인은 0유닛이면 파일을 안 쓴다)",
            f"python -m data.pipelines.build_vacant_units {slug}")

    # S9 서빙 등재 — 수집 등록과 다른 축이다
    if slug in _served_ids():
        add("서빙등재", OK, "거점 목록(services.districts.PAGES)에 있음")
    else:
        prev = {s["stage"]: s["status"] for s in out}
        ready = prev.get("Page마스터") in (OK, PARTIAL) and prev.get("앵커") != BLOCKED
        add("서빙등재", TODO if ready else BLOCKED,
            "거점 목록 미등재 (지도·API 목록에 안 뜬다)",
            "Gold 가 섰는데 목록에 없다 — app/data/measured_pages._is_measured 조건 확인" if ready
            else "Gold 가 서기 전에는 등재하지 않는다 — 시드를 지어내지 않기 위해")

    return out


def summarize(slug: str) -> dict:
    st = stages(slug)
    blocked = [s for s in st if s["status"] == BLOCKED]
    done = sum(1 for s in st if s["status"] == OK)
    # 다음 한 수는 **파이프라인 순서로 가장 앞선 미완 단계**다. 막힌 단계를 먼저 고르면
    # 안 된다 — 마지막 단계(서빙등재)는 선행이 없을 때 항상 막힘으로 나오므로, 그것을
    # 집으면 루프가 "아직 수집도 안 한 거점을 등재하라"는 헛수를 둔다.
    nxt = next((s for s in st if s["status"] in (BLOCKED, TODO) and s["next"]), {})
    return {"slug": slug, "done": done, "total": len(st), "stages": st,
            "blocked": [b["stage"] for b in blocked],
            "next_stage": nxt.get("stage", ""), "next": nxt.get("next", "")}


def main() -> int:
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in flags
    only_next = "--next" in flags
    slugs = sorted(_hubs()) if ("--all" in flags or not args) else args

    reports = [summarize(s) for s in slugs]
    if as_json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return 0
    if only_next:
        for r in reports:
            print(f"{r['slug']}\t{r['next_stage']}\t{r['next']}")
        return 0

    for r in reports:
        head = f"\n■ {r['slug']}  {r['done']}/{r['total']} 단계 통과"
        if r["blocked"]:
            head += "  막힘: " + ", ".join(r["blocked"])
        print(head)
        for s in r["stages"]:
            print(f"  {MARK[s['status']]} {s['stage']:10s} {s['evidence']}")
            if s["next"]:
                print(f"       -> {s['next']}")
    pending = next((r for r in reports if r["next"]), None)
    if pending:
        print(f"\n다음 한 수 [{pending['slug']} / {pending['next_stage']}]: {pending['next']}")
    elif reports:
        print("\n다음 한 수: 없음 — 지정한 거점은 모두 통과했다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

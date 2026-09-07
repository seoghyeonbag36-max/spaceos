"""screen_loop 회귀 테스트 — 브라우저·서버 없이 도는 것만 담는다.

실행: python scripts/test_screen_loop.py     (또는 `screen_loop.py --self-check` 와 같이)

여기서 검사하는 것은 셋이다.

1. **판정부가 없는 셀렉터를 잡는가** — `screen_loop.self_check()` 를 그대로 부른다.
   같은 규칙을 두 벌 적지 않는다.
2. **명세의 셀렉터가 실제 프론트에 있는가** — 클래스 토큰을 `apps/frontend/src` 에서
   찾는다. 브라우저 없이 오타를 잡는 정적 절반이고, 카나리 셀렉터는 **없어야** 한다.
3. **입력·체크포인트 규칙** — 거점 목록을 런타임에서 읽는가, slug 를 소스에 박지
   않았는가(만료된 `docs/prompt-playwright-e2e.md` 의 실패 양식), 재개가 이미 잰
   조합을 건너뛰는가.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import screen_loop as SL                                            # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "apps" / "frontend" / "src"

ok = True


def check(label: str, cond: bool, detail: str = "") -> None:
    global ok
    ok &= bool(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {label}{'  ' + detail if detail else ''}")


# ── 1) 판정부 자기검사 (없는 셀렉터를 실패로 잡는다) ───────────────────
check("self_check() 전부 통과", SL.self_check() == 0)


# ── 2) 명세의 셀렉터가 프론트에 실재하는가 ─────────────────────────────
def front_source() -> str:
    parts = []
    for ext in ("*.tsx", "*.ts", "*.css"):
        for f in FRONT.rglob(ext):
            parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


SRC = front_source()
check("프론트 소스를 읽었다", len(SRC) > 10000, f"{len(SRC)}자")


def class_tokens(sel: str) -> list[str]:
    """CSS 셀렉터에서 클래스 토큰만 뽑는다(`:has(optgroup)` 같은 의사클래스는 뺀다)."""
    return re.findall(r"\.([A-Za-z][\w-]*)", sel)


def exists(token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b", SRC) is not None


spec_sels = [n.sel for s in SL.TABS for n in s.nodes]
spec_sels += [s.hub_select for s in SL.TABS] + [s.root for s in SL.TABS]
spec_sels += [SL.SEL_MAP_CANVAS, SL.SEL_MAP_NOTE, SL.SEL_LIST_ROW,
              SL.SEL_ROW_NAME, SL.SEL_DETAIL_NAME, SL.SEL_PAGE_SUMMARY]
missing = sorted({t for sel in spec_sels for t in class_tokens(sel) if not exists(t)})
check("명세의 클래스가 전부 프론트에 있다", not missing, f"없는 것: {missing}")

check("카나리 셀렉터는 프론트에 없다",
      not any(exists(t) for t in class_tokens(SL.CANARY_SEL)), SL.CANARY_SEL)

# 상세패널은 반드시 좁혀 쓴다 — `.b-name` 만으로 찾으면 목록 첫 행을 집는다(§제약 3).
check("상세패널 셀렉터가 .b-detail 로 좁혀져 있다", ".b-detail " in SL.SEL_DETAIL_NAME)
check("지도 JS 가 같은 셀렉터 상수를 쓴다",
      SL.SEL_MAP_CANVAS in SL.MAP_JS and SL.SEL_MAP_NOTE in SL.MAP_JS
      and "__CANVAS__" not in SL.MAP_JS)

# 탭 이름은 App.tsx 의 NAV 라벨이다. 2026-09-06 에 "지도" → "Page" 로 갈렸고,
# 낡은 이름으로 부르면 타임아웃만 난다.
app_tsx = (FRONT / "App.tsx").read_text(encoding="utf-8")
bad_label = [s.label for s in SL.TABS if f'label: "{s.label}"' not in app_tsx]
check("탭 라벨이 App.tsx NAV 에 있다", not bad_label, f"없는 것: {bad_label}")
check("네 탭이 PPPP 순서다",
      [s.key for s in SL.TABS] == ["platform", "map", "posting", "program"])


# ── 3) 입력 — 거점 목록은 런타임에서 온다 ──────────────────────────────
hubs = SL.load_hubs()
check("PAGES 에서 거점을 읽는다", len(hubs) >= 13 and all("id" in h for h in hubs),
      f"{len(hubs)}곳")

# 소스에 slug 를 박지 않았는가. 문자열 **상수**만 본다(주석·docstring 의 예시는 예시다).
ids = {h["id"] for h in hubs}
tree = ast.parse(Path(SL.__file__).read_text(encoding="utf-8"))
literals = {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
check("소스에 거점 slug 문자열이 없다", not (literals & ids), str(sorted(literals & ids)))

# 요청 **순서대로** 그만큼만 나와야 한다 — 목록에서 뽑아 쓴다(여기서도 slug 를 박지 않는다).
trio = [h["id"] for h in hubs[:3]][::-1]
check("--hubs 는 요청 순서대로 그 거점만 고른다",
      [h["id"] for h in SL.select_hubs(hubs, ",".join(trio))] == trio, str(trio))

# 통과 조건에 적힌 예시가 지금 목록에서도 도는지 — 셋 중 하나가 사라지면 여기서 드러난다.
example = "yeonnam,sinchon,hongdae"
try:
    got = [h["id"] for h in SL.select_hubs(hubs, example)]
except SystemExit as e:
    got, msg = [], str(e)
else:
    msg = str(got)
check(f"--hubs {example}", got == example.split(","), msg[:120])
check("--hubs 없으면 전부", len(SL.select_hubs(hubs, None)) == len(hubs))

try:
    SL.select_hubs(hubs, "nowhere-such-hub")
    check("모르는 거점은 중단시킨다", False)
except SystemExit as e:
    check("모르는 거점은 중단시킨다", "nowhere-such-hub" in str(e))

try:
    SL.select_tabs("platform,nope")
    check("모르는 탭은 중단시킨다", False)
except SystemExit as e:
    check("모르는 탭은 중단시킨다", "nope" in str(e))

colors = SL.vacancy_colors()
check("공실 색을 디자인 토큰에서 읽는다",
      len(colors) >= 4 and all(re.fullmatch(r"#[0-9A-Fa-f]{6}", c) for c in colors), str(colors))


# ── 4) 체크포인트 — 이어 받는다 ────────────────────────────────────────
three = hubs[:3]
combos = [(h, s) for h in three for s in SL.TABS]
check("조합 수 = 거점 × 탭", len(combos) == 3 * len(SL.TABS))
check("빈 리포트면 전부 잰다", len(SL.pending(combos, {})) == len(combos))

results = {SL.combo_key(*combos[0]): {"status": "pass"},
           SL.combo_key(*combos[1]): {"status": "fail"}}
check("이미 잰 조합은 건너뛴다", len(SL.pending(combos, results)) == len(combos) - 2)
check("--retry-failed 는 실패분만 다시 잰다",
      len(SL.pending(combos, results, retry_failed=True)) == len(combos) - 1)

with tempfile.TemporaryDirectory() as d:
    out = Path(d) / "screen_loop.json"
    SL.save_report(out, {"results": results, "note": "가로 — em dash"})
    back = SL.load_report(out)
    check("리포트 왕복(utf-8)", back["results"] == results and "—" in back["note"])
    check("임시파일을 남기지 않는다", not list(Path(d).glob("*.tmp")))
    out.write_text("{깨진 json", encoding="utf-8")
    check("깨진 리포트는 빈 것으로 시작한다", SL.load_report(out) == {})
    check("리포트는 json 이다", isinstance(json.dumps(results), str))


# ── 5) 게이트 — 거점을 바꿨는데 API 를 안 부르면 실패 ──────────────────
spec = SL.TABS_BY_KEY["map"]
obs = SL._obs_ok(spec, SL.FAKE_HUB, len(hubs))
obs["gate_seen"] = "timeout"
check("게이트 타임아웃은 실패",
      any("부르지 않았다" in f["why"]
          for f in SL.judge(spec, obs, hub_total=len(hubs), hub_id=SL.FAKE_HUB)))

# 카나리 명세는 모든 탭에 하나씩 더 붙는다
canaries = SL.with_canary(SL.TABS)
check("카나리는 모든 탭에 붙는다",
      all(len(c.nodes) == len(s.nodes) + 1 and c.nodes[-1].sel == SL.CANARY_SEL
          for c, s in zip(canaries, SL.TABS)))
check("카나리가 원본 명세를 건드리지 않는다",
      all(SL.CANARY_SEL not in [n.sel for n in s.nodes] for s in SL.TABS))

print("\n" + ("모두 통과" if ok else "실패 있음"))
sys.exit(0 if ok else 1)

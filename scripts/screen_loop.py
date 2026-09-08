#!/usr/bin/env python
"""66거점 화면 회귀 검사 — 거점 × PPPP 4탭을 브라우저로 한 바퀴 돌며 4단계를 잰다.

## 왜 필요한가

지금 화면 검증은 `/verify` 가 **사람 손으로 한 거점씩** 여는 방식이다. 거점 66 × 탭 4 =
264조합을 손으로 돌 수는 없다. 그래서 `/verify` 의 절차(정적 3종 → 로컬 앱 → 지도 픽셀)
중 **반복 가능한 부분만** 떼어 무인 루프로 만든다. `/verify` 는 그대로 남는다 —
층 스택·거리뷰처럼 한 건물을 깊게 보는 자리는 여전히 사람이 본다(§경계 참조).

`scripts/watch_deploy_verify.py` 가 **API 수준**에서 하는 일을 이 스크립트가 **화면 수준**
에서 한다. 이 저장소가 두 번 당한 실패 양식이 "데이터는 멀쩡한데 화면이 틀렸다"이고,
그 반대("화면은 멀쩡한데 데이터가 빠졌다")는 저쪽이 잡는다.

## 무엇을 재는가 — 거점 × 탭 하나마다 네 단계

  S1  콘솔 에러 0 · pageerror 0 · API 5xx 0
  S2  지도 캔버스가 보이고(넓이·높이 > 0) SDK 자식이 1개 이상   ← Page 탭에만
  S3  공실 마커/폴리곤 수 > 0 · 결론 문장 노드 존재 · 거점 목록에 그 거점이 있음
  S4  초기 렌더 3초 이내 (KPI: 지도·건물 상세 로딩 3초)

S1 의 "콘솔 에러"에서 **리소스 적재 실패 줄(`Failed to load resource`)은 뺀다.** 그건
네트워크 채널이라 `page.on("response")` 로 따로 세고, 이 저장소에서 404 는 고장이 아니라
**아직 수집하지 않았다**는 뜻인 자리가 있다(`/ai/recommend-industry` 404 = 400m 안에 노드
없음, PlatformConsole 주석 참조). 그래서 4xx 는 리포트에 남기기만 하고 5xx 만 실패로 센다.

## 실행 (데스크톱 — 백엔드·프론트를 먼저 띄운다)

    # 터미널 1  cd apps\\backend ; py -3.11 -m uvicorn app.main:app --port 8000
    # 터미널 2  cd apps\\frontend ; npm run dev
    # 터미널 3
    set PYTHONIOENCODING=utf-8
    python -u scripts/screen_loop.py                       # 66거점 전부
    python -u scripts/screen_loop.py --hubs yeonnam,sinchon,hongdae
    python -u scripts/screen_loop.py --self-check          # 브라우저 없이 판정부만 자기검사
    python -u scripts/screen_loop.py --hubs yeonnam --canary   # 없는 셀렉터를 넣어 실검사

⚠ **로그를 파일로 리다이렉트할 때 `PYTHONIOENCODING=utf-8`.** Windows 기본 cp949 에는
  `—`(em dash) 가 없어 그 순간 UnicodeEncodeError 로 죽는다(2026-08-19 실측).
  이 스크립트는 stdout 을 utf-8 로 다시 열지만, 자식 프로세스·리다이렉트까지 덮지는 못한다.

## 설계 제약 (전례에서 나온 것이라 바꾸지 말 것)

1. **Node `@playwright/test` 를 깔지 않는다.** Python `playwright` 가 2026-07-24 부터
   있고 `/verify` 가 그걸 쓴다. 두 벌을 두면 검증 기준이 갈린다.
   → `docs/prompt-playwright-e2e.md` 가 만료된 이유 3번.
2. **거점 slug 를 박지 않는다.** 목록은 `app.services.districts.PAGES` 를 **런타임에**
   읽는다. 위 문서가 만료된 이유 1번이 slug 13개를 박아 둔 것이다.
3. **셀렉터를 좁게 쓴다.** `.b-name` 은 목록행과 상세패널 양쪽에 있어
   `querySelector('.b-name')` 은 목록 첫 행을 집는다 → 상세는 반드시 `.b-detail .b-name`.
   (2026-09-06 에 실제로 이걸로 한 번 헛짚었다.)
4. **중단돼도 이어 받는다.** 264조합은 한 번에 안 끝난다. 조합 하나가 끝날 때마다
   `reports/screen_loop.json` 을 다시 쓰고, 다시 부르면 이미 잰 조합을 건너뛴다.
   (`--fresh` 로 처음부터, `--retry-failed` 로 실패분만 다시.)
5. 로그·리포트는 utf-8 로만 쓴다(위 경고).

## 자기 검사 — 이 검사기가 초록을 거저 주지 않는다는 증거

`--self-check` 는 **브라우저 없이** 판정부(`judge`)만 돌린다. 없는 셀렉터를 넣은 관측을
만들어 판정부가 그걸 실패로 잡는지 확인한다. 관측(observation)을 브라우저 조작과 분리해
둔 이유가 이것이다 — 판정 규칙은 순수 함수라 서버도 지도 키도 없이 검사할 수 있다.
`scripts/test_screen_loop.py` 가 같은 함수를 더 많은 경우로 돌린다.

`--canary` 는 **실제 실행**에서 같은 일을 한다. 모든 탭 명세에 존재하지 않는 셀렉터를
덧붙이므로, 그 실행은 **전 조합이 실패로 나와야 정상**이다. 전부 통과로 나오면 이
스크립트가 화면을 안 보고 있다는 뜻이다.

## 경계 — 여기서 하지 않는 것

- **층 스택·거리뷰(`.b-twin`)** 는 열지 않는다. 파노라마까지 9초씩 × 66 이고, 그 표면은
  `/verify` 의 선언 게이트라 한 건물을 깊게 보는 편이 낫다.
- **Program 생성(`/marketing/generate`)** 은 부르지 않는다. Claude 실호출이라 거점마다
  10~20초 + 크레딧이다. Program 탭에서 보는 것은 "화면이 서고 거점 목록에 이 거점이
  있는가"까지다 — 그 이상은 이 루프의 몫이 아니다.
- `scripts/pppp_status.py` 에 게이트를 **더하지 않는다.** 측정이 실제로 도는 것을 확인한
  뒤에 따로 판단한다(게이트 24개 중 이미 선언이 8개다).

산출: `reports/screen_loop.json` + 실패한 조합만 `reports/screens/{거점}__{탭}.png`
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "backend"))

try:                                    # cp949 콘솔에서 em dash 로 죽지 않게
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

OUT = ROOT / "reports" / "screen_loop.json"
SHOTS = ROOT / "reports" / "screens"
COLORS_TS = ROOT / "apps" / "frontend" / "src" / "design" / "tokens" / "colors.ts"
BASE_URL = "http://localhost:5173"
BUDGET_MS = 3000        # KPI: 지도 로딩 3초 이내
NODE_TIMEOUT_MS = 8000  # 노드 하나를 기다리는 상한(예산보다 커야 "느림"과 "없음"이 갈린다)
GATE_TIMEOUT_MS = 15000

# 리소스 적재 실패 줄 — 콘솔이 아니라 네트워크 채널로 센다(위 docstring S1 참조).
RESOURCE_ERR = re.compile(r"Failed to load resource")

# 코드가 직접 쓰는 셀렉터 — 명세(TABS) 밖에서도 한 곳에만 둔다.
#
# ⚠ `.b-name` 은 **목록행과 상세패널 양쪽에 있다.** `querySelector('.b-name')` 은 목록
#   첫 행을 집으므로, 선택한 건물을 확인하려면 `.b-detail .b-name` 으로 좁혀야 한다.
#   이걸 모르면 패널이 엉뚱한 건물을 그린다고 오진한다(2026-09-06 실제로 헛짚었다).
SEL_MAP_CANVAS = ".map-canvas"
SEL_MAP_NOTE = ".map-note"
SEL_LIST_ROW = ".mapshell .sp-list .b-item"
SEL_ROW_NAME = ".b-name"                       # 이미 행 안으로 범위가 좁혀진 뒤에만 쓴다
SEL_DETAIL_NAME = ".mapshell .b-detail .b-name"
SEL_PAGE_TITLE = ".mapshell .sp-head .sp-title"
SEL_PAGE_SUMMARY = ".mapshell .side-panel .sp-sub"


# ──────────────────────────── 명세 ────────────────────────────
@dataclass(frozen=True)
class Node:
    """화면에 있어야 하는 노드 하나.

    `contains` 는 **문장의 뜻**을 잡는다. 예: Page 의 요약줄이 "샘플"이면 백엔드가
    404 를 내 로컬 8건 폴백을 그린 것이다 — 노드는 있는데 값이 가짜인 자리라,
    존재만 보면 통과해 버린다(/verify 의 `features 800 vs 8` 판별과 같은 축).
    """
    sel: str
    min_count: int = 1
    contains: str | None = None      # `{name}`·`{gu}` 를 쓰면 거점 값이 들어간다(resolve)
    why: str = ""


@dataclass(frozen=True)
class TabSpec:
    key: str                    # 리포트 키 (App.tsx 의 View 값)
    label: str                  # 좌측 레일 버튼 이름 (App.tsx NAV.label)
    root: str                   # 탭이 섰음을 알리는 루트 노드
    hub_select: str             # 거점 <select> — 좁게(§제약 3)
    gate: str | None            # 거점 전환이 실제로 부르는 API 경로 조각 ({hub} 치환)
    nodes: tuple[Node, ...]     # 그 탭의 "결론" 노드들
    extra_options: int = 0      # 거점 외 옵션 수
    map_check: bool = False     # S2 + 지도 오버레이 계수
    detail_click: bool = False  # 목록 첫 행을 눌러 상세패널까지 본다


# 탭 순서 = PPPP 순서 (Platform → Page → Posting → Program). App.tsx NAV 와 같다.
#
# 거점 <select> 를 고르는 법:
#   · Page      MapShell 이 `className="hub-select"` 를 직접 준다.
#   · Platform  `.picker` 안에 select 가 하나뿐이다.
#   · Posting   select 가 셋(상권·자리·전략)인데 **optgroup 을 내는 것은 DistrictPicker
#               뿐**이다(도시로 묶는다). 순서(nth)로 집으면 필드가 하나 늘 때 조용히
#               다른 select 를 고른다.
#   · Program   화면에 select 가 하나뿐이고, DistrictPicker 가 아니라 손으로 그린
#               것이라 optgroup 이 없다("— 결합 안 함 —" 빈 옵션 때문에 못 바꿨다).
TABS: tuple[TabSpec, ...] = (
    TabSpec(
        key="platform", label="Platform", root=".platconsole",
        hub_select=".platconsole .picker select",
        gate="/commercial-districts/{hub}/platform",
        nodes=(
            # 결론과 근거는 화면 맨 위 Verdict 가 낸다(2026-09-07 텍스트 축약).
            # 종전의 `.hero .heroarch`·`.herorule` 은 「정체성 원자료」Fold 안으로
            # 들어갔고 그 Fold 는 기본으로 접혀 있다 — state="visible" 로 기다리는
            # 이 검사기에는 안 보이므로 여기서 그것을 재면 안 된다.
            # `.vone` 에는 거점 이름이 들어간다(headline() 의 `name`) — 다른 탭처럼
            # 이름을 먼저 기다리는 것이 곧 **새 거점의** 결론을 기다리는 것이다.
            # 근거가 없으면 "업종 근거가 없어 유형을 판정하지 않는다"가 들어오는데
            # 그것도 결론이다(없음을 밝히는 문장). 노드가 아예 없으면 실패다.
            Node(".platconsole .verdict .vone", contains="{name}",
                 why="상권 정체성 결론 — 이 거점의 화면인가"),
            Node(".platconsole .verdict .vgrounds .gv", why="그 판정을 받치는 근거 값"),
        ),
    ),
    TabSpec(
        # ⚠ MapShell 은 `vacancy_source === "gold"` 인 거점만 목록에 올린다. 그래서
        #    옵션 수가 PAGES 보다 적으면 화면 결함이 아니라 **그 거점의 Gold 가 빠진
        #    것**이다 — 판정 문구가 두 수를 같이 적는 이유다.
        key="map", label="Page", root=".mapshell",
        hub_select=".hub-select",
        gate="/heatmap/buildings?district={hub}",
        nodes=(
            # 거점 이름이 든 노드를 **먼저** 기다린다 — 거점을 바꿔도 직전 거점의 화면이
            # 잠깐 남는 순간이 있고, 그때 재면 남의 화면을 통과로 읽는다.
            Node(SEL_PAGE_TITLE, contains="{name} · 건물 공실", why="이 거점의 화면인가"),
            # "…동 · 실측(추정)" — `실측` 이 아니면 API 404 폴백(로컬 샘플 8건)이다.
            Node(SEL_PAGE_SUMMARY, contains="실측", why="거점 요약 결론"),
            Node(SEL_LIST_ROW, why="건물 목록 행"),
        ),
        map_check=True, detail_click=True,
    ),
    TabSpec(
        key="posting", label="Posting", root=".postconsole",
        hub_select=".postconsole select:has(optgroup)",
        gate="/commercial-districts/{hub}/postings",
        nodes=(
            # ⚠ Platform 과 같다 — 거점을 바꾸면 `setResult(null)` 로 결과를 내리므로
            #    `.tier` 를 기다리는 것이 새 거점의 결과를 기다리는 것이 된다.
            # 자리를 고르면 입력 없이 한 번 자동으로 돌린다(PostingConsole 주석) —
            # 그래서 버튼을 누르지 않아도 3-Tier 가 서야 한다.
            Node(".postconsole .results .tiers .tier", min_count=1, why="3-Tier 결론 카드"),
            Node(".postconsole .results .rsrc", why="비용 기준·출처 문장"),
        ),
    ),
    TabSpec(
        key="program", label="Program", root=".progstudio",
        hub_select=".progstudio select",
        # 거점을 골라도 API 를 부르지 않는다(생성할 때 프롬프트에 결합된다) → 게이트 없음.
        gate=None,
        nodes=(
            # ⚠ 패널 수는 `.panel` 로 센다. 결과 패널(`<Card className="panel">`)에는
            #   **제목 요소가 없다** — 제목은 입력 폼에만 있어서 `.ptitle` 로 2개를
            #   요구하면 생성을 부르기 전에는 절대 채워지지 않는다. 그런데 이 루프는
            #   Program 생성을 부르지 않기로 스스로 정했다(§경계) → 명세가 자기 경계와
            #   모순이었다(2026-09-07 첫 실전 실행에서 드러났다).
            Node(".progstudio .panel", min_count=2, why="입력·결과 패널 두 개"),
            Node(".progstudio .panel .ptitle", why="입력 패널 제목"),
        ),
        extra_options=1,   # "— 결합 안 함 —"
    ),
)
TABS_BY_KEY = {t.key: t for t in TABS}

CANARY_SEL = ".spaceos-canary-does-not-exist"
# 자기검사 픽스처용 가짜 거점 id — 실제 slug 를 코드에 박지 않기 위한 것이다
# (`test_screen_loop.py` 가 "소스에 slug 문자열이 없다"를 검사한다).
FAKE_HUB = "__self_check_hub__"


def resolve(spec: TabSpec, hub: dict) -> TabSpec:
    """명세의 `contains` 에 거점 값을 끼운 사본. probe 와 judge 가 **같은** 명세를 본다.

    원본을 제자리에서 고치지 않는다 — 다음 거점이 앞 거점의 이름을 물려받는다.
    """
    if not any(n.contains and "{" in n.contains for n in spec.nodes):
        return spec
    return replace(spec, nodes=tuple(
        replace(n, contains=n.contains.format(**hub)) if n.contains else n
        for n in spec.nodes))


def with_canary(specs: tuple[TabSpec, ...]) -> tuple[TabSpec, ...]:
    """모든 탭에 **없는 셀렉터**를 덧붙인다 — 이 실행은 전 조합이 실패해야 정상이다."""
    node = Node(CANARY_SEL, why="자기검사 카나리 — 이게 통과하면 검사기가 화면을 안 보는 것")
    return tuple(replace(s, nodes=s.nodes + (node,)) for s in specs)


# ──────────────────────────── 입력 ────────────────────────────
def load_hubs() -> list[dict]:
    """거점 목록 — `app.services.districts.PAGES` 를 런타임에 읽는다(§제약 2).

    시드 54 + 실측 거점의 합본이고, 서빙 보류 도시는 `measured_pages.SERVED_CITIES`
    에서 이미 걸러져 들어온다. 여기서 다시 세거나 필터하지 않는다 — 세는 곳이 늘면
    그 중 하나가 낡는다.
    """
    try:
        from app.services.districts import PAGES
    except ImportError as e:   # pragma: no cover - 환경 문제
        raise SystemExit(
            f"[screen] app.services.districts 를 못 읽었다: {e}\n"
            "  → apps/backend 의존성이 있는 파이썬으로 부를 것"
            "(예: apps/backend/.venv 에 playwright 를 설치해 그 파이썬으로 실행)"
        ) from e
    return [{"id": p["id"], "name": p["name"], "gu": p.get("gu", "")} for p in PAGES]


def vacancy_colors() -> list[str]:
    """공실 상태색 — 프론트 디자인 토큰(`colors.vacancy`)에서 읽는다.

    지도 오버레이를 **색으로** 센다(아래 `probe_map` 참조). 색을 이 파일에 베껴 두면
    토큰이 바뀌는 날 검사기가 조용히 0 을 세게 되므로 단일 출처에서 읽는다.
    """
    src = COLORS_TS.read_text(encoding="utf-8")
    m = re.search(r"vacancy:\s*\[([^\]]*)\]", src)
    if not m:
        raise SystemExit(f"[screen] colors.vacancy 를 {COLORS_TS} 에서 못 찾았다")
    return re.findall(r"#[0-9A-Fa-f]{6}", m.group(1))


def preflight(base: str, hub_ids: list[str]) -> dict:
    """앱이 떠 있는지, Vite 프록시가 백엔드까지 닿는지 먼저 본다.

    `/verify` 의 "표면 고르기" 그대로다 — 프론트가 타는 실제 경로(`:5173/api/v1/...`)로
    두드린다. 백엔드에 직접(`:8000`) 물으면 프록시가 끊긴 것을 못 잡는다.
    """
    info: dict = {"base_url": base}
    try:
        with urllib.request.urlopen(base, timeout=10) as r:
            info["app_status"] = r.status
    except (urllib.error.URLError, OSError) as e:
        raise SystemExit(
            f"[screen] 프론트({base})가 응답하지 않는다: {e}\n"
            "  터미널 1: cd apps/backend && py -3.11 -m uvicorn app.main:app --port 8000\n"
            "  터미널 2: cd apps/frontend && npm run dev"
        ) from e
    try:
        with urllib.request.urlopen(f"{base}/api/v1/commercial-districts", timeout=20) as r:
            served = [d["id"] for d in json.loads(r.read().decode("utf-8"))]
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise SystemExit(
            f"[screen] Vite 프록시 → 백엔드가 끊겼다({base}/api/v1/commercial-districts): {e}\n"
            "  백엔드(:8000)가 떠 있는지, 프록시 설정이 살아 있는지 본다."
        ) from e
    info["served"] = len(served)
    # 목록이 다르면 그 자체가 결과다 — 중단하지 않고 리포트에 남긴 뒤 계속 돈다.
    missing = [h for h in hub_ids if h not in served]
    extra = [s for s in served if s not in hub_ids]
    info["served_missing"] = missing
    info["served_extra"] = extra
    if missing or extra:
        print(f"[screen] ⚠ PAGES({len(hub_ids)}) 와 서빙 목록({len(served)})이 다르다 — "
              f"빠짐 {missing} / 더 있음 {extra}", flush=True)
    return info


# ──────────────────────────── 관측 ────────────────────────────
class Recorder:
    """콘솔·pageerror·응답을 모은다. 조합마다 `reset()` 하고 조합 끝에 `snapshot()`."""

    def __init__(self) -> None:
        self.console: list[str] = []
        self.resource: list[str] = []
        self.page_errors: list[str] = []
        self.http: list[dict] = []

    def attach(self, page) -> None:
        page.on("console", self._on_console)
        page.on("pageerror", lambda e: self.page_errors.append(str(e)[:400]))
        page.on("response", self._on_response)

    def _on_console(self, msg) -> None:
        if msg.type != "error":
            return
        text = msg.text[:400]
        (self.resource if RESOURCE_ERR.search(text) else self.console).append(text)

    def _on_response(self, res) -> None:
        if "/api/v1/" not in res.url or res.status < 400:
            return
        self.http.append({"url": res.url.split("?")[0], "status": res.status})

    def reset(self) -> None:
        self.console.clear()
        self.resource.clear()
        self.page_errors.clear()
        self.http.clear()

    def snapshot(self) -> dict:
        return {
            "console_errors": list(self.console),
            "page_errors": list(self.page_errors),
            "resource_errors": self.resource[:5],
            "api_5xx": [h for h in self.http if h["status"] >= 500],
            "api_4xx": [h for h in self.http if h["status"] < 500],
        }


# 지도 오버레이를 **색으로** 센다.
#
# 왜 색인가: 네이버 SDK 의 오버레이 DOM 에는 우리가 붙일 수 있는 클래스가 없다. 그렇다고
# `.map-canvas svg path` 를 세면 SDK 컨트롤의 아이콘까지 딸려 들어와 폴리곤 0 개인 화면도
# 통과한다. 폴리곤/점의 색은 우리 토큰(colors.vacancy)에서 나오므로, 그 색으로 칠해진
# 노드만 세면 "우리가 그린 것"만 남는다.
#
# TODO(첫 데스크톱 실행에서 확인): 폴리곤이 SVG(path)가 아니라 canvas 로 그려지는
#   빌드라면 poly/dot 이 0 이고 canvases > 0 으로 나온다. 그때는 여기(한 곳)만 고친다 —
#   진단에 필요한 원시 계수(paths/divs/canvases)를 항상 같이 남기는 이유다.
MAP_JS = """
(hexes) => {
  const el = document.querySelector('__CANVAS__');
  const note = document.querySelector('__NOTE__');
  const noteText = note ? (note.innerText || '').slice(0, 300) : '';
  if (!el) return { found: false, note: noteText };
  const rgb = (h) => {
    const n = parseInt(h.slice(1), 16);
    return `rgb(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255})`;
  };
  const want = new Set(hexes.map(rgb));
  const norm = (s) => (s || '').replace(/\\s+/g, '');
  let poly = 0, dot = 0, paths = 0, divs = 0;
  for (const p of el.querySelectorAll('path')) {
    paths++;
    if (want.has(norm(getComputedStyle(p).fill))) poly++;
  }
  for (const d of el.querySelectorAll('div')) {
    divs++;
    if (want.has(norm(getComputedStyle(d).backgroundColor))) dot++;
  }
  const r = el.getBoundingClientRect();
  return {
    found: true, w: Math.round(r.width), h: Math.round(r.height),
    children: el.childElementCount, poly, dot, paths, divs,
    canvases: el.querySelectorAll('canvas').length, note: noteText,
  };
}
"""
# 셀렉터는 파이썬 상수에서 끼워 넣는다 — JS 안에 또 적으면 두 곳이 갈린다.
# (`.format()` 은 못 쓴다. 위 JS 가 템플릿 리터럴 `${...}` 를 쓴다.)
MAP_JS = MAP_JS.replace("__CANVAS__", SEL_MAP_CANVAS).replace("__NOTE__", SEL_MAP_NOTE)


def probe_map(page, hexes: list[str]) -> dict:
    return page.evaluate(MAP_JS, hexes)


def open_tab(page, spec: TabSpec, timeout_ms: int) -> None:
    """좌측 레일에서 탭을 누르고 그 화면의 루트가 설 때까지 기다린다.

    ⚠ 탭 이름은 2026-09-06 에 갈렸다(`"지도"` → `"Page"`, `"거점"` 신설). 낡은 이름으로
      부르면 타임아웃만 난다 — 이름은 App.tsx NAV 를 따른다(`/verify` 의 같은 경고).
    """
    page.get_by_role("button", name=spec.label, exact=True).first.click()
    page.wait_for_selector(spec.root, state="visible", timeout=timeout_ms)
    page.wait_for_selector(f"{spec.hub_select}:not([disabled])", state="visible",
                           timeout=timeout_ms)


def wait_nodes(page, spec: TabSpec, node_timeout_ms: int) -> dict:
    """명세의 노드들이 **보일 때까지** 기다렸다가 수와 텍스트를 읽는다.

    없는 노드는 예외로 끝내지 않고 `count: 0` 으로 관측에 남긴다 — 판정은 `judge` 가
    하고, 관측은 관측만 한다. 이 분리가 `--self-check` 를 가능하게 한다.
    """
    from playwright.sync_api import Error as PWError

    out: dict[str, dict] = {}
    for node in spec.nodes:
        # 문구가 걸린 노드는 **그 문구가 뜰 때까지** 기다린다. 존재만 보고 바로 읽으면,
        # 아직 직전 거점의 값이 남은 순간을 읽어 멀쩡한 화면을 실패로 적는다(반대로
        # 낡은 값이 마침 조건을 만족하면 통과로 적는다). 못 기다리면 그대로 흘려보내고
        # 판정은 `judge` 가 한다 — 여기서 실패를 선언하지 않는다.
        wait_sel = f'{node.sel}:has-text("{node.contains}")' if node.contains else node.sel
        loc = page.locator(node.sel)
        try:
            page.locator(wait_sel).first.wait_for(state="visible", timeout=node_timeout_ms)
        except PWError:
            pass
        try:
            count = loc.count()
            text = loc.first.inner_text()[:300] if count else ""
        except PWError as e:                      # 셀렉터 자체가 틀린 경우도 관측이다
            count, text = 0, f"[selector-error] {e}"[:300]
        out[node.sel] = {"count": count, "text": text}
    return out


def probe(page, spec: TabSpec, hub: dict, rec: Recorder, hexes: list[str],
          args) -> dict:
    """조합 하나를 실제로 열어 관측을 만든다. **판정하지 않는다.**"""
    from playwright.sync_api import Error as PWError

    rec.reset()
    t_click = time.monotonic()
    open_tab(page, spec, args.node_timeout_ms)
    tab_open_ms = round((time.monotonic() - t_click) * 1000)

    gate = spec.gate.format(hub=hub["id"]) if spec.gate else None
    gate_seen: str | None = None
    # 목록에 없는 거점을 고르려 하면 playwright 가 예외를 던진다. 그건 조작 실패가
    # 아니라 **결과**(거점이 화면 목록에서 빠졌다)이므로, 고르지 않고 판정에 맡긴다.
    #
    # ⚠ **옵션이 붙을 때까지 기다린 뒤에** 센다. `open_tab` 은 select 가 보이고
    #   비활성이 아닌 것까지만 보는데, 거점 목록은 비동기로 와서 그 순간 `<select>` 는
    #   비어 있을 수 있다. 기다리지 않고 세면 `missing-option` 으로 갈라져 **거점을
    #   아예 고르지 않고 직전 거점 화면을 잰다** — 2026-09-07 첫 실전 실행에서 실제로
    #   그랬다(같은 관측에 `trigger: missing-option` 과 `options: 66` 이 함께 찍혔다).
    opt_sel = f'{spec.hub_select} option[value="{hub["id"]}"]'
    try:
        page.locator(opt_sel).first.wait_for(state="attached",
                                             timeout=args.node_timeout_ms)
    except PWError:
        pass                            # 진짜로 없는 것일 수 있다 — 아래에서 센다
    has_option = page.locator(opt_sel).count() > 0
    # 현재 선택값도 **옵션이 붙은 뒤에** 읽는다 — 비어 있는 select 를 읽으면 기본
    # 거점까지 hub-switch 로 오해해, 나지도 않을 change 응답을 기다리게 된다.
    cur = page.locator(spec.hub_select).input_value()
    if not has_option:
        t0, trigger = t_click, "missing-option"
    elif cur == hub["id"]:
        # 기본 거점(garosugil)은 탭을 열자마자 그것이 잡혀 있다 — 같은 값으로 select 하면
        # change 가 안 나 요청도 없다. 그때는 **탭 열기부터** 초기 렌더로 잰다.
        t0, trigger = t_click, "tab-open"
    else:
        t0, trigger = time.monotonic(), "hub-switch"
        if gate:
            try:
                with page.expect_response(lambda r: gate in r.url,
                                          timeout=args.gate_timeout_ms) as got:
                    page.select_option(spec.hub_select, hub["id"])
                gate_seen = f"{got.value.status}"
            except PWError:
                gate_seen = "timeout"     # 거점을 바꿨는데 그 API 를 안 불렀다 = 결과다
        else:
            page.select_option(spec.hub_select, hub["id"])

    nodes = wait_nodes(page, spec, args.node_timeout_ms)
    render_ms = round((time.monotonic() - t0) * 1000)

    obs: dict = {
        "trigger": trigger, "tab_open_ms": tab_open_ms, "render_ms": render_ms,
        "gate": gate, "gate_seen": gate_seen,
        "selected": page.locator(spec.hub_select).input_value(),
        "options": page.locator(f"{spec.hub_select} option").count(),
        "nodes": nodes,
    }

    if spec.map_check:
        obs["map"] = probe_map(page, hexes)

    if spec.detail_click and nodes.get(SEL_LIST_ROW, {}).get("count"):
        # 목록 첫 행 → 상세패널. ⚠ `.b-name` 은 목록행과 상세패널 양쪽에 있다(§제약 3).
        rows = page.locator(SEL_LIST_ROW)
        try:
            row_name = rows.first.locator(SEL_ROW_NAME).inner_text()
            rows.first.click()
            page.wait_for_selector(SEL_DETAIL_NAME, state="visible",
                                   timeout=args.node_timeout_ms)
            panel_name = page.locator(SEL_DETAIL_NAME).first.inner_text()
        except PWError as e:
            row_name, panel_name = "", f"[error] {e}"[:200]
        obs["detail"] = {"row": row_name.strip(), "panel": panel_name.strip()}

    # 콘솔·응답은 **맨 마지막에** 걷는다. 상세패널 클릭까지 마친 뒤라야 그 조작이 낸
    # 에러도 이 조합의 것으로 잡힌다(먼저 걷으면 클릭이 낸 에러가 조용히 버려진다).
    obs.update(rec.snapshot())
    return obs


# ──────────────────────────── 판정 ────────────────────────────
def judge(spec: TabSpec, obs: dict, budget_ms: int = BUDGET_MS,
          hub_total: int | None = None, hub_id: str | None = None) -> list[dict]:
    """관측 하나를 네 단계로 판정한다 — **순수 함수**(브라우저·네트워크 없음).

    브라우저 조작과 갈라 둔 이유: 지도 키도 로컬 서버도 없는 곳에서 규칙 자체를 검사할
    수 있어야 한다(`--self-check`). 리포트에 관측을 통째로 싣는 이유도 같다 — 나중에
    같은 관측으로 다시 판정할 수 있다.
    """
    fails: list[dict] = []

    def bad(stage: str, why: str, **extra) -> None:
        fails.append({"stage": stage, "why": why, **extra})

    # S1 — 콘솔 에러 0 · pageerror 0 (+ API 5xx 0)
    if obs.get("console_errors"):
        bad("S1", f"콘솔 에러 {len(obs['console_errors'])}건",
            sample=obs["console_errors"][:3])
    if obs.get("page_errors"):
        bad("S1", f"pageerror {len(obs['page_errors'])}건", sample=obs["page_errors"][:3])
    if obs.get("api_5xx"):
        bad("S1", f"API 5xx {len(obs['api_5xx'])}건", sample=obs["api_5xx"][:3])

    # S2 — 지도 캔버스 (Page 탭에만)
    if spec.map_check:
        m = obs.get("map") or {}
        if not m.get("found"):
            bad("S2", f"{SEL_MAP_CANVAS} 가 없다", note=m.get("note", ""))
        elif not (m.get("w", 0) > 0 and m.get("h", 0) > 0):
            # inset:0 만으로는 높이가 0 으로 접힌다(2026-08-01 실측) — 스크린샷만 보면
            # "지도 키 문제"로 오진하는 자리라 DOM 으로 잰다.
            bad("S2", f"지도 캔버스 크기가 0 이다 ({m.get('w')}×{m.get('h')})")
        elif m.get("children", 0) < 1:
            bad("S2", "지도 캔버스에 SDK 자식이 없다", note=m.get("note", ""))

    # S3 — 결론 노드 · 거점 목록 · 공실 마커/폴리곤
    for node in spec.nodes:
        got = obs.get("nodes", {}).get(node.sel)
        if got is None:
            bad("S3", f"측정되지 않은 셀렉터: {node.sel}", why_node=node.why)
            continue
        if got["count"] < node.min_count:
            bad("S3", f"{node.sel} 이(가) {got['count']}개 — {node.min_count}개 이상이어야 한다",
                why_node=node.why, text=got.get("text", "")[:120])
            continue
        if node.contains and node.contains not in (got.get("text") or ""):
            bad("S3", f"{node.sel} 텍스트에 '{node.contains}' 가 없다",
                why_node=node.why, text=got.get("text", "")[:120])

    if hub_id is not None and obs.get("selected") != hub_id:
        bad("S3", f"거점 선택이 안 걸렸다 — select 값 {obs.get('selected')!r}")
    if hub_total is not None:
        want = hub_total + spec.extra_options
        if obs.get("options") != want:
            bad("S3", f"거점 목록 옵션 {obs.get('options')}개 — {want}개여야 한다(PAGES {hub_total})")

    if obs.get("gate_seen") == "timeout":
        bad("S3", f"거점을 바꿨는데 {obs.get('gate')} 를 부르지 않았다")

    if spec.map_check:
        m = obs.get("map") or {}
        overlays = m.get("poly", 0) + m.get("dot", 0)
        if m.get("found") and overlays < 1:
            bad("S3", "공실 마커/폴리곤이 0개다",
                counts={k: m.get(k) for k in ("poly", "dot", "paths", "divs", "canvases")})

    if spec.detail_click:
        d = obs.get("detail")
        if d is None:
            if obs.get("nodes", {}).get(SEL_LIST_ROW, {}).get("count"):
                bad("S3", "목록은 있는데 상세패널을 열지 못했다")
        elif not d.get("panel"):
            bad("S3", f"{SEL_DETAIL_NAME} 이 비어 있다 — 상세패널이 안 열렸다")
        elif d.get("panel") != d.get("row"):
            # 목록 첫 행과 다르면 패널이 다른 건물을 그린 것이다. `.b-name` 을 좁히지
            # 않으면 이 차이 자체를 못 본다(§제약 3).
            bad("S3", f"상세패널 건물이 다르다 — 목록 {d.get('row')!r} vs 패널 {d.get('panel')!r}")

    # S4 — 초기 렌더 예산
    if obs.get("render_ms") is None:
        bad("S4", "렌더 시간을 재지 못했다")
    elif obs["render_ms"] > budget_ms:
        bad("S4", f"초기 렌더 {obs['render_ms']}ms — 예산 {budget_ms}ms 초과",
            trigger=obs.get("trigger"))

    return fails


# ──────────────────────────── 리포트 ────────────────────────────
def load_report(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print(f"[screen] ⚠ 기존 리포트를 못 읽었다 — 새로 시작한다: {path}", flush=True)
        return {}


def save_report(path: Path, report: dict) -> None:
    """조합마다 다시 쓴다 — 도중에 세션이 죽어도 거기까지는 남는다(§제약 4).

    임시 파일에 쓰고 바꿔치기한다. 쓰는 중에 죽으면 원본이 반쯤 덮인 채 남는다.

    ⚠ **Windows 에서는 바꿔치기가 순간 막힌다.** 이 저장소는 `Documents/` 아래에 있어
      동기화·백신이 갓 쓴 `.tmp` 를 잠깐 붙잡는다. 재시도 없이 `os.replace` 를 부르면
      `PermissionError [WinError 5]` 로 **실행 전체가 죽는다** — 2026-09-07 첫 전수
      실행이 22번째 조합에서 그렇게 끝났다. 리포트 한 번 못 쓴 것이 264조합을 날릴
      이유는 없으므로, 몇 번 다시 해 보고 그래도 안 되면 **알리고 계속 간다**(§제약 4).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for wait in (0.0, 0.2, 0.5, 1.0, 2.0):
        if wait:
            time.sleep(wait)
        try:
            tmp.replace(path)
            return
        except PermissionError:
            continue
    print(f"[screen] ⚠ 리포트를 바꿔치기하지 못했다(잠김) — 이번 조합은 건너뛰고 간다: {tmp}",
          flush=True)


# ──────────────────────────── 자기 검사 ────────────────────────────
FAKE_HUB_ROW = {"id": "__self_check_hub__", "name": "자기검사거점", "gu": "검사구"}


def _obs_ok(spec: TabSpec, hub_id: str, hub_total: int) -> dict:
    """전 단계를 통과하는 가짜 관측 — 자기검사의 기준선."""
    obs = {
        "trigger": "hub-switch", "tab_open_ms": 200, "render_ms": 900,
        "gate": spec.gate, "gate_seen": "200",
        "selected": hub_id, "options": hub_total + spec.extra_options,
        "nodes": {n.sel: {"count": max(1, n.min_count),
                          "text": (n.contains or "결론 문장")} for n in spec.nodes},
        "console_errors": [], "page_errors": [], "resource_errors": [],
        "api_5xx": [], "api_4xx": [],
    }
    if spec.map_check:
        obs["map"] = {"found": True, "w": 1200, "h": 900, "children": 3,
                      "poly": 840, "dot": 0, "paths": 850, "divs": 40,
                      "canvases": 0, "note": ""}
    if spec.detail_click:
        obs["detail"] = {"row": "동남빌딩", "panel": "동남빌딩"}
    return obs


def self_check() -> int:
    """브라우저 없이 판정부를 검사한다. 반환값 = 실패 건수(0 이면 통과).

    핵심은 **없는 셀렉터를 실패로 잡는가**다(통과 조건 2). 나머지 셋은 그 규칙이
    나머지 단계를 무디게 만들지 않았는지 같이 본다.
    """
    total = 66
    bad = 0

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal bad
        if not cond:
            bad += 1
        print(f"{'PASS' if cond else 'FAIL'}  {label}{'  ' + detail if detail else ''}")

    for spec in (resolve(t, FAKE_HUB_ROW) for t in TABS):
        hub = FAKE_HUB
        ok = _obs_ok(spec, hub, total)
        check(f"[{spec.key}] 정상 관측은 통과", judge(spec, ok, hub_total=total, hub_id=hub) == [])

        # ① 없는 셀렉터 — 명세에 넣고, 화면에는 없다(count 0)
        canary = with_canary((spec,))[0]
        obs = _obs_ok(canary, hub, total)
        obs["nodes"][CANARY_SEL] = {"count": 0, "text": ""}
        fails = judge(canary, obs, hub_total=total, hub_id=hub)
        check(f"[{spec.key}] 없는 셀렉터를 S3 실패로 잡는다",
              any(f["stage"] == "S3" and CANARY_SEL in f["why"] for f in fails),
              str(fails))

        # ②  셀렉터를 아예 못 재고 지나간 경우도 실패다(조용한 통과 금지)
        obs2 = _obs_ok(canary, hub, total)
        obs2["nodes"].pop(CANARY_SEL, None)
        check(f"[{spec.key}] 측정 누락도 실패로 잡는다",
              any("측정되지 않은" in f["why"] for f in judge(canary, obs2, hub_total=total, hub_id=hub)))

        # ③ 나머지 단계가 살아 있는가
        o = _obs_ok(spec, hub, total); o["console_errors"] = ["Uncaught TypeError: x"]
        check(f"[{spec.key}] S1 콘솔 에러", any(f["stage"] == "S1" for f in judge(spec, o, hub_total=total, hub_id=hub)))
        o = _obs_ok(spec, hub, total); o["render_ms"] = BUDGET_MS + 1
        check(f"[{spec.key}] S4 예산 초과", any(f["stage"] == "S4" for f in judge(spec, o, hub_total=total, hub_id=hub)))
        o = _obs_ok(spec, hub, total); o["options"] = total - 1 + spec.extra_options
        check(f"[{spec.key}] 거점이 목록에서 빠지면 실패",
              any("옵션" in f["why"] for f in judge(spec, o, hub_total=total, hub_id=hub)))

    map_spec = resolve(TABS_BY_KEY["map"], FAKE_HUB_ROW)
    o = _obs_ok(map_spec, FAKE_HUB, total); o["map"]["children"] = 0
    check("[map] S2 SDK 자식 0", any(f["stage"] == "S2" for f in judge(map_spec, o, hub_total=total, hub_id=FAKE_HUB)))
    o = _obs_ok(map_spec, FAKE_HUB, total); o["map"]["h"] = 0
    check("[map] S2 캔버스 높이 0", any(f["stage"] == "S2" for f in judge(map_spec, o, hub_total=total, hub_id=FAKE_HUB)))
    o = _obs_ok(map_spec, FAKE_HUB, total); o["map"]["poly"] = 0; o["map"]["dot"] = 0
    check("[map] S3 마커·폴리곤 0", any("마커" in f["why"] for f in judge(map_spec, o, hub_total=total, hub_id=FAKE_HUB)))
    o = _obs_ok(map_spec, FAKE_HUB, total); o["detail"]["panel"] = "다른빌딩"
    check("[map] S3 상세패널이 다른 건물", any("상세패널 건물" in f["why"] for f in judge(map_spec, o, hub_total=total, hub_id=FAKE_HUB)))
    o = _obs_ok(map_spec, FAKE_HUB, total)
    # 거점을 바꿨는데 직전 거점의 화면이 남아 있는 순간 — 통과시키면 안 된다.
    o["nodes"][SEL_PAGE_TITLE] = {"count": 1, "text": "직전거점 · 건물 공실"}
    check("[map] S3 남의 거점 화면", any("이 거점의 화면인가" == f.get("why_node")
                                      for f in judge(map_spec, o, hub_total=total, hub_id=FAKE_HUB)))

    o = _obs_ok(map_spec, FAKE_HUB, total)
    o["nodes"][SEL_PAGE_SUMMARY] = {"count": 1, "text": "마포구 · 8동 · 샘플(추정)"}
    check("[map] S3 샘플 폴백 문구", any("실측" in f["why"] for f in judge(map_spec, o, hub_total=total, hub_id=FAKE_HUB)))

    print(f"\n[self-check] 실패 {bad}건")
    return bad


# ──────────────────────────── 루프 ────────────────────────────
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="66거점 × PPPP 4탭 화면 회귀 검사",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hubs", help="거점 slug 목록(콤마). 예: yeonnam,sinchon,hongdae")
    p.add_argument("--tabs", default=",".join(t.key for t in TABS),
                   help=f"검사할 탭(콤마). 기본 {','.join(t.key for t in TABS)}")
    p.add_argument("--base-url", default=BASE_URL)
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--shots", default=str(SHOTS))
    p.add_argument("--budget-ms", type=int, default=BUDGET_MS)
    p.add_argument("--node-timeout-ms", type=int, default=NODE_TIMEOUT_MS)
    p.add_argument("--gate-timeout-ms", type=int, default=GATE_TIMEOUT_MS)
    p.add_argument("--fresh", action="store_true", help="기존 리포트를 무시하고 처음부터")
    p.add_argument("--retry-failed", action="store_true", help="실패했던 조합만 다시 잰다")
    p.add_argument("--headed", action="store_true", help="브라우저 창을 띄운다")
    p.add_argument("--canary", action="store_true",
                   help="모든 탭에 없는 셀렉터를 덧붙인다 — 전 조합이 실패해야 정상")
    p.add_argument("--self-check", action="store_true",
                   help="브라우저 없이 판정부만 검사한다(서버·지도 키 불필요)")
    return p.parse_args(argv)


def select_hubs(all_hubs: list[dict], raw: str | None) -> list[dict]:
    if not raw:
        return all_hubs
    want = [s.strip() for s in raw.split(",") if s.strip()]
    known = {h["id"] for h in all_hubs}
    unknown = [w for w in want if w not in known]
    if unknown:
        raise SystemExit(
            f"[screen] 모르는 거점: {', '.join(unknown)}\n"
            f"  서빙 거점 {len(all_hubs)}곳: {', '.join(sorted(known))}")
    order = {h["id"]: h for h in all_hubs}
    return [order[w] for w in want]


def select_tabs(raw: str) -> tuple[TabSpec, ...]:
    keys = [s.strip() for s in raw.split(",") if s.strip()]
    unknown = [k for k in keys if k not in TABS_BY_KEY]
    if unknown:
        raise SystemExit(f"[screen] 모르는 탭: {', '.join(unknown)} "
                         f"(가능: {', '.join(TABS_BY_KEY)})")
    return tuple(TABS_BY_KEY[k] for k in keys)


def combo_key(hub: dict, spec: TabSpec) -> str:
    return f"{hub['id']}|{spec.key}"


def pending(combos: list[tuple[dict, TabSpec]], results: dict,
            retry_failed: bool = False) -> list[tuple[dict, TabSpec]]:
    """아직 재지 않은 조합만 고른다 — 264조합은 한 번에 안 끝난다(§제약 4).

    이미 **잰** 것은 통과든 실패든 건너뛴다. 무인 실행은 기록만 하고 고치지 않으므로
    (autorun §4), 실패를 다시 재는 것은 사람이 `--retry-failed` 로 정한다.
    """
    todo = []
    for hub, spec in combos:
        prev = results.get(combo_key(hub, spec))
        if prev is None or (retry_failed and prev.get("status") != "pass"):
            todo.append((hub, spec))
    return todo


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_check:
        return 1 if self_check() else 0

    # 뒤 슬래시를 떼어 둔다 — `.../api/v1` 을 이어 붙일 때 `//` 가 되는 것을 막는다.
    args.base_url = args.base_url.rstrip("/")
    all_hubs = load_hubs()
    hubs = select_hubs(all_hubs, args.hubs)
    specs = select_tabs(args.tabs)
    if args.canary:
        specs = with_canary(specs)
        print("[screen] ⚠ 카나리 모드 — 전 조합이 실패해야 정상이다", flush=True)
    hexes = vacancy_colors()

    out = Path(args.out)
    shots = Path(args.shots)
    report = {} if args.fresh else load_report(out)
    results: dict = report.get("results", {})

    info = preflight(args.base_url, [h["id"] for h in all_hubs])

    combos = [(h, s) for h in hubs for s in specs]
    todo = pending(combos, results, args.retry_failed)
    print(f"[screen] 거점 {len(hubs)} × 탭 {len(specs)} = {len(combos)}조합 · "
          f"이번에 잴 것 {len(todo)}개 (이미 잰 것 {len(combos) - len(todo)}개)", flush=True)

    report.update({
        "started": report.get("started") or datetime.now().isoformat(timespec="seconds"),
        "updated": datetime.now().isoformat(timespec="seconds"),
        "preflight": info, "budget_ms": args.budget_ms,
        "hubs_total": len(all_hubs), "tabs": [s.key for s in specs],
        "canary": bool(args.canary), "results": results,
    })
    if not todo:
        print("[screen] 잴 것이 없다 — --retry-failed 또는 --fresh 로 다시 부를 것", flush=True)
        _finish(report, out)
        return 1 if any(r.get("status") != "pass" for r in results.values()) else 0

    from playwright.sync_api import Error as PWError, sync_playwright

    shots.mkdir(parents=True, exist_ok=True)
    done = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(args.node_timeout_ms)
        rec = Recorder()
        rec.attach(page)
        page.goto(args.base_url, wait_until="domcontentloaded")

        # 지도 SDK 는 앱당 한 번만 뜬다(MapHost). 그 부팅을 첫 거점의 렌더 시간에
        # 얹으면 S4 가 SDK 부팅을 재게 되므로 미리 한 번 깨워 두고 따로 기록한다.
        map_spec = next((sp for sp in specs if sp.map_check), None)
        if map_spec is not None:
            t = time.monotonic()
            try:
                page.get_by_role("button", name=map_spec.label, exact=True).first.click()
                page.wait_for_function(
                    "() => { const el = document.querySelector('" + SEL_MAP_CANVAS + "');"
                    " return !!el && el.childElementCount > 0; }", timeout=30000)
                report["sdk_boot_ms"] = round((time.monotonic() - t) * 1000)
            except PWError:
                report["sdk_boot_ms"] = None
                print(f"[screen] ⚠ 지도 SDK 가 30초 안에 뜨지 않았다 — "
                      f"{map_spec.label} 탭은 S2 에서 실패한다", flush=True)

        for hub, spec in todo:
            key = combo_key(hub, spec)
            try:
                rspec = resolve(spec, hub)      # 명세에 이 거점의 이름을 끼운다
                obs = probe(page, rspec, hub, rec, hexes, args)
                fails = judge(rspec, obs, budget_ms=args.budget_ms,
                              hub_total=len(all_hubs), hub_id=hub["id"])
                status = "pass" if not fails else "fail"
            except PWError as e:
                obs, fails, status = {}, [{"stage": "S0", "why": f"조작 실패: {e}"[:400]}], "error"
            except Exception as e:                      # noqa: BLE001 - 한 조합 때문에 루프를 죽이지 않는다
                obs = {}
                fails = [{"stage": "S0", "why": f"{type(e).__name__}: {e}"[:400],
                          "trace": traceback.format_exc(limit=3)[:800]}]
                status = "error"

            shot = None
            if status == "pass":
                # 지난 실행의 스크린샷을 지운다 — reports/screens 는 **지금 실패한 것**만
                # 담아야 한다. 남겨 두면 고친 뒤에도 실패 화면이 그대로 쌓인다.
                stale_shot = shots / f"{hub['id']}__{spec.key}.png"
                if stale_shot.exists():
                    stale_shot.unlink()
            else:
                shot_path = shots / f"{hub['id']}__{spec.key}.png"
                try:
                    page.screenshot(path=str(shot_path))
                    shot = _rel(shot_path)
                except PWError:
                    pass

            results[key] = {
                "hub": hub["id"], "name": hub["name"], "tab": spec.key,
                "status": status, "failures": fails, "obs": obs, "shot": shot,
                "at": datetime.now().isoformat(timespec="seconds"),
            }
            done += 1
            ms = obs.get("render_ms", "-")
            head = fails[0]["why"] if fails else ""
            print(f"[screen] {done}/{len(todo)} {key}: {status} {ms}ms {head}", flush=True)
            report["updated"] = datetime.now().isoformat(timespec="seconds")
            save_report(out, report)      # 조합마다 — 죽어도 여기까지는 남는다

        browser.close()

    _finish(report, out)
    bad = [k for k, v in results.items() if v.get("status") != "pass"]
    print(f"[screen] 끝 — 실패 {len(bad)}건 / 잰 조합 {len(results)}개 · 리포트 {out}",
          flush=True)
    if args.canary:
        # 카나리 실행은 전부 실패해야 정상이다. 하나라도 통과하면 검사기가 눈을 감은 것.
        passed = [k for k, v in results.items() if v.get("status") == "pass"]
        if passed:
            print(f"[screen] ✗ 카나리인데 통과한 조합이 있다 — 검사기가 화면을 안 본다: {passed[:5]}",
                  flush=True)
            return 1
        print("[screen] ✓ 카나리 — 전 조합이 실패로 잡혔다(검사기가 살아 있다)", flush=True)
        return 0
    return 1 if bad else 0


def _rel(path: Path) -> str:
    """리포트에 적을 경로 — 저장소 안이면 상대경로로, 밖이면 그대로.

    `--shots` 로 저장소 밖(임시 폴더 등)을 가리킬 수 있다. 예전엔 여기서
    `relative_to(ROOT)` 가 ValueError 를 던져 **루프 전체가 죽었다** — 실패 하나를
    기록하려다 나머지 조합을 못 재는 자리라, 경로 계산이 검사를 막지 않게 한다.
    """
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _finish(report: dict, out: Path) -> None:
    results = report.get("results", {})
    report["summary"] = {
        "measured": len(results),
        "pass": sum(1 for v in results.values() if v.get("status") == "pass"),
        "fail": sum(1 for v in results.values() if v.get("status") == "fail"),
        "error": sum(1 for v in results.values() if v.get("status") == "error"),
    }
    save_report(out, report)


if __name__ == "__main__":
    raise SystemExit(main())

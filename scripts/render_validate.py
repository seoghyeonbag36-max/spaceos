#!/usr/bin/env python
"""지도가 필요 없는 세 표면의 렌더 검증 — ProgramStudio · HubExplorer · BuildingViewer.

## 왜 따로 있나 (`scripts/screen_loop.py` 와 무엇이 다른가)

`screen_loop.py` 는 66거점 × 4탭을 도는 **넓은** 회귀 루프이고, 자기 경계에
두 가지를 적어 두었다 — 층 스택·거리뷰(`.b-twin`)는 열지 않는다, Program 생성은
부르지 않는다. 그 두 자리는 "사람이 본다"로 남아 있었다.

여기는 그 반대다. **거점 하나 · 표면 셋**을 깊게 본다. 그리고 전제가 하나 더 있다:

  **지도 SDK 가 없는 환경에서도 서야 하는 화면만 고른다.**

네이버 지도 SDK(`oapi.map.naver.com`)에 못 나가는 환경 — 오프라인 컨테이너, 키가 없는
CI, 도메인 미등록 origin — 에서 이 세 화면은 **여전히 실데이터를 그려야 한다**. 세 화면
모두 값의 출처가 지도가 아니라 백엔드 gold 이기 때문이다. 그런데 그게 실제로 그런지는
아무도 확인한 적이 없었다. HubExplorer 는 MapHost 안에 살고(오버레이), BuildingViewer 는
지도 마커 클릭으로만 열리므로, "지도가 죽으면 이 화면들도 같이 죽는가"가 열린 질문이었다.

## 무엇을 재는가 — 표면마다 세 단계

  R1  콘솔 에러 0 · pageerror 0 · API 5xx 0
      단, **지도 SDK 계열은 따로 센다**(아래 `MAP_SDK`). 그건 이 검증의 전제이지 결함이
      아니다 — 리포트에 `map_sdk_notes` 로 남기되 실패로 세지 않는다.
  R2  뼈대가 섰는가 — 루트 노드와 필수 자식이 있는가
  R3  **빈 상태가 아닌 실제 값**인가 — 이게 이 스크립트의 존재 이유다.
      노드가 있는 것과 값이 든 것은 다르다. "불러오는 중…" · "실측 없음" · 옵션 0개는
      전부 R2 를 통과하고 R3 에서 떨어져야 한다.

## 실행

    # 터미널 1 — 백엔드
    cd apps/backend && .venv/bin/python -m uvicorn app.main:app --port 8022
    # 터미널 2 — 프론트 (프록시를 8022 로 돌린다)
    cd apps/frontend && PLACEOS_API_TARGET=http://localhost:8022 npm run dev
    # 터미널 3
    PYTHONIOENCODING=utf-8 python -u scripts/render_validate.py

    python -u scripts/render_validate.py --canary      # 실검사 — 전 표면이 실패해야 정상
    python -u scripts/render_validate.py --headed      # 눈으로 볼 때

환경변수:
    PLACEOS_WEB_BASE   프론트 주소 (기본 http://localhost:5173)
    PLACEOS_CHROMIUM   chromium 실행 파일 경로. 번들 브라우저가 없는 컨테이너에서 쓴다
                       (예: /opt/pw-browsers/chromium-1194/chrome-linux/chrome)

## 설계 제약 (screen_loop.py 의 것을 그대로 잇는다)

1. Node `@playwright/test` 를 깔지 않는다 — Python `playwright` 한 벌로만 간다.
2. **거점 slug 를 박지 않는다.** 목록은 백엔드 `/api/v1/commercial-districts` 를 런타임에
   읽어 첫 거점을 쓴다.
3. 판정(`judge`)은 관측(`observe`)에서 분리한 **순수 함수**다 — 브라우저 없이 검사할 수 있다.
4. 로그·리포트는 utf-8 로만 쓴다.

산출: `reports/render_validate.json` + `reports/screens/render_{표면}.png`
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:                                    # cp949 콘솔에서 em dash 로 죽지 않게
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

OUT = ROOT / "reports" / "render_validate.json"
SHOTS = ROOT / "reports" / "screens"
BASE_URL = "http://localhost:5173"
NODE_TIMEOUT_MS = 10000
# 마케팅 생성 — 키가 있으면 Claude 실호출이라 느리다(스텁 폴백은 즉시).
GEN_TIMEOUT_MS = 40000

# 리소스 적재 실패 줄은 콘솔이 아니라 네트워크 채널로 센다(screen_loop.py 와 같은 규칙).
RESOURCE_ERR = re.compile(r"Failed to load resource")

# 지도 SDK 계열 — **이 검증의 전제**라 결함으로 세지 않는다.
# 키가 없으면 loadNaverMaps() 가 네트워크에 나가기 전에 reject 하고(naverMap.ts),
# 키가 있고 차단된 환경이면 script.onerror 로 떨어진다. 두 경우 다 여기 걸린다.
MAP_SDK = re.compile(
    r"VITE_NAVER_MAPS_KEY_ID|oapi\.map\.naver\.com|naver\.maps|네이버 지도|navermap",
    re.IGNORECASE,
)


# ──────────────────────────── 관측 ────────────────────────────
class Recorder:
    """콘솔·pageerror·응답을 모은다. 표면마다 `reset()` 하고 표면 끝에 `snapshot()`."""

    def __init__(self) -> None:
        self.console: list[str] = []
        self.resource: list[str] = []
        self.page_errors: list[str] = []
        self.http_5xx: list[str] = []

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
        if res.status >= 500:
            self.http_5xx.append(f"{res.status} {res.url}"[:400])

    def reset(self) -> None:
        self.console.clear()
        self.resource.clear()
        self.page_errors.clear()
        self.http_5xx.clear()

    def snapshot(self) -> dict:
        """SDK 계열을 갈라서 낸다 — 결함(`*_errors`)과 전제(`map_sdk_notes`)를 섞지 않는다."""
        sdk, real = [], []
        for line in [*self.console, *self.resource, *self.page_errors]:
            (sdk if MAP_SDK.search(line) else real).append(line)
        return {
            "console_errors": [c for c in self.console if not MAP_SDK.search(c)],
            "resource_errors": [r for r in self.resource if not MAP_SDK.search(r)],
            "page_errors": [p for p in self.page_errors if not MAP_SDK.search(p)],
            "http_5xx": list(self.http_5xx),
            "map_sdk_notes": sdk,
            "_real_total": len(real),
        }


def _api(path: str) -> object:
    """백엔드를 **프론트 프록시를 통해** 읽는다 — 브라우저가 타는 경로와 같아야 한다."""
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=20) as r:
        return json.load(r)


# 표면마다: 브라우저를 몰아 DOM 수치를 뽑는다. 판정은 하지 않는다.
def observe_program(page, ctx: dict) -> dict:
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.get_by_role("button", name="Program").click()
    page.wait_for_selector(".progstudio", timeout=NODE_TIMEOUT_MS)
    # 거점 목록이 도착해 select 가 열릴 때까지 — 이걸 안 기다리면 "불러오는 중"을 잰다.
    page.wait_for_function(
        "() => { const s = document.querySelector('.progstudio select');"
        " return s && !s.disabled && s.options.length > 1; }",
        timeout=NODE_TIMEOUT_MS,
    )
    before = page.evaluate(
        """() => {
          const root = document.querySelector('.progstudio');
          const sel = root?.querySelector('select');
          const opts = sel ? [...sel.options].map(o => o.textContent.trim()) : [];
          const verdict = root?.querySelector('.verdict .vone');
          const grounds = [...(root?.querySelectorAll('.verdict .vgrounds .gv') ?? [])]
            .map(n => n.textContent.trim()).filter(Boolean);
          return {
            root: !!root,
            option_texts: opts,
            option_count: Math.max(0, opts.length - 1),   // 첫 줄은 "— 결합 안 함 —"
            select_disabled: sel ? sel.disabled : null,
            verdict_text: verdict ? verdict.textContent.trim() : "",
            grounds_count: grounds.length,
            loading_left: root ? root.textContent.includes('거점 불러오는 중') : false,
          };
        }"""
    )

    # 생성까지 **실제로 돌린다.** 폼만 보고 끝내면 이 화면의 답(채널 카드)은 한 번도
    # 그려지지 않는다. LLM 키가 없어도 백엔드가 규칙 기반 스텁으로 답하므로
    # (services/marketing.py `_rule_stub`) 오프라인에서도 실값이 나온다 —
    # 그래서 이 화면은 screen_loop.py 가 비워 둔 자리를 여기서 메울 수 있다.
    page.get_by_role("button", name="예시 채우기").click()
    page.locator(".progstudio button[type=submit]").click()
    page.wait_for_selector(".progstudio .result .rname", timeout=GEN_TIMEOUT_MS)
    after = page.evaluate(
        """() => {
          const txt = (s, r = document) => r.querySelector(s)?.textContent.trim() ?? "";
          const res = document.querySelector('.progstudio .result');
          const plans = [...(res?.querySelectorAll('.plan') ?? [])].map(n => ({
            channel: txt('.pchannel', n),
            content: txt('.pcontent', n),
            rationale: txt('.prationale', n),
          }));
          return {
            result_open: !!res,
            result_name: txt('.progstudio .result .rname'),
            result_source: txt('.progstudio .result .srcbadge'),
            plan_count: plans.length,
            online_count: res?.querySelectorAll('.plan.is-online').length ?? 0,
            offline_count: res?.querySelectorAll('.plan.is-offline').length ?? 0,
            plans_sample: plans.slice(0, 2),
            plans_empty: plans.filter(p => !p.channel || !p.content).length,
            tone_chips: [...(res?.querySelectorAll('.chips .chip') ?? [])].map(n => n.textContent.trim()),
          };
        }"""
    )
    return {**before, **after}


def observe_hubs(page, ctx: dict) -> dict:
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.get_by_role("button", name="거점").click()
    page.wait_for_selector(".hx-list .hx-item", timeout=NODE_TIMEOUT_MS)
    # 첫 거점을 골라 요약 패널까지 연다 — 목록만 보면 우측 패널은 검증되지 않는다.
    page.locator(f".hx-item:has-text('{ctx['hub_name']}')").first.click()
    page.wait_for_selector(".hx-summary .hx-figure-value", timeout=NODE_TIMEOUT_MS)
    return page.evaluate(
        """() => {
          const txt = (s, r = document) => r.querySelector(s)?.textContent.trim() ?? "";
          const items = [...document.querySelectorAll('.hx-list .hx-item')];
          const vac = items.map(i => txt('.hx-item-vac', i));
          const sum = document.querySelector('.hx-summary');
          const rows = [...(sum?.querySelectorAll('.hx-rows') ?? [])]
            .map(n => n.textContent.trim());
          return {
            item_count: items.length,
            title: txt('.hx-list .hx-title'),
            measured_items: vac.filter(v => v.includes('%')).length,
            absent_items: vac.filter(v => v.includes('실측 없음')).length,
            summary_open: !!sum,
            summary_name: txt('.hx-summary .hx-sum-name'),
            figure_value: txt('.hx-summary .hx-figure-value'),
            source_badge: txt('.hx-summary .hx-badge-src'),
            rows_text: rows.join(' | '),
            legend: txt('.hx-legend-text'),
          };
        }"""
    )


def observe_viewer(page, ctx: dict) -> dict:
    page.goto(f"{BASE_URL}/harness/building-viewer.html?district={ctx['hub_id']}",
              wait_until="domcontentloaded")
    page.wait_for_selector("[data-testid=harness-ready]", timeout=NODE_TIMEOUT_MS)
    page.wait_for_selector("[data-testid=viewer-measured] .fstack-row", timeout=NODE_TIMEOUT_MS)
    return page.evaluate(
        """() => {
          const scan = (kind) => {
            const s = document.querySelector(`[data-testid=viewer-${kind}]`);
            if (!s) return null;
            const rows = [...s.querySelectorAll('.fstack-row')];
            const kinds = {};
            for (const r of rows) {
              const k = [...r.classList].find(c => c !== 'fstack-row') ?? '?';
              kinds[k] = (kinds[k] ?? 0) + 1;
            }
            return {
              building: s.dataset.building ?? "",
              rows: rows.length,
              kinds,
              labels: rows.map(r => r.querySelector('.fstack-no')?.textContent.trim()),
              legend: s.querySelector('.bviewer-legend')?.textContent.trim() ?? "",
              street_state: s.querySelector('.sview-msg')?.textContent.trim()
                         ?? (s.querySelector('.sview-meta') ? '촬영 메타 표시' : '(없음)'),
            };
          };
          return { measured: scan('measured'), approx: scan('approx'),
                   harness_error: document.querySelector('[data-testid=harness-error]')?.textContent ?? null };
        }"""
    )


# ──────────────────────────── 판정 (순수 함수) ────────────────────────────
def judge(surface: str, obs: dict, ctx: dict, canary: bool = False) -> list[dict]:
    """관측 dict → 체크 목록. 브라우저 없이 부를 수 있어야 한다(테스트 가능성)."""
    checks: list[dict] = []

    def ck(stage: str, name: str, ok: bool, detail: object = "") -> None:
        checks.append({"stage": stage, "name": name, "ok": bool(ok), "detail": detail})

    # R1 — 결함만 센다. 지도 SDK 계열은 map_sdk_notes 로 빠져 있다.
    ck("R1", "콘솔 에러 0", not obs["console_errors"], obs["console_errors"][:3])
    ck("R1", "pageerror 0", not obs["page_errors"], obs["page_errors"][:3])
    ck("R1", "리소스 적재 실패 0", not obs["resource_errors"], obs["resource_errors"][:3])
    ck("R1", "API 5xx 0", not obs["http_5xx"], obs["http_5xx"][:3])

    if surface == "program":
        ck("R2", "ProgramStudio 루트", obs["root"])
        ck("R2", "결론 1줄(Verdict)", bool(obs["verdict_text"]), obs["verdict_text"][:120])
        ck("R2", "근거 3줄", obs["grounds_count"] >= 3, obs["grounds_count"])
        ck("R3", "거점 select 가 열려 있다", obs["select_disabled"] is False)
        ck("R3", f"거점 옵션 {ctx['hub_count']}개", obs["option_count"] == ctx["hub_count"],
           obs["option_count"])
        ck("R3", "옵션이 실제 거점 이름", ctx["hub_name"] in " ".join(obs["option_texts"]),
           obs["option_texts"][1:4])
        ck("R3", "'불러오는 중' 잔류 없음", not obs["loading_left"])
        # 생성 결과 — 이 화면의 답. 폼이 서는 것과 답이 나오는 것은 다르다.
        ck("R3", "생성 결과 패널", obs["result_open"], obs["result_name"])
        ck("R3", "채널안 온라인·오프라인 둘 다",
           obs["online_count"] > 0 and obs["offline_count"] > 0,
           f"온 {obs['online_count']} · 오프 {obs['offline_count']}")
        ck("R3", "채널 카드에 빈 칸 없음", obs["plans_empty"] == 0, obs["plans_sample"])
        ck("R3", "생성 출처 표기", bool(obs["result_source"]), obs["result_source"])

    elif surface == "hubs":
        ck("R2", "거점 목록 렌더", obs["item_count"] > 0, obs["item_count"])
        ck("R2", "요약 패널 열림", obs["summary_open"])
        ck("R3", f"목록 {ctx['hub_count']}곳", obs["item_count"] == ctx["hub_count"],
           obs["item_count"])
        ck("R3", "제목에 거점 수", str(ctx["hub_count"]) in obs["title"], obs["title"])
        ck("R3", "공실률 실측이 든 행 다수", obs["measured_items"] >= ctx["hub_count"] // 2,
           f"{obs['measured_items']}/{obs['item_count']}행")
        ck("R3", "요약이 고른 거점", ctx["hub_name"] in obs["summary_name"], obs["summary_name"])
        ck("R3", "대표 공실률에 값", "%" in obs["figure_value"], obs["figure_value"])
        ck("R3", "출처 배지 실측(Gold)", "실측" in obs["source_badge"], obs["source_badge"])
        ck("R3", "집계 행에 숫자", bool(re.search(r"\d", obs["rows_text"])), obs["rows_text"][:120])
        ck("R3", "실측 범위 배지", bool(obs["legend"]) and "없음" not in obs["legend"], obs["legend"])

    elif surface == "viewer":
        ck("R2", "하네스 오류 없음", obs["harness_error"] is None, obs["harness_error"])
        for kind in ("measured", "approx"):
            d = obs[kind]
            ck("R2", f"{kind} 스택 렌더", bool(d) and d["rows"] > 0, d and d["rows"])
            if not d:
                continue
            ck("R3", f"{kind} 층 라벨 1F..", bool(d["labels"]) and d["labels"][-1] == "1F",
               d["labels"][:4])
        m = obs["measured"]
        if m:
            # 스택이 존재하는 이유가 '영업/공실을 층으로 가른다'이므로 둘 다 실제로
            # 나와야 한다. 한쪽만 나오면 색이 하나뿐인 막대이고, 그건 검증이 아니다.
            ck("R3", "실배치 스택에 영업 층", m["kinds"].get("occupied", 0) > 0, m["kinds"])
            ck("R3", "실배치 스택에 공실 층", m["kinds"].get("vacant", 0) > 0, m["kinds"])
            ck("R3", "실배치 범례가 대장 근거", "건축물대장" in m["legend"], m["legend"][:120])
        a = obs["approx"]
        if a:
            ck("R3", "근사 스택은 근사라고 밝힌다", "근사" in a["legend"], a["legend"][:120])

    if canary:
        # 실검사 — 이 검사기가 초록을 거저 주지 않는다는 증거. 전 표면이 실패해야 정상이다.
        ck("R3", "CANARY(존재할 수 없는 기대)", False, "canary")

    return checks


# ──────────────────────────── 실행 ────────────────────────────
SURFACES = [
    ("program", "ProgramStudio", observe_program),
    ("hubs", "HubExplorer", observe_hubs),
    ("viewer", "BuildingViewer", observe_viewer),
]


def main(argv: list[str] | None = None) -> int:
    global BASE_URL
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--canary", action="store_true", help="실검사 — 전 표면이 실패해야 정상")
    ap.add_argument("--base", default=None, help="프론트 주소 (기본 PLACEOS_WEB_BASE 또는 :5173)")
    args = ap.parse_args(argv)

    import os
    BASE_URL = args.base or os.environ.get("PLACEOS_WEB_BASE") or os.environ.get("SPACEOS_WEB_BASE", BASE_URL)
    chromium_path = os.environ.get("PLACEOS_CHROMIUM") or os.environ.get("SPACEOS_CHROMIUM") or None

    # 거점 목록을 런타임에 읽는다 — slug 를 박지 않는다(설계 제약 2).
    try:
        hubs = _api("/api/v1/commercial-districts")
    except (urllib.error.URLError, OSError) as e:
        print(f"거점 목록을 못 읽었다 — 백엔드·프록시가 떠 있는지 확인할 것: {e}")
        return 2
    assert isinstance(hubs, list) and hubs, "거점 목록이 비었다"
    ctx = {"hub_count": len(hubs), "hub_id": hubs[0]["id"], "hub_name": hubs[0]["name"]}
    print(f"거점 {ctx['hub_count']}곳 · 기준 거점 {ctx['hub_name']}({ctx['hub_id']})")

    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed, executable_path=chromium_path)
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        rec = Recorder()
        rec.attach(page)

        for key, label, observe in SURFACES:
            rec.reset()
            entry: dict = {"surface": key, "label": label}
            try:
                dom = observe(page, ctx)
                obs = {**rec.snapshot(), **dom}
                entry["checks"] = judge(key, obs, ctx, canary=args.canary)
                entry["observed"] = dom
                entry["map_sdk_notes"] = obs["map_sdk_notes"]
            except Exception as e:                       # 관측 자체가 죽은 것도 결과다
                entry["checks"] = [{"stage": "R2", "name": "표면 관측", "ok": False,
                                    "detail": f"{type(e).__name__}: {e}"[:300]}]
                entry["map_sdk_notes"] = rec.snapshot()["map_sdk_notes"]
            shot = SHOTS / f"render_{key}.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
                entry["screenshot"] = str(shot.relative_to(ROOT))
            except Exception:
                pass

            failed = [c for c in entry["checks"] if not c["ok"]]
            entry["ok"] = not failed
            results.append(entry)
            mark = "PASS" if entry["ok"] else "FAIL"
            print(f"\n[{mark}] {label} — {len(entry['checks']) - len(failed)}/{len(entry['checks'])} 통과")
            for c in entry["checks"]:
                if not c["ok"]:
                    print(f"    ✗ {c['stage']} {c['name']}: {c['detail']}")
            if entry["map_sdk_notes"]:
                print(f"    · 지도 SDK 계열 {len(entry['map_sdk_notes'])}건(전제, 결함 아님):"
                      f" {entry['map_sdk_notes'][0][:90]}")
        browser.close()

    ok = all(r["ok"] for r in results)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_url": BASE_URL, "canary": args.canary, "context": ctx,
        "ok": ok, "surfaces": results,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'전부 통과' if ok else '실패 있음'} → {OUT.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

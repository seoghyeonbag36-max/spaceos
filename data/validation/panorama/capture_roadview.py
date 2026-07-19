"""로드뷰 자동 캡처 — 표본 30동을 네이버 파노라마로 스크린샷 (내부 검증 전용).

roadview_sample.csv 의 각 건물 중심좌표에 대해 pano.html(네이버 지도 JS 파노라마,
등록 도메인 localhost:5173)을 열어 건물을 바라보는 화면을 저장한다:
  shots/{순번}_{지번}_a.png   저층부 (tilt 5°)
  shots/{순번}_{지번}_b.png   상층부 (tilt 28° — 판정 기준이 '건물 전체 호실'이므로)
  shots/capture_report.json   건물별 상태·파노라마 촬영일

선행: 정적 서버가 떠 있어야 한다 —
  python -m http.server 5173 --directory data/validation/panorama
브라우저는 설치돼 있는 Edge/Chrome 채널을 사용한다 (playwright install 불필요).

실행: python -m data.validation.panorama.capture_roadview
"""
from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

_HERE = Path(__file__).resolve().parent
_CSV = _HERE.parent / "roadview_sample.csv"
_SHOTS = _HERE / "shots"
_KEY_RE = re.compile(r"^VITE_NAVER_MAPS_KEY_ID\s*=\s*(\S+)", re.M)
_TILTS = (("a", 5), ("b", 28))


def _naver_key() -> str:
    env = _HERE.parents[2] / "apps" / "frontend" / ".env"
    m = _KEY_RE.search(env.read_text(encoding="utf-8-sig"))
    if not m:
        raise SystemExit("apps/frontend/.env 에 VITE_NAVER_MAPS_KEY_ID 없음")
    return m.group(1).strip().lstrip("﻿")


def run() -> None:
    key = _naver_key()
    rows = list(csv.DictReader(_CSV.open(encoding="utf-8-sig")))
    _SHOTS.mkdir(exist_ok=True)
    report: list[dict] = []

    with sync_playwright() as pw:
        browser = None
        for channel in ("msedge", "chrome", None):
            try:
                browser = pw.chromium.launch(channel=channel, headless=True)
                break
            except Exception:
                continue
        if browser is None:
            raise SystemExit("Edge/Chrome/Chromium 실행 실패 — playwright install chromium 필요")

        page = browser.new_page(viewport={"width": 1152, "height": 864})
        for i, r in enumerate(rows, 1):
            lat, lon = r["coord"].split(",")
            slug = r["jibun"].replace(" ", "_")
            entry = {"idx": i, "id": r["id"], "jibun": r["jibun"], "status": "", "photo_date": ""}
            try:
                page.goto(f"http://localhost:5173/pano.html?key={key}&lat={lat}&lon={lon}")
                page.wait_for_function("document.title !== 'loading'", timeout=15000)
                info = page.evaluate("window.__pano")
                entry["status"] = info["status"]
                entry["photo_date"] = info.get("photoDate", "")
                if info["status"] == "ok":
                    for suffix, tilt in _TILTS:
                        page.evaluate(f"window.__setTilt({tilt})")
                        time.sleep(2.5)   # 파노라마 타일 로드 대기
                        page.screenshot(path=str(_SHOTS / f"{i:02d}_{slug}_{suffix}.png"))
            except Exception as exc:
                entry["status"] = f"error:{exc}"
            print(f"  [{i:02d}/{len(rows)}] {r['jibun']}: {entry['status']} {entry['photo_date']}")
            report.append(entry)
        browser.close()

    (_SHOTS / "capture_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for e in report if e["status"] == "ok")
    print(f"[capture] {ok}/{len(report)}동 캡처 완료 → {_SHOTS.relative_to(_HERE.parents[2])}")


if __name__ == "__main__":
    run()

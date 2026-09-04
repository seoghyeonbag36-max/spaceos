"""배포 완료를 기다렸다가 **프로덕션에서** 12거점을 실측 검증한다 (2026-09-04).

## 왜 무인인가

`git push origin main` 이후 남은 것은 GitHub Actions(테스트→빌드→배포→검증)와
그 결과를 프로덕션에서 확인하는 일뿐이다. 사람이 지켜볼 필요가 없고, 덮개를 닫아도
되는 작업이다(GUI 가 필요한 자리는 push·브라우저 검증·외부 로그인 셋뿐인데 여기엔
없다). 다만 **노트북이 자면 멈추므로** keep_awake.ps1 로 감싸 띄운다.

## 왜 CI 초록만으로 끝내지 않는가

CI 검증 단계는 `/health` 200 과 분석 API 의 `vacancy_source:"gold"` 를 본다. 그건
"배포가 됐고 gold 를 읽는다"까지다. 이번 변경의 핵심은 **서울 2차 12거점이 네 트랙
전부에서 응답하는가**이고, 그건 거점을 지정해 물어봐야 안다 — 이 저장소가 두 번
당한 양식이 "데이터가 빠졌는데 화면은 멀쩡해 보인다"이다.

그래서 12거점 각각에 대해 넷을 확인한다:
  · 목록      거점이 `/commercial-districts` 에 있는가
  · Page      `/heatmap/buildings` 가 실데이터를 내는가(features 수 — 8건이면 샘플 폴백)
              + `/heatmap/vacancy` 의 `vacancy_source` 가 `gold` 인가(합성 폴백 아님)
  · Posting   `/commercial-districts/{id}/postings` 가 유닛을 내는가
              (09-04 에 시드 54가 문지기라 비어 있던 자리)
  · Platform  `/commercial-districts/{id}/platform` 이 404 가 아닌가 — 정체성(수요신호·
              키워드)과 GNN 자리 제안을 한 응답으로 내므로 여기 하나로 두 산출물을 본다.
              `/ai/recommend-industry` 는 POST 라 무인 GET 검증에 맞지 않는다.

실행(무인):
  powershell -ExecutionPolicy Bypass -File scripts/keep_awake.ps1 ^
    -Command "python -u scripts/watch_deploy_verify.py"

산출: reports/deploy_verify.json + 콘솔 로그
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "deploy_verify.json"
ORIGIN = "https://spaceos-twin.web.app"
BASE = f"{ORIGIN}/api/v1"
# ⚠ `/health` 는 **앱 루트**다(main.py `@app.get("/health")`) — `/api/v1/health` 가
#   아니다. docs/deploy-cloud-run.md 와 deploy skill 이 `/api/v1/health` 로 적어 두어
#   그대로 쟀다가 404 를 '배포 실패'로 읽을 뻔했다(2026-09-04). 문서도 같이 고쳤다.
HEALTH = f"{ORIGIN}/health"

BATCH2 = ["miasageori", "suyu", "bulgwang", "yeonsinnae", "hwagok", "kkachisan",
          "mokdong-yc", "sanggye", "sangbong", "oryudong", "doksan", "cheonho"]

POLL_S = 60
MAX_WAIT_S = 40 * 60          # 배포는 보통 10분 안쪽 — 40분이면 재시도까지 넉넉하다


def _get(path: str, timeout: int = 30) -> tuple[int, object]:
    """(status, body). 실패는 예외로 올리지 않고 상태코드 0 으로 돌려준다.

    `path` 가 http 로 시작하면 절대 URL 로 본다(루트의 `/health` 용).
    """
    url = path if path.startswith("http") else f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "spaceos-deploy-verify"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, raw[:300]
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:                       # noqa: BLE001 — 네트워크 전반
        return 0, str(e)[:200]


def wait_for_ci() -> dict:
    """main 의 최신 워크플로가 끝날 때까지 기다린다. gh 가 없으면 건너뛴다."""
    t0 = time.time()
    last = ""
    while True:
        try:
            r = subprocess.run(
                ["gh", "run", "list", "--branch", "main", "--limit", "3",
                 "--json", "databaseId,status,conclusion,displayTitle"],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
            runs = json.loads(r.stdout or "[]")
        except Exception as e:                   # noqa: BLE001
            return {"why": f"gh 실행 불가 — CI 대기를 건너뛴다 ({e})", "runs": []}

        live = [x for x in runs if x["status"] in ("queued", "in_progress")]
        cur = " · ".join(f"{x['databaseId']}:{x['status']}{x['conclusion'] or ''}" for x in runs)
        if cur != last:
            print(f"[ci] {cur} — {datetime.now():%H:%M:%S}", flush=True)
            last = cur
        if not live:
            return {"why": "완료", "waited_s": round(time.time() - t0), "runs": runs}
        if time.time() - t0 > MAX_WAIT_S:
            return {"why": f"{MAX_WAIT_S // 60}분 대기 초과", "waited_s": round(time.time() - t0),
                    "runs": runs}
        time.sleep(POLL_S)


def verify() -> dict:
    rec: dict = {"base": BASE, "checked_at": datetime.now().isoformat(timespec="seconds")}

    st, health = _get(HEALTH)
    rec["health"] = {"status": st, "body": health}
    print(f"[prod] {HEALTH} → {st}", flush=True)

    st, dis = _get("/commercial-districts")
    ids: set[str] = set()
    if isinstance(dis, list):
        ids = {str(d.get("id")) for d in dis if isinstance(d, dict)}
    elif isinstance(dis, dict):
        rows = dis.get("districts") or dis.get("items") or []
        ids = {str(d.get("id")) for d in rows if isinstance(d, dict)}
    rec["districts"] = {"status": st, "count": len(ids),
                        "batch2_present": sorted(ids & set(BATCH2))}
    print(f"[prod] /commercial-districts → {st} · 거점 {len(ids)} · "
          f"batch2 {len(ids & set(BATCH2))}/12", flush=True)

    hubs: dict[str, dict] = {}
    for slug in BATCH2:
        h: dict = {}
        st, body = _get(f"/heatmap/buildings?district={slug}")
        feats = body.get("features") if isinstance(body, dict) else None
        h["page"] = {"status": st,
                     "features": len(feats) if isinstance(feats, list) else None}
        # `vacancy_source` 는 `/heatmap/buildings` 에 없다 — 그 응답의 키는
        # type·district·features 뿐이다. 합성/실측을 밝히는 것은 `/heatmap/vacancy` 다
        # (services/districts 가 gold 면 "gold", 폴백이면 "synthetic" 을 얹는다).
        stv, vac = _get(f"/heatmap/vacancy?district={slug}")
        h["vacancy"] = {"status": stv,
                        "source": vac.get("vacancy_source") if isinstance(vac, dict) else None,
                        "cells": len(vac.get("cells") or []) if isinstance(vac, dict) else None}

        st, body = _get(f"/commercial-districts/{slug}/postings")
        n = None
        if isinstance(body, list):
            n = len(body)
        elif isinstance(body, dict):
            n = len(body.get("postings") or body.get("units") or [])
        h["posting"] = {"status": st, "units": n}

        st, _ = _get(f"/commercial-districts/{slug}/platform")
        h["platform"] = {"status": st}

        hubs[slug] = h
        print(f"[prod] {slug:12s} page={h['page']['status']}/{h['page']['features']} "
              f"· vac={h['vacancy']['source']} · "
              f"posting={h['posting']['status']}/{h['posting']['units']} "
              f"· platform={h['platform']['status']}", flush=True)
    rec["hubs"] = hubs

    # 판정 — 셋 다 만족해야 통과로 본다. 하나라도 어긋나면 그대로 남긴다(고치지 않는다).
    bad: list[str] = []
    if rec["health"]["status"] != 200:
        bad.append("health")
    if len(rec["districts"]["batch2_present"]) != 12:
        bad.append("districts")
    for slug, h in hubs.items():
        if h["page"]["status"] != 200 or not h["page"]["features"]:
            bad.append(f"{slug}:page")
        if h["vacancy"]["status"] != 200 or h["vacancy"]["source"] != "gold":
            bad.append(f"{slug}:vacancy_source={h['vacancy']['source']}")
        if h["posting"]["status"] != 200 or not h["posting"]["units"]:
            bad.append(f"{slug}:posting")
        if h["platform"]["status"] != 200:
            bad.append(f"{slug}:platform")
    rec["failures"] = bad
    rec["verdict"] = "통과" if not bad else f"미달 {len(bad)}건"
    return rec


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rec = {"started": datetime.now().isoformat(timespec="seconds")}
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    rec["ci"] = wait_for_ci()
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    # 배포 직후에는 리비전 전환이 남아 있을 수 있다 — 한 번 쉬고 잰다.
    time.sleep(30)
    rec["verify"] = verify()
    rec["finished"] = datetime.now().isoformat(timespec="seconds")
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[verify] {rec['verify']['verdict']} → {OUT.relative_to(ROOT)}", flush=True)
    return 0 if not rec["verify"]["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())

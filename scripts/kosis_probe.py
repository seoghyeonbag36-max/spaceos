"""[Posting] KOSIS 통계표 탐색 — 원가율·인건비 소스가 실제로 쓸 수 있는지 확인한다.

## 왜 수집기가 아니라 탐색기인가

3-Tier 비용 모델에 넣을 **원가율**의 후보는 통계청 서비스업조사/경제총조사의
영업비용 구조다. 그런데 두 가지를 아직 모른다:

1. 그 통계가 **음식점업을 어느 수준까지 세분**해 공표하는가 (tier↔업종 대표군이
   일식·양식·중식 / 한식·분식·치킨·호프 / 커피·패스트푸드·제과 로 갈리므로,
   최소한 이 정도 세분류가 있어야 계수로 내릴 수 있다).
2. 영업비용을 **항목별로**(급여·원재료비·임차료…) 주는가, 총액만 주는가.

KOSIS statHtml 은 SSO 게이트라 브라우저 없이는 확인이 안 됐다(2026-08-22). 그래서
응답 구조를 모르는 채로 수집기를 쓰면 **가정 위에 파서를 얹는 꼴**이 된다. 먼저
목록을 열어 보고, 쓸 수 있다고 확인된 다음에 수집기를 만든다.

## 쓰는 법

    # 1) https://kosis.kr 회원가입 → 로그인 → [공유서비스] → OPEN API 인증키 신청
    #    (자동승인). 발급된 키를 data/.env 에 넣는다:
    #    KOSIS_API_KEY=발급받은키
    # 2) 목록에서 후보 통계표를 찾는다
    python scripts/kosis_probe.py search 서비스업조사
    python scripts/kosis_probe.py search 경제총조사
    # 3) 후보 통계표의 분류·항목 구조를 본다 (여기서 세분류 깊이와 비용 항목을 확인)
    python scripts/kosis_probe.py meta <orgId> <tblId>
    # 4) 실제 값을 몇 줄 뽑아 본다
    python scripts/kosis_probe.py data <orgId> <tblId>

## 확인된 것 (2026-08-22)

두 엔드포인트 모두 살아 있고 **막는 것은 키뿐**이다 — 키 없이 부르면
`{"err":"11","errMsg":"유효하지않은 인증KEY입니다."}` 가 온다. 즉 발급만 되면 바로 돈다.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ENV = _ROOT / "data" / ".env"

LIST_URL = "https://kosis.kr/openapi/statisticsList.do"
DATA_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
META_URL = "https://kosis.kr/openapi/statisticsData.do"
_UA = {"User-Agent": "Mozilla/5.0 (SpaceOS kosis-probe)"}


def _key() -> str:
    if not _ENV.exists():
        raise SystemExit(f"{_ENV} 없음")
    for line in _ENV.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("KOSIS_API_KEY="):
            v = line.split("=", 1)[1].strip()
            if v:
                return v
    raise SystemExit(
        "data/.env 에 KOSIS_API_KEY 가 비어 있다.\n"
        "  https://kosis.kr 회원가입 → 로그인 → 공유서비스 → OPEN API 인증키 신청(자동승인)\n"
        "  발급된 키를 data/.env 의 KOSIS_API_KEY= 뒤에 붙인다.")


def _get(url: str, **params) -> object:
    params["apiKey"] = _key()
    params.setdefault("format", "json")
    params.setdefault("jsonVD", "Y")
    q = f"{url}?{urllib.parse.urlencode(params)}"
    raw = urllib.request.urlopen(
        urllib.request.Request(q, headers=_UA), timeout=40).read()
    body = json.loads(raw.decode("utf-8", errors="replace"))
    if isinstance(body, dict) and body.get("err"):
        raise SystemExit(f"KOSIS 오류 {body['err']}: {body.get('errMsg')}")
    return body


def _walk(parent: str, depth: int, needle: str, seen: set, out: list) -> None:
    """통계목록 트리를 훑어 이름에 needle 이 든 통계표를 모은다.

    KOSIS 목록은 대주제→중주제→통계표 계층이라 한 번의 호출로는 안 나온다.
    깊이 제한을 두는 이유는 전체 트리가 1,000여 통계에 달해서다.
    """
    if depth > 3:
        return
    try:
        rows = _get(LIST_URL, method="getList", vwCd="MT_ZTITLE",
                    parentListId=parent)
    except SystemExit:
        raise
    except Exception:
        return
    if not isinstance(rows, list):
        return
    for r in rows:
        name = r.get("LIST_NM") or r.get("TBL_NM") or ""
        tbl = r.get("TBL_ID")
        lid = r.get("LIST_ID")
        if tbl and needle in name and tbl not in seen:
            seen.add(tbl)
            out.append((r.get("ORG_ID"), tbl, name))
        if lid and lid not in seen:
            seen.add(lid)
            if needle in name or depth < 2:
                _walk(lid, depth + 1, needle, seen, out)


def cmd_search(needle: str) -> None:
    out: list = []
    _walk("", 0, needle, set(), out)
    if not out:
        print(f"'{needle}' 로 찾은 통계표 없음 — 다른 낱말로 시도하거나 "
              f"kosis.kr 통합검색에서 tblId 를 직접 확인할 것")
        return
    print(f"'{needle}' 통계표 {len(out)}건")
    for org, tbl, nm in out:
        print(f"  orgId={org:6s} tblId={tbl:22s} {nm}")


def cmd_meta(org: str, tbl: str) -> None:
    """통계표의 분류(objL*)·항목(itm) 구조 — 세분류 깊이와 비용 항목을 여기서 본다."""
    for kind in ("ITM", "OBJ"):
        try:
            rows = _get(META_URL, method="getMeta", orgId=org, tblId=tbl, type=kind)
        except SystemExit as e:
            print(f"[{kind}] {e}")
            continue
        print(f"\n=== {kind} ({len(rows) if isinstance(rows, list) else '?'}건) ===")
        for r in (rows or [])[:60]:
            print("  " + " · ".join(f"{k}={v}" for k, v in r.items() if v))


def cmd_data(org: str, tbl: str) -> None:
    rows = _get(DATA_URL, method="getList", orgId=org, tblId=tbl,
                prdSe="Y", newEstPrdCnt="1")
    rows = rows if isinstance(rows, list) else [rows]
    print(f"{len(rows)}행 — 앞 15행")
    for r in rows[:15]:
        print("  " + json.dumps(r, ensure_ascii=False))


def main() -> None:
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "search" and len(a) == 2:
        cmd_search(a[1])
    elif a[0] == "meta" and len(a) == 3:
        cmd_meta(a[1], a[2])
    elif a[0] == "data" and len(a) == 3:
        cmd_data(a[1], a[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

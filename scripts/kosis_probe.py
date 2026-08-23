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
import time
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


# KOSIS 오류코드 30 = "데이터가 존재하지 않습니다". 목록 트리를 훑을 때 **잎 노드는
# 반드시 이걸 낸다** — 자식이 없다는 뜻이지 실패가 아니다. 2026-08-23 이전에는 이걸
# 치명 오류로 올려서 첫 잎에서 탐색 전체가 죽었다(루트 호출은 멀쩡히 30건을 준다).
_ERR_EMPTY = "30"
# 오류코드 40 = "1분간 호출가능건수(200건) 초과". 트리 순회는 호출이 수백 건이라
# 반드시 걸린다(2026-08-23 실측). 한도는 **분당**이므로 기다리면 풀린다.
_ERR_RATE = "40"
_RATE_MIN_GAP_S = 0.32      # 200건/분 = 0.3초 간격. 조금 여유를 둔다.
_RATE_BACKOFF_S = 62        # 걸렸을 때 창이 넘어갈 때까지

_last_call = 0.0


def _get(url: str, **params) -> object:
    global _last_call
    params["apiKey"] = _key()
    params.setdefault("format", "json")
    params.setdefault("jsonVD", "Y")
    q = f"{url}?{urllib.parse.urlencode(params)}"
    for attempt in range(3):
        gap = time.monotonic() - _last_call
        if gap < _RATE_MIN_GAP_S:
            time.sleep(_RATE_MIN_GAP_S - gap)
        _last_call = time.monotonic()
        raw = urllib.request.urlopen(
            urllib.request.Request(q, headers=_UA), timeout=40).read()
        body = json.loads(raw.decode("utf-8", errors="replace"))
        if not (isinstance(body, dict) and body.get("err")):
            return body
        err = str(body["err"])
        if err == _ERR_EMPTY:
            return []          # 빈 노드 — 순회를 계속한다
        if err == _ERR_RATE and attempt < 2:
            print(f"    [한도] 분당 200건 초과 — {_RATE_BACKOFF_S}초 대기 후 재시도",
                  file=sys.stderr, flush=True)
            time.sleep(_RATE_BACKOFF_S)
            continue
        raise SystemExit(f"KOSIS 오류 {err}: {body.get('errMsg')}")
    raise SystemExit("KOSIS 호출 한도를 계속 넘는다 — 잠시 뒤 다시 시도할 것")


def _walk(parent: str, depth: int, needle: str, seen: set, out: list,
          under: str | None = None) -> None:
    """통계목록 트리를 훑어 needle 에 걸리는 통계표를 모은다.

    KOSIS 목록은 대주제→조사명→통계표 계층이라 한 번의 호출로는 안 나온다.
    깊이 제한을 두는 이유는 전체 트리가 1,000여 통계에 달해서다.

    `under` 는 **이미 이름이 걸린 상위 분류**다. 이게 필요한 이유: 통계표 이름에는
    조사명이 안 들어간다("서비스업조사" 아래의 표는 "시도별 …" 식이다). 그래서
    통계표 이름만 보고 매칭하면 조사를 찾아 놓고도 표를 하나도 못 담는다
    (2026-08-23 실측 — 이것과 err 30 두 개가 겹쳐 탐색이 항상 빈손이었다).
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
        hit = needle in name
        if tbl and (hit or under) and tbl not in seen:
            seen.add(tbl)
            out.append((r.get("ORG_ID"), tbl, name, under or name))
        if lid and lid not in seen:
            seen.add(lid)
            # 이름이 걸린 분류 아래는 전부 담고, 아직 못 걸렸으면 두 단계까지 더 판다.
            if under or hit:
                _walk(lid, depth + 1, needle, seen, out, under or name)
            elif depth < 2:
                _walk(lid, depth + 1, needle, seen, out, None)


def cmd_roots() -> None:
    """대주제 30건. 여기서 LIST_ID 를 골라 `search <낱말> <루트>` 로 범위를 좁힌다.

    전체 순회는 호출이 수백 건이라 분당 한도(200)에 걸려 몇 분씩 기다린다.
    찾는 조사가 어느 주제인지 알면 십수 건으로 끝난다.
    """
    rows = _get(LIST_URL, method="getList", vwCd="MT_ZTITLE", parentListId="")
    for r in rows if isinstance(rows, list) else []:
        print(f"  {r.get('LIST_ID'):8s} {r.get('LIST_NM')}")


def cmd_search(needle: str, root: str = "") -> None:
    out: list = []
    _walk(root, 0, needle, set(), out)
    if not out:
        print(f"'{needle}' 로 찾은 통계표 없음 — 다른 낱말로 시도하거나 "
              f"kosis.kr 통합검색에서 tblId 를 직접 확인할 것")
        return
    print(f"'{needle}' 통계표 {len(out)}건")
    for org, tbl, nm, cat in out:
        print(f"  orgId={org or '?':6s} tblId={tbl:22s} [{cat}] {nm}")


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
    if a[0] == "roots" and len(a) == 1:
        cmd_roots()
    elif a[0] == "search" and len(a) in (2, 3):
        cmd_search(a[1], a[2] if len(a) == 3 else "")
    elif a[0] == "meta" and len(a) == 3:
        cmd_meta(a[1], a[2])
    elif a[0] == "data" and len(a) == 3:
        cmd_data(a[1], a[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

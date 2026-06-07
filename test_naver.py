"""네이버 API 키 진단 (자체완결). 실행: py test_naver.py

data/.env 의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 로 두 엔드포인트를 호출해
HTTP 상태코드와 네이버가 돌려주는 errorCode/errorMessage 를 그대로 보여준다.
※ Secret 은 화면에 출력하지 않는다(길이만 표시).
"""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ENV = Path(__file__).resolve().parent / "data" / ".env"


def load_env():
    out = {}
    if not ENV.exists():
        print(f"[!] {ENV} 없음")
        return out
    raw = ENV.read_bytes()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc); break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def call(url, headers, body=None):
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=headers, method="POST" if body else "GET")
    try:
        with urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, f"연결오류: {e}"


def main():
    env = load_env()
    cid = env.get("NAVER_CLIENT_ID", "")
    sec = env.get("NAVER_CLIENT_SECRET", "")
    print("== 키 확인 ==")
    print(f"  NAVER_CLIENT_ID   : '{cid}' (길이 {len(cid)})")
    print(f"  NAVER_CLIENT_SECRET: 길이 {len(sec)} (보안상 값 숨김)")
    print(f"  ID에 공백 포함?     : {'예!' if cid != cid.strip() or ' ' in cid else '아니오'}")
    if not cid or not sec:
        print("\n[!] 키가 비어있음 — data/.env 의 NAVER_CLIENT_ID/SECRET 확인")
        return

    h = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec, "Content-Type": "application/json"}

    print("\n== ① 데이터랩(검색어트렌드) 테스트 ==")
    body = {"startDate": "2025-01-01", "endDate": "2025-01-31", "timeUnit": "month",
            "keywordGroups": [{"groupName": "강남", "keywords": ["강남맛집"]}]}
    s, t = call("https://openapi.naver.com/v1/datalab/search", h, body)
    print(f"  HTTP {s}\n  응답: {t[:400]}")

    print("\n== ② 검색(블로그) 테스트 ==")
    h2 = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}
    s2, t2 = call("https://openapi.naver.com/v1/search/blog.json?query=%EA%B0%95%EB%82%A8&display=1", h2)
    print(f"  HTTP {s2}\n  응답: {t2[:300]}")

    print("\n== 판정 ==")
    if s == 200:
        print("  데이터랩 200 OK → 키 정상! score 재실행하면 LIVE 전환됩니다.")
    else:
        print("  데이터랩 실패. 위 errorCode 로 원인 파악:")
        print("   024/028 = 인증실패(ID/Secret 틀림·뒤바뀜)")
        print("   기타/403 = 앱에 '데이터랩(검색어트렌드)' API 미등록 가능성")


if __name__ == "__main__":
    main()

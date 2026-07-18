# -*- coding: utf-8 -*-
"""SpaceOS API 키 일괄 점검 스크립트.

사용법 (repo 어디서 실행해도 됨):
    python scripts/check_api_keys.py

각 .env의 키로 해당 API를 1회씩 실제 호출해 PASS/FAIL을 판정한다.
- 점검 대상: data/.env + apps/backend/.env (프론트 지도 키는 `npm run dev`로 확인)
- 키 값 자체는 절대 출력하지 않는다.
- .env가 없으면 .env.example을 복사해 값을 채우라고 안내한다.

온보딩 절차는 docs/next-steps-after-keys.md, 키 발급처는 docs/api-key-checklist.md 참조.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DATA_ENV = ROOT / "data" / ".env"
BACKEND_ENV = ROOT / "apps" / "backend" / ".env"


def load_env(path: Path) -> dict:
    if not path.exists():
        example = path.with_name(".env.example")
        print(f"[!] {path.relative_to(ROOT)} 없음 — {example.relative_to(ROOT)} 를 .env 로 복사한 뒤 키를 채우세요.")
        return {}
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return env


def fetch(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:  # 네트워크 오류 등
        return None, f"{type(e).__name__}: {e}"


results = []


def report(name, ok, detail):
    results.append((name, ok, detail))
    mark = {True: "PASS", False: "FAIL", None: "WARN"}[ok]
    print(f"[{mark}] {name}: {detail}")


data = load_env(DATA_ENV)
backend = load_env(BACKEND_ENV)

# ── 1. 서울 열린데이터광장 (생활인구) ──────────────────────────────
key = data.get("SEOUL_OPENAPI_KEY", "")
svc = data.get("SEOUL_LIVING_POP_SERVICE", "SPOP_LOCAL_RESD_DONG")
if key:
    status, body = fetch(f"http://openapi.seoul.go.kr:8088/{key}/json/{svc}/1/1/")
    try:
        j = json.loads(body)
        if svc in j:
            code = j[svc].get("RESULT", {}).get("CODE", "?")
            report("서울 열린데이터광장", True, f"정상 응답 (RESULT={code}, 서비스={svc})")
        else:
            code = j.get("RESULT", {}).get("CODE", "?")
            msg = j.get("RESULT", {}).get("MESSAGE", "")[:60]
            # INFO-100 = 인증키 오류, INFO-2xx = 키는 유효(데이터 없음 등)
            ok = False if code == "INFO-100" else (True if code.startswith("INFO-2") else None)
            report("서울 열린데이터광장", ok, f"{code} {msg}")
    except Exception:
        report("서울 열린데이터광장", None, f"HTTP {status}, 응답 파싱 실패: {body[:100]}")
else:
    report("서울 열린데이터광장", False, "SEOUL_OPENAPI_KEY 미설정")

# ── 2. 공공데이터포털 (상가정보 — 계정 공용키) ─────────────────────
key = data.get("DATA_GO_KR_SERVICE_KEY", "")
if key:
    url = ("https://apis.data.go.kr/B553077/api/open/sdsc2/largeUpjongList"
           f"?serviceKey={urllib.parse.quote(key)}&type=json")
    status, body = fetch(url)
    if status == 200 and '"header"' in body:
        try:
            j = json.loads(body)
            rc = j.get("header", {}).get("resultCode", "?")
            report("공공데이터포털(상가정보)", rc == "00", f"resultCode={rc}")
        except Exception:
            report("공공데이터포털(상가정보)", None, f"HTTP {status}: {body[:120]}")
    elif "SERVICE_KEY_IS_NOT_REGISTERED" in body or "SERVICE ERROR" in body:
        report("공공데이터포털(상가정보)", False, f"인증 오류 — 활용신청/키 확인 필요: {body[:120]}")
    else:
        report("공공데이터포털(상가정보)", None, f"HTTP {status}: {body[:150]}")
else:
    report("공공데이터포털(상가정보)", False, "DATA_GO_KR_SERVICE_KEY 미설정")

# ── 3. 한국부동산원 R-ONE ─────────────────────────────────────────
key = data.get("REB_RONE_API_KEY", "")
if key:
    url = ("https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
           f"?KEY={key}&Type=json&pIndex=1&pSize=1&STATBL_ID=A_2024_00045&DTACYCLE_CD=QY")
    status, body = fetch(url)
    if status == 200:
        low = body[:400]
        if "INFO-100" in low or "인증키" in low:
            report("한국부동산원 R-ONE", False, f"인증키 오류: {low[:120]}")
        elif "SttsApiTblData" in low or "INFO-200" in low or "CODE" in low:
            report("한국부동산원 R-ONE", True, "키 인증 통과")
        else:
            report("한국부동산원 R-ONE", None, f"응답 확인 필요: {low[:150]}")
    else:
        report("한국부동산원 R-ONE", None, f"HTTP {status}: {str(body)[:120]}")
else:
    report("한국부동산원 R-ONE", None, "미설정 (data.go.kr 공용키 경로면 생략 가능)")

# ── 4. 통계청 SGIS (accessToken 발급) ─────────────────────────────
ck, cs = data.get("SGIS_CONSUMER_KEY", ""), data.get("SGIS_CONSUMER_SECRET", "")
if ck and cs:
    status, body = fetch(
        "https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json"
        f"?consumer_key={ck}&consumer_secret={cs}")
    try:
        j = json.loads(body)
        ok = j.get("errCd") == 0
        report("통계청 SGIS", ok,
               "accessToken 발급 성공" if ok else f"errCd={j.get('errCd')} {j.get('errMsg', '')}")
    except Exception:
        report("통계청 SGIS", None, f"HTTP {status}: {body[:120]}")
else:
    report("통계청 SGIS", False, "SGIS_CONSUMER_KEY/SECRET 미설정")

# ── 5. 네이버 개발자센터 (지역 검색) ──────────────────────────────
nid, nsec = data.get("NAVER_CLIENT_ID", ""), data.get("NAVER_CLIENT_SECRET", "")
if nid and nsec:
    q = urllib.parse.quote("가로수길")
    status, body = fetch(
        f"https://openapi.naver.com/v1/search/local.json?query={q}&display=1",
        headers={"X-Naver-Client-Id": nid, "X-Naver-Client-Secret": nsec})
    report("네이버 개발자센터(검색)", status == 200,
           "지역검색 호출 성공" if status == 200 else f"HTTP {status}: {body[:120]}")
else:
    report("네이버 개발자센터(검색)", False, "NAVER_CLIENT_ID/SECRET 미설정")

# ── 6. V-World (장소 검색 — 등록 도메인 Referer 포함) ──────────────
key = data.get("VWORLD_API_KEY", "")
if key:
    q = urllib.parse.quote("가로수길")
    status, body = fetch(
        "https://api.vworld.kr/req/search?service=search&request=search&version=2.0"
        f"&query={q}&type=place&size=1&format=json&key={key}",
        headers={"Referer": "http://localhost:5173"})
    try:
        j = json.loads(body)
        st = j.get("response", {}).get("status", "?")
        err = j.get("response", {}).get("error", {})
        report("V-World", st == "OK",
               f"status={st}" + ("" if st == "OK" else f" ({err.get('text', '')[:80]} — 도메인 등록 확인)"))
    except Exception:
        report("V-World", None, f"HTTP {status}: {body[:120]}")
else:
    report("V-World", False, "VWORLD_API_KEY 미설정")

# ── 7. 카카오 로컬 ───────────────────────────────────────────────
key = data.get("KAKAO_REST_API_KEY", "")
if key:
    q = urllib.parse.quote("가로수길")
    status, body = fetch(
        f"https://dapi.kakao.com/v2/local/search/keyword.json?query={q}&size=1",
        headers={"Authorization": f"KakaoAK {key}"})
    report("카카오 로컬", status == 200,
           "키워드 검색 성공" if status == 200 else f"HTTP {status}: {body[:120]}")
else:
    report("카카오 로컬", False, "KAKAO_REST_API_KEY 미설정")

# ── 8. Anthropic Claude API (모델 목록 조회 — 과금 없는 인증 확인) ──
key = backend.get("LLM_API_KEY", "")
if key and key.startswith("sk-ant"):
    status, body = fetch(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
    if status == 200:
        try:
            n = len(json.loads(body).get("data", []))
            report("Anthropic Claude API", True, f"인증 성공 (사용 가능 모델 {n}개)")
        except Exception:
            report("Anthropic Claude API", True, "인증 성공")
    elif status == 401:
        report("Anthropic Claude API", False, "인증 실패 — 키가 유효하지 않음")
    else:
        report("Anthropic Claude API", None, f"HTTP {status}: {body[:120]}")
else:
    report("Anthropic Claude API", False, "LLM_API_KEY 미설정 또는 형식 오류")

# ── 9. NCP Maps (백엔드 Geocoding) ───────────────────────────────
kid = backend.get("NAVER_MAPS_KEY_ID", "")
sec = backend.get("NAVER_MAPS_CLIENT_SECRET", "")
if kid and sec and "PUT_YOUR" not in sec:
    q = urllib.parse.quote("강남구 가로수길 5")
    status, body = fetch(
        f"https://maps.apigw.ntruss.com/map-geocode/v2/geocode?query={q}",
        headers={"x-ncp-apigw-api-key-id": kid, "x-ncp-apigw-api-key": sec})
    try:
        j = json.loads(body)
        n = len(j.get("addresses", []))
        ok = status == 200 and j.get("status") == "OK"
        report("NCP Maps(Geocoding)", ok,
               f"지오코딩 성공 ({n}건)" if ok else f"HTTP {status}: {body[:120]}")
    except Exception:
        report("NCP Maps(Geocoding)", None, f"HTTP {status}: {body[:120]}")
else:
    report("NCP Maps(Geocoding)", False, "NAVER_MAPS_CLIENT_SECRET 미설정")

print()
n_pass = sum(1 for _, ok, _ in results if ok is True)
n_fail = sum(1 for _, ok, _ in results if ok is False)
n_warn = sum(1 for _, ok, _ in results if ok is None)
print(f"요약: PASS {n_pass} / FAIL {n_fail} / 확인필요 {n_warn}")
print("※ 프론트 지도 키(VITE_NAVER_MAPS_KEY_ID)는 `cd apps/frontend && npm run dev` 후 지도 렌더로 확인.")
sys.exit(1 if n_fail else 0)

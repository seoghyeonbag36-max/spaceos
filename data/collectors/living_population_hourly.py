"""[Page] 행정동 **시간대별** 생활인구 수집기 — 24시간 축의 재료.

## 왜 새 수집기인가

기존 `living_population.py` 는 같은 출처를 쓰지만 **구(區) 단위 25구 상대 정규화**를
돌려준다(`config.SCORE_BANDS["FOOT"]` 투입용). 거점 점수용이라 시간 축이 없다.
Page 히트맵의 시간 슬라이더가 필요한 것은 **행정동 × 24시간** 이고, 그건 이 데이터셋의
원본 입도다 — 접지 말고 그대로 받아야 한다.

## 프로브로 확정한 사실 (2026-08-24)

- 서비스명 `SPOP_LOCAL_RESD_DONG`, 총 630,988행.
- 행은 `STDR_DE_ID`(날짜) × `TMZON_PD_SE`(**00~23시**) × `ADSTRD_CODE_SE`(행정동) 이고
  값은 `TOT_LVPOP_CO`(총 생활인구) + 성·연령 28열.
- **날짜 경로 필터가 먹는다**: `/{start}/{end}/{YYYYMMDD}/` → 하루치 10,176행
  (424동 × 24시간). 전량 631콜을 받을 이유가 없다.
- **행정동 필터는 안 먹는다**: 날짜 뒤에 코드를 더 붙이면 `INFO-200`(해당 데이터 없음)이
  돌아온다. 그래서 하루치를 받아 **로컬에서** 거점 행정동만 남긴다.
- 보유 날짜는 63개 — `20260601~20260731` 연속 61일 + `20250918` · `20230929`.
  요일 분포가 평일 47 / 주말 16 이라 평일·주말 프로파일을 따로 낼 표본이 된다.

## 어느 행정동을 남기나

`silver/hub_adong.json`(= `build_hub_adong` 산출물)에 있는 코드만 남긴다. 424동 중
거점에 걸리는 것은 일부이므로 저장량이 10분의 1 수준으로 줄고, **거점에 못 붙는 동을
받아 두는 것은 Bronze 를 키우기만 한다.** 매핑이 없으면 실행을 거부한다 — 전량을
받아 놓고 나중에 못 붙이는 것이 최악이다.

⚠ 필터는 **행 단위**다(`seoul_trdar._filter_garosu` 와 같은 방식). 열은 원본 32개를
  그대로 둔다 — Bronze 는 무가공이 원칙이고, 성·연령 열은 Program 수요신호가 쓴다.

## 재실행 안전

날짜별로 파일이 갈리므로(`bronze/seoul/{날짜}/living_population_hourly.json`) 이미 받은
날짜는 건너뛴다. 무인 실행 중 끊겨도 다시 부르면 남은 날짜만 받는다.

실행:
  python -m data.collectors.living_population_hourly              # 최근 28일(4주)
  python -m data.collectors.living_population_hourly --days 61    # 6~7월 전체
  python -m data.collectors.living_population_hourly --force      # 이미 받은 날짜도 다시
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import time

try:  # 선택 의존성 — 키가 없으면 애초에 실행하지 않는다
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import BRONZE, load_env, save_json
from data.pipelines.build_hub_adong import load as load_hub_adong

SERVICE = "SPOP_LOCAL_RESD_DONG"
SLUG = "seoul"                      # 서울 전역 데이터 — 거점별로 쪼개지 않는다
FILENAME = "living_population_hourly.json"
_PAGE = 1000                        # 서울 열린데이터광장 1회 최대 행수
_SLEEP_S = 0.05
_RETRIES = 4

# 하루치 행수(424동 × 24시간). 날짜 목록을 훑을 때 offset 보폭으로만 쓴다 —
# 동 수가 해에 따라 바뀌므로 정확한 값이 아니라 **근사 보폭**이다.
_DAY_STRIDE = 10176


def _url(key: str, start: int, end: int, extra: str = "") -> str:
    return f"http://openapi.seoul.go.kr:8088/{key}/json/{SERVICE}/{start}/{end}{extra}"


def _get(key: str, start: int, end: int, extra: str = "") -> tuple[list[dict], int]:
    """단일 페이지. (rows, list_total_count). INFO-200(데이터 없음)은 빈 결과로 본다."""
    last: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            resp = requests.get(_url(key, start, end, extra), timeout=40)
            resp.raise_for_status()
            body = resp.json()
            if SERVICE not in body:
                code = (body.get("RESULT") or {}).get("CODE", "")
                if code == "INFO-200":          # 해당 데이터 없음 — 오류가 아니다
                    return [], 0
                msg = (body.get("RESULT") or {}).get("MESSAGE", str(body)[:200])
                raise RuntimeError(f"{SERVICE}: {code} {msg}")
            payload = body[SERVICE]
            code = (payload.get("RESULT") or {}).get("CODE", "")
            if code == "INFO-200":
                return [], 0
            return payload.get("row") or [], int(payload.get("list_total_count") or 0)
        except Exception as exc:                # 네트워크·일시 오류는 물러서서 재시도
            last = exc
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"{SERVICE} 페이지 {start}-{end} 실패: {last}")


def adong8(code: object) -> str:
    """행정동 코드를 서울 생활인구가 쓰는 **8자리**로 맞춘다.

    ⚠ 두 출처의 코드 체계가 다르다(2026-08-24 실측):
      - `build_hub_adong` 은 카카오 `coord2regioncode` 를 쓰므로 **10자리**
        행정표준코드다 — 예: 신사동 `1168051000`.
      - 서울 생활인구 `ADSTRD_CODE_SE` 는 **8자리**다 — 예: `11680510`.
        하루치 424개 코드 전부 8자리임을 확인했다.
      10자리는 8자리 + `"00"` 이라, 거점 3개 코드로 대조하니 셋 다 일치했다.

    이 정규화가 없으면 필터가 **한 행도 못 맞히면서 오류도 안 난다** — 날짜마다
    "0행 저장" 으로 조용히 끝난다. 그래서 예상 밖 모양은 그대로 돌려주고 호출부가
    경고할 수 있게 한다(멋대로 자르면 틀린 동에 붙는다).
    """
    s = str(code).strip()
    if len(s) == 10 and s.endswith("00"):
        return s[:8]
    return s


def hub_adong_codes() -> set[str]:
    """거점에 걸리는 행정동 코드 집합(8자리 정규화). 매핑이 없으면 빈 집합.

    ⚠ 파일을 직접 파싱하지 않는다. hub_adong.json 은 최상위에 `hubs` 를 두고 그 옆에
      주석용 키를 함께 싣기 때문에, 문서 전체를 순회하면 거점이 아닌 것까지 코드로
      집는다(2026-08-24 실측). 계약은 `build_hub_adong.load()` 한 곳에만 둔다 —
      `living_migration` · `build_page_migration` 도 같은 로더를 쓴다.
    """
    raw = [code for per_hub in load_hub_adong().values() for code in per_hub]
    out = {adong8(c) for c in raw}
    odd = sorted({str(c) for c in raw if len(adong8(c)) != 8})
    if odd:
        # 자릿수가 8 로 안 떨어지는 코드는 필터에서 조용히 0건이 된다 — 드러낸다.
        print(f"[livpop-h] 경고: 8자리로 정규화 안 되는 행정동 코드 {len(odd)}개 "
              f"— {odd[:5]}")
    return out


def available_dates(key: str, limit: int = 70) -> list[str]:
    """보유 날짜 목록(최신순). offset 을 하루치씩 뛰며 1행만 물어본다.

    전량을 받아 날짜를 세는 것보다 훨씬 싸다(70콜 × 1행). 데이터가 최신순으로
    정렬돼 있다는 관측(2026-08-24 프로브)에 기댄다 — 아니면 중복이 걸러지므로
    목록이 짧아질 뿐, 틀린 날짜가 들어오지는 않는다.
    """
    dates: list[str] = []
    _, total = _get(key, 1, 1)
    off = 1
    while off <= (total or 0) and len(dates) < limit:
        rows, _ = _get(key, off, off)
        if not rows:
            break
        ds = str(rows[0].get("STDR_DE_ID") or "")
        if ds and ds not in dates:
            dates.append(ds)
        off += _DAY_STRIDE
        time.sleep(_SLEEP_S)
    return dates


def _iso(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _already(yyyymmdd: str, codes: set[str]) -> bool:
    """이 날짜가 **현재 코드 집합으로** 이미 받아져 있는가.

    파일 존재만 보면 안 된다 — `hub_adong` 이 아직 일부 거점만 담고 있을 때 받은
    파일은 나머지 거점의 행정동이 빠져 있는데, 존재만 보고 건너뛰면 그 결손이
    영구화된다(2026-08-24 실제로 이 상태에 놓였다).

    행수로 판정한다: 한 동은 하루에 24시간 전부 나오므로 기대 행수는
    `len(codes) × 24` 다. 실제로 424동 × 24 = 10,176 이 하루치 총량과 맞았다.
    모자라면 다시 받는다 — 넘치면(코드가 줄었을 때) 굳이 다시 받지 않는다.
    """
    f = BRONZE / SLUG / _iso(yyyymmdd) / FILENAME
    if not f.exists():
        return False
    try:
        n = len(json.loads(f.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        return False
    return n >= len(codes) * 24


def collect_date(key: str, yyyymmdd: str, codes: set[str]) -> int:
    """하루치를 페이징으로 전부 받아 거점 행정동만 Bronze 에 남긴다. 반환: 저장 행수."""
    kept: list[dict] = []
    start, total = 1, None
    while True:
        rows, tot = _get(key, start, start + _PAGE - 1, f"/{yyyymmdd}/")
        if total is None:
            total = tot
        if not rows:
            break
        kept.extend(r for r in rows if adong8(r.get("ADSTRD_CODE_SE")) in codes)
        start += _PAGE
        if total and start > total:
            break
        time.sleep(_SLEEP_S)
    save_json(kept, SLUG, FILENAME, date=_iso(yyyymmdd))
    return len(kept)


def collect(days: int = 28, force: bool = False) -> dict[str, int]:
    """최근 `days` 개 날짜를 수집. 반환: 날짜 → 저장 행수."""
    key = os.getenv("SEOUL_OPENAPI_KEY")
    if not key or requests is None:
        print("[livpop-h] SEOUL_OPENAPI_KEY 미설정(또는 requests 없음) — 건너뜀")
        return {}

    codes = hub_adong_codes()
    if not codes:
        raise SystemExit(
            "[livpop-h] silver/hub_adong.json 이 없다(또는 비었다) — 먼저\n"
            "  python -m data.pipelines.build_hub_adong\n"
            "거점 행정동을 모르면 424동 전량을 받아 놓고도 거점에 못 붙인다.")
    print(f"[livpop-h] 거점 행정동 {len(codes)}개 · 최근 {days}일 대상")

    dates = available_dates(key)
    if not dates:
        print("[livpop-h] 날짜 목록을 못 얻었다 — 중단")
        return {}
    target = dates[:days]
    print(f"[livpop-h] 보유 날짜 {len(dates)}개 중 {target[-1]}~{target[0]} 수집")

    out: dict[str, int] = {}
    for ds in target:
        if not force and _already(ds, codes):
            print(f"  {_iso(ds)} 이미 있음 — 건너뜀")
            continue
        n = collect_date(key, ds, codes)
        wd = datetime.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8])).strftime("%a")
        out[ds] = n
        print(f"  {_iso(ds)}({wd}) {n}행")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=28,
                    help="최근 몇 개 날짜를 받을지. 기본 28(4주 — 평일 20 / 주말 8 로 "
                         "평일·주말 프로파일 표본이 균형을 이룬다)")
    ap.add_argument("--force", action="store_true",
                    help="이미 받은 날짜도 다시 받는다")
    a = ap.parse_args()
    load_env()
    res = collect(days=a.days, force=a.force)
    print(f"[livpop-h] 완료 — 새로 받은 날짜 {len(res)}개 · 총 {sum(res.values())}행")


if __name__ == "__main__":
    main()

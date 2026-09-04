"""[Page] 건축HUB 일일 쿼터 작업 프리플라이트 — 돌리기 전에 확인할 것 4종.

`/quota` 슬래시 커맨드가 부르는 스크립트다. 원래 커맨드 파일에 `python -c "..."` 로
임베드돼 있었는데, 이 프로젝트의 기본 셸이 PowerShell 이라 여러 줄 인라인 스니펫이
따옴표 파싱에서 깨졌다(2026-08-10). 셸 인용 문제를 없애려고 파일로 뺐다.

확인 항목:
  1. 쿼터가 실제로 열렸는가 — 로그가 아니라 1콜 프로브의 응답으로 판정한다
  2. 전원 — 배터리면 느려진다. 기전은 CPU가 아니라 무선 어댑터 절전(AC 0 / DC 2)이고
     이 작업은 네트워크 바운드라 정확히 거기서 아프다. 덮개를 닫으면 아예 언다
  3. 커밋 여유 — 1~2GB 면 회색 화면·무증상 크래시가 온다. 재부팅만 듣는다
  4. 잔여 — 전유부(대장) 미수집 거점과, 층별개요 **미시도** 동수.
     층별개요 잔여는 '미시도'와 '판정완료(상업층 0 확정)'로 갈라서 찍는다.
     붙여 쓸 명령줄에는 미시도가 있는 거점만 넣는다 — 잔여 동수로 고르면
     회수율 0 인 거점에 콜을 태운다(2026-08-19 에 672콜/22동으로 겪었다).

읽기만 한다. 프로브 1콜 말고는 아무것도 호출하지 않고 아무 파일도 쓰지 않는다.

실행: python -m scripts.quota_preflight        (저장소 루트 spaceos/ 에서)
      python scripts/quota_preflight.py
"""
from __future__ import annotations

import ctypes
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.collectors.common import load_env  # noqa: E402
from data.config.page_hubs import (  # noqa: E402
    ALL_HUBS,
    GYEONGGI_HUBS,
    HUBS,
    SEOUL_BATCH2_HUBS,
)

GOLD = ROOT / "data" / "gold"
BRONZE = ROOT / "data" / "bronze"
_EXPOS = "http://apis.data.go.kr/1613000/BldRgstHubService/getBrExposPubuseAreaInfo"

OK, WARN, BAD = "OK  ", "주의", "중단"

# 잔여는 **`ALL_HUBS` 로 센다.** 종전에는 `HUBS`(서울 코어 54)만 돌아서, 신규 배치로
# 등록된 거점은 대장이 0동이어도 잔여에 잡히지 않았다 — 2026-08-31 에 서울 2차 12 +
# 경기 13, **25거점이 미수집인데 "전유부 잔여 없음" 으로 찍혔다.** 08-30 에
# chain_status 가 같은 이유로 신규 배치를 "등록 안 됨" 으로 보고한 것과 같은 결함이다
# (배치 목록을 손으로 합치면 배치가 늘 때마다 틀린다). 단일 출처는 ALL_HUBS 다.
#
# 다만 **명령줄은 배치별로 갈라 찍는다** — 서울과 경기를 한 줄에 섞어 놓으면
# "경기는 빼고" 같은 지시를 그 줄 그대로는 실행할 수 없다.
_GROUPS: tuple[tuple[str, dict], ...] = (
    ("서울 코어", HUBS),
    ("서울 2차", SEOUL_BATCH2_HUBS),
    ("경기", GYEONGGI_HUBS),
)


def _paused() -> set[str]:
    """서빙 보류 도시의 거점 — **오늘 쿼터를 태울 대상에서 뺀다.**

    2026-09-03 에 경기(고양·파주) 서빙을 중단했고, 2026-09-05 에 수집도 멈추기로
    했다. 그런데 이 스크립트는 그 결정을 모른 채 경기 16거점 실행줄을 계속 찍고
    있었다 — 그 줄을 그대로 돌리면 **화면에 닿지 않을 데이터에 하루치 쿼터가 사라진다**
    (쿼터는 하루가 지나면 회수되지 않는다).

    판단은 `measured_pages.SERVED_CITIES` 한 곳에 있고 여기서 그것을 읽는다. 슬러그를
    손으로 적으면 재개할 때 고칠 곳이 둘이 되고, 그 중 하나는 잊힌다.

    판단을 못 읽으면 **빈 집합**을 돌려준다(아무것도 빼지 않는다). 못 읽은 것을
    '보류'로 단정하면 서울 잔여까지 조용히 사라져, 있는 일이 없는 것처럼 보인다.
    """
    backend = ROOT / "apps" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    try:
        from app.data.measured_pages import SERVED_CITIES
    except Exception:
        return set()
    return {slug for slug, hub in ALL_HUBS.items()
            if getattr(hub, "city", "seoul") not in SERVED_CITIES}


def check_quota() -> tuple[str, str]:
    """전유부 1콜 프로브. 429 면 아직 안 열린 것이므로 오늘 작업을 시작하지 않는다."""
    import os

    load_env()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not key:
        return BAD, "DATA_GO_KR_SERVICE_KEY 미설정 — .env 확인"
    try:
        import requests
    except ImportError:
        return BAD, "requests 미설치"

    # 압구정동 397 — 전유부가 **실제로 있는** 지번을 쓴다(totalCount>0 을 눈으로 확인함).
    # 빈 지번을 쓰면 0행 200 이 와서 '열렸지만 빈 응답' 과 구별이 안 된다.
    # bjdongCd 는 11000 이다 — 10300 으로 적으면 0행이 온다(2026-08-10 실측).
    params = {"serviceKey": key, "_type": "json", "numOfRows": 1, "pageNo": 1,
              "sigunguCd": "11680", "bjdongCd": "11000", "platGbCd": "0",
              "bun": "0397", "ji": "0000"}
    try:
        r = requests.get(_EXPOS, params=params, timeout=20)
    except Exception as e:  # noqa: BLE001
        return BAD, f"프로브 실패 — {type(e).__name__}: {e}"

    if r.status_code == 429:
        return BAD, "429 — 쿼터가 아직 안 열렸다. 오늘 작업을 시작하지 말 것"
    if r.status_code >= 500:
        return WARN, f"{r.status_code} — 건축HUB 서버 장애. 잠시 뒤 다시 볼 것"
    if r.status_code != 200:
        return BAD, f"HTTP {r.status_code} — {r.text[:120]}"
    try:
        head = r.json()["response"]["header"]
    except Exception:  # noqa: BLE001
        return WARN, f"비JSON 응답 — {r.text[:120]}"
    msg = head.get("resultMsg", "")
    if head.get("resultCode") not in ("00", "0"):
        return BAD, f"{head.get('resultCode')} {msg}"
    n = int(r.json()["response"]["body"].get("totalCount") or 0)
    if n == 0:
        return WARN, (f"{msg} 이지만 프로브 지번이 0행 — 쿼터는 열렸을 가능성이 높으나 "
                      "프로브 파라미터가 낡았을 수 있다(코드 주석 참조)")
    return OK, f"{msg} (프로브 지번 {n:,}행)"


def check_power() -> tuple[str, str]:
    """AC 연결 여부. Windows GetSystemPowerStatus(stdlib ctypes)로 읽는다."""
    if not sys.platform.startswith("win"):
        return OK, f"{sys.platform} — 전원 점검 건너뜀"

    class _S(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                    ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                    ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]

    st = _S()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st)):
        return WARN, "전원 상태를 읽지 못했다"
    pct = st.BatteryLifePercent
    pct_s = f"{pct}%" if pct != 255 else "?"
    if st.ACLineStatus == 1:
        return OK, f"AC 연결 (배터리 {pct_s})"
    return WARN, (f"배터리 구동 {pct_s} — 약 2~7배 느려진다(무선 어댑터 절전 DC=2). "
                  "AC 를 연결하고, 덮개는 열어 둘 것(닫으면 프로세스가 언다)")


def check_commit() -> tuple[str, str]:
    """커밋 여유. 1~2GB 면 회색 화면·무증상 크래시가 온다 — 재부팅만 듣는다."""
    if not sys.platform.startswith("win"):
        return OK, f"{sys.platform} — 커밋 점검 건너뜀"

    class _M(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    m = _M()
    m.dwLength = ctypes.sizeof(_M)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return WARN, "메모리 상태를 읽지 못했다"
    free = m.ullAvailPageFile / 1024 ** 3
    total = m.ullTotalPageFile / 1024 ** 3
    s = f"커밋 여유 {free:.1f}GB / {total:.1f}GB"
    if free < 2:
        return BAD, s + " — 크래시 임박. **재부팅할 것**(프로세스를 죽여도 소용없다)"
    if free < 5:
        return WARN, s + " — 여유가 적다. 긴 수집 전 재부팅을 권한다"
    return OK, s


def _tried(slug: str) -> set[str]:
    """이 거점에서 층별개요를 **이미 호출해 본** 건물 lnoCd 집합.

    수집기는 실행마다 `bronze/<slug>/<날짜>/bldg_flr_raw.json` 에 그 회차가 응답을
    받은 건물만 쓴다. 날짜별 파일을 전부 합치면 "지금까지 시도해 본 것" 이 된다.

    **왜 mtime 으로 판정하지 않는가**: quota.md 의 판단 순서 ②는 "bronze 가 있다면
    그 뒤에 대장을 새로 받았는가" 인데, 이걸 `building_vacancy.json` 의 mtime 으로
    재면 **항상 참이 된다.** floor_capacity 자신이 bronze 를 쓴 직후 같은 실행에서
    gold 를 제자리 갱신하기 때문이다(회수가 0 인 거점도 `_persist` 를 탄다).
    2026-08-19 에 이 오탐으로 50거점을 전부 넣어 672콜을 태우고 22동을 받았다.
    시도 여부는 추정하지 말고 **raw 에 그 건물이 있는지로 직접** 본다.
    """
    out: set[str] = set()
    for f in sorted((BRONZE / slug).glob("*/bldg_flr_raw.json")):
        try:
            out |= set(json.loads(f.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001  깨진 회차 하나가 판정을 막지 않게
            continue
    return out


def _gold(slug: str) -> list | None:
    p = GOLD / slug / "building_vacancy.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def report_remaining() -> None:
    """전유부(대장) 잔여와 층별개요 대상을 gold 에서 유도해 출력한다."""
    paused = _paused()
    missing, partial = [], []
    for slug in ALL_HUBS:
        if slug in paused:                # 서빙 보류 도시 — 오늘 쿼터를 태우지 않는다
            continue
        rows = _gold(slug)
        if rows is None or not rows:
            missing.append(slug)          # 파일이 없거나 0동 = 미수집
        elif any(r.get("capacity_method") == "rate_limited" for r in rows):
            partial.append((slug, sum(1 for r in rows
                                      if r.get("capacity_method") == "rate_limited")))

    live = len(ALL_HUBS) - len(paused)
    print(f"\n■ 전유부(대장) — 미수집 {len(missing)}거점 / 서빙 대상 {live}")
    if paused:
        # 숫자에서 뺐다는 사실을 밝힌다. 조용히 빼면 다음 사람이 "잔여 없음"을 완주로 읽는다.
        print(f"  (서빙 보류로 제외 {len(paused)}거점 — measured_pages.SERVED_CITIES 밖. "
              "재개하려면 거기에 도시 id 를 되넣는다)")
    if missing:
        for label, grp in _GROUPS:
            part = [s for s in missing if s in grp]
            if part:
                print(f"  [{label}] " + " ".join(part))
    if partial:
        print("  429 강등이 남은 거점(재실행하면 자동 재수집): "
              + " ".join(f"{s}({n})" for s, n in partial))

    # 붙여 쓸 명령줄까지 찍는다 — 층별개요만 찍고 전유부는 슬러그만 나열하던 것을 맞춘다
    # (2026-08-15). 429 강등 거점도 같은 실행에서 자동 재수집되므로 뒤에 붙인다.
    todo = missing + [s for s, _ in partial]
    if todo:
        for label, grp in _GROUPS:
            part = [s for s in todo if s in grp]
            if not part:
                continue
            print(f"      [{label} {len(part)}거점] → powershell -ExecutionPolicy Bypass "
                  "-File scripts\\run_bldgvac_until_done.ps1 -MaxPasses 20 "
                  + " ".join(part))
        print("        (쿼터가 먼저 끊기면 '진행 0동' 으로 멈춘다 — 정상이다. "
              "150동마다 체크포인트라 내일 같은 줄을 다시 돌리면 완료분을 건너뛴다)")
    else:
        print("  전유부 잔여 없음 — 오늘은 층별개요부터 돈다.")

    # 잔여를 **미시도 / 판정완료** 로 가른다. 둘을 합쳐 "잔여 N동" 으로 찍으면
    # 회수 가능한 작업처럼 읽히는데, 판정완료분은 몇 번을 호출해도 안 바뀐다
    # (층별개요를 정상 수신했고 그 응답에 상업 층이 0 인 건물 — 07-26 교정 조항).
    # bronze raw 를 전부 읽으므로 이 구간만 십수 초 걸린다. 수천 콜을 가르는
    # 판단이라 그 값은 한다.
    print("\n■ 층별개요 — 시도 이력 대조 중(bronze raw 스캔, 십수 초)…")
    rows_out = []
    for slug in ALL_HUBS:
        if slug in paused:                # 위와 같은 이유 — 보류 도시는 콜을 배정하지 않는다
            continue
        rows = _gold(slug)
        if not rows:
            continue
        appr = [r for r in rows if r.get("capacity_method") == "floor_approx"]
        if not appr:
            continue
        tried = _tried(slug)
        n_untried = sum(1 for r in appr if r.get("lnoCd") not in tried)
        n_judged = len(appr) - n_untried
        n_ouln = sum(1 for r in rows if r.get("capacity_method") == "floor_ouln")
        rows_out.append((n_untried, n_judged, slug, n_ouln))
    rows_out.sort(reverse=True)

    tot_untried = sum(r[0] for r in rows_out)
    tot_judged = sum(r[1] for r in rows_out)
    print(f"  floor_approx 잔여 {tot_untried + tot_judged:,}동 / {len(rows_out)}거점")
    print(f"    미시도   {tot_untried:>6,}동  ← 회수 가능성이 있는 것은 이것뿐이다")
    print(f"    판정완료 {tot_judged:>6,}동  (상업층 0 확정 — 재호출해도 안 바뀐다)")

    # **명령줄에는 미시도가 있는 거점만 넣는다.** 잔여 동수로 고르면 안 된다 —
    # 회수율을 정하는 건 '미시도 비율' 하나다(quota.md §회수율 표, 커밋 ac3566a).
    worth = [r for r in rows_out if r[0] > 0]
    if not worth:
        print("\n  ▶ 시도할 가치가 있는 거점 없음 — 오늘 층별개요로 받을 것이 없다.")
        print("    잔여가 남아 있어도 전부 판정완료분이다. 새 거점을 넣거나 대장을")
        print("    새로 받기 전까지는 여기서 늘어날 회수가 없다.")
    else:
        fresh = [r for r in worth if r[3] == 0]     # floor_ouln 0 — 재수집 낭비 없음
        stale = [r for r in worth if r[3] > 0]      # 이미 ouln 보유 — --only-approx 로
        print(f"\n  ▶ 시도할 가치가 있는 거점 {len(worth)} · 미시도 {tot_untried:,}동")
        if fresh:
            print(f"  [그냥 넣는다] ouln 0 인 {len(fresh)}거점 — "
                  f"{sum(r[0] for r in fresh):,}콜")
            for u, j, s, _ in fresh:
                print(f"      {s:<18}미시도 {u:>5}  판정완료 {j:>5}")
            print("      → python -m data.collectors.floor_capacity "
                  + " ".join(r[2] for r in fresh))
        if stale:
            cost_full = sum(r[0] + r[3] for r in stale)
            cost_only = sum(r[0] for r in stale)
            print(f"  [--only-approx 로만] ouln 보유 {len(stale)}거점 — "
                  f"미시도 {cost_only:,}동, 플래그 없이는 {cost_full:,}콜")
            for u, j, s, _ in stale:
                print(f"      {s:<18}미시도 {u:>5}  판정완료 {j:>5}")
            print("      → python -m data.collectors.floor_capacity --only-approx "
                  + " ".join(r[2] for r in stale))

    print("\n  ⚠ 대장을 아직 수집 중인 거점은 끝난 뒤에 다시 뽑을 것 — floor_approx 가 계속 는다.")
    print("  ⚠ 전유부와 층별개요를 동시에 돌리지 말 것 — 429 는 키 단위라 서로를 죽인다.")


def main() -> int:
    print("=== 건축HUB 쿼터 프리플라이트 ===")
    worst = 0
    for name, fn in (("쿼터", check_quota), ("전원", check_power), ("커밋", check_commit)):
        status, detail = fn()
        print(f"[{status}] {name}: {detail}")
        worst = max(worst, {OK: 0, WARN: 1, BAD: 2}[status])
    report_remaining()
    if worst == 2:
        print("\n중단 사유가 있다. 위 [중단] 항목을 해결하기 전에는 수집을 시작하지 않는다.")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())

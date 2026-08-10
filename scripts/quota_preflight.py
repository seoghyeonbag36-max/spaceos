"""[Page] 건축HUB 일일 쿼터 작업 프리플라이트 — 돌리기 전에 확인할 것 4종.

`/quota` 슬래시 커맨드가 부르는 스크립트다. 원래 커맨드 파일에 `python -c "..."` 로
임베드돼 있었는데, 이 프로젝트의 기본 셸이 PowerShell 이라 여러 줄 인라인 스니펫이
따옴표 파싱에서 깨졌다(2026-08-10). 셸 인용 문제를 없애려고 파일로 뺐다.

확인 항목:
  1. 쿼터가 실제로 열렸는가 — 로그가 아니라 1콜 프로브의 응답으로 판정한다
  2. 전원 — 배터리면 느려진다. 기전은 CPU가 아니라 무선 어댑터 절전(AC 0 / DC 2)이고
     이 작업은 네트워크 바운드라 정확히 거기서 아프다. 덮개를 닫으면 아예 언다
  3. 커밋 여유 — 1~2GB 면 회색 화면·무증상 크래시가 온다. 재부팅만 듣는다
  4. 잔여 — 전유부(대장) 미수집 거점과, 층별개요 대상 동수

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
from data.config.page_hubs import HUBS  # noqa: E402

GOLD = ROOT / "data" / "gold"
_EXPOS = "http://apis.data.go.kr/1613000/BldRgstHubService/getBrExposPubuseAreaInfo"

OK, WARN, BAD = "OK  ", "주의", "중단"


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
    missing, partial = [], []
    for slug in HUBS:
        rows = _gold(slug)
        if rows is None or not rows:
            missing.append(slug)          # 파일이 없거나 0동 = 미수집
        elif any(r.get("capacity_method") == "rate_limited" for r in rows):
            partial.append((slug, sum(1 for r in rows
                                      if r.get("capacity_method") == "rate_limited")))

    print(f"\n■ 전유부(대장) — 미수집 {len(missing)}거점 / 전체 {len(HUBS)}")
    if missing:
        print("  " + " ".join(missing))
    if partial:
        print("  429 강등이 남은 거점(재실행하면 자동 재수집): "
              + " ".join(f"{s}({n})" for s, n in partial))

    rows_out = []
    for slug in HUBS:
        rows = _gold(slug)
        if not rows:
            continue
        c = Counter(r.get("capacity_method") for r in rows)
        if c["floor_approx"]:
            rows_out.append((c["floor_approx"], slug, c["floor_ouln"]))
    rows_out.sort(reverse=True)

    fresh = [r for r in rows_out if r[2] == 0]      # floor_ouln 0 — 재수집 낭비 없음
    stale = [r for r in rows_out if r[2] > 0]       # 이미 ouln 보유 — --only-approx 로
    print(f"\n■ 층별개요 — floor_approx 잔여 {sum(r[0] for r in rows_out):,}동 "
          f"/ {len(rows_out)}거점")
    if fresh:
        print(f"  [그냥 넣는다] ouln 0 인 {len(fresh)}거점 — {sum(r[0] for r in fresh):,}콜")
        for n, s, _ in fresh:
            print(f"      {s:<18}{n:>6}동")
        print("      → python -m data.collectors.floor_capacity "
              + " ".join(s for _, s, _ in fresh))
    if stale:
        cost_full = sum(r[0] + r[2] for r in stale)
        cost_only = sum(r[0] for r in stale)
        print(f"  [--only-approx 로만] ouln 보유 {len(stale)}거점 — "
              f"{cost_only:,}동 회수에 플래그 없이는 {cost_full:,}콜")
        print("      → python -m data.collectors.floor_capacity --only-approx "
              + " ".join(s for _, s, _ in stale))
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

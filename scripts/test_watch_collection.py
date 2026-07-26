"""watch_collection 회귀 테스트 — 2026-07-26 songridan 오탐 재현.

실행: python scripts/test_watch_collection.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from watch_collection import MODES, watch      # noqa: E402

DONE_RE = MODES["flrcap"][0]
HUBS = ["hannam", "songridan"]


def line(slug: str) -> str:
    return f"[flr-cap:{slug}] building_vacancy.json 갱신 — capacity_method: {{}}\n"


ok = True


def check(label, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {label}{'  ' + detail if detail else ''}")


# ── 1) songridan 레이스 재현 ────────────────────────────────────────────
# 로그를 읽은 직후, alive() 를 호출하는 시점에 수집기가 마지막 줄을 쓰고 종료한다.
# 구 코드는 낡은 스냅샷으로 "미완료 사망"을 선언했다.
log = [line("hannam")]                       # songridan 완료 줄은 아직 없음
events = []


def read_racy():
    return "".join(log)


def alive_racy():
    # 생존 확인을 하는 '사이'에 수집기가 마지막 줄을 쓰고 죽는다 — 실제 순서 그대로.
    log.append(line("songridan"))
    return False


rc = watch(read_racy, alive_racy, DONE_RE, HUBS,
           lambda s, missing=None: events.append(s if s else f"DEAD:{missing}"),
           sleep=lambda _: None)

check("레이스에서도 정상 완료로 판정(rc=0)", rc == 0, f"rc={rc}")
check("songridan 을 완료로 보고", "songridan" in events, f"events={events}")
check("DEAD 오탐 없음", not any(str(e).startswith("DEAD") for e in events))

# ── 2) 진짜 실패는 여전히 잡는다 ────────────────────────────────────────
log2 = [line("hannam")]
events2 = []
rc2 = watch(lambda: "".join(log2), lambda: False, DONE_RE, HUBS,
            lambda s, missing=None: events2.append(s if s else f"DEAD:{missing}"),
            sleep=lambda _: None)
check("실제 미완료 사망은 DEAD 로 보고(rc=1)", rc2 == 1, f"rc={rc2}")
check("미완료 거점을 지목", "DEAD:['songridan']" in events2, f"events={events2}")

# ── 3) 중복 보고 없음 ───────────────────────────────────────────────────
log3 = [line("hannam"), line("songridan")]
events3 = []
watch(lambda: "".join(log3), lambda: True, DONE_RE, HUBS,
      lambda s, missing=None: events3.append(s), sleep=lambda _: None)
check("거점당 1회만 보고", events3 == ["hannam", "songridan"], f"events={events3}")

# ── 4) 완료 순서 보존 ───────────────────────────────────────────────────
log4 = [line("songridan"), line("hannam")]
events4 = []
watch(lambda: "".join(log4), lambda: True, DONE_RE, HUBS,
      lambda s, missing=None: events4.append(s), sleep=lambda _: None)
check("로그에 찍힌 순서대로 보고", events4 == ["songridan", "hannam"], f"events={events4}")

# ── 5) 로그가 아직 없어도 죽지 않는다 ───────────────────────────────────
events5 = []
rc5 = watch(lambda: "", lambda: False, DONE_RE, HUBS,
            lambda s, missing=None: events5.append(f"DEAD:{missing}"), sleep=lambda _: None)
check("빈 로그 + 사망 → 전 거점 미완료 보고", rc5 == 1 and "songridan" in events5[0])

print("\n=== ALL PASS ===" if ok else "\n=== FAILURES ABOVE ===")
sys.exit(0 if ok else 1)

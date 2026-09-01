"""거점 체인 무인 배치 — 세션 밖에서 혼자 돌고, 언제 죽어도 이어받는다.

## 왜 이 스크립트인가

2026-08-30 에 같은 사고를 **세 번** 겪었다: Claude Code 세션이 끝나면 그 안에서 띄운
백그라운드 수집이 함께 죽는다(금촌 대장 300/831 · 인허가 5거점 0행 · 상권 마스터).
토큰 만료도 같은 종류의 죽음이다. 그래서 이 스크립트는 **세션에 매달리지 않는다** —
`pythonw`/detached 로 띄우면 세션이 사라져도 계속 돈다.

## 지키는 것 셋 (2026-08-30 지시)

1. **덮개를 닫아도 돈다** — `scripts/keep_awake.ps1` 로 감싸 실행한다(아래 §실행).
   이 노트북은 Modern Standby(S0)라 전원 설정만으로는 안 잔다고 보장 못 한다.
2. **토큰이 만료돼도 훼손되지 않는다** — 모든 단계가 재개 가능하다. 수집기는 이미 받은
   것을 건너뛰고, 각 거점이 끝날 때마다 상태를 파일에 적는다. 중간에 죽으면 다음 실행이
   그 지점부터 잇는다. **부분 결과를 완료로 적지 않는다.**
3. **배터리 5% 미만이면 정리하고 멈춘다** — 거점 하나를 시작하기 전에 전원을 본다.
   AC 가 없고 5% 미만이면 진행분을 저장하고 정상 종료한다(강제 종료를 기다리지 않는다).

## 상태

`reports/hub_chain_batch.json` — 거점별 마지막 완료 단계와 시각. 사람이 읽을 로그는
`data/logs/hub-chain-batch.log`. 진행 판정은 이 파일이 아니라 **산출물**이 기준이다
(`scripts/chain_status.py`) — 이 파일은 이력이지 진실이 아니다.

## 실행

    # 무인으로 걸어둘 때 (권장) — 죽으면 10분 안에 스스로 되살아난다
    python scripts/resume_hub_chain.py --install

    # 한 번만 돌릴 때. 절전 억제는 이 스크립트가 스스로 건다(덮개를 닫아도 된다)
    python -u scripts/run_hub_chain_batch.py --batch seoul2

⚠ `keep_awake.ps1` 로 감싸지 않아도 된다(08-31 부터). 작업 스케줄러가 부른 PowerShell 이
  배터리 절약 모드에서 영구히 멈추는 것을 두 번 겪어, 절전 억제를 이 파일 안으로 옮겼다.

    --batch seoul2   서울 미커버 자치구 12거점 (SEOUL_BATCH2_HUBS)
    --batch gg2      경기 2차 13거점
    --hubs a,b,c     직접 지정
    --skip-ledger    대장을 건너뛴다(쿼터 0 · 점포·폴리곤만)
"""
from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

STATE = ROOT / "reports" / "hub_chain_batch.json"
LOG = ROOT / "data" / "logs" / "hub-chain-batch.log"
BATTERY_FLOOR = 5          # % — 이 아래면 새 거점을 시작하지 않는다


def say(msg: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


class _SPS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def keep_awake(hold: bool = True) -> bool:
    """덮개를 닫아도 계속 돌게 시스템 유휴 판정을 막는다. 화면은 붙잡지 않는다.

    종전에는 `keep_awake.ps1` 로 감싸 실행했다. 그런데 08-31 에 **작업 스케줄러가
    부른 PowerShell 이 두 번 다 영구히 멈췄다**(배터리 절약 모드에서 conhost 를 띄운
    채 대기). 감시자가 감시 대상보다 먼저 죽으면 무인 운전이 아니다. 그래서 절전
    억제를 여기로 옮겼다 — 이제 이 파일 하나만 살아 있으면 된다.

    ⚠ 스레드 단위 상태다. 메인 스레드에서 걸고, 그 스레드가 사는 동안 유지된다.
    """
    try:
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED if hold else ES_CONTINUOUS
        return ctypes.windll.kernel32.SetThreadExecutionState(flags) != 0
    except Exception:                                    # noqa: BLE001
        return False


def power() -> tuple[bool, int]:
    """(AC 연결 여부, 배터리 %). 못 읽으면 (True, 100) — 못 읽었다고 멈추지 않는다."""
    try:
        s = _SPS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
            return True, 100
        return s.ACLineStatus == 1, int(s.BatteryLifePercent)
    except Exception:                                        # noqa: BLE001
        return True, 100


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".json.tmp")          # 저장 도중 죽어도 기존 파일이 남는다
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def run(mod: list[str], label: str) -> bool:
    """파이썬 모듈 하나를 돌린다. 실패해도 예외를 던지지 않고 False 를 준다 —
    한 거점이 막혀도 배치 전체가 서면 안 된다."""
    env_note = " ".join(mod)
    say(f"    → {label}: {env_note}")
    try:
        r = subprocess.run([sys.executable, "-u", "-m", *mod], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=3600,
                           env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    except subprocess.TimeoutExpired:
        say(f"    ✗ {label}: 1시간 초과 — 다음으로 넘어간다(재실행하면 이어받는다)")
        return False
    if r.returncode != 0:
        tail = (r.stdout or "")[-300:] + (r.stderr or "")[-300:]
        say(f"    ✗ {label}: exit={r.returncode} · {tail.strip()[:200]}")
        return False
    return True


def hubs_of(batch: str) -> list[str]:
    from data.config import page_hubs as ph
    if batch == "seoul2":
        return list(ph.SEOUL_BATCH2_HUBS)
    if batch == "gg2":
        return [k for k in ph.GYEONGGI_HUBS
                if k not in ("hwajeong", "geumchon", "ilsan", "westerndom",
                             "tanhyeon", "unjeong", "yadang")]
    raise SystemExit(f"모르는 배치: {batch}")


def ledger_gap(slug: str) -> int:
    """대장 후보 대비 **아직 안 받은 동수.** 0 이면 완주, -1 이면 판단 불가.

    ⚠ **파일이 있다고 대장이 끝난 게 아니다.** 수집기는 150동마다 gold 를 저장하므로
      중간에 죽어도 `building_vacancy.json` 은 남는다. 그런데 종전 `stage_done` 은
      그 존재만으로 "ledger 완료"로 보고 대장 단계를 건너뛰어 파이프라인부터 돌렸다.
      2026-09-01 에 **kkachisan 450/797(56%) · sangbong 600/859(70%) 이 잘린 채
      anchor 까지 찍혔다** — sangbong 은 0.2분 만에 '완료'로 기록됐다. 배치가 죽고
      감시자가 되살릴 때마다 재현되는 구조였다(잃은 데이터는 없다. 판정만 틀렸다).

    후보 수는 수집기와 **같은 방식**으로 센다(점포를 건물로 묶은 수). 수집기는 대상
    전량에 행을 쓰므로(못 받은 건물도 `no_ledger`·`non_commercial` 로 남는다) 완주하면
    행 수 == 후보 수다 — 09-01 실측에서 완주한 7거점이 정확히 100% 로 맞았다.

    점포 원본을 읽어야 해서 거점당 수 MB 를 파싱한다. 몇 초 걸리지만, 이 몇 초가
    "받은 줄 알았는데 안 받은" 거점을 막는다.
    """
    gold = ROOT / "data" / "gold" / slug / "building_vacancy.json"
    if not gold.exists():
        return -1
    try:
        from data.collectors.building_vacancy import group_by_building
        from data.collectors.common import load_latest
        stores = load_latest(slug, "stores_raw.json")
        if not stores:
            return -1
        rows = json.loads(gold.read_text(encoding="utf-8"))
        return max(0, len(group_by_building(stores)) - len(rows))
    except Exception:                                        # noqa: BLE001
        return -1                    # 판단이 안 되면 완주로도 미완으로도 몰지 않는다


def stage_done(slug: str) -> str:
    """산출물로 판정한 마지막 완료 단계. 상태파일이 아니라 파일이 기준이다."""
    gold = ROOT / "data" / "gold" / slug
    if ledger_gap(slug) > 0:
        # 대장이 잘렸다. 뒤 단계 산출물이 이미 있어도 **대장부터 다시** 세운다 —
        # 잘린 분모로 만든 공실률·앵커는 틀린 값이지 '조금 부족한 값'이 아니다.
        return "stores"
    if (gold / "calibration.json").exists():
        return "anchor"
    if (gold / "page_building_master.geojson").exists():
        return "master"
    if (gold / "building_vacancy.json").exists():
        return "ledger"
    if list((ROOT / "data" / "bronze").glob(f"{slug}/*/stores_raw.json")):
        return "stores"
    return "none"


def do_hub(slug: str, skip_ledger: bool) -> str:
    """거점 하나를 체인 끝까지 민다. 반환은 도달한 단계."""
    done = stage_done(slug)
    say(f"  ■ {slug} (현재 {done})")

    if done == "none":
        run(["data.collectors.vworld_bldg", slug], "폴리곤")
        run(["data.collectors.building_vacancy", slug, "--no-ledger"], "점포")
        done = stage_done(slug)

    if skip_ledger:
        return done

    # 대장을 새로 받았으면 뒤 단계는 **낡았다.** 그때는 산출물이 있어도 다시 세운다 —
    # 안 그러면 새 분자·분모가 지도와 앵커에 반영되지 않는다. 2026-09-01 에 kkachisan·
    # sangbong 이 그 상태였다: 잘린 대장을 이어 받아 797·859동을 채웠는데, 이미 있던
    # master·calibration 때문에 `done`이 곧장 "anchor" 로 뛰어 파이프라인 넷과 앵커
    # 보정이 통째로 건너뛰어졌다(calibration 이 00:11·22:14 자로 남았다). 잘린 분모로
    # 만든 값이 그대로 서빙될 뻔했다.
    refreshed = False
    if done in ("stores",):
        run(["data.collectors.building_vacancy", slug], "대장(전유부)")
        run(["data.collectors.floor_capacity", slug], "층별개요")
        refreshed = True
        done = stage_done(slug)

    if refreshed or done in ("ledger",):
        run(["data.pipelines.build_building_attrs", slug], "건물속성")
        run(["data.pipelines.recalc_floor_ouln", slug], "분모 재계산")
        run(["data.pipelines.build_page_master", slug], "Page 마스터")
        run(["data.pipelines.build_vacant_units", slug], "공실유닛")
        done = stage_done(slug)

    if refreshed or done in ("master",):
        run(["data.pipelines.calibrate_vacancy", slug], "앵커 보정")
        done = stage_done(slug)
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="seoul2")
    ap.add_argument("--hubs", default="")
    ap.add_argument("--skip-ledger", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="수집하지 않고 남은 일만 판정한다. 종료코드 0=남음 · 3=전부 완료")
    a = ap.parse_args()

    hubs = [h.strip() for h in a.hubs.split(",") if h.strip()] or hubs_of(a.batch)

    if a.check:
        # 감시자(resume_hub_chain.ps1)가 부른다. **산출물로만** 판정한다 —
        # 상태파일은 이력이지 진실이 아니고, 배치가 죽은 자리에서는 특히 그렇다.
        done = {s: stage_done(s) for s in hubs}
        left = [s for s, v in done.items() if v != "anchor"]
        for s, v in done.items():
            print(f"  {s:<14}{v}")
        print(f"남은 거점 {len(left)}/{len(hubs)}" + (f" — {' '.join(left)}" if left else ""))
        return 0 if left else 3

    st = load_state()
    awake = keep_awake()
    say(f"=== 배치 시작 · 거점 {len(hubs)} · skip_ledger={a.skip_ledger} · "
        f"절전억제={'걸림' if awake else '실패(덮개를 열어 둘 것)'} ===")

    for i, slug in enumerate(hubs, 1):
        ac, pct = power()
        if not ac and pct < BATTERY_FLOOR:
            say(f"⚠ 배터리 {pct}% (AC 없음) — 새 거점을 시작하지 않는다. "
                f"진행분 저장하고 정상 종료 ({i-1}/{len(hubs)} 완료)")
            st["stopped_reason"] = f"battery {pct}%"
            st["stopped_at"] = datetime.now().isoformat(timespec="seconds")
            save_state(st)
            keep_awake(False)
            return 0
        if not ac:
            say(f"  (배터리 {pct}% — AC 없음. 2~7배 느리다)")

        t0 = time.time()
        reached = do_hub(slug, a.skip_ledger)
        st[slug] = {"stage": reached, "at": datetime.now().isoformat(timespec="seconds"),
                    "minutes": round((time.time() - t0) / 60, 1)}
        save_state(st)                       # 거점 하나가 끝날 때마다 저장한다
        say(f"  ✓ {slug} → {reached} ({st[slug]['minutes']}분) [{i}/{len(hubs)}]")

    st["finished_at"] = datetime.now().isoformat(timespec="seconds")
    save_state(st)
    keep_awake(False)                    # 놓아주지 않으면 이 프로세스가 죽을 때까지 막힌다
    say("=== 배치 완료 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

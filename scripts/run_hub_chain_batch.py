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

    # 덮개 닫고 돌릴 때 (권장)
    powershell -ExecutionPolicy Bypass -File scripts/keep_awake.ps1 ^
        -Command "python -u scripts/run_hub_chain_batch.py --batch seoul2"

    # 그냥 앞에서 돌릴 때
    python -u scripts/run_hub_chain_batch.py --batch seoul2

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


def stage_done(slug: str) -> str:
    """산출물로 판정한 마지막 완료 단계. 상태파일이 아니라 파일이 기준이다."""
    gold = ROOT / "data" / "gold" / slug
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

    if done in ("stores",):
        run(["data.collectors.building_vacancy", slug], "대장(전유부)")
        run(["data.collectors.floor_capacity", slug], "층별개요")
        done = stage_done(slug)

    if done in ("ledger",):
        run(["data.pipelines.build_building_attrs", slug], "건물속성")
        run(["data.pipelines.recalc_floor_ouln", slug], "분모 재계산")
        run(["data.pipelines.build_page_master", slug], "Page 마스터")
        run(["data.pipelines.build_vacant_units", slug], "공실유닛")
        done = stage_done(slug)

    if done in ("master",):
        run(["data.pipelines.calibrate_vacancy", slug], "앵커 보정")
        done = stage_done(slug)
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="seoul2")
    ap.add_argument("--hubs", default="")
    ap.add_argument("--skip-ledger", action="store_true")
    a = ap.parse_args()

    hubs = [h.strip() for h in a.hubs.split(",") if h.strip()] or hubs_of(a.batch)
    st = load_state()
    say(f"=== 배치 시작 · 거점 {len(hubs)} · skip_ledger={a.skip_ledger} ===")

    for i, slug in enumerate(hubs, 1):
        ac, pct = power()
        if not ac and pct < BATTERY_FLOOR:
            say(f"⚠ 배터리 {pct}% (AC 없음) — 새 거점을 시작하지 않는다. "
                f"진행분 저장하고 정상 종료 ({i-1}/{len(hubs)} 완료)")
            st["stopped_reason"] = f"battery {pct}%"
            st["stopped_at"] = datetime.now().isoformat(timespec="seconds")
            save_state(st)
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
    say("=== 배치 완료 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

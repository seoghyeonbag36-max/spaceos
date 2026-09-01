"""거점 체인 배치가 죽어 있으면 되살린다 — 사람도, Claude 세션도, 토큰도 필요 없다.

## 왜

수집을 죽이는 것은 코드가 아니라 **세션의 수명**이었다. 2026-08-30 에 세 번, 08-31 에
한 번. Claude Code 토큰이 만료되면 그 세션에서 띄운 것이 같이 죽고, 그때부터 누군가
다시 눌러 줄 때까지 아무 일도 일어나지 않는다. `run_hub_chain_batch.py` 는 이미 재개
가능했지만 **"다시 눌러 줄 사람"**이 필요했다. 이 스크립트가 그 사람을 대신한다.

작업 스케줄러가 10분마다 부른다. 한 번에 하는 일은 셋뿐이다:

1. 이미 돌고 있으면 아무것도 하지 않는다 — 중복 실행은 429 를 부른다(키 단위
   트래픽 제한이라 두 수집기가 서로를 죽인다)
2. **산출물**로 남은 거점을 센다(상태파일이 아니라). 없으면 조용히 끝낸다
3. 남았으면 detached 로 띄운다 — 덮개를 닫아도, 부른 셸이 사라져도 계속 돈다

## 왜 파이썬인가 (08-31 실측)

처음엔 PowerShell 스크립트였다. **작업 스케줄러 안에서 두 번 다 영구히 멈췄다** —
시작 20초 뒤 conhost 를 띄운 채 CPU 1.5초만 쓰고 대기, 6분이 지나도 첫 로그 한 줄을
못 썼다. 그 사이 배터리 절약 모드가 켜져 있었고(AC 빠짐 · 15%), 그 상태에서는
`Get-CimInstance Win32_Process` · `taskkill` 조차 2분을 넘겼다. PowerShell 을 진입점에
두면 **감시자 자신이 감시 대상보다 먼저 죽는다.**

python.exe 로 바꿔도 같은 자리에서 멈췄다(20분). 셋 다 공통점은 **콘솔을 붙인다**는
것이었다 — 시작 20초 뒤 conhost 가 뜨고 거기서 대기. 그래서 콘솔을 아예 만들지 않는
`pythonw.exe` 로 건다. 로그는 어차피 파일로 쓰므로 잃는 것이 없다.

게다가 `MultipleInstances=IgnoreNew` 라 그 한 번의 정지가 **이후 모든 실행을 막았다**
(다음 실행은 0x800710E0 "요청이 거부됨" — 프로세스를 죽인 뒤에도 스케줄러는 "실행 중"을
붙들고 있었다). 그래서:

- 진입점은 pythonw.exe 하나다. PowerShell 도, 콘솔도 거치지 않는다
- 물려도 5분이면 끊기고(`ExecutionTimeLimit`), 다음 실행이 낡은 것을 치운다
  (`StopExisting`) — 감시자가 스스로 막히지 않게 하는 것이 중복 방지보다 앞선다.
  중복 수집은 스케줄러가 아니라 PID 파일이 막는다
- 절전 억제(`keep_awake.ps1` 이 하던 일)는 배치 자신이 ctypes 로 한다
- 프로세스 조회에 WMI 를 쓰지 않는다 — **PID 파일 + 시작시각 대조**로 본다

2026-09-01 에 이 구조가 실제로 증명됐다: 배터리가 떨어져 노트북이 **21시간 잠들었다가**
깨어난 21:18:30 에, 사람도 Claude 세션도 없이 감시자가 배치를 되살렸고 이미 끝난 6거점을
건너뛰고 mokdong-yc 부터 이었다.

## 설치 / 해제

    python scripts/resume_hub_chain.py --install          # 10분마다 + 로그온 시
    python scripts/resume_hub_chain.py --uninstall
    python scripts/resume_hub_chain.py                    # 한 번만 판정·재개

관리자 권한이 필요 없다. 현재 사용자로 도는 작업이라 **로그온한 상태에서만** 뛴다
(그 편이 맞다 — 이 작업은 사용자 PATH 의 python 과 .env 를 쓴다).

⚠ 되살리는 것이지 고치는 것이 아니다. 쿼터가 소진돼 못 받는 상태라면 10분마다 깨어나
  "대장 대상 N동"만 찍고 진행 없이 끝난다. 그건 정상이고, 다음 날 쿼터가 열리면 같은
  감시자가 이어서 받는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))   # scripts 는 패키지가 아니다

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

LOG = ROOT / "data" / "logs" / "hub-chain-resume.log"
TASK_NAME = "SpaceOS-HubChain-Resume"

# Windows 프로세스 생성 플래그 — 부모가 죽어도 살아남고, 창을 띄우지 않는다
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def say(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:                                    # 기록 실패는 재개 실패가 아니다
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def pidfile(batch: str) -> Path:
    return ROOT / "reports" / f"hub_chain_batch.{batch}.pid"


def _start_time(pid: int) -> datetime | None:
    """PID 의 프로세스 시작시각. 죽었으면 None.

    PID 만으로 판정하면 안 된다 — 재부팅 뒤 같은 번호가 다른 프로세스에 붙으면
    "돌고 있다"고 오판해 **영영 재개하지 않는다.** WMI 는 절전 모드에서 수십 초씩
    걸리므로 쓰지 않고, 커널32 로 직접 묻는다.
    """
    import ctypes
    import ctypes.wintypes as wt

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        creation = wt.FILETIME()
        rest = (wt.FILETIME * 3)()
        if not k32.GetProcessTimes(h, ctypes.byref(creation), *[ctypes.byref(x) for x in rest]):
            return None
        # FILETIME(100ns, 1601-01-01 기준) → 로컬 시각
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        utc = datetime(1601, 1, 1) + timedelta(microseconds=ticks / 10)
        return utc + (datetime.now() - datetime.utcnow())
    finally:
        k32.CloseHandle(h)


def already_running(batch: str) -> int | None:
    p = pidfile(batch)
    if not p.exists():
        return None
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
        started = datetime.fromisoformat(rec["started"])
        actual = _start_time(int(rec["pid"]))
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        say("PID 파일을 못 읽었다 — 재개 대상으로 본다.")
        return None
    if actual is None:
        return None
    if abs((actual - started.replace(tzinfo=None)).total_seconds()) > 5:
        say(f"PID {rec['pid']} 는 다른 프로세스다(시작시각 불일치) — 재개 대상으로 본다.")
        return None
    return int(rec["pid"])


def remaining(batch: str) -> list[str]:
    """남은 거점을 **산출물로** 센다. 상태파일은 이력이지 진실이 아니다."""
    from run_hub_chain_batch import hubs_of, stage_done
    return [s for s in hubs_of(batch) if stage_done(s) != "anchor"]


def launch(batch: str) -> int:
    """배치를 detached 로 띄우고 PID 를 남긴다. PowerShell 을 거치지 않는다."""
    out = ROOT / "data" / "logs" / f"batch-{batch}-resume.out.log"
    out.parent.mkdir(parents=True, exist_ok=True)
    fh = out.open("a", encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        [sys.executable, "-u", "scripts/run_hub_chain_batch.py", "--batch", batch],
        cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
    )
    started = _start_time(proc.pid) or datetime.now()
    pidfile(batch).parent.mkdir(parents=True, exist_ok=True)
    pidfile(batch).write_text(
        json.dumps({"pid": proc.pid, "started": started.isoformat(), "batch": batch}),
        encoding="utf-8")
    return proc.pid


def install(batch: str, minutes: int) -> int:
    """작업 스케줄러에 건다. 관리자 권한 없이 되는 방법만 쓴다.

    ⚠ `Register-ScheduledTask`(PowerShell) 는 이 환경에서 자격증명을 기다리며 멈춘다 —
      비대화형 셸에서 2분을 넘겼다(08-31). `schtasks /IT` 는 암호 없이 등록된다.
    ⚠ 로그온 트리거에 `<UserId>` 를 넣지 않으면 "모든 사용자"가 되어 **관리자 권한을
      요구한다**(Access is denied). 현재 사용자 SID 를 박아야 통과한다.
    """
    # ⚠ **pythonw.exe 로 건다.** 콘솔을 붙이는 python.exe 로 걸면 작업 스케줄러 안에서
    #   영구히 멈춘다 — 08-31 에 PowerShell 로 두 번, python.exe 로 한 번, 셋 다 같은
    #   자리에서 죽었다(시작 20초 뒤 conhost 가 뜨고 그대로 대기, 20분이 지나도 첫 줄을
    #   못 쓴다). 그 사이 배터리 절약 모드였고, 창 없는 세션의 콘솔 할당이 물린 것이다.
    #   pythonw 는 콘솔을 만들지 않는다. 로그는 어차피 파일로 쓴다.
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    action = f'"{exe}" "{ROOT / "scripts" / "resume_hub_chain.py"}" --batch {batch}'
    r = subprocess.run(["schtasks", "/Create", "/TN", TASK_NAME, "/TR", action,
                        "/SC", "MINUTE", "/MO", str(minutes), "/IT", "/F"],
                       capture_output=True, text=True, encoding="cp949", errors="replace")
    if r.returncode != 0:
        say(f"작업 등록 실패: {(r.stdout + r.stderr).strip()[:200]}")
        return r.returncode
    say(f"작업 '{TASK_NAME}' 등록 — {minutes}분마다 · batch={batch}")

    # 배터리로 떨어져도 멈추지 않게 + 로그온 트리거 추가. XML 왕복이 유일하게
    # 통하는 경로다(Set-ScheduledTask 도 자격증명을 기다리며 멈춘다).
    xml = ROOT / "reports" / f".{TASK_NAME}.xml"
    q = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME, "/XML", "ONE"],
                       capture_output=True)
    s = q.stdout.decode("utf-16" if q.stdout[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8",
                        errors="replace")
    # 계정은 SID 가 아니라 **이름**으로 적는다. SID 를 넣으면 절전 모드에서 LSA 조회가
    # 실패해 "계정 이름과 보안 식별자 사이에 매핑이 이루어지지 않았습니다" 로 거부된다
    # (08-31 실측). 이름은 그대로 통한다.
    who = f"{os.environ.get('USERDOMAIN', '')}\{os.environ.get('USERNAME', '')}".strip("\\")
    # ⚠ `IgnoreNew` 를 쓰지 않는다. 한 인스턴스가 물리면 **이후 모든 실행이 거부**되고
    #   (0x800710E0), 스케줄러는 프로세스가 이미 죽은 뒤에도 "실행 중"을 붙들고 있었다
    #   (08-31 실측 — 감시자가 감시 대상보다 먼저 죽는 바로 그 자리다). `StopExisting`
    #   은 낡은 인스턴스를 치우고 새로 돈다. 중복 수집은 스케줄러가 아니라 PID 파일이
    #   막으므로, 여기서는 "막히지 않는 것"이 더 중요하다.
    # ⚠ 5분 제한도 같은 이유다. 판정·기동은 몇 초면 끝난다 — 5분을 넘겼다면 그것은
    #   일하는 중이 아니라 물린 것이다. 배치 자신은 이 작업의 자식이 아니라 detached 라
    #   여기서 죽지 않는다.
    for old, new in (("<DisallowStartIfOnBatteries>true<", "<DisallowStartIfOnBatteries>false<"),
                     ("<StopIfGoingOnBatteries>true<", "<StopIfGoingOnBatteries>false<"),
                     ("<StopOnIdleEnd>true<", "<StopOnIdleEnd>false<"),
                     ("<MultipleInstancesPolicy>IgnoreNew<",
                      "<MultipleInstancesPolicy>StopExisting<")):
        s = s.replace(old, new)
    limit = "<ExecutionTimeLimit>PT5M</ExecutionTimeLimit>"
    if "<ExecutionTimeLimit>" in s:
        s = re.sub(r"<ExecutionTimeLimit>[^<]*</ExecutionTimeLimit>", limit, s)
    else:
        s = s.replace("</Settings>", f"    {limit}\n  </Settings>")
    if "<LogonTrigger>" not in s and who:
        s = s.replace("</Triggers>",
                      f"    <LogonTrigger>\n      <Enabled>true</Enabled>\n"
                      f"      <UserId>{who}</UserId>\n    </LogonTrigger>\n  </Triggers>")
    xml.write_text(s, encoding="utf-16")
    r2 = subprocess.run(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml), "/F"],
                        capture_output=True, text=True, encoding="cp949", errors="replace")
    xml.unlink(missing_ok=True)
    if r2.returncode != 0:
        say(f"⚠ 배터리·로그온 설정은 못 넣었다(기본값으로 돈다): "
            f"{(r2.stdout + r2.stderr).strip()[:150]}")
    else:
        say("배터리에서도 시작·계속 · 로그온 트리거 추가됨")
    return 0


def uninstall() -> int:
    r = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                       capture_output=True, text=True, encoding="cp949", errors="replace")
    say(f"작업 해제 {'완료' if r.returncode == 0 else '실패'} — 이미 돌고 있는 배치는 그대로 둔다")
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="seoul2")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--minutes", type=int, default=10)
    a = ap.parse_args()

    if a.uninstall:
        return uninstall()
    if a.install:
        return install(a.batch, a.minutes)

    pid = already_running(a.batch)
    if pid:
        say(f"이미 실행 중 (PID {pid}) — 건드리지 않는다.")
        return 0
    left = remaining(a.batch)
    if not left:
        say(f"배치 '{a.batch}' 전 거점 완료 — 재개할 것 없음.")
        return 0
    new_pid = launch(a.batch)
    say(f"재개했다 — PID {new_pid} · 남은 거점 {len(left)} ({' '.join(left)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

<#
.SYNOPSIS
  장시간 작업(대장 수집 · GNN 학습) 동안 시스템이 잠들지 않게 붙잡는다.

.DESCRIPTION
  이 노트북은 Modern Standby(S0 저전력 유휴)다. 전원 구성표의 "덮개 닫기 동작 = 아무 것도
  안 함"(2026-08-25 설정)만으로는 앱·드라이버가 유휴로 판정하면 여전히 대기로 들어갈 수 있다.
  SetThreadExecutionState 로 ES_SYSTEM_REQUIRED 를 계속 걸어 그 판정 자체를 막는다.

  ⚠ 화면은 끈다(ES_DISPLAY_REQUIRED 를 걸지 않는다) — 덮개를 닫는 것이 목적이므로
    화면까지 붙잡으면 전력만 쓴다.
  ⚠ 배터리로는 여전히 느리다. CLAUDE.md 실측대로 대장 수집은 AC 전원에서 약 7배 빠르다.
    이 스크립트는 "잠들지 않게" 할 뿐 "느려지지 않게" 하지 못한다.

.EXAMPLE
  # 감싸서 실행 — 명령이 끝나면 자동으로 놓아준다 (권장)
  powershell -ExecutionPolicy Bypass -File scripts/keep_awake.ps1 -Command "python -u -m ml.training.train_gnn --epochs 600"

.EXAMPLE
  # 그냥 붙잡고만 있기 — Ctrl+C 로 해제
  powershell -ExecutionPolicy Bypass -File scripts/keep_awake.ps1
#>
param(
    [string]$Command = ""
)

$signature = @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
$power = Add-Type -MemberDefinition $signature -Name 'SpaceOsPower' -Namespace 'SpaceOs' -PassThru

# ⚠ PS 5.1 은 0x80000000 을 Int32 로 파싱해 [uint32] 캐스트가 터진다(-2147483648).
#   10진 리터럴로 적는다. 처음에 16진으로 적었다가 호출이 실패했는데도 성공 메시지가
#   찍혔다 — $prev 가 $null 이라 `-eq 0` 검사를 빠져나갔다. 아래처럼 명시적으로 막는다.
$ES_CONTINUOUS      = [uint32]2147483648   # 0x80000000
$ES_SYSTEM_REQUIRED = [uint32]1            # 0x00000001

$prev = $null
try {
    $prev = $power::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
} catch {
    throw "[keep_awake] SetThreadExecutionState 호출 자체가 실패했다: $_"
}
if ($null -eq $prev -or $prev -eq 0) {
    throw "[keep_awake] 절전 억제 실패(반환 0). 잠들 수 있으므로 덮개를 열어 두고 다시 시도할 것."
}
Write-Output "[keep_awake] 시스템 유휴 판정을 막는다 (화면은 끈다). PID=$PID"

try {
    if ($Command -ne "") {
        Write-Output "[keep_awake] 실행: $Command"
        $env:PYTHONIOENCODING = "utf-8"   # cp949 로 em dash 가 죽는다 (08-19 실측)
        & cmd.exe /c $Command
        $code = $LASTEXITCODE
        Write-Output "[keep_awake] 종료코드 $code"
        exit $code
    } else {
        Write-Output "[keep_awake] 붙잡는 중 — Ctrl+C 로 해제한다."
        while ($true) { Start-Sleep -Seconds 60 }
    }
} finally {
    # 놓아주지 않으면 이 프로세스가 죽을 때까지 절전이 막힌다
    [void]$power::SetThreadExecutionState($ES_CONTINUOUS)
    Write-Output "[keep_awake] 해제됨."
}

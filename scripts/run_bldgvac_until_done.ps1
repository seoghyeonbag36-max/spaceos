# 건물 공실 대장 수집을 **완료될 때까지** 반복 실행한다.
#
# 왜 필요한가 (2026-07-27):
#   수집기는 스스로 죽는 경우가 많다 — 연속 실패 시 자체 중단, 노트북 절전으로 정지,
#   Wi-Fi 끊김. 그때마다 사람이 배치를 다시 눌러야 했다. 진행분은 150동마다 gold 에
#   저장되고 재실행이 완료분을 건너뛰므로, 재실행 자체는 안전하게 반복할 수 있다.
#   이 스크립트는 그 "다시 누르기"를 없앤다.
#
# 완료 판정: 재실행했을 때 '대장 대상 0동' 이면 그 거점은 남은 게 없다는 뜻이다.
#   종료코드로는 판정할 수 없다 — 쿼터 소진으로 중간에 끊겨도 부분 저장 후 0 으로 끝난다.
#
# 무한 루프 방지: 한 패스에서 gold 총 동수가 전혀 늘지 않으면 더 돌려도 소용없다
#   (쿼터 소진, 네트워크 단절, 영구 실패 건물). 그 자리에서 멈추고 사유를 남긴다.
#
# 사용:
#   powershell -ExecutionPolicy Bypass -File scripts\run_bldgvac_until_done.ps1 euljiro hongdae
#   powershell ... -File scripts\run_bldgvac_until_done.ps1 -MaxPasses 20 hongdae
#
# 전원 주의: 반드시 AC 연결 상태로 돌릴 것 — 배터리 구동은 약 7배 느리고, 덮개를 닫으면
#   절전으로 프로세스가 얼어붙는다(이 스크립트도 같이 언다).

# Position=0 을 명시해야 한다 — ValueFromRemainingArguments 파라미터는 위치 바인딩에서
# 제외되므로, 빼면 첫 인자('hongdae')가 -MaxPasses 로 가서 int 변환 오류가 난다.
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Hubs,

    [int]$MaxPasses = 10
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot      # scripts\.. = spaceos
$log  = Join-Path $root 'data\logs\bldgvac-resume.log'
$gold = Join-Path $root 'data\gold'

if (-not $Hubs -or $Hubs.Count -eq 0) {
    Write-Host "거점을 하나 이상 지정하십시오. 예: run_bldgvac_until_done.ps1 euljiro hongdae"
    exit 2
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null

function Write-Log([string]$Text) {
    # 로그를 못 써도 수집은 계속한다. 로그 파일은 tail -f 같은 감시 도구가 붙들고 있을 수
    # 있고($ErrorActionPreference='Stop' 이라 그대로 두면 배너 한 줄 때문에 수집 전체가
    # 죽는다 — 2026-07-27 에 실제로 그랬다), 기록 실패는 수집 실패가 아니다.
    try { Add-Content -Path $log -Value $Text -Encoding utf8 -ErrorAction Stop } catch { }
    Write-Host $Text
}

function Get-GoldTotal {
    # 지정 거점들의 gold 총 동수. 파일이 없거나 깨졌으면 0 으로 친다(진행 판정용 근사).
    $sum = 0
    foreach ($h in $Hubs) {
        $p = Join-Path $gold "$h\building_vacancy.json"
        if (Test-Path $p) {
            try {
                # 반드시 변수에 먼저 받는다. PS 5.1 의 ConvertFrom-Json 은 배열을 파이프라인에
                # 풀어놓지 않고 통째로 1개 객체로 내보내므로, @(... | ConvertFrom-Json).Count 는
                # 원소 수가 아니라 항상 1 이 된다. 그러면 '진행 0동' 오판으로 매 첫 패스가
                # 중단된다(2026-07-27 garosugil 에서 실제 발생 — 720→1092 를 1→1 로 읽었다).
                $data = Get-Content $p -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($null -ne $data) { $sum += @($data).Count }
            } catch { }
        }
    }
    return $sum
}

$python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }

# 파이썬 출력을 UTF-8 로 주고받는다.
#
#   PS 5.1 은 네이티브 명령의 stdout 을 [Console]::OutputEncoding(기본 CP949)으로 디코딩한다.
#   파이썬이 뱉은 UTF-8 바이트가 CP949 로 잘못 해석돼 mojibake 문자열이 되고, 그걸 그대로
#   로그에 쓰면 "湲곗〈 stores_raw" 같은 깨진 줄이 남는다(2026-07-27 실제 발생).
#   기존 .bat 은 `>>` 로 바이트를 그대로 흘려서 이 문제가 없었다 — PowerShell 로 옮기면서
#   생긴 회귀다. 데이터(gold/bronze)는 파이썬이 직접 UTF-8 로 쓰므로 영향 없고 로그만 깨진다.
$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$before = Get-GoldTotal

for ($pass = 1; $pass -le $MaxPasses; $pass++) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Log "=== $stamp : until-done pass $pass/$MaxPasses — $($Hubs -join ' ') ==="

    # 로그는 StreamWriter 로 한 번만 열어 UTF-8 로 쓴다.
    #   - Tee-Object 는 쓰면 안 된다: PS 5.1 의 Tee-Object 에는 -Encoding 이 없고 UTF-16LE
    #     로 써서 로그를 깨뜨린다(2026-07-27 에 실제로 깨뜨렸다).
    #   - 줄마다 Add-Content 도 안 된다: 파일을 수천 번 열고 닫아 느리고 락 경합이 잦다.
    # 로그를 못 열면(감시 도구가 붙들고 있는 등) 화면 출력만으로 계속 진행한다.
    $sw = $null
    try { $sw = [System.IO.StreamWriter]::new($log, $true, [System.Text.UTF8Encoding]::new($false)) }
    catch { Write-Host "[until-done] 경고: 로그를 열 수 없어 화면에만 출력합니다 — $($_.Exception.Message)" }

    Push-Location $root
    try {
        $out = & $python -u -m data.collectors.building_vacancy @Hubs 2>&1 | ForEach-Object {
            $line = "$_"
            if ($sw) { $sw.WriteLine($line); $sw.Flush() }
            Write-Host $line
            $line
        }
    } finally {
        Pop-Location
        if ($sw) { $sw.Dispose() }
    }

    # 이번 패스가 각 거점에서 몇 동을 대상으로 잡았나 — 전부 0 이면 남은 일이 없다.
    $todo = @([regex]::Matches(($out -join "`n"), '대장 대상 (\d+)동') |
              ForEach-Object { [int]$_.Groups[1].Value })

    if ($todo.Count -gt 0 -and ($todo | Measure-Object -Sum).Sum -eq 0) {
        $msg = "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : until-done 완료 — 전 거점 잔여 0동 (pass $pass) ==="
        Write-Log $msg
        exit 0
    }

    $after = Get-GoldTotal
    if ($after -le $before) {
        $msg = "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : until-done 중단 — pass $pass 에서 진행 0동" +
               " (gold $before → $after). 쿼터/네트워크/영구실패 의심, 사람이 볼 것 ==="
        Write-Log $msg
        exit 1
    }
    Write-Host "[until-done] pass $pass 진행: gold $before → $after (+$($after - $before)동)"
    $before = $after
}

$msg = "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : until-done 중단 — MaxPasses($MaxPasses) 소진, 아직 미완료 ==="
Write-Log $msg
exit 1

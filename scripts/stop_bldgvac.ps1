# 건물 공실 대장 수집을 즉시 중단한다 — 2026-07-27 18:30 Wi-Fi 차단 예정에 맞춘 일회용 스크립트.
#
# PID 를 박지 않는다. 오늘 PID 는 4224 지만 예약 실행까지 몇 시간이 뜨고, 그 사이 프로세스가
# 정상 종료한 뒤 같은 PID 가 무관한 프로그램에 재사용될 수 있다. 커맨드라인으로 식별한다.
#
# 부모 cmd.exe 는 죽이지 않는다 — python 이 죽으면 배치가 EXIT= 줄을 로그에 남기고 스스로 끝난다.
#
# 진행분은 사라지지 않는다: _save_ledger 가 150동마다 gold/{slug}/building_vacancy.json 을
# 갱신하고, 재실행 시 그 파일을 읽어 완료된 bdMgtSn 을 건너뛴다. 손실은 마지막 체크포인트
# 이후 진행분(최대 149동)뿐이다.

$log = 'c:\Users\USER\Documents\Claude\Projects\SpaceOS\spaceos\data\logs\bldgvac-resume.log'
$ts  = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

$procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -like '*building_vacancy*' })

if ($procs.Count -gt 0) {
    foreach ($p in $procs) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    $msg = "=== $ts : 18:30 예정 중단 — building_vacancy $($procs.Count)개 종료(Wi-Fi 차단). 재개: scripts\run_bldgvac_resume.bat hongdae ==="
} else {
    $msg = "=== $ts : 18:30 중단 스케줄 — 실행 중인 building_vacancy 없음(이미 완료). 조치 없음 ==="
}

Add-Content -Path $log -Value $msg -Encoding utf8

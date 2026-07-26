@echo off
REM 건물 공실 대장 수집 재개 — 세션과 분리된 독립 프로세스로 실행(터미널을 닫아도 생존).
REM 재개 가능: 150동마다 체크포인트 저장 + 기존 완료 bdMgtSn 스킵 + 429 강등분 자동 재시도.
REM
REM 경로는 이 배치 파일 위치(%~dp0)에서 파생한다 — 절대경로를 박으면 다른 PC 에서 못 쓴다.
REM 인터프리터는 PYTHON 환경변수로 지정할 수 있고, 없으면 PATH 의 python 을 쓴다.
REM
REM 사용: scripts\run_bldgvac_resume.bat [거점 ...]   (거점 생략 시 전 거점)
REM   예: scripts\run_bldgvac_resume.bat euljiro hongdae
REM
REM 진행 감시:
REM   python scripts\watch_collection.py --log data\logs\bldgvac-resume.log ^
REM       --mode bldgvac --expect euljiro,hongdae

setlocal
cd /d "%~dp0.."
if "%PYTHON%"=="" set PYTHON=python
set LOG=data\logs\bldgvac-resume.log
if not exist data\logs mkdir data\logs

echo === %DATE% %TIME% : building_vacancy %* >> "%LOG%"
"%PYTHON%" -u -m data.collectors.building_vacancy %* >> "%LOG%" 2>&1
echo EXIT=%ERRORLEVEL% >> "%LOG%"
endlocal

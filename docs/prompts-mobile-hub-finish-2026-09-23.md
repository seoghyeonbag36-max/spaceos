# 모바일 프롬프트 — 서울 3·4차 15거점 체인 마무리 (2026-09-23 오전)

**언제 쓰나**: 09-22 밤에 무인으로 걸어 둔 체인(층별개요 → 파이프라인)이 끝났는지 확인하고,
안 끝났으면 남은 것만 이어서 끝낸 뒤, 등록 머지 조건까지 얼마나 남았는지 **재기만** 하는 날.
[09-21 프롬프트](prompts-mobile-hub-quota-2026-09-21.md)의 5·6단계를 이어받는다.

**경로**: **데스크톱 Dispatch 전용.** 클라우드 세션은 `.env` 키와 `data/bronze` 가 없어
시작조차 못 한다([PlaceOS_Mobile_Dispatch_Prompts.md](../PlaceOS_Mobile_Dispatch_Prompts.md) §0).
노트북이 켜져 있고 AC 가 꽂혀 있어야 한다.

## 09-22 밤 기준 상태 — 이 프롬프트의 출발점

| 단계 | 상태 (09-22 22:45) |
|---|---|
| 전유부(대장) | **15/15 완주** · 11,311동 · 429 강등 0 — 내일 이 15거점에 쓸 전유부 콜은 없다 |
| 층별개요 | 22:09 시작 → **22:35 노트북 강제 종료로 중단**(poi·bangbang·ydp-gucheong 완료, daerim 350/528) → 22:43 재개 |
| 파이프라인·앵커 | 층별개요 뒤 자동 · 예상 완료 AC 면 **09-23 00:30~01:30**(배터리면 더 늦다) |
| 무인 스크립트 | PID 23424 (22:43 재기동) · 로그 `data/logs/publish-gold-2026-09-22.log` — 층별개요 → 파이프라인 → **행정동 구역** → Gold 를 **PR #39 브랜치**(`feat/seoul-hubs-batch3-4-20260921`)에 커밋·push(별도 worktree 에서). 마지막 줄 `PUSH ok`/`PUSH fail` 다음 `END` |
| (폐기) | 첫 체인 PID 29724 · `finish-chain-2026-09-22.log` — 22:35 강제 종료로 죽었다. 이 로그는 끝이 없다 |
| git | 이 작업트리(현재 브랜치)에는 커밋 안 함. 등록(`page_hubs.py` 의 `SEOUL_BATCH3_HUBS`·`SEOUL_BATCH4_HUBS`)은 여기서는 **미커밋**, PR #39 브랜치에는 같은 내용이 커밋돼 있다 |

노트북이 꺼져 있는 날은 [클라우드 프롬프트](prompts-cloud-hub-verify-2026-09-23.md)를 쓴다 — PR #39 브랜치의 Gold 로 판정만 한다.

## 09-21 프롬프트와 다른 곳

1. **작업이 사라지면 재부팅부터 본다.** 09-22 밤 무인 작업이 두 번 죽었는데 원인은 세션이 아니라
   **노트북 재부팅**이었다 — 21:57 시작 메뉴 '다시 시작'(이벤트 1074), 22:35 **전원 버튼 길게 누름**
   강제 종료(이벤트 41 `LongPowerButtonPressDetected`). 어떤 띄우는 방식도 재부팅은 못 버티므로 모든 단계를
   **산출물로 재개**한다(2단계 `--check`). 긴 작업은 세션 밖(WMI)으로 띄운다 — 아래 두 명령 형태는
   09-22 22:2x 에 WMI 로 실제 띄워 python·cwd·`PYTHONIOENCODING`·리다이렉트를 확인했다.
       (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
2. until-done 의 **"진행 0동" 중단은 강등분 재수집에서 정상이다** — 행을 교체할 뿐 동수가 늘지 않는다.
   완주는 로그가 아니라 산출물(행 수 == 후보 수 · `rate_limited` 0)로 판정한다.
3. **이미 `anchor` 인 거점에는 층별개요를 다시 돌리지 않는다.** 층별개요는 `building_vacancy.json` 을
   제자리 갱신하므로 파이프라인을 다시 돌려야 하는데, `run_hub_chain_batch.py` 는 `anchor` 거점을 건너뛴다.
   받아 온 값이 서빙 숫자에 안 닿는다.

---

## 짧은 버전 — 폰에서는 이것만 입력해도 된다

```
[데스크톱 Dispatch] 작업 루트는 spaceos/ 다(상위 SpaceOS/ 에서 열렸으면 cd spaceos). spaceos/docs/prompts-mobile-hub-finish-2026-09-23.md 의 "프롬프트" 블록을 읽고 그대로 수행해. 응답은 한국어.
```

⚠ **커밋·push 는 필요 없다.** Dispatch 는 켜져 있는 이 노트북의 작업트리에 그대로 붙는다 —
이 문서가 미추적이어도 보인다. 클라우드 세션(`origin/main` 클론)은 push 해도 `.env`·bronze 가
없어 이 작업을 못 하므로, push 가 이 작업을 가능하게 해 주는 경로는 없다.

## 프롬프트 (그대로 붙여넣기)

```
[데스크톱 Dispatch 전용] 서울 3·4차 15거점의 어젯밤(09-22) 체인을 마무리한다.
작업 루트는 spaceos/ 다. 응답은 한국어.

대상 15거점 — 이 목록만 쓴다:
  공백: bangbang gildong nowon gurodigital ydp-gucheong seochoyeok poi dogok yangjae jamsil-tour daerim guui maebong gurojeonhwa bonseobu
  쉼표: bangbang,gildong,nowon,gurodigital,ydp-gucheong,seochoyeok,poi,dogok,yangjae,jamsil-tour,daerim,guui,maebong,gurojeonhwa,bonseobu

## 전제 — 아니면 멈춘다
- 이 세션이 내 노트북에 붙은 Dispatch 세션인지 본다:
    test -f .env && ls data/bronze | head -1
  둘 중 하나라도 없으면 클라우드 세션이다. 아무것도 하지 말고 그렇다고만 보고한다.
- /quota 스킬과 docs/prompts-mobile-hub-quota-2026-09-21.md 를 먼저 읽는다. 충돌하면 이 프롬프트를 따른다.
- 배터리 구동이면 나에게 "AC 연결해 주세요" 한 줄을 보내고 그대로 진행한다.

## 1. 어젯밤 체인이 아직 도는가
    tail -n 8 data/logs/publish-gold-2026-09-22.log
    powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"
    powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'finish_publish|finish_chain|building_vacancy|floor_capacity|run_hub_chain_batch|run_bldgvac|build_district_zones' } | Select-Object ProcessId,CommandLine | Format-List"
- 부팅 시각이 09-22 22:43 보다 뒤인데 END 줄이 없으면 또 재부팅으로 죽은 것이다 → 2단계부터 산출물로 이어간다.
- publish-gold 로그에 "PUSH ok" 줄이 있으면 어젯밤 Gold 가 PR #39 에 올라갔다. "PUSH fail" 이면 보고에 그 줄을 옮긴다
  (push 를 다시 시도하지 말 것 — 내가 정한다).
- 프로세스가 하나라도 살아 있으면 **아무것도 새로 띄우지 않는다.** Monitor 를 하나 걸고 END 줄을 기다린다:
    tail -n 0 -f data/logs/publish-gold-2026-09-22.log data/logs/floor-capacity.log data/logs/hub-chain-batch.log | grep -E --line-buffered "^\[20|회수율|✓|✗|배치 완료|배터리|Traceback"
- 로그에 END 줄이 있거나 프로세스가 없으면 2단계로 간다.

## 2. 산출물로 판정한다
    python scripts/run_hub_chain_batch.py --check --hubs <쉼표 목록>
- 15개 전부 anchor → 4단계로.
- stores 가 하나라도 있으면 **멈추고 보고한다.** 전유부는 09-22 에 15/15 완주했다 —
  stores 라면 무언가 지워졌거나 점포가 다시 받혔다는 뜻이다. 추측해서 고치지 말 것.
- ledger 또는 master 가 있으면 3단계로.

## 3. 남은 것만 이어서 — 세션 밖(WMI)으로 띄운다
세션 안 백그라운드는 세션과 같이 죽는다. 재부팅은 어떤 방식도 못 버티니, 죽으면 2단계부터 다시 판정한다.

### 3-a. 층별개요 — 2단계에서 ledger/master 였던 거점만
    python scripts/quota_preflight.py
출력의 "→ python -m data.collectors.floor_capacity ..." 줄(--only-approx 가 붙은 줄도)에서
**2단계에서 ledger/master 였던 거점만** 남긴다. anchor 인 거점은 뺀다. 남는 거점이 없으면 3-b 로.
줄이 두 개면 하나씩, 앞의 프로세스가 끝난 뒤에 다음을 띄운다.

    $root='C:\Users\USER\Documents\Claude\Projects\SpaceOS\spaceos'
    $a='<그 줄의 인자 — --only-approx 가 있으면 앞에 포함, 거점은 공백 구분>'
    $cmd='powershell.exe -NoProfile -ExecutionPolicy Bypass -File "'+$root+'\scripts\keep_awake.ps1" -Command "python -u -m data.collectors.floor_capacity '+$a+' >> data\logs\floor-capacity.log 2>&1"'
    $r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$cmd; CurrentDirectory=$root}
    "ret=$($r.ReturnValue) pid=$($r.ProcessId)"

- ret 가 0 이 아니거나, 30초 안에 floor-capacity.log 에 "대상 N동" 새 줄이 안 찍히면 멈추고 보고한다.
- $a 를 비우지 말 것. 거점 인자가 없으면 floor_capacity 는 garosugil 로 폴백한다.
- Monitor: tail -n 0 -f data/logs/floor-capacity.log | grep -E --line-buffered "회수율|대상 [0-9]|포기합니다|Traceback"
- 거점마다 "회수율 …%" 줄을 보고한다. 끝났는지는 위 pid 가 사라졌는지로 본다.

### 3-b. 파이프라인 — 층별개요 프로세스가 끝난 뒤에만
2단계 --check 를 다시 돌려 ledger/master 인 거점만 쉼표로 모은다.

    $csv='<ledger/master 거점, 쉼표 구분>'
    $cmd='cmd.exe /c "set "PYTHONIOENCODING=utf-8" && python -u scripts\run_hub_chain_batch.py --hubs '+$csv+' > data\logs\hub-chain-finish.out 2>&1"'
    $r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$cmd; CurrentDirectory=$root}
    "ret=$($r.ReturnValue) pid=$($r.ProcessId)"

- 이 스크립트는 절전 억제를 스스로 건다. keep_awake 로 감싸지 않는다.
- set "PYTHONIOENCODING=utf-8" 의 따옴표를 빼지 말 것 — 빼면 값 끝에 공백이 붙는다.
- Monitor: tail -n 0 -f data/logs/hub-chain-batch.log | grep -E --line-buffered "✓|✗|배치 완료|배터리|Traceback"
- 거점당 2.5~7분. 끝나면 2단계를 다시 돌려 15개 전부 anchor 인지 확인한다.

## 4. 검증 — 읽기만 한다 (API 0콜)
    python scripts/chain_status.py bangbang gildong nowon gurodigital ydp-gucheong seochoyeok poi dogok yangjae jamsil-tour daerim guui maebong gurojeonhwa bonseobu
- 거점별 N/9 와 막힌 단계를 표로 보고한다. "서빙등재"가 [!!] 여도 고치지 않는다 — 공개는 내가 정한다.
- 공개 전 확인 5거점 — poi · seochoyeok · yangjae · maebong · dogok. 공실 많음(high) 비율이 높게 나온 서초·강남 남부 권역이다:
    python -m data.analyze_anchor_population --rebuild poi seochoyeok yangjae maebong dogok
  --rebuild 를 빼지 말 것(빼면 옛 사이드카를 읽어 B·C·D·E 열이 0.0% 로 나온다). 거점당 수 분.
  R-ONE 과는 **C(용도 정렬) 열로** 비교한다. A(현행) 열은 집합상가를 포함해 부푼 값이라 인용하지 않는다.
  다섯 곳 모두 R-ONE **공유 매핑**이라(rone_districts.SHARED_RONE) 앵커가 인접 상권 표본이라는 점을 같이 적는다.
  calibration.json 의 gap_pp 는 인용하지 않는다(혼합 추정 기준이다).

## 5. 등록 머지까지 남은 거리 — 재기만 한다
15거점이 전부 anchor 일 때만 돌린다.
    python -m data.pipelines.build_district_zones bangbang gildong nowon gurodigital ydp-gucheong seochoyeok poi dogok yangjae jamsil-tour daerim guui maebong gurojeonhwa bonseobu
    python -m pytest data/tests -q
- build_district_zones 는 거점을 반드시 명시한다(비우면 ACTIVE_HUBS 전부를 돈다).
  어젯밤 후속 스크립트가 이미 만든 거점(district_zones.json 있음)은 빼도 된다 — 입력이 같아 결과가 같다.
- pytest 실패 수와 실패한 테스트 이름을 보고한다. 09-21 실측은 47건 실패였다
  (test_district_zones 45+1 · Page 진행률 100→88.9 1건). 오늘 몇 건으로 줄었는지가 핵심이다.
- build_gold · refresh_platform (Program·Platform Gold)은 돌리지 않는다. 전 거점 CSV 를 다시 쓰고
  뒤에 와야 하는 빌더 순서가 있다. 남은 실패가 그쪽이면 보고에 "다음 한 수"로만 적는다.

## 보고 규칙
- Monitor 통보는 보고 전에 로그로 대조한다(통보가 로그에 없는 시각·값으로 온 적이 있다). 로그에 없는 값은 보고하지 않는다.
- 503 한 줄은 보고하지 않는다. "연속 실패"·"포기합니다"·Traceback 은 보고한다.

## 끝낼 때
1. 내가 띄운 프로세스가 남아 있지 않은지 확인한다(1단계의 Get-CimInstance 명령).
2. 보고한다:
   - 15거점 chain_status N/9 표
   - 층별개요 거점별 회수율 (어젯밤분은 floor-capacity.log 의 "회수율" 줄)
   - 앵커 5거점: C열 공실률 vs R-ONE · high 비율
   - pytest data/tests: 실패 수와 대표 원인, 09-21(47건) 대비
   - 막힌 것: 전원 / 네트워크 / 산출물 이상 / 기타

## 하지 말 것
1. 전유부 수집. 15거점은 끝났다. 경기 보류 13거점(bamgasi 등)에도 쓰지 않는다 — 쓸지는 내가 정한다.
2. git commit · push · 브랜치 전환 · stash · worktree 추가/삭제. 등록 변경이 현재 브랜치 작업트리에 미커밋으로 있다.
   push 하면 Gold 가 선 거점이 그대로 프로덕션(placeos.web.app)에 뜬다.
3. 거점 등록 · SERVED_CITIES · seoul_pages.DISTRICTS 수정.
4. 층별개요와 다른 수집기 동시 실행. 429 는 키 단위라 서로를 죽인다.
5. 세션 안 백그라운드로 긴 작업 띄우기. scripts/run_batch3_chain.sh · run_batch4_after.sh 사용.
6. 모르는 게 나오면 추측해서 채우지 말고 멈추고 물어본다.
```

---

## 사용자 메모 (프롬프트 밖)

- **밤새 할 일은 없다.** AC 만 꽂아 두면 된다 — AC 절전 타임아웃은 08-25 부터 '안 함'이고,
  체인은 끝날 때까지 스스로 절전을 막는다. 아침에 Dispatch 가 붙으려면 노트북이 깨어 있어야 한다.
- **예상 소요**
  - 체인이 밤사이 끝났으면: 1 → 2(전부 anchor) → 4·5 만. **약 30~60분**(앵커 5거점 수 분씩 + 구역 빌드 + pytest).
  - 체인이 중간에 죽었으면 3단계가 더해진다: 층별개요 최대 40분 + 파이프라인 거점당 2.5~7분.
- **이 프롬프트가 끝나도 머지는 아니다.** 머지 조건은 15거점 Gold 완비 → `pytest data/tests` 녹색 →
  등록과 Gold 를 한 커밋으로(09-21 메모). Program·Platform Gold(`/gold-build`)와 커밋·공개 결정이 남는다.
- **전유부 쿼터**: 09-23 에도 서울 15거점 몫은 0 이다. 하루치 10,000콜을 쓸 수 있는 곳은
  서빙 보류 중인 경기 13거점(점포는 받았고 대장 0동)뿐이다. 쓰려면 이 프롬프트와 별도로 지시할 것.

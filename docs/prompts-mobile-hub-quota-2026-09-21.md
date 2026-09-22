# 모바일 프롬프트 — 건축HUB 하루치 전유부로 거점 돌리기 (2026-09-21)

**언제 쓰나**: 등록은 됐는데 대장(전유부)이 덜 받힌 거점이 있을 때, 폰에서 하루치 쿼터를
태우고 싶을 때. 2026-09-21 기준 대상은 서울 3·4차 15거점(`SEOUL_BATCH3_HUBS` ·
`SEOUL_BATCH4_HUBS`)이다.

**경로**: **데스크톱 Dispatch 전용.** 클라우드 세션은 `.env` 키와 `data/bronze` 가 없어
시작조차 못 한다([PlaceOS_Mobile_Dispatch_Prompts.md](../PlaceOS_Mobile_Dispatch_Prompts.md) §0).
노트북이 켜져 있고 AC 가 꽂혀 있어야 한다(배터리면 2~7배 느리다).

> **2026-09-22 실측 보강.** 클라우드에서 넷을 직접 쳐 보니 막는 이유가 둘이 아니라 **넷**이었다 —
> 위 둘에 더해 ③ 프록시 egress 허용목록에 `apis.data.go.kr` 가 없어 콜이 나가지 못하고(403),
> ④ 15거점 Gold 가 0개라 **키를 줘도** 09-20 에 받은 것을 처음부터 다시 받는 일이 된다.
> ④ 때문에 "키 없이 돌릴 수 있는 잔여 단계"(§6 파이프라인·앵커)도 클라우드에서는 없다.
> → [finding-cloud-expos-blocked-2026-09-22.md](finding-cloud-expos-blocked-2026-09-22.md)

**이 프롬프트가 기존 런북과 다른 곳** — 09-20 수집에서 확인한 넷을 반영했다:

1. 프리플라이트의 "전유부 미수집 N거점"은 **0동인 거점만** 센다. 잘린 대장
   (daerim 559/896)을 놓친다 → 대상은 산출물(`ledger_gap`)로 센다.
2. `run_hub_chain_batch.py` 는 수집기 출력을 `capture_output` 으로 삼킨다 → 150동
   체크포인트도 소진 신호도 안 보인다 → 전유부는 `run_bldgvac_until_done.ps1` 로 돌린다.
3. 같은 배치 러너는 이미 `ledger` 단계인 거점에 **층별개요를 건너뛴다**(`stores` 분기에만
   있다) → 층별개요를 따로 돌린 뒤 배치 러너로 파이프라인만 민다.
4. Monitor 통보가 로그에 없는 시각·값으로 여러 번 왔다(미래 시각 포함) → 보고 전에 로그로 대조한다.

---

## 프롬프트 (그대로 붙여넣기)

```
[데스크톱 Dispatch 전용] 건축HUB 하루치 전유부로 서울 신규 거점 수집을 진행한다.
작업 루트는 spaceos/ 다. 응답은 한국어.

## 전제 — 먼저 확인하고, 아니면 멈춘다
- 이 세션이 내 노트북에 붙은 Dispatch 세션인지 본다:
    test -f .env && ls data/bronze | head -1
  둘 중 하나라도 없으면 클라우드 세션이다. 수집이 불가능하니 아무것도 하지 말고 그렇다고만 보고한다.
- /quota 스킬을 먼저 읽는다. 아래는 그 위에 얹은 오늘의 절차이고, 충돌하면 이 프롬프트를 따른다.
- 대상은 data/config/page_hubs.py 의 SEOUL_BATCH3_HUBS + SEOUL_BATCH4_HUBS 다. 새 거점을 등록하지 않는다.

## 0. 프리플라이트
    python scripts/quota_preflight.py
- [중단] 이 하나라도 있으면 시작하지 않고 보고한다.
- 쿼터 429 = 아직 안 열렸다. 30분 간격으로 최대 4회 다시 본다. 계속 429면 보고하고 끝낸다.
- 쿼터 503 = 서버 장애지만 시작해도 된다. 09-20 에 503 이 44회 났어도 전부 1연속이라 수집기가 재시도로 넘겼다.
- 배터리 구동이면 나에게 "AC 연결해 주세요" 한 줄을 보내고 그대로 진행한다.
- 프리플라이트의 "전유부 미수집 N거점"을 대상 목록으로 쓰지 말 것. 0동인 거점만 세서 잘린 대장을 놓친다.

## 1. 오늘 몫 — 산출물로 센다
    PYTHONIOENCODING=utf-8 python -c "
    import sys,json; sys.path[:0]=['.','scripts']
    from pathlib import Path
    from run_hub_chain_batch import stage_done
    from data.collectors.building_vacancy import group_by_building
    from data.collectors.common import load_latest
    from data.config.page_hubs import SEOUL_BATCH3_HUBS as A, SEOUL_BATCH4_HUBS as B
    tot=0
    for s in [*A,*B]:
        g=Path('data/gold')/s/'building_vacancy.json'
        got=json.loads(g.read_text(encoding='utf-8')) if g.exists() else []
        rl=sum(1 for r in got if r.get('capacity_method')=='rate_limited')
        st=load_latest(s,'stores_raw.json')
        c=len(group_by_building(st)) if st else None
        need=(c-len(got)+rl) if c is not None else None
        tot+=need or 0
        print(f'{s:14s}{stage_done(s):8s}후보 {c}  받음 {len(got)}  강등 {rl}  오늘몫 {need if need is not None else \"점포먼저\"}')
    print(f'합계 {tot:,}동 · 하루 예산 약 8,000동')
    " 2>&1 | grep -v '^\[group\]'

- "점포먼저" 거점은 폴리곤·점포부터 받는다(건축HUB 콜 0):
    python -m data.collectors.vworld_bldg <slug>
    python -m data.collectors.building_vacancy <slug> --no-ledger
  받은 뒤 스니펫을 다시 돌려 오늘몫을 채운다.
- 하루 예산은 약 8,000동이다(09-20 실측: 8,103동째에 전유부 10,000콜 소진). 합이 넘으면 뒤쪽 거점은 내일로 뺀다.
- 순서:
  ① 단계 stores 이면서 받음 > 0 (잘린 대장) — 먼저 채운다
  ② 받음 0 인 거점 — 후보 동수 오름차순 (남은 쿼터로 완주 거점 수를 최대화)
  ③ 단계 ledger 인데 강등 > 0 — 재실행하면 강등분만 다시 받는다
  오늘몫 0 인 거점은 넣지 않는다.
- 정한 순서와 합계를 나에게 보고하고 2단계로 간다.

## 2. 전유부 — 세션 밖에 띄운다
세션 안 백그라운드는 세션이 끝나면 같이 죽는다(09-20 에 한 번 당했다). PowerShell 로 분리한다:

    $root='C:\Users\USER\Documents\Claude\Projects\SpaceOS\spaceos'
    $hubs='<1단계 순서 그대로, 공백 구분>'
    $env:PYTHONIOENCODING='utf-8'
    $ka=Start-Process powershell.exe -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "'+$root+'\scripts\keep_awake.ps1"') -WorkingDirectory $root -WindowStyle Hidden -PassThru
    $bv=Start-Process powershell.exe -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "'+$root+'\scripts\run_bldgvac_until_done.ps1" -MaxPasses 20 '+$hubs) -WorkingDirectory $root -WindowStyle Hidden -PassThru
    "keep_awake=$($ka.Id) until_done=$($bv.Id)"

- -ArgumentList 는 따옴표를 보존한 단일 문자열이다. 배열로 넘기면 인자가 쪼개져 조용히 즉시 끝난다.
- 30초 안에 둘을 확인한다: $bv.HasExited 가 False 인가 · data/logs/bldgvac-resume.log 에
  "대장 대상" 줄이 새로 찍혔는가. 하나라도 아니면 멈추고 보고한다.
- 두 PID 를 기억해 둔다. 끝날 때 keep_awake 를 직접 꺼야 한다.
- run_hub_chain_batch.py 로 전유부를 돌리지 말 것. 수집기 출력을 삼켜 체크포인트도 소진 신호도 안 보인다.

## 3. 보고 — 150동마다, 거점마다
Monitor 를 하나만 건다:
    tail -n 0 -f data/logs/bldgvac-resume.log | grep -E --line-buffered "checkpoint:|\[gold:|대장 대상|쿼터 소진|포기합니다|연속 실패|until-done|Traceback"
30분 만료되면 같은 명령으로 다시 건다. 두 개가 겹치면 같은 줄이 두 번 온다 — 새로 걸기 전에 이전 것을 끈다.

- 보고 전에 반드시 로그로 대조한다. 통보가 로그에 없는 시각·값으로 오는 일이 있었다(미래 시각 포함):
    grep "checkpoint:<slug>" data/logs/bldgvac-resume.log | tail -1
  로그에 없는 값은 보고하지 않는다.
- 150동 체크포인트: 거점 · N/전체 · 로그 시각 · 직전 150동 소요 · 예상 완료 시각
- 거점 완료([gold:]): 동수 · 소요 · status 분포 · capacity 방식(rate_limited · floor_approx 특히) · 오늘 누적 동수
- 503 한 줄은 보고하지 않는다. "연속 실패" 가 찍히면 보고한다.

## 4. 쿼터가 소진되면
"쿼터 소진" 또는 "포기합니다" 가 찍혀도 수집기는 안전하게 멈춘다 — 그 거점은 받은 데까지 저장하고,
같은 실행의 다음 거점들은 첫 건물 전에 중단해 아무것도 쓰지 않는다. until_done 은 다음 패스에서
진척이 0 이면 스스로 끝난다.
1. 기다린다. until_done 이 10분 안에 안 끝나면 Stop-Process -Id <until_done PID>.
2. 소진 사실과 멈춘 거점·동수를 보고한다.
3. 5단계(층별개요)는 쿼터가 따로라 그대로 진행한다.

## 5. 층별개요 — 전유부 프로세스가 끝난 뒤에만
전유부와 층별개요를 동시에 돌리면 429 가 키 단위라 서로를 죽인다. $bv.HasExited 가 True 인지 먼저 본다.
    python scripts/quota_preflight.py
출력의 "→ python -m data.collectors.floor_capacity ..." 줄에서 거점 목록을 그대로 가져온다.
손으로 목록을 만들지 않는다 — 프리플라이트가 미시도 건물이 있는 거점만 골라 준다.
    $slugs='<그 줄의 거점들>'
    $fc=Start-Process python -ArgumentList ('-u -m data.collectors.floor_capacity '+$slugs) -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput "$root\data\logs\floor-capacity.log" -RedirectStandardError "$root\data\logs\floor-capacity.err"
- floor_capacity 는 거점을 반드시 명시한다. 비우면 garosugil 로 폴백한다.
- Monitor: tail -n 0 -f data/logs/floor-capacity.log | grep -E --line-buffered "회수율|저장|포기합니다|Traceback"
- 거점마다 로그의 "회수율 …%" 줄을 보고한다.

## 6. 파이프라인·앵커 — 대장과 층별개요가 끝난 거점만 (건축HUB 콜 0)
    python scripts/run_hub_chain_batch.py --check --hubs <15거점 쉼표 구분>
단계가 ledger 인 거점만 고른다. stores 인 거점(대장 잘림)은 넣지 않는다 — 대장부터 다시 받으려 해
쿼터를 치고, 잘린 분모로 공실률을 만든다.
    $csv='<ledger 인 거점, 쉼표 구분>'
    $pb=Start-Process python -ArgumentList ('-u scripts\run_hub_chain_batch.py --hubs '+$csv) -WorkingDirectory $root -WindowStyle Hidden -PassThru
- 이 스크립트는 절전 억제를 스스로 건다. keep_awake 로 감싸지 않는다.
- ledger 단계에서는 건물속성 → 분모 재계산 → Page 마스터 → 공실유닛 → 앵커 보정만 돈다.
- Monitor: tail -n 0 -f data/logs/hub-chain-batch.log | grep -E --line-buffered "✓|✗|배치 완료|배터리"
- 끝나면 거점마다 확인한다: python scripts/chain_status.py <slug>
- ⚠ Page 마스터가 생기는 순간 그 거점은 로컬 서빙 목록에 자동으로 오른다(measured_pages._is_measured).

## 끝낼 때
1. keep_awake 를 끈다: Stop-Process -Id <keep_awake PID>
2. 보고한다:
   - 오늘 받은 전유부 동수 · 거점별 완주 여부
   - 층별개요 거점별 회수율
   - 거점별 chain_status 단계 (N/9)
   - 막힌 것: 쿼터 / 503 / 전원 / 기타
   - 내일 이어받을 거점과 1단계 스니펫 결과

## 하지 말 것
1. 전유부·층별개요 동시 실행. 5연속 429 면 그 실행 내내 엔드포인트를 포기해 하루치를 버린다.
2. git commit · git push. push 하면 Gold 가 선 거점이 그대로 프로덕션(placeos.web.app)에 뜬다.
   신규 거점 공개는 내가 정한다. push 는 GCM 인증 창 때문에 폰에서 끝나지도 않는다.
3. 거점 등록 · SERVED_CITIES · seoul_pages.DISTRICTS 수정.
4. scripts/run_batch3_chain.sh · run_batch4_after.sh 사용. 09-20 임시 스크립트이고 층별개요가 빠져 있다.
5. 모르는 게 나오면 추측해서 채우지 말고 멈추고 물어본다.
```

---

## 사용자 메모 (프롬프트 밖)

- **2026-09-21 기준 예상**: 1단계 합계 약 1,415동 + 점포먼저 2곳(guui ≈1,078 · poi ≈1,235)
  ≈ **3,700동**. 하루 예산 8,000동 안이라 전유부·층별개요·파이프라인까지 하루에 끝날 수 있다.
  분당 25~47동이면 전유부만 1.5~2.5시간이다.
- **끝나면 15거점이 로컬에서 서빙된다.** 프로덕션 공개는 커밋·push 시점이고, 그 결정은
  이 프롬프트가 하지 않는다. 공개 전에 볼 것: 서초·강남 남부 4거점(서초역·양재역·매봉역·도곡동)이
  09-20 에 나란히 `high` 35~39% 로 나왔다 — 앵커 대조 결과로 실제 공실인지 확인할 것.
- **등록(`SEOUL_BATCH3_HUBS`·`SEOUL_BATCH4_HUBS`)은 아직 `main` 에 없다.** 09-21 실측: Gold 없이
  등록만 머지하면 데이터 pytest 가 47건 깨진다 — `test_district_zones` 가 `ACTIVE_HUBS` 전부에
  `district_zones.json` 을 요구하고(45+1), Page 진행률이 100 → 88.9 로 떨어진다(1). 서울 거점은
  등록 즉시 `ACTIVE_HUBS` 에 들어가기 때문이다. 이 프롬프트의 6단계는 Page 마스터·앵커까지만
  세우고 **구역(`build_district_zones`)·Platform·Program Gold 는 세우지 않는다** — 그건 `/gold-build`
  몫이다. 머지 조건: 15거점 Gold 완비 → `python -m pytest data/tests -q` 녹색 → 등록과 Gold 를
  한 커밋으로. 등록 브랜치는 `feat/seoul-hubs-batch3-4-20260921` (draft PR).
- 전유부가 다 끝난 날에도 이 프롬프트를 그대로 쓸 수 있다 — 1단계가 오늘몫 0 을 내면
  5·6단계만 돈다.

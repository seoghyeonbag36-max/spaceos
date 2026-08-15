---
description: "건축HUB 일일 쿼터 소진 — 대장(전유부) 재개 → 소진 시 층별개요"
argument-hint: "[거점 slug ...] (비우면 잔여분을 스스로 판정)"
---

# 오늘치 건축HUB 쿼터를 다 쓴다

건축HUB 일일 쿼터(오퍼레이션당 10,000콜, 자동승인)는 **하루 안 쓰면 그날치가 사라진다.**
거점 확장(Tier1 22 → 54)을 막는 것은 코드가 아니라 이 쿼터뿐이므로, 이 커맨드는
"오늘 받을 수 있는 만큼 받는다" 하나만 한다.

근거 문서: @docs/finding-expos-quota-2026-08-09.md

## 이번 대상
$ARGUMENTS

비어 있으면 스스로 판정한다 — `data/config/page_hubs.py` 의 `HUBS`(54) 와
`data/gold/*/building_vacancy.json` 을 대조해 **미수집·부분수집 거점**을 찾는다.
`building_vacancy.json` 이 있어도 동수가 0 이면 미수집이다(쿼터가 먼저 끊긴 경우).

## 1. 프리플라이트 — 스크립트 하나로 끝난다

```
python scripts/quota_preflight.py
```

쿼터(1콜 프로브) · 전원 · 커밋 여유 · 잔여를 한 번에 찍는다. 읽기만 하고 아무것도 쓰지 않는다.
종료코드는 `0`=이상없음 · `1`=주의 · `2`=중단. **`[중단]` 이 하나라도 있으면 시작하지 않는다.**

읽는 법:

- **쿼터** — `429` 면 아직 안 열렸다. 로그로 판단하지 말고 이 응답으로 판단한다
- **전원** — 배터리면 사용자에게 AC 연결을 요청한다. 기전은 CPU가 아니다(프로세서 최대
  상태는 AC·DC 모두 100%). 갈리는 건 **무선 어댑터 절전(AC 0=최대성능 / DC 2=중간절전)**
  하나이고, 이 작업은 지번당 HTTP 1~3콜의 네트워크 바운드라 정확히 거기서 아프다.
  꽂을 수 없다면 기전만 제거할 수 있다(배터리 소모는 늘어난다):
  ```
  powercfg /setdcvalueindex SCHEME_CURRENT 19cbb8fa-5279-450e-9fac-8a3d5fedd0c1 12bbebe6-58d6-4636-95bb-3217ef867c1a 0
  powercfg /setactive SCHEME_CURRENT
  ```
  속도와 별개로 **덮개를 닫으면 절전으로 프로세스가 언다** — 배율이 아니라 정지다
- **커밋** — 여유 1~2GB 면 회색 화면·무증상 크래시가 온다. **재부팅만 듣는다**
  (프로세스를 죽여도 소용없다 — 프로세스 밖에서 자란다)
- **잔여** — 전유부 미수집 거점과 층별개요 대상을 그대로 붙여 쓸 명령줄까지 찍어 준다

시작 지점을 사용자에게 보고하고 들어간다.

## 2. 전유부(대장) — 오늘의 1순위

```
powershell -ExecutionPolicy Bypass -File scripts\run_bldgvac_until_done.ps1 -MaxPasses 20 <slug ...>
```
백그라운드로 띄우고 `data/logs/bldgvac-resume.log` 에 Monitor 를 건다. 필터는 성공
신호만 잡으면 안 된다 — `대장 대상|쿼터 소진|until-done|gold:|Traceback|포기합니다` 처럼
**실패 신호까지** 넣는다(침묵은 성공이 아니다).

- 150동마다 bronze 체크포인트 → 중단돼도 진행분은 남고 재실행이 완료분을 건너뛴다
- `_EXPOS_FULL_MAX=300` 캡이 걸려 있다. dongdaemun 34,600 → 3,900콜로 줄인 장치다
- 완료 판정은 종료코드가 아니라 **"대장 대상 0동"** 이다

## 3. 소진되면 → 층별개요 (쿼터가 따로 걸린다)

`getBrExposPubuseAreaInfo` 가 소진돼도 `getBrFlrOulnInfo` 는 별도 10,000콜이 남아 있다.
그리고 **대표 집계를 만드는 건 이쪽뿐이다** — `services/gold_vacancy.py` 의
`_COUNTED_METHODS = {"floor_ouln"}` 이라, 전유부를 다 받아도 이 단계 없이는 **백엔드가 서빙하는
공실률에 그 거점이 한 동도 기여하지 않는다.**

⚠ 이걸 "Tier1 승격이 안 된다" 로 적어 뒀던 것은 틀렸다(2026-08-15 정정). `tier` 라벨은
`build_page_master.py` 가 `tier = "Tier1(대장)" if vac else "Tier2(폴리곤근사)"` 로,
**`building_vacancy.json` 존재만으로** 정한다. 그래서 대장만 받아둔 거점은 층별개요 없이
파이프라인 재실행만으로 라벨이 오른다 — 콜 0. 층별개요가 좌우하는 것은 라벨이 아니라
**서빙되는 숫자**다. 둘을 섞어 읽으면 "Tier1 인데 공실률이 비어 있는" 거점을 오진하게 된다.

```
python -m data.collectors.floor_capacity <slug ...> [--only-approx]
```
⚠ **거점을 반드시 명시한다.** 인자가 없으면 `garosugil` 로 폴백한다(경고를 찍는다).

거점 목록은 손으로 적지 말고 gold 에서 뽑는다:
```
python -c "
import json; from pathlib import Path; from collections import Counter
from data.config.page_hubs import HUBS
out=[]
for s in HUBS:
    p=Path('data/gold')/s/'building_vacancy.json'
    if not p.exists(): continue
    c=Counter(r.get('capacity_method') for r in json.load(open(p,encoding='utf-8')))
    if c['floor_approx']: out.append((c['floor_approx'], s, c['floor_ouln']))
out.sort(reverse=True)
for n,s,o in out: print(f'{s:<16}approx {n:>5}  ouln {o:>5}')
"
```

**뽑은 걸 그대로 다 넣지 말 것.** 기본 대상은 `floor_approx` **와 기존 `floor_ouln`**
둘 다다(07-19 `pageNo` 버그 산출물 재수집 조항). 그래서 잔여가 몇 동뿐인 Tier1 거점도
전량 재호출이 된다 — 08-10 실측 21거점 **263동 회수에 12,108콜(동당 46콜)**.

- **`floor_ouln` 이 0 인 거점**(= 대장만 받아둔 배치3) → 인자로 넣는다. 재수집 낭비가 없다
- **`floor_ouln` 이 이미 큰 거점**의 소량 잔여 → **`--only-approx`** 로만 받는다
- 대장을 아직 수집 중인 거점은 **끝난 뒤에 뽑는다** — `floor_approx` 가 계속 는다

## 하지 말 것

1. **두 수집기 동시 실행 금지.** 429 는 오퍼레이션이 아니라 **키** 단위 트래픽 제한이라
   서로를 죽인다. 수집기는 5연속 429 면 그 엔드포인트를 그 실행 내내 포기하므로,
   병렬로 돌리면 하루치를 통째로 버릴 수 있다. 반드시 순차.
2. `refetch_truncated_expos --include-capped` 금지. 캡으로 아낀 절감분이 그대로 되돌아온다.
   층·호 단위 매칭이 붙어 집합건물을 집계에 넣을 때만 연다.
3. 표제부 우선 재배치(finding §4)를 이 자리에서 적용하지 말 것. 배치3 완료 후
   전 거점 재산출과 함께 검증한다.

## 완주한 거점이 생기면

```
python -m data.pipelines.recalc_capacity <slug ...>
python -m data.pipelines.build_page_master <slug ...>
python -m data.analyze_anchor_population        # 앵커 대조
```
⚠ 두 파이프라인은 인자가 없으면 **54거점 전부**를 돈다. 거점을 명시한다.
`build_page_master` 가 `coverage.json` 의 `tier` 를 `Tier1(대장)` 로 올린다 —
승격은 코드 변경이 아니라 산출물 갱신이다.

그래서 **대장을 받아두고 파이프라인을 안 돌린 거점은 라벨만 낡아 있다.** 08-15 에 9거점이
그 상태였다(gangnam·dongdaemun·gwangjang·mangwon·konkuk·samcheong·hapjeong·jamsil·mullae —
`coverage.json` 은 08-08, `building_vacancy.json` 은 08-09~15). 쿼터가 소진돼 더 받을 게
없는 날에도 이 재실행은 할 수 있다. 찾는 법:

```
python -c "
import json,datetime; from pathlib import Path
from data.config.page_hubs import HUBS
for s in HUBS:
    v=Path('data/gold')/s/'building_vacancy.json'; c=Path('data/gold')/s/'coverage.json'
    if not (v.exists() and c.exists()): continue
    d=json.loads(c.read_text(encoding='utf-8'))
    if d.get('tier','').startswith('Tier1'): continue
    n=len(json.loads(v.read_text(encoding='utf-8')))
    if n: print(f'{s:<14}{n:>5}동  coverage {d.get(\"built_at\")}')
"
```

앵커 대조 시 **두 숫자를 섞어 읽지 말 것**: 파이프라인이 찍는 "대표 집계 공실률"은
`expos_units`(집합건물)를 포함해 60%대로 뜨지만, 백엔드가 서빙하는 값은 `floor_ouln` 만
센 것이다. R-ONE 과의 격차가 0 이 되는 게 정상도 아니다 — 우리는 호실·전수,
R-ONE 은 면적·표본이라 모집단이 다르다.

## 마치며

Gold 산출물은 런타임에 읽으므로 **ignore 예외에 들어가 있는지 `git check-ignore` 종료코드로**
확인한 뒤 커밋한다. 빠지면 프로덕션만 조용히 폴백한다.

끝낼 때 사용자에게 보고할 것: 오늘 받은 동수 · 남은 동수 · 무엇에 막혔는지(쿼터/네트워크/전원).

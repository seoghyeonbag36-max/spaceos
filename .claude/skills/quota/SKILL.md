---
name: quota
description: 건축HUB 일일 쿼터를 하루치 다 태우는 런북 — 프리플라이트 → 대장(전유부) 재개 → 소진 시 층별개요. 수집을 걸어둘 때.
---

# 오늘치 건축HUB 쿼터를 다 쓴다

> 체인에서의 위치: `hub-chain` 3단계(대장). 자리를 비운 채 돌릴 때는 `autorun`.

> ✅ **대장(전유부) 수집은 2026-08-17 에 당시 54/54 로 완주했다(현재 서빙 66거점도 전부 Tier1) — 이 커맨드의 원래 목적은
> 달성됐다.** 더 이상 Page 트랙을 막는 쿼터 병목은 없다. 지금 이 커맨드가 쓰이는 자리는
> 둘뿐이다: ① **신규 거점을 추가**할 때 ② 층별개요(`floor_ouln`) 잔여를 더 채울 때.
> 기존 54거점에 대해 습관적으로 돌리지 말 것 — 아래 §회수율 표대로 **이미 층별개요를
> 돌린 거점의 기대 회수는 0** 이고, 콜만 태운다.

건축HUB 일일 쿼터(오퍼레이션당 10,000콜, 자동승인)는 **하루 안 쓰면 그날치가 사라진다.**
거점을 확장하는 동안 그 속도를 정한 것은 코드가 아니라 이 쿼터였고(Tier1 13 → 22 → 40
→ 49 → **54 완주**), 이 커맨드는 "오늘 받을 수 있는 만큼 받는다" 하나만 한다.

근거 문서: docs/finding-expos-quota-2026-08-09.md

## 이번 대상

호출 인수로 받은 거점 slug 목록. 비어 있으면 아래 프리플라이트로 잔여분을 스스로 판정한다.

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

⚠ **잔여 동수로 대상을 고르지 말 것 — 회수율을 정하는 건 "아직 시도하지 않았는가"
하나다.** 08-17 에 같은 `--only-approx` 를 돌렸는데 결과가 둘로 쪼개졌다:

| 거점 상태 | 회수율 |
|---|---|
| 미시도 (kyunghee·wangsimni·sadang·sukmyung·hyehwa) | 94.3~96.2% |
| 부분 시도 (chungmuro — 그날 받은 대장 201동분만 새것) | 54.5% |
| **이미 완주 (dangsan·mullae·samcheong)** | **0.0%** |

완주한 거점에 남은 `floor_approx` 는 **응답이 없는 게 아니라 층별개요에 상업 층이
0 인 건물**이다(mullae 60동 재호출 → bronze 233KB 정상 수신, 갱신 0). 몇 번을
호출해도 안 바뀐다. 위 세 번째 줄에 그날 129콜을 써서 3동을 받았다.

그래서 **바로 윗줄의 "소량 잔여 → --only-approx" 는 그 거점이 아직 층별개요를 한 번도
안 돌린 경우에만 맞다.** 이미 돌린 거점이면 잔여가 몇 동이든 기대 회수는 0 이다.

**대상은 손으로 고르지 말고 프리플라이트 출력을 그대로 쓴다.** `quota_preflight.py` 가
잔여를 **미시도 / 판정완료** 로 갈라 찍고, **미시도가 있는 거점만** 명령줄에 넣는다.
"시도할 가치가 있는 거점 없음" 이면 오늘 층별개요로 받을 것이 없다는 뜻이다.

⚠ **시도 여부를 mtime 으로 재지 말 것.** 종전 판단 순서 ②("bronze 가 있다면 그 뒤에
대장을 새로 받았는가")를 `building_vacancy.json` 의 mtime 으로 재면 **항상 참이 된다** —
`floor_capacity` 자신이 bronze 를 쓴 직후 같은 실행에서 gold 를 제자리 갱신하기 때문이고,
**회수가 0 인 거점도** `_persist` 를 타서 mtime 이 올라간다. 프리플라이트는 이제 추정
대신 `bronze/<slug>/*/bldg_flr_raw.json` 에 **그 건물이 들어 있는지로 직접** 본다.

2026-08-19 에 이 오탐으로 50거점 672동을 전부 넣었다. 결과가 판단 기준을 확정해 준다:

| 오늘 시도한 672동 | 회수 | 판정(상업층 0) | 회수율 |
|---|---|---|---|
| **미시도였음** | **22** | 1 | **95.7%** |
| 이미 시도했었음 | 0 | 649 | **0.0%** |

미시도 95.7% 는 위 08-17 표(94.3~96.2%)와 같은 값이고, 기시도는 예외 없이 0 이다.
필터가 있었으면 **23콜로 22동**을 받았을 일에 672콜을 썼다 — 649콜이 순수 낭비다.

회수율은 이제 로그에 무조건 찍힌다(`결과 N동 중 갱신 … 회수율 …%`). 종전에는 진행
출력이 갱신 경로 뒤에 있어 **회수 0 인 거점은 한 줄도 안 찍혔고**, "돌고 성과 0" 과
"아예 안 돎" 이 구분되지 않았다. 다음 실행 대상을 고르기 전에 이 줄을 먼저 본다.

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
python -m data.analyze_anchor_population --rebuild <slug ...>   # 앵커 대조
```
⚠ 두 파이프라인은 인자가 없으면 **`page_hubs.ACTIVE_HUBS` 전부**를 돈다(2026-09-05 기준 서울 66거점).
거점을 명시한다. — 개수를 여기 박지 않는 이유는 서빙 판단이 바뀌면 이 줄이 낡기 때문이다.
`build_page_master` 가 `coverage.json` 의 `tier` 를 `Tier1(대장)` 로 올린다 —
승격은 코드 변경이 아니라 산출물 갱신이다.

⚠ **앵커에 `--rebuild` 를 빼지 말 것.** `analyze_anchor_population` 은 건물 속성을
`silver/<slug>/building_attrs.json` 사이드카에서 읽는데, `load_cache` 가 **파일이
있으면 그냥 쓴다**. 대장을 새로 받아도 사이드카는 옛날 것이라 `rone_size`·`is_shop`
이 비고, 그 결과 **표 1 의 B·C·D·E 열이 전부 `0.0%( 0)` 으로 나온다**(08-17 신규
5거점에서 발생 — 사이드카가 08-16 자였다). A열만 채워져 있으면 이걸 의심한다.
재생성은 bronze 재파싱이라 **API 콜 0** 이지만 거점당 수 분 걸린다.

앵커를 읽을 때 **A현행 열을 R-ONE 과 비교하지 말 것.** A는 집합상가를 포함해 부풀고
(08-17 dongdaemun A 83.7% vs C용도 36.7% · 앵커중 15.3%), 집합건물은 내부 점포가
`bdMgtSn` 으로 귀속되지 않아 분자가 구조적으로 빈다(finding-expos-quota §2).
대조는 **C(용도 정렬)** 로 한다.

그래서 **대장을 받아두고 파이프라인을 안 돌린 거점은 산출물이 낡아 있다.** 08-15 에 9거점이
그 상태였다(gangnam·dongdaemun·gwangjang·mangwon·konkuk·samcheong·hapjeong·jamsil·mullae —
`coverage.json` 은 08-08, `building_vacancy.json` 은 08-09~15). 쿼터가 소진돼 더 받을 게
없는 날에도 이 재실행은 할 수 있다.

찾을 때 **`tier` 라벨로 거르지 말 것.** 낡음은 두 종류이고 라벨은 그중 하나만 드러낸다:

1. 라벨이 `Tier2` 로 남은 거점 — 눈에 보인다
2. **이미 `Tier1` 이라 라벨로는 멀쩡해 보이고 숫자만 낡은 거점** — 08-15 `nambu` 가 그랬다.
   대장 506동이 16:12 에 채워졌는데 지도·커버리지는 08-08 자 그대로였다(공실률 68.0%,
   실제 63.3%). tier 로 거르는 판정은 이걸 통째로 놓친다

그래서 라벨이 아니라 **mtime 을 비교한다** — 대장이 산출물보다 새로우면 재실행 대상이다:

```
python -c "
import json,datetime; from pathlib import Path
from data.config.page_hubs import HUBS
f=lambda t: datetime.datetime.fromtimestamp(t).strftime('%m-%d %H:%M')
stale=[]
for s in HUBS:
    d=Path('data/gold')/s
    v,g,c=d/'building_vacancy.json',d/'page_building_master.geojson',d/'coverage.json'
    if not v.exists(): continue
    n=len(json.loads(v.read_text(encoding='utf-8')))
    if not n: continue                    # 0동 = 미수집. 돌려도 올릴 게 없다(쿼터 대기)
    vm=v.stat().st_mtime
    gm=g.stat().st_mtime if g.exists() else 0
    cm=c.stat().st_mtime if c.exists() else 0
    if gm<vm or cm<vm:
        stale.append(s); print(f'{s:<14}{n:>5}동  대장 {f(vm)} > 산출물 {f(gm) if gm else \"없음\"}')
print('재실행 대상:', ' '.join(stale) or '없음')
"
```

`floor_capacity` 도 `building_vacancy.json` 을 제자리 갱신하므로, **층별개요를 받은 날은
그 거점도 여기 걸린다** — 층별개요 뒤에 파이프라인을 안 돌리면 받아온 `floor_ouln` 이
서빙되는 숫자에 반영되지 않는다.

앵커 대조 시 **두 숫자를 섞어 읽지 말 것**: 파이프라인이 찍는 "대표 집계 공실률"은
`expos_units`(집합건물)를 포함해 60%대로 뜨지만, 백엔드가 서빙하는 값은 `floor_ouln` 만
센 것이다. R-ONE 과의 격차가 0 이 되는 게 정상도 아니다 — 우리는 호실·전수,
R-ONE 은 면적·표본이라 모집단이 다르다.

## 마치며

Gold 산출물은 런타임에 읽으므로 **ignore 예외에 들어가 있는지 `git check-ignore` 종료코드로**
확인한 뒤 커밋한다. 빠지면 프로덕션만 조용히 폴백한다.

끝낼 때 사용자에게 보고할 것: 오늘 받은 동수 · 남은 동수 · 무엇에 막혔는지(쿼터/네트워크/전원).

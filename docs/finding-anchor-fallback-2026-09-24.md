# 표를 갱신하고 수집기를 안 돌리면 조용히 대체값이 나온다 (2026-09-24)

> **한 줄**: 설정·배정표를 늘리는 것과 그것을 **먹는 수집기를 다시 돌리는 것**은 별개의 수다.
> 안 돌려도 실패하지 않는다 — **그럴듯한 값이 나온다**. 2026-09-24 하루에 이 함정에 두 번 걸렸다.
>
> | # | 갱신한 것 | 안 돌린 것 | 조용히 나온 것 |
> |---|---|---|---|
> | 1 | `DISTRICT_RONE` 에 15거점 매핑(09-20) | `rone_rent` | 앵커 = 폴백 **10.00%** (15거점 전부) |
> | 2 | `unit_jipgyegu` 배정표 66→81거점 | `living_population_jipgyegu` | `foot` 거점 **72/81** (9거점 탈락) |
> | 3 | 유닛 foot 81/81 | `build_posting_inputs` | `pppp_status` 의 `rent·foot` **66/81** 그대로 |
> | 4 | `build_posting_inputs` 재실행 | `build_gold`(그 위의 시계열) | 재실행해도 **66거점** 그대로 |
> | 5 | 거점 81개 등록 | `DISTRICT_TRDAR` **설정 자체가 미작성** | 수집기가 "전체 1,648행 중 **거점 245행**"으로 거르고, `build_trdar_demand` 가 exit=0 인 채 66거점 |
>
> **넷 다 에러가 없다.** 1번은 그럴듯한 상수가, 2번은 빠진 거점이, 3·4번은
> **재실행해도 안 바뀌는 수**가 나온다. 특히 4번이 고약하다 — 빌더를 다시 돌렸는데
> 출력이 그대로라 "이미 최신"으로 오독하기 쉽다. 실제로는 **입력이 낡은 것**이었다.
>
> **교훈**: 산출물의 거점 수가 안 오르면 그 빌더가 아니라 **그 빌더의 입력**을 본다.
> 한 층씩 파지 말고 정본 체인(`scripts/run_batch2_chain.py --list`)을 먼저 펼쳐
> 어디서 끊겼는지 본다 — 09-24 에 네 층을 하나씩 파고 나서야 그 목록에 닿았다.

## 사례 1 — 매핑만 추가하면 앵커는 조용히 폴백 10.0% 가 된다

## 무슨 일이 있었나

서울 3·4차 15거점의 층별개요 수집을 마치고 `calibrate_vacancy` 를 돌렸더니
**15거점 전부 앵커가 정확히 `10.00%`** 로 찍혔다. 이건 R-ONE 실측치가 아니라
`calibrate_vacancy.ANCHOR_FALLBACK` 상수다 — "R-ONE 원본을 못 읽을 때만" 쓰는 값이다.

같은 실행에서 나온 α(0.324~0.901)와 `gap_pp`(+1.1~+20.9%p)는 **전부 같은 가짜
기준선에 대고 잰 값**이라 아무 정보가 없었다. 그런데 출력 형식은 실측 앵커일 때와
구분이 안 된다 — 로그도 `calibration.json` 도 "이건 폴백이다"라고 말하지 않는다.

## 원인 — 두 자리가 따로 논다

앵커는 **두 곳**이 맞아야 나온다.

| 자리 | 파일 | 상태(09-24 아침) |
|---|---|---|
| 거점 → R-ONE 상권 **매핑** | `data/config/rone_districts.DISTRICT_RONE` | 09-20 에 15거점 추가됨 ✅ |
| 그 상권의 **시계열 수집** | `bronze/platform13/*/rone_vac_mid.json` | 신규 15거점 **0행** ❌ |

`anchor_of()` 는 bronze 에서 읽은 `{district_id: %}` 를 **slug 로** 조회한다.
매핑을 추가해도 **수집기를 다시 돌리지 않으면** bronze 에 그 slug 행이 생기지 않고,
`.get(slug) or ANCHOR_FALLBACK` 이 조용히 10.0 을 돌려준다.

```python
def anchor_of(slug: str) -> float:
    return _rone_latest("vac_mid").get(slug) or ANCHOR_FALLBACK
```

실측: 수집 전 최신분기 district 수 **86**(신규 15 전무) → `rone_rent` 재실행 후 **101**.

## 고친 방법

```
python -m data.collectors.rone_rent      # 인자 없음 — DISTRICT_RONE 전체를 다시 받는다
```

결과 15/15 확보. 값은 7.25~17.44% 로 폴백 10.0 과 최대 7.4%p 어긋난다.

공유 구조가 값에 그대로 드러난다 — 같은 R-ONE 상권을 빌린 거점은 앵커가 **같다**:

| R-ONE 상권 | 앵커 | 빌려 쓰는 거점 |
|---|---|---|
| 서울>강남>남부터미널 | 7.7526% | seochoyeok · yangjae · bangbang · poi |
| 서울>강남>테헤란로 | 9.0493% | dogok · maebong |
| 서울>기타>독산/시흥 | 14.7380% | gurojeonhwa · gurodigital |

## 같이 드러난 두 번째 결손 — `recalc_floor_ouln` 누락

15거점 전부 `rone_aligned(mid)` 가 **"gap 산출 불가(면적 기준 결측)"** 였다.
코드가 대표값으로 지정한 `vacancy_area_pct` 는 `recalc_floor_ouln` 이 행에 넣는
`active_floors_lo/hi` 가 있어야 나오는데, 그 단계가 체인에 없다.

돌려 보니 교정 폭이 작지 않았다 — `capacity == active` 로 고정돼 있던 아티팩트 행이
거점당 **52~253동**이고, 평균 공실률이 이만큼 움직인다:

| 거점 | 전 | 후 |
|---|---|---|
| seochoyeok | 19.9% | 10.5% |
| bangbang | 18.9% | 13.1% |
| poi | 21.1% | 16.7% |
| ydp-gucheong | 18.5% | 13.3% |
| bonseobu | 22.0% | **23.1%** (유일하게 올라감) |

즉 이 단계를 건너뛰면 **공실률이 부풀려진 채** Page마스터·앵커 대조로 흘러간다.

## 재발 방지

1. **새 거점을 `DISTRICT_RONE` 에 추가했으면 `rone_rent` 를 반드시 다시 돌린다.**
   매핑 추가와 수집은 별개의 수이고, 안 돌리면 실패가 아니라 **그럴듯한 폴백**이 나온다.
2. **앵커가 폴백인지 확인하는 법** — 여러 거점의 `anchor_pct` 가 **정확히 10.00** 으로
   같으면 의심한다. 실측 앵커는 그렇게 딱 떨어지지 않는다.
3. `recalc_floor_ouln` 은 `build_page_master` **앞**에 와야 한다. 뒤에 돌리면
   `building_vacancy.json` 이 새것이 되어 Page마스터가 낡는다(mtime 대조로 잡힌다).

체인 순서(수집 이후):

```
floor_capacity → recalc_floor_ouln → build_building_attrs → build_page_master
  → [rone_rent (신규 매핑이 있으면)] → calibrate_vacancy
  → build_vacant_units → build_unit_jipgyegu → build_unit_foot
```

## 사례 2 — 배정표를 늘려도 `foot` 은 안 늘어난다

`build_unit_jipgyegu` 로 배정표를 **66 → 81거점**(유닛 664 → 840쌍)으로 올린 뒤
`build_unit_foot` 을 돌렸더니 **거점 72** 가 나왔다. 9거점이 조용히 빠졌고, 전부
오늘 올린 15거점 중 일부였다(bonseobu·daerim·gildong·gurodigital·gurojeonhwa·
guui·maebong·poi·yangjae). 기존 66거점은 하나도 안 빠졌다.

원인은 `build_unit_foot.run()` 의 이 두 줄이다 — 프로필이 없으면 **거르고 넘어간다**:

```python
p = prof.get(v["oa_code"])
if not p or p["weekday"] is None:
    continue
```

`prof` 는 bronze 생활인구에서 온다. 그런데 그 수집기(`living_population_jipgyegu`)는
**배정표에 있는 집계구만 남기는** 설계다("전량을 받아 놓고 못 붙이는 것이 최악"). 즉
배정표를 늘린 뒤 **다시 받지 않으면** 새 거점의 집계구는 bronze 에 아예 없다.

실측: 표본의 집계구가 **2,028개**뿐이었다(서울 전체 19,038 중 10.7%). 빠진 9거점은
필요한 집계구가 7~11곳인데 **있는 것이 0곳**이었다. 통과한 6거점도 아슬아슬했다 —
seochoyeok 6곳 중 3, jamsil-tour 9곳 중 1, nowon 4곳 중 1. 즉 "통과"가 곧
"서열이 제대로 갈린다"는 뜻이 아니다.

고치는 순서 — 수집기 대상은 **세 배정표의 합집합**이라 한 번 받을 때 같이 넓힌다:

```
build_unit_jipgyegu          # 유닛 (Posting foot)
scripts/build_cell_jipgyegu  # 100m 격자 (Page 유동·밀도)   ← 09-05·66거점으로 낡아 있었다
  → living_population_jipgyegu --month 202607 --days 7
  → build_unit_foot
```

⚠ `node_jipgyegu`(GNN 노드)는 **2026-09-15 에 의도적으로 비워졌다** — 점포 소스가
카카오 로컬 → 상가정보로 바뀌며 node_id 체계가 `kakao:*` → `sdsc:*` 로 갈렸다.
`oa_codes` 1,155 는 남아 있어 keep-list 에는 계속 기여한다.

## 사례 5 — `DISTRICT_TRDAR` 은 아예 안 쓰여 있었다 (뿌리 원인)

앞 넷은 "다시 안 돌렸다"였지만 이건 **설정이 없었다**. 09-20 에 `DISTRICT_RONE`(R-ONE
상권)은 15거점분을 채웠는데 `DISTRICT_TRDAR`(서울 상권분석 상권)은 안 채웠다. 둘 다
"거점 → 외부 상권코드" 매핑인데 파일이 다르고 짝이 맞는지 검사하는 자리가 없다.

증상이 전부 **정상 종료**였다는 점이 핵심이다:

- `seoul_trdar` → `전체 1,648행 중 거점 245행` (245 = 옛 66거점분)
- `build_trdar_demand` → `exit=0` · `245행 / 66거점`
- `build_posting_inputs` → `exit=0` · `66거점` (재실행해도 그대로)
- `build_gold` → program context 는 **80거점**인데 시계열만 66 — **한 실행 안에서 두 수가 갈렸다**

마지막 줄이 이 저장소의 전형적 실패 양식이다. 같은 빌더가 같은 실행에서 어떤 산출물은
81거점으로, 어떤 것은 66거점으로 낸다. 원인은 소스마다 **거점 목록을 다른 데서 읽기**
때문이다(`ACTIVE_HUBS` vs `DISTRICT_TRDAR` vs `TRDAR_TO_DISTRICT`).

### 고친 방법 — 도구를 같이 만들었다

매핑이 손으로 쓰는 설정인데 보조 도구가 없어서 매번 빠졌다. `scripts/propose_trdar_mapping.py`
를 새로 만들었다: `TbgisTrdarRelm` 을 **필터 없이 전량**(1,650행) 받아 EPSG:5181 →
WGS84 로 바꾸고 거점 중심에서의 거리순으로 후보를 낸다. 이미 다른 거점이 쓰는 코드는
`⚠이미 <slug>` 로 표시한다 — `TRDAR_TO_DISTRICT` 가 dict 라 **중복은 뒤엣것이 조용히 이기기** 때문이다.

채택 규칙(2026-09-24 사용자 판단): **거점 `stores_radius_m`(700m) 안의 상권 전부**,
반경이 겹치면 **최근접 거점**이 갖는다. 700m 는 그 거점의 점포 수집 반경과 같은 값이라
거점 정의와 일관된다. 결과 **107코드 / 15거점**(거점당 7.1) · 중복 0 · 합계 352코드 / 81거점.

⚠ 기존 66거점은 거점당 3.7 로 더 엄선돼 있다 — 밀도 기준이 거점 간에 균일하지 않다는
뜻이므로, 거점 간 상권 수를 비교 지표로 쓰지 말 것.

## 남긴 판단

15거점은 **전부 공유 앵커**(자기 R-ONE 표본 없음)다. 그중 넷은 기존 서울 공유 대역
1.0~1.7km 를 넘는다 — daerim 2.96km · poi 2.21km · gurodigital 2.10km ·
gurojeonhwa 2.09km. **그대로 쓰기로 했다**(2026-09-24 사용자 판단) — 2차 확장 13거점도
전부 공유였고 Posting 레이어가 `rone-shared` 로 표기한다. 다만 `calibration.json` 에는
공유 여부·거리가 **남지 않으므로**, 이 거점들의 `gap_pp` 를 단독 근거로 인용하지 말 것.

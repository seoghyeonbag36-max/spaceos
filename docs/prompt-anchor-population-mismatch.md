# 다음 작업용 프롬프트 — 앵커 모집단 불일치 규명 (최우선)

> **2026-08-01 완료.** 결과: `docs/finding-anchor-population.md` · 재현: `python -m data.analyze_anchor_population`
> 판정은 **A ∧ B**(둘 다 참, 겹침)다. 모집단·단위를 R-ONE 에 맞추면 13거점 합
> 51.8% → 30.5% 로 21.3%p 가 닫히고, 남는 ~20%p 는 분자 층 커버리지에서 온다.
> 후속 작업 프롬프트: `docs/prompt-floor-level-matching.md`

2026-07-28 하루 동안 집계 공실률 과대추정의 원인 후보를 하나씩 소거했다. 다섯 개가
빠졌고 **둘만 남았다.** 그중 앵커 쪽을 먼저 봐야 하는 이유는 단순하다 — 앵커가 원인이면
분자 커버리지를 아무리 파도 격차는 안 닫히고, 앵커가 맞다면 분자가 유일한 설명이 된다.
어느 쪽이든 다음 작업의 방향이 결정된다. API 콜도 들지 않는다.

관련 커밋: `d0535fc`(교정 6종) · `ba7512c`(hongdae 층별개요) · `4423e59`(절단 복구).

---

## 붙여 넣을 프롬프트

```
SpaceOS 13거점의 건물 공실률이 부동산원(R-ONE) 앵커보다 계통적으로 높다.
앵커와 우리 지표가 애초에 같은 것을 재고 있는지 확인해줘.

## 현황
13거점 중 12곳에서 추정치가 앵커보다 높다(calibrate primary gap):
  euljiro +63.0%p · myeongdong +49.1%p · hongdae +43.4%p · ikseon +41.5%p ·
  seoulsup +32.1%p · seochon +25.0%p · yeonnam +19.0%p · apgujeong +17.2%p ·
  seongsu +15.9%p · garosugil +11.7%p · hannam +10.3%p · itaewon +7.3%p ·
  songridan -1.5%p

## 이미 소거된 원인 (다시 파지 말 것)
1. capacity 산식(floor_approx vs floor_ouln) — 07-28 재수집으로 approx 6% 미만.
2. capacity_method 차이(expos_units vs floor_ouln) — 분모 규모를 통제하면 두 방법의
   공실률이 거의 같다(1~2호 17.0/16.3% · 11~20호 42.1/42.5% · 21~50호 46.4/52.8%).
3. 거점 특성 — 격차 순위가 건물 규모 구성으로 설명된다.
4. 분자 stale — refresh_active 갱신 0건.
5. 분모 오염(주거·업무 혼입) — NON_CAPACITY_PURPS 가 정상 작동. 51호+ 38동에서
   필터를 통과해 남은 7,434호는 대부분 정상 상업 용도(기타판매시설 22.9% ·
   기타제1종근생 13.5% · 학원 9.0% · 상점 8.1%). 필터가 제거한 7,377호도 판단이
   정확하다(아파트 3,159 · 사무소 1,497 · 오피스텔 1,173).
6. bronze 전유부 절단 — 23동 복구 완료(4423e59). 고쳤더니 지표는 오히려 나빠졌다.

## 남은 후보 2개
A. 앵커 모집단 불일치  ← 이번 작업
B. 분자 소스의 대형건물 커버리지 결손
   (active~capacity log-log 기울기 0.67~0.70 — 분모 10배에 분자 약 5배.
    상가정보와 인허가는 독립 소스인데 패턴이 같다.)

## 해야 할 일
1. R-ONE '중대형 상가 공실률'(statbl_id A_2024_00251)이 정확히 무엇을 재는지 확인.
   특히 세 가지:
   - **면적 기준인가 호실 수 기준인가.** 우리 지표는 호실 수 기준이다. R-ONE 이
     임대가능 면적 대비 공실 면적이라면 두 값은 애초에 단위가 다르다.
   - **모집단이 무엇인가.** 중대형(3층 이상 또는 연면적 330㎡ 초과)이라면 우리가
     세는 소형 건물 다수가 앵커 모집단에 없다. 반대로 우리는 대형 건물의 상층부
     호실까지 전부 분모에 넣는다.
   - **표본 조사인가 전수인가.** 표본이라면 조사 대상 건물이 몇 동인지.
2. 우리 지표를 앵커 모집단에 맞춰 다시 집계했을 때 격차가 닫히는지 검정.
   gold 에 floors 가 있으므로 "3층 이상 또는 연면적 330㎡ 초과" 조건으로 건물을
   걸러 재집계할 수 있다. 소규모 앵커(vac_small)와도 같은 방식으로 대조할 것.
3. 1층만으로 집계한 값도 함께 볼 것. 가로수길 가두 1층 실태조사(2024) 41.6% 는
   PoC 초기 앵커였고 모집단이 명확하다(메인도로 1층 점포). 우리 지표를 1층으로
   좁혔을 때 이 값에 근접하면 모집단 불일치가 확정된다.
4. 결론에 따라 갈라진다:
   - 앵커가 원인 → 지표 정의나 앵커를 바꾼다. α 보정으로 덮지 말 것
     (α 는 어느 쪽이 사실인지 말해주지 않는다 — 07-26 교훈).
   - 앵커가 맞다 → 후보 B 로 넘어간다. 그때는 로드뷰 재표본이 필요한데
     **층화 기준을 capacity_method 가 아니라 분모 규모로 잡을 것.**

## 데이터 (전부 로컬, API 콜 0)
- R-ONE 원본: data/bronze/platform13/{날짜}/rone_vac_mid.json · rone_vac_small.json
  행 형태: {district_id, quarter, value, rone_cls, statbl_id, itm_nm, unit}
  1,134행 / 21개 분기(20211~20261) / 54거점.
- 거점→R-ONE 상권 매핑: data/config/rone_districts.py (DISTRICT_RONE, 54개)
  예) garosugil → '서울>강남>신사역', hongdae → '서울>영등포신촌>홍대/합정'
- 수집기: data/collectors/rone_rent.py
- 앵커 적용부: data/pipelines/calibrate_vacancy.py 의 anchor_of()
- 우리 지표: data/gold/{slug}/page_building_master.geojson
  (properties 에 capacity·active·licensed·active_pip·floors·capacity_method)

## 완료 기준
- R-ONE 중대형 공실률의 단위·모집단·표본 규모가 문서로 정리된다.
- 우리 지표를 그 모집단에 맞춰 재집계한 값과 앵커의 격차가 숫자로 나온다.
- 후보 A/B 중 어느 쪽인지 판정되고, 아니라면 무엇이 남는지 명시된다.

## 주의
- **집계는 반드시 건물별 min(active, capacity) 클램프 후 합산.** 단순
  sum(active)/sum(capacity) 로 하면 active>capacity 인 건물(거점당 34~45%)의
  초과분이 다른 건물의 공실을 상쇄해 공실률이 0% 로 눌린다
  (yeonnam 단순합 0.0% vs 클램프 27.5%).
- **분모 집계는 지번(pnu) 단위로 dedupe 할 것.** page_building_master.geojson 의
  expos_units feature 790개는 고유 지번이 496개뿐이다(폴리곤 294장 중복).
  feature 단위로 세면 27.7% 과대 같은 허수가 나온다.
- 파이썬 stdout 이 cp949 로 잡혀 em-dash 등에서 UnicodeEncodeError 로 죽는다.
  PYTHONIOENCODING=utf-8 을 걸 것.
- Windows + PowerShell 5.1. .ps1 을 새로 만들면 UTF-8 BOM 으로 저장할 것.
- 긴 작업은 백그라운드로. 노트북이 배터리면 약 7배 느려지고 덮개를 닫으면 멈춘다.
```

---

## 왜 이 순서인가

`calibrate_vacancy` 의 α 보정은 격차를 **덮을 뿐 어느 쪽이 사실인지 말해주지 않는다.**
2026-07-26 에 같은 함정을 한 번 밟았다 — α=9.043 이 나왔는데 그건 측정값이 아니라
붕괴한 capacity 산출물의 아티팩트였다.

지금 α 는 거점별로 0.093~1.091 로 12배 흩어져 있다(myeongdong 0.093 · songridan 1.091).
단일 현상에 대한 보정계수가 이만큼 흩어진다면 보정 대상이 잘못 정의됐다는 신호다.

그리고 이번 세션에서 **분모를 정밀화할 때마다 지표가 나빠지는 패턴**이 두 번 재현됐다
(07-27 Tier1 승격, 07-28 절단 복구). 데이터가 정확해질수록 앵커에서 멀어진다면
앵커 쪽을 의심하는 것이 순서다.

## 관련 문서

- `docs/prompt-vacancy-anchor-drift.md` — 07-27 앵커 이탈(처리 완료, 가설은 틀렸음)
- `docs/prompt-playwright-e2e.md` — 시각 검증(07-27부터 미착수)
- `docs/poc-building-vacancy.md` §성공 기준 — 41.6% 앵커의 정정 노트
- `.claude/skills/verify` (spaceos:verify) — 로컬 앱 확인 절차

## 잔여 항목 (이 작업과 무관하게 남아 있음)

- `garosugil` 1동이 `_MAX_EXPOS_PAGES=80` 상한에 걸려 전유부가 여전히 잘려 있다
  (`expos_total` 8,000호 초과). 상한을 올리고 `refetch_truncated_expos` 재실행 필요.
- 로드뷰 표본 `roadview_capacity_{ikseon,myeongdong,yeonnam}.csv` 89동은 전부 미라벨이고
  07-26 `floor_approx` 중심 쿼터라 64동의 method 가 이미 바뀌었다 — **폐기 대상.**

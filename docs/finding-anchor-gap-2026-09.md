# R-ONE 앵커 격차 규명 (2026-09-07)

`rone_aligned` 가 어디서 나오고, 화면의 대표 공실률과 어떻게 이어지며,
"표본 대 전수" 가설이 실제로 성립하는지를 **저장소 산출물만으로** 판정한 결과다.

- 대상 거점: `yeonnam` · `sinchon` · `hongdae` (대조군 `garosugil`)
- 프로브: **네트워크 0콜 · bronze/silver 불필요 · 코드 무수정.** `data/gold` 의 추적 파일만 읽었다
- 기계가 읽을 값: `reports/anchor_gap_2026-09.json`
- 재현: 부록 A

---

## 0. 한 줄 결론

**가설은 틀렸다.** 지금 화면에 뜨는 대표 공실률(연남 12.5 · 신촌 17.2 · 홍대 15.0%)에서
규모 축 **하나만** R-ONE 중대형 쪽으로 좁히면(다른 조건 전부 동일) 격차는 줄지 않고
**3거점 전부 늘어난다** — `+7.53 / +5.51 / +6.87%p` → `+9.92 / +8.67 / +7.86%p` (§3-1).
작은 건물이 서빙 대표값을 **아래로 누르고 있었기** 때문이다(분모층수 ≤2 세그먼트 공실률
6.58 / 8.75 / 11.27%).

모집단·단위·분자 규칙 **세 축을 다 맞춘** 값이 `rone_aligned.mid` 이고, 그 격차는
**+15.8 / +8.1 / +12.0%p** 다 — 화면의 격차보다 크다. 즉 화면의 `+7.5%p` 는 정렬된
격차가 아니라 **정렬 안 된 값에 앵커를 붙여 뺀 수**이고, 실제 격차를 절반 이하로
작게 보이게 한다.

격차의 원인은 표본/전수가 아니라 **큰 건물의 분자 결손**이다 — 08-01 에 이미
"후보 B" 로 특정돼 있던 것이다(§3-3).

---

## 1. `rone_aligned` 는 언제 어느 파이프라인에서 계산되는가

| 항목 | 내용 |
|---|---|
| 계산 주체 | `data/pipelines/calibrate_vacancy.py:139` `_rone_aligned()` |
| 호출 지점 | 같은 파일 `run()` 내부 `calibrate_vacancy.py:266` → `out["rone_aligned"]` (`:269`) |
| 입력 ① | `data/gold/<hub>/building_vacancy.json` (`calibrate_vacancy.py:217-220` 에서 로드) — 수집기 `data.collectors.building_vacancy` 산출 |
| 입력 ② | `silver/<hub>/building_attrs.json` — `data/pipelines/build_building_attrs.py:281` `load()` 로 읽는다. `is_mall` / `is_shop` / `rone_size` / `com_area_flr` 가 여기서 온다 (`build_building_attrs.py:262-267`) |
| 입력 ③ | `bronze/platform13/<날짜>/rone_vac_mid.json` · `rone_vac_small.json` — `calibrate_vacancy.py:_rone_latest()` 가 **최신 분기**만 뽑아 앵커로 쓴다 (`calibrate_vacancy.py:57-68`) |
| 분자 | `active_floors_lo` / `active_floors_hi` — `data/pipelines/recalc_floor_ouln.py` 가 행에 심어 둔 **층 단위** 값 |
| 출력 | `data/gold/<hub>/calibration.json` → `rone_aligned.{mid,small,mall}` |
| 실행 순서 | `build_building_attrs` → `recalc_floor_ouln` → `build_page_master` → **`calibrate_vacancy`** (`scripts/run_hub_chain_batch.py:235-243`, `.claude/skills/gold-build/SKILL.md:31-35`) |

세그먼트 정의(코드 실물, `calibrate_vacancy.py:158-163` + `build_building_attrs.py:262-267`):

- `mall` = `capacity_method == "expos_units"` **또는** `is_mall`(전유부 행이 있거나 `regstr_gb == "집합"`)
- `mid` / `small` = 나머지 중 `is_shop`(표제부 주용도가 상가류)인 것을 `rone_size` 로 가른다.
  `mid` = 지상층수 ≥ 3 **또는** 연면적 > 330㎡
- 그 외(업무·숙박 등)는 `seg is None` 으로 **탈락** — 어느 계열에도 안 들어간다

소비처는 이미 `rone_aligned.mid` 를 쓴다: `apps/backend/app/services/vacancy_forecast.py:37`,
`ml/inference/predictor.py:41`.

### 1-1. 낡았는가 — **아니다. 값은 2026-09-04 빌드로 갱신돼 있다**

`note` 의 `(2026-08-01)` 은 `calibrate_vacancy.py:202` 의 **하드코딩 문자열**이다.
지표를 *정의한* 날짜이지 *계산한* 날짜가 아니다. 값이 그때 것인지는 두 가지로 갈랐다.

1. **같은 빌드에서 나왔음** — `calibration.json` 의 하위호환 값 `estimated_vacancy_pct` 는
   `page_building_master.geojson` 에서 계산된다(`calibrate_vacancy.py:231-241`).
   현재 master 로 다시 계산하면 **연남 50.4 · 신촌 24.1 · 홍대 31.0** 으로 파일 값과
   소수점까지 일치한다(부록 A-1). master 의 빌드 시각은 `coverage.json:built_at`
   = `2026-09-04T23:26:55`(연남) 이다. 즉 `calibration.json` 전체가 그 빌드 뒤에 쓰였다.
2. **값 자체가 08-01 과 다르다** — `docs/finding-anchor-population.md:145-159` 의
   08-01 표와 비교하면 `mid` 면적기준이 연남 25.0 → **20.8**, 홍대 23.6 → **20.1** 로,
   앵커도 연남 4.5 → **5.0**, 홍대 8.7 → **8.1** 로 바뀌었다(R-ONE 분기 진행).

→ **`rone_aligned` 는 낡지 않았다. 낡은 것은 `note` 안의 날짜 표기뿐이다.**
   (`git log -1 -- data/gold/yeonnam/calibration.json` → `1723703 2026-09-05`)

---

## 2. 대표 공실률과 `rone_aligned.mid` 는 어떻게 이어지는가

### 2-1. 화면의 12.5% 가 나오는 경로

`scripts/chain_status.py:146-158` `_served_vac()` 는 `coverage.json` 의
`by_capacity_method.floor_ouln.vacancy_pct` 를 읽는다. 그 값은
`data/pipelines/build_page_master.py:550-569` 에서 이렇게 만들어진다.

```
source 가 "stores+ledger*" 인 feature  →  pnu(지번) 중복 제거  →  capacity_method 별 집계
vacancy = 1 − Σactive / Σcapacity          (호실 = 점포 수 / 상업 호수)
```

`page_building_master.geojson` 에서 이 규칙을 그대로 돌리면 **연남 770동 12.53% ·
신촌 690동 17.19% · 홍대 959동 14.97%** — `coverage.json` 값과 일치한다(부록 A-1).
`chain_status` 의 격차는 여기서 앵커를 뺀 것이다.

```
$ PYTHONIOENCODING=utf-8 python scripts/chain_status.py yeonnam sinchon hongdae
  [OK] 앵커   대표 12.5% vs 앵커 5.0%   = +7.5%p
  [OK] 앵커   대표 17.2% vs 앵커 11.68% = +5.52%p
  [OK] 앵커   대표 15.0% vs 앵커 8.1%   = +6.9%p
```

### 2-2. 두 수는 **세 축**에서 갈라진다

| 축 | 서빙 대표값 (12.5 / 17.2 / 15.0) | `rone_aligned.mid` (20.8 / 19.8 / 20.1) |
|---|---|---|
| **모집단** | `capacity_method == floor_ouln` 인 **모든** 상업 건물 — 규모·주용도 무관, 소형(1~2층) 포함 | 일반건축물 · 상가 주용도 · **3층↑ 또는 330㎡ 초과**. 업무·숙박·집합 탈락 |
| **출처 파일** | `page_building_master.geojson` (폴리곤 매칭·상업 판정 통과분) | `building_vacancy.json` (상가정보 bdMgtSn 그룹핑 전체) |
| **단위** | 호실 — `1 − Σactive / Σcapacity` | **면적가중 층 점유** — `Σ(1 − hi/cap)·면적 / Σ면적` (`calibrate_vacancy.py:193-196`) |
| **분자 규칙** | 건물별 `active`(점포 수) | 층 단위 `active_floors_hi`(**상한** = 층 미상 점포·인허가를 빈 층에 낮은 층부터 배정) |

**모집단이 부분집합 관계가 아니다.** `mid` 는 서빙 대표값을 좁힌 것이 아니라 **다른 집합**이다:
연남 `mid` 836동 > 서빙 770동, 홍대 `mid` 1,129동 > 서빙 959동 (신촌만 664 < 690).
`building_vacancy.json` 이 남아 있는 `garosugil` 로 직접 확인했다(부록 A-2) —
capacity 가 있는 지번 **920개** 중 master 의 서빙 지번은 **673개**, 서빙에 없고
`building_vacancy` 에만 있는 지번이 **247개**, 그 반대는 **0개**다.
폴리곤(V-World) 매칭에서 떨어진 건물이 앵커 대조에는 그대로 들어간다.

### 2-3. 그래서 격차가 다르다 — 정리

| 거점 | R-ONE 앵커 | 서빙 대표(호실·전수) | chain_status 격차 | `mid` 면적기준 | calibration 격차 |
|---|---|---|---|---|---|
| yeonnam | 5.00 | 12.53 | **+7.53** | 20.8 | **+15.8** |
| sinchon | 11.68 | 17.19 | **+5.51** | 19.8 | **+8.1** |
| hongdae | 8.10 | 14.97 | **+6.87** | 20.1 | **+12.0** |
| garosugil (대조) | 18.23 | 15.84 | **−2.39** | 19.0 | **+0.8** |

출처: `reports/anchor_gap_2026-09.json` · `data/gold/<hub>/{coverage,calibration}.json`.
(`chain_status` 는 1자리 반올림값을 빼서 `+7.5 / +5.52 / +6.9` 로 찍는다. 위 표는 2자리다.)

> `chain_status` 의 격차는 **정렬되지 않은 값과 앵커의 차**다. 가드레일(`ANCHOR_GAP_MAX = 30.0`,
> `chain_status.py:39`)을 지키는 데는 쓸 수 있어도, "우리가 R-ONE 보다 얼마나 높은가"의
> 답으로 인용하면 안 된다. 그 답은 `+15.8 / +8.1 / +12.0` 쪽이다.

---

## 3. 가설 검증 — "R-ONE 은 중대형 표본, 우리는 전수라 격차가 난다"

### 3-1. 서빙 모집단 **안에서** 규모로 좁혀 본다

`page_building_master.geojson` 의 `floors`(건물 지상층수)와 `com_floors`(공실률 분모가
되는 상업층 목록)로, 서빙 대표값과 **완전히 같은 규칙**(floor_ouln · pnu dedupe · 호실 기준)
아래 규모만 바꿨다. 한 축만 움직이므로 가설이 직접 검증된다.

| 거점 | 앵커 | 전체(=서빙 대표) | 건물층수 ≥3 | 분모층수 ≥3 | 분모층수 ≤2 |
|---|---|---|---|---|---|
| yeonnam | 5.00 | 770동 **12.53%** (+7.53) | 612동 13.23% (**+8.23**) | 397동 14.92% (**+9.92**) | 373동 6.58% |
| sinchon | 11.68 | 690동 **17.19%** (+5.51) | 487동 18.41% (**+6.73**) | 337동 20.35% (**+8.67**) | 353동 8.75% |
| hongdae | 8.10 | 959동 **14.97%** (+6.87) | 777동 15.37% (**+7.27**) | 598동 15.96% (**+7.86**) | 361동 11.27% |
| garosugil | 18.23 | 612동 **15.84%** (−2.39) | 570동 15.84% (−2.39) | 429동 15.82% (−2.41) | 183동 15.96% |

**3거점 전부 격차가 커진다.** 좁힐수록 커지고, 더 좁히면(분모층수 기준) 더 커진다.
`garosugil` 만 평평한데, 이 거점은 애초에 앵커 **아래**(−2.4%p)라 방향을 논할 대상이 아니다.

### 3-2. 왜 반대로 가는가

작은 건물이 서빙 대표값을 **아래로 누르고 있었다**. 분모층수 ≤2 세그먼트의 공실률은
연남 6.58% · 신촌 8.75% · 홍대 11.27% 로 각 거점 전체값보다 낮다. 규모로 좁히면
이 저공실 덩어리가 빠지므로 남은 값이 올라간다.

`calibration.json` 의 소규모 세그먼트가 같은 것을 다른 경로로 말한다 — `small` 은 앵커
**아래**다: 신촌 8.2% vs 앵커 19.54% (**−11.3%p**) · 홍대 6.8% vs 14.91% (**−8.1%p**) ·
가로수길 9.3% vs 14.88% (**−5.6%p**). 연남은 R-ONE 소규모 표본이 없어(`anchor_vac_small_pct: 0.0`)
비교 대상이 없다.

이는 `docs/finding-anchor-population.md:196-205` 의 규모 구간 분해(1\~2층 10.4% → 3\~5층
22.8% → 6\~10층 28.9%)와 방향이 같다. 그때의 진단은 **"작은 건물에서는 맞고 큰 건물에서만
벌어진다"** 였고, 지금 3거점 실측이 그것을 재확인한다.

### 3-3. 판정

**가설은 성립하지 않는다 — 적어도 지금의 출발점에서는 반대다.**

가설이 참이었던 것은 **08-01 시점의 다른 출발점**에서였다. 그때 좁힌 대상은
집합건축물이 섞인 `primary`/`mixed`(연남 50.4% · 홍대 31.0% · 신촌 24.1%,
`coverage.json:mixed_vacancy_pct`)였고, 거기서는 집합(공실률 61.6 / 35.0 / 68.1%,
`coverage.json:by_capacity_method.expos_units`)을 빼는 것만으로 큰 폭이 닫혔다.
**지금의 서빙 대표값은 그 정리가 이미 반영된 값이다** — `gold_vacancy.py:76`
`_COUNTED_METHODS = {"floor_ouln"}` 가 집합건물을 이미 뺀다. 남은 축(규모)은 반대로 민다.

정리하면 **격차를 만드는 것은 표본/전수의 차이가 아니라 큰 건물의 분자 결손**이고,
이는 08-01 에 이미 "후보 B" 로 특정돼 있던 원인이다(`docs/finding-anchor-population.md`
`§0` · `§5-2` — 상가정보 `flrNo` 공란 35.8%, 그 행의 `hoNo` 는 100% 동시 공란이라
상가정보 내부 복원 불가).

---

## 4. 화면에 무엇을 그려야 하는가

### 4-1. 지금 화면의 문제 — 한 앵커에 정렬 안 된 값을 붙여 뺀다

`apps/backend/app/services/gold_vacancy.py:203-233` 은 `floor_ouln` 셀 집계 평균(`avg_vacancy`)에
`anchor_pct`(`calibration.json` 의 R-ONE 중대형)와 `anchor_gap_pp = avg − anchor` 를 붙인다.
프론트는 그것을 그대로 그린다:

- `apps/frontend/src/pages/HubExplorer.tsx:300-317` — `거점 대표 공실률` (12.5%)
- `apps/frontend/src/pages/HubExplorer.tsx:336-345` — `앵커 대조 R-ONE` `5.0% +7.5%p`
- `apps/frontend/src/pages/MapShell.tsx:405-409` — `앵커 5.0% +7.5%p`

한편 **같은 앱의 다른 화면은 다른 수를 쓴다** — `vacancy_forecast.py:37` 과
`ml/inference/predictor.py:41` 은 `rone_aligned.mid`(20.8%)를 쓴다. 지금 프로덕션에는
같은 거점의 공실률이 **12.5% 와 20.8% 두 개** 떠 있고, 둘 다 라벨은 "공실률"이다.
툴팁("모집단·단위가 달라 격차 0 이 정상은 아니다")은 사실을 적고 있지만, **화면의 숫자
`+7.5%p` 자체가 정렬 전 값이라는 사실은 말하지 않는다.**

### 4-2. 두 수를 같이 보여준다면 — 라벨 제안

`+7.5%p` 를 "R-ONE 대비 격차"로 계속 쓰면 안 된다. 격차를 실제보다 **절반 이하로 작게**
보이게 한다(연남 7.5 vs 15.8). 두 수를 나란히, 각자의 모집단을 라벨에 박아 놓는 형태가 맞다.

| 자리 | 라벨 | 값(연남) | 부제 / 툴팁 |
|---|---|---|---|
| 주 지표 | **거점 전체 공실률** <span>(실측·호실 기준)</span> | **12.5%** | 상업 건물 770동 전체 · 1 − 점포/상업호실. 규모·주용도 무관, 집합건축물 제외 |
| 대조 지표 | **중대형 상가 공실률** <span>(R-ONE 정렬)</span> | **20.8%** | R-ONE 과 같은 모집단(3층↑ 또는 330㎡ 초과 · 상가 주용도)·같은 단위(면적 기준) 836동 |
| 앵커 | **R-ONE 중대형 (2026 최신 분기)** | **5.0%** | `calibration.json:anchor_source` · 표본 상권당 중대형 약 16동(`finding-anchor-population.md:23-25`) |
| 격차 | **정렬 격차** | **+15.8%p** | 대조 지표 − 앵커. **주 지표에서 빼지 않는다** |
| 폭 | **불확실 구간** | **15.2 ~ 27.6%** | 층 밴드(`vacancy_floor_hi/lo_pct`). 상가정보 `flrNo` 공란 약 30% 에서 오는 폭 |

지켜야 할 세 가지:

1. **앵커 옆에 붙는 격차는 `rone_aligned.mid` 에서만 뺀다.** 지금처럼 `avg_vacancy − anchor` 를
   `anchor_gap_pp` 로 내려보내면 화면이 구조적으로 격차를 축소한다.
2. **두 수에 서로 다른 이름을 준다.** 둘 다 "공실률"이면 어느 화면을 봤느냐에 따라 답이
   달라진다(지금 heatmap 12.5 / predict-vacancy 20.8 가 그 상태다).
3. **밴드를 같이 싣는다.** 대표값(면적가중 상한)만 단독으로 쓰면 소형에서 과소추정이
   그대로 나간다 — `small` 세그먼트가 앵커 아래로 내려간 것이 그 증상이다(§3-2).

> 이 문서는 **판정만** 한다. 위 라벨은 제안이며, 코드는 한 줄도 고치지 않았다.

---

## 5. 데스크톱이 필요한 것 (이 세션에서 막힌 것)

클라우드 세션에는 `data/bronze` · `data/silver` 가 없다(`.gitignore:25-28`).
`data/gold/<hub>/building_vacancy.json` 도 **`garosugil` 한 거점만** 추적된다
(`git ls-files data/gold | grep building_vacancy` → 1건). 그래서 다음은 못 했다.

| 못 한 것 | 필요한 파일 | 데스크톱 명령 |
|---|---|---|
| `_rone_aligned` 를 3거점에서 직접 재실행 | `gold/<hub>/building_vacancy.json` + `silver/<hub>/building_attrs.json` | `python -m data.pipelines.calibrate_vacancy yeonnam sinchon hongdae` |
| `mid` 모집단이 서빙 모집단을 넘어서는 폭을 3거점에서 세기 | 위와 동일 | 부록 A-2 를 3거점으로 확장 |
| 330㎡ 기준을 반영한 정확한 규모 절단 | `building_attrs.json` 의 `rone_size` | — (§3-1 은 층수만 쓴 근사다) |
| 잔여 격차가 분자 결손인지 재확인 | bronze 상가정보 · 인허가 | `python -m data.analyze_anchor_population` |

§3-1 의 규모 절단은 **연면적 330㎡ 조건이 빠진 근사**다. 3층 미만이면서 330㎡ 를 넘는
건물은 `mid` 에 들어가지만 이 표에서는 "≤2" 로 빠진다. 그런 건물은 저공실 쪽(≤2 세그먼트)에
있으므로, 넣으면 절단값은 §3-1 이 보인 것보다 **내려가는** 방향이다.

절단값과 실제 `mid` 를 나란히 두면 이렇다 — 연남 14.92 → 20.8 · 홍대 15.96 → 20.1 ·
**신촌 20.35 → 19.8**. 신촌만 `mid` 가 절단값보다 낮다. 세 축이 동시에 움직이므로
(모집단 확장 + 면적가중 + 층 단위 분자) 어느 축이 얼마를 밀었는지는 여기서 못 가른다 —
그건 데스크톱에서 `calibrate_vacancy` 를 축별로 끄고 돌려야 나온다.

**다만 결론은 이 근사에 좌우되지 않는다.** §3-1 은 한 축(규모)만 바꾼 통제 비교이고,
그 결과가 3거점 전부 격차 증가다. 330㎡ 조건을 넣으면 절단값이 더 내려가므로
"좁히면 올라간다"는 방향은 약해질 수 있지만, 앵커 대조에 실제로 쓰이는 값인
`mid`(20.8 / 19.8 / 20.1%)가 서빙 대표값(12.53 / 17.19 / 14.97%)보다 **3거점 전부 높다**는
사실은 근사와 무관하게 파일에 그대로 적혀 있다.

---

## 부록 A — 재현

전부 `data/gold` 의 git 추적 파일만 읽는다. 네트워크 0콜, bronze/silver 불필요.

### A-0. 기계가 읽을 값 재생성 (`reports/anchor_gap_2026-09.json`)

```bash
cd /path/to/spaceos
PYTHONIOENCODING=utf-8 python - <<'PY'
import json
from pathlib import Path
GOLD = Path("data/gold")
HUBS = ["yeonnam", "sinchon", "hongdae", "garosugil"]

def served_rows(slug):
    fc = json.loads((GOLD / slug / "page_building_master.geojson").read_text(encoding="utf-8"))
    seen, rows = set(), []
    for f in fc["features"]:
        p = f["properties"]
        if not str(p.get("source", "")).startswith("stores+ledger"):
            continue
        if p["pnu"] in seen:
            continue
        seen.add(p["pnu"]); rows.append(p)
    return rows

def rate(rs, anchor=None):
    a = sum(r["active"] for r in rs); c = sum(r["capacity"] for r in rs)
    v = round((1 - a / c) * 100, 2) if c else None
    out = {"buildings": len(rs), "active": a, "capacity": c, "vacancy_pct": v}
    if anchor is not None and v is not None:
        out["gap_pp"] = round(v - anchor, 2)
    return out

out = {"generated_for": "docs/finding-anchor-gap-2026-09.md",
       "reproduce": "docs/finding-anchor-gap-2026-09.md 부록 A 의 heredoc 을 그대로 실행",
       "inputs": ["data/gold/<hub>/page_building_master.geojson",
                  "data/gold/<hub>/coverage.json",
                  "data/gold/<hub>/calibration.json"],
       "hubs": {}}
for h in HUBS:
    cal = json.loads((GOLD / h / "calibration.json").read_text(encoding="utf-8"))
    cov = json.loads((GOLD / h / "coverage.json").read_text(encoding="utf-8"))
    anchor = cal["anchor_pct"]
    rows = [r for r in served_rows(h) if (r.get("capacity_method") or "") == "floor_ouln"]
    out["hubs"][h] = {
        "gold_built_at": cov["built_at"],
        "anchor_mid_pct": anchor,
        "anchor_small_pct": cal.get("anchor_vac_small_pct"),
        "served": rate(rows, anchor),
        "narrowed_bldg_floors_ge3": rate([r for r in rows if (r.get("floors") or 0) >= 3], anchor),
        "narrowed_denom_floors_ge3": rate([r for r in rows if len(r.get("com_floors") or []) >= 3], anchor),
        "narrowed_denom_floors_le2": rate([r for r in rows if len(r.get("com_floors") or []) < 3], anchor),
        "calibration_rone_aligned": cal.get("rone_aligned"),
        "calibration_combined_pct": cal.get("estimated_vacancy_pct"),
        "coverage_mixed_pct": cov.get("mixed_vacancy_pct"),
        "coverage_by_capacity_method": cov.get("by_capacity_method"),
    }
Path("reports/anchor_gap_2026-09.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
for h, v in out["hubs"].items():
    m = v["calibration_rone_aligned"].get("mid") or {}
    print(f"{h:10s} 앵커 {v['anchor_mid_pct']:5.2f}% · 서빙 {v['served']['vacancy_pct']:5.2f}% "
          f"({v['served']['gap_pp']:+.2f}%p) · 중대형정렬 {m.get('vacancy_area_pct')}% "
          f"({m.get('gap_pp'):+}%p)")
PY
```

기대 출력:

```
yeonnam    앵커  5.00% · 서빙 12.53% (+7.53%p) · 중대형정렬 20.8% (+15.8%p)
sinchon    앵커 11.68% · 서빙 17.19% (+5.51%p) · 중대형정렬 19.8% (+8.1%p)
hongdae    앵커  8.10% · 서빙 14.97% (+6.87%p) · 중대형정렬 20.1% (+12.0%p)
garosugil  앵커 18.23% · 서빙 15.84% (-2.39%p) · 중대형정렬 19.0% (+0.8%p)
```

### A-1. 서빙 대표값 재현 + `calibration.combined` 대조 (§1-1 · §2-1)

```bash
PYTHONIOENCODING=utf-8 python - <<'PY'
import json, collections
for h in ("yeonnam", "sinchon", "hongdae"):
    fc = json.load(open(f"data/gold/{h}/page_building_master.geojson", encoding="utf-8"))
    seen, agg = set(), collections.defaultdict(lambda: {"a": 0, "c": 0, "n": 0})
    ca = cc = 0
    for f in fc["features"]:
        p = f["properties"]
        if not str(p.get("source", "")).startswith("stores+ledger"):
            continue
        ca += p.get("active", 0); cc += p.get("capacity", 0)   # combined(v1) — dedupe 없음
        if p["pnu"] in seen or not p.get("capacity"):
            continue
        seen.add(p["pnu"])
        m = p.get("capacity_method") or "unknown"
        agg[m]["a"] += p["active"]; agg[m]["c"] += p["capacity"]; agg[m]["n"] += 1
    print(h, {m: (v["n"], round((1 - v["a"] / v["c"]) * 100, 2)) for m, v in agg.items()},
          "| combined", round((1 - ca / cc) * 100, 1))
PY
# → yeonnam {'floor_ouln': (770, 12.53), 'expos_units': (57, 61.61)} | combined 50.4
#   sinchon {'floor_ouln': (690, 17.19), 'expos_units': (103, 35.03)} | combined 24.1
#   hongdae {'floor_ouln': (959, 14.97), 'expos_units': (51, 68.07)} | combined 31.0
# combined 50.4 / 24.1 / 31.0 == calibration.json:estimated_vacancy_pct (동일 빌드 증거)
# floor_ouln 12.5 / 17.2 / 15.0 == coverage.json:by_capacity_method (서빙 대표값)
```

### A-2. `mid` 모집단이 서빙 모집단의 부분집합이 아님 (§2-2) — `garosugil` 만 가능

```bash
PYTHONIOENCODING=utf-8 python - <<'PY'
import json
rows = json.load(open("data/gold/garosugil/building_vacancy.json", encoding="utf-8"))
fc = json.load(open("data/gold/garosugil/page_building_master.geojson", encoding="utf-8"))
bv = {r.get("lnoCd") for r in rows if r.get("capacity")}
ml = {f["properties"]["pnu"] for f in fc["features"]
      if str(f["properties"].get("source", "")).startswith("stores+ledger")}
print("building_vacancy pnu", len(bv), "| 서빙 pnu", len(ml),
      "| bv−서빙", len(bv - ml), "| 서빙−bv", len(ml - bv))
PY
# → building_vacancy pnu 920 | 서빙 pnu 673 | bv−서빙 247 | 서빙−bv 0
```

### A-3. 규모 절단 (§3-1)

```bash
PYTHONIOENCODING=utf-8 python - <<'PY'
import json
for h in ("yeonnam", "sinchon", "hongdae", "garosugil"):
    fc = json.load(open(f"data/gold/{h}/page_building_master.geojson", encoding="utf-8"))
    seen, rows = set(), []
    for f in fc["features"]:
        p = f["properties"]
        if not str(p.get("source", "")).startswith("stores+ledger"):
            continue
        if (p.get("capacity_method") or "") != "floor_ouln" or p["pnu"] in seen:
            continue
        seen.add(p["pnu"]); rows.append(p)
    def r(rs):
        a = sum(x["active"] for x in rs); c = sum(x["capacity"] for x in rs)
        return f"{len(rs):4d}동 {round((1 - a / c) * 100, 2):6.2f}%" if c else "  -"
    print(f"{h:10s} 전체 {r(rows)}"
          f" | 건물층수>=3 {r([x for x in rows if (x.get('floors') or 0) >= 3])}"
          f" | 분모층수>=3 {r([x for x in rows if len(x.get('com_floors') or []) >= 3])}"
          f" | 분모층수<=2 {r([x for x in rows if len(x.get('com_floors') or []) < 3])}")
PY
# → yeonnam    전체  770동  12.53% | 건물층수>=3  612동  13.23% | 분모층수>=3  397동  14.92% | 분모층수<=2  373동   6.58%
#   sinchon    전체  690동  17.19% | 건물층수>=3  487동  18.41% | 분모층수>=3  337동  20.35% | 분모층수<=2  353동   8.75%
#   hongdae    전체  959동  14.97% | 건물층수>=3  777동  15.37% | 분모층수>=3  598동  15.96% | 분모층수<=2  361동  11.27%
#   garosugil  전체  612동  15.84% | 건물층수>=3  570동  15.84% | 분모층수>=3  429동  15.82% | 분모층수<=2  183동  15.96%
```

### A-4. 체인 상태(격차 원문)

```bash
PYTHONIOENCODING=utf-8 python scripts/chain_status.py yeonnam sinchon hongdae
```

---

## 부록 B — 인용한 파일

| 경로 | 무엇을 인용했나 |
|---|---|
| `data/pipelines/calibrate_vacancy.py:139-205` | `_rone_aligned()` 정의 · 세그먼트 판정 · 면적가중 식 |
| `data/pipelines/calibrate_vacancy.py:217-269` | 입력 파일 · `run()` 안에서의 호출 위치 |
| `data/pipelines/calibrate_vacancy.py:202` | `note` 의 `(2026-08-01)` 하드코딩 |
| `data/pipelines/build_building_attrs.py:262-267,281` | `is_mall` / `is_shop` / `rone_size` 판정, `load()` 가 읽는 silver 경로 |
| `data/pipelines/build_page_master.py:550-569,596-613` | 서빙 대표값 산식(pnu dedupe) · `coverage.json` 기록 |
| `scripts/chain_status.py:39,146-158,260-276` | 가드레일 30%p · `_served_vac()` · 앵커 단계 |
| `scripts/run_hub_chain_batch.py:235-243` | 파이프라인 실행 순서 |
| `apps/backend/app/services/gold_vacancy.py:76,203-233` | `_COUNTED_METHODS` · `anchor_gap_pp` 계산 |
| `apps/backend/app/services/vacancy_forecast.py:34-38` · `ml/inference/predictor.py:38-42` | `rone_aligned.mid` 소비처 |
| `apps/frontend/src/pages/HubExplorer.tsx:300-345` · `MapShell.tsx:405-409` | 현재 화면 라벨 |
| `data/gold/<hub>/calibration.json` | `anchor_pct` · `rone_aligned.{mid,small,mall}` · `estimated_vacancy_pct` |
| `data/gold/<hub>/coverage.json` | `built_at` · `by_capacity_method` · `mixed_vacancy_pct` |
| `data/gold/<hub>/page_building_master.geojson` | `active` · `capacity` · `capacity_method` · `floors` · `com_floors` · `pnu` · `source` |
| `data/gold/garosugil/building_vacancy.json` | 앵커 모집단 대조(유일하게 추적되는 거점) |
| `docs/finding-anchor-population.md:1-10,120-159,196-219` | 08-01 선행 판정 · 규모 구간 분해 · `flrNo` 공란 |
| `reports/anchor_gap_2026-09.json` | 이 문서 수치의 기계 판본 |

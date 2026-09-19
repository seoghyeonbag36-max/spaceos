# 근거 인덱스 — 논문 본문에 쓸 수 있는 수치의 전부

**이 파일에 없는 숫자는 논문에 쓰지 않는다.** 새 수치가 필요하면 먼저 여기에
출처·재현 경로와 함께 등재한 뒤 본문에 쓴다. → [README.md](README.md) 작성 규칙

⚠ **모집단이 다른 값을 섞지 말 것.** 아래 표는 세 종류의 실험 조건을 담고 있고
서로 비교 가능하지 않다. 각 수치의 조건을 반드시 확인한다.

| 조건 | 그래프 | 라벨 | 피처 | 시점 |
|---|---|---|---|---|
| **A. 서빙본** | 66거점 47,442노드 | category_group 7종 | 117열 | 2026-09-05 |
| **B. 실험군(group)** | 54거점 | category_group 7종 | 105/115열 | 2026-08-19~26 |
| **C. 실험군(category2)** | 54거점 | category 2단계 32클래스 | 105/115열 | 2026-08-27 |

Page의 **조건 D(2026-09-06 동결 구조 감사)**는 아래 별도 절에 등재한다. 위 그래프 조건 A/B/C와 모집단·태스크가 다르며 합산하지 않는다.

⚠ B 의 off-prior 37.6% 와 A 의 33.8% 는 **성능 저하가 아니다** — 거점이 54→66 으로
늘며 모집단이 바뀐 것이다(`docs/feature-platform.md` §0 이 직접 경고한다).

---

## P1 · Platform — GNN 업종추천

### 집필 시 해석 정정 및 재현 범위 2026-09-19

아래 원래 기록의 수치는 보존하되 해석은 이 절을 우선한다. 기각 결과를 개선으로 바꾸는 정정이 아니라 과도한 통계적 단정을 제한하는 정정이다.

- PLATFORM-E01: `train_gnn.py::_split`, `_district_top3`, `_offprior_top3` 대조. 클래스별 60/20/20 노드 분할, train 라벨만으로 거점 Top-3 정의. 같은 그래프의 전이적 평가이며 새 거점·미래 시점 외부 검증이 아니다. off-prior는 사전분포 실패 부분집합이며 그래프 구조의 순수 인과 기여를 분리하지 않는다.
- PLATFORM-E02: `train_gnn.py`의 lift 계산은 Top-1 기준선 대비 상대 증가율이다. +5.3%를 Top-3 차이로 해석하지 않는다. `ml/models/gnn/industry_gnn.py`는 GCNConv 기반이다.
- PLATFORM-E03: 조건 B 표는 기준 포함 네 행으로, 서로 다른 시드·모집단의 독립 반복 네 번이 아니다. 단일 팔 SE 1.63%p와 차이 비교만으로 쌍대 유의성을 판정하지 않는다. 조건 C의 4.32배는 off-prior 표본 수 증가이며 검정력 자체의 배수가 아니다. p=1.0은 효과 영 또는 동등성의 증명이 아니다.
- PLATFORM-E04: §0-O의 MDE는 유의수준 0.05에서 `1.96√D/n`으로 계산한 근사 검출 경계다. 목표 검정력·대립가설 오차를 포함한 정식 표본설계가 아니다. 다른 라벨 과제의 경계를 비교해 같은 효과를 검출한다고 주장하지 않는다. 노드 간 공간 의존성도 반영하지 않았다.
- PLATFORM-E05: 2026-09-15 노드 소스 교체와 과거 Bronze 삭제로 현행 학습 명령은 옛 그래프의 재현을 보장하지 않는다. 출처 `ml/training/train_gnn.py` 머리말, `docs/finding-map-provider-google-2026-09-15.md`. 본 원고 조건 A/B/C는 역사적 보존 결과이며 현재 신규 학습의 성능이 아니다.
- PLATFORM-E06: `reports/gnn_category2_mcnemar_2026-08-27.json`은 노드별 덤프가 gitignore 대상이고 요약만 새 클론에서 검증 가능하다고 명시한다. 합계 741+2747+148+149=3785, 불일치 148+149=297, 두 팔 차이 +0.03pp, 연속성 보정 chi2=0.0·p=1.0을 요약에서 검산한다. 학습 재실행과 구별한다.
- PLATFORM-E07: Kipf, T. N. & Welling, M. (2017), *Semi-Supervised Classification with Graph Convolutional Networks*, ICLR, arXiv:1609.02907. [저자 PDF](https://arxiv.org/pdf/1609.02907)의 초록·서론·전파식 확인.
- PLATFORM-E08: Shchur, O., Mumme, M., Bojchevski, A. & Günnemann, S. (2018), *Pitfalls of Graph Neural Network Evaluation*, Relational Representation Learning Workshop, NeurIPS, arXiv:1811.05868. [저자 연구실 서지](https://www.cs.cit.tum.de/daml/gnn-benchmark/)와 [PDF](https://arxiv.org/pdf/1811.05868)의 초록·서론 확인. 원문 성능 숫자 전재 없음.

### 서빙본 성능 (조건 A)

| 값 | 수치 | 출처 |
|---|---|---|
| 그래프 규모 | 노드 47,442 · 엣지 188,673 · 피처 117열 | `feature-platform.md` §0 |
| Top-1 / Top-3 | **64.9% / 91.7%** | 홀드아웃 층화 60/20/20 |
| macro-F1 | 0.235 | 〃 |
| 거점 사전분포 기준선 | Top-1 61.7% / Top-3 89.4% | 〃 |
| **lift** | **+5.3%** | 〃 |
| off-prior Top-3 | **33.8%** (n=1,011) | `test_offprior_top3` |
| 태스크 | 업종을 가리고 입지만으로 대분류 7종 분류 | `feature-platform.md` §0 |

> 논문의 핵심 관찰: **Top-3 91.7% 는 높아 보이지만 기준선이 이미 89.4%다.**
> "어느 거점이냐"가 업종 대부분을 결정하고 그래프가 얹는 정보는 작다.
> off-prior(사전분포로는 정의상 맞힐 수 없는 자리)만이 그래프의 실제 기여를 잰다.

### 성능 천장 — 4회 독립 확인 (조건 B)

레버를 넷 바꿔 봤고 **전부 표준오차(약 1.63%p) 안**이었다.

| 시도 | off-prior Top-3 | 판정 | 출처 |
|---|---|---|---|
| 기준 (105열) | 37.63% | — | §0-D |
| 이웃 업종 분포 8열 추가 (113열) | 36.49% | 기각 | §0-I |
| 조기종료 기준 3종 ablation | 35.92 ~ 37.17% | 기각 | §0-E · `reports/gnn_selectby_ablation.json` |
| 행정동 24시간 축 10열 (115열) | 37.51% | 기각 | §0-J · `reports/gnn_adong_2026-08-25.json` |

> **§0-E 의 결정적 관찰**: 게이트 지표(off-prior)를 val 에서 **직접 최적화**한 팔이
> macro_f1 최적화 팔과 소수점까지 같은 값(37.17%)에 멈췄다. val 은 37.70%까지 올랐고
> test 는 37.17% — val 과잉적합도 아니다. **이 피처 집합의 천장이 37%대**라는 뜻이다.

### 진단 — 막는 것은 변동의 **양**이 아니라 **종류** (§0-J)

within-district 분산 0.221짜리 10열을 실제로 늘렸는데도 움직이지 않았다.
시간·유동 계열로는 **약국을 병원 옆에서 가릴 수 없다.** 필요한 것은 업종 자체에 대한
정보(감성·인접 구조)이고, 그 두 경로는 §0-K(감성)·§0-I(인접)가 각각 기각했다.

### 감성 경로 기각 (§0-K, 2026-08-25)

600ep 을 돌리지 않고 기각했다. 수집은 이미 끝나 있었고, 세 다리를 재 보니 셋 다 끊긴다.
리뷰 유사도 엣지 불가 사유: 네이버 블로그 검색 API 가 본문이 아닌 **약 150자 스니펫**만 준다
— 27거점 8,554건 중 점포명 2개 이상 동시 언급 **15건(0.2%)**. 점포 단위 리뷰 원문은 공식 API 부재.

### 라벨 세분화 — 검정력 4.32배 확보 후 "가를 차이 없음" 확인 (조건 C, §0-N)

출처: `reports/gnn_category2_mcnemar_2026-08-27.json` · 32클래스 · seed 42

| 표본 확대 | 값 |
|---|---|
| group off-prior n | 877 |
| **category2 off-prior n** | **3,785** (4.32배) |
| 표준오차 | 1.63pp → **0.78pp** |

| 팔 | 피처 | Top-1 | Top-3 | macro-F1 | off-prior Top-3 | lift |
|---|---|---|---|---|---|---|
| control_105 | 105 | 0.3267 | 0.6063 | 0.0733 | **0.2349** | 30.7% |
| adong_115 | 115 | 0.3229 | 0.6033 | 0.0719 | 0.2325 | 29.2% |
| jipgyegu_115 | 115 | 0.3272 | 0.6031 | 0.0710 | **0.2351** | 30.9% |

기준선: major_top1 0.2266 · district_prior_top1 0.2500 · district_prior_top3 0.5323

**McNemar (control_105 vs jipgyegu_115, n=3,785)**: both_hit 741 · both_miss 2,747 ·
a_only 148 · b_only 149 · discordant 297 · 델타 **+0.03pp** · chi2 = 0.0 · **p = 1.0**

> 검정력을 4.32배로 키운 뒤에도 p=1.0 이다. **표본이 부족해서 못 가른 것이 아니라
> 효과가 0 이다.**

### 수집을 사기 전에 기각 — 검정력 계산 (§0-O, 2026-08-27)

`reports/offprior_hub_yield_probe_2026-08-27.json` · `scripts/offprior_hub_yield_probe.py`
(학습 없이 `_split`/`_district_top3` 재사용)

거점별 off-prior 수율: 전체 **0.0217** · 중앙 0.0209 · 최소 0.0052(nokdu) ~ 최대 0.0429(gwangjang)
· **변동계수 CV 0.39** · 거점 크기 중앙 720노드
→ off-prior 2배에 필요한 신규 거점: 평균 수율 **56곳** · 상위 4분위만 골라도 **45곳**
(= 지금 프로젝트를 통째로 한 번 더 짓는 규모)

**McNemar 최소검출효과 MDE** (p<0.05, `|n01 - n10| = 1.96 * sqrt(D)`)

| 구성 | n | MDE |
|---|---|---|
| group 현재 | 877 | 2.25pp |
| **category2 현재 (이미 확보)** | **3,785** | **0.89pp** |
| group + 거점 2배 (신규 45~56곳 수집) | 1,754 | 1.59pp |
| category2 + 거점 2배 | 7,570 | 0.63pp |

> **거점을 2배로 늘려 얻는 MDE 1.59pp 는, 라벨 세분화로 공짜로 얻은 0.89pp 보다 나쁘다.**
> 45~56거점을 새로 수집해 이미 가진 것보다 낮은 해상도를 사는 셈이다.

실측 효과크기를 유의하게 가르는 데 필요한 표본:

| 비교 | 실측 델타 | 필요 n | = 거점 |
|---|---|---|---|
| jipgyegu vs adong | +0.26pp | 44,592 | 636곳 |
| adong vs control | −0.24pp | 52,334 | 747곳 |
| jipgyegu vs control | +0.03pp | 3,349,347 | 47,785곳 |

서울에 이 성격의 상권이 636곳 있지 않다. **표본으로 가를 수 있는 문제가 아니다.**

### 수요신호 주입 — 유일한 양성 결과 (2026-08-16)

| 지표 | 종전(58피처) | 수요신호(95피처) | 델타 |
|---|---|---|---|
| test_top1 | 0.6308 | 0.6384 | +0.0076 |
| test_top3 | 0.9050 | 0.9080 | +0.0030 |
| test_macro_f1 | 0.1887 | **0.2124** | +0.0237 (상대 **+12.6%**) |
| lift | 3.1 | **4.4** | +1.3 |

> 읽는 법: **macro-F1 +12.6% 가 top-1 +0.76%p 보다 중요하다.** 음식점 60% 편중 탓에
> top-1 은 다수 클래스가 지배한다. macro-F1 상승은 약국·문화시설 같은 희소 업종이
> 실제로 더 뽑히기 시작했다는 뜻이고, 추천 다양성은 제품 가치에 직결된다.

### 라벨 단계와 정확도의 교환 관계

라벨을 category 2단계(30클래스)로 내리면 **lift +22%로 커지나 Top-3 57%로 KPI 미달.**
세분 업종일수록 그래프 정보가 더 필요하지만 절대 정확도는 낮다.

---

### LSTM 공실 예측 — 서빙본 (2026-09-04 학습 · 66거점)

⚠ **GNN 의 조건 A/B/C 와 다른 모집단·태스크다.** 위 표들과 합산하거나 비교하지 않는다.
태스크는 분기 시계열의 **방향**(오르는가 내리는가) 예측이고, 공실률 값 자체의 정확도가
아니다. 인용할 때 "방향 정확도"라는 말을 떼지 않는다.

| 값 | 수치 | 출처 |
|---|---|---|
| 방향 정확도 | **70.8%** (46/65) | `feature-platform.md` §0 · 홀드아웃 |
| MAE / RMSE | **1.061** / **1.387** (vac_proxy 원단위) | 〃 |
| look_back | 8분기 (분기 데이터라 30개월이 아니다) | `feature-platform.md` §0 |
| 산출물 | `ml/artifacts/vacancy_lstm.pt` · `data/gold/platform_vacancy_forecast.json` · `ml/mlruns` | 〃 |
| 학습 | `ml/training/train_lstm.py` | 〃 |

**거점 확장에 따른 보수화** — 표본이 커질수록 지표가 내려간다. 앞의 값들보다 마지막 값을
인용한다(신뢰구간이 가장 좁다).

| 거점 | 방향 정확도 | MAE |
|---|---|---|
| 13 | 84.6% | 0.901 |
| 27 | 74.1% | 0.803 |
| 54 | 72.2% | 1.109 |
| **66 (서빙본)** | **70.8%** | **1.061** |

> **논문에서 쓸 수 있는 자리**: 이 곡선 자체가 재료다. 초기 표본에서 높게 나온 값이
> 모집단을 넓히며 어떻게 내려앉는지를 네 지점으로 보인 기록은 드물다. 목표선 70%를
> **0.8%p 차로** 넘고 있다는 사실도 함께 쓴다 — 거점이 더 늘면 내려갈 수 있는 자리다.

⚠ **알려진 취약점**: 신규 거점을 `data/config/rone_districts.py` 에 등재하지 않으면 해당
거점의 R-ONE 열이 전 분기 NaN 이 되고, **pooled LSTM 이 전 거점 NaN 으로 붕괴한다**
(`feature-platform.md` §0). 성능 수치를 재현할 때 이 매핑을 먼저 확인한다.

---

## P2 · Page — 건물 단위 공실률 데이터셋

| 값 | 수치 | 출처 |
|---|---|---|
| Tier1(건축물대장 실측) 거점 | **66/66** | `scripts/pppp_status.py` |
| 대표 집계 커버리지 90% 이상 | 66/66 (최저 100.0%) | 〃 |
| R-ONE 앵커 대조 보유 | 66/66 | 〃 |
| 히트맵 레이어 | 공실 · 임대(R-ONE) · 유동 · 밀도 (동일 100m 격자) | 〃 |

### 공간 해상도 승격 — 상권 → 집계구 (2026-08-26)

| 값 | 수치 |
|---|---|
| 집계구 수 | 거점당 중앙 **26곳** (4~66) |
| 집계구 면적 중앙 | **22,407㎡** |
| 커버된 셀 | **3,699개 · 54/54거점 전부** (부분 커버 거점 0) |

> **한 화면에 두 눈금이 섞이면 색은 그럴듯한데 셀 간 비교가 거짓이 된다** — 그래서
> 거점 단위 전부-아니면-전무로 싣는다. 논문에서 방법론적 주장으로 쓸 수 있는 원칙이다.

### 승격이 실제로 무엇을 고쳤는가 — 검증 가능한 형태

종전 셀 값은 `(상권 총량) × (거점 공통 구성비)` 였다. 시각을 바꿔도 **모든 셀에 같은
상수가 곱해져** 거점 내 서열이 구조적으로 불변이었다(슬라이더가 밝기만 바꿨다).

| 검증 | 결과 |
|---|---|
| 시각에 따라 셀 서열이 바뀌는 거점 | **52/54** |
| 03시 vs 14시 Spearman rho | 중앙 **0.812** · 최소 0.498(kyunghee) |
| 대조군(상권 경로) rho | **1.000** (테스트가 고정) |

⚠ **입도가 올라간 것이지 격자 실측이 된 것은 아니다** (집계구 22,407㎡ > 셀 10,000㎡).
⚠ 점포 밀도(`stor`)는 집계구 원천이 없어 **상권 단위에 남았다** — 같은 레이어 안에서 눈금이 다르다.

### 시간 축

평일 24시간 66거점 · 주말 66거점 (표본 28일: 평일 20 / 주말 8).
미충족 거점은 응답이 `time_source:"trdar_band"` 로 6구간임을 밝히고 물러난다.

---

## P3 · Posting — 공개 데이터의 ROI 정밀도 한계

⚠ **이 편은 양성 결과가 적고 기각 기록이 많다.** 그것을 논문의 주장으로 삼는다:
"공개 데이터 범위에서 층·면적 축 ROI 정밀화는 닫혀 있다"를 **증명하는** 편이다.

| 근거 | 내용 | 출처 |
|---|---|---|
| 3-Tier 폴백 | 고급화/가성비/기능중심 + `roi_months` | `services/districts.tier_scenarios` |
| 감도 실험 | **32조합 전수** | §0-D |
| 유닛 면적 입도 | **50%** (게이트 폐기 2026-09-05, 관측 전용) | `pppp_status.py` |
| `prem`(권리금) | 수집 과제가 아니라 **입력 계약**으로 확정 | §0-K |
| 집합건물 전유부 편입 | 정량 조사 후 **기각** | §0-R |
| 호실 면적 공식 소스 | 공개 범위에서 **닫힘** | §0-S · `finding-posting-unit-area-sources-2026-08-29.md` |
| 상가정보 `flrNo` 로 면적 특정 | 재 보고 **기각** | §0-W · `finding-posting-unit-area-flrno-2026-09-06.md` · `reports/posting_unit_area_flrno_probe_2026-09-06.json` |
| 층 축 | 두 번(§0-M·§0-Q) 같은 벽에 부딪힘 — 균등분할 유지 | §0-M · §0-Q |
| R-ONE 서울 모집단 | **59~64 상권**뿐 (21분기 58 / 17분기 1 / 7분기 5) | §0-O · `rone_districts.py` 전수확인 2026-07-24 |

> **§0-N 의 특징적 기록**: 매출 앵커에서 버그를 하나 찾아 고쳤는데 **그래도 가설은 기각됐다.**
> 버그 수정이 결과를 바꾸지 않았다는 것을 남긴 기록은 드물다.

⚠ 3D 디지털 트윈은 2026-09-05 폐기(§0-V) — 절차적 박스가 실측 형상이 아니었다.
번들 832KB → 4KB. 논문에서 "시각화 충실도 ≠ 정보량" 사례로 쓸 수 있다.

---

## P4 · Program — LLM 마케팅 생성의 사실성 가드레일

⚠ **정량 평가가 없다.** 아래는 전부 설계·계약·테스트 통과 기록이고 성능 수치가 아니다.
실증 논문으로 쓰려면 평가 설계부터 새로 해야 한다 → README 의 경고 참조.

| 근거 | 내용 | 출처 |
|---|---|---|
| 생성 엔진 | `POST /marketing/generate` + ProgramStudio + `ha_guard` 후처리 | `services/marketing.py` · `services/ha_guard.py` |
| 입력 계약 3층 | 자리 · 상권 · 검증 브리프(2026-09-17 대상 재정의 — 예비창업자·팝업/가오픈/MVP 검증) | §0-V · `tests/test_posting_marketing.py` 브리프 배선 · `tests/test_ha_guard.py` 미검증 경험 |
| 출력 분리 | 퍼포먼스 / 상권활성화 | §0-F · `tests/test_program_output_split.py` (14건) |
| ~~상용 온보딩~~ | 2026-09-17 삭제 — 받을 점주 원문이 없다 | §0-K · §0-V |
| 검증 지표 | 지표 · 측정 방법 · 목표선 · 기각 조건 | §0-V · `tests/test_program_output_split.py` · `tests/test_ha_guard.py` 지표 검사 |
| 검색 트렌드 라벨 | 66/66거점 | `pppp_status.py` |
| 데이터 채널 타당성 | 채널별 가능/불가 전수 판정 (크롤링 금지선 포함) | §0 (2026-07-18) |

> **트렌드 라벨의 의미와 수정 이력**: 종전에는 라벨이 없으면 트렌드 검사가 조용히 통과했다.
> 현재 `_check_trend`는 컨텍스트·라벨 부재에 `trend_unverified` 경고를 반환한다.
> 아래 P3·P4 집필 보완 근거의 PROGRAM-E02를 따른다. 과거 실패를 현행 동작으로 서술하지 않는다.

---

## 교차 편 — 방법론 (어느 편에도 쓸 수 있다)

이 저장소가 반복적으로 실행한 절차. P1 에서 정식화하고 나머지 편에서 인용하는 것을 권한다.

1. **값싼 프로브를 먼저 산다** — 학습·수집 없이 기존 split 재사용으로 표본·수율만 잰다
2. **검정력을 먼저 계산한다** — MDE 가 실측 효과크기보다 크면 그 실험은 사지 않는다
3. **음성 결과를 지우지 않는다** — 지우면 다음 사람이 같은 것을 다시 시도한다(§0-I 가 명시)
4. **문서가 낡는 것을 구조로 막는다** — 진행률·거점 수의 단일 출처는 스크립트다

> 4번의 근거: 이 저장소의 문서는 실제로 두 번 낡았다(08-02 Tier1 13거점, 08-09 22거점에서 멈춤).
> `scripts/pppp_status.py` · `scripts/chain_status.py` 가 산출물에서 직접 센다.

---

## 등재 대기 (본문에 쓰기 전 확인 필요)

- [x] LSTM 공실 예측 성능 — 2026-09-09 등재 완료. [서빙본 절](#lstm-공실-예측--서빙본-2026-09-04-학습--66거점) 참조. GNN 조건 A/B/C 와 모집단·태스크가 다르므로 합산하지 않는다
- [ ] Page 공실률의 R-ONE 앵커 대비 **격차 수치** — "앵커 대조 보유 66/66"은 보유일 뿐 격차가 아니다
- [ ] Posting 감도 실험 32조합의 **결과 수치** — 조합 수만 인덱스에 있다
- [x] Page 핵심 문헌 Alsudais의 저자 공개본 v2: 8페이지 텍스트·시각 대조 완료. [읽기 장부](page-study/reading-ledger.md). 출판본·별도 부록·보조문헌 전체 본문은 미확인이고, 다른 P의 상태를 완료로 바꾸지 않는다.

---

## 알려진 문서 결함 (앵커를 걸기 전에 알아야 한다)

⚠ `docs/feature-platform.md` 에 **`0-M` 이 두 번** 있다 (line 305 "감성 구역을 행정동
실측 구역으로" · line 466 "집계구 배선 → 600ep → McNemar"). 앵커로 인용할 때 절 번호만
쓰면 어느 쪽인지 알 수 없다 — **제목까지 함께 적는다.**

---

<a id="page-condition-d"></a>

## P2 · Page — 조건 D: 동결 자료의 구조 감사·영향·계산 재현성

등재일: 2026-09-07. 원 실행은 `audits/page-analysis-20260906`, 입력 명세는 `audits/page-inventory-20260906/manifest.json`이다. 이 절의 수치는 특정 입력 묶음에 대한 결과이며 현재 운영 전체·서울 전체·실제 공실 정확도로 확대하지 않는다. [추가 검증 결과](page-study/evidence-verification.json)의 `summary` 및 참조 파일 해시로 재확인했다.

| 근거 ID | 수치·판정 | 원천 / 검증 경로 | 허용되는 해석 |
|---|---|---|---|
| PAGE-D01 | 66거점 · 52,642 마스터 폴리곤 | `structural-audit.json`의 `hubs`, `rules`; 추가 검증 `hubs/polygons` | 동결된 가공 마스터 검사 범위 |
| PAGE-D02 | 층 정보 검사 30,912 폴리곤 | `rules.floor_semantics`, `rules.floor_interval_formula` | 해당 분모에서 계산 일관성 확인 |
| PAGE-D03 | 원천 관측 시점 정렬 66거점 평가 불가 | `rules.temporal_observation_alignment` | 최신성·동시점 현실 검증 완료 아님 |
| PAGE-D04 | 별도 프로세스 반복에서 마스터·커버리지·서빙 66/66 일치 | `reproduction-comparison.json`; 커버리지는 `built_at`만 제외 | 동일 선택 입력 반복. 바이트 비교는 마스터에만 해당 |
| PAGE-D05 | 기존 행 순서 시험 198회 · 거점 집계 변경 0회 · 격자 소속 또는 분자·분모 영향 65거점 | `order-sensitivity.json`; 추가 검증 `order_*` | 동일 내용 순서 변형의 사후 탐색. 현실 위치 오차·독립 표본 수 아님 |
| PAGE-D06 | 층 배정 범위 폭 중앙값 16.235267101643892%p · 최댓값 34.38818565400844%p | `impact-intervals.json`; 추가 검증 `floor_interval_*` | 정보 부족에 따른 범위. 통계적 신뢰구간·현실 공실 오차 아님 |
| PAGE-D07 | 독립 검토 표본 211개 전부 `unresolved` | `sample-design.json`, `independent-review-sample.csv` | 사람 정답·오류율 미확보. 2026-09-07 사용자도 자료·검토자 부재 확인 |
| PAGE-D08 | 보존 서빙 사본 비교 66/66 · 독립 셀 재합산 66/66 통과 | 추가 검증 `stored_serving_comparisons_pass/cell_reaggregation_pass` | 기존 검사 결과 JSON의 주장만 재인용하지 않고 응답 객체·셀 합계를 대조 |
| PAGE-D09 | 새 Git 체크아웃 Gold→서빙 66/66 일치 | 추가 검증 `fresh_gold_to_serving_matches`와 거점별 의미 해시 | 새 로컬 체크아웃 실행. 원천부터 전체 파이프라인·클라우드 실행·독립 팀 재현 아님 |
| PAGE-D10 | 보존 감사 파일 224개 해시 일치 · 목록 중 미보유 537개 | 추가 검증 `archived_file_availability` | Git 보존 범위의 무결성. 모든 로컬 사본의 재배포·보존을 뜻하지 않음 |
| PAGE-D11 | 원본 인벤토리 946개 중 새 체크아웃 보유 265개 · 미보유 681개 | 추가 검증 `data_availability` | 현재 패키지로 Bronze→Gold 전체 재실행 불가. 원래 로컬 원본 소실을 뜻하지 않음 |
| PAGE-D12 | PC 재검증: 서빙 사본·셀 재합산·Gold→서빙 각각 66/66 통과. 감사 파일 761개 및 원본 인벤토리 946개 보유·해시 일치 | 추가 검증 `pc_session_recheck`; 전체 실행 출력은 Git 제외 `private/pc-evidence-verification.json`과 등록 SHA-256 | 기존 파일을 보유한 PC에서 같은 계산 결과를 확인. 새 체크아웃·전체 파이프라인 재현 아님. PAGE-D10·D11의 이전 체크아웃 보유량을 대체하지 않음 |

**재검증 명령:** 저장소 루트에서 `python docs/papers/page-study/verify_evidence.py`. 표의 원 실행 결과를 다시 집계하고, 실제 Gold 서빙 함수를 호출한다. 원래 대장 파이프라인을 실행하는 명령이 아니다. 사용한 체크아웃 커밋, 실행기 해시, Python 및 로드한 저장소 코드 해시는 검증 JSON에 있다. 최상위 기록은 이전 새 체크아웃 결과이며, `pc_session_recheck`는 2026-09-07 PC 실행을 별도로 보존한다. 입력 해시와 거점별 서빙 객체·의미 해시는 두 실행에서 일치했다. 파일 보유량·커밋·실행기 및 로드 코드 해시의 차이를 생성시각 차이로 지우지 않는다.

마스터 키·계산식 등의 통과를 현실 정답으로 승격하지 않는다. 같은 지번에 대한 넓은 검사에서 표시된 613행·428그룹은 [후속 분류](audits/page-analysis-20260906/same-lot-flag-qualification.json)에 따라 **확정 오류로 등재하지 않는다**. 기존 코드의 집계 제외 규칙과 출처 표기를 유지한다. 기존 릴리스 변경을 신규 개업·폐업·수집 오류로 해석하지 않는다.

문헌 근거: Alsudais, *Incorrect Data in the Widely Used Inside Airbnb Dataset*, 저자 공개본 `arXiv:2007.03019v2`, 관련 출판 DOI `10.1016/j.dss.2020.113453`, 출판연도 2021. [원문 등록·읽기 범위](page-study/source-register.json). 원문 내 수치 불일치는 읽기 장부에 남겼으며 원고에 해당 수치·검정 결과를 옮기지 않는다. 우리의 표집·해시·행 순서 검사가 원문에 그대로 있었던 것으로 서술하지 않는다.

## Page 문헌 보완의 서지 식별값

2026-09-19 확인. 아래는 문헌 식별용 연도·권호·쪽·DOI이며 조건 D의 실증 수치가 아니다. 실제 확인 위치와 적용 제한은 [문헌 검토 기록](page-study/literature-review-20260919.md)에 있다.

| 문헌 | 확인한 서지 | 일차 출처 |
|---|---|---|
| Alsudais | 2021 · Decision Support Systems 141 · 113453 · arXiv:2007.03019v2 · DOI 10.1016/j.dss.2020.113453 | https://www.sciencedirect.com/science/article/pii/S0167923620302086 |
| Marsden, J. R. & Pingry, D. E. | 2018 · Decision Support Systems 115 · A1–A7 · DOI 10.1016/j.dss.2018.10.007 | https://www.sciencedirect.com/science/article/pii/S0167923618301647 |
| National Academies of Sciences, Engineering, and Medicine | 2019 · Reproducibility and Replicability in Science · 제3장 정의 절 · DOI 10.17226/25303 | https://www.nationalacademies.org/read/25303/chapter/6 |
| Sandve, G. K., Nekrutenko, A., Taylor, J. & Hovig, E. | 2013 · PLOS Computational Biology 9(10) · e1003285 · DOI 10.1371/journal.pcbi.1003285 | https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003285 |
| Timmerman, Y. & Bronselaer, A. | 2019 · Decision Support Systems 126 · 113138 · DOI 10.1016/j.dss.2019.113138 | https://biblio.ugent.be/publication/8634924 |

<a id="posting-program-update"></a>

## P3·P4 집필 보완 근거

확인일 2026-09-19. 과거 프로브의 모집단과 이번 코드 계약 검사를 분리한다. 원천·Gold·제품 코드는 변경하지 않았다. 세부 검수와 문헌 확인 범위는 [집필 기록](posting-program-writing-20260919.md)에 있다.

| ID | 근거·판정 | 출처와 확인 범위 |
|---|---|---|
| POSTING-E01 | 역사적 공식 소스 조사: 54거점·528 후보행. 건축HUB·서울교통공사·LH·온비드의 면적·임대가능 상태·모집단·키 적격성 대조. 모든 공개 데이터의 불가능성 증명 아님 | `docs/finding-posting-unit-area-sources-2026-08-29.md`; `data/validation/posting_unit_area_sources.py` |
| POSTING-E02 | 층번호 프로브: 66거점·664유닛, 단일층 30개(4.5%), 해당 용량 분포 `{1: 30}`, 면적 차이 n=30·min=0·max=0·median=0.0평 | `reports/posting_unit_area_flrno_probe_2026-09-06.json`의 `served_hubs/units_total/single_floor_units/single_floor_pct/single_floor_capacity_dist/delta_pyeong_on_single` 직접 대조. 이번에 프로브 재실행 아님 |
| POSTING-E03 | 층번호 후속은 층별 유닛 분할에 종속되므로 독립 성공·실패 실험으로 중복 계수하지 않음 | `docs/finding-posting-unit-area-flrno-2026-09-06.md`의 「왜 §0-Q 와 같은 것인가」 |
| POSTING-E04 | 매출 앵커의 기준 모집단 오류는 수정됐지만 설명 가설은 기각. 후속 R-ONE 대조에서 ‘전부 프라임’ 전제도 반증 | `docs/feature-posting.md` §0-N 「매출 앵커」, §0-O 「진짜 소득」. 과거 운영 판정을 사실상 공실·ROI 정답으로 승격하지 않음 |
| POSTING-E05 | 현재 통계 기반 매출·비용 계산과 수기 계수 폴백은 `basis`로 구분. 초기 투자 계수와 유닛 면적 가정은 실제 계약·성과 정답이 아님 | `apps/backend/app/services/districts.py::tier_scenarios`, `posting_revenue.py`, `vacant_inventory.py` 읽기 대조 |
| POSTING-E06 | 공식 소스 적격성 계약 검사 3 passed | 저장소 루트 `python -m pytest data/tests/test_posting_unit_area_sources.py -q`. 외부 API 호출·실측 정확도 평가 아님 |
| PROGRAM-E01 | 현행 대상은 검증하려는 창업자. 입력 ProgramBrief, 출력 online/offline/signals. 점주 원문 온보딩은 삭제 | `docs/feature-program.md` §0-V; `program_brief.py`, `marketing.py` |
| PROGRAM-E02 | 트렌드 컨텍스트·라벨 부재는 `trend_unverified` warning. 상승 라벨 혼재 시 모순 검사 차단을 하지 않는 한계 유지 | `ha_guard.py::_check_trend`; `test_no_context_means_no_trend_check`, `test_context_without_trend_labels_is_also_unverified`, `test_mixed_trend_does_not_block` |
| PROGRAM-E03 | 미검증 경험 주장 차단과 앞으로 측정할 지표를 구별. 생성 조각은 줄바꿈으로 연결 | `ha_guard.py::check_program`, `_check_unproven_evidence`; `docs/feature-program.md` §0-V의 문장 경계 결함 |
| PROGRAM-E04 | violation이면 생성물을 버리고 규칙 스텁으로 폴백, warning이면 생성물을 유지하고 findings 표시. 빈 findings는 전 항목 검증 완료 아님 | `marketing.py::generate_program`; `test_violation_falls_back_to_stub`, `test_warning_keeps_llm_output`, `test_stub_without_llm_has_empty_findings` |
| PROGRAM-E05 | HA 가드·출력 계약 검사 합계 54 passed | `apps/backend`에서 `python -m pytest tests/test_ha_guard.py tests/test_program_output_split.py -q`. 고정 예시·목킹 검사이며 LLM 실호출·사실성 위반율·광고 효과 평가 아님 |
| PROGRAM-E06 | 지표명·측정 방법·목표선·기각 조건의 구조와 내용 경고를 구별 | `test_signal_requires_a_decision_rule`, `test_missing_signals_is_warning`, `test_signal_without_number_is_warning`, `test_signal_without_decision_rule_is_warning` |

### P4 문헌 서지 식별값

- Min 등, 2023, *FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation*. EMNLP, 12076–12100. DOI `10.18653/v1/2023.emnlp-main.741`. ACL 서지·PDF 초록·서론과 평가 정의를 확인. 원문 성능 수치를 본 원고로 옮기지 않는다.
- Gao, Yen, Yu, Chen, 2023, *Enabling Large Language Models to Generate Text with Citations*. EMNLP, 6465–6488. DOI `10.18653/v1/2023.emnlp-main.398`. ACL 서지·PDF 초록·평가 차원 설명을 확인. 전체 부록 정독·벤치마크 실행 완료를 뜻하지 않는다.

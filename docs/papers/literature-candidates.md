# SpaceOS 디지털 4P 선행연구 후보 비교표

> 범위: 후보 비교까지만 수행한다. 이 문서는 뼈대 논문 선정이나 논문 본문이 아니다.
> 조사일: 2026-09-06. SpaceOS 대응은 `data-specification.md`와 직전 데이터 검증 결과인
> 커밋 `fa1b903`의 산출물을 읽어 작성했다. 수치 성능 주장은 옮기지 않았다.

## 확인 원칙과 상태 표기

- 서지사항과 DOI는 각 출판사 논문 페이지 및 Crossref DOI 레코드를 대조했다. DOI 링크는
  출판사 랜딩 페이지로 연결한다.
- **원문 확인**은 출판사 원문 또는 저자 공개 원고에서 방법·데이터·평가 절을 읽었다는 뜻이다.
  **초록만 확인**인 후보는 초록에서 확인되는 연구 범위만 적고 방법·분할은 `원문 확인 필요`로 남겼다.
- 접근 제한은 우회하지 않았다. 현재 환경의 ACM·Taylor & Francis·Emerald 원문 제한은 그대로 기록했다.
- Q1은 [Clarivate JCR 안내](https://clarivate.com/academia-government/scientific-and-academic-research/research-funding-analytics/journal-citation-reports/)의
  **JIF category quartile**을 우선 기준으로 삼는다. 그러나 이 환경에서는 구독 JCR의 저널별 연도·분야
  레코드를 확인하지 못했으므로 전 후보를 **Q1 미확인**으로 둔다. SJR도 추정하지 않고 별도 열에
  미확인으로 남긴다. 학술대회 논문은 보조 문헌으로 분리한다.
- `평가 분할 없음`은 논문이 예측 연구가 아닌 실험·방법론 논문인 경우다. `미확인`과 구별한다.

## Platform — 상권·입지 기반 추천과 공간 학습

| 후보 | 연구 질문·핵심 기여 | 데이터: 출처 / 관측 단위 / 기간 / 타깃 | 방법 / 기준선 / 평가 분할 | SpaceOS 대응과 재현 가능 부분 | 추가 데이터·실험 및 불일치 | 원문 상태 | JCR Q1 확인 / SJR |
|---|---|---|---|---|---|---|---|
| **CityTransfer** — Bin Guo, Jing Li, Vincent W. Zheng, Zhu Wang, Zhiwen Yu (2018), *Proceedings of the ACM on Interactive, Mobile, Wearable and Ubiquitous Technologies*. [DOI·출판사](https://doi.org/10.1145/3161411) | 한 도시에서 학습한 체인점 입지 지식을 데이터가 부족한 다른 도시로 옮길 수 있는가. 다원 도시 피처와 전이학습을 결합한 매장 입지 추천 문제를 제시한다. | 중국 도시의 POI·인구이동 등 도시 데이터와 체인 매장 위치; 후보 지역 단위, 기존 매장 존재/선호가 타깃. 정확한 도시·기간·표본은 원문 확인 필요. | 전이학습 기반 순위화로 확인되나 네트워크 구성, 기준선, 음성 표본 생성 및 train/test 분할은 **미확인**. | 거점·점포 그래프, 업종 라벨, 상권 수요 피처를 source/target 거점으로 나누는 cold-start 실험 설계는 이식 가능. | SpaceOS는 도시 간 전이보다 서울 내 거점 분류이며 실제 출점 성공 라벨이 없다. 도시/거점 holdout과 거점 사전분포 기준선을 새로 비교해야 한다. | **초록만 확인**(ACM 원문 403). | **Q1 미확인** — JCR 연도·분야 레코드 미열람 / SJR 미확인 |
| **Knowledge Transfer with Weighted Adversarial Network for Cold-Start Store Site Recommendation** — Yan Liu, Bin Guo, Daqing Zhang, Djamal Zeghlache, Jingmin Chen, Ke Hu, Sizhe Zhang, Dan Zhou, Zhiwen Yu (2021), *ACM Transactions on Knowledge Discovery from Data*. [DOI·출판사](https://doi.org/10.1145/3442203) | 신규 도시의 라벨 부족과 도시 간 분포 차이를 함께 다루는 cold-start 입지 추천. 가중 adversarial transfer로 관련성이 다른 source 표본을 조절한다. | 다도시 다원 도시 데이터와 체인점 입지; 공간 후보 단위 및 입지 적합성 타깃. 기간·세부 원천·표본은 원문 확인 필요. | weighted adversarial network로 확인되나 기준선 목록, 하이퍼파라미터와 공간 분할은 **미확인**. | SpaceOS의 거점별 피처 분포 차이를 domain shift로 정의하고 leave-one-hub-out 평가를 하는 부분은 재현 가능. | 현재 라벨은 업종 분류이지 신규 매장의 생존·매출·적합성 라벨이 아니다. 추천 타깃을 바꾸지 말고 분류 태스크로 재정의해야 한다. | **초록만 확인**(ACM 원문 403). | **Q1 미확인** / SJR 미확인 |

### Platform 보조 문헌 — 학술대회

| 후보 | 역할 | 확인 상태 |
|---|---|---|
| **O²-SiteRec: Store Site Recommendation under the O2O Model via Multi-graph Attention Networks** — Hua Yan, Shuai Wang, Yu Yang, Baoshen Guo, Tian He, Desheng Zhang (2022), IEEE ICDE. [DOI·IEEE](https://doi.org/10.1109/ICDE53745.2022.00044) | 온라인·오프라인 관계를 여러 그래프로 표현하는 직접적인 multi-graph 비교 대상. SpaceOS 점포·공간 엣지 ablation 설계에 유용하다. | **초록만 확인**. 데이터, 기준선, 분할은 원문 확인 필요. 학술대회이므로 Q1 표기 대상 아님. |

- **우선 검토 후보:** cold-start와 domain shift가 SpaceOS의 신규 거점 평가에 가장 직접적인 두 번째 후보.
- **불일치:** 두 연구는 실제 체인 출점 위치를 타깃으로 하지만 SpaceOS는 기존 점포의 업종을 가린 분류다.
  random split 성능을 입점 성공으로 바꾸어 해석할 수 없다.
- **원문 확보 필요:** 세 후보 모두. 특히 음성 후보 구성과 도시/시간 누수 방지 분할을 확인하기 전에는
  방법론을 뼈대로 확정할 수 없다.

## Page — 공공·공간자료 결합과 공실 추정

| 후보 | 연구 질문·핵심 기여 | 데이터: 출처 / 관측 단위 / 기간 / 타깃 | 방법 / 기준선 / 평가 분할 | SpaceOS 대응과 재현 가능 부분 | 추가 데이터·실험 및 불일치 | 원문 상태 | JCR Q1 확인 / SJR |
|---|---|---|---|---|---|---|---|
| **Modeling the Census Tract Level Housing Vacancy Rate with the Jilin1-03 Satellite and Other Geospatial Data** — Mingzhu Du, Le Wang, Shengyuan Zou, Chen Shi (2018), *Remote Sensing*. [DOI·출판사](https://doi.org/10.3390/rs10121920) | 단일 원천 대신 위성영상과 보조 공간자료를 결합해 소지역 주택 공실률을 추정할 수 있는가. 공간 단위 공실률 모델과 변수 기여 비교를 제시한다. | 미국 Buffalo의 census tract; census 공실률이 타깃이고 Jilin1-03 야간영상 및 기타 지리 피처를 결합한다. 횡단면 관측이며 정확한 촬영·census 기준일은 원문 표에서 재확인 필요. | 회귀 기반 다원자료 모델과 피처 조합 비교. 기준선·검증 분할의 정확한 구성은 원문 재확인 필요. | R-ONE 상권 공실 앵커, 건축물대장·상가정보, 생활인구의 다원 결합 및 원천별 ablation은 재현 가능. | 주택 census 정답과 상업 유닛 파생 공실은 관측 정의가 다르다. SpaceOS에는 건물/유닛 현장 정답과 독립 test 지역이 필요하다. | **원문 확인**(출판사 공개 원문); 세부 분할은 재확인 표기. | **Q1 미확인** / SJR 미확인 |
| **Individual Vacant House Detection in Very-High-Resolution Remote Sensing Images** — Shengyuan Zou, Le Wang (2019), *Annals of the American Association of Geographers*. [DOI·출판사](https://doi.org/10.1080/24694452.2019.1665492) | 집계 공실률이 아니라 개별 빈집을 초고해상도 영상에서 식별할 수 있는가. 객체 단위 탐지로 공간 해상도를 높인다. | 초고해상도 원격탐사 영상과 개별 주택 공실 라벨; 건물 객체가 관측 단위. 지역·기간·타깃 라벨 취득 절차는 원문 확인 필요. | 영상 기반 개별 객체 탐지로 확인되나 모델, 기준선, 공간 holdout은 **미확인**. | 건물 폴리곤 단위 결과 지도, 객체 귀속 오차와 coverage 평가 틀은 Page 품질 평가에 참고 가능. | SpaceOS는 영상 원천이 없고 점포·대장 결합으로 후보 공실을 산출한다. 주거 빈집 탐지법을 상업 유닛 정답 없이 재현할 수 없다. | **초록만 확인**(Taylor & Francis 접근 제한). | **Q1 미확인** / SJR 미확인 |

- **우선 검토 후보:** 첫 번째 후보. 공실률의 공간 단위, 다원자료 결합, 원천별 기여 비교가 Page에 가장 가깝다.
- **불일치:** 두 후보 모두 주택 공실이며 SpaceOS의 상업 유닛 `vacancy_rate`는 공공 원천을 결합한 파생값이다.
  census·현장조사 정답과 동급으로 취급할 수 없다.
- **원문 확보 필요:** 두 번째 후보의 라벨 수집, 객체 매칭, 공간 분할. 첫 번째 후보도 재현 전 정확한 기준일과
  train/test 또는 교차검증 단위를 다시 확인해야 한다.

## Posting — 비용·임대료·수익성 시나리오와 불확실성

| 후보 | 연구 질문·핵심 기여 | 데이터: 출처 / 관측 단위 / 기간 / 타깃 | 방법 / 기준선 / 평가 분할 | SpaceOS 대응과 재현 가능 부분 | 추가 데이터·실험 및 불일치 | 원문 상태 | JCR Q1 확인 / SJR |
|---|---|---|---|---|---|---|---|
| **Monte Carlo simulations for real estate valuation** — Martin Hoesli, Elion Jani, André Bender (2006), *Journal of Property Investment & Finance*. [DOI·출판사](https://doi.org/10.1108/14635780610655076) | 단일 점 추정보다 입력 불확실성을 분포로 두는 Monte Carlo가 부동산 가치평가의 위험을 더 투명하게 보이는가. | 부동산 valuation case의 현금흐름 입력과 가치 분포가 분석 대상. 자산·기간·실증 표본 여부는 원문 확인 필요. | Monte Carlo 기반 valuation으로 확인되나 입력분포 추정, deterministic 기준선, 검증 방식은 **미확인**. | `rent`, `prem`, `foot`, 매출 전제와 `roi_months`를 범위/분포로 바꾸고 tornado·확률분포를 보고하는 절차는 적용 가능. | SpaceOS에는 실현 매출·계약 임대료 분포가 없다. 공개 집계값에 임의 분포를 씌우면 안 되며 사용자 입력 범위나 외부 실증 자료가 필요하다. | **초록만 확인**(Emerald 접근 제한). | **Q1 미확인** / SJR 미확인 |
| **Sensitivity Analysis for Property Appraisal** — Smyly Bannerman (1993), *Journal of Property Valuation and Investment*. [DOI·출판사](https://doi.org/10.1108/EUM0000000003306) | 가치평가 결론이 핵심 가정 변화에 얼마나 민감한지 명시적으로 드러내는 방법을 다룬다. | 부동산 appraisal 입력과 산출 가치; 사례·기간·관측 단위는 원문 확인 필요. | sensitivity analysis로 확인되나 요인 설계, 기준 시나리오, 검증은 **미확인**. 예측 논문인지도 원문 확인 필요. | 기존 3-Tier와 입력별 민감도를 분리하고, 출처별 불확실성을 표시하는 비교 틀은 재현 가능. | SpaceOS의 층 계수와 권리금 미입력 전제는 관측값이 아니다. 실현 ROI 정확도를 평가하려면 계약·매출 패널이 필요하다. | **초록만 확인**(Emerald 접근 제한). | **Q1 미확인** / SJR 미확인 |

- **우선 검토 후보:** 첫 번째 후보. 점 추정 ROI 대신 결과 분포를 제시하는 설계가 Posting의 음성 결과와 잘 맞는다.
- **불일치:** 두 후보의 valuation 입력이 실제 거래/현금흐름인지 확인되지 않았고, SpaceOS에는 개별 점포의
  실현 수익과 계약비용이 없다. 따라서 예측 정확도나 인과효과 연구로 바로 옮길 수 없다.
- **원문 확보 필요:** 두 후보 모두. 입력분포의 근거, 변수 상관, 기준 시나리오 및 out-of-sample 평가 유무를 확인해야 한다.

## Program — 지역 수요 조건 생성과 사실성·의사결정 평가

| 후보 | 연구 질문·핵심 기여 | 데이터: 출처 / 관측 단위 / 기간 / 타깃 | 방법 / 기준선 / 평가 분할 | SpaceOS 대응과 재현 가능 부분 | 추가 데이터·실험 및 불일치 | 원문 상태 | JCR Q1 확인 / SJR |
|---|---|---|---|---|---|---|---|
| **The potential of generative AI for personalized persuasion at scale** — S. C. Matz, J. D. Teeny, S. S. Vaid, H. Peters, G. M. Harari, M. Cerf (2024), *Scientific Reports*. [DOI·출판사](https://doi.org/10.1038/s41598-024-53755-0) · [공개 원문](https://pmc.ncbi.nlm.nih.gov/articles/PMC10897294/) | 생성형 AI가 개인 특성에 맞춘 설득 메시지를 대규모로 만들고 비개인화 메시지보다 효과적인가. 여러 사전등록 실험으로 생성과 평가를 분리한다. | 온라인 실험 참가자·메시지 평가/행동의도 단위; 개인 성향을 조건으로 생성된 메시지가 처치. 연구별 모집·기간과 전체 outcome은 원문 표 참조. | 무작위 조건 배정의 실험들, 개인화/비개인화 비교. 예측 train/test 분할이 아니라 실험군 비교다. | SpaceOS 수요 컨텍스트 포함/제외, 실제 근거 제공/미제공, 사람 작성/LLM 생성 팔을 무작위화하는 평가 설계는 재현 가능. | 개인 성향과 지역 집계 수요는 다른 조건이다. 클릭·방문·구매 로그가 없으므로 현재는 사실성, 관련성, 의사결정 유용성까지만 평가 가능하다. | **원문 확인**(출판사·PMC 공개 원문). | **Q1 미확인** / SJR 미확인 |
| **Human favoritism, not AI aversion: People’s perceptions (and bias) toward generative AI, human experts, and human–GAI collaboration in persuasive content generation** — Yunhao Zhang, Renée Gosline (2023), *Judgment and Decision Making*. [DOI·출판사](https://doi.org/10.1017/jdm.2023.37) | 동일한 설득 콘텐츠도 제작 주체가 인간, AI, 협업이라고 알려질 때 품질 판단이 달라지는가. 산출물 품질과 source disclosure 효과를 분리한다. | 온라인 참가자의 설득 콘텐츠 평가와 제작 주체 조건; 판단/선호가 outcome. 정확한 표본·모집 기간은 원문 표 참조. | 인간·GAI·협업 콘텐츠 및 disclosure 조건을 비교하는 무작위 실험. 예측 분할 없음. | Program 결과를 blind 평가한 뒤 제작 주체를 공개하는 2단계 평가와, 사람/LLM/협업 기준선 비교를 그대로 적용 가능. | 이 연구는 상권 사실 오류를 직접 검증하지 않는다. SpaceOS에는 입력 근거와 출력 문장의 claim-level entailment, 전문가 오류 판정 기준이 추가로 필요하다. | **원문 확인**(Cambridge 공개 원문). | **Q1 미확인** / SJR 미확인 |
| **Consumer Responses to AI-Generated Charitable Giving Ads** — Luis Arango, Stephen Pragasam Singaraju, Outi Niininen (2023), *Journal of Advertising*. [DOI·출판사](https://doi.org/10.1080/00913367.2023.2183285) | AI 생성 광고라는 정보가 자선 광고에 대한 소비자 반응을 어떻게 바꾸는가. 광고 생성 주체와 disclosure를 마케팅 맥락에서 직접 다룬다. | 소비자 실험의 광고 노출·평가 단위; 자선 광고 반응이 타깃. 표본·기간·측정척도는 원문 확인 필요. | 실험 연구로 확인되나 조건, 기준선, 무작위화와 분석계획은 **미확인**. | Program의 AI disclosure 및 사람 작성 기준선 설계에 직접 대응한다. | 자선광고와 지역 상점 마케팅은 목적·위험이 다르며, 지역 수요 근거성이나 사실 오류는 별도 평가해야 한다. | **초록만 확인**(Taylor & Francis 접근 제한). | **Q1 미확인** / SJR 미확인 |

- **우선 검토 후보:** 첫 번째 후보는 context-conditioned 생성 실험, 두 번째 후보는 blind 품질평가와
  disclosure 편향 분리에 각각 적합하다. 뼈대 후보를 하나로 고르기보다 사실성 평가 논문을 추가로 찾아야 한다.
- **불일치:** 확보한 연구는 설득력·인식 평가 중심이며 SpaceOS의 핵심 가드레일인 지역 수요 사실성,
  출처 충실성, 잘못된 의사결정 방지를 직접 측정하지 않는다. 광고 효과 로그도 없다.
- **원문 확보 필요:** 세 번째 후보. 앞의 두 후보도 설문 문항·자극물·사전등록 자료를 내려받아
  한국어 지역 마케팅에 맞는 평가척도로 번안 가능한지 확인해야 한다.

## 뼈대 논문 선정 전에 해결할 문제

1. **Platform:** 출점 적합성/성공과 기존 점포 업종 분류 중 어느 타깃을 연구할지 먼저 고정하고,
   거점 holdout 및 시간 holdout을 만들 수 있는지 확인한다.
2. **Page:** 상업 건물·유닛의 독립 공실 정답을 확보하지 못하면 데이터 결합·품질 논문으로 범위를
   제한한다. 주택 vacancy 연구를 성능 기준으로 직접 비교하지 않는다.
3. **Posting:** 계약 임대료·권리금·실현 매출 패널 또는 사용자가 제공하는 범위 입력 없이는 Monte Carlo
   분포를 설정하지 않는다. 현재 3-Tier의 민감도/가정 투명성 연구로 한정할지 결정한다.
4. **Program:** 설득력과 사실성을 분리하고, claim-level 근거 일치·전문가 판단·의사결정 유용성의
   사전등록 평가 프로토콜을 새로 설계한다.
5. **공통:** JCR 구독 환경에서 후보별 **평가연도·JIF category·quartile**을 캡처 가능한 공식 레코드로
   재확인한다. 원문 미확보 후보는 방법·기준선·평가 분할을 확정하지 않는다.

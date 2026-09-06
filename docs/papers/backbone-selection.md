# SpaceOS 디지털 4P 뼈대 논문 선정 검토

검토일: 2026-09-06. 입력: `literature-candidates.md`, `data-specification.md`, `evidence-index.md` 및 아래 외부 출처. 변경 범위는 이 문서다. 실험 실행이나 논문 본문 작성 결과가 아니다.

## 결론과 선정 상태

각 P의 우선 검토 논문을 아래와 같이 좁힌다. **네 편 모두가 ‘AI/MIS 분야 Q1 + 공공데이터 유사성 + 원문 검증’을 통과했다고 판정하지 않는다.** 특히 Platform의 분야별 Q1과 Posting의 데이터 적합성이 남아 있다. 초록으로 확인한 방법을 원문 재현 가능성으로 확대 해석하지 않는다.

| P | 우선 논문 | SpaceOS 적용 연구 | 판정 |
|---|---|---|---|
| Platform | Liu et al. (2021), Knowledge Transfer with Weighted Adversarial Network for Cold-Start Store Site Recommendation, ACM TKDD. DOI: [10.1145/3442203](https://doi.org/10.1145/3442203) | 거점 간 전이와 미관측 거점의 업종 추천 | 조건부: 관련 연구 유지. AI/정보시스템 분야 Q1 및 원문 상세 미확인 |
| Page | Alsudais (2021), Incorrect data in the widely used Inside Airbnb dataset, Decision Support Systems. DOI: [10.1016/j.dss.2020.113453](https://doi.org/10.1016/j.dss.2020.113453) | 공개 데이터의 객체 귀속·수집 오류·버전 재현성 검증 | 데이터 품질 연구의 우선 뼈대. 공실 예측 논문으로 선정한 것은 아님 |
| Posting | Önüt, Efendigil & Soner Kara (2010), A combined fuzzy MCDM approach for selecting shopping center site: An example from Istanbul, Turkey, Expert Systems with Applications. DOI: [10.1016/j.eswa.2009.06.080](https://doi.org/10.1016/j.eswa.2009.06.080) | 가격·비용 시나리오의 다기준 평가 및 민감도 | 조건부 방법론 후보. 원 논문의 입지 선택과 가격 의사결정은 다름 |
| Program | Heo, Son & Park (2025), HaluCheck: Explainable and verifiable automation for detecting hallucinations in LLM responses, Expert Systems with Applications. DOI: [10.1016/j.eswa.2025.126712](https://doi.org/10.1016/j.eswa.2025.126712) | 홍보문 주장과 제공한 공공데이터 근거의 일치 검증 | 사실성 평가의 우선 뼈대. 광고 전환 효과의 근거로 사용 불가 |

## Q1 확인 수준

Q1은 논문 자체의 등급이 아니라 특정 연도·분야·평가지표에 따른 저널 분류다. 현재 저널 등급을 과거 게재 당시 등급으로 바꾸어 쓰지 않는다.

- **Decision Support Systems:** [Comillas 대학 IIT 저널 기록](https://www.iit.comillas.edu/publicacion/info_revista/en/114/Decision_Support_Systems)의 JCR-JIF 열에서 2024 Q1 및 2021 Q1 확인. 이 표에는 세부 분야가 없으며 Clarivate 원본 직접 열람은 아니다.
- **Expert Systems with Applications:** [Comillas 대학 IIT 저널 기록](https://www.iit.comillas.edu/publicacion/info_revista/es/60/Expert_Systems_with_Applications)의 JCR-JIF 열에서 2024 Q1 확인. 이 근거로 Posting 논문의 2010년 등급을 주장하지 않는다. 세부 분야별 원본 순위는 미확인이다.
- **ACM TKDD:** [UTeM 도서관 JCR2023 목록](https://library.utem.edu.my/images/PDF/List_Journal_Citation_Report_Clarivate_-_JCR2023.pdf)의 검색 색인에서 COMPUTER SCIENCE, SOFTWARE ENGINEERING Q1을 확인했다. PDF 원문 대조와 AI/정보시스템 분야 Q1 확인을 완료하지 못했다. 따라서 엄격한 분야 요건 충족으로 처리하지 않는다.

<!-- TODO(문헌): 세 저널의 동일 기준연도 JCR 분야별 원본 레코드를 확보하고, 특히 TKDD의 AI/MIS 분야 Q1 충족 여부를 확정한다. -->

## Platform: 전이학습과 공간 일반화

서지는 [일본 국립국회도서관 기록](https://ndlsearch.ndl.go.jp/books/R100000136-I1360025437451349632)과 기존 후보표를 대조했다. 확인 수준은 서지·초록이며 최종 출판본의 데이터 구성·분할·코드 재현 확인은 미완료다.

선정 이유는 신규 지역에서 데이터가 부족한 입지 추천 문제와 거점 간 정보 이전이라는 공통점이다. 원 논문과 SpaceOS가 동일 공공 API를 사용한다는 증거는 없다.

SpaceOS에서는 상권·분기 집계, 점포 업종과 공간 관계를 입력 후보로 삼는다. 거점을 통째로 제외하는 공간 분할과 가능한 경우 시간 분할을 사용하고, 업종 빈도 기준선·표 기반 모델·현재 그래프 방법을 비교하도록 설계한다. 이는 새 실험 제안이며 수행 결과가 아니다.

기존 업종 라벨 복원은 실제 입점 성공 예측이 아니다. 학습·평가 간 인접 정보 유출을 점검하고, 기존 성능 천장과 기각 결과를 유지한다. 매출·폐업 등 독립 결과 라벨이 없으면 사업 성공 효과를 주장하지 않는다.

## Page: 공공데이터 기반 공실 정보의 신뢰성

[저자 공개본 안내 및 초록](https://arxiv.org/abs/2007.03019)은 공개 Inside Airbnb 자료의 수집 과정 오류와 릴리스 간 재현성 문제를 명시한다. 저자 공개본 링크의 존재를 확인했으며 이번 검토에서 전체 본문 정독·출판본 대조까지 완료하지 않았다.

원 자료는 민간 플랫폼에서 수집한 공개 자료이며 정부 공공데이터와 동일하지 않다. 이 논문을 택하는 이유는 데이터 출처가 아니라 객체 귀속과 수집·가공 과정에 대한 검증 구조다.

SpaceOS 확장은 건축물대장·점포·인허가·임대 통계를 결합할 때 공간 키, 시점, 중복, 결측 및 조인 실패가 결과에 미치는 영향을 감사하는 연구다. 원본 스냅샷·수집 시점·변환 버전·검증 규칙을 기록하고 독립 검토 표본으로 오류 유형을 확인한다. R-ONE 집계와의 일치만으로 개별 공실의 정확성을 입증할 수 없다.

제안 제목: **공공데이터 결합 기반 상업용 공실 정보의 데이터 품질과 재현성 평가: SpaceOS 사례**. 현장 정답 없이 공실 예측 정확도를 주장하는 연구보다 현재 데이터와 연결이 분명하다. 짧은 연구노트의 사례를 바꾸는 것만으로 석사 논문이 되지는 않으며, 독립 감사와 오류 전파 분석이 필요하다.

## Posting: 비용 시나리오의 의사결정 지원

[저자 소속 대학 기록·초록](https://avesis.yildiz.edu.tr/yayin/3ba81251-efe4-4060-8787-9f268014b7c2/a-combined-fuzzy-mcdm-approach-for-selecting-shopping-center-site-an-example-from-istanbul-turkey)에서 fuzzy AHP와 fuzzy TOPSIS를 이용한 쇼핑센터 입지 선택을 확인했다. 전체 원문과 입력표는 미검증이다.

SpaceOS에 이전할 수 있는 것은 다기준 평가 절차다. 입지 선택을 가격대·비용 시나리오 선택으로 옮기는 것은 연구자의 확장이며 직접 재현이 아니다. 따라서 **데이터 유사성을 요구하는 최종 뼈대 선정 조건은 아직 미충족**이다.

사용 후보 입력은 출처를 가진 임대료 집계, 면적, 계약 입력 및 명시적 비용 가정이다. 상권 추정 매출을 개별 매장 실매출로 사용하지 않는다. 선호 가중치는 사용자·전문가 조사 없이 지어내지 않으며, 확률분포의 근거가 없으면 확률적 ROI를 계산하지 않는다. 근거 있는 구간이 확보된 경우에만 결정론적 민감도를 분석한다.

제안 제목: **공공 임대 통계와 계약 입력을 결합한 입점 비용 시나리오의 민감도 분석**. 현재 제품의 회수기간 추천 정의·출처 계약은 변경하지 않는다. 원문 확인 후 실제 계약·비용 자료 확보 가능성과 함께 채택 여부를 결정한다.

## Program: 홍보문 사실성 검증

출판 논문과 [저자 SSRN 공개본 레코드](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4944961)를 구분한다. 공개본 제목은 *Halucheck: Integrating Hallucination Detection Techniques in Llm-Based Conversational Systems*이며 출판본과 버전 차이를 대조해야 한다. 출판본 전체 본문 검증은 미완료다.

SpaceOS에서는 생성문을 검증 가능한 주장으로 나누고, 각 주장에 사용한 데이터 근거를 연결하는 평가를 설계한다. 동일 입력에 대한 일반 생성·근거 제공 생성·검증 후 수정 방식을 비교한다. 사람 검토자가 근거에 의한 지지·모순·판단 불가를 구분하고, 자동 평가와 사람 판정의 일치 및 누락을 확인한다. 이 비교 설계는 SpaceOS 확장안이며 원 논문 실험을 그대로 옮겼다는 뜻이 아니다.

제안 제목: **공공 상권 데이터에 근거한 생성형 AI 홍보문의 사실성 검증**. 생성문은 합성 평가 자료로 표기한다. 상권 집계를 점포 실적이나 개인 특성으로 바꾸지 않는다. 클릭·전환 관측이 없으면 마케팅 성과 향상을 주장하지 않는다. 기존 감성 분석 기각을 되돌리지 않는다.

## 기존 후보 처리

- CityTransfer와 ICDE O²-SiteRec은 관련 연구로 보존한다. 학회 실적을 저널 Q1로 대체하지 않는다.
- Remote Sensing 및 Annals AAG의 공실 논문은 공간 연구 참고문헌이다. 주거·영상 기반 정답과 현재 상업용 행정자료의 차이 때문에 Page 우선 뼈대에서 제외한다.
- 부동산 Monte Carlo·감도분석 후보는 참고문헌으로 남긴다. Q1 미검증과 입력분포 부재를 해결한 것으로 처리하지 않는다.
- 설득·광고 반응 후보는 Program의 후속 사용자 실험 참고문헌이다. 현재 데이터로 실제 광고 효과를 검증할 수 없어 사실성 연구를 먼저 진행한다.

## 검수와 다음 작업

이번 산출물의 검수 항목은 `selection_has_four_p`, `selection_has_doi_and_sources`, `selection_discloses_verification_gaps`, `selection_preserves_data_limitations`이다. 논문 본문에 새 실측 수치를 추가하지 않았고 seed를 실측으로 바꾸지 않았다.

다음 실행 우선순위는 **Page의 데이터 품질 감사 설계**다. 실제 공개본을 읽어 원 논문의 검증 절차를 대조한 뒤, 보유 스냅샷과 독립 검토 가능한 표본을 확인하고 연구 질문·변수·평가 절차를 작성한다. Program은 사람 판정용 평가셋 설계가 뒤따른다. Platform과 Posting은 위 미충족 조건을 먼저 해소해야 한다.

이 문서는 검토 결과를 마무리한 것이며, 엄격한 요건의 최종 뼈대 네 편 선정 완료나 실험 완료를 선언하는 문서가 아니다.

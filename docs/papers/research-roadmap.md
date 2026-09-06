# SpaceOS 논문 작업 전체 단계

이 문서는 작업 단계와 산출물의 상태를 설명한다. 새 논문 실험 결과나 제품 진행률을 선언하지 않는다. 각 P는 같은 절차를 따르되 데이터·타깃·모집단을 별도로 정의한다. 현재 실증 준비의 우선 대상은 Page다.

| 단계 | 작업·완료 기준 | 현재 상태 | 산출물 |
|---|---|---|---|
| 환경 준비 | 저장소 접근, 인터넷, 필요한 분석 도구 확인 | 사용자 제공 클라우드 점검 기록 있음. 현재 로컬 세션에서 클라우드 재확인하지 않음 | [데이터 명세의 인계 기록](data-specification.md) |
| 데이터 명세 | 원천·키·단위·시점·가공·출처·한계 정리 | 초기 명세 작성 완료. 전수 데이터 검증과 다름 | [data-specification.md](data-specification.md) |
| 문헌 후보·뼈대 검증 | 서지, 원문, 분야·연도별 Q1, 데이터·방법 적합성 확인 | 후보 검토 작성. 엄격한 요건의 모든 P 최종 확정은 미완료 | [literature-candidates.md](literature-candidates.md), [backbone-selection.md](backbone-selection.md) |
| 연구 설계 | 연구 질문→변수→분모→평가 절차→한계 연결 | Page 작성 완료. 다른 P의 설계는 후속 대상 | [page-data-quality-protocol.md](page-data-quality-protocol.md) |
| 원천 인벤토리·manifest | 현재 보존 자료, 선택·병합 경로, 파일·코드 해시, 시점·Git 상태 확인 | 인벤토리 작성·해시 검증 완료. G0는 과거 계보·불변 사본 미확인으로 부분 충족 | [실행 보고서](audits/page-inventory-20260906/README.md), [생성기](build_page_audit_manifest.py) |
| 전수 구조 감사 | 식별·단위·공간·시점·집계 규칙별 실패와 평가 불가 분리 | 미실행 | 설계의 B 및 M1/M3 |
| 독립 표본 감사 | 확률표집, 독립 근거, 검토자 판정과 미판정 기록 | 미실행. 자동 검사 통과만으로 대체 불가 | 설계의 C 및 M2 |
| 영향·재현성 분석 | 같은 단위·시점의 영향 비교, 고정 입력 재실행과 릴리스 차이 분리 | 미실행 | 설계의 D/E 및 M4~M7 |
| 근거 등재 | 수치마다 코호트·분자·분모·원천·재현 경로 등재 | 기존 근거 있음. 새 감사 결과는 미등재 | [evidence-index.md](evidence-index.md) |
| 논문 작성·검토 | 검증한 문헌과 등재된 근거로 절별 작성, 한계·기각 유지 | 기존 본문은 뼈대 상태. Page 감사 본문 작성 전 | [paper-page.md](paper-page.md) 및 다른 P 원고 |
| 제출물 준비 | 인용·연구윤리·기여·재현 자료 검토 후 문서 형식 완성 | 미진행 | 제출 용도별 원고·포트폴리오 |

문헌 검증은 실증 준비와 병행할 수 있다. 하지만 미확인 문헌을 확정 인용하거나 Q1 게재 논문을 참고했다는 이유로 작성한 원고 자체를 Q1 수준이라고 판정하지 않는다. Page 저자 공개본의 확인 범위는 감사 설계 문서에 기록돼 있으며 최종 출판본과 대조는 남아 있다.

## 이번 단계의 작업 계약

- 대상: 이 문서, `build_page_audit_manifest.py`, `audits/page-inventory-20260906/manifest.json`, `inventory.csv`, `manifest.sha256`, `README.md`.
- 입력: 동결한 `ACTIVE_HUBS` 범위의 Page 핵심 원천·중간 산출물·Gold, R-ONE 공실 보조자료, 관련 코드·환경 버전. 관측 시점 미확인은 그대로 남긴다.
- 검수: `manifest_digest_matches`, `manifest_file_fingerprints_match`, `manifest_selector_matches_loader`, `manifest_inventory_matches`, `manifest_cohort_matches_registry`, `manifest_unknowns_preserved`.
- 금지: 원천·제품 코드 수정, 원천 API 재수집, 미측정값 보완, Gold 재빌드, 자동 커밋·푸시. 파일 해시 포착을 과거 입력의 증명이나 불변 사본 생성으로 표현하지 않는다.

## 이번 단계 이후

manifest의 선택 경로를 사용해 읽기 전용 전수 구조 감사를 시작한다. 실행 전 원천 해시를 재대조한다. 변경된 자료가 있으면 이전 실행에 섞지 않고 새로운 run-id로 재포착한다. 독립 점유 자료나 과거 입력 이력이 없어도 구조 감사는 수행할 수 있지만, 그 결과를 현실 공실 정확도나 과거 실행의 완전 재현으로 확대하지 않는다.

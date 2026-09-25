# PlaceOS 직원 채용 지원·연구 준비 자료

2026-09-25 개정. 기존 파일 위치 `career_docs/placeos/`를 유지했다. 지원 대상은 고려대학교 기술경영전문대학원 행정팀, 연세대학교 앵커사업단, 연세대학교 산학협력단 행정/앵커사업의 세 공고다. 석사 연구계획은 채용과 별개다.

## 먼저 확인할 사항

연세대 산학협력단 접수는 **9월 27일**, 앵커사업단은 **9월 30일**까지이며 조기 마감 가능하다. 두 공고의 마감 시각은 미확인이다. 고려대 **9월 30일 24시**는 사용자 제공 정보이며 이미지에서는 확인하지 못했다.

[연세대 채용시스템 공지](https://rhr.yonsei.ac.kr/main/noticeDetail.do?seqnr=29)가 전형 과정의 AI 도구 사용을 금지한다. 연세대 자료는 제출용 자기소개서 대신 공고 분석과 본인 작성 빈칸표로 구성했다. 이메일 접수인 앵커사업단에 대한 적용 여부는 별도 확인이 필요하다. 생성 문장을 제출용으로 쓰지 않는다.

## 파일 목록

| 파일 | 용도 |
|---|---|
| 01_job_fit_analysis.md | 세 공고 조건·요건·프로젝트 매핑, J01~J05 출처 |
| 02_evidence_and_contribution.md | 내부 구현·실행·기여 근거표 E01~E21 |
| 03_placeos_portfolio.md | 3쪽 목표 공통 프로젝트 포트폴리오, 행정 역량의 보조 자료 |
| 04_technical_brief.md | 시스템·데이터·알고리즘·검증 상태 |
| 05_application_draft.md | 기관별 사용 안내 |
| 05a_korea_mot_application.md | 고려대 행사·서무 중심 4문항 임시 초안 |
| 05b_yonsei_anchor_worksheet.md | 공식 5문항·각 300자 내외의 본인 작성표 |
| 05c_yonsei_uif_worksheet.md | 협약·정산 직무 증빙과 공식 문항 확인표 |
| 06_project_experience_bullets.md | 이력서용 프로젝트 문장·직무별 한계 |
| 07_interview_preparation.md | 개인 역할·한계·직무·Codex 확인 |
| 08_graduate_research_plan.md | 채용과 분리한 석사 연구 준비·근무 충돌 검토 |
| 09_final_review.md | 내용·개인정보·분량·패키지 검토 |
| pdf/ | 03·04·05·05a·05b·05c·08 PDF |
| release/placeos_career_review.zip | 전체 채용 개인 검토 자료 |
| release/placeos_korea_career_review.zip | 고려대 검토용 03·04·05a |
| release/placeos_yonsei_anchor_review.zip | 앵커사업단 개인 작성표만 |
| release/placeos_yonsei_uif_review.zip | 산학협력단 개인 확인표만 |
| release/placeos_research_preparation.zip | 04·08 연구 준비 |

## 확인 상태와 검증

기획·개발·사업 방향성과 가치 수립, 약 150시간은 본인 진술·추정이다. 구체적인 파일별 기여·경력·학력은 미확인이다. 저장소 기준 커밋은 `ef31a059f962eab5ae922f7d722b8ef9dc435bfc`이며 81개 거점 집계, 시계열 1,782행 및 선택 테스트 6개를 확인했다. 현장 공실 정확도·사업 효과·LLM 실호출을 검증한 것은 아니다.

검사 항목: 문서 필수항목 검사, 주장별 근거 검사, 개인정보·비밀정보 검사, ZIP 구성 검사. 결과는 `internal/document_checks.json`, PDF 검토는 `internal/pdf_qa.json`, 문항 분량은 `internal/application_lengths.json`에 기록한다. 통과 여부와 지원 자격 충족은 별개다. 재생성은 `internal/build_package.py`, 검사는 `internal/verify_documents.py`로 수행한다. Windows 맑은 고딕·ReportLab·PyMuPDF가 필요하며 로컬 의존성은 `.build/deps`에 있다.

## 제출 전 남은 사용자 확인

1. 학력·졸업 여부·경력·자격·근무 가능 여부와 각 공고의 요건을 대조한다.
2. 고려대 공식 제출방식·문항·분량·마감 시각을 확인하고 희망연봉을 이력서에 기재한다.
3. PlaceOS 기간·직접 개발한 기능·기획 결정 사례·AI 활용 범위를 채운다.
4. 연세대 AI 제한과 앵커사업단 적용 여부를 확인하고 본인 작성·제출 요건을 따른다.
5. 개인정보·증빙은 공개 저장소에 넣지 않고 기관의 공식 접수 방식으로 직접 처리한다.
6. 추가 포트폴리오 허용을 확인한다. ZIP은 제출을 대신하지 않으며 자동 지원은 하지 않는다.

기존 reports 두 파일의 변경은 보존했다. 제품 코드와 배포 설정은 변경하지 않는다. 사용자의 최신 지시에 따라 문서 변경만 Git 반영 대상으로 삼으며 커밋·푸시·머지 결과는 최종 응답에서 실제 상태를 보고한다.

# Page 문헌 검토 보완 기록

확인일: 2026-09-19. 대상은 Page 원고의 관련 연구, 참고문헌과 Word 변환이다. 기존 조건 D 실증값·판정·출처 계약은 변경하지 않는다. 검수 항목은 `literature_claim_traceability`, `bibliography_identity`, `empirical_numbers_unchanged`, `unknowns_preserved`, `docx_content_parity`, `docx_visual_review`다.

## 확인 범위와 적용

| 문헌 | 이번 확인 위치 | 원고에 사용하는 내용 | 사용하지 않는 내용 |
|---|---|---|---|
| Alsudais (2021), DOI 10.1016/j.dss.2020.113453 | 출판사 서지·초록, arXiv:2007.03019v2 PDF의 객체·릴리스 관련 본문. 기존 전 페이지 대조는 reading-ledger.md에 보존 | 객체 의미와 릴리스 특정의 필요 | 원문 오류 비율·검정 수치, 최종본 오류 판정 |
| Marsden & Pingry (2018), DOI 10.1016/j.dss.2018.10.007 | 출판사 검색 색인에서 제공되는 초록·서론. 직접 열기는 실패. 전문 확인 아님 | 데이터 수집·검증·품질 명세의 필요 | 상세 임계값, 전 절의 방법 검증 완료 주장 |
| Timmerman & Bronselaer (2019), DOI 10.1016/j.dss.2019.113138 | UGent 기관 페이지의 초록·서지·다운로드 접근 표시. PDF는 UGent only | 규칙 기반 품질 측정과 판정 불확실성이라는 문제의식 | 확률·가능성 분포, 품질 임계값과 수식의 적용 |
| Sandve, Nekrutenko, Taylor & Hovig (2013), DOI 10.1371/journal.pcbi.1003285 | PLOS 출판사 HTML 전문의 서론과 Rule 1–10. 참고문헌 목록 확인은 인용된 모든 원문 검토를 뜻하지 않음 | 생성 경로·버전·중간 결과의 보존, 주장과 결과 연결 | PlaceOS 순서 검사를 이 논문의 방법으로 귀속, 공개 접근성 완료 주장 |
| National Academies of Sciences, Engineering, and Medicine (2019), DOI 10.17226/25303 | 공식 온라인 본문 제3장 Defining Reproducibility and Replicability, 인쇄면 43–46 및 Conclusion 3-1 | 동일 자료 계산 재현과 새 자료 반복 검증의 용어 구분 | 전체 보고서 정독·모든 권고 준수 주장 |

## 일차 출처

- Alsudais 저자 공개본: https://arxiv.org/pdf/2007.03019v2
- Alsudais 출판 기록: https://www.sciencedirect.com/science/article/pii/S0167923620302086
- Marsden·Pingry: https://www.sciencedirect.com/science/article/pii/S0167923618301647
- Timmerman·Bronselaer: https://biblio.ugent.be/publication/8634924
- Sandve 등: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003285
- National Academies 제3장: https://www.nationalacademies.org/read/25303/chapter/6

## 해석 제한

이번 검토는 연구 질문에 맞춘 범위 제한 문헌 검토이며 체계적 문헌고찰이 아니다. 위 문헌을 근거로 공실 정확도나 최초성을 주장하지 않는다. Alsudais 최종본·별도 부록·원자료·저자 코드와 기존 보조문헌 전문의 미확보 상태를 유지한다. 이전 source-register.json과 reading-ledger.md는 과거 판본·검토 이력으로 보존한다. 이번에 원문 파일의 새 다운로드·해시 검증이나 그림·표의 새 전수 시각 대조를 수행했다고 주장하지 않는다.

Word에는 기존 연구 근거 링크를 자료 주석으로 묶고, 본문 수치·한계·외부 문헌 인용을 유지한다. 새 실험, 데이터 재수집 또는 제품 코드 변경은 없다.

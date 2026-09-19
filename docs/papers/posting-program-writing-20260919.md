# Posting·Program 집필 및 검수 기록

작성일: 2026-09-19.

## 범위와 판정 원칙

대상은 `paper-posting.md`, `paper-program.md`, `evidence-index.md` 및 이 기록이다. Posting은 보존된 진단의 한계 연구, Program은 현행 계약의 시스템·설계 연구로 완결된 초안을 작성했다. 원천 데이터, 제품 코드, feature 문서와 reports는 수정하지 않았다. 실측이 없는 값과 실제 사업 성과는 채우지 않았다. Page의 기존 작업은 유지했다.

## 근거 대조

- Posting의 공식 소스 조사는 당시 54거점·528 후보행의 기록이다. 층번호 프로브의 66거점·664유닛과 모집단을 합치지 않았다.
- 층번호 프로브 JSON에서 단일층 30개(4.5%)와 면적 차이의 최솟값·최댓값·중앙값이 모두 영임을 확인했다. 과거 프로브를 이번에 재실행한 것은 아니다.
- 층번호 후속을 층별 분할의 독립 실험으로 중복 계수하지 않았다. 매출 앵커 오류 수정과 설명 가설 기각을 구분하고, ‘전부 프라임’ 전제의 반증을 유지했다.
- Program은 현재 ProgramBrief와 online/offline/signals 계약을 기준으로 썼다. 삭제된 온보딩과 과거의 트렌드 맥락 부재 시 무경고 통과를 현행 기능으로 기술하지 않았다.
- 테스트 통과를 사실성 위반율, 실제 투자 회수 또는 사용자 성과로 해석하지 않았다.

## 문헌 확인 범위

| 문헌 | 확인한 출처·범위 | 사용 범위 |
|---|---|---|
| Marsden & Pingry (2018) | [출판사](https://www.sciencedirect.com/science/article/pii/S0167923618301647)의 서지·공개 초록·서론 | 수치 데이터 품질과 재현 문제. 전체 본문 확보 주장은 하지 않음 |
| Alsudais (2021) | [저자 공개본](https://arxiv.org/pdf/2007.03019v2), 기존 Page 문헌 검토 기록 | 공개 자료의 객체 식별과 판본 의존성. PlaceOS 정확도를 대신하는 증거 아님 |
| Min 등 (2023) | [ACL 서지와 PDF](https://aclanthology.org/2023.emnlp-main.741/), 초록·서론·평가 정의 | 사실 주장과 지지 근거의 분리. 성능 수치 전재·벤치마크 실행 없음 |
| Gao 등 (2023) | [ACL 서지와 PDF](https://aclanthology.org/2023.emnlp-main.398/), 초록·평가 차원 설명 | 유창성·정답성·인용 품질의 구별. 전체 부록 검토를 뜻하지 않음 |

## 실행한 검사

- `posting_source_contract`: 루트에서 `python -m pytest data/tests/test_posting_unit_area_sources.py -q` → **3 passed**. 외부 API 실호출이나 호실 면적 정확도 검사가 아니다.
- `program_guard_contract`: `apps/backend`에서 `python -m pytest tests/test_ha_guard.py tests/test_program_output_split.py -q` → **54 passed**. 고정 사례·목킹 검사다. 실 LLM 호출은 실행하지 않았다.
- 문서 검수 통과: 미작성 표시 없음, 필수 절 존재, 로컬 링크 대상 존재, 절 번호를 제외한 수치 토큰의 인덱스 등재, `git diff --check`. 기각·한계·미측정의 의미는 본문과 근거를 대조했다.

## 남아 있는 연구 한계

두 파일은 참고문헌까지 갖춘 원고 초안이며 투고 승인이나 실증 완결을 뜻하지 않는다. Posting에는 실제 계약·성과와 연결한 외부 정답이 없고, Program에는 독립 생성 품질 평가가 없다. 후속 평가 설계는 실행 결과와 구분해 본문에 명시했다.

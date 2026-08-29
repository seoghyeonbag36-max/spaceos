# Posting 호실 면적 실측 소스 탐색 — 2026-08-29

## 결론

현재 `vacant_units.json` 의 528개 거점-feature 후보행을 실제 호실 인벤토리로 대체할 공개·공식
소스는 확인되지 않았다. 따라서 `area` 를 새 값으로 채우지 않고, 건축물대장 상업면적
÷ `capacity`인 현행 균등분할과 `inputs_source["area"]="gold-ledger"`를 유지한다.
면적 게이트는 **0.5**, Posting 진행률은 **97.6%** 그대로다. 이는 구현 실패를 숨긴
수치가 아니라 관측 근거가 없는 값을 만들지 않는 fail-closed 상한이다.

이 결론은 “조사를 안 했다”가 아니다. 후보가 아래 계약 네 조건을 모두 만족해야만
배선하도록 `data.validation.posting_unit_area_sources`와 테스트로 고정했다.

1. 호실 단위 면적
2. 현재 공실·임대가능 상태
3. 54거점의 528 거점-feature 후보행(450 거점/PNU 쌍·407 고유 PNU)과 같은
   민간 일반건축물 모집단
4. 기존 유닛에 붙일 안정적인 키(PNU+호 또는 동등한 키)

## 공식 후보 판정

| 후보 | 호실 면적 | 현재 공실 | 기존 인벤토리 범위 | 안정 조인키 | 판정 |
|---|---:|---:|---:|---:|---|
| [국토교통부 건축HUB 건축물대장정보](https://www.data.go.kr/data/15134735/openapi.do) | O | X | X | O | 전유부는 집합건물이고 공실 상태가 없다. 기존 450 PNU와 교집합 0이라는 08-26 실측을 뒤집지 못한다 |
| [서울교통공사 지하상가임대정보](https://www.data.go.kr/data/15071329/fileData.do) | O | O | X | X | 상가번호·면적·공실/임대진행을 분기 갱신하지만 지하철 역사 내부 공공상가라는 별도 인벤토리다 |
| [LH 분양임대공고별 공급정보](https://www.data.go.kr/dataset/15038398/openapi.do) | O | O | X | X | 공고별 호·층·면적은 실측이지만 LH 공급분으로 범위가 다르다 |
| [온비드 이용기관 공매물건](https://www.data.go.kr/data/15000849/openapi.do) | X | O | X | X | 공공자산 임대공고이며 기존 민간 유닛의 호실 면적·PNU+호 계약이 없다 |

상업·업무용 실거래가 공개자료는 **매매** 자료이고, 공개된 전월세 실거래는 주택
임대차가 대상이므로 후보 표에도 올리지 않았다. 민간 매물 사이트 크롤링은 공식 API가
아니며 약관·재현성·배포 자산성 문제가 있어 탐색 계약에서 제외했다.

## 대상 파일과 통과 조건

- 대상 파일
  - `data/validation/posting_unit_area_sources.py`
  - `data/tests/test_posting_unit_area_sources.py`
  - 이 문서
  - `docs/feature-posting.md` — Posting 97.6%·`area` 0.5의 현재 상태와 재개 조건
- 입력 소스와 출처 표기
  - 위 공공데이터포털의 기관 원문 메타데이터
  - 런타임 값은 추가하지 않았으므로 기존 `gold-ledger` 의미를 변경하지 않음
- 통과 테스트
  - `test_no_public_source_is_eligible_for_existing_private_units`
  - `test_area_source_candidates_have_primary_evidence_and_rejection_reason`
  - `test_partial_public_stock_cannot_promote_the_existing_area_contract`
- 금지 사항
  - 일부 공공자산 표본을 54거점의 528 거점-feature 후보행을 대체하는 실측처럼 배선하지 않는다.
  - 호실 면적·현재 공실 상태·동일 모집단·안정 조인키 중 하나라도 없으면 값을 만들지 않는다.
  - `inputs_source` 의미와 집합건물 배제 규칙을 바꾸지 않는다.

## 다시 열 수 있는 조건

공식 소스 또는 B2B 임대인 제공 데이터가 **같은 행에서** `PNU`, 호실/층, 전용면적,
현재 임대가능 상태, 관측시점을 제공할 때만 다시 연다. B2B 입력 계약으로 옮기려면
새 출처 값을 정의해야 하므로 `AGENTS.md` §4의 별도 설계 판단을 먼저 받아야 한다.
외부 코파일럿 공급자의 URL·키 설정은 이 면적 승격과 별개의 운영 작업이다.

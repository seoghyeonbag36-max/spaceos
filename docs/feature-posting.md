# Posting — 입점 솔루션 (외부 AI 창업 코파일럿 연동)

> PPPP: **Promotion → Posting**. 공실에 입점하려는 창업자에게 입점 의사결정 정보를 구조화해 제공한다.
> **2026-07-18 개정**: 자체 비용-효용 계산 대신 **외부에서 만든 AI 창업 코파일럿 프로그램을 연동해 적용**하는 것을 1순위로 한다. 내부 3-Tier(고급화/가성비/기능중심) 계산은 폴백·검증용으로 유지.

## 0. 구현 현황 (2026-08-17)

**어댑터는 여전히 미연동이고, 실제로 도는 것은 항상 3-Tier 폴백이다.**
`_call_copilot()` 이 늘 `None` 을 반환한다 — 외부 코파일럿의 입출력 명세가 없어서이지
코드가 없어서가 아니다. 그래서 그간의 작업은 **폴백의 입력과 기준**을 올리는 쪽이었다.

| 항목 | 상태 | 비고 |
|---|---|---|
| 3-Tier 폴백 계산 | ✅ | 고급화/가성비/기능중심 + `roi_months` |
| `rec` 추천 기준 | ✅ **정의 완료(08-16)** | **회수 최단**. `districts.recommend_tier()` 가 계산 — 손으로 적은 값이 54거점 카드에 노출되던 것을 걷어냈다 |
| 실제 공실 유닛 인벤토리 | ◐ **49/54거점 524유닛** | 잔여 5곳은 `build_vacant_units` **재실행 대기**(08-17 확인) — 데이터 제약이 아니다 |
| 3-Tier 입력 4종 | ◐ **1.5/4** | `rent` ✅ R-ONE · `foot` ◐ flpop+시드서열 · `area` ⬜ · `prem` ⬜ |
| 외부 코파일럿 어댑터 | ⬜ | **외부 명세 확보**가 선행 |
| 3-Tier **비용 모델** | 🔴 **미보정 — 현 병목** | 아래 |

🔴 **`rec` 을 정하자 병목이 비용 모델로 옮겨왔다.** 추천 기준을 "회수 최단"으로 둔 이상
`roi_months` 계산식이 **곧 추천 결과**가 된다. 그런데 `tier_scenarios()` 의 `month_cost`
에 **원가·인건비가 없다**:

- 마진이 **51~73%** 로 나온다 — 실제 외식업은 10~20% 다.
- 회수기간이 **0.5~1.6개월**이다.
- `factory`(기능중심) 전략은 **전수 실측에서 한 번도 1위가 못 된다** — 세 전략 중
  하나가 구조적으로 死문항이라면 비교 자체가 성립하지 않는다.

영향범위가 유닛 상세가 아니라 **54거점 카드 전체**(`tier_mix`·`rec_top`)라
Posting 의 다음 작업은 여기다. 대상 파일 `apps/backend/app/services/districts.py`.

위 수치의 출처는 `recommend_tier()` 의 docstring(`districts.py:118~123`)이고,
`factory` 판정은 **면적 10~80평 · 임대료 100~2000만원 · 유동 저/고 전수 스윕** 결과다.

⚠ **단위 혼용과 혼동하지 말 것.** `roi()` 가 `invest(백만원) / net(만원)` 이라 회수기간이
100배 작게 나오던 결함은 2026-08-01 에 교정됐다(`invest × 100 / net`). 남은 것은 계산
단위가 아니라 **비용 항목 누락**이다.

## 0-1. 연동 타당성 검증 (2026-07-18)

| 항목 | 판단 | 근거 |
|---|---|---|
| 아키텍처 적합성 | **가능** | Posting은 서비스 계층이 얇아(합성 3-Tier 계산) 어댑터 패턴으로 외부 프로그램 교체가 쉬움 |
| 연동 방식 | **조건부** | 외부 코파일럿의 제공 형태(REST API / Python 패키지 / 별도 앱)가 미확정 — `services/posting.py` 어댑터 한 곳에만 가정을 격리 |
| 폴백 | **필수** | 코파일럿 미설정·장애 시 내부 3-Tier 계산(`services/districts.py::tier_scenarios`)으로 응답 보장 |
| 스키마 | **필수** | 외부 응답을 `PostingResult`(예상 매출·투자비·ROI·손익분기)로 정규화 — FE·리포트가 공급자에 독립 |

## 1. 담당 코드 영역

```
apps/backend/app/services/posting.py      외부 코파일럿 어댑터 + 3-Tier 폴백 (현존)
apps/backend/app/services/districts.py    tier_scenarios() · recommend_tier() ← 비용 모델·추천 기준
apps/backend/app/services/posting_inputs.py  rent/foot/area/prem 실데이터 서빙
apps/backend/app/schemas/posting.py       시뮬레이션 요청/결과 스키마 (현존)
apps/backend/app/api/v1/ai.py             POST /simulate-revenue (현존)
apps/backend/app/core/config.py           posting_copilot_url / posting_copilot_key
data/pipelines/build_posting_inputs.py    → gold/platform_posting_inputs.json
data/pipelines/build_vacant_units.py      → gold/{거점}/vacant_units.json (49거점)
ml/inference/predictor.py                 매출 예측(LSTM) — 폴백·크로스체크 재사용
```

## 2. 환경 설정

```bash
cd apps/backend && source .venv/bin/activate
# 외부 AI 창업 코파일럿 (미설정 시 내부 3-Tier 폴백으로 동작)
echo "POSTING_COPILOT_URL=https://..." >> .env    # 확정 시 기입
echo "POSTING_COPILOT_KEY=..." >> .env
uvicorn app.main:app --reload
```

## 3. 작업 순서

> **현재 위치: 0번이 다음이다.** 1번은 외부 명세가 없어 막혀 있고, 그 사이 폴백의
> 입력(`rent`)과 기준(`rec`)을 올렸다. 이제 그 둘이 올라탄 **계산식**이 남았다.

0. **3-Tier 비용 모델 보정 (최우선)** — `districts.tier_scenarios()` 의 `month_cost` 에 원가·인건비를 넣는다. 통과 조건: 마진이 외식업 실측대(10~20%)에 들어오고, `factory` 가 적어도 일부 입력 조합에서 1위가 될 것. 지금은 셋 중 둘로만 순위가 갈린다.
1. **어댑터 계약 확정** — 외부 코파일럿의 입출력 명세 확보 → `services/posting.py`의 `_call_copilot()` TODO 해소. 그 전까지는 요청/응답을 `PostingRequest`/`PostingResult`로 고정해 둔다.
2. **폴백 유지** — `POSTING_COPILOT_URL` 미설정 또는 호출 실패 시 3-Tier 계산으로 동일 스키마 반환 (`source: "fallback-3tier"` 표기).
3. **정규화 검증** — 코파일럿 응답 필드 ↔ `PostingResult` 매핑 테이블 작성, 단위(만원/월) 불일치 방지.
4. **추천 연계** — GNN 업종 추천(Platform) 결과를 코파일럿 입력(업종 후보)으로 전달해 "이 공실 + 추천 업종 + 전략별 ROI"를 묶어 제공.
5. **근거 데이터 보강(선택)** — 공정위 가맹정보(창업비용, `api-keys-and-specs.md` §8-C)로 폴백 가정을 실데이터로 치환.

## 4. Claude Code 작업 예시

```
/clear
/posting 외부 코파일럿 응답 명세가 확정됨.
  services/posting.py 의 _call_copilot() 을 실제 API 호출로 교체하고
  응답을 PostingResult 로 정규화. 실패 시 3-Tier 폴백 유지.
  tests/test_posting.py 에 mock 응답 정규화 테스트 추가.
```

## 5. 검증

- `cd apps/backend && pytest` — 폴백 계산·스키마 정규화 단위 테스트
- 코파일럿 미설정 상태에서 `/api/v1/ai/simulate-revenue`가 3-Tier 결과를 반환하는지 확인
- 외부 응답 매핑에 단위·통화 가정이 주석으로 명시됐는지 확인 (`TODO: 실제 연동` 규칙 준수)

# docs/apply — 공모전 신청서

**목표**: 공모전·창업·학회 출품 원고를 근거 대장 위에서 쓴다. 신청서 작성에는 "잘 썼는가"를
판정하는 테스트가 없어서 Codex 로 내보낼 수 없었는데, 통과 조건을 **거짓이 아님**으로 좁혀
스크립트 하나로 만들었다. 그 결과 이 디렉터리의 작업은 판단(Claude Code)과 실행(Codex)으로
갈린다.

작성 규칙은 [AGENTS.md](AGENTS.md). 근거 대장은 [claims.json](claims.json).

## 검사

```bash
# 전체
python scripts/check_application.py

# 원고 하나
python scripts/check_application.py --doc docs/apply/01-spatial-info/draft.md

# 제출 직전 — FILL 마커가 남아 있으면 실패
python scripts/check_application.py --doc docs/apply/01-spatial-info/draft.md --require-complete
```

산출은 `reports/application_check.json`. `scripts/run_full_verify.py` 의 `application-check`
스텝으로도 돈다.

## 분업

| | 맡는 것 |
|---|---|
| **Claude Code** (판단) | 부문 선택 · 리프레이밍 각도 · 배점↔절 대응 · `claims.json` 의 allow/forbid 판정 · FILL 마커 안에 무엇을 쓸지 |
| **Codex** (실행) | 마커 자리 채우기 · 표 옮기기 · 분량 맞추기 · 검사기 실패 고치기 · `.docx` 변환 |

마커의 지시와 본문이 어긋나면 **마커가 맞다**. 마커를 고치려면 판단이 필요하므로 그때는
멈추고 보고한다.

## 원고 상태

캘린더(출품 캘린더 아티팩트)의 여덟 자리 중 마감이 가까운 둘만 골격을 세웠다.

| | 대회 | 마감 | 원고 |
|---|---|---|---|
| 01 | 제8회 공간정보 활용·아이디어 경진대회 | 2026-09-18 | [draft.md](01-spatial-info/draft.md) — 골격 |
| 02 | 2026 GovTech 창업 경진대회 | 2026-09-21 10:00 | [draft.md](02-govtech/draft.md) — 골격 |
| 03 | 제3회 미래융합인재 발굴 SW 챌린지 | 2026-10-07 | 미착수 — 일반부 3~5인 팀·연령 요건이라 자격 확인 먼저 |
| 04 | 제9회 핀테크 아이디어 공모전 | 2026-10-08 16:00 | 미착수 — 여신 언어로의 리프레이밍이 선행 |
| 05 | 제3회 부동산정보 활용성 논문 공모전 | 공고 대기 | 미착수 — 1단계는 논문제안서뿐 |
| 06 | 한국정보기술학회 2026 추계 | 2026-10-23 | 미착수 — `docs/papers/` 소관. LSTM 근거 등재가 선행 |
| 07 | 2026 DATA·AI 분석 경진대회 | 2026-11-25 | 미착수 — 부문 규정 확인 먼저 |
| 08 | PACIS 2027 | 2027-03-01 | 미착수 — `docs/papers/` 소관. AIS 템플릿 필수 |

06·08 은 학술 원고라 [docs/papers](../papers/) 의 규칙과 근거 인덱스를 따른다. 이 디렉터리는
신청서 전용이다.

## 서식을 아직 대조하지 못했다

두 원고 모두 머리에 `<!-- 확인필요(서식): … -->` 가 붙어 있다. 주최처 서식(hwp)을 받아
항목명·분량·배점을 대조하기 전까지 절 구성은 **가설**이다. 대조한 뒤에는 그 주석을 지운다.

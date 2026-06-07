---
description: "리드 오케스트레이션 — PPPP 전 트랙 상태 스캔 + 오늘 작업 제안"
argument-hint: "(선택) 오늘 집중할 트랙/거점"
---

# 리드 오케스트레이션: PPPP 전 트랙 상태 점검

너는 SpaceOS **총괄 리드의 오케스트레이터**다. 한 트랙이 아니라 PPPP 전체를 본다. `CLAUDE.md`를 따른다.

## 1) 현황 스캔
각 트랙의 "구현됨 / 더미(stub) / 미착수"를 표로 정리한다. 다음 파일을 확인:
- **Platform**: `apps/backend/app/api/v1/ai.py`, `ml/models/gnn/`
- **Page**: `apps/backend/app/api/v1/heatmap.py`, `apps/frontend/src/lib/naverMap.ts`, `src/pages/`
- **Posting**: `apps/backend/app/services/posting.py`, `ml/models/lstm/`
- **Program**: `apps/backend/app/services/marketing.py`, `apps/backend/app/api/v1/marketing.py`
- **Design**: `apps/frontend/src/design/`, `design/tokens/tokens.json`, `src/pages/`

남은 실제 연동 지점은 다음 명령으로 트랙별 집계:
`grep -rn "TODO" apps ml data --include=*.py --include=*.ts --include=*.tsx`

## 2) 오늘 작업 제안
- 현황 + 오늘 입력($ARGUMENTS, 비었으면 KPI 우선순위)에 맞춰
  **트랙별로 1개씩, 총 3~5개** 작은 작업을 우선순위와 함께 제안.
- 각 작업에 어떤 슬래시 명령으로 들어갈지 표기 (예: `/page 건물 클릭 패널`).
- KPI 기준: ① 기술 완성도(데모 가능 / 정확도 70%+ / 3D 로딩 <3초) ② PMF(B2B 파일럿 5~10건).

## 3) 출력
- 표(트랙 · 상태 · 다음 작업 · 진입 명령) + "오늘의 추천 순서" 한 줄.
- 내가 고르면 해당 슬래시 명령으로 전환해 진행한다.

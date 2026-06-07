---
description: "공통 검증 — 백엔드 테스트 + 프론트 타입체크 + ML import"
argument-hint: "(선택) 검증 대상"
---

# 공통 검증 루틴

방금 변경분을 검증한다. 대상(선택): $ARGUMENTS

실행:
- 백엔드 테스트/임포트: `cd apps/backend && pytest -q`
- 프론트 타입체크/빌드: `cd apps/frontend && npm run build`
- ML 핵심 import: `cd ml && python -c "import torch; print('torch', torch.__version__)"`

규칙:
1. 실패하면 원인과 수정안(diff)을 제시하고, 통과까지 반복.
2. `CLAUDE.md` 규칙 점검: 경로 · 타입힌트 · 한국어 주석 · `TODO` 표기.
3. 3D/대시보드 변경은 스크린샷으로 시각 확인을 권고.

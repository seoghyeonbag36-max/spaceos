# SpaceOS 개발 문서

Claude Code(CLI) 기반 SpaceOS 개발 가이드. PPPP 프레임워크 4기능별로 "무엇을 설치하고 어떤 코드를 작성하는지" 정리한다.

## 문서 목록

| 문서 | 내용 |
|------|------|
| [00-claude-code-setup.md](00-claude-code-setup.md) | Claude Code 설치·인증·프로젝트 연결·공통 워크플로우 |
| [01-app-design-handoff.md](01-app-design-handoff.md) | **외부 작업자 핸드오프** — 파일 이전 + Claude Code 설치 + 디자인/프론트엔드 작업 |
| [feature-platform.md](feature-platform.md) | **Platform** — 상권 AI 추천 엔진 (LSTM 공실 예측 + GNN 업종 추천) |
| [feature-page.md](feature-page.md) | **Page** — 공실 히트맵 + 3D 디지털 트윈 |
| [feature-posting.md](feature-posting.md) | **Posting** — 입점 솔루션 (전략별 비용-효용·ROI 분석) |
| [feature-program.md](feature-program.md) | **Program** — LLM 마케팅 자동화 + 행사 추천 |

## 권장 진행 순서

1. **00 설치/설정** → git init + Claude Code 로그인 + 슬래시 커맨드 확인
2. **데이터 기반 마련** — `data/`의 Bronze→Silver→Gold 파이프라인 (거점: 라페스타→성수동→용봉동)
3. **Platform** — AI 모델이 다른 기능의 입력이 되므로 우선 구축
4. **Page** — 모델 결과를 히트맵·3D로 시각화
5. **Posting / Program** — 분석 결과를 입점 솔루션·마케팅으로 확장

## 공통 원칙 (CLAUDE.md 발췌)

- 응답·주석·문서는 한국어, 기술 용어 영문 병기
- 데이터 기반·추측 최소화 — 더미값은 `TODO`로 실연동 지점 명시
- 성능 목표: AI 공실 예측 정확도 70%+(Phase1), 3D 맵 로딩 <3초, API p95 <200ms
- 비밀값은 `.env`(`.gitignore` 보호)에만 — 커밋 금지

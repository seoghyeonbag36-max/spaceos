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
| [spaceos-vibe-build-sequence.md](spaceos-vibe-build-sequence.md) | **빌드 순서 + 현재 위치** — Phase 0~6 의존 순서, 막힌 것의 종류 구분 |

## 진행률은 문서에서 읽지 않는다

```bash
python scripts/pppp_status.py
```

산출물을 세어 트랙별 진행률과 게이트를 찍는다. 문서의 거점 수·정확도는 **적은 날의
값**이라 낡는다(이 저장소에서 실제로 두 번 낡았다 — Tier1 을 13, 그 다음 22 로 적고
있었다). 위 스크립트가 `[자동]` 으로 표시하는 값이 단일 기준이고, `[선언]` 은 근거
경로를 확인한 뒤 인용한다.

## 권장 진행 순서

1. **00 설치/설정** → git init + Claude Code 로그인 + 슬래시 커맨드 확인
2. **데이터 기반 마련** — `data/`의 Bronze→Silver→Gold 파이프라인 (거점: 신사동 가로수길→성수동)
3. **Platform** — AI 모델이 다른 기능의 입력이 되므로 우선 구축
4. **Page** — 모델 결과를 히트맵·3D로 시각화
5. **Posting / Program** — 분석 결과를 입점 솔루션·마케팅으로 확장

## 공통 원칙 (CLAUDE.md 발췌)

- 응답·주석·문서는 한국어, 기술 용어 영문 병기
- 데이터 기반·추측 최소화 — 더미값은 `TODO`로 실연동 지점 명시
- 성능 목표: AI 공실 예측 정확도 70%+(Phase1), 3D 맵 로딩 <3초, API p95 <200ms
- 비밀값은 `.env`(`.gitignore` 보호)에만 — 커밋 금지

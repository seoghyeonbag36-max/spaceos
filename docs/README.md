# SpaceOS 개발 문서

Claude Code(CLI) 기반 SpaceOS 개발 가이드. PPPP 프레임워크 4기능별로 "무엇을 설치하고 어떤 코드를 작성하는지" 정리한다.

## 문서 목록

| 문서 | 내용 |
|------|------|
| [00-claude-code-setup.md](00-claude-code-setup.md) | Claude Code 설치·인증·프로젝트 연결·공통 워크플로우 |
| [01-app-design-handoff.md](01-app-design-handoff.md) | **외부 작업자 핸드오프** — 파일 이전 + Claude Code 설치 + 디자인/프론트엔드 작업 |
| [feature-platform.md](feature-platform.md) | **Platform** — 상권 AI 추천 엔진 (LSTM 공실 예측 + GNN 업종 추천) |
| [feature-page.md](feature-page.md) | **Page** — 공실 히트맵 + 층별 매물 목록 + 네이버 거리뷰 |
| [feature-posting.md](feature-posting.md) | **Posting** — 입점 솔루션 (전략별 비용-효용·ROI 분석) |
| [feature-program.md](feature-program.md) | **Program** — LLM 마케팅 자동화 + 상용 입력 온보딩 |
| [spaceos-vibe-build-sequence.md](spaceos-vibe-build-sequence.md) | **빌드 순서 + 현재 위치** — Phase 0~6 의존 순서, 막힌 것의 종류 구분 |
| [deploy-cloud-run.md](deploy-cloud-run.md) | **배포(현행)** — main 푸시 → GitHub Actions → Cloud Run. 빌드 시점 가드·수동 배포·무료 한도 |
| [deploy-vercel.md](deploy-vercel.md) | ~~배포~~ **이력 전용** — Vercel 은 2026-08-28 프로덕션에서 내려왔다(무료 플랜 상업적 사용 금지). `vercel --prod` 를 쓰지 말 것 |
| [api-keys-and-specs.md](api-keys-and-specs.md) · [api-key-checklist.md](api-key-checklist.md) | 인증키 5종과 응답 필드 스펙 |
| [poc-building-vacancy.md](poc-building-vacancy.md) | 건물 단위 공실 PoC 설계 (D1 스키마) |
| [decision-infra-layer-2026-08-25.md](decision-infra-layer-2026-08-25.md) | **결정·구현 기록** — PPPP 게이트가 세지 않는 층(DB·인증·과금·오케스트레이션) |
| [prep-sgis-application.md](prep-sgis-application.md) | SGIS 집계구 경계 취득 기록 (막힘 5 해소 · 재신청 절차 보존) |

### 실측 기록 (finding-*) — 판단의 근거가 남은 곳

| 문서 | 무엇을 결론지었나 |
|------|------|
| [finding-sequence-and-accuracy-2026-08-17.md](finding-sequence-and-accuracy-2026-08-17.md) | 작업 순서·정확도 목표 재설정, Top-1 게이트 폐기와 off-prior 게이트 신설 |
| [finding-anchor-population.md](finding-anchor-population.md) | R-ONE 앵커 대조 — 격차를 어떻게 읽나 |
| [finding-expos-quota-2026-08-09.md](finding-expos-quota-2026-08-09.md) | 건축HUB 전유부 쿼터가 확장 속도를 정한 기록 (해소 08-17) |
| [finding-foot-traffic-resolution.md](finding-foot-traffic-resolution.md) | 유동인구 해상도 — ~~`foot` 만 집계구를 기다린다~~ → **해소 08-25**. 본문 결론 둘이 반증돼 문서 앞에 정정 배너가 붙어 있다 |
| [finding-posting-unit-area-sources-2026-08-29.md](finding-posting-unit-area-sources-2026-08-29.md) | Posting 호실 면적 공식 소스 재탐색 — 기존 54거점 528 거점-유닛에 승격 가능한 공개 후보 0건, 0.5 가중 유지 |
| [finding-platform13-batch-structure-2026-08-30.md](finding-platform13-batch-structure-2026-08-30.md) | 경기 Platform 을 막던 것은 배치 이름이 아니라 **세 곳에 흩어진 거점 목록**이었다 |
| [finding-goyang-paju-hubs-2026-08-30.md](finding-goyang-paju-hubs-2026-08-30.md) | 고양·파주 상권 판정 — 경기 거점의 정본. 라페스타·웨스턴돔은 **예외 서빙** |
| [finding-goyang-paju-candidates-2026-08-30.md](finding-goyang-paju-candidates-2026-08-30.md) | 고양·파주 추가 거점 후보 프로브 → 13곳 등록. **등록은 노출이 아니다** |
| [finding-ilsan-verdict-2026-08-30.md](finding-ilsan-verdict-2026-08-30.md) | 라페스타 기각 → **같은 날 폐기**. 정본은 위 `goyang-paju-hubs` |
| [finding-gyeonggi-aggregate-buildings-2026-08-30.md](finding-gyeonggi-aggregate-buildings-2026-08-30.md) | 경기 계획상가 실측 — 서울 규칙 유지, 화정만 근거가 얇다고 화면이 밝힌다 |
| [finding-gyeonggi-licensing-source-2026-08-30.md](finding-gyeonggi-licensing-source-2026-08-30.md) | 경기 인허가는 경기데이터드림 `GENRESTRT` — 키·응답 검증 완료, 좌표계 함정 하나 |
| [finding-hub-caveat-axes-2026-09-02.md](finding-hub-caveat-axes-2026-09-02.md) | 계획상가 거점을 가르는 **두 축이 어긋난다** — 판정 축이 프록시였음이 실측으로 드러났다 |

## 진행률은 문서에서 읽지 않는다

```bash
python scripts/pppp_status.py
```

산출물을 세어 트랙별 진행률과 게이트를 찍는다. 문서의 거점 수·정확도는 **적은 날의
값**이라 낡는다(이 저장소에서 실제로 두 번 낡았다 — Tier1 을 13, 그 다음 22 로 적고
있었다). 위 스크립트가 `[자동]` 으로 표시하는 값이 단일 기준이고, `[선언]` 은 근거
경로를 확인한 뒤 인용한다.

`[선언]` 게이트는 줄이는 것이 목표다 — 2026-08-19 에 Platform off-prior 게이트가
학습 체크포인트에서 직접 읽히면서 `[선언]` 9 → 8 이 됐다.

⚠ **그리고 스크립트가 세지 않는 것이 둘 있다.** 진행률 100% 를 "끝났다"로 읽지 않으려면
같이 봐야 한다.

1. **인프라 층** — DB·인증·과금·오케스트레이션 전체는 PPPP 트랙 게이트에 **아예 없다**.
   → [decision-infra-layer-2026-08-25.md](decision-infra-layer-2026-08-25.md)
2. **KPI② PMF** — B2B 파일럿 5~10건은 KPI 우선순위 2번인데 **이를 재는 게이트가 0개**였다.
   즉 PPPP 진행률은 KPI 절반(기술 완성도)만 말한다.
   → **2026-08-27 착수**: `pppp_status.py` 가 이제 KPI② 블록을 따로 찍는다(트랙 평균에는
   섞지 않는다 — 섞으면 사각지대가 묻힌다). 계측은 배선됐고 실제 파일럿 수는
   `GET /api/v1/admin/usage` 의 `active_orgs` 로 본다.
   ⚠ **"계측 배선 4/4" 는 "파일럿 4건"이 아니다** — 잴 준비가 됐다는 뜻이다.
   (배선 4번째는 계정 DB 마이그레이션 가드 — 2026-08-28 Neon Postgres 연결과 함께 붙었다.)
   → [decision-infra-layer-2026-08-25.md](decision-infra-layer-2026-08-25.md) §8

2026-08-29에는 Program 상용 입력 온보딩의 조직 인증·명시 동의·원문 비저장 계약까지
배선됐다. 이것도 **파일럿 고객이 생겼다는 뜻은 아니다**. 기술 계약 통과와 KPI②의
`active_orgs` 실측을 분리해 읽는다.

**선언이 낡는 것이 이 저장소의 주된 실패 양식이다.** 2026-08-25 에 Platform 게이트가
"막힘 5 의 선행은 SGIS 자료신청" 이라고 적고 있는 동안 그 자료는 **같은 날 이미 받아
써서** Posting `foot` 을 승격시킨 뒤였다. 선언을 인용하기 전에 **근거 경로를 연다.**

## 권장 진행 순서

1. **00 설치/설정** → git init + Claude Code 로그인 + 슬래시 커맨드 확인
2. **데이터 기반 마련** — `data/`의 Bronze→Silver→Gold 파이프라인 (거점: 신사동 가로수길에서 시작해 현재 **서울 66거점 전부 Tier1**)
3. **Platform** — AI 모델이 다른 기능의 입력이 되므로 우선 구축
4. **Page** — 모델 결과를 히트맵·층별 매물 목록·거리뷰로 시각화
5. **Posting / Program** — 분석 결과를 입점 솔루션·마케팅으로 확장

## 공통 원칙 (CLAUDE.md 발췌)

- 응답·주석·문서는 한국어, 기술 용어 영문 병기
- 데이터 기반·추측 최소화 — 더미값은 `TODO`로 실연동 지점 명시
- 성능 목표: AI 공실 예측 정확도 70%+(Phase1), 지도·건물 상세 로딩 <3초, API p95 <200ms
- 비밀값은 `.env`(`.gitignore` 보호)에만 — 커밋 금지

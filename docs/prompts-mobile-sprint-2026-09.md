# 9월 스프린트 모바일 프롬프트 14개

> 평일 근무 중·출퇴근 길에 폰으로 진행하는 작업의 **붙여넣기용 프롬프트**.
> 계획 본문: [plan-design-upgrade-2026-09.md](plan-design-upgrade-2026-09.md) · [plan-mvp-3hubs-2026-09.md](plan-mvp-3hubs-2026-09.md)
> 일반 모바일 작업 규칙(두 경로·불가능한 것): [../SpaceOS_Mobile_Dispatch_Prompts.md](../SpaceOS_Mobile_Dispatch_Prompts.md)
> 프롬프트 안의 수치는 2026-09-06 실측이다. 오래 지나면 §0 의 명령으로 다시 잰다.

---

## 0. 쓰기 전에 — 매일 밤 하는 것

클라우드 세션(claude.ai/code)은 **`origin/main` 만 본다.** 커밋 안 된 작업은 폰에서 안 보이고,
세션은 어제 상태 위에서 이미 있는 것을 다시 만든다.

```bash
git status --short          # 비어 있어야 한다
git push origin main        # ⚠ 반드시 백그라운드로 (GCM 인증 창)
```

수치를 다시 재야 하면:
```bash
python scripts/chain_status.py
python scripts/pppp_status.py
cd apps/frontend && grep -oE "#[0-9a-fA-F]{3,8}" src/pages/*.css src/components/*.css src/App.css | wc -l
```

**프롬프트를 고를 때**: A군(6개)은 폰의 Claude/GPT 앱에 붙여넣는다. B군(8개)은 claude.ai/code
클라우드 세션에 붙여넣고 결과를 PR 로 받는다.

---

# A군 — 폰만으로 완결 (Claude·GPT 모바일 앱)

## A1 · D0 여정 지도 — 점심 15분

```
너는 SpaceOS 창업자의 UX 리서치 파트너다. 아래 정보로 페르소나 3명의 여정 지도를 만든다.

[서비스] SpaceOS — 물리적 상권의 디지털 트윈. 빈 건물을 찾아 입점·홍보까지 잇는다.
[화면 4개] 순서대로
  Platform  이 입지·상권은 어떤 플랫폼인가 (업종 구성·유동·연령·시간대)
  Page      어디가 비었나 (건물·층 단위 공실 지도 + 네이버 거리뷰)
  Posting   그 자리 얼마고 몇 개월에 회수되나 (3-Tier: 고급화/가성비/기능중심)
  Program   어떻게 알리나 (온라인 퍼포먼스 / 오프라인 상권활성화)

[페르소나 3명]
 ① 소상공인 — 카페 창업 희망, 예산 1.5억, 연남동 선호
 ② 프랜차이즈 출점팀 — 서울 66거점 중 다음 출점 후보 3곳을 추린다
 ③ 지자체 담당자 — 우리 구 공실 추이와 활성화 프로그램 후보를 본다

[페르소나마다 적을 것]
 1. 앱을 열기 전 머릿속 질문 한 문장
 2. 화면 4개를 어떤 순서로 지나는가 — 건너뛰는 화면이 있으면 그 이유
 3. 각 단계에서 "이거면 됐다"고 느끼는 최소 정보 한 줄
 4. 중간에 이탈한다면 어디서, 왜
 5. 마지막에 손에 쥐는 결론 (문장으로)

[형식] 페르소나당 표 1개. 마크다운.
[금지]
 - 화면을 새로 만들지 마라. 위 4개 안에서만 움직인다
 - "AI가 추천해준다" 같은 뭉뚱그린 표현 — 어떤 값이 화면에 떠야 하는지 적어라
```

## A2 · D1 기획안 (.docx) — 퇴근길 30분

```
너는 SpaceOS 창업자의 기획 담당이다. 아래 사실만 사용해 사업 기획안을 쓴다.

[서비스] SpaceOS — 물리적 상권의 디지털 트윈 플랫폼.
가설: "Place ▶ Platform" — 물리적 공간을 SNS·디지털 관점의 플랫폼으로 읽는다.
PPPP 프레임워크(전통 4P 와 1:1):
  Place ▶ Platform     이 입지·상권은 어떤 플랫폼인가
  Product ▶ Page       이 platform 안에 어떤 page 가 만들어져야 하는가
  Price ▶ Posting      어떤 가격대의 page 가 posting 되어야 하는가
  Promotion ▶ Program  posting 한 page 를 어떤 홍보 program 으로 돌릴 것인가

[실측 — 이 숫자만 쓴다. 새 숫자를 만들지 마라]
서울 66거점 전부 Tier1(건축물대장 실측)
연남동   노출 1,133동 · 대표공실 12.5% (R-ONE 앵커 5.0%  · 격차 +7.5%p)
신촌·이대 노출 1,443동 · 대표공실 17.2% (앵커 11.68% · 격차 +5.52%p)
홍대     노출 1,325동 · 대표공실 15.0% (앵커 8.1%  · 격차 +6.9%p)
공실 유닛 인벤토리 66/66거점 664유닛
히트맵 4레이어(공실·임대·유동·밀도)가 같은 100m 격자 위에 선다
업종추천 Top-3 91.7% (거점 사전분포 89.3% 대비 Top-1 lift 5.3%)
비즈니스 모델: DaaS 월 500만원 B2B 구독 / 6개월차 파일럿 5~10건 목표

[독자] (투자자 | 프랜차이즈 본사 | 지자체) 중 하나를 골라 그 사람에게 쓴다
[목차] 1 문제 2 해법 3 PPPP 4 실측 근거 5 비즈니스 모델 6 로드맵 7 팀
[분량] A4 8~12쪽
[출력] Word(.docx). 한글 폰트를 반드시 임베딩할 것 — 폰트명만 지정하면 □ 로 깨진다
[금지]
 - 위 실측 표에 없는 수치를 만들어내지 마라. 필요하면 "[측정 필요]" 로 남겨라
 - "AI 기반", "혁신적인" 같은 내용 없는 수식어
 - 앵커 격차(+5.5~+7.5%p)를 숨기지 마라. 전수 실측과 중대형 표본은 다른 수를
   잰다는 설명을 4장에 넣어라
```

## A3 · D2a 랜딩 PRD — 퇴근길 30분

```
SpaceOS 랜딩 페이지의 PRD 를 쓴다. 이 PRD 를 Lovable 에 그대로 넣을 것이다.

[전제] 앱(지도 대시보드)은 이미 있다. 이 랜딩은 앱 앞에 서는 별개 페이지다.
       랜딩에 지도·대시보드를 만들지 않는다 — 스크린샷 자리만 비워 둔다.
[답할 질문] "SpaceOS 가 뭐고, 왜 지금이고, 왜 우리인가"
[읽는 사람] (투자자 | 프랜차이즈 본사 | 지자체) 중 하나를 골라 그 사람에게 쓴다

[쓸 수 있는 실측 — 이 밖의 숫자를 만들지 마라]
서울 66거점 전부 Tier1(건축물대장 실측)
연남동 1,133동 공실 12.5% / 신촌·이대 1,443동 17.2% / 홍대 1,325동 15.0%
공실 유닛 인벤토리 66거점 664유닛
히트맵 4레이어(공실·임대·유동·밀도)가 같은 100m 격자
업종추천 Top-3 91.7%

[색] 주색 #0EA5B7. #03C75A(네이버 그린)는 네이버 연동 맥락에만 — 남발 금지

[PRD 가 담을 것]
 1. 섹션 순서(히어로~푸터) — 각 섹션이 답하는 질문 한 줄씩
 2. 섹션별 카피 초안 — 헤드라인 + 본문 2~3문장
 3. 이미지·일러스트 슬롯 — 무엇이 들어갈 자리인지 설명 + 파일명 자리표시자
 4. CTA 문구와 그 CTA 가 가는 곳
 5. 모바일에서 무엇이 접히는가

[금지]
 - "AI 기반", "혁신적인", "원스톱" 같은 내용 없는 수식어
 - 실측 밖의 숫자 — 필요하면 [측정 필요]
 - 지도·대시보드 구현 지시. 스크린샷 슬롯으로만 표시한다
```

## A4-a · D3 레퍼런스 해부 — 캡처를 올리고 쓴다 · 점심 15분

> 핀터레스트에서 저장한 캡처를 **폰에서 그대로 첨부**한다. 이게 폰이 데스크톱보다 나은 자리다.

```
첨부한 UI 캡처를 SpaceOS 에 옮길 수 있는 "규칙"으로 분해한다.

[SpaceOS 화면 제약 — 이걸 어기는 레이아웃은 가져올 수 없다]
 - 중앙은 네이버 지도 전체화면 고정. 나머지는 전부 그 위에 뜬 오버레이다
 - 패널이 지도를 밀어내면 위반이다
 - 좌측 64px 아이콘 레일(모바일 52px)
 - 주색 #0EA5B7 · 네이버 그린 #03C75A 는 네이버 연동 맥락에만

[캡처마다 답할 것 — 4줄, 짧게]
 1. 정보 위계 — 무엇이 제일 크고 무엇이 제일 작은가 (px 추정)
 2. 여백 규칙 — 반복되는 간격 단위가 보이는가 (4px 배수인가 8px 배수인가)
 3. 색을 몇 개 썼나. 강조색은 화면 면적의 몇 % 인가
 4. 가져올 수 있는 것 한 줄 / 가져오면 안 되는 것 한 줄

[검색 키워드 — 더 모을 때 쓴다]
 real estate dashboard UI · property analytics dashboard · map dashboard dark UI
 geospatial dashboard · vacant building · empty storefront korea
 data storytelling landing page · korean fintech app UI · isometric city illustration

[금지]
 - 좋다/나쁘다 평가. 우리가 쓸 수 있는 규칙만 뽑는다
 - 캡처 이미지를 그대로 쓰라는 제안 (참조용이다 — 구조만 가져온다)
```

## A4-b · D3 일러스트 생성 — 자투리 10분

```
아이소메트릭 일러스트, 한국 도심 상가 건물, 3~5층.
1층은 영업 중(간판·조명 켜짐), 2~3층은 비어 있음(창문 어둡고 임대 현수막).
색: 배경 #F4F7FB, 선 #1C2533, 빈 층 강조 #0EA5B7.
평면적·미니멀, 그림자 없음, 배경 투명, 텍스트·간판 글씨 없음.
정사각 비율. SVG 로 줄 수 있으면 SVG, 아니면 투명 PNG.
```

변형이 필요할 때 위 문단에서 첫 줄만 바꾼다:
- **히어로용** — `한국 도심 골목 한 블록, 건물 6~8동, 일부만 조명 켜짐. 가로 16:9`
- **섹션용** — `건물 한 동의 층 단면. 층마다 상태가 다름(영업/공실/미상). 세로 3:4`
- **아이콘용** — `건물 한 동, 극단순 픽토그램, 선 2px, 단색 #0EA5B7. 정사각`

⚠ 생성 일러스트는 **랜딩 전용**이다. 앱 화면에 넣으면 실측 데이터와 섞여
"이 그림도 데이터인가" 하는 오해가 생긴다.

## A5 · D6 도메인 후보 — 점심 15분

```
SpaceOS 랜딩용 도메인 후보를 고른다.

[서비스] 물리적 상권의 디지털 트윈 SaaS. B2B(프랜차이즈 본사·자산운용사·지자체) 대상.
[제약]
 - 현재 주소는 spaceos-twin.web.app — B2B 미팅에서 임시 배포처럼 보인다
 - 한국 시장이 우선. .kr / .co.kr / .com 순으로 본다
 - "spaceos" 는 다른 서비스가 선점했을 수 있다 — 대체안도 같이 낸다

[낼 것]
 1. 후보 8개. 각각 왜 그 이름인지 한 줄
 2. 발음·받아적기 난이도 — 전화로 불러줄 수 있는가
 3. 상표·기존 서비스 충돌 가능성이 보이면 표시

[금지] 가용성을 단정하지 마라. 반드시 등록기관에서 직접 확인해야 한다고 적어라
```

**구매 후 연결 절차 (폰에서 된다)**
1. 등록기관(가비아·후이즈 등)에서 구매
2. Firebase 콘솔 → Hosting → 사이트 `spaceos-twin` → 커스텀 도메인 추가
3. 안내받은 TXT 로 소유 확인 → A 레코드 등록 → 인증서 발급 대기
4. 연결되면 `docs/deploy-cloud-run.md` 와 `CLAUDE.md` 의 프로덕션 주소를 같이 고친다

## A6 · M1 시나리오 고정 — 점심 15분

```
D0 의 여정 지도를 "검증 가능한 시나리오"로 바꾼다.

[기준 시나리오] 소상공인 김민수(34) · 카페 창업 · 예산 1.5억 · 연남동
목표: 앱을 처음 열어 5분 안에 넷을 얻는다 (도움말 없이)
 ① 연남동은 어떤 상권인가  ② 어디가 비었나(건물·층)
 ③ 그 자리 얼마고 몇 개월에 회수되나  ④ 어떻게 알리나

[단계마다 적을 것]
 1. 사용자의 조작 (탭/클릭/입력) 한 줄
 2. 화면이 그 순간 보여줘야 하는 것 한 줄
 3. 이 단계가 실패했다고 판정하는 조건 한 줄 (예: "3초 안에 안 뜨면 실패")
 4. 다음 단계로 가는 길이 화면에 있는가 — 없으면 무엇을 만들어야 하나

[통과 조건 6개를 각 단계에 배분한다]
 C1 뒤로가기 없이 완주   C2 결론이 스크롤 없이 보임   C3 콘솔 에러 0
 C4 지도 렌더 3초 이내   C5 모든 수치가 출처를 말함   C6 3거점에서 같은 조작이 같은 자리

[현재 화면] 좌측 레일에 탭 6개 — 서울 · 거점 · Platform · Page · Posting · Program
[금지] 없는 기능을 전제하지 마라. 위 6개 탭 안에서만 시나리오를 짠다
```

---

# B군 — 클라우드 세션 지시 (claude.ai/code → PR)

> 각 프롬프트는 **대상 파일 · 입력 근거 · 통과 조건 · 금지** 넷을 채웠다.
> 하나라도 못 채우는 작업은 클라우드로 내보내지 않는다.

## B1 · D5-0 Tailwind 죽은 설정 제거

```
apps/frontend 의 죽은 Tailwind 설정을 걷어낸다. 순수 정리 작업이다.

[확인부터] tailwindcss 는 설치돼 있지 않고 소스에 @tailwind 지시문도 0개다.
tailwind.config.ts 만 토큰 1:1 매핑을 들고 남아 있고 첫 줄이
"// TODO: tailwindcss 설치 후 활성화" 다. 이 사실을 직접 확인하고 먼저 보고하라.

[대상 파일]
 삭제: apps/frontend/tailwind.config.ts
 문서 수정(전부 tailwind 를 언급한다):
   docs/feature-design-system.md · design/README.md
   docs/DESIGN-VIBE-PROMPTS.md · SpaceOS_PPPP_Design_Vibe_Coding_Guide.md
 → "토큰 → Tailwind 매핑" 서술을 지우고 동기화 규칙을 세 곳으로 고친다:
   design/tokens/tokens.json ⇄ apps/frontend/src/design/tokens/*.ts ⇄ src/styles/tokens.css

[같이 확인만] package.json 의 d3 · plotly.js-dist-min 은 src/ 어디에서도 import 되지
않는 것으로 보인다. 사실인지 직접 확인해 보고하되 이번 커밋에서 지우지는 마라.

[통과 조건] cd apps/frontend && npm run build 통과. 화면 동작 변화 0
[금지]
 - tailwindcss 를 설치하지 마라. 지우는 작업이지 살리는 작업이 아니다
 - CSS 변수 체계를 건드리지 마라 (var() 가 이미 202곳에 서 있다)
```

## B2 · D5-1 Pretendard 실배치 + 타입스케일

```
Pretendard 를 실제로 배치하고 타입스케일을 고정한다.

[문제] src/styles/tokens.css 가 --font-sans: "Pretendard" 를 선언하는데
apps/frontend/public/fonts/ 디렉터리가 없다 → 전 화면이 조용히 system-ui 로 떨어진다.
파일 상단의 "TODO: Pretendard 폰트 public/fonts 에 배치" 가 그대로 남아 있다.

[대상 파일]
 apps/frontend/public/fonts/            (신규)
 apps/frontend/src/styles/tokens.css
 apps/frontend/src/design/tokens/typography.ts
 design/tokens/tokens.json              (동기화)

[할 일]
 1. npm 패키지 pretendard 에서 woff2(Regular 400 · Bold 700)를 public/fonts/ 로 복사한다.
    서브셋 빌드가 있으면 그쪽을 쓴다 — 용량이 얼마인지 보고하라
 2. 타입스케일 5단을 tokens.css 에 CSS 변수로 고정한다.
    본문 15px · 줄간격 1.5 를 지킨다(프로젝트 한글 가독성 규칙)
 3. typography.ts 와 tokens.json 을 같은 값으로 맞춘다
 4. tokens.css 의 해당 TODO 주석을 지운다

[통과 조건]
 - ls apps/frontend/public/fonts 에 woff2 2개 이상
 - npm run build 통과
 - 스케일 밖의 font-size 가 몇 개 남았는지 세어 보고 (이번에 다 고칠 필요는 없다)

[금지]
 - Google Fonts 등 외부 CDN 링크 — 폰트는 자체 호스팅한다
 - Tailwind 를 설치하지 마라
```

## B3 · D5-2 여백 토큰 일괄 치환 ★클라우드에 가장 잘 맞는 작업

```
간격(spacing) 토큰을 만들고 하드코딩된 값을 치환한다. 순수 리팩터다.

[문제] tokens.css 에 spacing 토큰이 아예 없다(radius·shadow 만 있다).
그래서 CSS 가 색·간격을 직접 적는다 — 하드코딩 hex 558 vs var() 202 (채택률 27%).

[대상 파일 — 하드코딩이 많은 순서. 괄호는 현재 hex/var 수]
 src/pages/PlatformConsole.css    (107 / 70)
 src/pages/PageDashboard.css      ( 96 / 65)
 src/pages/ProgramStudio.css      ( 80 / 27)
 src/pages/PostingConsole.css     ( 63 / 21)
 src/pages/HubExplorer.css        ( 50 / 43)
 src/pages/MapShell.css           ( 47 / 41)
 src/pages/SeoulDashboard.css     ( 16 / 19)
 src/components/BuildingViewer.css(  8 /  0)
 src/App.css (11/8) · src/components/MapHost.css (7/7)

[할 일]
 1. --sp-1 ~ --sp-8 (4·8·12·16·24·32·48·64px)을 tokens.css 에 추가한다
 2. 위 파일들의 padding/margin/gap 을 토큰으로 치환한다.
    4px 배수에 안 맞는 값은 임의로 반올림하지 말고 목록으로 보고하라
 3. 하드코딩 hex 중 tokens.css 에 이미 대응 변수가 있는 것만 var() 로 바꾼다.
    대응이 없는 색은 그대로 두고 목록으로 보고하라 — 색 축은 D5-3 에서 정한다

[통과 조건]
 - npm run build 통과
 - 아래 두 숫자를 작업 전/후로 세어 보고할 것
     grep -oE "#[0-9a-fA-F]{3,8}" src/pages/*.css src/components/*.css src/App.css | wc -l
        → 558 에서 200 이하로
     grep -o "var(--" src/pages/*.css src/components/*.css src/App.css | wc -l
        → 증가해야 한다
 - 레이아웃 변화 0. 픽셀이 움직였다면 실패다

[금지]
 - .tsx 안의 인라인 스타일과 지도 오버레이 색(MapShell.tsx 의 fillColor 등)은 건드리지 마라.
   SDK 가 인라인으로 그리는 자리라 CSS 변수가 닿지 않는다
 - 새 색을 만들지 마라
 - Tailwind 를 설치하지 마라
```

## B4 · D5-3 PPPP 4트랙 색 축

```
PPPP 4트랙을 색으로 구분할 수 있게 토큰 축을 넓힌다.

[문제] 지금 색 축이 2개뿐이다 — --naver-green #03C75A · --brand #0EA5B7.
그래서 좌측 레일·화면 헤더·지도 범례가 "지금 어느 트랙인지"를 색으로 말하지 못한다.

[제약 — 어기면 네이버 연동 디자인 규칙 위반]
 1. #03C75A 는 네이버 연동 맥락에만(길찾기·네이버페이). 트랙 색으로 쓰지 마라
 2. #0EA5B7 brand teal 은 앱 전체 주색으로 남긴다.
    4트랙 중 하나에 배정하면 나머지 셋이 종속돼 보인다
 3. 4트랙 색은 teal 보다 채도가 낮아야 한다 — 주색을 이기면 안 된다
 4. 공실 상태색과 혼동되면 안 된다. MapShell.tsx 의 STATUS(full·partial·high·empty)를
    먼저 읽고 충돌하지 않는 색을 고른다

[대상 파일]
 apps/frontend/src/styles/tokens.css
 apps/frontend/src/design/tokens/colors.ts
 design/tokens/tokens.json
 apps/frontend/src/App.tsx  (레일 활성 상태)

[통과 조건]
 - 4트랙 색이 세 파일에 같은 값으로 있다
 - 각 색이 배경 #F4F7FB 와 표면 #FFFFFF 위에서 WCAG AA(4.5:1)를 넘는지 계산해 표로 보고
 - npm run build 통과

[금지]
 - 화면에 색을 실제로 칠하는 작업은 이번에 하지 마라. 토큰과 레일까지다
   (화면 적용은 D5-4·D5-6 에서 컴포넌트와 함께)
```

## B5 · D5-4 design/components 실투입

```
만들어 두고 한 번도 쓰이지 않은 디자인 컴포넌트를 실제 화면에 넣는다. 순수 리팩터다.

[문제] apps/frontend/src/design/components/ 에 6개가 있는데 페이지가 import 하는 것은 0개다.
토큰 colors 만 3개 파일(HubExplorer·MapShell·PageDashboard)에서 쓴다.
  Button.tsx · Card.tsx · BottomSheet.tsx · MapMarkerPin.tsx · VacancyLegend.tsx · NaverPayButton.tsx

[할 일 — 이번 범위는 셋]
 1. 먼저 각 컴포넌트의 실제 props 를 읽고, 지금 화면 마크업과 얼마나 어긋나는지 보고하라.
    어긋남이 크면 컴포넌트를 화면에 맞추지 말고 그 사실을 적고 멈춰라
 2. Card 를 PlatformConsole · PostingConsole · ProgramStudio 의 반복 블록에 넣는다
 3. Button 을 위 세 화면의 액션 버튼에 넣는다
 4. BottomSheet 를 MapShell 정보 패널에 넣을 수 있는지 검토만 한다.
    지도 생명주기를 건드려야 한다면 하지 말고 이유를 적어라

[통과 조건]
 - grep -rn "@/design/components" src/pages/ 가 3개 화면 이상에서 잡힌다
 - npm run build 통과 (tsc -b 포함)
 - 화면 동작 변화 0. 버튼이 하던 일이 바뀌었으면 실패다

[금지]
 - MapMarkerPin 은 건드리지 마라 (D5-5 지도 작업에서 쓴다)
 - 컴포넌트의 공개 props 를 바꾸지 마라. 화면 쪽을 맞춘다
 - 새 컴포넌트를 만들지 마라
```

## B6 · D5-6 글자 정리

```
화면당 글자 수를 줄인다. "결론 1줄 + 근거 3줄" 이 규칙이다.

[문제] 한 화면이 결론·근거·원자료를 동시에 편다.
 PageDashboard.tsx 919줄 · PlatformConsole.tsx 805줄 · ProgramStudio.tsx 611줄

[규칙]
 - 화면 맨 위에 그 화면의 결론 한 문장 — 스크롤 없이 보여야 한다
 - 그 아래 근거 3줄
 - 나머지는 접거나(<details>) 상세 패널로 민다. 지우지 마라
 - 각 탭의 헤드라인은 그 탭이 답하는 질문이다
     Platform  이 입지·상권은 어떤 플랫폼인가
     Page      이 platform 안에 어떤 page 가 만들어져야 하는가
     Posting   어떤 가격대의 page 가 posting 되어야 하는가
     Program   posting 한 page 를 어떤 홍보 program 으로 돌릴 것인가

[대상 — 이번엔 둘만]
 apps/frontend/src/pages/PlatformConsole.tsx
 apps/frontend/src/pages/ProgramStudio.tsx

[통과 조건]
 - npm run build 통과
 - 화면별 텍스트 노드 수를 작업 전/후로 세어 보고 (목표 −50%)
 - 데이터를 화면에서 지우지 않았음을 확인 — 접힌 것과 지운 것은 다르다

[금지]
 - PageDashboard.tsx 는 건드리지 마라. #board 해시로 밀려난 화면이고
   층별 매물·입점·마케팅 세 섹션의 이사가 아직 안 끝났다
 - 수치를 반올림하거나 요약해 정확도를 낮추지 마라
 - 출처 표기("R-ONE 앵커" · "TRDAR 상권 단위" 등)를 접지 마라 — 그건 근거다
```

## B7 · M2 앵커 격차 probe ★이미 있는 것부터 읽는다

```
R-ONE 앵커 격차를 실측으로 해명한다. 새로 만들기 전에 이미 있는 것부터 읽는다.

[먼저 읽을 것 — 이게 핵심이다]
data/gold/<hub>/calibration.json 에 rone_aligned 필드가 이미 있다. 연남동 기준:
  rone_aligned.mid = { vacancy_area_pct 20.8, anchor_pct 5.0, gap_pp 15.8, buildings 836 }
  small · mall 도 따로 있고, note 가 대상 정의를 적어 두었다 —
  "mid = 중대형 앵커 대조 대상(일반건축물·상가 주용도·3층 이상 또는 330㎡ 초과),
   mall = 집합건축물(중대형 앵커 대조 금지 — R-ONE 집합상가는 별도 계열)"
그런데 note 는 (2026-08-01) 이고 gold 재빌드는 2026-09-04 다 — 이 필드가 낡았을 수 있다.

[답할 것]
 1. rone_aligned 는 언제 어느 파이프라인에서 계산되는가 — 코드를 찾아 보고하라
 2. 현재 대표 공실률(연남 12.5% · 신촌 17.2% · 홍대 15.0%)과 rone_aligned.mid 는 어떻게
    이어지는가. chain_status 의 격차(+7.5 / +5.52 / +6.9%p)와 calibration 의 gap_pp 가
    다르다면 왜 다른가
 3. 가설 검증 — "R-ONE 은 중대형 표본, 우리는 전수라 격차가 난다."
    우리 표본을 R-ONE 대상 규모로 좁히면 격차가 실제로 줄어드는가. 3거점 숫자로 답하라
 4. 화면에 무엇을 그려야 하는가. 두 수를 같이 보여준다면 라벨을 뭐라고 쓸 것인가

[대상 거점] yeonnam · sinchon · hongdae
[산출물] docs/finding-anchor-gap-2026-09.md — .claude/skills/probe-first 양식을 따른다
[통과 조건] 문서의 모든 수치가 저장소 파일 경로로 출처를 댄다 + 재현 명령을 같이 적는다

[금지]
 - 원천 재수집을 시도하지 마라. 클라우드 세션에는 bronze/silver 가 없다(.gitignore).
   data/gold 만으로 갈 수 있는 데까지 가고, 막히면 "데스크톱 필요"라고 적어라
 - 코드를 고치지 마라. 이번은 판정만이다
 - 격차를 작아 보이게 만들지 마라. 크면 큰 대로 적는다
```

## B8 · M5a 66거점 화면 루프 스크립트

```
66거점 화면 회귀 검사 스크립트를 만든다. 이번엔 코드까지만 — 실행은 데스크톱이다.

[왜] 지금 화면 검증은 /verify 가 사람 손으로 한 거점씩 여는 방식이다.
거점 66 × 탭 4 = 264조합을 손으로 못 돈다.

[만들 것] scripts/screen_loop.py
 입력: app.services.districts.PAGES 를 런타임에 읽어 거점 목록을 얻는다
       (apps/backend/app/services/districts.py:54 — DISTRICTS + measured_pages.MEASURED)
 루프: 거점마다 4탭(Platform·Page·Posting·Program)을 열고
   [S1] 콘솔 에러 0 · pageerror 0
   [S2] 지도 캔버스 visible + SDK 자식 ≥ 1
   [S3] 공실 마커/폴리곤 수 > 0 · 결론 문장 노드 존재
   [S4] 초기 렌더 3초 이내
 출력: reports/screen_loop.json + 실패한 거점만 스크린샷

[설계 제약 — 전례에서 나온 것이라 협상 대상이 아니다]
 1. @playwright/test(Node)를 새로 깔지 마라. Python playwright 가 2026-07-24 부터 있고
    /verify 가 그걸 쓴다. 두 벌을 두면 검증 기준이 갈린다
 2. 거점 slug 를 하드코딩하지 마라 — docs/prompt-playwright-e2e.md 가 만료된 이유가
    slug 13개를 박아 둔 것이다
 3. 셀렉터를 좁게 써라. .b-name 은 목록행과 상세패널 양쪽에 있어
    querySelector('.b-name') 은 목록 첫 행을 집는다 → .b-detail .b-name
 4. 체크포인트로 재개 가능해야 한다. 264조합은 한 번에 안 끝날 수 있다
 5. 로그를 파일로 쓸 때 PYTHONIOENCODING=utf-8 — Windows cp949 에 em dash 가 없어 죽는다

[먼저 읽을 것] .claude/skills/verify · .claude/skills/autorun
[통과 조건]
 - --hubs yeonnam,sinchon,hongdae 로 3거점만 도는 옵션이 있다
 - 없는 셀렉터를 넣었을 때 스크립트가 그걸 실패로 잡는다 (자기 검사)
 - /verify 절차와 겹치는 부분은 재사용한다

[금지]
 - 실행하지 마라. 클라우드에는 네이버 지도 SDK 키도 로컬 서버도 없다. 코드와 테스트까지다
 - pppp_status.py 에 게이트를 추가하지 마라. 게이트 24개 중 이미 선언이 8개다 —
   측정이 실제로 도는 걸 확인한 뒤 별도로 판단한다
```

---

## 부록. 하루 운영 리듬

| 시각 | 하는 일 |
|---|---|
| 전날 밤 | `git status --short` 확인 → `git push origin main` (백그라운드) |
| 출근길 5분 | B군 프롬프트 하나를 클라우드 세션에 건다 |
| 점심 15분 | A1 · A4-a · A5 · A6 중 하나 (핀터레스트 캡처 첨부는 여기가 최적) |
| 오후 5분 | 세션 결과 확인 → PR 머지 (머지하면 Cloud Run 자동 배포까지 간다) |
| 퇴근길 30분 | A2 · A3 (긴 문서 작업) |
| 저녁·주말 데스크톱 | D5-5 red-dot · D5-7 4P 플로우 · M4 3거점 검증 · M5b 루프 실행 · M6 데모 |

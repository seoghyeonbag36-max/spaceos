# 디자인 바이브 코딩 프롬프트 모음 (Claude Code 복붙용)

> SpaceOS 폴더에서 `claude` 실행 후 붙여넣는다. 원칙: 토큰 먼저 → 컴포넌트 → 화면 → Storybook.
> 모든 디자인은 docs/feature-design-system.md 의 네이버 연동 규칙을 따른다.

## 0. 디자인 시스템 부트스트랩
```
docs/feature-design-system.md 와 design/README.md, design/brand/naver-brand.md 를 읽어줘.
apps/frontend 에 Tailwind+Storybook 을 설치하고, src/design/tokens 의 색·타이포·간격 토큰을
tailwind.config.ts 에 연결해줘. Pretendard 폰트를 public/fonts 에 넣고 tokens.css 의 @font-face 를 연결.
네이버 그린은 연동 맥락에만, brand teal 은 SpaceOS 고유 기능에만 쓰는 규칙을 주석으로 남겨줘.
```

## 1. Platform 화면 — 상권 첫 스킨십(디지털 프로필)
```
상권을 '처음 만나는' 화면을 만들어줘. 네이버 지도 위에 상권 카드(분위기 키워드·감성지수·
주고객)를 brand teal 강조로 보여주고, 길찾기 같은 네이버 연동 버튼만 Button variant="naver"(그린) 사용.
Card·BottomSheet 컴포넌트를 재사용하고, 한글 가독성(Pretendard 15px/1.5)·대비 AA 를 지켜줘.
스토리(Platform.stories.tsx)도 추가.
```

## 2. Page 화면 — 공실 히트맵 + 3D/지도
```
네이버 지도 위에 공실 위험도를 MapMarkerPin(vacancy 색계열)으로 찍고, VacancyLegend 범례를
우하단에 고정해줘. 건물 클릭 시 BottomSheet 로 3년 변천사·폐업 사유·추천 업종 적합도를 보여줘.
지도 컨트롤과 충돌하지 않게 안전영역(safe-area)·여백 토큰을 지키고, 마커 대비를 확인해줘.
```

## 3. Posting 화면 — 입점 솔루션 카드(3 tier)
```
고급화/가성비/기능중심 3개를 나란히 비교하는 카드 UI 를 Card 로 만들어줘.
tier 헤더는 각기 다른 톤(고급화=ink, 가성비=brand, 기능중심=muted)으로 구분하고,
ROI·손익분기를 큰 숫자(display)로 강조. 결제로 이어지는 단건 리포트 버튼 옆에는
NaverPayButton(공식 슬롯)을 배치하되 버튼 자체는 변형하지 말 것.
```

## 4. Program 화면 — 마케팅/행사 자동화
```
LLM 이 생성한 마케팅안/행사안을 검수·편집하는 에디터 화면을 만들어줘.
좌측 생성 결과 리스트(Card), 우측 Rich Text 편집 영역. 액션 버튼은 brand teal,
'네이버 예약/지도 등록' 등 네이버 연동 버튼만 그린. Humanistic Authority 톤(공감·중립)을
마이크로카피에 반영해줘.
```

## 5. 네이버 연동 컴포넌트 — 지도/페이
```
design/assets/naverpay 의 공식 버튼 에셋으로 NaverPayButton 을 실제 공식 버튼으로 교체해줘
(임의 색·문구 변경 금지). 네이버 지도는 src/lib/naverMap.ts 와 연결해 마커/바텀시트가
지도 위에 자연스럽게 떠 있도록 z-index·여백을 맞춰줘. 결제 플로우는 backend payments.py 와 연동.
```

## 6. 품질 — 접근성·일관성 검수
```
Storybook 의 a11y 애드온으로 모든 컴포넌트 대비(AA)·포커스 링을 점검하고,
토큰을 벗어난 하드코딩 색/폰트가 있으면 토큰으로 치환해줘. 변경은 Before/After 캡처와 함께 PR.
```

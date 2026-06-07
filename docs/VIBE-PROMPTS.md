# 바이브 코딩 프롬프트 모음 (Claude Code 복붙용)

> 각 블록을 SpaceOS 폴더에서 `claude` 실행 후 그대로 붙여넣는다.
> 원칙: ① 작은 단위로 요청 ② 생성 후 실행/테스트로 검증 ③ git 커밋. (CLAUDE.md 가 컨텍스트로 자동 로드됨)

## 0. 공통 시작
```
이 저장소는 SpaceOS 모노레포다. CLAUDE.md 와 docs/ 를 먼저 읽고,
오늘 작업 범위를 3~5개 작은 작업으로 쪼개 제안해줘. 내가 승인하면 하나씩 진행한다.
```

## 1. Platform (상권 디지털 프로필 + AI 추천 엔진)
```
docs/10-platform-redefinition.md, feature-platform.md 를 읽어줘.
data/silver 의 상권 리뷰·채널·인구 데이터를 입력으로 받아
'상권 디지털 프로필'(감성지수, 주고객 연령/소득, 채널별 노출, 분위기 키워드 5개)을
산출하는 서비스를 apps/backend/app/services/platform_profile.py 에 만들어줘.
ml/models/lstm 의 공실 예측, ml/models/gnn 의 업종 추천을 호출하는
/api/v1/ai 라우터와 연결하고, 결과는 data/gold 의 platform_profile 테이블 스키마로 저장.
더미 데이터 지점에는 TODO 로 실제 연동 위치를 표시해줘.
```

## 2. Page (공실 히트맵 + 3D/지도 시각화)
```
feature-page.md 와 feature-naver-integration.md 를 읽어줘.
apps/frontend 에서 네이버 지도(naverMap.ts)를 상권 중심에 띄우고,
/api/v1/heatmap/{district_id} GeoJSON 으로 공실 위험도를 색상 히트맵으로 표시하는
DistrictMap 컴포넌트를 만들어줘. 건물 클릭 시 과거 3년 업종 변천사 + AI 요약 폐업 사유 +
추천 업종 적합도를 사이드 패널에 보여줘. 색상 규칙(저위험 초록~고위험 빨강)을 상수로 분리.
```

## 3. Posting (입점 솔루션 카드 — 3 tier)
```
feature-posting.md 를 읽어줘.
공실 building_id 와 industry_type, strategy(고급화/가성비/기능중심)를 입력받아
예상 매출(LSTM 재사용), 초기 투자비, 월 고정비, ROI(회수 기간), 손익분기 시점을 계산하는
apps/backend/app/services/posting.py 와 /api/v1/ai/simulate-revenue 를 만들어줘.
3개 tier를 한 번에 비교하는 '입점 솔루션 카드' 응답 스키마로 반환.
```

## 4. Program (LLM 마케팅 자동화 + 행사 추천)
```
feature-program.md 를 읽어줘.
상권 프로필을 입력으로 (a)온라인 퍼포먼스 마케팅(채널·예산·크리에이티브)
(b)오프라인 행사(축제·플리마켓·공연) 기획안을 LLM 으로 자동 생성하는
apps/backend/app/services/llm.py + events.py + /api/v1/marketing/generate-content 를 만들어줘.
Humanistic Authority(균형·공생·공감) 가이드를 시스템 프롬프트에 반영.
```

## 5. 네이버 연동 (지도 + 페이)
```
feature-naver-integration.md 를 읽어줘.
1) 백엔드 naver_geo.py 의 geocode 로 data/bronze 상가 주소를 좌표로 정규화해
   data/silver 에 parquet 으로 저장하는 스크립트를 data/pipelines 에 만들어줘.
2) payments.py 의 reserve/apply 스텁을 실제 네이버페이 결제형 플로우로 채워줘(.env 키 사용).
```

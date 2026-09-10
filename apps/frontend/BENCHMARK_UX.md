# 벤치마킹 UX 적용 기록

## 재사용 코드와 화면 참고의 구분

- 실제 재사용 코드: Airbnb의 `@visx/shape@4.0.0`에서 `Bar` 컴포넌트. `PlatformComparison.tsx`의 서버 `distinct.delta_pp` 비교 차트에서 사용한다.
- 출처: https://github.com/airbnb/visx · MIT 라이선스. 배포 고지는 `public/THIRD_PARTY_NOTICES.txt`에 포함한다.
- 나머지 제품의 배포 JS/CSS·브랜드 자산은 복사하지 않았다. 화면 구성과 상호작용은 아래 공개 자료를 참고해 기존 React·CSS 토큰으로 구현했다.
- Shopify Polaris와 Esri Calcite는 각각 사용 조건이 있으므로 의존성으로 추가하지 않았다.

## 참고 자료와 적용

| 참고 서비스 | 공개 자료 | 적용 |
|---|---|---|
| 네이버 지도 | https://help.naver.com/service/5637/contents/8249?lang=ko&osType=PC | 기존 단일 지도·층 스택·거리뷰 유지, 후보 선택 맥락 보존 |
| 네모 | https://play.google.com/store/apps/details?hl=ko&id=kr.co.sugarhill.nemoapp | 건물 카드 → 입점 검토 동선 |
| 부동산플래닛 | https://www.bdsplanet.com/map/realprice_map.ytp?ubt_mode=explore_basic | 상태·검색 필터, 조건 초기화, 빈 결과 안내 |
| 소상공인365 | https://www.data.go.kr/data/15143517/fileData.do?recommendDataYn=Y | 조건과 근거를 결과 가까이 표시 |
| 서울시 상권분석 | https://golmok.seoul.go.kr/introduce.do | 같은 상권의 후보 조건·근거 비교 |
| 캐시노트 | https://cashnote.kr/ | 초기 투자·월 비용·회수기간의 금액 중심 위계 |
| 스티비 | https://help.stibee.com/email/send/status | 초안·편집·복사 성공/실패의 실제 상태 구분 |
| LoopNet | https://www.loopnet.com/search/commercial-real-estate/new-york-ny/for-lease/ | 지도와 목록의 필터 연동, 후보 비교 |
| Placer.ai | https://www.placer.ai/guides/site-selection-guide | 비교표와 공통 눈금 차트 |
| Esri Business Analyst | https://doc.arcgis.com/en/business-analyst/web/suitability-analysis.htm | 후보 선택 → 비교 → 근거 검토 |
| Airbnb | https://www.airbnb.com/help/article/1236 | 후보 저장·선택 이유 메모 |
| Shopify | https://www.shopify.com/tools/profit-margin-calculator | 기본 입력·세부 전략 분리, 계산에 사용한 입력 표시 |
| Buffer | https://buffer.com/publish | 채널별 초안 선택·편집·미리보기 |

## 보존한 계약

- `vacancy_source`·`inputs_source`, 앵커·집계 예외, 기존 산식과 추천 기준은 그대로다.
- Page의 건물 ID는 파이프라인 `build_vacant_units.py`의 `vu-{building_id}` 규칙을 따른 Posting 응답 유닛과 정확하게 대조한다. 일치하지 않으면 자동 선택·계산하지 않는다. 층 표본으로 ROI를 계산하지 않는다.
- 후보·메모·초안 편집은 React 메모리에서만 유지한다. 새로고침 후 유지되는 서버 저장이나 브라우저 저장소 기능이 아니다.
- Program의 편집본에는 생성 원본의 HA 검증을 적용했다고 표시하지 않는다. 예약·발행·성과는 실제 연동 API가 없어 추가하지 않았다.
- Platform 비교는 동일 상권에서 선택한 후보만 사용하며, 서버 값·출처·정밀도·결측을 유지한다. 점수는 입점 성공 확률이 아니다.

## 검증

`npm run build`, `npm run lint`, `npm run test`로 확인한다. 지도 SDK·API는 테스트 픽스처이며 실제 지도·서버·LLM 호출 검증과 구분한다.

- `App.test.tsx`: Page→Posting 정확 인계, 불일치 차단, 탭 왕복 후 후보·지도 보존.
- `MapShell.test.tsx`: 지도/목록 필터, 후보·메모·출처, 거점 전환 및 오버레이 정리.
- `PlatformConsole.test.tsx`: 후보 최대 3개, 거점 전환 초기화, 원값·음수·결측·출처 비교.
- `PostingConsole.test.tsx` 및 `PostingConsole.flow.test.tsx`: API 배선, 계산 입력·응답 대조, 수정 전후 비교 및 지연 응답 무효화.
- `ProgramStudio.test.tsx`: 초안 편집·미리보기·복사·원본 복원, HA·출처·온보딩 동의·지연 응답.

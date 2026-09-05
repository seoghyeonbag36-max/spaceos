# Glossary — SpaceOS

SpaceOS 프로젝트 전체에서 사용되는 용어·약어·고유명사 사전.

## 핵심 프레임워크
| 용어 | 의미 | 맥락 |
|------|------|------|
| **SpaceOS** | 프로젝트명 — 물리적 상권의 디지털 트윈 SaaS | "Place ▶ Platform" 가설 |
| **PPPP** | Platform·Page·Posting·Program | 디지털 4P 전환 프레임워크. **2026-09-05 부터 전통 4P 와 1:1** — 종전엔 Page 가 Product/Price 를 겸하고 Posting·Program 이 Promotion 을 나눠 가졌다 |
| **Platform** | **Place ▶ Platform** | 이 입지·상권은 어떤 플랫폼인가 — 물리적 공간을 SNS·디지털 관점의 공간/플랫폼으로 읽는다. 상권 AI 추천 엔진 |
| **Page** | **Product ▶ Page** | 이 platform 안에 어떤 page 가 만들어져야 하는가(제품이 아니라 page 다). 공실 히트맵 + 층별 매물 목록 + 네이버 거리뷰 |
| **Posting** | **Price ▶ Posting** | 어떤 **가격대**의 page 가 이 platform 에 posting 되어야 하는가. 입점 솔루션 (고급화/가성비/기능중심 3-Tier + 회수기간) |
| **Program** | **Promotion ▶ Program** | posting 한 page 를 온·오프라인에서 어떤 홍보 program 으로 돌릴 것인가. 마케팅 자동화 |
| **Humanistic Authority** | 균형(Balance)·공생(Symbiosis)·공감(Empathy) | 인문적 권위 3대 지표 |

## 기술 용어
| 용어 | 의미 | 맥락 |
|------|------|------|
| **GNN** | Graph Neural Network | 업종 간 시너지/잠식 분석, Top-3 정확도 70%+ |
| **LSTM** | Long Short-Term Memory | 시계열 매출·공실률 예측 |
| **PostGIS** | PostgreSQL 공간 확장 | 건물·공실 GIS 데이터 |
| ~~**Three.js / R3F**~~ | ~~3D 렌더링 라이브러리~~ | **2026-09-05 제거.** 3D 트윈이 그리던 절차적 박스는 실측 형상이 아니라 층 상태를 색으로 칠한 것뿐이라 2D 층 스택으로 갈았다(번들 832KB→4KB). 이름이 나오면 이력이다 |
| **네이버 지도** | 지도 + **거리뷰 파노라마** SDK (`lib/naverMap.ts`) | 유일한 베이스맵. Mapbox GL 은 2026-08-25, Three.js 는 2026-09-05 제거 |
| **2D 층 스택** | 건물 상세의 층 표현 (`components/BuildingViewer.tsx`) | 층 근거(`com_floors`·`occ_floors`)를 가진 건물의 **몇 층이 비었나**를 색으로 그린다. 3D 트윈의 후신 — 3D 를 없앤 것이지 층 표현을 없앤 것이 아니다 |
| **거리뷰(파노라마)** | 네이버 거리뷰 (`renderStreetView`) | "가보지 않고 그 자리의 성격을 본다". ⚠ **촬영 시점이 과거라 공실 판정의 근거가 아니다** — 촬영일을 반드시 함께 그린다 |
| **`no_com_floor`** | 층별개요를 받았고 지상 상업층이 0 인 건물 | 결손이 아니라 **판정**이라 커버리지 분모에서 뺀다(2026-09-05). 이걸 결손으로 세면 회수 불가능한 수집 과제가 생긴다 |
| **구역(Zone)** | 거점 안의 **행정동** 단위 구획 (`gold/{거점}/district_zones.json`) | 2026-09-05 에 손으로 적은 감성 구역 324개를 대체. 점포·건물·공실은 실측, **감성은 null**(좌표 가진 점포 리뷰 채널 부재). 구역 수는 거점이 걸친 행정동 수라 1~11개로 다르다 |
| **Bronze/Silver/Gold** | 데이터 레이크 3계층 | 원본 → 정제 → 분석용 |
| **MLflow** | ML 모델 버전 관리 | 학습 → 등록 → 추론 자동화 |
| ~~**GLB / glTF**~~ | ~~3D 모델 포맷~~ | **미사용.** 3D 폐기(2026-09-05)로 소비자가 없다. `/buildings/{id}/model` stub 이 경로 문자열만 돌려주는데 부르는 곳이 없다 |
| **OSM** | OpenStreetMap | 건물 윤곽·층수 데이터 소스 |
| **ETL/ELT** | Extract-Transform-Load | Airflow DAG으로 자동화 |

## 바이브 코딩 용어
| 용어 | 의미 |
|------|------|
| **바이브 코딩 (Vibe Coding)** | 자연어 PRD → AI 코드 생성 → 검증 사이클 |
| **PRD-driven** | Product Requirements Document 먼저 작성 후 AI에 입력 |
| **Cursor Composer** | 멀티파일 동시 편집 모드 |
| **Cursor Agent Mode** | 장기 컨텍스트·자율 작업 모드 |
| **Claude Code** | Anthropic CLI 기반 코딩 에이전트 |
| **.cursorrules** | Cursor 프로젝트 컨텍스트 파일 |
| **CLAUDE.md** | Claude Code 메모리 파일 |
| **프롬프트 체이닝** | 다단계 LLM 호출 워크플로우 (LangChain) |
| **Self-healing loop** | 에러 → AI 자동 수정 반복 |
| **AI 생성률** | 전체 코드 중 AI가 1차 생성한 비율 (목표 70%+) |

## 비즈니스 용어
| 용어 | 의미 |
|------|------|
| **DaaS** | Data as a Service — B2B SaaS 구독 (월 500만원~) |
| **CAC** | Customer Acquisition Cost — 약 200만원 (B2B) |
| **LTV** | Lifetime Value — 약 6,000만원 |
| **LTV/CAC** | 약 30배 |
| **BEP** | Break-Even Point — 18개월차 (2028년 하반기) |
| **TAM** | Total Addressable Market — 상업용 부동산 34조 |
| **SAM** | Serviceable Available Market — 1.2조 (프롭테크) |
| **SOM** | Serviceable Obtainable Market — 1,500억 |
| **PMF** | Product-Market Fit |
| **NPS** | Net Promoter Score |
| **Sean Ellis Test** | Must-have 40%+ 측정 (PMF 검증) |
| **MVP** | Minimum Viable Product |
| **IR** | Investor Relations (투자유치 자료) |
| **Pre-Seed/Seed/Pre-A** | 투자 라운드 단계 |
| **LOI** | Letter of Intent (도입의향서) |
| **예비창업자패키지** | 정부 창업 지원사업 |

## 고객 페르소나
| 약칭 | 풀네임 | 설명 |
|------|--------|------|
| **프랜차이즈 본사** | 신사업/출점 담당 | 교촌·BBQ·스타벅스 — 신규점포 폐점 리스크 줄이기 |
| **자산운용사 MD** | Merchandising Director | 이지스·코람코 — 공실 관리·MD 구성 |
| **지자체 상권 활성화** | 일자리경제과 | 강남구청·마포구청 — 예산 대비 행사 효과 |
| **예비창업자** | 소상공인 | 망하지 않을 자리 찾기 (B2C) |

## 거점 상권
| 약칭 | 풀네임 | 우선순위 |
|------|--------|---------|
| **가로수길** | 서울 강남구 신사동 가로수길 | 1순위 — 건물 단위 공실 PoC 거점 |
| **홍대·연남동** | 서울 마포구 홍대·연남동 | 1순위 후보 — SNS 데이터 압도적 |
| **성수동** | 서울 성동구 성수동 | 2순위 — 트렌드 검증 테스트베드 |

## Exit 타겟
| 우선순위 | 회사 | 인수 동기 |
|---------|------|---------|
| 1순위 | 네이버·카카오 | 지역 기반 광고·커머스 확장 |
| 2순위 | 직방·다방 | 상업용 부동산 시장 확대 |
| 3순위 | 금융권 | 부동산 담보 가치 평가 |
| 보조 | IPO | 시장 상황 따라 |

## 데이터 소스
| 약칭 | 풀네임 |
|------|--------|
| **공공데이터포털** | data.go.kr — 소상공인시장진흥공단 상가정보 |
| **네이버지도/카카오맵** | POI·리뷰·별점·사진 |
| **네이버부동산** | 상가 임대 매물 |
| **LH 임대정보** | 한국토지주택공사 임대 공시 |
| **OSM** | OpenStreetMap 건물 데이터 |
| **인스타그램 Graph API** | 해시태그·위치태그 |

## 일정·마일스톤
| 약칭 | 의미 |
|------|------|
| **M1~M6** | 6개월 로드맵 월 단위 (M1=2026-06, M6=2026-11) |
| **Phase 1** | MVP (M1~M4) |
| **Phase 2** | 확장 (M5~M10) — 광역시 5개 |
| **Phase 3** | DaaS (M11~M18) — 전국 단위 |
| **Phase 4** | Exit (M18~M24) — M&A |

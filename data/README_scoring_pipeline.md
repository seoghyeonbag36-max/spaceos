# 서울 25구 거점 선정 데이터 파이프라인

물리적 상권을 디지털 트윈으로 플랫폼화하기 위한 **첫 단계**: 서울 25개 구를 4기준(SNS·공실·지도유입·유동인구) × 2대상(B2C 방문고객·B2B 입주업체)으로 채점해 SpaceOS 진입 우선순위를 산출한다.

## 구조

```
data/
├─ config/seoul_districts.py     # 25구 코드·base 앵커·키워드·점수 밴드·tilt (SSOT)
├─ collectors/
│  ├─ living_population.py        # FOOT 유동인구 — 서울 생활인구/골목상권
│  ├─ naver_datalab.py           # MAP  지도/IT 유입 — 네이버 데이터랩/검색광고
│  └─ sns_mentions.py            # SNS  업로드 — 인스타 해시태그/네이버 블로그
├─ pipelines/
│  ├─ district_score.py          # Bronze→Silver→Gold 점수 산식
│  └─ dags/district_score_dag.py # Airflow DAG
└─ gold/seoul_district_scores.json  # 산출물(점수표)
```

## 실행 (폴백 모드 — API 키 없이 즉시 동작)

```bash
cd <repo-root>
python -m data.pipelines.district_score
```

API 키가 없으면 `config`의 프록시 앵커(中신뢰)로 점수표를 생성한다. 결과는 `data/gold/seoul_district_scores.json`에 저장되고, 콘솔에 순위표가 출력된다.

## 실측 승급 — API 키 발급

| 기준 | 출처 | 환경변수 | 발급처 |
|------|------|---------|--------|
| FOOT 유동인구 | 서울 생활인구 OpenAPI | `SEOUL_OPENAPI_KEY` | data.seoul.go.kr (인증키 신청) |
| MAP 지도/IT 유입 | 네이버 데이터랩 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | developers.naver.com |
| SNS 업로드 | 인스타 Graph API | `INSTAGRAM_ACCESS_TOKEN`, `IG_USER_ID` | developers.facebook.com (비즈니스 계정) |
| SNS (보조) | 네이버 블로그 검색 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | developers.naver.com |
| VAC 공실 | 소상공인 상가 API(보조) / 한국부동산원·쿠시먼앤드웨이크필드(권위) | `DATA_GO_KR_SERVICE_KEY` | data.go.kr |

### 실측 실행 (사용자 PC — 네트워크·키 있는 환경)

> ⚠️ 클라우드 샌드박스는 외부 API 접속이 차단되어 실측이 불가하다. 아래는 **로컬 PC**에서 실행한다.

```bash
pip install -r data/requirements.txt
cp data/.env.example data/.env      # 키 채우기 (아래 발급 절차)
python -m data.run_collection       # 각 기준 LIVE/프록시 진단 + Gold 점수표 갱신
```

`run_collection`은 기준별로 🟢 LIVE(실측) / ⚪ 프록시 폴백을 표시한다. 키가 일부만 있으면 해당 기준만 실측, 나머지는 자동 폴백한다.

### API 키 발급 절차

1. **네이버**(MAP+SNS보조, 가장 쉬움): developers.naver.com → 애플리케이션 등록 → '데이터랩(검색어트렌드)'+'검색' API 추가 → Client ID/Secret 복사.
2. **서울 생활인구**(FOOT): data.seoul.go.kr 로그인 → 인증키 신청. 이후 '자치구단위 서울생활인구(내국인)' 데이터셋 상세페이지에서 **서비스명·필드명**을 확인해 `.env`의 `SEOUL_LIVING_POP_*`에 기입(데이터셋마다 다름).
3. **소상공인 상가 API**(VAC density, 선택): data.go.kr/data/15012005/openapi.do → 활용신청 → 디코딩 인증키. `VACANCY_MODE=density`로 전환 시 사용. 미사용 시 공식 공실률 base 앵커 유지(권장).
4. **인스타 Graph API**(SNS, 선택): 비즈니스 계정+토큰 필요. 미발급 시 네이버 블로그 신호로 SNS 프록시 동작.

## 점수 산식

1. **Bronze**: 각 수집기가 구별 0~100 정규화 지표 반환.
2. **Silver**: `SCORE_BANDS`로 대상별 1~4점 변환. 공실(VAC)은 B2B에서 "많을수록 高점수"(SpaceOS가 푸는 문제), B2C에서는 상한 3으로 제한.
3. **Gold**: 대상별 합산 + 전체 합산(최대 32) → 동점은 `TILT` 연속점수로 정렬 → 순위·Phase.

Phase 1(1~5위) 즉시 진입 / Phase 2(6~12위) 확장 / Phase 3·4(13~25위) 외곽.

## Airflow 배포

```bash
cp data/pipelines/dags/district_score_dag.py $AIRFLOW_HOME/dags/
# PYTHONPATH에 repo 루트 추가 → DAG가 data.* 패키지 import
```

스케줄 @weekly. SNS는 트렌드 변화가 빨라 별도 일간 DAG 분리를 권장한다.

## 주의

- base 앵커는 1차 프록시(공개 핫플/검색 순위 + 쿠시먼앤드웨이크필드 2025 공실률). 투자/의사결정용으로는 실측 승급 필수.
- 개인정보: 통신/SNS 데이터는 비식별화 원칙·개인정보보호법 준수(집계 단위만 사용).

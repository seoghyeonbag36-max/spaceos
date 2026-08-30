# 경기 인허가 소스 — 경기데이터드림 `GENRESTRT` 로 간다 (2026-08-30)

## 0. 판정

**키 발급 완료·응답 검증 완료(2026-08-30).** 소스는 쓸 수 있다.
남은 것은 수집기 한 개이고, 거기에 **좌표계 함정이 하나** 있다(§7).
경기데이터드림 Open API `GENRESTRT`(일반음식점 현황_인허가)가 31개 시군 전체를 덮고,
필드가 서울 인허가 수집기가 쓰는 것과 같은 계열이다.

## 1. 왜 필요한가

`build_building_history` 가 `bronze/{slug}/licensing_biz.json` 을 요구한다. 없으면
건물 이력이 안 서고(`gold/{slug}/building_history.json` 미생성), `build_page_master` 의
분자 보강(`_licensed_pip`)도 못 탄다. 2026-08-30 화정·금촌이 정확히 그 상태다 —
Tier1 은 섰지만 **서울보다 분자가 얇다.**

서울은 `collectors/seoul_licensing.py` 가 서울 열린데이터광장에서 받는다. 서울 전용이다.

## 2. 죽은 길 — 실측으로 확인했다

| 경로 | 결과 |
|---|---|
| `localdata.go.kr` (구 LOCALDATA REST) | **응답 없음(타임아웃)**. 2026-04-15 병행 종료 후 폐쇄 — 저장소 주석과 일치 |
| 전국일반음식점표준데이터 파일 (`file.localdata.go.kr/file/general_restaurants/info`) | **HTTP 403** (UA 위장해도 동일) |
| data.go.kr `15058548 경기도_식품접객업소 현황` | **LINK 형** — 결국 경기데이터드림으로 넘긴다 |
| data.go.kr `15064977 식약처 인허가 업소 정보` | **LINK 형** — 식품안전나라 별도 키 필요 |

즉 **기존 `DATA_GO_KR_SERVICE_KEY` 로는 못 받는다.** 새 키가 필요하다.

## 3. 살아 있는 길

```
https://openapi.gg.go.kr/GENRESTRT?KEY={인증키}&Type=json&pIndex=1&pSize=100&SIGUN_NM=고양시
```

- 서비스명 `GENRESTRT` — 데이터셋 "일반음식점 현황_인허가"
  (infId `PCLA9AX1WQGYL7DNY5RE21793910`). 페이지가 JS 렌더라 브라우저로 읽어 확인했다.
- 호스트·프로토콜 실측: 서비스명이 틀리면 `ERROR-310`(서비스명 없음),
  키가 없거나 `sample` 이면 `ERROR-290`(인증키 무효). **둘 다 받아 봤다** —
  즉 호스트는 살아 있고 남은 것은 키뿐이다.
- 제공 항목(포털 명세): 사업장명 · 인허가일자 · **영업상태** · **폐업일자** ·
  소재지 지번주소 · 도로명주소 · **위경도** · 소재지면적 · 위생업태명.
  → 서울 수집기가 쓰는 축과 같다. `licensing_biz.json` 을 같은 모양으로 채울 수 있다.
- 31개 시군 전체 — 고양·파주 둘 다 포함.

## 4. 키 발급 (사람이 해야 하는 일) — **하나만 받으면 된다**

포털 안내를 직접 읽어 확인했다(2026-08-30):

- **인증키는 계정당 1개이고 모든 Open API 에 공통으로 쓴다.** 데이터셋마다 따로
  신청하지 않는다 — data.go.kr 의 '활용신청' 모델과 다르다.
- 발급은 **자동**이다. "인증키 발급 요청을 클릭하면 자동으로 인증키가 발급됩니다."
- **호출 횟수 제한 없음** — "경기데이터플랫폼은 OpenAPI요청 횟수에 제한을 두고있지 않습니다."
  (건축HUB 일 10,000콜 같은 쿼터 관리가 필요 없다는 뜻이다.)

경로:

1. 로그인 — `https://data.gg.go.kr/portal/openapi/insertApikeyPage.do` 로 가면 로그인으로 넘어간다.
   **네이버·카카오톡·구글 간편로그인** 가능(회원가입: `/portal/user/signup/mainPage.do`).
2. 인증키발급 화면에서 **활용용도 · 활용 URL · 내용** 세 칸을 적는다.
3. 발급된 키를 `.env` 에 `GG_OPENAPI_KEY` 로 넣는다. 확인은 §3 URL 1콜.

**이 세션이 대신 할 수 없다** — 계정 로그인이 걸린다.

## 5. 키가 풀리면 함께 열리는 것

계획서 Phase 3 이 요구하는 **경기 생활이동인구**도 같은 포털이다
(`docs/plan-gyeonggi-expansion-2026-08-29.md` §2-B). 같은 인증키로 되는지는
**키를 받은 뒤 1콜로 확인한다** — 지금 단정하지 않는다.

## 6. 그때까지의 상태

- 화정·금촌은 인허가 없이도 **Tier1 로 서 있다**(앵커 -2.72%p · -0.07%p).
- 없는 것은 ① 건물 이력 API ② 분자 보강. 둘 다 **비어 있는 것이 정상**이고
  화면이 그 사실을 밝히면 된다 — 시드로 채우지 않는다.
- 일산(라페스타) 채택 판정은 이 키가 풀린 뒤로 미룬다(사용자 판단, 2026-08-30).

## 부록 — 재현

```bash
curl.exe -s "https://openapi.gg.go.kr/GENRESTRT?KEY=sample&Type=json&pIndex=1&pSize=3"
# → {"RESULT":{"CODE":"ERROR-290","MESSAGE":"인증키가 유효하지 않습니다..."}}
curl.exe -s "https://openapi.gg.go.kr/NOSUCHSERVICE?KEY=sample&Type=json"
# → {"RESULT":{"CODE":"ERROR-310","MESSAGE":"해당 서비스의 서비스명을 찾을 수 없습니다..."}}
```

---

## 7. 키 검증 실측 (2026-08-30) — 되는 것과 걸리는 것

`GG_OPENAPI_KEY` 를 `data/.env` 에 넣고 실호출했다. **`INFO-000 정상 처리`.**

### 되는 것

| 항목 | 실측 |
|---|---|
| 전체 행 수 | **486,387** (경기 전 시군, 영업+폐업 모두) |
| 고양+파주 비중 | **11.2%** (3,000행 표본) → 약 54,000행 |
| 영업 행의 지번주소 | **100%** |
| 영업 행의 WGS84 좌표 | **98.2%** |
| 필드 | 36개 — `BIZPLC_NM` `LICENSG_DE` `BSN_STATE_NM` `CLSBIZ_DE` `REFINE_LOTNO_ADDR` `REFINE_ROADNM_ADDR` `REFINE_WGS84_LAT/LOGT` `LOCPLC_AR_INFO` `BIZCOND_DIV_NM_INFO` |

### 걸리는 것 셋

1. **시군 필터가 없다.** `SIGUN_NM` 은 **무시된다**(고양시/파주시/빈값 모두 486,387).
   `SIGUN_CD` 는 인식되지만(`INFO-200`) 응답의 `SIGUN_CD` 가 **전 행 null** 이라
   코드값을 알아낼 방법이 없다. → **전량 페이징 후 `REFINE_LOTNO_ADDR` 로 거른다.**
   서울 수집기가 쓰는 방식과 같다("서울 전역을 한 번만 페이징하며 거점 버킷에 담는다").
   pSize 1000 × **487콜**. 경기데이터드림은 호출 제한이 없어 쿼터 문제는 아니다.

2. **영업상태 문자열이 다르다.** 서울 `영업/정상` ↔ 경기 **`영업`** / `폐업`.
   소비층(`build_building_history._is_open`)은 `"영업" in state` 로 보므로 통과하지만,
   `TRDSTATEGBN`("01"=영업)은 우리가 만들어 넣어야 한다.

3. 🔴 **좌표계가 다르다 — 이게 진짜 함정이다.**
   `build_page_master._licensed_pip` 이 `EPSG:2097 → EPSG:4326` 변환을 **하드코딩**한다
   (서울 인허가 X/Y 가 중부원점 TM 계열이라서다. 게다가 표준 EPSG 와 -257m 어긋나
   '자가 보정'까지 붙어 있다). 경기 값은 **이미 WGS84** 이므로 그대로 `X/Y` 에 넣으면
   변환을 한 번 더 먹어 좌표가 통째로 어긋난다. **조용히 틀리는 종류다** —
   PIP 가 아무 건물에도 안 걸려 분자 보강이 0 이 되고, 그게 정상처럼 보인다.

   → 수집기가 행에 좌표계를 표기하고(`"CRS": "EPSG:4326"`), `_licensed_pip` 이
     표기된 행은 변환을 건너뛰게 한다. 서울 행은 표기가 없으므로 종전 경로 그대로다.

### 다음 작업 순서

1. `data/collectors/gg_licensing.py` — 전량 페이징 → 주소 필터 → 서울 스키마로 정규화
   (`MGTNO` `BPLCNM` `UPTAENM` `TRDSTATEGBN` `TRDSTATENM` `DCBYMD` `APVPERMYMD`
   `SITEWHLADDR` `RDNWHLADDR` `SITEAREA` `X` `Y` + `CRS`)
2. `_licensed_pip` 에 CRS 분기 추가 (+ 회귀 테스트)
3. 화정·금촌 수집 → `build_building_history` → Page 마스터 재빌드

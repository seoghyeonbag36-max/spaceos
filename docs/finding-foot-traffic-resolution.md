# 발견 — 유동인구 공간 해상도 실사 (B1, 2026-08-02)

> 질문: "생활인구를 거점 안까지 내릴 수 있는가." 앞서 `foot`(구역 유동인구)을
> **공간 해상도 부재**로 막아뒀고([spaceos-vibe-build-sequence.md](spaceos-vibe-build-sequence.md) 6-1),
> 해제 조건을 "생활인구 50m 격자 또는 골목상권 10m 도로 단위"로 적어뒀다.
> 그 두 가지가 실제로 존재하는지, 어떤 형태인지 API 를 직접 두드려 확정한다.

## 0. 결론 세 줄

1. **50m 격자·10m 도로 단위는 공개되지 않는다.** 실재하는 최소 단위는 집계구이고,
   집계구 생활인구는 OpenAPI 가 아니라 **파일 다운로드 전용**이다.
2. **집계구 경계(폴리곤)는 자동 취득 경로가 없다** — SGIS 자료신청(회원가입·승인)을
   사람이 거쳐야 한다. 코드로 뚫을 수 있는 문제가 아니다.
3. **그런데 상권 단위 시간대별 유동인구는 이미 Bronze 에 들어와 있다.**
   4-2(유동 레이어)·4-4(시간 슬라이더)는 새 수집 없이 지금 배선할 수 있다.
   막힌 것은 `foot` 하나뿐이다.

---

## 1. 실측한 것 — 네 갈래

| 경로 | 공간 해상도 | 시간 해상도 | 취득 | 지금 가능 |
|---|---|---|---|---|
| **A. 상권** `VwsmTrdarFlpopQq` | 1,650개 상권 (가로수길 ≒507m) | 6구간 + 요일 7 + 성·연령 | **Bronze 보유** | ✅ |
| **B. 행정동** `SPOP_LOCAL_RESD_DONG` | 행정동 (거점당 1~2) | **24시간** + 성·연령 15 | API 즉시 | ✅ |
| **C. 자치구** `SPOP_LOCAL_RESD_JACHI` | 25구 | 24시간 | API 즉시 | ✅(무용) |
| **D. 집계구** OA-14979 | 집계구 | 24시간 | **파일 + 경계 신청** | ⛔ |

### A. 상권 단위 — 이미 있다

`data/bronze/platform13/2026-07-25/seoul_trdar_flpop.json` · **3,990행 · 28필드**

```
TMZON_00_06 / 06_11 / 11_14 / 14_17 / 17_21 / 21_24   ← 시간대 6구간
MON ~ SUN_FLPOP_CO                                     ← 요일 7
ML/FML, AGRDE_10~60_ABOVE                              ← 성별·연령 6구간
```

경계는 `TbgisTrdarRelm`(1,650건)이 준다 — 단 **폴리곤이 아니라 중심좌표 + 영역면적**이다.

```
3120186 가로수길 | 발달상권 | 256,688㎡ (≒507m) | 신사동 | TM(201996,446810)
3120178 신사역   | 발달상권 | 353,066㎡ (≒594m) | 논현동 | TM(201729,446276)
```

**좌표계 = EPSG:5181 확정.** 세 후보를 변환해 가로수길 실제 좌표(37.520/127.023)와 대조:

| EPSG | 변환 결과 | 판정 |
|---|---|---|
| **5181** | 37.52077 / 127.02258 | ✅ 일치 |
| 5174 | 37.52352 / 127.02337 | ✗ 북쪽 300m |
| 2097 | 37.52352 / 127.02048 | ✗ |

거점별 상권 수: 190코드 / 54거점 = **평균 3.5개** (최대 청량리 9, 최소 1개가 2거점).

### B. 행정동 단위 — API 즉시, 시간 해상도가 가장 좋다

`SPOP_LOCAL_RESD_DONG` · 926,092행 · 최신 `20260729`(5일 전, 매일 갱신)

```json
{"STDR_DE_ID":"20260729","TMZON_PD_SE":"00","ADSTRD_CODE_SE":"11110515",
 "TOT_LVPOP_CO":"14259.6961", ...성별×연령 15구간}
```

`TMZON_PD_SE` 가 **00~23 시간별**이다. A(6구간)보다 세밀하다.
경계는 SGIS `boundary/hadmarea.geojson` 으로 받는다(인증 확인, 서울 25건 → `low_search` 로 하위).

### D. 집계구 단위 — 두 겹으로 막혔다

- **OpenAPI 없음.** 데이터셋 페이지에 "Sheet와 OpenAPI는 4일전 당일자료만 제공",
  실제 제공은 **ZIP 143개**(일별 38~40MB, 월 아카이브 ~1,200MB). 2017.1~2026.7.
  서비스명 후보 4종(`_TOT`·`_JIPGYE`·`_ADSTRD`·`_RESD`) 전부 `ERROR-500`.
- **경계는 더 막혀 있다.** SGIS OpenAPI 인증은 되지만 `boundary/` 에 집계구가 없다
  (`hadmarea`=행정구역만 응답, `totarea`·`jipgyegu` 는 엔드포인트 부재).
  집계구 경계는 [SGIS 자료제공](https://sgis.mods.go.kr/view/pss/openDataIntrcn) 회원가입 →
  **자료신청 → 승인 → 다운로드**. 서울 빅데이터캠퍼스에도 있으나 역시 신청 절차다.

라이선스는 문제없다 — 공공누리 1유형(상업 이용·변경 가능).

---

## 2. 함께 발견한 버그 — `living_population` 은 API 를 한 번도 쓴 적이 없다

[data/collectors/living_population.py](../data/collectors/living_population.py) 가 **항상 조용히 폴백**한다.
Program LLM 목킹 때와 같은 유형이다 — 고장이 폴백에 가려 보이지 않았다.

```
수집 결과 == _proxy_fallback() ?  True
```

원인 두 가지:

| # | 문제 | 실태 |
|---|---|---|
| 1 | **필드명 불일치** | `SEOUL_LIVING_POP_SGG_FIELD=SGG_CD` 로 필터하는데 API 실제 필드는 `ADSTRD_CODE_SE`. `r.get("SGG_CD")` 가 전부 `""` → 25구 모두 합계 0 → `any(raw.values())` False → 폴백 |
| 2 | **동일 URL 25회 호출** | [L49-53](../data/collectors/living_population.py#L49-L53) 의 `url` 이 루프 변수 `gu` 를 쓰지 않는다. 같은 요청을 25번 보내고 결과를 구별로 필터만 한다 |

부수적으로 `/1/1000/` 은 전체 926,092행 중 1,000행만 받는다 — 필드명을 고쳐도
날짜·시간대를 지정하지 않으면 표본이 임의의 1,000행이다.

⚠ 그래서 지금 `config.SCORE_BANDS["FOOT"]` 에 들어가는 25구 값은 **전부 config 앵커
상수**다(강남 100 · 중구 92 · 종로 84). 실측이 아니다. Platform 점수의 FOOT 축이
여기에 걸려 있다.

---

## 3. 결정

### 3-1. `foot`(구역 유동인구)의 해제 조건을 정정한다

기존 기록: "생활인구 50m 격자 또는 골목상권 10m 도로 단위" → **둘 다 공개되지 않는다.**
정정된 해제 조건:

> **집계구 단위 생활인구(파일) + 집계구 경계(SGIS 자료신청)**

그리고 이것은 **코드 작업이 아니라 신청 절차**다. 사람이 SGIS 에 신청해 승인을 받아야
착수할 수 있다. 승인 전까지 `foot` 은 계속 막아둔다 —
[AGENTS.md §0](../AGENTS.md) 의 판단은 유지된다.

⚠ 상권 단위(A)로 `foot` 을 대신하면 안 된다. 가로수길은 상권이 2개뿐이라
12개 공실 유닛이 2등급으로만 갈린다. "실측처럼 보이는 추정치"가 된다.

### 3-2. 4-2·4-4 는 집계구를 기다리지 않는다

셋을 한 덩어리로 묶어 뒀던 게 잘못이었다. 실사 결과 **둘은 이미 풀려 있다.**

| 대상 | 소스 | 이유 |
|---|---|---|
| **4-4 시간 슬라이더** | **B 행정동 24시간** | 시간 해상도가 목적. A 는 6구간뿐 |
| **4-2 유동 레이어** | **A 상권** | 거점당 3.5개로 공간 구분이 되고, 행정동보다 상권 실체에 가깝다. 중심점+면적을 원으로 근사 |

표기 규칙: 두 경로 모두 `foot_source` 를 응답에 싣는다 (`"trdar"` / `"living_dong"`).
**원으로 근사한 상권 영역은 폴리곤이 아니라는 사실을 프론트가 밝혀야 한다** — 실제
상권 경계선처럼 읽히면 안 된다.

### 3-3. 순서

1. **`fix/living-population-fallback`** — §2 버그 (Codex, 아래 슬롯 채워짐)
2. **`chore/foot-layer-trdar`** — 4-2 유동 레이어 (Codex, 1 이후)
3. **`chore/time-slider-living-dong`** — 4-4 시간 슬라이더 (Codex, 1 이후)
4. SGIS 집계구 자료신청 — **사람** (오늘 신청, 승인까지 대기)
5. `foot` 배선 — 4번 승인 이후. Claude Code

---

## 4. Codex 발주 슬롯 — 채워진 것

§3-3 의 1~3번은 규약 4개가 모두 채워졌다.

| 슬롯 | 1. 폴백 버그 | 2. 유동 레이어 | 3. 시간 슬라이더 |
|---|---|---|---|
| 대상 파일 | `living_population.py` | `services/foot_layer.py`(신규)·`heatmap.py`·`MapShell.tsx` | `services/foot_hourly.py`(신규)·`heatmap.py`·`MapShell.tsx` |
| 입력 소스 | `SPOP_LOCAL_RESD_DONG`, 필터 필드 `ADSTRD_CODE_SE` | Bronze `seoul_trdar_flpop.json` + `TbgisTrdarRelm`(EPSG:5181) | `SPOP_LOCAL_RESD_DONG` `TMZON_PD_SE` 00~23 |
| 출처 표기 | 폴백 시 `foot_source="config_anchor"` 를 반환값에 명시 | `foot_source="trdar"` + 영역은 원 근사임을 표기 | `foot_source="living_dong"` |
| 통과 조건 | `test_living_pop_uses_api_not_fallback` (필드명 깨뜨리면 실패해야 함) | `test_foot_layer_source_is_trdar` · `test_trdar_center_epsg5181` | `test_hourly_has_24_slots` |
| 금지 | 실패를 폴백으로 삼키지 말 것 | 상권을 폴리곤이라 표기 금지 | 결측 시간대를 보간하지 말 것 |

**아직 못 채우는 것**: `foot` 유닛 배선. 입력 소스(집계구)가 승인 전이라 슬롯 2번이 빈다.
AGENTS.md §5 에 따라 발주하지 않는다.

---

## 부록 — 실측에 쓴 명령

```powershell
# 서비스명 실측 (ERROR-500 = 미제공)
http://openapi.seoul.go.kr:8088/{KEY}/json/{SERVICE}/1/2/

# 확인된 서비스: SPOP_LOCAL_RESD_DONG · SPOP_LOCAL_RESD_JACHI
#               SPOP_DAILYSUM_JACHI · TbgisTrdarRelm · VwsmTrdarFlpopQq
# 미제공:       SPOP_LOCAL_RESD_TOT/JIPGYE/ADSTRD · VwsmTrdarRelm · VwsmAdstrdRelm

# SGIS
https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json   # 인증 OK
https://sgisapi.kostat.go.kr/OpenAPI3/boundary/hadmarea.geojson?year=2022&adm_cd=11
#   → 25건(시군구). 집계구 경계 엔드포인트는 없음
```

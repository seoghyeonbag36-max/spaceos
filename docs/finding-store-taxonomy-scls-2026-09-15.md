# 상가정보 **소분류**(`indsSclsNm`) 어휘 실측 — 이 머신에서는 잴 수 없다 (2026-09-15)

## 판정

🔴 **측정 불가 — 표본이 이 머신에 존재하지 않는다.**

`편의점` · `약국` · `커피전문점` 세 소분류 문자열을 확정하려 했고, **확정하지 못했다.**
세 경우 모두 결론은 같다: **"이 표본에 없다"가 아니라 "표본 자체가 없다."**

그래서 `data/config/store_taxonomy.py` 에 **소분류 상수(`SCLS_*`)를 추가하지 않았다.**
추가할 수 있는 실측 문자열이 0개다. 추측을 코드에 넣지 않는 것이 이 작업의 전제였다.

이 문서는 "아직 못 했다"의 기록이 아니라 **무엇을 확인했고 왜 막혔는지**의 기록이다.
다음 사람이 같은 30분을 반복하지 않도록, 후보 네 곳을 전부 열어 보고 각각 왜
근거가 될 수 없는지를 남긴다. 특히 §3 의 함정은 **그럴듯해서 위험하다.**

---

## 1. 감사 실행 — 출력 그대로

지시된 명령을 그대로 돌렸다.

```bash
mkdir -p reports/logs
PYTHONIOENCODING=utf-8 python -m data.config.store_taxonomy --audit \
  > reports/logs/taxonomy_audit_20260915.log 2>&1
```

산출물 `reports/logs/taxonomy_audit_20260915.log` (253 bytes) **전문**:

```
[taxonomy] 거점 66곳 · 행 0 · 가두 0
[taxonomy] ⚠ Bronze 없음 66곳: garosugil, apgujeong-rodeo, hongdae, yeonnam, ikseon, seochon, myeongdong, euljiro …
[taxonomy] 셀 것이 없다 — building_vacancy 로 stores_raw 수집이 먼저다
```

> 로그를 여기에 전문 인용하는 이유: `reports/logs/` 는 gitignore 대상이라
> (`.gitignore:209`) 커밋되지 않는다. 컨테이너가 회수되면 파일은 사라진다.
> **이 문서가 그 로그의 유일한 영속 사본이다.**

읽을 것: 거점 **66곳 전부** Bronze 없음. 가두 점포 0행. 사상률 계산 자체가 돌지 않았다.
미사상 소분류 상위 25 목록은 **찍히지 않았다** — 셀 행이 0이라 그 블록에 진입하지 않는다.

---

## 2. 왜 없나 — 두 겹으로 막혀 있다

### (1) Bronze 는 커밋되지 않는다

```
.gitignore:27   data/bronze/*
```

`data/bronze/` 는 `.gitkeep` 만 남기고 통째로 제외된다. 신규 클론·CI·이 원격 세션은
**구조적으로** `stores_raw.json` 을 갖지 못한다. 머신 전체를 훑어도 없다:

```bash
find / -name '*stores_raw*' 2>/dev/null   # → 0건
```

### (2) 지시된 폴백(`building_vacancy` 선행)도 막혀 있다

작업 지시는 "Bronze 가 없으면 building_vacancy 먼저"를 허용한다. 돌렸다:

```
[env] /home/user/spaceos/data/.env 없음 — 모든 기준 프록시 폴백으로 실행
[bldg-vac] DATA_GO_KR_SERVICE_KEY 미설정(또는 requests 없음) — 건너뜀
```

수집기가 **스스로 건너뛴다.** `DATA_GO_KR_SERVICE_KEY`(공공데이터포털 15012005)가
환경에 없고 `data/.env` 도 없다. 자격증명이 없으면 수집은 시작조차 하지 않는다.
(`requests` 모듈도 이 환경에 없다 — 같은 가드가 둘을 함께 본다.)

→ **API 콜 0건 유지.** 이 작업은 한 번도 외부를 호출하지 않았다.

---

## 3. ⚠ 함정 — 소분류처럼 보이는 것이 저장소에 **있다**. 그것은 카카오다

가장 중요한 절이다. 이걸 모르면 다음 사람이 "실측했다"고 믿으며 카카오 어휘를
규칙에 심는다.

`data/gold/*/program_content_context.csv` 의 `kind=category` 행은
**빌더 코드상 정확히 소분류다** — `build_gold.py:524` 가 이렇게 만든다:

```python
# `places` 는 상가정보(stores_raw) 행이다 — 2026-09-15 카카오 로컬에서 갈았다.
cats = Counter(category_path(d).split(" > ")[-1] for d in places)   # ← 마지막 조각 = indsSclsNm
```

그래서 이 CSV 를 열면 `약국`(62회)·`커피전문점`(58회)이 **그대로 보인다.**
바로 이게 함정이다. **커밋된 CSV 는 소스 교체 이전 산출물이다.**

| | |
|---|---|
| CSV 를 마지막으로 쓴 커밋 | `c7a51df` **2026-09-04** |
| 소스를 카카오→상가정보로 갈은 커밋 | `8432cbc` **2026-09-15** (11일 뒤, 그 사이 136커밋) |

빌더는 갈렸지만 **산출물은 아직 안 갈렸다.** 이 문서와 독립적으로 같은 사실이
`finding-map-provider-google-2026-09-15.md` §(2-2) 런북에도 적혀 있다 —
"이 실행이 `program_content_context.csv` 66개를 통째로 다시 쓴다 … category 행의
어휘가 **카카오 → 상가정보 소분류로 갈린다**".

### 코드가 아니라 어휘로도 증명된다

66개 CSV 전수 집계 — 고유 category 키 **124종 · 등장 1,980회**:

| 증거 | 값 | 무엇을 뜻하나 |
|---|---|---|
| 슬래시(`/`) 결합 키 | **0종** | 상가정보 소분류는 `커피전문점/카페/다방`·`백반/한정식` 처럼 `/` 로 묶인다. 하나도 없다 |
| 쉼표(`,`) 결합 키 | **17종** | `호프,요리주점` · `제과,베이커리` · `돈까스,우동` — 카카오 `category_name` 의 형태다 |
| 브랜드명 키 | **5종** | `CU` · `GS25` · `세븐일레븐` · `이마트24` · `스타벅스` |
| `커피전문점/카페/다방` | **0회** | 상가정보 형태는 등장하지 않는다 |

🔴 **브랜드명이 결정타다.** 상가정보 소분류는 **247개 고정 코드북**이다. 거기에
`CU`·`스타벅스` 같은 상호가 들어갈 자리는 없다. 이 어휘는 카카오다.

→ 여기서 `약국`·`커피전문점`을 집어다 "실측 문자열"이라 부르면, 약관 때문에
**걷어낸 카카오 파생 어휘를 규칙으로 세탁해 되돌리는 것**이 된다. 하지 않았다.

---

## 4. 나머지 후보 — 전부 열어 봤다

| # | 후보 | 결과 | 왜 안 되나 |
|---|---|---|---|
| 1 | `data/logs/probe_d1_2026-07-07.log` | ❌ | 39개 필드 확정의 근거이나 **샘플 행이 1건**이다. 그 행의 `indsSclsNm` 은 `광고물 설계/제작업`(대분류 과학·기술) — 7종과 무관 |
| 2 | `data/gold/garosugil/platform_store_graph_nodes.parquet` | ❌ | 노드 스키마에는 `inds_scls` 가 **있다**(`build_gold.py:277`). 그런데 커밋된 파일에는 그 컬럼이 없다 — 바이너리에 `inds_scls` 0회 · `kakao` **15회**. 소스 교체 이전 빌드다 |
| 3 | `data/gold/*/program_content_context.csv` | ❌ | §3 — 카카오 어휘다 |
| 4 | `finding-sequence-and-accuracy-2026-08-17.md` §6 | ❌ | 클래스 **수**(mcls 75 · scls 247 · ksic 306)와 대응 관계는 확정하지만 **개별 소분류 문자열을 나열하지 않는다**. 교차표도 중분류 층위다(`약국→소매(의약·화장품) 744`) |
| 5 | `reports/*.json` (probe 산출물 19종) | ❌ | `indsScls`/`inds_scls`/`소분류` 검색 0건 |

`data/gold/` 에 커밋된 산출물은 8종 뿐이고(`page_building_master.geojson` ·
`coverage.json` · `calibration.json` · `vacant_units.json` ·
`vacant_floor_units.json` · `program_content_context.csv` · `district_zones.json` ·
`building_history.json`), **이 중 상가정보 소분류를 담는 것은 없다.**
`vacant_*` 의 `grp`/`was` 는 중분류 최빈값이라 §(2-5) 중분류 감사가 쓴 그 소스다.

> 참고: `building_history.json` 에도 `다방`·`편의점`·`전통찻집` 이 보인다. 그것은
> **인허가(licensing) `industry_type` = 업태명**이고 상가정보 계층이 아니다. 같은
> 이유로 근거가 될 수 없다.

---

## 5. 세 목표에 대한 결론

| 목표 | 가정된 중분류 | 현행 규칙(미검증) | 실측 결과 |
|---|---|---|---|
| **편의점** | `종합 소매` 하위 | `_has(scls, "편의점")` | ❌ **표본 없음** — 확정 못 함 |
| **약국** | `의약·화장품 소매` 하위 | `_has(scls, "약국")` | ❌ **표본 없음** — 확정 못 함 |
| **커피전문점** | `비알코올` 하위 | `_has(scls, "카페","커피","다방","찻집")` | ❌ **표본 없음** — 확정 못 함 |

세 규칙은 **2026-09-15 이전과 똑같이 미검증 추측으로 남는다.** 이번 작업은 그것을
확정하지도, 악화시키지도 않았다 — 다만 **왜 확정할 수 없었는지**를 근거로 고정했다.

### ⚠ 테스트에 이미 들어가 있는 소분류 문자열도 추측이다

`data/tests/test_store_taxonomy.py::test_maps_to_seven_group_vocabulary` 는 이미
`커피전문점/카페/다방` · `편의점` · `약국` 을 파라미터로 들고 있고 통과한다.
**통과한다는 사실이 그 문자열이 실재한다는 근거는 아니다** — 규칙과 테스트가 같은
추측을 공유하면 서로를 검증하지 못한다. 실측이 되는 날 **가장 먼저 대조할 대상이
이 세 값**이다. (그렇다고 지금 약화시키지는 않았다. 틀렸다는 근거도 없기 때문이다.)

---

## 6. 무엇이 있으면 끝나나

자격증명 하나다.

```bash
# 1) 공공데이터포털 15012005 서비스키를 data/.env 에 넣는다
echo 'DATA_GO_KR_SERVICE_KEY=…' >> data/.env

# 2) Bronze 수집 (stores_raw.json)
PYTHONIOENCODING=utf-8 python -m data.collectors.building_vacancy

# 3) 이 작업의 1번으로 복귀 — 그때는 미사상 소분류 상위 25가 실제로 찍힌다
PYTHONIOENCODING=utf-8 python -m data.config.store_taxonomy --audit \
  > reports/logs/taxonomy_audit_$(date +%Y%m%d).log 2>&1

# 한 거점만 좁혀 보려면
PYTHONIOENCODING=utf-8 python -m data.config.store_taxonomy --audit garosugil
```

그 로그에 **보이는 문자열만** `SCLS_CVS` · `SCLS_PHARMACY` · `SCLS_CAFE` 로 넣고,
중분류 상수(`MCLS_*`)와 같은 양식으로 출처(로그·날짜·등장 건수)를 주석에 남긴다.
판정 순서(① 약국 ② 편의점 ③ 카페 ④ 병원 ⑤ 숙박 ⑥ 문화시설 ⑦ 음식점)는 유지한다.

---

## 7. 이번에 건드리지 않은 것

- `SCLS_*` 상수 — **추가하지 않았다**(넣을 실측 문자열이 0개)
- `to_category_group` 판정 순서 · `RETAIL_MARKER` · `MCLS_*` — 그대로
- 7종 라벨 문자열 — 그대로(체크포인트 `classes` 계약)
- `build_gold` · `train_gnn` — 돌리지 않았다

## 8. 회귀 상태 (이 작업 시점)

```
python -m pytest data/tests/test_store_taxonomy.py -q   → 58 passed
python -m pytest data/tests -q --ignore=…/test_ledger_backoff.py
                                                        → 341 passed, 1 skipped
python -m data.config.store_taxonomy --gold             → 135파일 · 65종 · 13,855회
                                                          어휘 23.1% · 등장 47.0% (하한 유지)
```

⚠ `data/tests` 전건은 이 환경에서 **수집 단계에서 멈춘다** —
`test_ledger_backoff.py:20` 이 `import requests` 인데 모듈이 없다. 작업 전
**깨끗한 트리에서도 같은 실패**라 이번 변경과 무관한 환경 결손이다.
파이썬도 두 개다: 기본 `python` 에는 pytest 가 없고 `apps/backend/.venv/bin/python`
에 있다(SessionStart 훅이 안내하는 그대로).

---

## 근거 출처

- `reports/logs/taxonomy_audit_20260915.log` — §1 에 전문 인용(gitignore 대상)
- `data/logs/probe_d1_2026-07-07.log` — 39필드·샘플 1건
- `docs/finding-sequence-and-accuracy-2026-08-17.md` §5·§6 — 계층 클래스 수·교차표
- `docs/finding-map-provider-google-2026-09-15.md` §7-2·§(2-2)·§(2-5) — 약관 경위·재생성 런북·중분류 감사
- `git log` `c7a51df`(2026-09-04) ↔ `8432cbc`(2026-09-15) — §3 의 11일 간극

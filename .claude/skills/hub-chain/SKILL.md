---
name: hub-chain
description: 거점 하나를 후보 판정 → 등록 → 수집 → Gold → 앵커 대조 → 서빙 등재 → 검증 → 배포까지 한 줄로 미는 선형 체인. 새 거점·새 도시를 실제로 세울 때 이것을 따라 내려간다.
---

# 거점 체인 — 한 거점을 끝까지 민다

여러 skill 을 순서대로 부르는 **파이프라인**이다. 각 단계는 앞 단계의 산출물을 입력으로
받고, **통과 조건을 산출물로 확인한 뒤에만** 다음으로 간다.

상태는 선언이 아니라 파일에서 읽는다:

```bash
python scripts/chain_status.py <slug>          # 9단계 통과 여부 + 근거 + 다음 명령
python scripts/chain_status.py <slug> --next   # 다음 한 수만
python scripts/chain_status.py --all --json    # 기계용
```

호출 인수 = 거점 slug(들). 비어 있으면 무엇을 밀지 먼저 묻는다.

## 체인

| # | 단계 | 부르는 skill | 통과 조건(프로버 단계) |
|---|---|---|---|
| 0 | 후보 판정 | `probe-first` | 건물당 점포 ≤10 · R-ONE 매핑 확인 |
| 1 | 등록 | `hub-onboard` §1 | `등록` ok — page_hubs ↔ cities 정합 |
| 2 | 점포·폴리곤 | `hub-onboard` §2 | `점포` `폴리곤` ok |
| 3 | 대장(쿼터) | `quota` + `autorun` | `대장` ok · `정밀분모` ok |
| 4 | Gold 빌드 | `gold-build` | `Page마스터` = Tier1 · 정밀커버리지 ≥80% |
| 5 | 앵커 대조 | `gold-build` | `앵커` 격차 \|gap\| ≤ 30%p |
| 6 | 서빙 등재 | `page` / `backend-dev` | `서빙등재` ok — API 목록에 뜬다 |
| 7 | 검증 | `verify` | 정적 3종 + 지도 픽셀 |
| 8 | 배포 | `deploy` | CI 초록 (`vacancy_source: gold` 확인 포함) |

## 단계별 실행

### 0. 후보 판정 — 등록 전에 잰다
건물당 점포 수(상가정보 ÷ bdMgtSn 그룹) > 10 이면 계획상가 밀집이라 우리 분모가
대다수를 놓친다. 일산 라페스타 37.4 가 여기서 걸린다. 대조군(가로수길 4.0)을 같이 잰다.

### 1~2. 등록과 1차 수집
```bash
# page_hubs.py 에 PageHub 한 줄 (+ 새 도시면 app/data/cities.py 에도)
python -m data.collectors.vworld_bldg <slug>
python -m data.collectors.building_vacancy <slug> --no-ledger
```
여기까지는 쿼터가 넉넉하다. 이 시점에서 이미 **지도에 폴리곤이 뜨는 Tier2** 다.

### 3. 대장 — 이 체인의 유일한 실질 병목
```bash
python scripts/quota_preflight.py                      # 쿼터·전원·시도이력
python -m data.collectors.building_vacancy <slug>      # 전유부→표제부
python -m data.collectors.floor_capacity <slug>        # 층별개요
```
하루에 안 끝나면 **여기서 잠시 멈추는 것이 정상이다.** 다음 날 이어 받는다 — 수집기가
받은 것을 건너뛴다. 자리를 비운 채 돌릴 때는 `autorun`(keep_awake · UTF-8 · watch).

### 4~5. Gold 와 앵커
```bash
python -m data.pipelines.build_building_attrs <slug>
python -m data.pipelines.recalc_floor_ouln <slug>
python -m data.pipelines.build_page_master <slug>
python -m data.pipelines.build_vacant_units <slug>
python -m data.pipelines.calibrate_vacancy
python scripts/chain_status.py <slug>
```

### 6. 서빙 등재 — **여기가 이 체인에서 유일하게 되돌리기 어려운 단계다**
`app/data/seoul_pages.DISTRICTS` 에 오르는 순간 화면에 뜬다. Gold 가 서기 전에 올리면
**시드(zones·units)를 지어내야 하고**, 그러면 합성값이 실측처럼 보인다. 4~5 를 통과하기
전에는 올리지 않는다. 새 도시 거점은 `city` 필드가 붙어 있어야 프론트가 가른다.

### 7~8. 검증과 배포
`verify` → `deploy`. 푸시는 백그라운드로(GCM 인증창).

## 2단계(고양·파주) 실행 순서 — 확정

프로브(2026-08-29)와 R-ONE 표본으로 정해진 순서다. **한 번에 한 거점씩** 민다.

| 순서 | 거점 | city | R-ONE | 건물당 점포 | 비고 |
|---|---|---|---|---|---|
| 1 | `hwajeong` 화정 | goyang | `경기>고양시청` | 8.5 | 표본·비율 둘 다 통과 |
| 2 | `geumchon` 금촌 | paju | `경기>파주시청` | 3.0 | 서울 평균보다 낮다 |
| 3 | `unjeong` 운정 | paju | 파주시청 **공유** | 5.3 | `rone-shared` 표기 필요 |
| 4 | `ilsan` 일산 라페스타 | goyang | 탄현역 공유 | **37.4** | 집합상가 명시 없이는 넣지 않는다 |

1·2 를 먼저 완주해 **경기 파이프라인이 서울과 같은 스키마로 서는지 확인**한 뒤 3 으로
간다. 3 부터는 임대 앵커 공유 표기(`rone-shared`)가 코드에 없으면 진행하지 않는다 —
없는 채로 넣으면 공유 사실이 화면에서 사라진다. 4 는 §0 판정을 다시 받는다.

서울 54거점을 잇는 "road" 는 도시 필터로 연결한다 — **화면을 복제하지 않는다**(`city-expand` §5).

## 함정 (이 체인을 처음 돌리며 실제로 밟은 것)

- **수집기가 모르는 거점을 조용히 건너뛴다 → 지금은 죽는다.** 2026-08-30 `hwajeong`
  수집이 "미등록 거점 — 건너뜀"을 찍고 **exit 0** 으로 끝나, 체인은 성공으로 읽었다.
  원인은 경기 거점이 `GYEONGGI_HUBS` 라는 별도 dict 에 있는데 수집기가 `HUBS` 만 본 것.
  조회는 `page_hubs.get_hub()`(= `ALL_HUBS`)로 모았고 미등록은 `SystemExit` 이다.
  `apps/backend/tests/test_city_registry.py` 가 되돌림을 막는다.
  → **교훈: 단계 통과는 로그가 아니라 프로버로 확인한다.** exit 0 은 통과가 아니다.
- **인자 없이 도는 전 거점 루프는 여전히 서울 54곳이다.** 경기 거점은 이름을 대고
  부를 때만 잡힌다 — 산출물 없는 거점이 매 실행 실패로 찍히고 거점 수 분모가 흔들리는 것을 막는다.
- **배터리면 2~7배 느리다.** 대장 단계 전에 AC 를 연결한다(프리플라이트가 경고한다).

## 규칙

- **대장(3단계)은 한 거점씩.** 건축HUB 쿼터는 키 단위라 동시에 돌리면 서로를 죽인다
  (429 는 키 단위 — 프리플라이트도 "전유부와 층별개요를 동시에 돌리지 말 것"이라 적는다).
  **2단계(점포·폴리곤)는 다르다** — 상가정보·V-World 는 별도 서비스에 쿼터도 넉넉해
  다음 거점 것을 미리 받아 둬도 된다. 2026-08-30 화정 대장이 도는 동안 금촌을 그렇게 받았다.
- **어디까지 왔는지는 기억이 아니라 프로버로 안다.** 여러 거점을 걸쳐 놨다면 더욱.
- **단계를 건너뛰지 않는다.** 특히 5→6. 앵커 대조 없이 등재된 거점은 나중에 값이
  틀렸을 때 화면에서 되돌려야 한다.
- **막히면 그 자리에 기록한다.** 쿼터·표본 부재는 실패가 아니라 대기다 —
  `docs/finding-*.md` 에 남기고 다음 거점으로 간다(그 판단은 `loop-engine`).

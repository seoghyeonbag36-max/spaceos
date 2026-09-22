# 클라우드 프롬프트 — 노트북이 꺼져 있어도 도는 15거점 검증 (2026-09-23)

**언제 쓰나**: 노트북이 꺼져 있거나 Dispatch 가 안 붙는 날. 폰의 **Claude Code 클라우드 세션**
(claude.ai/code, 저장소 `seoghyeonbag36-max/spaceos`)에서 연다.

**할 수 있는 것과 없는 것** — 클라우드는 GitHub 의 새 클론이라 `.env`(API 키)와
`data/bronze`·`data/silver` 가 없다([PlaceOS_Mobile_Dispatch_Prompts.md](../PlaceOS_Mobile_Dispatch_Prompts.md) §0).

| | 클라우드에서 |
|---|---|
| 전유부·층별개요 수집 | ❌ API 키 없음 |
| 파이프라인(Page 마스터·앵커)·구역 빌드·앵커 대조(`--rebuild`) | ❌ 전부 bronze/silver 를 읽는다 |
| **push 된 Gold 로 개수·숫자 확인** | ✅ |
| **백엔드가 그 Gold 를 서빙하는지 확인** | ✅ (TestClient) |
| **data·backend pytest — 머지 조건까지 남은 거리** | ✅ (CI 와 같은 명령) |

그래서 이 프롬프트는 **판정만** 한다. 만들어야 할 것이 남았으면 노트북 몫으로 적고 끝낸다.

## 전제 — 09-22 밤 노트북이 해 두는 일

노트북의 무인 체인(`data/logs/finish-chain-2026-09-22.log`)이 끝나면 후속 스크립트가 이어서:
1. 15거점 중 `anchor` 까지 온 거점의 **행정동 구역**(`build_district_zones`)을 만들고
2. 그 거점들의 Gold(`page_building_master` · `coverage` · `calibration` · `vacant_units` · `district_zones`)를
   **`feat/seoul-hubs-batch3-4-20260921`**(draft PR #39)에 커밋해 push 한다. `main` 에는 안 간다.
   `building_vacancy.json` 은 `.gitignore` 대상이라 안 올라간다.
3. 기록: 노트북 `data/logs/publish-gold-2026-09-22.log`

**노트북은 그 커밋이 PR #39 에 올라온 뒤에 꺼야 한다.** 그 전에 끄면 체인이 죽고 아무것도 안 올라간다.
PR #39 커밋 목록에 `data(gold): 서울 3·4차 …` 가 보이면 꺼도 된다(GitHub 앱으로 확인).

---

## 짧은 버전 — 폰에서 이것만 입력해도 된다

```
[클라우드 세션] 브랜치 feat/seoul-hubs-batch3-4-20260921 을 체크아웃하고 docs/prompts-cloud-hub-verify-2026-09-23.md 의 "프롬프트" 블록을 그대로 수행해. 응답은 한국어.
```

## 프롬프트 (그대로 붙여넣기)

```
[클라우드 세션 — 노트북 꺼져 있어도 됨] 서울 3·4차 15거점: 어젯밤 노트북이 push 한 Gold 를 판정하고,
등록 머지까지 남은 거리를 잰다. 판정만 한다. 응답은 한국어.

대상 15거점:
  bangbang gildong nowon gurodigital ydp-gucheong seochoyeok poi dogok yangjae jamsil-tour daerim guui maebong gurojeonhwa bonseobu

## 0. 브랜치
    git fetch origin feat/seoul-hubs-batch3-4-20260921
    git checkout -B feat/seoul-hubs-batch3-4-20260921 origin/feat/seoul-hubs-batch3-4-20260921
    git log --oneline -5
- 맨 위 근처에 "data(gold): 서울 3·4차" 커밋이 있는지 본다. 없으면 노트북의 체인이나 자동 push 가
  끝나지 못한 것이다 → 1단계만 돌려 무엇이 없는지 보고하고 **멈춘다.** 이 세션에서 만들 방법은 없다.

## 지켜야 할 것
- 이 세션에는 .env 도 data/bronze·silver 도 없다. data.collectors.* · data.pipelines.* ·
  data.analyze_anchor_population · build_gold 는 **실행하지 않는다**(실패를 확인하려고 돌려 보지도 말 것).
- git push · merge · PR 상태 변경 금지. main push 는 프로덕션 자동 배포다. 이 세션은 아무것도 커밋하지 않는다.
- 코드·설정·테스트를 고치지 않는다. 실패는 분류해서 보고만 한다.
- 모르는 게 나오면 추측해서 채우지 말고 멈추고 물어본다.

## 1. 산출물 개수 — 15거점 × Gold
    python - <<'EOF'
    from pathlib import Path
    H="bangbang gildong nowon gurodigital ydp-gucheong seochoyeok poi dogok yangjae jamsil-tour daerim guui maebong gurojeonhwa bonseobu".split()
    need=["page_building_master.geojson","coverage.json","calibration.json","vacant_units.json","district_zones.json"]
    extra=["vacant_floor_units.json","program_content_context.csv"]   # 기존 거점엔 있다 — 다른 빌더 몫
    for s in H:
        d=Path("data/gold")/s
        miss=[f for f in need if not (d/f).exists()]
        ex=[f for f in extra if (d/f).exists()]
        print(f"{s:14s} 필수 {len(need)-len(miss)}/{len(need)}  없음 {miss or '-'}  기타 {ex or '-'}")
    EOF

## 2. 거점별 숫자 — Gold 에서 읽는다
    python - <<'EOF'
    import json; from pathlib import Path; from collections import Counter
    H="bangbang gildong nowon gurodigital ydp-gucheong seochoyeok poi dogok yangjae jamsil-tour daerim guui maebong gurojeonhwa bonseobu".split()
    for s in H:
        d=Path("data/gold")/s
        try:
            c=json.loads((d/"coverage.json").read_text(encoding="utf-8"))
            g=json.loads((d/"page_building_master.geojson").read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"{s:14s} Gold 없음"); continue
        st=Counter(f["properties"].get("status") for f in g["features"]); n=sum(st.values())
        print(f"{s:14s} {c.get('tier')}  대표공실 {c.get('reference_vacancy_pct')}%  정밀 {c.get('reference_coverage_pct')}%  "
              f"동 {n}  high {st.get('high',0)/max(n,1):.0%}  {dict(st)}")
    EOF
- calibration.json 의 gap_pp 는 인용하지 않는다(집합건물을 섞은 혼합 추정 기준). 격차는 3단계의 API 값만 쓴다.

## 3. 서빙에 닿는가 — 백엔드를 띄우지 않고 TestClient 로
    pip install -r apps/backend/requirements.txt
    cd apps/backend && python - <<'EOF'
    from fastapi.testclient import TestClient
    from app.main import app
    H="bangbang gildong nowon gurodigital ydp-gucheong seochoyeok poi dogok yangjae jamsil-tour daerim guui maebong gurojeonhwa bonseobu".split()
    with TestClient(app) as c:
        for s in H:
            r=c.get(f"/api/v1/commercial-districts/{s}/summary")
            j=r.json() if r.status_code==200 else {}
            h=c.get("/api/v1/heatmap/buildings", params={"district": s})
            n=len(h.json().get("features",[])) if h.status_code==200 else None
            print(f"{s:14s} summary {r.status_code}  공실 {j.get('vacancy_rate')}  앵커 {j.get('anchor_pct')}  "
                  f"격차 {j.get('anchor_gap_pp')}pp  보류 {j.get('vacancy_withheld')}  heatmap {h.status_code} {n}건")
    EOF
- heatmap 이 800건대면 Gold 실데이터, 8건이면 샘플 폴백이다. 404 면 서빙 목록에 안 오른 것 — 원인을 코드에서
  찾아 보고만 한다(measured_pages._is_measured 가 Page 마스터 존재로 판정한다).
- 이 단계가 앱 기동부터 실패하면(DB 등) 건너뛰고 그 오류 한 줄만 보고한다.

## 4. 테스트 — CI 와 같은 명령
    pip install -r data/requirements.txt pytest
    python -m pytest data/tests -q 2>&1 | tail -40
    cd apps/backend && python -m pytest -q 2>&1 | tail -20
- 09-21 실측은 data 47건 실패였다(test_district_zones 45+1 · Page 진행률 100→88.9 1건). 오늘 몇 건인가.
- 실패를 셋으로 가른다:
  (a) 15거점 Gold 가 아직 없는 것 — 노트북이 만들어야 한다(어느 빌더인지 적는다)
  (b) 등록 때문에 기대값이 바뀐 것 — 거점 수·진행률 같은 숫자 기대
  (c) 그 밖
- 가능하면 PR #39 의 CI 결과도 본다(gh pr checks 39 — gh 가 없으면 건너뛴다).

## 5. 보고
- 15거점 Gold 표 (필수 5종 있음/없음 · 기타)
- 거점별: 대표 공실률 · high 비율 · 앵커 · 격차(anchor_gap_pp) · heatmap 건수
- **공개 전 확인 5거점** poi · seochoyeok · yangjae · maebong · dogok 를 따로 묶는다 — 서초·강남 남부
  권역으로 high 비율이 높게 나왔다. 다섯 곳 모두 R-ONE **공유 매핑**(rone_districts.SHARED_RONE)이라
  앵커가 인접 상권 표본이라는 점을 같이 적는다.
- pytest: data·backend 실패 수와 (a)(b)(c) 분류, 09-21(47건) 대비
- 머지까지 남은 것을 **노트북이 필요한 것 / 클라우드에서 가능한 것**으로 갈라 적는다
```

---

## 사용자 메모 (프롬프트 밖)

- **노트북을 끄는 시점**: PR #39 에 `data(gold): 서울 3·4차 …` 커밋이 보인 뒤. 예상 09-23 00:00~01:30.
  그 전에 끄면 체인과 자동 push 가 같이 죽는다 — 그때는 이 프롬프트가 "Gold 없음"만 보고한다.
- **자동 push 가 실패했으면**(커밋이 안 보이는데 체인은 끝남): 노트북을 켤 수 있는 날
  [Dispatch 프롬프트](prompts-mobile-hub-finish-2026-09-23.md)로 이어받는다. 원인은 노트북
  `data/logs/publish-gold-2026-09-22.log` 에 남는다.
- **PR #39 에 push 되면 CI 가 돈다**(pull_request 트리거). 배포는 `main` push 에만 걸려 있어 프로덕션은 안 바뀐다.
  CI 가 빨간 것은 정상이다 — Program Gold(`program_content_context.csv`) 등은 아직 없다.
- **머지는 이 프롬프트가 하지 않는다.** 머지 조건: 15거점 Gold 완비 → `pytest data/tests` 녹색 →
  등록과 Gold 가 한 PR 로(09-21 메모). 공개 여부도 그때 정한다.

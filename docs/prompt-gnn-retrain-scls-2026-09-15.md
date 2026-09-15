# 다음 작업용 프롬프트 — 노드 소스 교체 뒤 GNN 재학습 (라벨 어휘 결정 포함)

2026-09-15 카카오 저장층 이전(`docs/finding-map-provider-google-2026-09-15.md` §7-2)의
마지막 미결 항목이다. 점포 노드가 카카오 → 상가정보로 바뀌었고, 서빙 배치
`gold/platform_industry_recommend.json` 은 아직 **옛 카카오 노드로 만들어진 것**이다.

⚠ **선행 작업이 있다.** `docs/prompt-store-taxonomy-scls-2026-09-15.md`(소분류 어휘 실측)를
먼저 끝낼 것. `편의점`·`약국`·`커피전문점` 판정이 아직 미검증 추측이라, 그 상태로
학습하면 **라벨이 틀린 모델**이 나온다. 라벨 품질이 거기서 정해진다.

---

## 이 작업이 어려운 이유 — 대조군을 만들 수 없다

이 저장소는 2026-08-26 에 값비싼 교훈을 얻었다(`docs/feature-platform.md` §0-Q).
행정동 시간블록을 **닷새 전 기준선(37.63%)** 에 대고 `−0.12%p` 로 기각했는데,
같은 시대 코드로 대조군을 돌려 보니 기준선이 실제로는 **35.92%** 였고 그러면
행정동은 `+1.59%p` 였다. **기각 판정이 낡은 기준선에 걸려 있었다.**

그래서 이 저장소의 규칙은 "**대조군을 같은 런에서 같이 돌린다**" 다.

**그런데 이번에는 그 규칙을 지킬 수 없다.** 옛 그래프(카카오 47,442노드)의 소스가
**설계상 사라졌다** — `bronze/*/kakao_places.json` 을 없앴고, 재수집은 약관 위반이다
(finding §7-2). 옛 값의 유일한 기록은 커밋된 `platform_industry_recommend.json` 의
`metrics` 블록이다.

따라서 **이번 재학습은 회귀 측정이 아니라 새 기준선 수립**이다. 그렇게 쓰지 않으면
다음 사람이 또 낡은 기준선에 대고 판정한다.

---

## 붙여 넣을 프롬프트

```
PlaceOS GNN 을 새 노드 소스(상가정보)로 재학습해줘. 다만 **학습 명령을 먼저 돌리지 말고**
아래 순서를 지킬 것 — 라벨 어휘를 먼저 결정해야 한다.

## 확정된 사실 (다시 규명하지 말 것)

1. 노드 소스가 2026-09-15 에 카카오 로컬 → 소상공인 상가정보로 바뀌었다.
   node_id 체계 `kakao:{장소id}` → `sdsc:{bizesId}`.
   경위·근거: docs/finding-map-provider-google-2026-09-15.md §7-2.
   ⚠ 옛 카카오 그래프는 **재현 불가능하다**(Bronze 를 없앴고 재수집은 약관 위반).
   그러므로 **대조군을 만들 수 없다** — 이 재학습은 새 기준선 수립이다.

2. 현행 서빙 산출물의 metrics(= 옛 카카오 그래프, 유일한 기록):
     nodes 47,442 · edges_used 188,673 · features 117 · classes 7 · label_level group
     test_top1 0.6494 · test_top3 0.9167 · macro_f1 0.2352
     test_offprior_top3 0.3383 · offprior_nodes 1,011
     baseline_district_prior_top1 0.6168 · baseline_district_prior_top3 0.8935
     lift_vs_district_prior_pct 5.3
     jipgyegu_features 0 · adong_hour_features 0 · neighbor_label_features 0

3. 계층별 거점사전 기준선(2026-08-17 실측,
   docs/finding-sequence-and-accuracy-2026-08-17.md §6):
     카카오 7종      Top-1 61.2% / Top-3 89.7%
     상가정보 대분류 10종  Top-1 34.0% / Top-3 69.9%
     상가정보 중분류 75종  Top-1 13.3% / Top-3 28.5%
     상가정보 소분류 247종 Top-1  8.8% / Top-3 20.1%
   → **어휘를 바꾸면 기준선이 같이 움직인다.** Top-3 만 보고 "떨어졌다"고 쓰면 오독이다.

4. **이미 실측으로 기각된 레버들이다. 다시 사지 말 것**:
   - 감성(블로그) — 공간 키가 district_id 하나뿐이라 거점 원핫과 **정보량 0**(증명).
     노드 귀속 3.18%이고 공실에는 원리적으로 없다 (feature-platform §0-K)
   - 행정동 시간블록 — +1.60%p, McNemar p=0.166 (유의하지 않다)
   - 집계구 시간블록 — +2.05%p, McNemar p=0.111 (유의하지 않다).
     행정동 vs 집계구는 p=0.777 로 **구별 불가**
   - 이웃 업종 분포(--neighbor) — off-prior −1.14%p (1σ 이내). 기본 off 유지
   - --class-weight — macro-F1 +7.6% 뿐인데 top-1 이 0.64→0.28 로 무너진다
   ⚠ n=877~1,011 표본은 검정력이 낮아 **3~4%p 아래 차이는 원리적으로 못 잰다.**
     '유의하지 않다'는 '차이가 없다'가 아니라 '이 표본으로는 못 가른다'는 뜻이다.

5. CLI 는 이미 필요한 것을 다 갖고 있다(ml/training/train_gnn.py):
     --no-save --label-level group|category2 --epochs --patience --hidden
     --select-by --dump-preds --edge-types --no-resume --ckpt-every
     --neighbor --adong --jipgyegu --no-demand --no-building --class-weight --report
   `train()` 은 두 가드로 **저장을 강제로 끈다** — `if save and class_weight:` 와
   `if save and label_level != "group":` (2026-09-15 기준 853·859행. 줄번호는 밀리니
   조건문으로 찾을 것). 체크포인트 재개는 내장이다.

## 해야 할 일

### 0단계 — 선행 확인 (건너뛰면 라벨이 틀린 모델이 나온다)

   docs/prompt-store-taxonomy-scls-2026-09-15.md 가 끝났는가?
   `편의점`·`약국`·`커피전문점` 소분류 문자열이 실측으로 확정됐는가?
   안 됐으면 **여기서 멈추고** 그 작업을 먼저 한다.

   python -m data.config.store_taxonomy --audit     # 사상률 확인

### 1단계 — Gold·사이드카 재생성 (node_id 가 갈렸으므로 순서가 중요하다)

   python -m data.pipelines.build_gold --platform13
   python -m data.pipelines.build_store_graph_edges --platform13
   python -m data.pipelines.build_page_building_features
   python -m data.pipelines.build_node_jipgyegu
   python -m pytest data/tests -q

   ⚠ 사이드카를 안 만들면 조인이 전부 빈다. 조용하지는 않다 — train_gnn 이
     "집계구 귀속 0건" 경고를 찍고 건너뛴다.
   ⚠ 1단계가 program_content_context.csv 66개를 통째로 다시 쓴다(정상이다).

### 2단계 — 라벨 어휘 3안을 **저장 없이** 재 본다

   상가정보는 가두 점포 **전체**를 준다. 7종에 사상되지 않는 업종(소매·교육·미용 등)은
   category_group 이 공란이라 `_labels` 가 '미분류' 클래스로 받는다. 그래서 선택이 생긴다:

   (a) 7종 + 미분류 = 8클래스   — 코드 기본 동작. 미분류가 최대 클래스가 될 수 있다
   (b) 7종만 (미분류 노드 제외) — 옛 모집단에 가장 가깝다. 카카오 수집이 그 7개
       카테고리만 골라 받았으므로, 모집단을 맞추면 수치가 그래도 읽힌다
   (c) 상가정보 대분류 10종     — 새 체계. 기준선 Top-3 69.9%

   **셋 다 `--no-save` 로 돌려 수치만 표로 만든다.** 어느 것도 아직 저장하지 않는다.

   mkdir -p reports/preds                    # reports/* 는 gitignore — 새 클론에는 없다
   OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8 python -u -m ml.training.train_gnn \
     --epochs 600 --patience 80 --no-save --dump-preds reports/preds/gnn_a_$(date +%Y%m%d).json

   ⚠ `OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8` 는 생략하지 말 것(CLAUDE.md) — 스레드를
     풀면 이 환경에서 메모리가 터지고, 인코딩을 빼면 로그 리다이렉트가 cp949 에서 죽는다.

   ⚠ (b)는 **코드가 없다.** `_labels` 가 미분류를 클래스로 만들고, 노드를 빼면
     `_edge_index` 가 그 노드를 참조하는 엣지를 버려야 한다. 이 필터를 구현하는 것이
     이 작업의 실제 과제다 — `--label-level` 에 새 값을 더하는 형태가 자연스럽다
     (예: `group_mapped`). 저장 게이트(`if save and label_level != "group":`)도
     같이 손대야 한다 — 없애지 말고 허용 목록에 더한다.
   ⚠ (c)는 category_group_src(indsLclsNm) 컬럼을 라벨로 쓰면 된다 — 노드 테이블에
     이미 있다(재수집 불필요, build_gold `_store_node_rows` 참조).

### 3단계 — 어휘를 결정하고 근거를 적는다

   표에 최소 이것들을 넣는다: classes · nodes · test_top1 · test_top3 · macro_f1 ·
   test_offprior_top3 · offprior_nodes · **그 어휘의 거점사전 기준선**(3항 표).
   Top-3 는 기준선과 **나란히** 적는다 — 기준선 없는 Top-3 는 읽을 수 없는 수치다.

   판단 기준:
   - KPI(`scripts/pppp_status.py`)는 `metrics.test_top3 ≥ 0.70` 을 본다
   - off-prior Top-3 는 **2026-08-26 에 게이트가 폐기됐다** — 관측만 한다(임계 50%)
   - 서빙 응답의 업종명이 바뀌는가(체크포인트 `classes`). 바뀌면 프론트 확인이 필요하다

### 4단계 — 저장하고 서빙을 확인한다

   먼저 옛 산출물을 백업한다(되돌릴 길을 만든 뒤에 덮는다):

     cp data/gold/platform_industry_recommend.json \
        reports/platform_industry_recommend_kakao_backup.json

   그다음 결정한 어휘로 저장 런을 돌리고:

     python scripts/pppp_status.py
     cd apps/backend && .venv/bin/python -m pytest -q
     # /api/v1/ai/recommend-industry 가 **모든 서빙 거점**에서 200 인지
     #   (2026-07-24 에 이 단계를 빠뜨려 33거점 확장 때 신규 거점이 404 였다)

### 5단계 — 기록

   - docs/finding-map-provider-google-2026-09-15.md §7-2-1(남은 노출)을 **해소로** 갱신
   - §7-2-3(어휘·게이트 재산정)에 결정과 근거를 적는다
   - docs/feature-platform.md 의 "GNN 업종 추천" 절 머리말 경고를 실측값으로 교체
   - reports/ 에 세 어휘의 수치표와 예측 덤프를 남긴다

## 완료 기준

- 세 어휘(a·b·c)의 수치표가 **각 어휘의 거점사전 기준선과 나란히** 남았다
- 어휘 결정의 근거가 문서에 적혔고, 저장 런의 metrics 가 그 어휘와 일치한다
- 옛 서빙 산출물이 reports/ 에 백업됐다
- 통과 조건:

      python -m pytest data/tests -q                      # 전건
      cd apps/backend && .venv/bin/python -m pytest -q    # 전건
      python scripts/pppp_status.py                        # KPI Top-3 ≥ 70%
      python scripts/run_full_verify.py                    # 정적 3종

## 금지 사항

- **대조군 없이 "올랐다/떨어졌다"고 쓰지 말 것.** 옛 카카오 그래프는 재현 불가능하다
  (Bronze 를 없앴다). 어휘·모집단이 다른 수치를 회귀로 읽으면 2026-08-26 과 같은
  잘못된 판정이 된다 — 그때는 낡은 기준선 때문에 기각이 뒤집혔다
- **4항의 기각된 레버를 다시 사지 말 것** — 감성·행정동·집계구·--neighbor·--class-weight.
  근거가 실측으로 남아 있다(일부는 증명이라 표본을 늘려도 안 풀린다)
- **7종 라벨 문자열을 바꾸지 말 것** — 체크포인트 `classes` 와 어긋나면 서빙 업종명이
  조용히 바뀐다. 어휘를 (c)로 갈 때는 그 변경을 **문서에 명시**하고 프론트를 확인한다
- **백업 없이 platform_industry_recommend.json 을 덮지 말 것**(4단계)
- **--label-level category2 로 저장하려 하지 말 것** — 코드가 강제로 끈다. 그건 버그가
  아니라 서빙 어휘 보호 장치다(`if save and label_level != "group":`). (b)안을 넣을 때
  그 가드를 **없애지 말고** 새 어휘를 허용 목록에 더하는 형태로 손볼 것
- **카카오 로컬을 되살리지 말 것** — 응답 저장은 약관 위반이다.
  data/tests/test_store_taxonomy.py 의 불변식 테스트가 막고 있다
- **한 런으로 결론 내지 말 것** — SEED=42 고정이라 재현은 되지만, 3~4%p 아래 차이는
  n≈1,000 표본으로 못 가른다. 쌍대 비교가 필요하면 --dump-preds 로 예측을 남기고
  scripts/mcnemar_gnn_arms.py 를 쓴다
```

---

## Codex 로 내보낼 수 있는가 — 4항목 점검

`.claude/skills/codex-handoff` 기준으로 **두 칸이 빈다. 내보내지 않는다.**

| 항목 | 상태 |
|---|---|
| 대상 파일 | ⚠ 2단계 (b)안의 필터를 어디에 넣을지가 설계다(`_labels` · `_edge_index` · 저장 게이트) |
| 입력 소스·출처 표기 | ✅ 확정 |
| 통과 조건 | ✅ 4개 |
| 금지 사항 | ⚠ 형식은 찼지만 **어휘 결정 자체가 판단**이다 — 위임 대상이 아니다 |

1·4번이 판단을 품고 있으므로 **Claude Code 몫**이다. 1단계(Gold·사이드카 재생성)만
떼면 명세가 확정되지만 명령 네 줄이라 나눌 이득이 없다.

## 왜 소분류 실측이 먼저인가

재학습은 **라벨을 고정한 뒤에** 하는 일이다. 지금은 `편의점`·`약국`·`커피전문점`
세 규칙이 미검증 추측이라, 그 상태로 돌리면 세 클래스의 라벨이 틀린 채로 학습된다.
그러면 다시 돌려야 하고, GNN 런은 600epoch 짜리다.

순서는 **소분류 실측 → 어휘 결정 → 재학습** 이고, 이 문서는 그 마지막 칸이다.

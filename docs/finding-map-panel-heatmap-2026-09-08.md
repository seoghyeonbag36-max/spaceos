# finding — map 탭 회귀 실패 2건 판정 (C4)

- 날짜: 2026-09-08
- 브랜치: `claude/map-panel-heatmap-regression-v6ros1` (지시받은 이름은
  `chore/cloud-c4-map-panel-and-heatmap` — 세션에 고정된 개발 브랜치가 위 이름이라 그쪽으로 냈다)
- 성격: **판정만.** `apps/` 아래 소스와 `scripts/screen_loop.py` 를 한 줄도 고치지 않았다.
  이 문서 하나만 추가한다.
- 방법: 코드 정독 + **백엔드 인프로세스 실측**(`app.services.districts` · `building_vacancy`
  를 그대로 불러 값을 읽었다). 화면은 띄우지 않았다 — 이 문서에 "고쳤다/빨라졌다"류의
  측정하지 않은 주장은 없다.
- 선행 문서: [finding-map-hubswitch-2026-09-08.md](finding-map-hubswitch-2026-09-08.md) (C1).
  같은 실행에서 나온 `render_ms` 단조 증가를 다룬다. 이 문서는 그 실행의 **판정 실패 2건**을
  본다.

---

## 0. 한 줄 결론

| # | 관측 | 판정 | 한 줄 근거 |
|---|---|---|---|
| (가) | `/heatmap/buildings?district=hapjeong` 를 부르지 않았다 | **A — 제품 결손** | `hapjeong` 은 합성 거점이 아니라 **Gold Tier1(292동)** 이고, 설령 합성이어도 이 문구는 나올 수 없다(§2-2) |
| (나) | `.mapshell .sp-head .sp-title` 이 0개 | **판정 불가 — 단 (B)는 아니다** | `sp-title` 은 **데이터와 무관하게 무조건** 렌더된다(§3-1). 명세가 요구하는 값이 맞다. 0개가 된 경위는 리포트 한 필드로 갈리는데 그 파일이 이 저장소에 없다(§3-4) |

**명세(`scripts/screen_loop.py`)는 두 건 모두 고칠 것이 없다** — §4.

---

## 1. 이 문서가 보지 못한 것

`reports/screen_loop.json` 은 이 저장소에 없다(커밋된 적이 없고 PC 의 다른 세션에
미커밋으로 있다). 그래서:

- 어느 조합이 어떤 실패를 냈는지, 같은 조합에 다른 실패가 같이 있었는지 **모른다.**
- (가)와 (나)가 **같은 조합**의 것인지도 모른다. 아래 판정은 그것에 기대지 않도록 썼다 —
  각 문구가 나오려면 검사기가 어떤 상태를 통과해야 하는지를 코드에서 거꾸로 짚었다.

---

## 2. (가) "거점을 바꿨는데 `/heatmap/buildings?district=hapjeong` 를 부르지 않았다"

### 2-1. `hapjeong` 이 어떤 거점인가 — 실측

`apps/backend/.venv` 파이썬으로 서비스를 그대로 불러 읽었다:

```
PAGES total 66 | hapjeong idx 14
list_summaries(): 66곳 · 그중 vacancy_source == "gold" 인 곳 66곳(전부)
hapjeong: {'vacancy_source': 'gold', 'vacancy_rate': 10.7, 'building_count': 149,
           'precision_pct': 62.1, 'anchor_pct': 8.1, 'caveat': '', 'vacancy_withheld': False}
building_vacancy_geojson('hapjeong') → features 292
```

- 등록: [data/config/page_hubs.py:65](../data/config/page_hubs.py#L65) (서울 · 마포)
- 시드: [seoul_pages.py:265](../apps/backend/app/data/seoul_pages.py#L265)
- Gold: `data/gold/hapjeong/coverage.json` — `tier: "Tier1(대장)"` · `shown: 292`
- 즉 **`/heatmap/buildings?district=hapjeong` 는 200 에 292 features 를 낸다.** 404 가 아니다.

### 2-2. "합성 거점이면 404 라 건너뛴다"는 분기가 이 관측을 설명하는가 — **아니다** (세 겹)

지목된 주석은 [MapShell.tsx:10](../apps/frontend/src/pages/MapShell.tsx#L10) ·
[:152-153](../apps/frontend/src/pages/MapShell.tsx#L152) 이고, 실제 분기는
[:166-167](../apps/frontend/src/pages/MapShell.tsx#L166) 의
`all.filter(d => d.vacancy_source === "gold")` 하나뿐이다.

1. **그 분기는 목록만 거른다. 호출을 거르는 분기는 없다.**
   건물 조회 이펙트([:176-183](../apps/frontend/src/pages/MapShell.tsx#L176))는
   `districtId` 가 바뀌면 **조건 없이** `getBuildingVacancy(districtId)` 를 부른다.
   `hub` 를 보지도, `vacancy_source` 를 보지도 않는다.
2. **`hapjeong` 은 그 필터에 걸리지 않는다.** 서빙 66거점이 전부 `gold` 라 필터가
   지우는 거점이 지금 하나도 없다(§2-1). 즉 옵션 목록에 그대로 있다.
3. **설령 걸렸더라도 이 문구는 안 나온다.** 검사기는 옵션이 없으면 고르지 않고
   `trigger="missing-option"` 으로 지나가며([screen_loop.py:466-468](../scripts/screen_loop.py#L466))
   `gate_seen` 은 `None` 으로 남는다([:463](../scripts/screen_loop.py#L463)).
   그때 나오는 문구는 **"거점 선택이 안 걸렸다"**([:569](../scripts/screen_loop.py#L569))이지
   "부르지 않았다"([:575-576](../scripts/screen_loop.py#L575))가 아니다.
   → 이 문구는 **옵션이 있었고 `select_option` 이 실제로 걸렸을 때만** 나온다.
4. (덤) **404 자체도 이 문구를 만들지 못한다.** 게이트는 응답 이벤트를 기다릴 뿐이라
   404 도 `gate_seen = "404"` 로 잡힌다([:477-481](../scripts/screen_loop.py#L477)).
   "합성 → 404" 이야기는 어느 쪽으로 굴려도 이 관측에 닿지 않는다.

### 2-3. 그래서 남는 읽기

옵션이 있었고, 거점이 실제로 바뀌었고, 그럼에도 **15초([screen_loop.py:109](../scripts/screen_loop.py#L109))
안에 그 요청의 응답이 한 번도 오지 않았다.** URL 은 문자열로 정확히 겹친다 —
프론트가 만드는 것은 `/api/v1/heatmap/buildings?district=hapjeong`
([api.ts:3](../apps/frontend/src/lib/api.ts#L3) · [:313-314](../apps/frontend/src/lib/api.ts#L313))이고
게이트 조각은 그 부분문자열이다([screen_loop.py:191](../scripts/screen_loop.py#L191)).
`api.ts` 에 캐시가 없어 "이미 받아서 안 부른다"도 성립하지 않는다.

남는 것은 하나다: **`select_option` 이후 15초 동안 요청이 나가지 못했다.**
`setDistrictId` → 커밋 → 이펙트 → `fetch` 사슬이 그 시간 안에 못 돈 것이고,
그것은 검사기가 아니라 **앱 쪽**이다. → **(A) 제품 결손.**

### 2-4. C1 과 맞물리는 자리 (같은 실행, 같은 뿌리로 읽힌다)

- `hapjeong` 은 `PAGES` 순서 **14번째**다(§2-1). C1 이 받은 `render_ms` 는
  13번째까지 13,234ms → **234,687ms** 로 단조 증가했다(C1 §1-1).
  즉 이 조합은 **이미 메인스레드가 수 분 단위로 막혀 있던 지점 바로 다음**이다.
- map 탭은 조합마다 `districtId` 가 `garosugil` 로 되감기고(C1 §4-D ·
  [MapShell.tsx:155](../apps/frontend/src/pages/MapShell.tsx#L155)),
  거점을 바꾸기 **전에** 840동을 한 번 다 그린다. 그 위에 C1 §3-B 의
  짝 없는 클릭 리스너가 세션 내내 쌓인다.
- 다만 **"리스너가 쌓여서 15초를 넘겼다"는 이 저장소에서 확정되지 않는다**(C1 §6-3 그대로).
  확정되는 것은 여기까지다 — 요청이 안 나갔고, 명세는 그것을 옳게 잡았다.

---

## 3. (나) "`.mapshell .sp-head .sp-title` 이(가) 0개"

### 3-1. `sp-head` · `sp-title` 은 언제 렌더되는가 — **무조건**

[MapShell.tsx:391-396](../apps/frontend/src/pages/MapShell.tsx#L391):

```
<div className="overlay side-panel">      ← 조건 없음
  <div className="sp-head">               ← 조건 없음
    <div className="sp-track">…
    <div className="sp-title">{hub?.name ?? "가로수길"} · 건물 공실</div>
```

`.mapshell` 루트([:370](../apps/frontend/src/pages/MapShell.tsx#L370))가 있으면
`.sp-head`·`.sp-title` 도 반드시 있다. 데이터 게이트도, `hub` 게이트도 없다 —
`hub` 가 `undefined` 면 `"가로수길 · 건물 공실"` 로 떨어질 뿐 노드는 그대로다.
이 성질은 C1 도 같은 줄에서 읽었다(C1 §2-2: "`.sp-title` 은 `hub` 메모가 바뀌는 즉시").

### 3-2. 데이터가 비었을 때

- 건물이 0동이어도 `.sp-title` 은 그대로. 비는 것은 `.sp-list` 안의 `.b-item` 뿐이다
  ([:411-412](../apps/frontend/src/pages/MapShell.tsx#L411)).
- API 실패 폴백은 목록을 **비우지 않는다** — 로컬 샘플 8건으로 채우고
  `.sp-sub` 를 `"샘플(추정)"` 로 바꾼다([:179-181](../apps/frontend/src/pages/MapShell.tsx#L179) ·
  [:398](../apps/frontend/src/pages/MapShell.tsx#L398)). 그 자리를 잡는 명세 노드는
  `.sp-sub` 의 `contains="실측"` 이고([screen_loop.py:196-197](../scripts/screen_loop.py#L196)),
  이건 `.sp-title` 과 무관하다.

→ **"데이터가 비어서 sp-title 이 없다"는 성립하지 않는다.** 명세가 요구하는
`min_count=1` 은 화면의 실제 계약과 일치한다. **(B) 명세 오류가 아니다.**

### 3-3. 그럼 0개는 언제 나오는가 — 두 갈래뿐

검사기는 이 노드를 재기 전에 이미 `.mapshell` 이 **보이는 것**을 확인했다
([screen_loop.py:410-418](../scripts/screen_loop.py#L410), `open_tab`). 그리고 `count()` 는
가시성이 아니라 **DOM 존재**를 센다([:443](../scripts/screen_loop.py#L443)).
그러므로 0개는 둘 중 하나다:

1. **읽는 순간 `.mapshell` 서브트리가 DOM 에 없었다.**
   MapShell 은 탭이 map 이 아니거나([App.tsx:119](../apps/frontend/src/App.tsx#L119)),
   MapHost 가 비활성일 때([MapHost.tsx:105](../apps/frontend/src/components/MapHost.tsx#L105))
   아예 언마운트된다. 조합 도중 그렇게 되려면 React 루트가 통째로 무너지거나
   (에러 바운더리가 없다 — 잡히지 않은 예외는 루트를 내린다) 개발서버 HMR 로
   모듈이 갈렸거나 해야 한다.
   ⚠ 이 갈래라면 **같은 조합에서 `.sp-sub`·`.b-item` 도 0개**여야 하고
   (같은 서브트리다), 십중팔구 S1 `pageerror` 도 같이 찍힌다.
2. **노드를 재지 못했다.** `count()`/`inner_text()` 가 예외를 내면 검사기는 그것을
   실패로 세지 않고 **`count: 0` · `text: "[selector-error] …"` 로 적어 판정에 넘긴다**
   ([screen_loop.py:444-446](../scripts/screen_loop.py#L444)). 페이지가 죽었거나
   왕복이 막힌 경우가 여기다 — (가)와 같은 뿌리가 된다.

### 3-4. 리포트 한 필드로 갈린다 (PC 에서 1분)

`reports/screen_loop.json` 에서:

```
results["<hub>|map"].obs.nodes[".mapshell .sp-head .sp-title"].text
```

- `"[selector-error] …"` 로 시작하면 → **갈래 2**. 노드가 없던 게 아니라 못 잰 것이고,
  (가)와 같은 원인(메인스레드/페이지 상태)으로 묶인다.
- 빈 문자열이면 → **갈래 1**. 그때는 같은 조합의 `.sp-sub`·`.b-item` 계수와
  `page_errors` 를 같이 본다. 셋이 다 0 이고 `pageerror` 가 있으면 **렌더 중 예외로
  루트가 내려간 것**이고, 그건 새 제품 결손이다(이 저장소의 데이터로는 재현되지 않는다 —
  Gold 마스터 73개의 `status` 값을 전수로 세었는데 `full/partial/high/empty` 밖의 값이
  **0개**라, `STATUS[b.status]` 가 터지는 경로는 배제된다).
- 스크린샷도 남아 있다: `reports/screens/<hub>__map.png`(실패 조합만 저장된다,
  [screen_loop.py:869-880](../scripts/screen_loop.py#L869)).

이 파일이 없으면 여기서 더 갈 수 없다. 그래서 **판정 불가**로 적는다 —
"아마 이것이다"로 A 를 붙이지 않는다.

---

## 4. 명세는 고칠 것이 없다 (C4_NO_SPEC_EDIT)

- (가) 게이트 `"/heatmap/buildings?district={hub}"`([screen_loop.py:191](../scripts/screen_loop.py#L191))는
  화면의 실제 계약과 일치한다 — 거점이 바뀌면 이 호출이 **반드시** 나가야 한다
  ([MapShell.tsx:176-183](../apps/frontend/src/pages/MapShell.tsx#L176)). 예외 분기가 없으므로
  "합성 거점은 봐준다" 같은 예외를 명세에 넣을 이유도 없다. 넣으면 그날로
  **진짜 미호출을 못 잡는 명세**가 된다.
- (나) `.mapshell .sp-head .sp-title ≥ 1` 도 화면의 계약과 일치한다(§3-1).
  데이터가 비어도 유지되는 노드라, 이 자리를 느슨하게 만들면 "패널이 통째로 사라진 화면"을
  통과시키게 된다.
- 리포트가 "없다"와 "못 쟀다"를 이미 구분해 적고 있다([:444-446](../scripts/screen_loop.py#L444)).
  §3-3 을 가르는 데 필요한 정보는 명세를 고치지 않아도 이미 남는다.

`scripts/screen_loop.py` 는 **변경 없음**. PC 에 다른 세션의 미커밋 변경이 있다는 전제도
그대로 지켰다.

---

## 5. 코드를 고치지 않은 이유

(가)는 A 로 판정했지만 **20줄 안쪽으로 "명확한" 수정이 아니다.**

- 눈에 보이는 결손은 C1 §3-B 의 짝 없는 클릭 리스너
  ([MapShell.tsx:291](../apps/frontend/src/pages/MapShell.tsx#L291) ·
  [:305](../apps/frontend/src/pages/MapShell.tsx#L305) ↔
  `clearOverlays` [:255-258](../apps/frontend/src/pages/MapShell.tsx#L255))이고,
  `clearInstanceListeners` 를 붙이는 수정 자체는 대여섯 줄이다.
- 그러나 **그것이 이 15초 게이트를 넘긴 원인이라는 것은 확정되지 않았다**(C1 §6-3).
  확정에는 힙 스냅샷 또는 페이지 리셋 A/B 가 필요하고(C1 §7-1·§7-4), 이 환경에는
  브라우저도 지도 키도 없어 고친 뒤 **좋아졌다고 말할 방법이 없다.**
- 근거 없는 값을 채우지 않는다는 이 저장소의 제1원칙(AGENTS.md §0)은 코드에도 걸린다 —
  "고쳤다"는 주장도 근거가 필요하다. 그래서 판정까지만 하고 멈춘다.

---

## 6. 다음 한 수 (PC, 결정 실험)

1. §3-4 의 한 필드를 읽는다 — (나)가 갈린다.
2. **새 페이지에서 `hapjeong` 만 단독으로 돈다.** 누적 가설의 직접 검정이고,
   기존 리포트를 건드리지 않게 `--out` 을 따로 준다:

   ```powershell
   py -3.11 scripts/screen_loop.py --hubs hapjeong --tabs map --fresh `
     --out reports/screen_loop_hapjeong.json
   ```

   - 게이트가 **통과**하면 → (가)는 그 거점의 문제가 아니라 **누적**이다(C1 §7-4 를 좁힌 형태).
   - 게이트가 **또 timeout** 이면 → 누적과 무관한 별도 결손이다. 그때는 첫 회
     13,234ms 의 내역부터 쪼갠다(C1 §7-5).
3. 그 결과가 나오면 C1 §7-1(힙 스냅샷)로 리스너 수정의 정당성을 확정한 뒤 고친다.

---

## 7. 통과 조건 대조

| 조건 | 결과 |
|---|---|
| `C4_VERDICT` | (가) **A** — §2 (`MapShell.tsx:166-167`·`:176-183` · `screen_loop.py:466-468`·`:569`·`:575-576`) / (나) **판정 불가, (B) 아님** — §3 (`MapShell.tsx:391-396`·`:411-412` · `screen_loop.py:443-446`) |
| `C4_BUILD` | **미실행** — 소스를 고치지 않았다. (`npm run build` 는 추적 파일 `apps/frontend/tsconfig.tsbuildinfo` 를 다시 쓰므로 금지 목록에 걸린다) |
| `C4_NO_SPEC_EDIT` | `scripts/screen_loop.py` **변경 없음** — §4 |

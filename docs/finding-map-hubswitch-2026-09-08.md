# finding — Page(map) 탭에서 거점을 바꿀수록 초기 렌더가 단조 증가한다

- 날짜: 2026-09-08
- 브랜치: `chore/cloud-c1-map-hubswitch-diagnosis`
- 성격: **진단만.** `apps/` 아래 소스는 한 줄도 고치지 않았다. 이 문서 하나만 추가한다.
- 방법: 코드 정독 + 저장소 안의 Gold 산출물 계수. **화면을 띄우지 않았다** —
  이 문서에는 측정하지 않은 "빨라졌다/고쳤다" 류의 주장이 없다.
- **추가 확인 2026-09-08** (브랜치 `claude/playwright-locator-count-timeout-62qboz`):
  §7-6 을 처리했다 — playwright 소스를 읽어 §2-1 의 전제를 확정했다(§2-1-1).
  **전제는 맞았고 234,687ms 의 해석은 그대로 선다.** 이번에도 화면은 띄우지 않았다.
  고친 것은 이 문서뿐이다.

> **2026-09-08 추가 — §9.** §6 의 누적 가설 중 "짝이 없다 → 전환마다 등록이 쌓인다"를
> 스텁 지도 위에서 계측해 **확정**하고, 짝을 붙였다. §1~§8 은 진단 당시 그대로 둔다.
> §9 도 ms 는 재지 않았다 — 실제 지도를 못 띄웠으므로 "빨라졌다"는 말은 여전히 없다.

---

## 0. 한 줄 결론

`MapShell` 이 거점마다 만드는 오버레이(건물 폴리곤·점)는 **`setMap(null)` 로 지도에서
떼기만 하고 그 위에 붙인 클릭 리스너를 떼지 않는다**
([MapShell.tsx:255-258](../apps/frontend/src/pages/MapShell.tsx#L255) ↔
[:291](../apps/frontend/src/pages/MapShell.tsx#L291) ·
[:305](../apps/frontend/src/pages/MapShell.tsx#L305)).
그 오버레이가 얹히는 지도는 **앱 수명 동안 죽지 않는 단 하나의 인스턴스**이고
([MapHost.tsx:69-85](../apps/frontend/src/components/MapHost.tsx#L69)),
회귀 루프는 페이지를 **한 번만 열고 264조합을 그 위에서 다 돈다**
([screen_loop.py:835](../scripts/screen_loop.py#L835)).
그래서 map 탭에서 만든 것만 세션 내내 쌓일 자리가 있다 —
Platform·Posting·Program 은 `naver` 를 **한 번도 참조하지 않으므로**(§4-A) 쌓일 자리가 없다.

**2026-09-08 저녁 실측 → §10.** 실제 지도에서 다시 쟀다. 앞 거점은 반으로 줄었지만
**계열은 여전히 자라고(rho +0.864) 예산 3,000ms 안에 든 hub-switch 는 0/11 이다.**
C2 는 누적의 한 갈래였을 뿐이다 — 남은 갈래는 L3 가 가른다.

단, "짝이 없다"까지가 코드로 확정되는 범위다. **"짝이 없어서 GC 되지 않는다"는
네이버 SDK 내부 동작이라 이 저장소에서 확정할 수 없다** — §6-1·§6-4 로 넘긴다.

---

## 1. 관측과 그 한계

### 1-1. 받은 숫자

map 탭 `hub-switch` 의 초기 렌더(ms, 관측 순서):

```
13234  18203  24172  29969  36234  37469  39422  40328
43218  43219  48046  48860  234687
```

- 예산은 **3,000ms** ([screen_loop.py:107](../scripts/screen_loop.py#L107), KPI "지도 로딩 3초").
  **첫 관측부터 이미 4.4배 초과**다. 누적은 그 위에 얹힌 별개의 문제다(§5-3).
- 같은 실행의 `tab-open` 은 **4,750~7,375ms** — 1.55배 폭 안에 머물렀다.
  같은 실행에서 hub-switch 는 **17.7배** 벌어졌다.
- Platform 탭 hub-switch 는 **6,172ms 한 건**뿐이다.

### 1-2. 한계 — 이 숫자로 할 수 없는 말

1. **264조합 중 69조합에서 중단된 실행이다.** 66거점을 한 바퀴 돈 결과가 아니다.
   조합 순서는 거점-major 다(`[(h, s) for h in hubs for s in specs]`,
   [screen_loop.py:808](../scripts/screen_loop.py#L808)) — 즉 거점 하나마다
   Platform→Page→Posting→Program 을 돌고 다음 거점으로 간다.
2. **`reports/screen_loop.json` 이 이 저장소에 없다.** 커밋된 적이 없고(PC 의 다른
   세션에 미커밋으로 있다), 이 세션은 그 파일을 만들지도 고치지도 않는다. 따라서
   **어느 숫자가 어느 거점인지 나는 모른다.** §2-3 의 대응은 *가정*이고 그렇게 표시했다.
3. 69 = 17거점 × 4탭 + 1 이므로 map 조합은 **17개**여야 하는데 hub-switch 값은 13개다.
   차이 4개(= tab-open 1개 + 관측이 남지 않은 3개)의 정체는 리포트 없이는 모른다.
   조합이 `status: "error"` 로 끝나면 `obs` 가 `{}` 라 `render_ms` 자체가 없다
   ([screen_loop.py:861-867](../scripts/screen_loop.py#L861)).
4. "tab-open 4,750~7,375ms" 를 나는 **조합마다 기록되는 `tab_open_ms`**
   ([screen_loop.py:459](../scripts/screen_loop.py#L459))의 범위로 읽었다. `trigger ==
   "tab-open"` 인 조합은 기본 거점 하나뿐이라 범위가 나올 수 없기 때문이다.
   이 독법이 틀리면 §5-2 의 판별 논거 하나가 무너진다 — §6-2 에서 확인할 것.

### 1-3. 저장소에서 직접 센 것 (이건 실측이다)

`data/gold/*/page_building_master.geojson` 의 feature 수 = map 탭이 한 거점에서 그리는
건물 수. 73개 디렉터리(서빙 66 + 경기 보류 7 — CLAUDE.md 의 "73 은 서빙 거점 수가
아니다"와 같은 수다):

| 통계 | 값 |
|---|---|
| 중앙값 | 635 |
| 평균 | 754 |
| 최대 | 2,813 (`dongdaemun`) |
| 최소 | 58 (`westerndom`, 보류) |
| 합계 | 55,037 |

> MapShell 주석의 "840~1,443동"([MapShell.tsx:46](../apps/frontend/src/pages/MapShell.tsx#L46))
> 은 낡았다. 실제 범위는 58~2,813 이다.

`app.services.districts.PAGES` 순서(= 루프가 도는 순서) 앞 18개:

| # | 거점 | 건물 | 누적 |
|---:|---|---:|---:|
| 0 | garosugil | 840 | 840 |
| 1 | apgujeong-rodeo | 769 | 1,609 |
| 2 | hongdae | 1,325 | 2,934 |
| 3 | yeonnam | 1,133 | 4,067 |
| 4 | ikseon | 1,748 | 5,815 |
| 5 | seochon | 846 | 6,661 |
| 6 | myeongdong | 1,084 | 7,745 |
| 7 | euljiro | 1,972 | 9,717 |
| 8 | seongsu | 831 | 10,548 |
| 9 | seoulsup | 698 | 11,246 |
| 10 | itaewon | 845 | 12,091 |
| 11 | hannam | 714 | 12,805 |
| 12 | songridan | 453 | 13,258 |
| 13 | gangnam | 987 | 14,245 |
| 14 | hapjeong | 292 | 14,537 |
| 15 | mangwon | 959 | 15,496 |
| 16 | samcheong | 614 | 16,110 |
| 17 | gwangjang | 1,742 | 17,852 |

---

## 2. 측정 창이 무엇을 재는가 — 먼저 이것부터

원인을 고르기 전에 `render_ms` 가 무엇의 시간인지 고정해야 한다. 아니면 브라우저가
느린 것과 검사기가 기다리는 것을 섞어 읽는다.

### 2-1. 창의 경계

`hub-switch` 의 `t0` 는 `select_option` **직전**이고, 끝은 명세 노드 3개를 다 읽은
뒤다([screen_loop.py:474](../scripts/screen_loop.py#L474) →
[:486-487](../scripts/screen_loop.py#L486)). 창 안에 들어오는 것:

| 순서 | 무엇 | 상한 |
|---|---|---|
| 1 | `expect_response("/heatmap/buildings?district=…")` + `select_option` | 15,000ms ([:109](../scripts/screen_loop.py#L109)) |
| 2 | 노드별 `wait_for(state="visible")` × 3 | 각 8,000ms ([:439](../scripts/screen_loop.py#L439)) |
| 3 | 노드별 `loc.count()` × 3 | **상한 없음** ([:443](../scripts/screen_loop.py#L443)) — 소스로 확인, §2-1-1 |
| 4 | 노드별 `inner_text()` × 3 | 각 8,000ms(기본값, [:832](../scripts/screen_loop.py#L832)) |

상한이 있는 것만 다 터져도 15,000 + 3×(8,000+8,000) = **63,000ms** 다.
관측이 43,000~48,000ms 에서 평평해지는 것은 이 천장에 붙은 모양이고,
**234,687ms 는 상한 있는 항목만으로는 나올 수 없다.** 3번(`count()`)처럼 상한이 없는
호출이 렌더러 메인스레드에 막혀 통째로 늘어졌다고 보는 것이 이 숫자에 맞는 유일한
읽기다.

### 2-1-1. `Locator.count()` 에 timeout 이 없다 — 소스로 확인했다 (§7-6 처리)

처음 이 문서는 "`count()` 에 timeout 인자가 없다"를 **기억에 따른 추측**으로 적고
확인을 §7-6 으로 넘겼다("이 환경에는 playwright 가 없다"). **그 환경 기술이 틀렸다** —
원격 세션에는 Node `playwright` 1.56.1 이 `/opt/node22/lib/node_modules/playwright` 에
설치돼 있다. 그 소스와 PyPI 의 Python 패키지를 읽어 확인했다. **전제는 맞았다.**

**Python 쪽 — 인자가 아예 없다.** `screen_loop.py` 가 쓰는 것이 이쪽이다
(아래 표는 PyPI 최신 `playwright` **1.62.0** 의 휠을 풀어 읽은 것이다).

| 자리 | 내용 |
|---|---|
| `playwright/_impl/_locator.py` | `async def count(self) -> int:` — **파라미터가 `self` 뿐이다** |
| `playwright/_impl/_frame.py` | `_query_count` 가 `send("queryCount", None, {"selector": selector})` — 두 번째 인자가 `timeout_calculator` 인데 **`None`** 이다 |
| `playwright/_impl/_connection.py` `_augment_params` | `timeout: float = 0` 으로 시작해 `if timeout_calculator:` 일 때만 값을 넣는다 → `None` 이므로 **0 이 그대로 서버로 간다** |

**드라이버(서버) 쪽 — 0 이면 타이머를 안 만든다.**

| 자리 | 내용 |
|---|---|
| 클라이언트 번들 | `_queryCount(selector) { … this._channel.queryCount({ selector }, kNoTimeout) }` — 상수 이름이 **`kNoTimeout`** 이고 그 값이 `{ signal: undefined, timeout: 0 }` 이다 |
| `dispatcher` | `controller.run(…, validMetadata.timeout)` (1.56 은 `validParams?.timeout`) |
| `ProgressController.run` | `const deadline = timeout ? monotonicTime() + timeout : 0;` → `if (deadline)` 안에서만 `setTimeout` 을 건다. **0 이면 타이머가 없다** |

Node 1.56.1 의 공개 타입도 같다 — `types.d.ts` 는 `count(): Promise<number>;` 로 **인자를
받지 않고**, `locator.js` 의 `async count(_options)` 위에는 `// options are only here for
testing` 이 붙어 있다. 형제 메서드들이 `timeout: this._frame._timeout(options)` 를 끼워
넣는 자리에서 `_queryCount` 만 **그것을 끼우지 않는다.**

버전 문제도 아니다. `playwright-python` **v1.40.0 · v1.48.0 · v1.54.0 · v1.58.0 · v1.62.0**
에서 `count()` 의 서명이 전부 같고(`self` 만 받는다), `_query_count` 도 전부 timeout 을
안 보낸다(1.40 은 인자 자체가 `send("queryCount", {"selector": …})` 로 timeout 자리가 없고,
1.54 부터가 위 표의 `None` 형태다). PC 가 어느 버전을 썼든 결론은 안 바뀐다.

여기서 따라오는 것 셋:

1. **`page.set_default_timeout(8000)`([screen_loop.py:832](../scripts/screen_loop.py#L832))이
   `count()` 에는 닿지 않는다.** 기본 타임아웃은 `TimeoutSettings` 를 거치는 호출에만
   붙는데 `count()` 는 그 경로를 통째로 건너뛴다. 같은 `wait_nodes` 안에서
   `wait_for`(명시 8,000ms)와 `inner_text`(기본 8,000ms)는 상한을 받고 `count()` 만 못 받는다.
2. **막히는 이유도 소스에 있다.** 드라이버의 `queryCount` 는
   `callOnSelector(selector, …, ({ elements }) => elements.length, {})` 로 **페이지 안에서
   셀렉터를 평가해 센다.** 렌더러 메인스레드가 바쁘면 이 평가가 큐에 걸린 채로 있고,
   끊어 줄 타이머가 없으니 호출이 통째로 늘어진다. §2-2 가 말한 그 모양이다.
3. **63,000ms 는 이제 추측이 아니라 상한이다.** 창 안에서 상한 없는 호출은 `count()` 3개
   뿐이므로(map 명세의 노드가 정확히 3개다 —
   [screen_loop.py:192-199](../scripts/screen_loop.py#L192)),
   **234,687 − 63,000 = 171,687ms 이상이 `count()` 안에서 렌더러를 기다린 시간**이다.
   이 최소 171.7초는 §5-후보6("측정계가 부풀렸다")으로 설명되지 않는다 — 타이머가 없는
   호출은 부풀릴 상한 자체가 없다. 부풀린 것이 아니라 **정말로 그만큼 막혀 있었다**는
   뜻이고, 그래서 후보 6 은 원인이 아니라 확대경이라는 §5 의 판정이 유지된다.

### 2-2. 그래서 이 숫자는 "렌더 시간"이 아니라 "메인스레드가 막혀 있던 시간"에 가깝다

명세 노드 3개 중 둘은 새 데이터를 기다리지 않아도 만족될 수 있다:
`.sp-title` 은 `hub` 메모가 바뀌는 즉시([MapShell.tsx:396](../apps/frontend/src/pages/MapShell.tsx#L396)),
`.b-item` 은 직전 거점의 행이 아직 남아 있어서
([:412](../apps/frontend/src/pages/MapShell.tsx#L412)). 그런데도 수십 초가 걸린다는 것은
**노드가 안 뜬 것이 아니라 Playwright 의 왕복 자체가 막혔다**는 뜻이다.
= 자바스크립트 메인스레드가 그동안 계속 바빴다. 원인 후보는 전부 이 관점에서 본다.

### 2-3. 시간이 "그 거점의 크기"를 따라가지 않는다 (가정 위의 계산)

13개 숫자가 PAGES 순서의 거점 1~13 에 그대로 대응한다고 **가정**하면:

| 거점 | 건물 | render_ms |
|---|---:|---:|
| apgujeong-rodeo | 769 | 13,234 |
| hongdae | 1,325 | 18,203 |
| yeonnam | 1,133 | 24,172 |
| ikseon | 1,748 | 29,969 |
| seochon | 846 | 36,234 |
| myeongdong | 1,084 | 37,469 |
| euljiro | **1,972** | 39,422 |
| seongsu | 831 | 40,328 |
| seoulsup | 698 | 43,218 |
| itaewon | 845 | 43,219 |
| hannam | 714 | 48,046 |
| songridan | **453** | 48,860 |
| gangnam | 987 | 234,687 |

Spearman(render_ms, 그 거점 건물 수) = **-0.473** (음수다).
가장 큰 거점(euljiro 1,972동)이 39초, 가장 작은 거점(songridan 453동)이 49초다.

**이 결론은 위 가정에 크게 기대지 않는다.** 어떤 대응이든 거점 1~17 의 건물 수는
292~1,972 사이(6.75배)에서 오르내리는데 PAGES 순서로는 단조가 아니고, 관측은 단조로
17.7배 벌어졌다. 즉 **"어떤 거점은 원래 크다"로는 이 모양이 안 나온다.**
시간을 결정하는 것은 그 거점이 무엇인지가 아니라 **몇 번째로 열렸는지**다.

---

## 3. 거점(districtId)이 바뀔 때 — 생성/정리 대응표

`districtId` 가 바뀌면 도는 이펙트를 전부 짝지었다. 짝이 없는 칸이 후보다.

### 3-A. naver.maps 오버레이

| 만드는 자리 | 지우는 자리 | 짝 |
|---|---|---|
| `Marker`(공실의심 점) [MapShell.tsx:284-290](../apps/frontend/src/pages/MapShell.tsx#L284) | `clearOverlays()` 의 `o.setMap(null)` [:256](../apps/frontend/src/pages/MapShell.tsx#L256) | ⚠ **떼기만 한다.** `destroy()`·`clearInstanceListeners()` 없음 |
| `Polygon`(건물 footprint) [:298-304](../apps/frontend/src/pages/MapShell.tsx#L298) | 같음 | ⚠ 같음 |
| `Polygon`(density 셀) [:339-342](../apps/frontend/src/pages/MapShell.tsx#L339) | 같음 | ⚠ 같음 (루프에서는 안 그림 — 기본 레이어가 vacancy) |
| `Polygon`(rent 셀) [:357-361](../apps/frontend/src/pages/MapShell.tsx#L357) | 같음 | ⚠ 같음 (루프에서는 안 그림) |
| `Circle`(HeatMap 폴백) [:323-326](../apps/frontend/src/pages/MapShell.tsx#L323) | 같음 | ⚠ 같음 (루프에서는 안 그림) |

`overlaysRef` 배열 자체는 매번 비워지므로([:257](../apps/frontend/src/pages/MapShell.tsx#L257))
**MapShell 쪽 참조는 확실히 끊긴다.** 남는 참조가 있다면 SDK 쪽이다(§3-B).

### 3-B. 이벤트 리스너 — **여기가 유일하게 짝이 비어 있다**

| 만드는 자리 | 지우는 자리 | 짝 |
|---|---|---|
| `Event.addListener(map, "zoom_changed")` [:251](../apps/frontend/src/pages/MapShell.tsx#L251) | `Event.removeListener(h)` [:252](../apps/frontend/src/pages/MapShell.tsx#L252) | ✅ |
| `Event.addListener(dot, "click", () => focus(b))` [:291](../apps/frontend/src/pages/MapShell.tsx#L291) | **없다** | ❌ |
| `Event.addListener(poly, "click", () => focus(b))` [:305](../apps/frontend/src/pages/MapShell.tsx#L305) | **없다** | ❌ |

핸들을 변수에 받지도 않는다. 리스너 클로저는 `focus`(→ `map`, `setSelected`)와
**`b` 를 통째로** 붙잡는다. `b` 는 `ring`(좌표쌍 배열)까지 든 `Building` 이다
([:62-69](../apps/frontend/src/pages/MapShell.tsx#L62) ·
[:96-109](../apps/frontend/src/pages/MapShell.tsx#L96)).

대조군이 저장소 안에 있다 — **같은 지도를 쓰는 `HubExplorer` 는 이 문제가 없다.**
경계 폴리곤을 `clickable: false` 로 만들어 리스너를 아예 안 붙이고
([HubExplorer.tsx:157](../apps/frontend/src/pages/HubExplorer.tsx#L157)),
같은 이펙트에 정리 함수를 달아 둔다([:182-185](../apps/frontend/src/pages/HubExplorer.tsx#L182)).
`MapShell` 의 재그리기 이펙트에는 **정리 함수가 아예 없다**
([:271-365](../apps/frontend/src/pages/MapShell.tsx#L271)) — 다음 실행의 첫 줄
`clearOverlays()`([:274](../apps/frontend/src/pages/MapShell.tsx#L274))가 그 역할을 대신하고,
언마운트는 별도 이펙트([:262](../apps/frontend/src/pages/MapShell.tsx#L262))가 받는다.

### 3-C. heatmap 인스턴스

| 만드는 자리 | 지우는 자리 | 짝 |
|---|---|---|
| `visualization.HeatMap` [:316-319](../apps/frontend/src/pages/MapShell.tsx#L316) | `overlaysRef` 에 push 후 `setMap(null)` [:320](../apps/frontend/src/pages/MapShell.tsx#L320) | ⚠ 형식상 짝은 있으나 **이번 실행과 무관** — `layer` 기본값이 `"vacancy"`([:138](../apps/frontend/src/pages/MapShell.tsx#L138))이고 루프는 레이어를 바꾸지 않는다 |

**이번 관측의 원인이 아니다.** 검사기가 유동/밀도/임대 레이어를 누르지 않기 때문이다.

### 3-D. 거리뷰 파노라마

| 만드는 자리 | 지우는 자리 | 짝 |
|---|---|---|
| `new naver.maps.Panorama` [naverMap.ts:129-134](../apps/frontend/src/lib/naverMap.ts#L129) | `destroy()` [:135](../apps/frontend/src/lib/naverMap.ts#L135), 호출부 [BuildingViewer.tsx:140](../apps/frontend/src/components/BuildingViewer.tsx#L140) | ✅ |
| `Event.addListener(pano, 'pano_status'/'init')` [:138](../apps/frontend/src/lib/naverMap.ts#L138)·[:145](../apps/frontend/src/lib/naverMap.ts#L145) | **없다** (`destroy()` 가 대신 정리한다고 전제) | ⚠ |
| 두 이벤트가 **하나도 안 오면** Promise 가 영영 안 풀린다 [:127-164](../apps/frontend/src/lib/naverMap.ts#L127) | 없음(타임아웃 없음) | ⚠ |

**이번 관측의 원인이 아니다.** 검사기는 `.b-twin` 을 누르지 않는다 —
`detail_click` 은 목록 첫 행만 누르고([screen_loop.py:500-511](../scripts/screen_loop.py#L500)),
층 스택·거리뷰는 이 루프의 경계 밖이라고 명시돼 있다([screen_loop.py:70-71](../scripts/screen_loop.py#L70)).
그래도 짝이 빈 자리라 적어 둔다.

### 3-E. 비동기 응답

| 만드는 자리 | 지우는 자리 | 짝 |
|---|---|---|
| `listDistricts()` [MapShell.tsx:161-173](../apps/frontend/src/pages/MapShell.tsx#L161) | `alive=false` 만 | ⚠ 요청은 계속 간다 |
| `getBuildingVacancy(districtId)` [:176-183](../apps/frontend/src/pages/MapShell.tsx#L176) | `alive=false` 만 | ⚠ 같음 |
| `getRentHeatmap(districtId)` [:185-192](../apps/frontend/src/pages/MapShell.tsx#L185) | `alive=false` 만 | ⚠ 같음 + **레이어 가드가 없다**(§4-C) |
| `getFootfallHeatmap` [:196-203](../apps/frontend/src/pages/MapShell.tsx#L196) | `alive=false` + `layer` 가드 | ✅ |
| `getDensityHeatmap` [:205-212](../apps/frontend/src/pages/MapShell.tsx#L205) | `alive=false` + `layer` 가드 | ✅ |
| `recommendIndustry` [:222-235](../apps/frontend/src/pages/MapShell.tsx#L222) | `alive=false` 만 | ⚠ |

`api.ts` 전체에 `AbortController` 가 **0개**다(`fetch` 호출은
[api.ts:11](../apps/frontend/src/lib/api.ts#L11)·[:17](../apps/frontend/src/lib/api.ts#L17)·[:31](../apps/frontend/src/lib/api.ts#L31)·[:424](../apps/frontend/src/lib/api.ts#L424) 넷뿐이고
넷 다 `signal` 을 안 받는다). `alive` 플래그는 **setState 만 막고 요청은 못 막는다.**
루프는 조합을 직렬로 돌아 동시 요청이 1~2개뿐이므로 **이번 관측의 주범은 아니다.**

### 3-F. React 컴포넌트·DOM

| 만드는 자리 | 지우는 자리 | 짝 |
|---|---|---|
| 지도 인스턴스 [MapHost.tsx:76-81](../apps/frontend/src/components/MapHost.tsx#L76) | **없다 — 의도적으로 앱 수명 동안 산다** | ✅(설계) / ⚠(이 문제의 무대) |
| `MapShell` 마운트/언마운트 [App.tsx:119](../apps/frontend/src/App.tsx#L119) + [MapHost.tsx:105](../apps/frontend/src/components/MapHost.tsx#L105) | 언마운트 시 `clearOverlays` [MapShell.tsx:262](../apps/frontend/src/pages/MapShell.tsx#L262) | ✅ |
| 목록 행 `.b-item` × 전체 건물 수 [:412-425](../apps/frontend/src/pages/MapShell.tsx#L412) | React 가 뗀다 | ✅ (가상화 없음 → 매번 수천 노드 커밋) |

---

## 4. map 탭에서만 생기는 이유 (비대칭의 근거)

### 4-A. 다른 탭은 지도를 건드리지 않는다 (실측)

```
PlatformConsole.tsx   naver 참조 0회
PostingConsole.tsx    naver 참조 0회
ProgramStudio.tsx     naver 참조 0회
SeoulDashboard.tsx    naver 참조 0회
```

`naver` 를 쓰는 화면은 `MapShell` · `HubExplorer` · `PageDashboard` 셋뿐인데,
`HubExplorer`(거점 탭)는 루프의 탭 명세에 없고([screen_loop.py:166-225](../scripts/screen_loop.py#L166)),
`PageDashboard` 는 `#board` 해시로만 열린다([App.tsx:80](../apps/frontend/src/App.tsx#L80)).
**이번 실행에서 지도를 만진 화면은 `MapShell` 하나뿐이다.**

### 4-B. map 탭만 "컴포넌트보다 오래 사는 것"에 쓴다

Platform 탭이 거점을 바꾸면 만든 것이 전부 그 컴포넌트의 DOM 안에 있고, 탭을 떠나면
React 가 통째로 뗀다. map 탭이 거점을 바꾸면 만든 것이 **MapHost 의 지도 위에** 얹힌다.
지도는 안 죽는다([MapHost.tsx:69-85](../apps/frontend/src/components/MapHost.tsx#L69)).
페이지도 안 죽는다(`page.goto` 는 실행당 1회, [screen_loop.py:835](../scripts/screen_loop.py#L835)).
**쌓일 자리가 map 탭에만 있다.**

### 4-C. 거점 하나 바꿀 때 오버레이를 3~4번 다시 그린다

재그리기 이펙트의 의존성 배열([:365](../apps/frontend/src/pages/MapShell.tsx#L365)):

```
[layer, pinMode, ready, map, buildings, rentHm, footHm, densHm, center.lat, center.lng]
```

`setDistrictId` 하나로 이 중 여러 개가 순차로 바뀐다:

1. `hub` 메모 → `center` 가 즉시 바뀐다([:157-158](../apps/frontend/src/pages/MapShell.tsx#L157))
   → **재그리기 #1 은 `buildings` 가 아직 직전 거점이다.** 남의 건물 수백~2천 동을
   새 좌표에서 한 번 다 그린다.
2. `setRentHm(null)`([:187](../apps/frontend/src/pages/MapShell.tsx#L187)) → **재그리기 #2**
3. `getBuildingVacancy` 응답 → `setBuildings` → **재그리기 #3**
4. `getRentHeatmap` 응답 → `setRentHm(값)` → **재그리기 #4**

(1·2 는 React 배치에 따라 한 번으로 합쳐질 수 있다 → **3~4회**.)
4번은 순수한 낭비다: `rentHm` 은 임대 레이어에서만 쓰이는데 **그 이펙트에만 레이어
가드가 없다.** 형제 이펙트 둘은 있다 —
`if (layer !== "footfall") return;`([:197](../apps/frontend/src/pages/MapShell.tsx#L197)) ·
`if (layer !== "density") return;`([:206](../apps/frontend/src/pages/MapShell.tsx#L206)).
[:195](../apps/frontend/src/pages/MapShell.tsx#L195) 의 주석("거점 전환마다 3번 호출할
이유가 없다")이 rent 에는 적용되지 않은 채 남아 있다.

이것은 **누적을 설명하지 않는다.** 다만 누적이 있다면 **그 적립 속도를 3~4배로
곱한다**. 그리고 §5-3 의 "첫 회 13초"의 상당 부분이 여기서 나온다.

### 4-D. 탭을 열 때마다 거점이 garosugil 로 되감긴다

`districtId` 의 초기값은 `DEFAULT_DISTRICT`([:155](../apps/frontend/src/pages/MapShell.tsx#L155))다.
`MapShell` 은 탭을 떠날 때 언마운트되므로([App.tsx:119](../apps/frontend/src/App.tsx#L119)),
**map 조합마다 garosugil 840동을 먼저 한 번 그리고 나서 목표 거점으로 바꾼다.**
`open_tab` 은 `.hub-select` 가 보이면 끝나는데([screen_loop.py:418](../scripts/screen_loop.py#L418))
그 시점은 `listDistricts()` 만 오면 되는 시점이라
([MapShell.tsx:375](../apps/frontend/src/pages/MapShell.tsx#L375)),
**garosugil 렌더는 `tab_open_ms` 가 아니라 `render_ms` 창으로 새어 들어간다.**

---

## 5. 후보 원인 — 각각이 "단조 증가"를 설명하는가

### 후보 1 — 오버레이 클릭 리스너가 짝 없이 쌓인다 ★ 유력

- 근거: [MapShell.tsx:291](../apps/frontend/src/pages/MapShell.tsx#L291) ·
  [:305](../apps/frontend/src/pages/MapShell.tsx#L305) 에서 만들고, 지우는 코드가
  저장소 전체에 없다(`Event.removeListener` 는 [:252](../apps/frontend/src/pages/MapShell.tsx#L252)
  한 곳뿐, `clearInstanceListeners`·`clearListeners` 는 **0회**).
  `clearOverlays`([:255-258](../apps/frontend/src/pages/MapShell.tsx#L255))는
  `setMap(null)` 만 한다.
- 규모: 전환 1회당 3~4회 × 그 거점 건물 수(453~1,972) ≈ **1,800~7,900개**의
  Polygon + 클로저 + `Building`(ring 포함). 13회 전환이면 **수만 개**다.
- 단조 증가를 설명하는가: **설명한다.** 쌓이는 곳(지도)이 세션 내내 안 죽고
  ([MapHost.tsx:69-85](../apps/frontend/src/components/MapHost.tsx#L69)),
  페이지도 안 죽는다([screen_loop.py:835](../scripts/screen_loop.py#L835)).
  힙이 커질수록 major GC 가 훑을 것이 늘고 새 할당이 느려지므로,
  **"몇 번째 전환인가"가 시간을 결정하고 "그 거점이 얼마나 큰가"는 결정하지 않는다** —
  §2-3 의 Spearman −0.473 이 정확히 그 모양이다.
- **약한 고리**: `setMap(null)` 뒤에도 SDK 가 그 오버레이를 붙잡는지는
  **네이버 SDK 내부라 이 저장소에서 확정할 수 없다.** SDK 파일을 받아 확인하려
  했으나 이 환경에서 `oapi.map.naver.com` 이 막혀 실패했다(HTTP 000). → §6-1·§6-4

### 후보 2 — 오버레이 DOM(SVG `path`)이 지워지지 않고 남는다

- 근거: 코드에는 없다. `setMap(null)` 이 노드를 떼는지 여부는 SDK 몫이다.
  검사기가 이미 그 원시 계수를 기록하고 있다 —
  `paths`/`divs`/`children`/`canvases`([screen_loop.py:384-398](../scripts/screen_loop.py#L384)).
- 단조 증가를 설명하는가: **설명은 하지만, 이번 관측과는 어긋나는 데가 있다.**
  DOM 이 계속 쌓였다면 `.maphost` 를 다시 보이게 하는 순간
  ([MapHost.tsx:89](../apps/frontend/src/components/MapHost.tsx#L89), `visibility` 토글)
  거대한 레이아웃이 걸려 **`tab_open_ms` 도 같이 자라야 한다.** 관측은 4,750~7,375ms 로
  거의 평평했다(§1-1). 그래서 나는 후보 2 보다 후보 1(힙 쪽)에 무게를 둔다.
  단 이 논거는 §1-2-4 의 독법에 기대고 있다.
- 판정: **리포트의 `obs.map.paths` 를 보면 즉시 갈린다** → §6-2.

### 후보 3 — 목록 수천 행을 가상화 없이 매번 다시 커밋한다

- 근거: [MapShell.tsx:412-425](../apps/frontend/src/pages/MapShell.tsx#L412) —
  `filtered.map()` 이 건물 전부를 `<button>` 으로 그린다. 행마다 자식 5개다.
  1,000동이면 커밋 한 번에 ~6,000노드.
- 단조 증가를 설명하는가: **설명하지 못한다.** React 는 이전 행을 뗀다. 매번 같은
  비용이지 자라는 비용이 아니다. **첫 회 13초의 큰 몫**이지만 13→234 의 이유는 아니다.

### 후보 4 — 지도 타일·이미지 캐시가 서울 곳곳을 돌며 커진다

- 근거: 거점이 바뀔 때마다 카메라를 옮긴다
  ([MapShell.tsx:238-242](../apps/frontend/src/pages/MapShell.tsx#L238), zoom 16 고정
  [MapHost.tsx:78](../apps/frontend/src/components/MapHost.tsx#L78)).
- 단조 증가를 설명하는가: **일부만.** 새 지역을 볼수록 디코딩된 타일이 늘어 메모리
  압력이 커지는 것은 맞지만, 타일 캐시는 보통 상한이 있어 **곧 평평해진다.** 13회
  전환에서 17.7배는 이것만으로 안 나온다. **그리고 map 탭 특유라는 성질은 만족한다.**

### 후보 5 — 취소되지 않는 fetch / 백엔드가 느려진다

- 근거: `AbortController` 0개(§3-E).
- 단조 증가를 설명하는가: **설명하지 못한다.** 두 가지가 반증한다.
  (1) 루프는 조합을 직렬로 돌아 동시 요청이 1~2개다.
  (2) **`tab_open_ms` 가 평평했다.** 그 구간은 `listDistricts()` 왕복이 지배하므로,
  백엔드·네트워크가 세션 내내 느려졌다면 그것도 같이 자랐어야 한다.
  느려진 것은 서버가 아니라 **브라우저**다.

### 후보 6 — 검사기가 실제보다 크게 재고 있다 (측정계 문제)

- 근거: §2-1 의 상한 표. 43~48초 평탄부는 상한 천장에 붙은 모양이고,
  234,687ms 는 상한 없는 `count()`([screen_loop.py:443](../scripts/screen_loop.py#L443))가
  막힌 모양이다. **`count()` 에 상한이 없다는 것은 소스로 확인했다(§2-1-1).**
- 단조 증가를 설명하는가: **설명하지 못한다 — 이것은 원인이 아니라 확대경이다.**
  검사기가 막히려면 메인스레드가 먼저 막혀야 한다. 다만 **숫자를 액면가로 읽으면
  안 된다**는 뜻은 된다: 13,234ms 와 48,860ms 의 비(3.7배)는 실제 렌더 비용의 비가
  아니라 "타임아웃 몇 개를 태웠나"에 가깝다.
  단 **234,687ms 만은 그 읽기가 안 통한다.** 상한 있는 항목을 다 태워도 63,000ms 이고
  나머지는 타이머가 없는 `count()` 가 실제로 기다린 시간이다(§2-1-1) — 그 조합에서는
  최소 171.7초 동안 메인스레드가 정말로 막혀 있었다. **확대경으로 깎아낼 수 없는
  유일한 관측**이다.

---

## 6. 가장 유력한 원인 하나

> **후보 1 — `MapShell` 이 거점마다 만드는 오버레이의 클릭 리스너에 짝이 없고
> ([MapShell.tsx:291](../apps/frontend/src/pages/MapShell.tsx#L291) ·
> [:305](../apps/frontend/src/pages/MapShell.tsx#L305)),
> 그 오버레이가 얹히는 지도가 앱 수명 동안 죽지 않아
> ([MapHost.tsx:69-85](../apps/frontend/src/components/MapHost.tsx#L69))
> 페이지를 한 번도 새로 열지 않는 이 루프
> ([screen_loop.py:835](../scripts/screen_loop.py#L835))에서 세션 내내 누적된다.**

### 6-1. 왜 이것을 골랐나

1. **저장소 안에서 유일하게 짝이 비어 있는 자리다.** §3 의 다섯 축을 다 짝지어 보면
   빈 칸은 3-B 두 줄뿐이고, 나머지 빈 칸(3-D 파노라마, 3-E fetch)은 이번 실행에서
   아예 실행되지 않거나(§3-D) 직렬 실행이라 쌓일 수 없다(§3-E).
2. **비대칭이 맞는다.** map 탭만 컴포넌트보다 오래 사는 객체에 물건을 얹는다(§4-A·§4-B).
   Platform 의 hub-switch 가 6,172ms 한 건으로 끝난 것과 정확히 대응한다.
3. **거점 크기와 무관하다는 관측에 맞는다.** Spearman −0.473(§2-3). 누적 가설은
   시간이 순번을 따라가고 크기를 안 따라가는 것을 예측하는데, 관측이 그렇다.
4. **저장소 안에 대조군이 있다.** 같은 지도를 쓰는 `HubExplorer` 는 리스너를 안 붙이고
   ([HubExplorer.tsx:157](../apps/frontend/src/pages/HubExplorer.tsx#L157)) 정리 함수를
   달아 둔다([:182-185](../apps/frontend/src/pages/HubExplorer.tsx#L182)).
   같은 팀이 같은 지도 위에서 한쪽은 짝을 맞췄고 한쪽은 안 맞췄다.

### 6-2. "왜 첫 회 13초인데 마지막은 234초인가"에 답하는가 — 반은 답하고 반은 못 한다

**13초(누적 없는 1회 비용) — 설명한다.** 후보 1 이 아니라 후보 3+4-C+4-D 의 합이다:

- 탭을 열 때마다 거점이 garosugil 로 되감기고, 그 840동 렌더가 측정 창으로 샌다(§4-D)
- 전환 1회에 오버레이를 3~4번 그린다 — 그중 최소 한 번은 **직전 거점 건물**이다(§4-C)
- 목록 수천 행을 가상화 없이 커밋한다(후보 3)
- 그 사이 메인스레드가 막혀 Playwright 왕복이 늘어진다(§2-2)

**13초 → 49초(단조 증가) — 설명한다.** 지우지 않은 것이 죽지 않는 지도 위에 쌓이고,
페이지가 한 번도 리셋되지 않는다. 힙이 커질수록 GC 와 할당이 느려지고, 느려질수록
검사기의 대기 상한을 하나씩 더 태운다. 43~48초에서 평평해지는 것은
**증상이 멈춘 게 아니라 측정계가 천장(63초, §2-1)에 다가간 것**이다.

**49초 → 234초 — 설명하지 못한다. 미해결로 남긴다.**
4.8배 점프는 그 앞의 완만한 곡선과 결이 다르다. 상한 없는 `count()` 가 막힌 모양이라는
읽기(§2-1)는 **소스로 확정됐지만**(§2-1-1) *어떻게* 그 숫자가 나올 수 있었는지만 말하고,
*왜 그 조합에서* 그랬는지는 말하지 않는다. 가능한 갈래 — **전부 추측이고, 코드로는 어느 쪽도 못 고른다**:
(a) 그 시점에 렌더러가 메모리 한계에 닿아 GC 가 폭주했다,
(b) 그 조합이 실행의 마지막이라 중단(Ctrl-C·절전) 직전의 정지가 시간에 섞였다,
(c) 그 거점 고유의 사건(응답 지연·데이터 이상)이 겹쳤다.
→ §7-3 이 이 갈래를 가른다.

### 6-3. 이 결론의 약한 고리 (숨기지 않는다)

- "`setMap(null)` 만으로는 SDK 가 오버레이를 놓지 않는다"를 **나는 확인하지 못했다.**
  `naver.maps.Event` 가 리스너를 대상 객체에 다는지, 모듈 전역 레지스트리에 다는지에
  따라 결론이 갈린다. 전자면 후보 1 은 누수가 아니고, 그때 남는 것은 후보 2·4 다.
  SDK 를 받아 보려 했으나 이 환경에서 네트워크가 막혔다.
- 따라서 §6-1 은 **"짝이 없다"라는 확정 사실 + "그래서 샌다"라는 미확정 추론**의
  합이다. 두 번째 마디는 §7-1 이 확정한다.

---

## 7. 코드만으로 판정할 수 없어 PC 실행이 필요한 항목

우선순위 순. 1·2 는 **이미 PC 에 있는 데이터만으로** 끝날 수 있다.

### 7-1. (결정적) 힙 스냅샷으로 오버레이가 실제로 남는지 본다

거점을 5회 이상 바꾸며 전환 사이에 DevTools 힙 스냅샷을 찍는다. 확인할 것:

- `Polygon` / `Marker` 인스턴스 수가 전환마다 **누적하는가**, 전환 후 GC 하면 **떨어지는가**
- 남는다면 **retainer 경로**가 무엇인가 — `naver.maps.Event` 의 레지스트리인가,
  `map` 인스턴스인가, 다른 것인가
- 콘솔에서: `naver.maps.Event.hasListener(<setMap(null) 한 polygon>, 'click')`,
  `typeof naver.maps.Event.clearInstanceListeners`

→ 이것이 §6-3 의 약한 고리를 확정하거나 **후보 1 을 기각**한다.

### 7-2. (데이터가 이미 있을 것) `reports/screen_loop.json` 을 읽는다

이 세션은 그 파일을 만들지도 고치지도 않는다. PC 에서 **읽기만** 하면 된다.
map 조합마다 다음을 시계열로 뽑는다:

| 필드 | 어디서 | 무엇을 가른다 |
|---|---|---|
| `obs.map.paths` · `divs` · `children` | [screen_loop.py:384-398](../scripts/screen_loop.py#L384) | **후보 2**: 단조 증가하면 DOM 이 남는 것, 평평하면 힙만 새는 것 |
| `obs.map.poly` · `dot` | 같음 | 매 전환 "우리가 그린 것"의 수가 그 거점 건물 수와 맞는가 |
| `obs.tab_open_ms` | [:459](../scripts/screen_loop.py#L459) | **§1-2-4 의 독법 확정** + 후보 2·5 의 반증 논거 확정 |
| `obs.gate_seen` | [:480](../scripts/screen_loop.py#L480) | 15초를 게이트가 먹었는지, 노드 대기가 먹었는지 |
| `obs.hub` ↔ `obs.render_ms` | [:884-888](../scripts/screen_loop.py#L884) | **§2-3 의 가정 제거** — 실제 대응으로 Spearman 재계산 |
| `console_errors` · `page_errors` | [:352-359](../scripts/screen_loop.py#L352) | 234초 조합에 OOM·SDK 예외가 있었는가(§6-2-c) |

### 7-3. 234,687ms 를 재현한다

같은 거점 목록을 **같은 순서로** 다시 돌려, 그 위치에서 다시 이상값이 나오는지 본다.
나오면 §6-2 의 (a) 또는 (c), 안 나오면 (b)(실행 종료 부작용)다.

### 7-4. 페이지 리셋 A/B — 누적 가설의 직접 검정

조합마다 `page.reload()` 를 넣은 **일회용** 실행을 한다(스크립트를 커밋하지 말 것 —
`scripts/screen_loop.py` 는 이 작업의 금지 대상이다).

- 단조 증가가 **사라지고 13초 근처에서 평평**해지면 → 누적이 원인이다(후보 1/2/4).
- 그대로 자라면 → 원인은 브라우저 세션 밖에 있다(후보 5 쪽을 다시 본다).

**이 한 번의 실행이 §6 을 확정하거나 기각한다.** 코드를 고치기 전에 이것부터 한다.

### 7-5. 첫 회 13초의 내역을 쪼갠다

Performance 패널로 전환 1회를 녹화해 **오버레이 생성 / React 커밋 / GC** 가 각각 몇
%인지 본다. 후보 3(목록 가상화)과 4-C(3~4회 재그리기) 중 어느 쪽이 큰지 여기서 갈린다.
동시에 §4-C 의 "재그리기 3~4회"를 `console.count()` 로 실측한다 —
**나는 이것을 코드에서 읽었을 뿐 세어 보지 않았다.**

### 7-6. Playwright 타임아웃 표면 확인 — ✅ **처리됨 (2026-09-08)**

`Locator.count()` 에 timeout 이 없다는 §2-1 의 전제를 playwright 소스로 확인했다.
**전제는 맞았고, 234,687ms 의 읽기는 다시 세우지 않아도 된다** → 근거는 §2-1-1.

이 항목이 적어 둔 "이 환경에는 playwright 가 없다"는 **틀린 기술이었다.** 원격 세션에는
Node `playwright` 1.56.1 이 `/opt/node22/lib/node_modules/playwright` 에 설치돼 있다
(브라우저는 `/opt/pw-browsers`). Python 패키지는 실제로 설치돼 있지 않지만 —
`screen_loop.py` 가 쓰는 것은 이쪽이다 — PyPI 에서 받아 소스만 읽으면 되는 일이었다.
얻은 것은 확인 하나가 아니라 셋이다(§2-1-1 의 "따라오는 것 셋"):
`set_default_timeout` 이 `count()` 에 닿지 않는다는 것, 막히는 지점이
`callOnSelector`(페이지 안 평가)라는 것, 63,000ms 가 확정 상한이라 234,687ms 중
**최소 171,687ms 는 실제로 메인스레드가 막혀 있던 시간**이라는 것.

남은 것은 *왜 그 조합에서* 그랬는가뿐이다 — §6-2 의 (a)/(b)/(c) 를 가르는 것은
여전히 §7-2(리포트 읽기)와 §7-3(재현)이다.

---

## 8. 이 문서가 하지 않은 것

- **코드를 고치지 않았다.** `apps/` 아래 변경 0건.
- 예산 상수(`BUDGET_MS = 3000`)를 건드리지 않았다.
- `scripts/screen_loop.py` · `reports/*` · `apps/frontend/tsconfig.tsbuildinfo` 를
  건드리지 않았다(PC 에 다른 세션의 미커밋 변경이 있다).
- **성능이 개선됐다는 주장을 하지 않았다.** 화면을 띄우지 않았으므로 그럴 근거가 없다.
- 고칠 방법을 코드로 제안하지 않았다. §7-1·§7-4 가 원인을 확정하기 전에 고치면
  "무엇을 고쳤는지 모르는 채 숫자만 좋아진" 변경이 된다.

> 위 다섯 줄은 §1~§8 을 쓴 진단 세션의 범위다. **§9 는 다른 세션이고 코드를 고쳤다** —
> 다만 고치기 전에 §9-2 로 원인을 계측했고(그래서 "무엇을 고쳤는지 모르는 채"가 아니다),
> §9 도 ms 는 재지 않아 "성능이 개선됐다"는 주장은 이 문서 어디에도 없다.

---

## 9. 검정 — 스텁 지도 위에서 리스너를 셌다 (2026-09-08, 후속 세션)

§7-1(힙 스냅샷)·§7-4(page.reload A/B)는 실제 지도가 필요해 이 컨테이너에서 못 한다
(`oapi.map.naver.com` 차단, §6-3 과 같은 벽). 대신 **§6 의 가설을 두 마디로 쪼개**
코드로 확정 가능한 쪽만 실행으로 검정했다.

| 마디 | 확정 여부 |
|---|---|
| (ㄱ) 거점을 바꿀 때마다 `addListener` 등록이 **전환 횟수에 비례해 늘고, 짝이 안 따라온다** | **§9-2 에서 확정** |
| (ㄴ) 그렇게 남은 등록 때문에 **SDK 가 오버레이를 놓지 않아 힙이 자란다** | **여전히 미확정** — §9-4 |

### 9-1. 방법

`window.naver` 를 **스텁으로 주입**(`page.add_init_script`)하고 빌드 산출물(`dist`)을
정적 서빙해 Playwright 로 몰았다. API 는 `page.route` 로 픽스처를 물렸다(거점 12개,
건물 30~60동 또는 고정 50동). 스텁은 `Map`·`LatLng`·`Marker`·`Polygon`·`Rectangle`·
`Circle`·`InfoWindow`·`visualization.HeatMap` 과 `Event.addListener/removeListener/
clearInstanceListeners` 를 흉내 내며, **등록을 레지스트리에 넣고 해제 때 뺀다.**
`liveListeners` = 그 레지스트리 크기다.

- Chromium: `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`
- 하네스는 스크래치패드에만 두고 **커밋하지 않았다**(`scripts/screen_loop.py`·`reports/*`·
  `tsconfig.tsbuildinfo` 도 건드리지 않았다).
- 전환마다 `addListener` 계수가 400ms 동안 멈출 때까지 기다린 뒤 읽었다 — §4-C 의
  "전환 1회에 재그리기 3~4번"을 다 셈에 넣기 위해서다.

### 9-2. 결과 — 누수 확정

**MapShell, 줌 16(폴리곤 경로), 모든 거점 건물 수 50 고정, 10회 전환:**

| 전환 # | addListener 누계 | removeListener 누계 | **live** |
|---:|---:|---:|---:|
| 0 (탭 열기) | 109 | 0 | **109** |
| 1 | 259 | 0 | **259** |
| 2 | 409 | 0 | **409** |
| 3 | 609 | 0 | **609** |
| 5 | 1,009 | 0 | **1,009** |
| 7 | 1,309 | 0 | **1,309** |
| 10 | 1,859 | 0 | **1,859** |

화면에 떠 있는 건물은 내내 50동인데 살아 있는 등록은 **전환당 약 175개씩 단조 증가**했다.
`removeListener` 는 **10회 전환 내내 0** 이고, 탭을 떠날 때 딱 1번 불린다 —
`zoom_changed` 하나뿐이다(§3-B 의 ✅ 한 줄). `clearInstanceListeners`·`clearListeners` 는 0회.

**건물 수를 거점마다 바꾼 실행(30~60동)에서도 같다** — 10회 전환 뒤
`add 1,710 / remove 0 / live 1,709`, 종류별로 `click 1,709` + `zoom_changed 1`.
**줌 14(핀·Marker 경로)도 같다** — `add 796 / remove 0 / live 795`.
즉 §3-B 의 두 줄(`dot` · `poly`)이 **양쪽 표현 모두에서** 짝 없이 쌓였다.

> `overlaysAttached`(= `setMap(null)` 을 안 받은 오버레이 수)는 항상 **지금 화면이
> 그려야 할 수와 같았다**(줌 16 이면 현재 거점 건물 전부, 줌 14 면 그중 공실의심만).
> `clearOverlays()` 는 제 일을 하고 있었고 새던 것은 **리스너 등록뿐**이다 —
> §3-A 의 "MapShell 쪽 참조는 확실히 끊긴다"가 실행으로 맞았다.

**PageDashboard(`#board`) 도 같다.** 거점 10회 전환에서 `add 445 / remove 0 / live 445`
(지도는 매번 `destroy()` 되고 `mapsCreated 10 / mapsDestroyed 10` 으로 짝이 맞는데,
리스너만 0회 해제였다). 이 화면은 지도가 죽으므로 §4-B 의 "쌓일 무대"는 없지만,
**앱이 핸들을 안 들고 있어 뗄 방법이 없다**는 사실은 MapShell 과 동일하다.

### 9-3. 덤 — §4-C 의 "재그리기 3~4회"를 처음 실측했다

건물 수를 50 으로 고정한 실행에서 **전환 1회당 Δadd 는 150 또는 200** 이었다
(= 3회 또는 4회 × 50동). §7-5 가 "코드에서 읽었을 뿐 세어 보지 않았다"고 남긴 항목이
그대로 맞았다. 건물 수가 다른 실행에서는 예컨대 57동 → 60동 전환의 Δadd 가 **234**
= `57 + 57 + 60 + 60` 이었다 — **재그리기 4회 중 앞 2회가 직전 거점 건물을 그린다**는
§4-C-1 의 읽기까지 수가 맞는다.

### 9-4. 이 검정이 확정하지 **못한** 것 (§6-3 은 아직 열려 있다)

- **실제 SDK 가 아니다.** 스텁 레지스트리가 등록을 붙잡는 것은 내가 그렇게 만든 것이다.
  진짜 `naver.maps.Event` 가 리스너를 대상 객체에 다는지(=오버레이와 함께 GC 된다)
  모듈 전역에 다는지는 **여전히 모른다.** 확정된 것은 앱 쪽 사실 하나다 —
  **핸들을 받아 두지 않아 뗄 방법 자체가 없었고, 등록 수가 전환 횟수에 비례해 늘었다.**
- **ms 는 재지 않았다.** 실제 타일·렌더가 없으므로 §1 의 13,234~234,687ms 는 이 검정과
  무관하게 그대로 남는다. **"성능이 개선됐다"는 주장을 하지 않는다.**
- **§7-4(페이지 리셋 A/B)·§7-1(힙 스냅샷)은 그대로 남는다.** 이 수정이 §1 의 곡선을
  펴는지는 PC 에서 실제 지도로 다시 재야 안다.
- 픽스처 건물 수는 30~60동이다. 실제 거점은 58~2,813동(§1-3)이라 **절대 수가 아니라
  기울기의 모양**만 옮겨 읽을 수 있다.

### 9-5. 고친 것

본보기는 저장소 안에 이미 있던 `zoom_changed` 짝이다
([MapShell.tsx:251-252](../apps/frontend/src/pages/MapShell.tsx#L251) — 수정 뒤 :257-258).

- [MapShell.tsx:143](../apps/frontend/src/pages/MapShell.tsx#L143) `listenersRef` 신설 —
  오버레이에 붙인 핸들을 `overlaysRef` 와 **같은 수명**으로 든다.
- [MapShell.tsx:261-268](../apps/frontend/src/pages/MapShell.tsx#L261) `clearOverlays()` 가
  `setMap(null)` **전에** 리스너를 뗀다. 언마운트 이펙트와 재그리기 이펙트의 첫 줄이
  둘 다 이 함수를 부르므로([:272](../apps/frontend/src/pages/MapShell.tsx#L272) ·
  [:284](../apps/frontend/src/pages/MapShell.tsx#L284)) 두 경로가 한 번에 덮인다.
- [MapShell.tsx:301](../apps/frontend/src/pages/MapShell.tsx#L301)(점) ·
  [:315](../apps/frontend/src/pages/MapShell.tsx#L315)(폴리곤) — 핸들을 `listenersRef` 에 담는다.
- [PageDashboard.tsx:296](../apps/frontend/src/pages/PageDashboard.tsx#L296)·
  [:298](../apps/frontend/src/pages/PageDashboard.tsx#L298) 같은 짝. 지도에 직접 붙는
  `click`([:342](../apps/frontend/src/pages/PageDashboard.tsx#L342))은 수명이 달라
  `mapListenersRef` 로 나누고, 지도를 `destroy()` 하는 정리 함수에서 같이 뗀다
  ([:365-366](../apps/frontend/src/pages/PageDashboard.tsx#L365)).
  오버레이 쪽 둘([:405](../apps/frontend/src/pages/PageDashboard.tsx#L405) 점 ·
  [:437](../apps/frontend/src/pages/PageDashboard.tsx#L437) 그리드)은 `clearOverlays()` 가 받는다.

**동작은 한 줄도 바꾸지 않았다** — 만드는 리스너의 수·시점·클로저가 같고, 뗄 자리만 생겼다.

### 9-6. 수정 후 (같은 하네스, 같은 픽스처)

**MapShell, 줌 16, 건물 50 고정, 10회 전환** — `live` 가 **51 로 상수**다
(현재 거점 폴리곤 50 + `zoom_changed` 1). 전환 횟수와 무관하다:

| 전환 # | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 수정 전 live | 109 | 259 | 409 | 609 | 809 | 1,009 | 1,159 | 1,309 | 1,509 | 1,709 | **1,859** |
| 수정 후 live | 51 | 51 | 51 | 51 | 51 | 51 | 51 | 51 | 51 | 51 | **51** |

- 건물 수 가변(30~60동) 실행: `live` = **현재 거점 건물 수 + 1** 로만 움직인다(31→61).
- 줌 14(핀 경로): `live` = 현재 거점 공실의심 건물 수 + 1(16→31). 역시 순번과 무관.
- 두 실행 모두 **탭을 떠나면 `live` 가 0** 이다(수정 전에는 1,858·795 가 남았다).
- PageDashboard: 10회 전환 뒤 `add 445 / remove 445 / live 0`(수정 전 `remove 0 / live 445`).

`removeMiss`(레지스트리에 없는 핸들을 뗀 횟수)는 모든 실행에서 **0** 이다 — 이중 해제나
엉뚱한 핸들 해제가 없다는 뜻이다.

### 9-7. 통과 조건

- `cd apps/frontend && npm run build` — **통과**(`tsc -b` + vite, MapShell 청크 12.59→12.80 kB).
- 수정 후 리스너 수가 전환 횟수와 무관하게 평평 — **§9-6 에서 확인**.
- `npm run lint` 는 이 컨테이너에서 못 돌린다(`@eslint/js` 미설치). 수정과 무관한 기존 상태다.

---

## 10. 실제 네이버 지도에서 다시 쟀다 (2026-09-08 저녁, L2)

> §9 는 **스텁 지도** 위에서 리스너 수만 셌다. ms 는 아무도 안 쟀다.
> 여기서 처음 **실제 SDK·실제 지도**로 잰다.

### 10-1. 무엇을 어떻게 쟀나

```
python -u scripts/screen_loop.py --fresh \
    --out reports/screen_loop_2026-09-08_postfix.json --node-timeout-ms 20000
```

- 카나리아 선행: `--hubs yeonnam --canary` → 4조합 전부 실패로 잡혔다(검사기가 살아 있다).
- 4탭을 그대로 돌았다(거점-major). `--budget-ms` 는 건드리지 않았다(3000).
- `--node-timeout-ms 20000` 은 어제와 같은 조건을 만들기 위한 것이지 완화가 아니다
  (어제 실행도 20000 이었음이 §L1 §3-4 에서 확정됐다).
- **73조합에서 의도적으로 끊었다.** 어제가 69조합(17거점)에서 멈췄으므로 비교 구간을
  맞춘 것이다. 전수는 L5 가 한다. `finished` 는 이 리포트에도 없다.

⚠ **실행 계보상 이탈 하나.** 이 측정은 `main` 이 아니라
`fix/screen-loop-run-robustness`(b79067f) 위에서 돌았다. 그 커밋은 어제 세션이 고쳐 놓고
커밋하지 못한 검사기 수정 3건이다(`save_report` 의 WinError 5 재시도 · 옵션이 붙기 전에
세어 `missing-option` 으로 오진하던 자리 · Program 탭 명세의 자기모순).
그것 없이 재면 **어제와 다른(더 나쁜) 검사기로 재는 것**이 되어 비교가 성립하지 않는다.
판정 기준·예산·타임아웃 기본값은 그 커밋에서 바뀌지 않았다.

### 10-2. 두 계열 — 거점 순서로 짝지은 것

`render_ms`. `(error)` 는 조작이 20초 안에 안 돼 `obs` 가 남지 않은 것이다.

| # | 거점 | 2026-09-07 | 2026-09-08 | 변화 |
|--:|---|--:|--:|--:|
| 1 | garosugil *(tab-open)* | 5,078 | **1,469** *pass* | −71% |
| 2 | apgujeong-rodeo | 13,234 | 4,953 | −63% |
| 3 | hongdae | 18,203 | 6,829 | −62% |
| 4 | yeonnam | 24,172 | 12,062 | −50% |
| 5 | ikseon | 48,860 | 25,360 | −48% |
| 6 | seochon | 36,234 | 26,515 | −27% |
| 7 | myeongdong | 29,969 | 31,500 | **+5%** |
| 8 | euljiro | (error) | 42,860 | — |
| 9 | seongsu | 40,328 | (error) | — |
| 10 | seoulsup | 39,422 | 45,688 | **+16%** |
| 11 | itaewon | 43,219 | 52,250 | **+21%** |
| 12 | hannam | 43,218 | 54,406 | **+26%** |
| 13 | songridan | 37,469 | (error) | — |
| 14 | gangnam | 48,046 | (error) | — |
| 15 | hapjeong | 234,687 | (error) | — |
| 16 | mangwon | (error) | 30,547 | — |
| 17 | samcheong | (error) | (error) | — |
| 18 | gwangjang | (없음) | (error) | — |

**앞은 반으로 줄고 뒤는 어제보다 커진다.** 6번째부터 개선폭이 무너지고,
10번째부터는 어제보다 느리다.

### 10-3. 축 1 — 누적이 사라졌는가 → **아니다**

오늘 hub-switch 계열(n=11):

```
4,953 → 6,829 → 12,062 → 25,360 → 26,515 → 31,500 → 42,860
      → 45,688 → 52,250 → 54,406 → 30,547
```

| | 2026-09-07 | 2026-09-08 |
|---|---:|---:|
| Spearman(실행 순서 ↔ `render_ms`) | +0.731 | **+0.864** |
| 최소 → 최대 | 13,234 → 234,687 | 4,953 → 54,406 |

**계열은 여전히 자란다.** 상관은 오히려 더 세다. C2(커밋 9683dd5)가 뗀 오버레이 클릭
리스너는 **누적의 한 갈래였을 뿐이고, 남은 갈래가 있다.**
→ §6 의 후보 2·4·5 가 살아 있다. **L3(페이지 리셋 A/B + 힙 스냅샷)로 넘긴다.**

단 후보 2 는 이 실행에서도 다시 기각된다 — §10-5.

마지막 `30,547`(mangwon)은 앞의 54,406 보다 낮다. 그 앞에 오류 3건이 연달아 있었고
오류 하나가 20초를 대기로 태운다. **다만 페이지는 실행 전체에서 한 번만 로드된다**
([screen_loop.py:870](../scripts/screen_loop.py#L870) — `page.goto` 1회, `reload` 없음).
따라서 "오류가 상태를 되돌렸다"고 말할 근거는 없다. **관측만 적어 둔다.**

### 10-4. 축 2 — 절대값이 예산 안인가 → **아니다**

**hub-switch 11건 중 예산 3,000ms 안에 든 것은 0건이다.**
첫 hub-switch(apgujeong-rodeo)부터 4,953ms 로 이미 예산의 **1.65배**다.

⚠ §1-1 이 못박은 것을 다시 적는다 — **누적이 줄어든 것과 예산을 지키는 것은 다른 문제다.**
앞 거점이 −60% 가 됐어도 KPI("지도·건물 상세 로딩 3초 이내")는 **그대로 깨져 있다.**

예외는 `garosugil` 하나다(1,469ms, tab-open, pass). 이것은 hub-switch 가 아니고,
아래 교란을 함께 읽어야 한다.

### 10-5. `obs.map` 계수 — 전환마다 상수다 (후보 2 재기각)

| 거점 | paths | divs | children |
|---|--:|--:|--:|
| garosugil | 840 | 53 | 2 |
| hongdae | 1,325 | 48 | 2 |
| ikseon | 1,748 | 61 | 2 |
| euljiro | 1,972 | 61 | 2 |
| songridan → (error) | — | — | — |
| mangwon | 959 | 61 | 2 |

- `paths` 는 **그 거점의 건물 수**를 그대로 따라간다(euljiro 1,972 = §2-3 표의 값).
  전환 순번과 무관하다.
- `divs` 48~61 · `children` **2 상수** · `canvases` 0.
- → **DOM 은 쌓이지 않는다.** 후보 2 는 어제 리포트(L1 §2-1)에 이어 두 번째로 기각된다.

`tab_open_ms` 는 어제처럼 **자란다**: 1,344 → 1,484 → 2,047 → 969 → 6,516 → 17,703 →
10,079 → 10,500 → 17,282 → 18,531 → 18,546. 17~18초대에서 평평해진다.
즉 **탭을 여는 것 자체도 세션이 늙을수록 느려진다** — 쌓이는 것은 DOM 이 아니다.

### 10-6. `gate_seen` 이 옮겨 다닌다 — C4 판정 정정을 뒷받침한다

| 실행 | `gate_seen: "timeout"` 인 거점 |
|---|---|
| 2026-09-07 | hapjeong 1건 |
| 2026-09-08 | **seoulsup · itaewon · hannam 3건** |

`/heatmap/buildings` 요청이 15초 창을 놓치는 현상은 **hapjeong 고유가 아니다.**
오늘은 hapjeong 이 아예 오류로 빠지고 다른 세 거점에서 났다.
→ `finding-map-panel-heatmap-2026-09-08.md` §2 가 (가)를 "hapjeong 의 제품 결손"으로
판정한 것은 **정정이 필요하다**(L1 §4-2 와 같은 결론에 독립적으로 도달했다).
그 셋 다 `render_ms` 45,688 / 52,250 / 54,406 으로 정체 구간에 있다.

### 10-7. 다른 세 탭은 오늘 전부 통과했다

| 탭 | 2026-09-07 (69조합) | 2026-09-08 (73조합) |
|---|---|---|
| platform | pass 14 · fail 2 · error 2 | **pass 19** |
| map | pass 0 · fail 14 · error 3 | pass 1 · fail 11 · error 6 |
| posting | pass 13 · fail 1 · error 3 | **pass 18** |
| program | pass 15 · error 2 | **pass 18** |

전체 판정도 pass 42/69 → **56/73** 이다.
**map 을 뺀 모든 탭이 깨끗해졌다.** 어제 platform·posting·program 에 있던 실패는
map 조합이 무대를 망가뜨린 하류 증상이었다는 읽기(`finding-screen-s0` §3-5 의 (1))와 맞는다.

### 10-8. 교란 요인 — 이 비교가 완전하지 않은 이유

숨기지 않는다. 아래 넷은 **어제와 오늘 사이에서 같이 바뀐 것**들이다.

1. **SDK 부팅이 캐시됐다.** `sdk_boot_ms` 4,469 → **531**. 브라우저·Vite 캐시가 더운
   상태였다. §10-4 의 `garosugil` 1,469ms 는 이 영향을 크게 받는다.
2. **카나리아를 먼저 돌렸다.** Vite 모듈 그래프가 데워진 뒤 본 측정을 했다.
   어제는 `npm run dev` 직후였을 수 있다(확인할 기록이 없다).
3. **검사기가 바뀌었다**(§10-1 의 이탈). 옵션 대기가 추가돼 조합당 타이밍이 달라졌다.
4. **오류의 자리가 다르다.** 어제는 #8 euljiro 가 오류였고 오늘은 #9 seongsu 다.
   오류 하나가 20초를 태우므로 그 뒤 거점의 조건이 서로 어긋난다.
   §10-2 의 10~12번 "+16~26%" 를 **회귀로 단정하지 않는 이유**가 이것이다.

→ 그래서 **믿을 수 있는 것은 "계열이 여전히 자란다"(축 1)와 "예산 안이 0/11"(축 2)이다.**
거점별 증감 %는 위 넷 때문에 그대로 읽으면 안 된다.

### 10-9. 남은 미결

| 항목 | 어디로 |
|---|---|
| 누적의 남은 원인(후보 4·5, 그리고 §6-3 의 약한 고리) | **L3** — 페이지 리셋 A/B + 힙 스냅샷 |
| 첫 회 4,953ms 의 내역(무엇이 5초를 먹는가) | §7-5 — 아직 안 쪼갰다 |
| 234,687ms 재현 | 오늘 재현되지 않았다. hapjeong 은 오늘 오류였다 → §7-3 미결 |
| 66거점 전체에서도 같은가 | **L5** — 오늘은 18거점까지만 봤다 |

### 10-10. 통과 조건 대조

| 조건 | 결과 |
|---|---|
| `L2_MEASURED` — 실제 네이버 지도로, 두 계열을 거점 순서로 짝지음 | ✅ §10-2 |
| `L2_TWO_AXES` — "누적"과 "예산"이 따로 판정됨 | ✅ §10-3 / §10-4 |
| `L2_HONEST` — 예산에 못 들어왔으면 그렇게 적음 | ✅ **0/11**, §10-4 |

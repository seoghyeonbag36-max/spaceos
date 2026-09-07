# finding — 화면 회귀 S0 10건은 렌더 지연의 결과인가, 별개의 결손인가

- 날짜: 2026-09-08
- 브랜치: `chore/cloud-c3-s0-operation-failures`
- 성격: **진단만.** `apps/` 와 `scripts/` 아래는 한 줄도 고치지 않았다. 이 문서 하나만 추가한다.
- 방법: 코드 정독 + **백엔드 실측 1건**(§3-3). 화면은 띄우지 않았다 —
  이 문서에는 재지 않은 "빨라졌다/고쳤다" 류의 주장이 없다.
- 같은 회귀 실행의 앞선 진단: [finding-map-hubswitch-2026-09-08.md](finding-map-hubswitch-2026-09-08.md) (이하 **C1**)

---

## 0. 판정 — 두 종류 각각

| 종류 | 관측 | 판정 | 확신 |
|---|---|---|---|
| **(가) map** | `wait_for_selector(".hub-select:not([disabled])")` 20,000ms 실패 | **(1) 렌더 지연의 결과** | 높음 — 단 §3-5 의 갈래 하나를 코드로 배제하지 못했다 |
| **(나) posting** | `Locator.click` on `role=button name="Posting"` 20,000ms 실패 | **(1) 렌더 지연의 결과** | **확정** — 소거로 닫힌다(§2-3) |

한 줄로: **둘 다 `open_tab` 의 첫 두 줄에서 났고, 둘 다 "화면에 그것이 없어서"가 아니라
"렌더러 메인스레드가 그동안 막혀 있어서" 났다.**
([screen_loop.py:416-419](../scripts/screen_loop.py#L416))

⚠ 다만 **(가)의 관측 문구를 액면대로 읽으면 안 된다.** "`hub-select` 가 disabled 로 남았다"는
**코드상 일어날 수 없다** — `:not([disabled])` 는 이 화면에서 아무것도 거르지 않는다(§3-1).
실제로 기다린 것은 `disabled` 가 풀리기를이 아니라 **그 `<select>` 가 생기기를**이다.

---

## 1. 20,000ms 이 어디서 나오는가 — 두 관측은 같은 손잡이 하나에서 나왔다

`open_tab` 은 세 줄이다([screen_loop.py:415-419](../scripts/screen_loop.py#L415)):

```python
def open_tab(page, spec, timeout_ms):
    page.get_by_role("button", name=spec.label, exact=True).first.click()   # ← (나)
    page.wait_for_selector(spec.root, state="visible", timeout=timeout_ms)
    page.wait_for_selector(f"{spec.hub_select}:not([disabled])", state="visible",
                           timeout=timeout_ms)                              # ← (가)
```

- (가)의 셀렉터 `.hub-select` 는 **map 탭 명세의 `hub_select` 와 문자 그대로 같다**
  ([screen_loop.py:190](../scripts/screen_loop.py#L190)). 즉 세 번째 줄이다.
- (나)의 `name="Posting"` 은 **posting 탭 명세의 `label`** 이다
  ([screen_loop.py:203](../scripts/screen_loop.py#L203)). 즉 첫 번째 줄이다.

**두 관측 모두 20,000ms 인 것은 우연이 아니다.**
- 세 번째 줄의 상한은 `args.node_timeout_ms` 다(`probe` 가 그 값으로 부른다).
- 첫 번째 줄(`Locator.click`)은 상한을 따로 받지 않고 `page.set_default_timeout(args.node_timeout_ms)`
  를 탄다([screen_loop.py:832](../scripts/screen_loop.py#L832)). Playwright 자체 기본값은 30,000ms 다.

코드의 기본값은 **8,000**이다([screen_loop.py:108](../scripts/screen_loop.py#L108)).
따라서 이 실행은 **`--node-timeout-ms 20000`** 으로 돌았고
([screen_loop.py:732](../scripts/screen_loop.py#L732)), 두 종류는 **같은 실행·같은 손잡이**의
서로 다른 두 줄이다. 이것이 이 문서가 둘을 한 판정 틀에 놓는 근거다.

### 1-1. 이 실패가 리포트에 어떻게 남는가

`open_tab` 의 예외는 `probe` 밖으로 나가 루프가 받는다 —
`status: "error"`, `stage: "S0"`, 그리고 **`obs` 는 `{}`**
([screen_loop.py:861-862](../scripts/screen_loop.py#L861)).
즉 이 10건에는 `render_ms`·`tab_open_ms`·`console_errors` 가 **하나도 남지 않았다.**
§7 이 "무엇을 더 봐야 하나"를 리포트의 *이웃 조합*에서 찾는 이유다.

### 1-2. 이 문서가 갖지 못한 것

`reports/screen_loop.json` 은 **이 저장소에 없다**(커밋된 적이 없다 · C1 §1-2-2 와 같다).
그래서 나는 **10건의 실제 예외 문구도, 어느 거점이었는지도, 실행 순서상 어디였는지도 모른다.**
아래 판정은 전부 *코드가 허용하는 상태 공간*을 좁혀서 얻은 것이고,
관측값에 기대는 대목은 그때마다 그렇다고 밝혔다.

---

## 2. (나) posting 탭 — `role=button name="Posting"` 클릭이 20초를 태웠다

### 2-1. 그 버튼은 언제 마운트되는가 — **항상**

좌측 레일은 `view` 와 **무관하게** 그려진다
([App.tsx:90-104](../apps/frontend/src/App.tsx#L90)).
`NAV` 여섯 항목이 무조건 `map` 되고([App.tsx:92](../apps/frontend/src/App.tsx#L92)),
그중 하나가 `{ key: "posting", label: "Posting", … }` 다
([App.tsx:58](../apps/frontend/src/App.tsx#L58)).
버튼에는 `disabled` 가 없다([App.tsx:93-99](../apps/frontend/src/App.tsx#L93)).

접근명도 정확히 `"Posting"` 이다 — 아이콘 `<svg>` 는 `aria-hidden` 이고
([App.tsx:131](../apps/frontend/src/App.tsx#L131)) 남는 텍스트는 `<span>Posting</span>`
하나다([App.tsx:101](../apps/frontend/src/App.tsx#L101)).
저장소 전체에서 접근명이 `Posting` 인 요소는 이것뿐이므로 `.first` 도 이 버튼을 집는다.

### 2-2. 레일이 사라지는 경로는 둘뿐이고, 이 실행은 그 둘을 타지 않는다

```
App.tsx:76   if (isAdmin) return <AdminCoverage />;   ← 레일 없이 통째로 반환
App.tsx:80   if (isBoard) return <PageDashboard />;   ← 레일 없이 통째로 반환
```

둘 다 해시로만 켜진다(`#admin` · `#board`,
[App.tsx:64-65](../apps/frontend/src/App.tsx#L64)).

- 루프는 `page.goto(args.base_url)` 를 **실행당 한 번** 부르고 base_url 에 해시가 없다
  ([screen_loop.py:835](../scripts/screen_loop.py#L835) · [:106](../scripts/screen_loop.py#L106)).
- 저장소에서 해시를 **쓰는** 코드는 한 곳뿐이다 —
  [HubExplorer.tsx:116](../apps/frontend/src/pages/HubExplorer.tsx#L116) 의
  거점 id 를 `hub=…` 해시로 쓴다. 그런데 HubExplorer(「거점」 탭)는 **루프의 탭 명세에 없고**
  ([screen_loop.py:166-225](../scripts/screen_loop.py#L166)), 값도 `#admin`/`#board` 가 아니다.

⇒ **이 실행에서 "Posting" 버튼이 DOM 에 없었던 순간은 없다.**

### 2-3. 가려졌을 가능성도 닫힌다 (Playwright 클릭이 무는 두 번째 조건)

`Locator.click` 은 대상이 **보이고 · 활성이고 · 안정적이고 · 포인터를 받는지**를 확인한 뒤에
누른다. 앞의 둘은 §2-1 로 끝났고, "포인터를 받는가"는 기하학으로 끝난다:

| 요소 | 규칙 | 결과 |
|---|---|---|
| `.rail` | `position: fixed; left:0; width: var(--rail-w); z-index: 1200` ([App.css:10-12](../apps/frontend/src/App.css#L10)) | 좌측 64px([tokens.css:79](../apps/frontend/src/styles/tokens.css#L79)) · **최상위** |
| `.maphost` | `position: fixed; inset: 0 0 0 var(--rail-w)` ([MapHost.css:5-6](../apps/frontend/src/components/MapHost.css#L5)) | **레일 오른쪽에서 시작한다 — 겹치지 않는다** |
| `.mapshell` | `position: absolute; inset: 0` ([MapShell.css:9-10](../apps/frontend/src/pages/MapShell.css#L9)) | `.maphost`(`overflow:hidden`) 안이라 레일까지 못 나온다 |

저장소 CSS 전체에서 `position: fixed` 규칙은 **위 둘뿐**이고,
`z-index ≥ 1000` 은 **레일(1200)과 `.pagedash .twinmodal`(2000) 둘뿐**이다
([PageDashboard.css:85](../apps/frontend/src/pages/PageDashboard.css#L85)).
후자만이 레일을 덮을 수 있는데 — **그것이 `PageDashboard` 인 이유가 여기 있다.**
그 화면은 `#board` 로만 열리므로([App.tsx:80](../apps/frontend/src/App.tsx#L80))
§2-2 에 의해 이 실행에서 열리지 않는다.
MapShell 자신의 모달(`.twin-modal`, [MapShell.tsx:529-549](../apps/frontend/src/pages/MapShell.tsx#L529))도
`.b-twin` 버튼을 눌러야 열리는데([MapShell.tsx:460](../apps/frontend/src/pages/MapShell.tsx#L460)),
검사기는 목록 첫 행(`.b-item`)만 누르고 층 스택·거리뷰는 경계 밖이라고 명시돼 있다
([screen_loop.py:500-511](../scripts/screen_loop.py#L500) · [:70-71](../scripts/screen_loop.py#L70)).

### 2-4. 판정 — **(1) 렌더 지연의 결과. 소거로 확정.**

`click()` 이 20초를 태울 수 있는 경로를 다 세우면:

| # | 경로 | 상태 |
|---|---|---|
| 1 | 버튼이 없다 | **배제** — §2-1·§2-2 |
| 2 | `disabled` 다 | **배제** — [App.tsx:93-99](../apps/frontend/src/App.tsx#L93) 에 없다 |
| 3 | 다른 요소가 덮었다 | **배제** — §2-3 |
| 4 | 이름이 겹쳐 엉뚱한 것을 집었다 | **배제** — 접근명 `Posting` 은 하나뿐 |
| 5 | **안정성·클릭가능 판정이 끝나지 않았다** | **남는 유일한 경로** |

5번은 곧 **렌더러 메인스레드가 막혀 있었다**는 말이다. Playwright 의 안정성 검사는
대상의 박스가 연속 두 애니메이션 프레임에서 같은지를 본다 — rAF 가 돌지 않으면 이 검사는
영원히 끝나지 않고 상한을 태운다. C1 이 map 탭에서 잡아낸 증상
(§2-2 "노드가 안 뜬 게 아니라 Playwright 왕복 자체가 막혔다")과 **같은 것**이고,
§4 가 그 막힘이 왜 하필 이 클릭 시점에 걸리는지를 보인다.

---

## 3. (가) map 탭 — `.hub-select:not([disabled])` 가 20초를 태웠다

### 3-1. `:not([disabled])` 는 이 화면에서 **아무것도 거르지 않는다** (확정)

`.hub-select` 는 `DistrictPicker` 가 그리는 `<select>` 다
([MapShell.tsx:377-378](../apps/frontend/src/pages/MapShell.tsx#L377)).
그 컴포넌트는 `disabled` 를 **prop 으로 받아** 그대로 내려보낸다
([DistrictPicker.tsx:72](../apps/frontend/src/components/DistrictPicker.tsx#L72) ·
[:76](../apps/frontend/src/components/DistrictPicker.tsx#L76) ·
[:99](../apps/frontend/src/components/DistrictPicker.tsx#L99)).

**저장소 어느 호출부도 그 prop 을 넘기지 않는다:**

| 호출부 | `disabled` 전달 |
|---|---|
| [MapShell.tsx:377](../apps/frontend/src/pages/MapShell.tsx#L377) | 없음 |
| [PlatformConsole.tsx:183](../apps/frontend/src/pages/PlatformConsole.tsx#L183) | 없음 |
| [PostingConsole.tsx:155](../apps/frontend/src/pages/PostingConsole.tsx#L155) | 없음 |

React 는 `disabled={undefined}` 를 **속성으로 내보내지 않는다.** 따라서 `.hub-select` 에는
`disabled` 속성이 붙은 순간이 없고, `:not([disabled])` 는 `.hub-select` 와 같은 셀렉터다.

> 참고: 네 탭 중 `:not([disabled])` 가 실제로 무언가를 거르는 곳은 **Program 탭 하나뿐**이다 —
> 그 select 는 `DistrictPicker` 가 아니라 손으로 그린 것이고 `disabled={districts === null}` 을 갖는다
> ([ProgramStudio.tsx:386](../apps/frontend/src/pages/ProgramStudio.tsx#L386) ·
> [screen_loop.py:217](../scripts/screen_loop.py#L217)).

⇒ **(가)는 "disabled 가 안 풀렸다"가 아니다. "그 노드가 20초 안에 나타나지 않았다"다.**

### 3-2. 그 노드는 언제 나타나는가 — `hubs.length > 0` 이 되는 순간

```tsx
MapShell.tsx:375   {hubs.length > 0 && (
MapShell.tsx:377      <DistrictPicker className="hub-select" districts={hubs} … />
```

`hubs` 를 채우는 곳은 하나뿐이다 — `listDistricts()` 응답을
`vacancy_source === "gold"` 로 거른 결과
([MapShell.tsx:161-173](../apps/frontend/src/pages/MapShell.tsx#L161), 필터는
[:166](../apps/frontend/src/pages/MapShell.tsx#L166)).
초기값은 `[]` 이므로 **마운트 직후에는 `.hub-select` 가 DOM 에 없다.**

그리고 `MapShell` 은 탭을 떠날 때마다 언마운트된다
([App.tsx:119](../apps/frontend/src/App.tsx#L119) ·
[MapHost.tsx:105](../apps/frontend/src/components/MapHost.tsx#L105) `{active && children}`).
⇒ **map 조합 하나하나가 매번 `/api/v1/commercial-districts` 왕복을 임계경로에 놓는다.**
CSS 로 숨겨진 순간은 없다 — `.hub-select` 는 `height: 40px` 의 평범한 오버레이 자식이라
([MapShell.css:30-36](../apps/frontend/src/pages/MapShell.css#L30)) 그려지는 즉시 `visible` 이다.

### 3-3. 그 왕복은 얼마나 드는가 — **실측했다**

이 컨테이너의 백엔드 venv 로 그 엔드포인트의 실제 계산부
(`app.services.districts.list_summaries`, [districts.py:379-381](../apps/backend/app/services/districts.py#L379))를
5회 불렀다:

```
import          : 400 ms
PAGES           : 66
list_summaries  : 3812.3, 126.5, 144.6, 125.0, 128.2  (ms)
응답 거점 66 / vacancy_source == "gold" : 66
```

읽을 것 셋:

1. **`gold` 거점이 66/66 이다.** 따라서 §3-2 의 `hubs.length > 0` 게이트가
   *필터 때문에* 막힐 일은 없다. 응답만 오면 `.hub-select` 는 즉시 조건을 만족한다.
2. **첫 호출 3,812ms, 이후 125~145ms.** 첫 호출이 비싼 것은 하위 로더의
   `lru_cache(maxsize=1)` 가 그때 채워지기 때문이다
   (예: [posting_revenue.py](../apps/backend/app/services/posting_revenue.py) 에 11개).
   그런데 루프는 **시작 프리플라이트에서 바로 그 엔드포인트를 한 번 두드린다**
   ([screen_loop.py:301](../scripts/screen_loop.py#L301)) — 조합을 재기 전에 이미 덥혀진다.
3. ⇒ **이 대기의 서버 몫은 조합당 약 0.13초다.** 20,000ms 의 0.7% 다.

> 실측의 경계: 이 컨테이너에서 **함수를 직접** 부른 값이다. 데스크톱의
> Vite 프록시·uvicorn·HTTP 왕복은 포함돼 있지 않고, Gold 산출물도 이 저장소 사본이다.
> 그래도 결론의 방향은 바뀌지 않는다 — 프록시가 0.13초를 20초로 만들지는 않는다.

### 3-4. 같은 실행의 숫자와 맞춰 본다

C1 §1-1 이 이 실행의 `tab_open_ms` 를 **4,750~7,375ms** 로 적었다
(그 독법 자체에 C1 이 단 유보는 C1 §1-2-4 에 있다. 나는 그 유보를 그대로 물려받는다).
`tab_open_ms` 는 바로 이 세 줄의 합이다([screen_loop.py:457-459](../scripts/screen_loop.py#L457)).

- 서버 몫 ≈ 130ms (§3-3)
- 관측 ≈ 4,750~7,375ms
- ⇒ **그 대기의 97% 이상은 통과한 조합에서조차 브라우저 몫이었다.**
- 20,000ms 는 그 값의 **2.7~4.2배**다. 같은 실행에서 이웃한 map `hub-switch` 는
  13,234 → 234,687ms 로 **17.7배** 벌어졌다(C1 §1-1).

한 지표가 17.7배 벌어진 실행에서 그 옆의 지표가 3~4배 튀어 상한을 넘는 것은
**예외가 아니라 같은 곡선 위의 한 점**이다.

### 3-5. 판정 — **(1) 렌더 지연의 결과.** 배제하지 못한 갈래 하나를 밝힌다

코드가 허용하는 경로:

| # | 경로 | 상태 |
|---|---|---|
| 1 | `disabled` 가 안 풀렸다 | **배제** — §3-1, 그런 속성이 존재하지 않는다 |
| 2 | 응답은 왔는데 `gold` 가 0건이라 게이트가 안 열렸다 | **배제** — §3-3 실측 66/66 |
| 3 | CSS 로 안 보였다 | **배제** — [MapShell.css:30-36](../apps/frontend/src/pages/MapShell.css#L30) |
| 4 | 서버가 20초를 먹었다 | **배제** — §3-3, 조합당 ≈0.13초 |
| 5 | **메인스레드가 막혀 응답 콜백·커밋·Playwright 폴링이 못 돌았다** | **가장 잘 맞는다** — §3-4·§4 |
| 6 | `listDistricts()` 가 실패했고 `.catch` 가 삼켰다 | **배제하지 못했다** ↓ |

6번이 남는 이유: [MapShell.tsx:171](../apps/frontend/src/pages/MapShell.tsx#L171) 의
`.catch(() => { /* 목록 실패 시 기본 거점 단독으로 계속 */ })` 는 **에러를 통째로 삼킨다.**
실패하면 `hubs` 가 `[]` 로 남고 `.hub-select` 는 **영원히 안 나타나며 화면에는 아무 표시도 없다.**
그러면 20,000ms 는 "느려서"가 아니라 "끝나지 않아서" 태워진다 — 그건 (2)다.

그럼에도 **(1)로 판정하는 이유**:

- 같은 엔드포인트를 **바로 앞 조합**(같은 거점의 Platform 탭)이 부른다
  ([PlatformConsole.tsx:102](../apps/frontend/src/pages/PlatformConsole.tsx#L102)).
  탭 순서는 Platform → Page → Posting → Program 이고 조합은 거점-major 다
  ([screen_loop.py:808](../scripts/screen_loop.py#L808) · [:166-225](../scripts/screen_loop.py#L166)).
  Platform 조합이 지나갔다면 그 왕복은 몇 초 전에 성공한 것이다.
- 같은 실행에서 map `hub-switch` 관측이 **13건 남았다**(C1 §1-1). 그 13건은 전부
  `.hub-select` 를 통과해 값까지 고른 조합이다 — 엔드포인트도 gold 필터도 이 실행에서
  반복적으로 정상 동작했다.
- 반면 5번은 §3-4 의 수치와 정확히 맞물린다.

**이것은 확정이 아니라 "가장 잘 맞는 읽기"다.** 6번을 닫는 방법은 §7-1 에 있고,
**PC 에 이미 있는 파일을 읽기만 하면 된다.**

---

## 4. "앞선 거점의 미완료 작업에 막힐 수 있는 경로" — 두 자리에서 확인된다

지시받은 세 번째 확인 항목이다. 코드에서 두 경로가 나온다.

### 4-A. map 조합 → **바로 다음 posting 조합의 클릭** (이것이 (나)의 자리다)

조합 순서가 거점-major 라([screen_loop.py:808](../scripts/screen_loop.py#L808))
**posting 조합은 같은 거점의 map 조합 바로 다음**이다. 그런데 map 조합의 마지막 동작은
`detail_click` 이다([screen_loop.py:500-511](../scripts/screen_loop.py#L500)) —
목록 첫 행을 누른다. 그 행의 `onClick` 은
([MapShell.tsx:416](../apps/frontend/src/pages/MapShell.tsx#L416)) `focus(b)` 를 부르고,
`focus` 는 `setSelected(b)` + `map.panTo(...)` 다
([MapShell.tsx:264-268](../apps/frontend/src/pages/MapShell.tsx#L264)).

그 한 번의 클릭이 켜 놓는 것:

| 무엇 | 어디 | 언제 끝나는가 |
|---|---|---|
| 목록 전체 재커밋 (`filtered.map()`, 건물 수만큼 `<button>` × 자식 5개) | [MapShell.tsx:412-425](../apps/frontend/src/pages/MapShell.tsx#L412) | 커밋 한 번 |
| **`map.panTo()` 카메라 애니메이션** — 매 프레임 오버레이 전부 재도색 | [MapShell.tsx:267](../apps/frontend/src/pages/MapShell.tsx#L267) | **애니메이션이 끝날 때까지 rAF 점유** |
| `recommendIndustry` 왕복 | [MapShell.tsx:222-235](../apps/frontend/src/pages/MapShell.tsx#L222) | 응답이 올 때 |

그런데 검사기는 이 중 **첫 커밋만** 기다린다 —
`wait_for_selector(".mapshell .b-detail .b-name")`
([screen_loop.py:506](../scripts/screen_loop.py#L506))는 같은 커밋에 만족되기 때문이다.
**panTo 애니메이션과 추천 왕복이 도는 한가운데서 조합이 끝나고, 그 다음 Playwright 동작이
곧바로 "Posting" 버튼 클릭이다.**
클릭의 안정성 검사는 rAF 두 프레임을 요구하는데(§2-4), 그 rAF 를 SDK 의 pan 재도색이
쥐고 있다. 건물 수는 거점당 **58~2,813동**(C1 §1-3)이다.

⇒ **(나)는 "앞선 작업이 안 끝난 채로 다음 조작이 들어간" 자리다.** 그리고 이 경로는
검사기가 무엇을 기다리는지 때문에 **구조적으로 매번 열려 있다** — 지연이 클수록 걸린다.

### 4-B. map 탭 열기 자체가 **직전 거점이 아니라 garosugil** 을 먼저 그린다

`districtId` 의 초기값은 항상 `DEFAULT_DISTRICT = "garosugil"` 이고
([MapShell.tsx:31](../apps/frontend/src/pages/MapShell.tsx#L31) ·
[:155](../apps/frontend/src/pages/MapShell.tsx#L155)),
마운트 즉시 두 요청이 **동시에** 나간다:

- `listDistricts()` — `.hub-select` 를 만드는 것([MapShell.tsx:161-173](../apps/frontend/src/pages/MapShell.tsx#L161))
- `getBuildingVacancy("garosugil")` — 840동을 가져오는 것([MapShell.tsx:176-183](../apps/frontend/src/pages/MapShell.tsx#L176))

후자가 도착하면 재그리기 이펙트가 **840개 Polygon + 840개 클릭 리스너**를 만들고
([MapShell.tsx:294-307](../apps/frontend/src/pages/MapShell.tsx#L294)) 목록 840행을 커밋한다.
두 콜백은 **같은 메인스레드 한 줄**을 두고 겨룬다. C1 §4-D 가 "탭을 열 때마다 garosugil 을
먼저 그린다"고 적은 그 비용이, `.hub-select` 대기 창에도 그대로 얹힌다.

여기에 **`React.StrictMode`** 가 곱해진다([main.tsx:9-11](../apps/frontend/src/main.tsx#L9)).
개발 서버에서 마운트 이펙트는 두 번 돈다 — 루프는 `npm run dev`(`localhost:5173`)를 대상으로
돌므로([screen_loop.py:29-33](../scripts/screen_loop.py#L29) ·
[:106](../scripts/screen_loop.py#L106)) 위 두 요청과 재그리기가 **조합마다 두 벌**이다.
(프로덕션 빌드에는 없는 증폭이다. 판정을 바꾸지는 않지만, `tab_open_ms` 가 4.75~7.4초였던
이유의 한 몫이다.)

### 4-C. 그리고 무대는 세션 내내 리셋되지 않는다

C1 이 확정한 두 가지가 여기에도 그대로 적용된다:
지도는 앱 수명 동안 죽지 않고([MapHost.tsx:69-85](../apps/frontend/src/components/MapHost.tsx#L69)),
페이지는 실행당 한 번만 열린다([screen_loop.py:835](../scripts/screen_loop.py#L835)).
즉 **(가)·(나)가 겨루는 메인스레드는 C1 이 "단조 증가"를 관측한 바로 그 메인스레드다.**

---

## 5. 그래서 이 10건은 별개의 신호가 아니다

- 두 종류 모두 **`open_tab` 의 첫 두 줄**이다(§1). 판정부(`judge`)는 한 번도 돌지 않았다.
- 두 종류 모두 **"화면에 그것이 없다"로는 설명되지 않는다** — (나)는 소거로 확정(§2-4),
  (가)는 네 경로를 배제하고 하나만 남겼다(§3-5).
- 두 종류 모두 **메인스레드 점유 시간에 비례해 터진다.** 같은 실행에서 그 시간은
  13초 → 234초로 자랐다(C1 §1-1).

⇒ **10건은 C1 이 진단한 렌더 지연의 *하류 증상*이다. 별도로 고칠 결손을 세지 않는다.**
따라서 **이 10건을 근거로 새 수정을 만들지 않는다.** C1 §7-1·§7-4 가 렌더 지연의 원인을
확정하면 이 10건은 같이 사라져야 하고, 사라지지 않으면 그때 (2)로 다시 판정한다.

### 5-1. C1 에 대한 정정 한 줄 (조건부)

C1 §2-1 은 측정 창의 천장을 `15,000 + 3×(8,000+8,000) = 63,000ms` 로 계산했다.
이 실행이 `--node-timeout-ms 20000` 이었다면(§1) 그 천장은
**`15,000 + 3×(20,000+20,000) = 135,000ms`** 다.

바뀌는 것: C1 §2-1·§6-2 의 "43~48초 평탄부는 63초 천장에 붙은 모양"이라는 읽기가
**약해진다** — 천장이 135초면 43~48초는 천장 근처가 아니다.
바뀌지 않는 것: **234,687ms 는 여전히 상한 있는 항목만으로 나올 수 없다**(135,000 < 234,687).
C1 §6-2 의 미해결(49초 → 234초)은 그대로 남는다.
이 정정은 `--node-timeout-ms 20000` 추정에 기대므로 §7-2 가 같이 확인한다.

---

## 6. (2)는 아니지만 이 실행이 드러낸 결손 셋 — 방향만 적고 **고치지 않는다**

10건의 원인은 아니다. 그러나 §3 을 세우다 코드에서 나온 것이고, 다음에 같은 진단을
반복하게 만드는 자리라 남긴다. **어느 것도 이 브랜치에서 손대지 않았다.**

### 6-1. 거점 목록 실패가 조용하다 — `.catch` 가 삼키고 화면이 비어 버린다

`MapShell` 은 목록 요청이 실패하면 아무 말 없이 `hubs = []` 로 남는다
([MapShell.tsx:171](../apps/frontend/src/pages/MapShell.tsx#L171)) → 거점 선택기가
**아예 그려지지 않는다**([MapShell.tsx:375](../apps/frontend/src/pages/MapShell.tsx#L375)).
사용자에게도 검사기에게도 "왜 없는지"가 남지 않는다. §3-5 의 6번을 코드로 못 닫는 이유가 이것이다.

같은 파일 안에 **대조군**이 있다: `ProgramStudio` 는 실패를 상태로 남긴다 —
`.catch(() => { setDistricts([]); setDistrictErr(true); })`
([ProgramStudio.tsx:130](../apps/frontend/src/pages/ProgramStudio.tsx#L130)).
`PostingConsole` 은 `setErr(String(e))` 로 남긴다
([PostingConsole.tsx:69](../apps/frontend/src/pages/PostingConsole.tsx#L69)).
**세 화면이 같은 실패를 세 가지로 다룬다.**

> 방향(제안): `MapShell` 도 실패를 상태로 남기고, 선택기 자리에 그 사실을 그린다.
> 그러면 "없음"과 "느림"이 화면에서 갈리고, 검사기의 S0 도 20초를 태우는 대신 그 문구를 읽는다.
> ⚠ 이건 §6-1 의 진단이지 이 작업의 산출물이 아니다.

### 6-2. `:not([disabled])` 는 네 탭 중 셋에서 아무 일도 하지 않는다 (검사기 쪽)

§3-1 에서 확정한 것이다. 결과는 두 가지다.

- **실패 문구가 오해를 부른다.** "disabled 를 기다리다 실패"로 읽히지만 실제는 "노드가 없다"다.
  이 문서 §0 의 경고가 그것이다.
- **Platform 탭에는 반대 방향의 구멍이 하나 있다.** `PlatformConsole` 은 `districts` 가 비어도
  `<select>` 를 그린다([PlatformConsole.tsx:183](../apps/frontend/src/pages/PlatformConsole.tsx#L183))
  — 옵션이 0개인 빈 select 다. 그런데 명세의 셀렉터는 `.platconsole .picker select`
  ([screen_loop.py:169](../scripts/screen_loop.py#L169))라 **그 빈 select 에도 걸린다.**
  map(`hubs.length > 0` 게이트)과 posting(`select:has(optgroup)` — 옵션이 없으면
  `<optgroup>` 도 없다, [DistrictPicker.tsx:102-118](../apps/frontend/src/components/DistrictPicker.tsx#L102))은
  이 구멍이 없다.
  Platform 탭만 목록이 비어도 `open_tab` 을 통과하고 그 뒤 `select_option` 에서 터진다.

> **`scripts/screen_loop.py` 는 이 작업의 금지 대상이라 한 글자도 고치지 않았다.**
> 판단이 필요하면 이 절만 인용해서 별도 작업으로 낸다.

### 6-3. 목록 왕복이 map 조합마다 임계경로에 있다

`api.ts` 에는 캐시가 없다 — `getJSON` 은 매번 `fetch` 한다
([api.ts:30-34](../apps/frontend/src/lib/api.ts#L30)).
`MapShell` 이 탭을 떠날 때마다 언마운트되므로([App.tsx:119](../apps/frontend/src/App.tsx#L119))
**같은 목록을 조합마다 다시 받는다.** 서버 몫이 0.13초라 이것만으로는 문제가 아니지만
(§3-3), `.hub-select` 의 등장을 **네트워크 왕복 뒤로 밀어 두는** 구조라
메인스레드가 막힐 때 가장 먼저 상한을 태우는 자리가 된다.
`AbortController` 가 저장소에 0개라는 C1 §3-E 와 같은 축이다.

---

## 7. 남은 불확실을 닫는 것 — **전부 PC 에 이미 있는 데이터로 끝난다**

### 7-1. (결정적, §3-5 의 6번) 실패 10건의 **실행 위치**를 본다

`reports/screen_loop.json` 을 **읽기만** 한다. 조합마다 `at` 타임스탬프가 있으므로
([screen_loop.py:884-888](../scripts/screen_loop.py#L884)) 실행 순서를 복원할 수 있다.

| 볼 것 | (1)이면 | (2)면 |
|---|---|---|
| S0 10건의 실행 순서상 위치 | **뒤쪽에 몰린다** — `render_ms` 가 커진 뒤 | 처음부터 흩어져 있다 |
| S0 직전 조합의 `obs.render_ms` | 이미 수십 초 | 평범(수 초) |
| posting S0 가 **같은 거점의 map 조합 바로 뒤**인가 | 그렇다 (§4-A) | 무관하게 흩어진다 |
| map S0 직후 같은 거점 posting 도 S0 인가 | 짝으로 온다 | 짝이 없다 |

**이 표 하나로 §3-5 의 5번과 6번이 갈린다.**

### 7-2. 실패 문구 원문을 읽는다 — (나)는 여기서 완전히 닫힌다

`failures[0].why` 에 `f"조작 실패: {e}"[:400]` 로 예외 문자열이 남아 있다
([screen_loop.py:862](../scripts/screen_loop.py#L862)).
Playwright 의 `click` 타임아웃 메시지는 **왜 못 눌렀는지를 call log 로 같이 싣는다** —
`element is not stable` / `intercepts pointer events` / `element is not visible` 중 어느 것인지가
그 400자 안에 들어온다.

- `not stable` 계열 → §2-4 의 5번 확정 = **(1)**
- `intercepts pointer events` → §2-3 이 틀렸다는 뜻이므로 그 요소를 찾아 (2)로 재판정
- 같은 문자열로 `--node-timeout-ms 20000` 여부도 확인된다 → §5-1 의 정정이 성립하는지

### 7-3. `sdk_boot_ms` 와 `preflight` 를 같이 본다

리포트 최상위에 있다([screen_loop.py:840-848](../scripts/screen_loop.py#L840) ·
[:806](../scripts/screen_loop.py#L806)).
`preflight.served` 가 66 이고 `served_missing` 이 비었으면 §3-3 의 "gold 66/66" 이
그 실행에서도 성립했다는 뜻이다 — §3-5 의 2번을 실측으로 닫는다.

### 7-4. 재현 — 한 번의 실행으로 (1)/(2)가 갈린다

C1 §7-4 의 A/B(조합마다 `page.reload()`)를 그대로 쓴다. 페이지를 조합마다 리셋했을 때
**S0 10건이 같이 사라지면 (1)이 확정된다.** 남으면 그 남은 건이 (2)이고, 그때
§6-1 을 먼저 본다.
(⚠ 그 일회용 스크립트를 `scripts/screen_loop.py` 에 커밋하지 말 것 — 이 작업의 금지 대상이다.)

---

## 8. 이 문서가 하지 않은 것

- **코드를 고치지 않았다.** `apps/` 아래 변경 0건, `scripts/` 아래 변경 0건.
- **타임아웃을 완화하지 않았다.** `BUDGET_MS`·`NODE_TIMEOUT_MS`·`GATE_TIMEOUT_MS` 를 건드리지 않았다.
- **`screen_loop` 명세를 바꾸지 않았다.** §6-2 는 관찰이지 변경이 아니다.
- **`reports/*` 를 만들지도 고치지도 않았다.** §7 은 전부 *읽기* 지시다.
- **성능이 개선됐다는 주장을 하지 않았다.** 화면을 띄우지 않았다.
- §3-3 의 백엔드 실측 외에는 새 값을 만들지 않았고, 그 값의 경계는 §3-3 아래에 적었다.

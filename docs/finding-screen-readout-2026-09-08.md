# finding — 2026-09-07 화면 회귀 리포트 판독 (L1)

> **성격: 읽기 전용.** 어제 실행의 리포트 하나를 읽어, 오늘 낮 클라우드가 낸 진단 세 개가
> "리포트를 못 봐서" 미결로 남긴 자리를 닫는다. **새로 실행한 것은 없다.**
> `scripts/screen_loop.py` 를 돌리지 않았고 `reports/screen_loop.json` 은 바뀌지 않았다.

- **입력:** `reports/screen_loop_2026-09-07.json` (어제 실행의 사본 — 이 커밋에서 처음 git 에 올린다)
- **원본:** `reports/screen_loop.json` — 같은 내용. 다음 실행이 이 경로를 덮으므로 사본을 남겼다.
- **스크린샷:** `reports/screens/` 25장 (실패 조합만 저장된다)

## 0. 한 줄 결론

**단조 증가는 실행 순서에서 관측되지만, 세 진단이 인용한 "13234 → … → 234687" 은
값을 오름차순 정렬한 것이지 실행 순서가 아니다.** 실제 순서로 세우면 24,172 다음이
48,860 이고 그 뒤 36,234·29,969 로 내려갔다가 37~48초대에서 **평평해진다.**
DOM 은 누적하지 않는다(`paths` 는 거점의 건물 수를 그대로 따라간다).
S0 오류 10건은 **뒤에 몰려 있고**, 마지막 8조합이 전부 오류다 — 세션이 조작 불가 상태로
끝났다. 234,687ms 조합은 실행의 마지막이 아니었다(69조합 중 58번째).

---

## 1. 리포트의 뼈대

| 필드 | 값 |
|---|---|
| `started` → `updated` | 2026-09-07T22:27:46 → 22:51:15 (23분 29초) |
| `finished` | **키 자체가 없다** — 중단 확정 |
| `budget_ms` | 3000 |
| `hubs_total` / `tabs` | 66 / platform·map·posting·program |
| `sdk_boot_ms` | 4469 |
| `preflight` | `base_url` localhost:5173 · `app_status` 200 · `served` **66** · `served_missing` **[]** · `served_extra` [] |
| 조합 수 | 69 (= 17거점 × 4탭 + 1) |

판정: pass 42 / fail 17 / error 10. 탭별로 가르면 **map 탭은 pass 가 0 개다.**

| 탭 | pass | fail | error |
|---|---:|---:|---:|
| platform | 14 | 2 | 2 |
| map | **0** | 14 | 3 |
| posting | 13 | 1 | 3 |
| program | 15 | 0 | 2 |

전체 오류 계수: `console_errors` **0** · `page_errors` **0** · `api_5xx` **0** ·
`resource_errors` 16 · `api_4xx` 16(전부 `/api/v1/ai/recommend-industry` 404).

⚠ **앱은 예외를 한 번도 던지지 않았다.** 자바스크립트 오류도, 5xx 도 없다. 느려졌을 뿐이다.
4xx 16건은 이 저장소의 규약대로 실패로 세지 않는다(400m 안에 노드가 없으면 404 다).

⚠ 리포트에 **실행 인자(`args`)가 기록되지 않는다.** 그래서 `--node-timeout-ms` 값은
예외 문자열에서 역산했다(§3).

---

## 2. 1번 — map 조합 시계열 (finding-map-hubswitch §7-2)

`at` 오름차순, 즉 **실제 실행 순서**다.

| # | 거점 | trigger | tab_open_ms | render_ms | gate_seen | paths | divs | children | poly | dot |
|--:|---|---|--:|--:|---|--:|--:|--:|--:|--:|
| 1 | garosugil | tab-open | 4,703 | 5,078 | — | 840 | 53 | 2 | 840 | 0 |
| 2 | apgujeong-rodeo | hub-switch | 6,719 | 13,234 | 200 | 769 | 55 | 2 | 769 | 0 |
| 3 | hongdae | hub-switch | 4,828 | 18,203 | 200 | 1,325 | 48 | 2 | 1,325 | 0 |
| 4 | yeonnam | hub-switch | 15,672 | 24,172 | 200 | 1,133 | 61 | 2 | 1,133 | 0 |
| 5 | ikseon | hub-switch | 13,547 | **48,860** | 200 | 1,748 | 61 | 2 | 1,748 | 0 |
| 6 | seochon | hub-switch | 16,422 | 36,234 | 200 | 846 | 55 | 2 | 846 | 0 |
| 7 | myeongdong | hub-switch | 1,359 | 29,969 | 200 | 1,084 | 61 | 2 | 1,084 | 0 |
| 8 | euljiro | — | — | — | — | — | — | — | — | — |
| 9 | seongsu | hub-switch | 16,860 | 40,328 | 200 | 831 | 61 | 2 | 831 | 0 |
| 10 | seoulsup | hub-switch | 19,703 | 39,422 | 200 | 698 | 48 | 2 | 698 | 0 |
| 11 | itaewon | hub-switch | 15,500 | 43,219 | 200 | 845 | 48 | 2 | 845 | 0 |
| 12 | hannam | hub-switch | 16,594 | 43,218 | 200 | 714 | 55 | 2 | 714 | 0 |
| 13 | songridan | hub-switch | 15,828 | 37,469 | 200 | 453 | 61 | 2 | 453 | 0 |
| 14 | gangnam | hub-switch | 16,109 | 48,046 | 200 | 987 | 55 | 2 | 987 | 0 |
| 15 | **hapjeong** | hub-switch | 19,812 | **234,687** | **timeout** | 292 | 48 | 2 | 292 | 0 |
| 16 | mangwon | — | — | — | — | — | — | — | — | — |
| 17 | samcheong | — | — | — | — | — | — | — | — | — |

8·16·17 은 `status: "error"` 라 `obs` 가 `{}` 다 — **필드가 없다.** 추정으로 채우지 않는다.

### 2-1. `paths` · `divs` · `children` — **누적하지 않는다** → 후보 2 기각

- `paths` 는 840 → 769 → 1,325 → 1,133 → 1,748 → 846 … 로 **오르내린다.**
  그리고 매 행에서 `paths == poly` 이고, 그 값은 **그 거점의 건물 수**다.
  finding-map-hubswitch §1-3 이 gold 에서 직접 센 값과 하나씩 맞는다
  (ikseon 1,748 · hongdae 1,325 · songridan 453 · hapjeong 292).
- `divs` 는 48 / 53 / 55 / 61 을 오갈 뿐 추세가 없다. `children` 은 **2 상수**. `canvases` 0.
- → **DOM 은 남지 않는다.** `setMap(null)` 은 노드를 뗀다. **후보 2 는 기각된다.**

⚠ 다만 후보 2 가 스스로 든 반증 논거("DOM 이 쌓였다면 `tab_open_ms` 도 자라야 하는데
평평했다")는 **논거 자체가 틀렸다** — §2-3 을 보라. 기각은 유지되지만, 근거는
그 논거가 아니라 위의 `paths` 직접 계수다.

### 2-2. 시간은 "그 거점의 크기"를 따라가지 않는다 — 실제 대응으로 재계산

finding-map-hubswitch §2-3 은 13개 값이 PAGES 순서 거점 1~13 에 대응한다고 **가정**했다.
그 가정은 틀렸다. 실제 대응은 위 표다. 다른 점:

| 항목 | §2-3 의 가정 | 실제 |
|---|---|---|
| 234,687ms 의 주인 | gangnam | **hapjeong** |
| euljiro | 39,422ms | **render_ms 자체가 없다**(error) |
| seochon | 36,234ms | 36,234ms (우연히 일치) |
| ikseon | 29,969ms | **48,860ms** |
| 목록에 없던 거점 | — | **hapjeong** 이 빠져 있었다 |

Spearman(실제 대응, n=14):

| 짝 | rho |
|---|---:|
| `render_ms` ↔ 건물 수(`paths`) | **−0.169** (§2-3 은 −0.473 이라 적었다) |
| `render_ms` ↔ 실행 순서 | **+0.785** |
| `render_ms` ↔ 실행 순서 (hub-switch 13건만) | +0.731 |
| `tab_open_ms` ↔ 실행 순서 | **+0.679** |
| `tab_open_ms` ↔ `render_ms` | +0.604 |
| hapjeong 제외 시 `render_ms` ↔ 건물 수 | **+0.038** |

**결론은 방향이 같고 크기가 다르다.** 시간은 거점의 크기와 사실상 무관하고
(−0.169, hapjeong 빼면 +0.038), **실행 순서와 붙는다**(+0.785).
다만 §2-3 이 인용한 −0.473 은 가정 위의 값이었으므로 그 숫자는 쓰지 말아야 한다.

### 2-3. `tab_open_ms` — §1-2-4 의 독법은 **틀렸다**

§1-2-4 는 "tab-open 4,750~7,375ms" 를 **`tab_open_ms` 의 범위**로 읽었다. 아니다.
그 세 숫자는 `trigger == "tab-open"` 인 **세 조합의 `render_ms`** 다:

| 조합 | render_ms |
|---|--:|
| garosugil / platform | 7,375 |
| garosugil / map | 5,078 |
| garosugil / posting | 4,750 |

실제 `tab_open_ms` 의 범위는 **1,359 ~ 19,812ms** 이고, 4,703 → 6,719 → 4,828 에서
시작해 **15,000~19,800 대로 올라가 평평해진다**(rho +0.679).
즉 **탭을 여는 것 자체도 세션이 늙을수록 느려진다.** myeongdong 1,359ms 는 예외값이다.

### 2-4. `gate_seen`

hub-switch 13건 중 **12건이 `200`**, hapjeong 하나만 `timeout` 이다.
`GATE_TIMEOUT_MS = 15000`([screen_loop.py:109](../scripts/screen_loop.py#L109))이므로,
정상 조합에서는 거점 전환 API 응답이 15초 안에 왔다. **15초를 먹은 것은 게이트가 아니라
그 뒤의 노드 대기다** — `render_ms` 40초대에도 `gate_seen` 은 200 이다.

---

## 3. 2번 — S0 오류 10건의 실행 위치 (finding-screen-s0 §7-1 · §7-2)

### 3-1. 위치 — **뒤에 몰려 있다**

69조합 중 오류의 위치: **#30, #59, #62, #63, #64, #65, #66, #67, #68, #69**

```
#30  euljiro|map          (고립)
#59  hapjeong|posting     ← 직전 #58 hapjeong|map 이 234,687ms
#62~#69  mangwon(map·posting·program) · samcheong(4탭 전부) · gwangjang|platform
         ← 마지막 8조합이 전부 오류. 여기서 실행이 끝났다.
```

**흩어져 있지 않다.** 마지막 8조합은 연속이고, 그 앞에서 render_ms 가 이미 37~48초대로
올라가 있었다. finding-screen-s0 §7-1 표의 왼쪽 열(=**(1) 렌더 지연의 결과**)이 성립한다.

### 3-2. 짝으로 오는가 — **3건 중 2건에서 그렇다**

| 거점 | map 조합 | 바로 다음 posting |
|---|---|---|
| hapjeong | #58 fail (234,687ms) | #59 **S0** ✔ 짝 |
| mangwon | #62 **S0** | #63 **S0** ✔ 짝 |
| euljiro | #30 **S0** | #31 pass ✘ 짝 아님 |

§4-A 가 예측한 "map 조합 → 바로 다음 posting 의 클릭" 은 hapjeong·mangwon 에서 성립하고
euljiro 에서는 성립하지 않는다. **euljiro 는 회복했다** — 그 뒤 39조합이 더 돌았다.

### 3-3. 예외 원문 — `not stable` · `intercepts pointer events` · `not visible` 은 **하나도 없다**

10건 전부 `Timeout 20000ms exceeded` 다. 두 종류로 갈린다.

**(가) `wait_for_selector` 3건** — `:not([disabled])` 가 안 풀렸다

| 조합 | 셀렉터 | call log 의 추가 줄 |
|---|---|---|
| euljiro\|map | `.hub-select:not([disabled])` | 없음 |
| hapjeong\|posting | `.postconsole select:has(optgroup):not([disabled])` | 없음 |
| mangwon\|map | `.hub-select:not([disabled])` | **`locator resolved to visible <select class="hub-select">…</select>`** |

⚠ mangwon 한 건이 결정적이다. **select 는 보였다.** 그런데 20초 내내
`disabled` 가 안 풀렸다. 요소가 없던 게 아니라 **앱이 그 20초 동안 목록을 못 채웠다.**

**(나) `Locator.click` 7건** — 요소를 **찾지도 못했다**

```
waiting for get_by_role("button", name="Posting", exact=True).first
```
call log 가 여기서 끝난다. **`locator resolved to …` 줄이 없다** = 20초 동안 그 버튼이
DOM 에 나타나지 않았다. 클릭을 가로챈 요소가 있었다면 `intercepts pointer events` 가
찍혔을 텐데 없다. → **§2-3(가로채는 요소) 재판정은 필요 없다. (1) 이 유지된다.**

### 3-4. `--node-timeout-ms 20000` 확정

`NODE_TIMEOUT_MS` 기본값은 **8000**
([screen_loop.py:108](../scripts/screen_loop.py#L108))인데 예외에는 20000 이 찍혔다.
→ 어제 실행은 `--node-timeout-ms 20000` 으로 돌았다. finding-screen-s0 §5-1 의 정정이 성립한다.

---

## 4. 3번 — `.sp-title` 은 없던 게 아니라 **못 잰** 것 (finding-map-panel-heatmap §3-4)

hapjeong|map 의 값:

```
nodes[".mapshell .sp-head .sp-title"] = {
  "count": 0,
  "text": "[selector-error] Locator.inner_text: Timeout 20000ms exceeded.\n
           Call log:\n  - waiting for locator(\".mapshell .sp-head .sp-title\").first\n"
}
```

**`[selector-error]` 로 시작한다 → §3-4 의 갈래 2 다.** 노드가 없던 게 아니라
읽지 못한 것이고, (가)와 같은 원인으로 묶인다.

같은 조합에서 `.sp-sub` 와 `.b-item` 은 **`null`** 이다 — 계수 자체를 남기지 못했다.
`page_errors` 와 `console_errors` 는 **둘 다 빈 배열**이다.

### 4-1. 스크린샷이 이것을 못박는다

`reports/screens/hapjeong__map.png` 를 열었다. 화면은 **정상적으로 다 그려져 있다**:

- 사이드패널 제목 **"합정 · 건물 공실"** 이 있다 — `.sp-title` 은 존재했다
- 부제 **"마포구 · 292동 · 실측(추정) · 거점 10.7%"**
- 건물 목록(호호빌 33% · 코너중앙 50% …)이 채워져 있다
- 지도에 폴리곤이 그려져 있다 — `obs.map.paths = 292` 와 일치한다
- 거점 select 가 **"합정 · 공실 10.7%"** 로 바뀌어 있다

### 4-2. 그래서 (가) 판정에 정정이 필요하다

finding-map-panel-heatmap §2 는 (가)를 **(A) 제품 결손 — "요청이 15초 안에 나가지 못했다"**
로 판정했다. 리포트와 스크린샷이 보이는 것은 그보다 좁다:

- `gate_seen: "timeout"` 은 `expect_response` 가 **15초 창 안에 그 응답을 못 봤다**는 뜻이지
  ([screen_loop.py:497-502](../scripts/screen_loop.py#L497)) "부르지 않았다"가 아니다.
- 292개 폴리곤이 실제로 그려졌고 부제에 "292동" 이 찍혔다.
  이 292 는 hapjeong 의 gold 건물 수이고, 로컬 샘플 폴백으로는 나올 수 없는 값이다.
  → **요청은 결국 갔고 응답도 왔다.** 창 안에 못 들어왔을 뿐이다.
- 즉 (가)는 (나)·S0 10건과 **같은 하나의 사건**이다 — 그 조합에서 메인스레드가 234초 막혔다.
  독립된 결손이 아니다.

⚠ 검사기의 문구 "부르지 않았다"([screen_loop.py:595](../scripts/screen_loop.py#L595))는
관측을 과장해 옮긴다. 다만 **이 작업에서 명세를 고치지 않는다**(L1_NO_RERUN 및 금지 조항).
차이만 적어 둔다.

---

## 5. 4번 — `sdk_boot_ms` 와 `preflight` (finding-screen-s0 §7-3)

| 필드 | 값 | 뜻 |
|---|---|---|
| `sdk_boot_ms` | 4,469 | 네이버 SDK 부팅에 4.5초. 첫 조합 render 5,078ms 의 대부분이다 |
| `preflight.app_status` | 200 | 앱이 떠 있었다 |
| `preflight.served` | **66** | 그 실행에서도 서빙 66거점이 성립했다 |
| `preflight.served_missing` | **[]** | 빠진 거점 없음 |
| `preflight.served_extra` | [] | 여분 없음 |

→ finding-screen-s0 §3-3 의 "gold 66/66" 이 그 실행에서도 성립했다. **§3-5 의 2번이 닫힌다.**

---

## 6. 세 문서의 어느 절이 닫혔나

### 6-1. `finding-map-hubswitch-2026-09-08.md`

| 절 | 상태 | 근거 |
|---|---|---|
| §7-2 (리포트를 읽는다) | ✅ **닫힘** | 여섯 줄 전부 §2 에 값이 있다 |
| §1-2-3 (map 17개인데 hub-switch 13개) | ✅ **닫힘** | 1 tab-open + 13 hub-switch + 3 error(obs `{}`) = 17. 문서의 셈이 맞았다 |
| §1-2-4 (tab-open 독법) | ⚠ **틀렸음 확인** | 4,750~7,375 은 `tab_open_ms` 가 아니라 tab-open 3조합의 `render_ms` (§2-3) |
| §2-3 (가정 위의 대응·Spearman) | ⚠ **정정 필요** | 234,687 의 주인은 gangnam 이 아니라 hapjeong. rho −0.473 → **−0.169** |
| 후보 2 (DOM 잔존) | ✅ **기각** | `paths`·`divs`·`children` 평평 (§2-1). 단 문서가 든 반증 논거는 무효 |
| §6-2 분기 (b) "마지막 조합이라 중단이 섞였다" | ✅ **기각** | hapjeong\|map 은 69조합 중 **58번째**. 뒤로 11조합이 더 돌았다 |
| §6-2 분기 (c) "그 거점 고유 사건" | ⚠ **약해졌다** | `console_errors`·`page_errors`·`api_5xx` 전부 0. 292동이 정상 렌더됐다 |
| §6-2 분기 (a) "GC 폭주" | ❌ **미결** | 리포트에 힙 지표가 없다 → **L3 §7-1** |
| §6-3 약한 고리 (SDK 가 오버레이를 놓는가) | ❌ **미결** | 리포트로 판정 불가 → **L3** |
| §7-3 (234,687ms 재현) | ❌ **미결** | 재실행이 필요하다 → **L2 / L5** |

### 6-2. `finding-screen-s0-2026-09-08.md`

| 절 | 상태 | 근거 |
|---|---|---|
| §7-1 (실패 10건의 실행 위치) | ✅ **닫힘** | 뒤에 몰림. 마지막 8조합 연속 오류 (§3-1) |
| §7-2 (예외 원문) | ✅ **닫힘** | `not stable`·`intercepts`·`not visible` 없음. 20000ms 확정 (§3-3·§3-4) |
| §7-3 (`sdk_boot_ms`·`preflight`) | ✅ **닫힘** | 4,469 · served 66 · missing [] (§5) |
| §3-5 판정 **(1) 렌더 지연의 결과** | ✅ **유지·강화** | 위 셋이 전부 (1) 쪽이다 |
| §4-A (map → 다음 posting 짝) | ⚠ **부분 성립** | 3건 중 2건. euljiro 는 회복했다 (§3-2) |
| §7-4 (A/B 재현) | ❌ **미결** | → **L3** |

### 6-3. `finding-map-panel-heatmap-2026-09-08.md`

| 절 | 상태 | 근거 |
|---|---|---|
| §3-4 (한 필드로 갈린다) | ✅ **닫힘** | `[selector-error]` → **갈래 2**. 못 잰 것이다 (§4) |
| (나) `.sp-title` 판정 | ⚠ **(A)→ 하류 증상으로 정정** | 스크린샷에 제목이 있다 (§4-1) |
| (가) heatmap 판정 | ⚠ **정정 필요** | 요청은 결국 갔다. 292 폴리곤이 그려졌다 (§4-2) |
| §4 (명세는 고칠 것이 없다) | ⚠ **한 문구는 재검토 대상** | "부르지 않았다"는 과장. 이 작업에서 고치지 않는다 |
| §6 (다음 한 수 — PC 결정 실험) | ❌ **미결** | → **L4** |

---

## 7. 이 판독이 하지 **않은** 것

- **재실행하지 않았다.** 위 값은 전부 2026-09-07 22:27~22:51 한 번의 실행에서 나왔다.
  그 실행은 66거점 중 **17거점(69조합)** 에서 멈췄다. 남은 49거점은 관측이 없다.
- **누적의 원인을 확정하지 않았다.** 후보 2(DOM)를 기각했을 뿐, 후보 1·4·5 중
  무엇인지는 리포트로 갈리지 않는다. 힙 지표가 리포트에 없다.
- **C2 수정의 효과를 재지 않았다.** 이 리포트는 C2(커밋 9683dd5) **이전**의 것이다.
- **234,687ms 가 왜 그 조합에서 나왔는지** 설명하지 못한다. (b)만 기각했다.
- `obs` 가 `{}` 인 3조합(euljiro·mangwon·samcheong 의 map)은 **필드가 없다.**
  추정으로 채우지 않았다.
- 리포트에 **실행 인자가 기록되지 않는다.** `--node-timeout-ms 20000` 은 예외 문자열에서
  역산한 것이지 리포트가 직접 말한 값이 아니다.

## 8. 통과 조건 대조

| 조건 | 결과 |
|---|---|
| `L1_READOUT` — 1~4 네 자리에 실제로 읽은 값 | ✅ §2 · §3 · §4 · §5 |
| `L1_CLOSES` — 세 문서의 해당 절이 닫힘/미결로 판정 | ✅ §6 (닫힘 7 · 정정 4 · 미결 5) |
| `L1_COMMIT` — `reports/screen_loop_2026-09-07.json` 이 git 에 | ✅ 이 커밋 |
| `L1_NO_RERUN` — screen_loop 미실행, 원본 불변 | ✅ `reports/screen_loop.json` 의 mtime·크기 불변(96,054B) |

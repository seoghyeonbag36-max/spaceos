# 로컬 PC 작업 프롬프트 L1~L7 — 2026-09-08 저녁

> [prompts-local-pc-2026-09-08.md](prompts-local-pc-2026-09-08.md) 의 **프롬프트 전용판**이다.
> 그 문서는 왜 이 일들이 PC 몫인지와 명령을 담고, 이 문서는 **붙여넣을 것 일곱 개**만 담는다.
> 각 프롬프트는 **단독으로 선다** — 새 세션에 하나만 붙여넣어도 필요한 숫자·파일·판정 기준이
> 전부 안에 있다. 앞 작업의 대화를 이어받지 않는다.

## 어떻게 쓰나

- **한 세션에 하나씩.** 프롬프트 하나가 끝나면 새 세션에서 다음 것을 붙여넣는다.
  한 세션에 둘을 넣으면 앞 작업의 실패를 뒤 작업이 덮어 쓴다.
- **순서: L1 → L2 → L3 → L4 → L5 → L6 → L7.** L3·L4 는 조건부다(각 프롬프트 첫 줄에 적혀 있다).
- **선행 조건**(터미널 3개·`.env` 키·`PYTHONIOENCODING`)은 앞 문서 §2 에 있다. 그것부터 한다.
- **L1~L6 은 각자 브랜치에서 돈다.** `main` 푸시는 Cloud Run 프로덕션 배포를 태우므로
  머지는 **L7 이 한 번에** 한다.

| ID | 무엇을 | 성격 | 브랜치 | 대략 |
|---|---|---|---|---|
| **L1** | 어제 리포트 판독 — 미결 3건을 닫는다 | 읽기 전용 | `feat/l1-screen-readout-2026-09-08` | 25분 |
| **L2** | C2 수정을 실제 지도에서 ms 로 잰다 | 측정 | `feat/l2-hubswitch-remeasure` | 40분 |
| **L3** | 페이지 리셋 A/B + 힙 스냅샷 (조건부) | 실험 | `feat/l3-reset-ab` | 30분 |
| **L4** | hapjeong heatmap 미호출 (조건부) | 판정+수정 | `feat/l4-hapjeong-heatmap` | 20분 |
| **L5** | 66거점 264조합 전수 — 무인 | 무인 실행 | `feat/l5-screen-loop-full` | 야간 |
| **L6** | 앵커 격차 축 분해 (09-07 T3 미완) | 진단 | `feat/l6-anchor-gap-axes` | 30분 |
| **L7** | `/verify` · 머지 · 배포 | 마감 | `main` | 20분 |

---

## 공통 계약 (PC 판) — 모든 프롬프트에 적용된다

각 프롬프트에 "이 문서의 공통 계약을 적용하라"고 적혀 있다. 내용은 이렇다.
**클라우드 판**([cloud-workday-claude-2026-09-08.md](cloud-workday-claude-2026-09-08.md))과
1·2번이 다르다 — 여기서는 화면을 띄울 수 있다.

1. `CLAUDE.md` · `AGENTS.md` 를 읽고 시작한다. 코드 주석·문서는 한국어, 기술 용어는 영문 병기.
2. **화면을 띄웠으므로 ms 를 말해도 된다. 단 잰 것만 말한다.** 안 잰 값을 추정으로 채우지 않는다.
   오늘 낮 클라우드가 낸 문서 다섯 개에는 "빨라졌다"가 한 줄도 없다 — 그게 정확한 상태다.
   그 위에 **잰 값을 얹는 것**이 오늘 밤의 일이고, 안 쟀는데 얹는 것이 그것을 망치는 유일한 길이다.
3. 예산 상수(`BUDGET_MS = 3000`)·타임아웃(`NODE_TIMEOUT_MS` · `GATE_TIMEOUT_MS`)·판정 기준을
   **완화해서 통과시키지 않는다.** 명세가 틀렸다는 근거를 찾으면 고치지 말고 보고한다.
4. **저장소 루트(`spaceos/`)에서 실행한다.** 상위 폴더(`../`)에는 아무것도 만들지 않는다.
5. 로그를 파일로 낼 때 `PYTHONIOENCODING=utf-8` · `python -u`. cp949 에 `—`(em dash)가 없어
   리다이렉트 순간 UnicodeEncodeError 로 죽는다(2026-08-19 실측).
6. `git add .` · `git add -A` · force push · **`main` 직접 푸시 금지**. 명시 경로만 stage 한다.
   `main` 푸시는 GitHub Actions → Cloud Run 프로덕션 배포를 태운다. 머지는 L7 이 한다.
7. `data/`(bronze/silver/gold) 산출물과 `.github/workflows/deploy.yml` 은 수정하지 않는다.
8. 최종 응답은 `완료 ID / 실행한 명령과 결과 / 판정 / 바꾼 파일 / 브랜치·SHA / 남은 미결` 순서로
   짧게 적는다. **미결을 완료로 만들지 않는다.**

---

# L1 — 어제 리포트 판독 (재실행보다 먼저)

**왜 첫 번째인가.** `scripts/screen_loop.py` 는 기본 출력이 `reports/screen_loop.json` 이라
**다시 돌리는 순간 어제 실행의 유일한 사본이 덮인다.** 오늘 머지된 진단 세 개가 전부
그 파일 하나를 못 읽어 미결로 남았다.

````text
SpaceOS 저장소 루트에서 작업한다. docs/prompts-local-pc-L1-L7-2026-09-08.md 의 공통 계약을
적용하라. 브랜치는 feat/l1-screen-readout-2026-09-08 이고 main 에서 딴다.

[상황]
어제(2026-09-07) 66거점 × 4탭 = 264조합 화면 회귀 전수 실행이 69조합에서 중단됐다.
판정은 pass 42 / fail 17 / error 10 이었다. 그 리포트가 reports/screen_loop.json 에
그대로 남아 있고, 이 파일은 **git 에 커밋된 적이 없어 이 PC 에만 있다.**

오늘 낮 클라우드 세션이 진단 문서 세 개를 냈는데, 셋 다 이 파일을 못 읽어 미결을 남겼다.
너는 그 미결을 읽기만으로 닫는다.

[먼저 — 이 두 줄을 하기 전에는 아무것도 하지 마라]
  copy reports\screen_loop.json reports\screen_loop_2026-09-07.json
  dir reports\screens
사본을 뜬 것을 확인한 뒤에 진행한다. 재실행은 이 작업에서 하지 않는다.

[너의 일] 아래 넷을 순서대로 읽고 판정하라. 절 번호는 그 문서에서 이 값을 기다리는 자리다.

1. docs/finding-map-hubswitch-2026-09-08.md §7-2
   map 조합(키가 "<hub>|map")의 시계열을 뽑아라.
   - obs.map.paths · divs · children 이 단조 증가하는가(=DOM 이 남는다) 평평한가(=힙만 샌다)
   - obs.map.poly · dot 이 그 거점의 건물 수와 맞는가
   - obs.tab_open_ms · obs.gate_seen
   - obs.hub ↔ obs.render_ms 의 실제 대응으로 Spearman 을 다시 계산하라.
     그 문서 §2-3 은 대응을 모른 채 가정으로 계산했다. 그 가정을 지워라.

2. docs/finding-screen-s0-2026-09-08.md §7-1 · §7-2
   status "error" · stage "S0" · obs 가 {} 인 10건의 **실행 순서상 위치**를 복원하라.
   조합마다 at 타임스탬프가 있다.
   - 뒤쪽에 몰려 있고 직전 조합의 obs.render_ms 가 이미 수십 초 → "렌더 지연의 결과" 확정
   - 처음부터 흩어져 있음 → 별개의 결손
   - posting S0 가 같은 거점의 map 조합 바로 뒤에 오는가(짝으로 오는가)
   그리고 failures[0].why 의 예외 원문(400자)을 읽어라. Playwright click 타임아웃은
   왜 못 눌렀는지를 call log 로 같이 싣는다 — not stable / intercepts pointer events /
   not visible 중 무엇인가. 그 문자열로 이 실행이 --node-timeout-ms 20000 이었는지도 확정된다.

3. docs/finding-map-panel-heatmap-2026-09-08.md §3-4
   results["<hub>|map"].obs.nodes[".mapshell .sp-head .sp-title"].text 를 읽어라.
   - "[selector-error]" 로 시작 → 노드가 없던 게 아니라 **못 잰** 것(2번과 같은 뿌리)
   - 빈 문자열 → 서브트리가 없던 것. 그때는 같은 조합의 .sp-sub · .b-item 계수와
     page_errors 를 같이 보고 reports/screens/<hub>__map.png 도 열어 확인하라.

4. 리포트 최상위의 sdk_boot_ms 와 preflight 를 읽어라.
   preflight.served 가 66 이고 served_missing 이 비었으면 그 실행에서도 gold 66/66 이
   성립했다는 뜻이다(finding-screen-s0 §7-3 이 기다리는 값).

[산출물]
docs/finding-screen-readout-2026-09-08.md 하나를 새로 쓴다. 담을 것:
  - 위 1~4 각각 "무엇을 읽었고 무엇이 갈렸나" 표
  - 세 문서의 어느 절이 이걸로 **닫혔는지 / 여전히 미결인지** 명시
  - 리포트에 그 필드가 아예 없었으면 "없었다"고 적는다(추정으로 채우지 않는다)
그리고 reports/screen_loop_2026-09-07.json 을 커밋한다 — .gitignore 207 줄의
`!reports/*.json` 이 예외로 열어 두었다. 앞으로의 진단이 이 파일을 다시 못 읽는 일이 없게.

[통과 조건]
L1_READOUT: 1~4 네 자리에 각각 실제로 읽은 값이 적혀 있다.
L1_CLOSES: 세 문서의 해당 절이 닫힘/미결로 판정돼 있다.
L1_COMMIT: reports/screen_loop_2026-09-07.json 이 git 에 올라갔다.
L1_NO_RERUN: screen_loop 을 한 번도 실행하지 않았다. reports/screen_loop.json 이 안 바뀌었다.

[금지]
scripts/screen_loop.py 수정, screen_loop 재실행, reports/screen_loop.json 덮어쓰기,
리포트에 없는 값을 추정으로 채우기, 값이 문서 서술과 다를 때 문서를 먼저 고치는 것
(차이부터 보고하라).
````

---

# L2 — C2 수정을 실제 지도에서 잰다

**왜 필요한가.** C2(커밋 9683dd5)는 **스텁 지도** 위에서 리스너 수만 셌다.
**ms 는 아무도 안 쟀다.** 실제 네이버 SDK 에서 그 리스너가 시간을 먹고 있었는지는 여기서 갈린다.

````text
SpaceOS 저장소 루트에서 작업한다. docs/prompts-local-pc-L1-L7-2026-09-08.md 의 공통 계약을
적용하라. 브랜치는 feat/l2-hubswitch-remeasure 이고 main 에서 딴다.
선행: L1 이 끝나 reports/screen_loop_2026-09-07.json 이 있어야 한다. 없으면 멈추고 보고하라.

[상황]
어제 실행에서 map 탭 hub-switch 초기 렌더가 거점을 바꿀수록 단조 증가했다(ms, 관측 순서):
  13234 18203 24172 29969 36234 37469 39422 40328 43218 43219 48046 48860 234687
예산은 3000ms 다(KPI "지도 로딩 3초"). 같은 실행의 tab-open 은 4750~7375ms 였고,
Platform 탭 hub-switch 는 6172ms 한 건뿐이라 map 탭 특유의 현상이다.

오늘 낮 클라우드가 원인을 특정하고(docs/finding-map-hubswitch-2026-09-08.md)
수정을 머지했다(커밋 9683dd5 · main 머지 535b88b):
  MapShell 이 거점마다 만드는 오버레이(폴리곤·점)에 붙인 클릭 리스너를 setMap(null) 이
  떼지 않아, 앱 수명 내내 죽지 않는 단 하나의 지도 인스턴스 위에 등록이 쌓였다.
  listenersRef 를 두고 clearOverlays() 가 setMap(null) 전에 떼도록 고쳤다.
  PageDashboard 는 오버레이 리스너와 지도 직결 리스너를 나눠 정리한다.
그 근거는 **스텁 지도 위 리스너 계수뿐이다**: 10회 전환에 live listeners 109 → 1859
(전환당 +175, removeListener 0) 였던 것이 수정 후 51 상수. ms 는 재지 않았다.

[먼저 — 실행]
  set PYTHONIOENCODING=utf-8
  python -u scripts/screen_loop.py --hubs yeonnam --canary
      ← 검사기가 진짜 화면을 보는지 확인. **실패가 나와야 정상**이다(없는 셀렉터를 넣는다).
  python -u scripts/screen_loop.py --fresh ^
      --out reports/screen_loop_2026-09-08_postfix.json ^
      --node-timeout-ms 20000
      ← 69조합(≈17거점)을 넘기면 Ctrl+C 로 끊어도 된다. 조합마다 리포트를 다시 쓴다.

⚠ --tabs map 으로 줄여 돌지 마라. 어제는 거점마다 4탭을 돌고 다음 거점으로 갔다
  (거점-major, map 탭 사이에 다른 세 탭이 끼어 있다). 탭을 빼면 누적 조건 자체가 달라져
  계열이 비교 불가다.
⚠ --node-timeout-ms 20000 은 어제와 같은 조건으로 재기 위한 것이지 완화가 아니다.
  --budget-ms 는 건드리지 마라.
⚠ --out 을 반드시 준다. 기본 경로는 어제 리포트를 덮는다.

[너의 일]
어제(reports/screen_loop_2026-09-07.json)와 오늘(위 새 파일)의 hub-switch render_ms 를
**거점 순서로 짝지어** 비교하고 셋을 판정하라.

1. 단조 증가가 사라졌는가. 사라졌으면 누적의 원인은 리스너였다.
   여전히 자라면 finding-map-hubswitch §6 의 후보 2·4·5 가 남는다 → L3 로 넘긴다.
2. 평평해진 뒤의 **절대값**이 예산 3000ms 안인가.
   ⚠ 그 문서 §1-1 이 못박은 것 — 첫 관측 13234ms 부터 이미 예산의 4.4배였다.
   누적이 사라져도 첫 회가 13초면 KPI 는 그대로 깨져 있다. 둘을 섞어서 말하지 마라.
3. obs.map.paths · divs · children 과 poly · dot 이 전환마다 상수로 유지되는가.

[산출물]
docs/finding-map-hubswitch-2026-09-08.md 에 §10 을 **추가**한다(§1~§9 는 그대로 둔다).
  - 두 계열 표(거점 순서로 짝지은 것) · 감소율 · 예산 대비 위치
  - 위 3의 계수
  - 남은 미결
그리고 §0 한 줄 결론 아래에 "2026-09-08 저녁 실측 → §10" 한 줄을 단다.
새 리포트 json 도 커밋한다.

[통과 조건]
L2_MEASURED: 실제 네이버 지도로 재고, 두 계열이 거점 순서로 짝지어져 있다.
L2_TWO_AXES: "누적이 사라졌는가"와 "예산 안인가"가 **따로** 판정돼 있다.
L2_HONEST: 예산 안에 못 들어왔으면 못 들어왔다고 적혀 있다.

[금지]
예산·타임아웃을 고쳐 통과시키기, 원인이 남아 있는데 이 자리에서 코드 고치기
(먼저 L3 로 확정한다), 재지 않은 값을 적기, scripts/screen_loop.py 수정.
````

---

# L3 — 페이지 리셋 A/B + 힙 스냅샷 (조건부)

**언제 보내나.** L2 에서 **단조 증가가 남았을 때만**. 사라졌으면 건너뛰고 L4 로 간다.
`finding-map-hubswitch` §7-4 가 "이 한 번의 실행이 §6 을 확정하거나 기각한다"고 지목한 자리다.

````text
SpaceOS 저장소 루트에서 작업한다. docs/prompts-local-pc-L1-L7-2026-09-08.md 의 공통 계약을
적용하라. 브랜치는 feat/l3-reset-ab 이고 main 에서 딴다.
선행: L2 재실행에서도 map 탭 hub-switch render_ms 가 거점마다 자란다는 것이 확인됐어야 한다.
그렇지 않으면 이 작업을 하지 말고 그 사실을 보고하라.

[상황]
C2(커밋 9683dd5)가 오버레이 클릭 리스너의 짝을 붙였는데도 누적이 남았다. 즉
docs/finding-map-hubswitch-2026-09-08.md §6 의 후보 중 리스너 말고 다른 것이 살아 있다.
그 문서가 남긴 미확정은 두 개다:
  §6-3 "짝이 없어서 GC 되지 않는다"는 네이버 SDK 내부 동작이라 코드로 확정 불가
  §7-4 페이지 리셋 A/B — 누적 가설의 직접 검정

[너의 일 — 둘 다 한다]

(1) 페이지 리셋 A/B
조합마다 page.reload() 를 넣은 **일회용** 실행을 만들어 어제와 같은 거점 순서로 돌려라.
  - 단조 증가가 사라지고 첫 회 근처에서 평평 → 누적이 원인이다(후보 1/2/4).
    C2 가 그중 리스너 하나만 뗀 것이므로 남은 후보를 코드에서 다시 좁혀라.
  - 그대로 자람 → 원인은 브라우저 세션 밖이다(후보 5). 그쪽을 먼저 본다.
⚠ 그 일회용 스크립트를 scripts/screen_loop.py 에 커밋하지 마라. 스크래치패드에 두고
  결과 json 만 reports/screen_loop_ab_2026-09-08.json 으로 낸다.

(2) 힙 스냅샷 (§7-1)
--headed 로 띄우고 DevTools 로 거점을 5회 이상 바꾸며 전환 사이에 스냅샷을 찍어라.
  - Polygon / Marker 인스턴스 수가 전환마다 누적하는가, GC 후 떨어지는가
  - 남는다면 retainer 경로가 무엇인가 — naver.maps.Event 의 레지스트리인가, map 인스턴스인가
  - 콘솔에서 아래 두 줄의 **실제 반환값**을 적어라:
      naver.maps.Event.hasListener(<setMap(null) 한 polygon>, 'click')
      typeof naver.maps.Event.clearInstanceListeners
    C2 가 뗀 뒤에도 true 가 나오면 짝이 덜 붙은 것이다. clearInstanceListeners 가
    function 이면 그게 남은 후보의 처방일 수 있다 — 다만 이 작업에서 적용하지는 마라.

[산출물]
docs/finding-map-hubswitch-2026-09-08.md 에 §11 을 추가한다.
  - A/B 두 계열과 판정(누적이 원인인가 아닌가)
  - 힙 스냅샷 수치와 위 두 줄의 반환값
  - §6 의 후보 목록 중 무엇이 **기각**되고 무엇이 남았는지 — 하나로 좁혀지면 그 하나를 지목
  - 좁혀지지 않으면 "좁혀지지 않았다"고 적는다. 그럴듯한 원인을 지어내지 마라.

[통과 조건]
L3_AB: A/B 두 계열이 있고 누적 가설이 확정 또는 기각됐다.
L3_HEAP: 힙 수치와 콘솔 두 줄의 실제 반환값이 적혀 있다.
L3_NARROW: §6 후보 목록의 생사가 각각 적혀 있다.

[금지]
원인 확정 전 코드 수정, scripts/screen_loop.py 변경(일회용 스크립트는 커밋하지 않는다),
예산 완화, 재지 않은 값 서술.
````

---

# L4 — hapjeong heatmap 미호출 (조건부)

**언제 보내나.** L2/L5 재실행에서 이 실패가 **남았을 때만**.
`hapjeong` 은 순서상 14번째 거점이라, C2 로 누적이 사라졌으면 같이 사라졌을 수 있다.

````text
SpaceOS 저장소 루트에서 작업한다. docs/prompts-local-pc-L1-L7-2026-09-08.md 의 공통 계약을
적용하라. 브랜치는 feat/l4-hapjeong-heatmap 이고 main 에서 딴다.

[먼저 — 남아 있는지부터 확인한다]
  python -u scripts/screen_loop.py --hubs hapjeong --tabs map --headed ^
      --out reports/screen_loop_hapjeong.json
gate_seen 이 200 으로 잡히면 **이 작업은 여기서 끝난다.** 그 사실만 보고하고 멈춰라
(C2 수정으로 해소된 것이다 — 고칠 것이 없다).

[상황 — 실패가 남았을 때만 아래를 한다]
어제 실행에서 map 탭 판정 실패로 "거점을 바꿨는데 /heatmap/buildings?district=hapjeong 를
부르지 않았다"가 나왔다. 오늘 낮 클라우드가 이것을 (A) 제품 결손으로 판정했다
(docs/finding-map-panel-heatmap-2026-09-08.md §2). 그 문서가 배제한 것:
  - hapjeong 은 합성 거점이 아니라 Gold Tier1 이다 — building_vacancy_geojson 이 292 features 를 낸다
  - MapShell 의 vacancy_source 필터는 **목록만** 거른다. 호출을 거르는 분기가 없다
    (건물 조회 이펙트는 districtId 가 바뀌면 조건 없이 getBuildingVacancy 를 부른다)
  - 옵션이 없었다면 검사기는 trigger="missing-option" 으로 지나가며 다른 문구를 낸다
  - 404 여도 gate_seen 은 "404" 로 잡힌다 — "부르지 않았다"가 안 나온다
남는 읽기는 하나다: select_option 이후 **15초 안에 요청이 나가지 못했다**.
setDistrictId → 커밋 → 이펙트 → fetch 사슬이 그 시간 안에 못 돈 것이고, 그것은 앱 쪽이다.

[너의 일]
그 사슬 어디서 막히는지 Performance 패널로 전환 1회를 녹화해 구간을 갈라라
(오버레이 생성 / React 커밋 / GC 가 각각 몇 %인가 — finding-map-hubswitch §7-5 와 같은 방법).
동시에 그 문서 §4-C 가 코드에서 읽기만 한 "재그리기 3~4회"를 console.count() 로 실측하라.

수정 범위:
  - 20줄 안쪽으로 명확하면 고친다. 그보다 크면 **문서만** 쓰고 수정안을 제안한다.
  - scripts/screen_loop.py 는 고치지 않는다. finding-map-panel-heatmap §4 가
    "명세는 두 건 모두 고칠 것이 없다"고 판정했고 그 판정을 유지한다.
  - 고쳤으면 주석에 "왜 그래야 했나, 안 그러면 무엇이 깨지나"를 한국어로 남긴다.

[산출물]
docs/finding-map-panel-heatmap-2026-09-08.md 에 §5 를 추가한다(실측 구간 · 판정 · 수정 여부).
고쳤다면 같은 명령을 다시 돌려 gate_seen 이 200 으로 잡히는 것을 확인하고 그 값을 적는다.

[통과 조건]
L4_RECHECK: 먼저 남아 있는지 확인했고 그 결과가 적혀 있다.
L4_PROFILE: 막히는 구간이 실측(Performance 녹화 · console.count)으로 갈렸다.
L4_VERIFIED: 고쳤다면 재실행에서 gate_seen 200 + npm run build 통과.
L4_NO_SPEC_EDIT: scripts/screen_loop.py 가 안 바뀌었다.

[금지]
명세(검사기) 수정, 예산·타임아웃 완화, 20줄을 넘는데 밀어붙여 고치기,
판정 없이 고치기, 백엔드 데이터 계약 변경.
````

---

# L5 — 66거점 264조합 전수 (무인)

**언제 보내나.** L2(·L3·L4)가 깨끗해진 뒤, 자리를 비울 때.
깨진 채로 264조합을 도는 것은 시간 낭비다.

````text
SpaceOS 저장소 루트에서 작업한다. docs/prompts-local-pc-L1-L7-2026-09-08.md 의 공통 계약과
/autorun 규칙(절전 억제·인코딩·감시·체크포인트)을 적용하라.
브랜치는 feat/l5-screen-loop-full 이고 main 에서 딴다.

[상황]
어제 264조합 전수가 69조합에서 중단됐다(finished 가 리포트에 없다).
그 뒤 C2(오버레이 리스너 정리)가 머지됐고, 오늘 저녁 L2 에서 앞부분을 실측했다.
이제 전수를 다시 건다. 몇 시간 걸리므로 무인으로 돌린다.

[실행]
  set PYTHONIOENCODING=utf-8
  if not exist reports\logs mkdir reports\logs
  powershell -ExecutionPolicy Bypass -File scripts\keep_awake.ps1 -Command ^
    "python -u scripts/screen_loop.py --fresh > reports\logs\screen_loop_2026-09-08.log 2>&1"

- 이 노트북은 Modern Standby(S0) 라 전원 설정만으로는 안 잔다고 보장하지 못한다.
  keep_awake.ps1 로 감싸면 명령이 끝날 때 자동으로 놓아준다.
- **AC 전원**에 꽂는다. 배터리에서는 무선 어댑터 절전 때문에 네트워크 바운드 작업이 크게 느리다.
- 중단되면 --fresh 를 **빼고** 다시 부른다(조합마다 리포트를 다시 쓰므로 이어받는다).
  실패분만 다시 볼 때는 --retry-failed.

[너의 일 — 실행이 끝난 뒤]
1. finished 가 리포트에 찍혔는지 확인하라. 없으면 몇 조합에서 멈췄는지와 마지막 조합을 적는다.
2. 실패를 S1(콘솔·5xx) / S2(캔버스·SDK) / S3(마커·결론문장·거점목록) / S4(예산 초과)
   네 단계로 분류해 표로 내라.
3. 각 실패가 (a) 화면 버그인지 (b) 검사기 셀렉터 문제인지 판정하라. 근거는 reports/screens/
   스크린샷과 실제 소스다 — 추측하지 마라.
   전례: `.b-name` 이 목록행과 상세패널 양쪽에 있어 querySelector 가 목록 첫 행을 집은 적이
   있다(상세는 `.b-detail .b-name` 로 좁혀야 한다). 같은 양식을 의심하라.
4. **4xx 는 실패로 세지 않는다.** 이 저장소에서 404 는 "아직 수집 안 함"인 자리가 있다
   (/ai/recommend-industry 404 = 400m 안에 노드 없음). 5xx 만 고장이다.
5. render_ms 를 거점 순서로 세워 단조 증가가 66거점 전체에서도 없는지 확인하라 —
   L2 는 앞 17거점만 봤다.

[산출물]
- reports/screen_loop.json 을 reports/screen_loop_2026-09-08_full.json 으로 복사해 커밋한다.
- docs/finding-screen-full-2026-09-08.md 에 위 1~5 를 적는다.
- (b) 로 판정된 것이 있으면 **고치지 말고** 목록만 낸다 — 검사기 수정은 별도 작업이다.

[통과 조건]
L5_FINISHED: finished 가 찍혔거나, 어디서 왜 멈췄는지 적혀 있다.
L5_TRIAGE: 실패가 S1~S4 로 분류되고 각각 (a)/(b) 판정과 근거가 있다.
L5_MONOTONIC: 66거점 전체의 render_ms 계열이 표로 있고 단조 증가 여부가 판정돼 있다.
L5_COMMIT: 전수 리포트가 git 에 올라갔다.

[금지]
예산·타임아웃 완화, 실패를 줄이려 검사기 셀렉터 고치기, 4xx 를 실패로 세기,
전수를 끝내지 않고 "통과"로 적기.
````

---

# L6 — 앵커 격차 축 분해 (09-07 T3 이 미완)

**왜 PC 인가.** `data/bronze`·`data/silver` 가 클라우드에 없다.
**미완 근거**: `docs/finding-anchor-gap-2026-09.md` 의 절 목록이 §5 에서 끝난다 — §6 이 없다.

````text
SpaceOS 저장소 루트에서 작업한다. docs/prompts-local-pc-L1-L7-2026-09-08.md 의 공통 계약을
적용하라. 브랜치는 feat/l6-anchor-gap-axes 이고 main 에서 딴다.

[상황]
docs/finding-anchor-gap-2026-09.md §5 가 "데스크톱이 필요하다"고 남긴 자리가 그대로 비어 있다
(그 문서에 §6 이 없다 = 09-07 런북 T3 이 미실행이다). bronze/silver 가 있는 이 PC 에서만 된다.

[먼저 — 실행]
  set PYTHONIOENCODING=utf-8
  python -m data.pipelines.calibrate_vacancy yeonnam sinchon hongdae
  python -m data.analyze_anchor_population yeonnam sinchon hongdae
⚠ 인자 없이 돌리면 ACTIVE_HUBS 66거점을 전부 돈다. slug 를 반드시 명시한다.

[너의 일]
풀 것 하나: rone_aligned.mid 가 서빙 대표값보다 높은 이유가 세 축 중 어느 것인가.
  축A 모집단 확장 (3층↑ 또는 330㎡ 초과 · 상가 주용도)
  축B 면적가중 (호실 기준 → 면적 기준)
  축C 층 단위 분자 (active_floors_lo/hi)
지금 그 문서 §3-1 은 층수만 쓴 근사라 330㎡ 조건이 빠져 있고, 그래서 어느 축이 얼마를
밀었는지 못 가른다. calibrate_vacancy 를 축별로 끄고 돌려 3거점에서 기여도를 %p 로 갈라라.

기준값 — 문서에 이미 적힌 것이다. **재현되는지 먼저 대조하라.**
  서빙 대표값       연남 12.53 · 신촌 17.19 · 홍대 14.97 %
  rone_aligned.mid  연남 20.8  · 신촌 19.8  · 홍대 20.1  %
  근사 절단값       연남 14.92 · 신촌 20.35 · 홍대 15.96 %
  ※ 신촌만 mid 가 절단값보다 낮다 — 축이 서로 상쇄되는 자리다. 여기부터 봐라.

[산출물]
- reports/anchor_gap_axes_2026-09-08.json (기계가 읽을 값)
- docs/finding-anchor-gap-2026-09.md 에 §6 추가: 축별 기여도 표(3거점 × A/B/C, %p) +
  신촌 역전의 설명 + 남은 미결

[통과 조건]
L6_AXES: 축 A/B/C 기여도가 3거점에서 %p 로 갈렸다.
L6_SINCHON: 신촌 역전이 설명되거나, 설명 못 했으면 그렇게 적혀 있다.
L6_NO_GOLD_EDIT: data/gold 산출물이 안 바뀌었다(이건 진단이지 재빌드가 아니다).

[금지]
gold 산출물 변경, 값이 문서와 다를 때 문서를 먼저 고치는 것(차이부터 보고하라),
API 신규 호출(이 두 스크립트는 수집이 아니다).

[왜 이게 다음에 쓰이나 — 참고]
이 결과가 폰 트랙 B16(M2-1 앵커 라벨 정렬)의 입력이다. 지금 프로덕션에는 같은 거점의
공실률이 12.5% 와 20.8% 로 두 개 떠 있다.
````

---

# L7 — `/verify` · 머지 · 배포

**마지막에 한 번.** L1~L6 브랜치를 여기서 main 에 모으고, 그 푸시가 프로덕션 배포를 태운다.

````text
SpaceOS 저장소 루트에서 작업한다. docs/prompts-local-pc-L1-L7-2026-09-08.md 의 공통 계약을
적용하라. 이 작업만 main 을 만진다.

[1단계 — 정적 검사와 프론트 테스트를 PC 에서 한 번은 돌린다]
  cd apps\frontend
  npm ci
  npm run test          ← 오늘 머지된 vitest (MapShell · HubExplorer · PostingConsole)
  npm run build         ← tsc -b + vite build
  cd ..\backend
  py -3.11 -m pytest -q      ← .venv 가 있으면 .venv\Scripts\python -m pytest -q
  cd ..\..
클라우드가 통과를 봤지만 node·python 버전이 갈릴 수 있는 자리라 PC 에서 한 번 확인한다.
실패하면 **머지하지 말고** 거기서 멈춰 보고하라.

[2단계 — /verify]
/verify 를 돌리되, 오늘 main 에 들어간 것 다섯 개를 화면에서 확인하는 데 초점을 둔다.
전부 오늘 머지됐고 **아무도 실제 지도로 안 봤다**.

1. C2(9683dd5) MapShell·PageDashboard 의 리스너 정리 — 건물 클릭이 여전히 되는가.
   ⚠ 리스너를 **떼는** 수정이라 클릭이 죽는 것이 이 수정의 전형적인 회귀다.
   거점을 3회 바꾼 뒤 마지막 거점에서 폴리곤·핀을 클릭 → 상세 패널이 뜨는지 본다.
   패널 확인은 `.b-detail .b-name` 로 좁혀라(`.b-name` 은 목록행에도 있어 첫 행을 집는다).
2. 줌 14(Marker 경로)와 줌 17(폴리곤 경로) 양쪽에서 1을 반복한다 — 다른 코드다.
   MapShell 의 PIN_MAX_ZOOM 이 15 이므로 그 경계를 넘나든다.
3. PageDashboard(#board)에서도 같은 확인.
4. 층 스택 + 네이버 거리뷰가 그대로 뜨는가 — 촬영일과 "공실 판정 근거 아님" 문구 동반.
5. 콘솔 pageerror 0.
결과는 reports/full_verify.json 에 남긴다. 실패는 고치지 말고 먼저 목록으로 보고하라.

[3단계 — 게이트 재확인]
  python scripts/pppp_status.py
숫자가 아니라 **게이트**를 본다. 오늘 작업으로 낡은 서술이 생겼으면 경위를 남겨 고친다
(지우지 않는다 — 이 저장소는 낡은 선언을 지우지 않고 경위를 덧붙인다).

[4단계 — 머지]
L1~L6 중 **통과 조건을 채운 브랜치만** main 에 머지한다. 채우지 못한 것은 브랜치로 남긴다.
  git checkout main && git pull origin main
  git merge --no-ff feat/l1-screen-readout-2026-09-08   (이하 통과한 것만)
충돌이 나면 손으로 해결하지 말고 무엇이 충돌했는지 보고하라 — 같은 문서의 다른 절을
여러 작업이 건드렸을 수 있다(finding-map-hubswitch 는 §10·§11 두 자리다).

[5단계 — 배포]
  git push -u origin main
  python scripts/watch_deploy_verify.py
⚠ main 푸시는 GitHub Actions → Cloud Run 프로덕션 배포를 태운다(문서 한 줄이라도 마찬가지다).
2단계에서 실패가 났으면 푸시 전에 docs/deploy-cloud-run.md 를 읽고 판단한다.
프로덕션은 https://spaceos-twin.web.app 다. 배포 후 거점 하나를 실제로 열어 확인하라.

[통과 조건]
L7_STATIC: npm run test · npm run build · pytest 결과가 적혀 있다(미실행을 통과로 적지 않는다).
L7_PIXEL: 위 1~5 항목이 각각 확인/실패로 적혀 있다.
L7_MERGE: 머지한 브랜치와 남긴 브랜치가 이유와 함께 적혀 있다.
L7_DEPLOY: 배포 결과와 프로덕션 확인 결과가 적혀 있다.

[금지]
검사 실패를 남긴 채 머지, git add -A, force push, 통과 조건 미달 브랜치 머지,
배포 확인 없이 "배포됐다" 적기.
````

---

## 부록. 한 줄로 무엇을 닫는가

| ID | 지금 열려 있는 것 | L 이 닫는 것 |
|---|---|---|
| L1 | C1 §7-2 · C3 §7-1·§7-2 · C4 §3-4 가 리포트를 못 읽어 미결 | 읽기만으로 셋 |
| L2 | C2 가 스텁 위 리스너 계수뿐 — ms 미측정 | 실제 지도 ms |
| L3 | "짝이 없어서 GC 안 된다"가 코드로 확정 불가 | A/B + 힙으로 확정·기각 |
| L4 | hapjeong 요청이 15초 안에 안 나갔다(제품 결손) | 남았는지 → 구간 실측 |
| L5 | 어제 전수가 69조합에서 중단 | 264조합 완주 |
| L6 | 앵커 격차가 세 축 중 어느 것인지 미분해 | %p 로 분해 |
| L7 | 오늘 머지된 다섯이 전부 화면 미확인 | 픽셀 확인 → 배포 |

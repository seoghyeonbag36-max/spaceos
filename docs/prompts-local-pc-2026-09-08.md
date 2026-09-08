# 로컬 PC 작업 프롬프트 — 2026-09-08 저녁

> 오늘 클라우드(Claude Code on the web)가 C1~C5 를 끝내 `main` 에 다 들어갔다.
> **그 다섯 개는 전부 화면을 못 본 상태로 머지됐다.** 이 문서는 그것을 실증하는 순서와,
> 폰·클라우드에서 구조적으로 못 하는 나머지를 프롬프트로 만든 것이다.
> 항목마다 ① 왜 PC 여야 하는가 ② 붙여넣을 명령 ③ 붙여넣을 프롬프트 ④ 통과 조건 순이다.
>
> 앞선 판: [runbook-desktop-2026-09-07.md](runbook-desktop-2026-09-07.md)(T1~T4) ·
> 오늘 낮 트랙: [cloud-workday-claude-2026-09-08.md](cloud-workday-claude-2026-09-08.md) ·
> 폰 트랙: [prompts-mobile-2026-09-08.md](prompts-mobile-2026-09-08.md)
>
> **붙여넣을 프롬프트만 필요하면** → [prompts-local-pc-L1-L7-2026-09-08.md](prompts-local-pc-L1-L7-2026-09-08.md).
> L1~L7 을 **단독으로 서는** 프롬프트 일곱 개로 다시 썼다(새 세션에 하나씩 붙여넣는다).
> 이 문서의 프롬프트는 그 축약본이다 — 둘이 어긋나면 저쪽이 기준이다.

---

## 0. 왜 이것들이 PC 몫인가 (2026-09-08 클라우드 세션 실측)

| 막힌 것 | 근거 |
|---|---|
| 네이버 지도 실렌더 | `oapi.map.naver.com` 이 컨테이너에서 막혔고 `VITE_NAVER_MAPS_KEY_ID` 가 PC 에만 있다. C2 는 **스텁 지도** 위에서 리스너만 세었다(커밋 9683dd5) |
| `reports/screen_loop.json` 판독 | 그 파일은 저장소에 **없다**(커밋된 적 없음 · PC 에만 있다). C1 §7-2 · C3 §7-1~7-3 · C4 §3-4 가 전부 이 파일 하나를 기다린다 |
| ms 재측정 | 오늘 머지된 것 중 "빨라졌다"고 말할 수 있는 문서는 **하나도 없다** — 공통 계약이 그걸 금지했다 |
| 앵커 격차 축 분해 | `data/bronze`·`data/silver` 가 클라우드에 없다(09-07 T3 이 그대로 미완 — `finding-anchor-gap-2026-09.md` 에 §6 이 아직 없다) |
| 수집·재학습 | `.gitignore` 가 bronze/silver 를 막아 원천이 없고, 건축HUB 키·쿼터도 PC 에만 있다 |

반대로 **클라우드가 이미 통과 확인한 것**(PC 에서 다시 안 해도 된다):
`npm run build` · `npm run lint` · 백엔드 `pytest` · 새 vitest 3파일.
단 vitest 는 **L7 에서 한 번은 PC 로 돌린다** — CI 와 로컬 node 버전이 갈릴 자리다.

---

## 1. 오늘 밤의 우선순위 한 줄

**L1 → L2 → L3 → (L4) → L5 → L6 → L7**

L1 이 맨 앞인 이유는 하나다. `reports/screen_loop.json` 은 **어제 실행의 유일한 사본**이고,
`screen_loop.py` 는 기본 출력 경로가 그 파일이라 **다시 돌리는 순간 덮인다**
([screen_loop.py:103](../scripts/screen_loop.py#L103) · 이어받기 설계 §제약 4).
읽기 전에 재실행하면 오늘 머지된 진단 세 개가 영구히 미결로 남는다.

---

## 2. 준비 (5분)

PowerShell 3개. **`PYTHONIOENCODING` 을 생략하지 말 것** — cp949 에 `—`(em dash)가 없어
로그 리다이렉트 순간 UnicodeEncodeError 로 죽는다(2026-08-19 실측).

```powershell
# 터미널 1 — 백엔드
cd apps\backend
py -3.11 -m uvicorn app.main:app --port 8000

# 터미널 2 — 프론트
cd apps\frontend
npm run dev

# 터미널 3 — 작업용
set PYTHONIOENCODING=utf-8
git fetch origin main
git checkout main
git pull origin main
git status --short        # ⚠ screen_loop.py 에 미커밋 변경이 있다면 여기서 드러난다
```

준비 확인 — 셋 다 값이 나와야 다음으로 간다.

```powershell
curl http://localhost:8000/health
curl http://localhost:5173
type apps\frontend\.env | findstr VITE_NAVER_MAPS_KEY_ID
```

⚠ `git status` 가 `scripts/screen_loop.py` 를 미커밋으로 보이면 **L1 전에 그것부터 판단한다.**
오늘 클라우드 작업 네 개가 "PC 에 미커밋 변경이 있다"는 이유로 이 파일을 건드리지 않았다.
그 변경이 무엇인지 모른 채 재실행하면 어제와 다른 검사기로 재는 것이 된다.

---

## 3. L1 · 어제 리포트를 읽는다 — **재실행보다 먼저** (25분)

**왜 PC 인가.** 그 파일이 PC 에만 있다. 그리고 **읽기만으로 세 문서의 미결이 닫힌다.**

### 명령 — 사본부터 뜬다 (이 두 줄이 이 문서에서 제일 중요하다)

```powershell
copy reports\screen_loop.json reports\screen_loop_2026-09-07.json
dir reports\screens | find /c ".png"
```

### 프롬프트

```
어제(09-07) 66거점 화면 회귀 전수 실행이 69조합에서 중단됐고, 그 리포트가
reports/screen_loop.json 에 그대로 남아 있다. 사본을 reports/screen_loop_2026-09-07.json
으로 떠 두었다. **읽기만 한다 — 코드도 리포트도 고치지 마라.**

오늘 클라우드가 낸 진단 세 개가 전부 이 파일 하나를 못 읽어 미결로 남겼다.
아래 순서로 그 미결을 닫아라. 각 항목에 그 문서의 절 번호를 적어 뒀다.

1. C1 §7-2 — map 조합의 시계열을 뽑아라.
   obs.map.paths · divs · children 이 단조 증가하는가(→ DOM 이 남는다),
   평평한가(→ 힙만 샌다). obs.map.poly · dot 이 그 거점 건물 수와 맞는가.
   obs.tab_open_ms · obs.gate_seen 도 같이 낸다.
   obs.hub ↔ obs.render_ms 실제 대응으로 Spearman 을 다시 계산해
   C1 §2-3 이 세운 가정을 지워라.

2. C3 §7-1·§7-2 — S0 10건(error·obs 가 {}) 의 실행 순서상 위치를 복원하라.
   조합마다 at 타임스탬프가 있다. 뒤쪽에 몰려 있고 직전 조합의 render_ms 가 이미
   수십 초면 "렌더 지연의 결과"가 확정된다. 처음부터 흩어져 있으면 별개 결손이다.
   failures[0].why 의 예외 원문(400자)도 읽어라 — Playwright click 타임아웃은
   not stable / intercepts pointer events / not visible 중 무엇인지를 call log 로 싣는다.
   그 문자열로 이 실행이 --node-timeout-ms 20000 이었는지도 확정된다.

3. C4 §3-4 — results["<hub>|map"].obs.nodes[".mapshell .sp-head .sp-title"].text 를 읽어라.
   "[selector-error]" 로 시작하면 못 잰 것(=가와 같은 뿌리),
   빈 문자열이면 서브트리가 없던 것이다. 후자면 같은 조합의 .sp-sub · .b-item 계수와
   page_errors 를 같이 보고 reports/screens/<hub>__map.png 도 열어라.

4. 최상위의 sdk_boot_ms 와 preflight 를 읽어라(C3 §7-3).
   preflight.served 가 66 이고 served_missing 이 비었으면 그 실행에서도 gold 66/66 이
   성립했다는 뜻이다.

[산출물]
docs/finding-screen-readout-2026-09-08.md 하나. 위 1~4 각각에 "무엇을 읽었고 무엇이
갈렸나"를 표로 적고, 세 문서(C1/C3/C4)의 어느 절이 이걸로 닫혔는지 명시해라.
값이 문서의 서술과 다르면 문서를 고치지 말고 **차이부터 보고**해라.
그리고 reports/screen_loop_2026-09-07.json 을 커밋해라 — .gitignore 207 줄의
`!reports/*.json` 이 예외로 열어 두었다. 앞으로의 진단이 이 파일을 다시 못 읽는 일이 없게.

[금지]
scripts/screen_loop.py 수정, reports/screen_loop.json 덮어쓰기, 재실행,
리포트에 없는 값을 추정으로 채우기.
```

**통과 조건**: 새 문서에 C1 §7-2 · C3 §7-1·§7-2 · C4 §3-4 네 자리가 각각 "닫힘/여전히 미결"로
판정돼 있다 + `reports/screen_loop_2026-09-07.json` 이 git 에 올라간다.

---

## 4. L2 · C2 수정이 실제로 먹었는가 — ms 를 처음으로 잰다 (40분)

**왜 PC 인가.** C2(커밋 9683dd5)는 **스텁 지도** 위에서 리스너 수만 셌다
(수정 전 10회 전환에 109 → 1,859, 수정 후 51 상수). **ms 는 아무도 안 쟀다.**
실제 네이버 SDK 에서 그 리스너가 실제로 시간을 먹고 있었는지는 여기서만 갈린다.

### 명령 — 어제와 **같은 순서**로 돌려야 비교가 된다

조합 순서는 거점-major 다([screen_loop.py:808](../scripts/screen_loop.py#L808)).
어제 실행이 앞에서부터 69조합(≈17거점)까지 갔으므로 같은 앞부분을 같은 순서로 재현한다.

```powershell
set PYTHONIOENCODING=utf-8

# (1) 검사기가 진짜 화면을 보는지 먼저 — 실패가 나와야 정상이다
python -u scripts/screen_loop.py --hubs yeonnam --canary

# (2) 어제 앞부분 재현 · 어제 리포트를 덮지 않도록 --out 을 따로 준다
#     탭을 빼지 않는다(기본 4탭) — 어제와 같은 거점-major 순서여야 비교가 된다
python -u scripts/screen_loop.py --fresh ^
  --out reports/screen_loop_2026-09-08_postfix.json ^
  --node-timeout-ms 20000
#     ↑ 69조합(≈17거점)을 넘기면 Ctrl+C 로 끊어도 된다. 조합마다 리포트를 다시 쓰므로
#       거기까지가 그대로 남는다(설계 제약 4).

# (3) 결과 요약
python -c "import json;d=json.load(open('reports/screen_loop_2026-09-08_postfix.json',encoding='utf-8'));r=d['results'];print(len(r));print([(k,v.get('obs',{}).get('render_ms')) for k,v in r.items() if k.endswith('|map')][:20])"
```

⚠ `--node-timeout-ms 20000` 은 **어제와 같은 조건으로 재기 위한 것**이지 완화가 아니다.
예산(`--budget-ms 3000`)은 건드리지 않는다.
⚠ `--tabs map` 으로 줄여 돌지 말 것 — 어제는 거점마다 4탭을 돌고 다음 거점으로 갔다
(map 탭 사이에 다른 세 탭이 끼어 있다). 탭을 빼면 **누적 조건 자체가 달라져** 계열이 비교 불가다.

### 프롬프트

```
C2(커밋 9683dd5, main 머지 535b88b)가 map 오버레이 클릭 리스너에 removeListener 짝을
붙였다. 그 근거는 스텁 지도 위 리스너 계수뿐이고 ms 는 아무도 안 쟀다.
방금 실제 네이버 지도로 page 탭 전수를 다시 돌려
reports/screen_loop_2026-09-08_postfix.json 에 남겼다. 어제 것은
reports/screen_loop_2026-09-07.json 이다.

[너의 일]
두 실행의 hub-switch render_ms 를 **거점 순서로 짝지어** 비교하고 다음 셋을 판정하라.

1. 단조 증가가 사라졌는가.
   어제: 13234 18203 24172 29969 36234 37469 39422 40328 43218 43219 48046 48860 234687
   오늘 계열이 평평하면 누적은 리스너였다. 여전히 자라면 C1 §6 의 후보 2·4·5 로 돌아간다.
2. 평평해진 뒤의 절대값이 예산 3,000ms 안인가.
   ⚠ C1 §1-1 이 못박은 것 — **첫 관측 13,234ms 부터 이미 예산의 4.4배**였다.
   누적이 사라져도 첫 회가 13초면 KPI 는 그대로 깨져 있다. 둘을 섞어서 말하지 마라.
3. obs.map.paths·divs·children 과 poly·dot 이 전환마다 상수로 유지되는가.

[산출물]
docs/finding-map-hubswitch-2026-09-08.md 에 §10 을 추가한다(§1~§9 는 그대로 둔다).
담을 것: 두 계열 표 · 감소율 · 예산 대비 위치 · 위 3의 계수 · 남은 미결.
그리고 §0 한 줄 결론 아래에 "2026-09-08 저녁 실측" 한 줄을 달아 §10 을 가리켜라.

[규칙]
- 이번에는 실제 지도를 띄웠으므로 ms 를 말해도 된다. 단 **잰 것만** 말한다.
- 예산·타임아웃을 고쳐 통과시키지 마라. 안 줄었으면 안 줄었다고 적어라.
- 원인이 남아 있으면 이 자리에서 코드를 고치지 마라 — 먼저 L3(A/B)로 확정한다.
```

**통과 조건**: 두 계열 비교표 + 판정 3개. 예산 안에 못 들어왔으면 **들어왔다고 쓰지 않는다.**

---

## 5. L3 · 페이지 리셋 A/B — 누적 가설의 직접 검정 (30분)

**왜 PC 인가.** C1 §7-4 가 "이 한 번의 실행이 §6 을 확정하거나 기각한다"고 지목한 자리다.
L2 에서 단조 증가가 **남았을 때만** 돌린다. 사라졌으면 이 항목은 건너뛰고 L4 로 간다.

### 프롬프트

```
L2 재실행에서도 map 탭 hub-switch render_ms 가 거점마다 자란다.
C1 §7-4 의 A/B 를 지금 한다.

조합마다 page.reload() 를 넣은 **일회용** 실행을 만들어 같은 거점 순서로 돌려라.
  - 단조 증가가 사라지고 첫 회 근처에서 평평해지면 → 누적이 원인이다(C1 후보 1/2/4).
    C2 가 그중 리스너 하나만 뗐다는 뜻이므로, 남은 후보를 코드에서 다시 좁혀라.
  - 그대로 자라면 → 원인은 브라우저 세션 밖이다(후보 5). 그쪽을 먼저 본다.

⚠ 그 일회용 스크립트를 scripts/screen_loop.py 에 커밋하지 마라. 스크래치패드에 두고
결과 json 만 reports/ 로 낸다(reports/screen_loop_ab_2026-09-08.json).

같이 볼 것 — C1 §7-1(힙):
DevTools 로 거점을 5회 이상 바꾸며 스냅샷을 찍고, Polygon/Marker 인스턴스가 전환마다
누적하는지, GC 후 떨어지는지, 남으면 retainer 경로가 무엇인지 본다. 콘솔에서
  naver.maps.Event.hasListener(<setMap(null) 한 polygon>, 'click')
  typeof naver.maps.Event.clearInstanceListeners
두 줄의 실제 반환값을 적어라. C2 가 뗀 뒤에도 true 가 나오면 짝이 덜 붙은 것이다.

[산출물] docs/finding-map-hubswitch-2026-09-08.md §11.
[금지] 원인 확정 전 코드 수정, 예산 완화, screen_loop.py 변경.
```

**통과 조건**: A/B 두 계열 + 힙 스냅샷 수치. C1 §6 의 후보 목록이 **하나로 좁혀지거나 전부 기각**된다.

---

## 6. L4 · hapjeong heatmap 미호출 — 남았는지부터 본다 (20분 · 조건부)

C4 는 이것을 **(A) 제품 결손**으로 판정했다. `hapjeong` 은 Gold Tier1 292동이고,
"합성 거점이면 404 라 건너뛴다"는 분기는 목록만 거를 뿐 **호출을 거르는 분기가 없다**.
남은 읽기는 하나다 — `select_option` 뒤 15초 안에 요청이 못 나갔다.
그리고 `hapjeong` 은 순서상 **14번째**, 즉 어제 render_ms 가 이미 수 분이던 지점 바로 뒤다.

**그래서 이건 C2 이후에 자동으로 사라졌을 수 있다.** 먼저 확인하고, 남았을 때만 고친다.

```powershell
python -u scripts/screen_loop.py --hubs hapjeong --tabs map --headed ^
  --out reports/screen_loop_hapjeong.json
```

### 프롬프트 (실패가 남았을 때만)

```
C2 수정 뒤에도 hapjeong 의 map 조합이 /heatmap/buildings?district=hapjeong 를
15초 안에 못 부른다. reports/screen_loop_hapjeong.json 과 --headed 로 본 화면이 근거다.

docs/finding-map-panel-heatmap-2026-09-08.md §2 가 여기까지 좁혀 놨다 —
분기 문제가 아니라 setDistrictId → 커밋 → 이펙트 → fetch 사슬이 그 시간 안에 못 돈 것이다.
그 사슬 어디서 막히는지 Performance 패널로 한 번 녹화해 구간을 갈라라.

수정이 20줄 안쪽으로 명확하면 고치고, 그보다 크면 문서만 쓴다.
scripts/screen_loop.py 는 고치지 않는다 — C4 §4 가 "명세는 두 건 모두 고칠 것이 없다"고
판정했고 나도 그 판정을 유지한다.

[통과 조건] 수정 후 같은 명령으로 gate_seen 이 200 으로 잡힌다. 화면으로도 확인한다.
```

---

## 7. L5 · 66거점 전수 재실행 — 자리 비울 때 (야간 무인)

`/autorun` 규칙을 따른다(절전 억제 · UTF-8 · 체크포인트). 264조합이라 몇 시간 걸린다.
L2/L3 이 깨끗해진 **뒤에** 건다 — 깨진 채로 264조합을 도는 것은 시간 낭비다.

```powershell
set PYTHONIOENCODING=utf-8
if not exist reports\logs mkdir reports\logs
powershell -ExecutionPolicy Bypass -File scripts\keep_awake.ps1
python -u scripts/screen_loop.py --fresh > reports\logs\screen_loop_2026-09-08.log 2>&1
```

중단되면 같은 명령에서 `--fresh` 를 빼고 다시 부른다(이어받기 — 설계 제약 4).
실패분만 다시 볼 때는 `--retry-failed`.

**통과 조건**: `finished` 가 리포트에 찍힌다 + 실패를 S1~S4 로 분류한 표.
전수가 끝나면 `reports/screen_loop.json` 을 **날짜 붙여 커밋한다**(L1 과 같은 이유).

---

## 8. L6 · 앵커 격차 축 분해 — 09-07 T3 이 그대로 남았다 (30분)

**왜 PC 인가.** `data/bronze`·`data/silver` 가 클라우드에 없다.
**미완인 근거**: `docs/finding-anchor-gap-2026-09.md` 의 절 목록이 §5 에서 끝난다 — §6 이 없다.
어제 런북 T3 이 요구한 산출물이 하나도 안 만들어졌다.

```powershell
set PYTHONIOENCODING=utf-8
python -m data.pipelines.calibrate_vacancy yeonnam sinchon hongdae
python -m data.analyze_anchor_population yeonnam sinchon hongdae
type data\gold\yeonnam\calibration.json | findstr rone_aligned
```

⚠ 인자 없이 돌리면 `ACTIVE_HUBS` 66거점을 전부 돈다. slug 를 명시한다.

### 프롬프트

```
docs/finding-anchor-gap-2026-09.md §5 가 "데스크톱에서만 된다"고 남긴 자리를 채운다.
방금 calibrate_vacancy 와 analyze_anchor_population 을 3거점으로 돌렸다.

풀 것 하나: rone_aligned.mid 가 서빙 대표값보다 높은 이유가 세 축 중 어느 것인가.
  축A 모집단 확장(3층↑ 또는 330㎡ 초과 · 상가 주용도)
  축B 면적가중(호실 기준 → 면적 기준)
  축C 층 단위 분자(active_floors_lo/hi)
지금 §3-1 은 층수만 쓴 근사라 330㎡ 조건이 빠져 있고, 그래서 어느 축이 얼마를 밀었는지
못 가른다. 축별로 끄고 돌려 3거점에서 기여도를 %p 로 갈라라.

기준값(문서에 이미 적힌 것 — 재현되는지 먼저 대조):
  서빙 대표값      연남 12.53 · 신촌 17.19 · 홍대 14.97 %
  rone_aligned.mid 연남 20.8 · 신촌 19.8 · 홍대 20.1 %
  근사 절단값      연남 14.92 · 신촌 20.35 · 홍대 15.96 %
  ※ 신촌만 mid 가 절단값보다 낮다 — 축이 서로 상쇄되는 자리다. 먼저 봐라.

[산출물] reports/anchor_gap_axes_2026-09-08.json + 문서에 §6 추가.
[금지] gold 산출물 변경(이건 진단이지 재빌드가 아니다), 값이 다를 때 문서를 먼저 고치는 것.
```

**부가 가치**: 이 결과가 폰 트랙 **B16(M2-1 앵커 라벨 정렬)** 의 입력이다.
지금 프로덕션에는 같은 거점의 공실률이 12.5% 와 20.8% 로 **두 개** 떠 있다.

---

## 9. L7 · 마무리 — 검증·머지·배포 (20분)

```powershell
# (1) 오늘 머지된 vitest 를 PC 에서 한 번은 돌린다 (CI 와 node 버전이 갈릴 자리)
cd apps\frontend
npm ci
npm run test
npm run build

# (2) 게이트 재확인
cd ..\..
python scripts/pppp_status.py | findstr /v "└"

# (3) 커밋 — 명시 경로만 stage 한다
git add reports/screen_loop_2026-09-07.json reports/screen_loop_2026-09-08_postfix.json docs/
git commit -m "test(page): 09-07 리포트 판독 + C2 수정 후 렌더 실측"

# (4) ⚠ main 푸시는 프로덕션 배포를 태운다 (GitHub Actions → Cloud Run)
git push -u origin main
python scripts/watch_deploy_verify.py
```

### 프롬프트 (마지막에 한 번)

```
/verify

오늘 main 에 들어간 것을 화면에서 확인한다. 근거 없이 넘어가지 마라 —
아래 다섯은 전부 오늘 머지됐고 **아무도 실제 지도로 안 봤다**.

1. C2 (9683dd5) MapShell·PageDashboard 의 리스너 정리 — 건물 클릭이 여전히 되는가.
   리스너를 떼는 수정이라 **클릭이 죽는 것**이 이 수정의 전형적인 회귀다. 거점을 3회 바꾼 뒤
   마지막 거점에서 폴리곤·핀 클릭 → 상세 패널이 뜨는지 본다(패널 확인은 `.b-detail .b-name` 로 좁혀라).
2. 줌 14(Marker 경로)와 줌 17(폴리곤) 양쪽에서 1을 반복한다 — 두 경로가 다른 코드다.
3. PageDashboard(#board)에서도 같은 확인.
4. 층 스택 + 거리뷰가 그대로 뜨는가(촬영일·'공실 근거 아님' 문구 동반).
5. 콘솔 pageerror 0.

결과는 reports/full_verify.json 에 남기고, 실패는 고치지 말고 먼저 목록으로 보고해줘.
```

---

## 10. 이번 밤에 **하지 않는 것**

| 안 하는 것 | 이유 |
|---|---|
| 건축HUB 수집 · GNN/LSTM 재학습 | 66거점 Tier1 이 이미 완주했고 관련 게이트가 전부 100% 다. 오늘의 병목은 데이터가 아니라 **화면**이다. 고양·파주 20거점은 서빙 보류라 게이트가 세지 않는다 |
| B9 계정 화면 · B10 글자 정리 · B11 4P 플로우 | 폰/클라우드 트랙이다([prompts-mobile-2026-09-08.md](prompts-mobile-2026-09-08.md) §1). PC 시간을 여기 쓰면 L1~L3 이 또 밀린다 |
| `scripts/screen_loop.py` 명세 수정 | C4 §4 가 "두 건 모두 고칠 것이 없다"고 판정했다. 고칠 근거가 새로 나오면 별도 작업으로 낸다 |
| 09-07 런북 T4(PageDashboard 글자 정리) | 폰 트랙 B10 으로 이관됐다(대상이 커졌다) |

---

## 부록. 이 저장소가 반복해서 밟는 함정

| 함정 | 증상 | 처방 |
|---|---|---|
| 리포트를 읽기 전에 재실행 | 유일한 사본이 덮인다 | **L1 을 먼저.** `--out` 으로 새 경로에 낸다 |
| `PYTHONIOENCODING` 누락 | 리다이렉트 순간 UnicodeEncodeError | 터미널마다 `set PYTHONIOENCODING=utf-8` |
| 하위 폴더에서 스크립트 실행 | `No such file or directory` | 항상 저장소 루트에서 |
| `calibrate_vacancy` 인자 없이 실행 | 66거점을 전부 돈다 | slug 명시 |
| 선언 게이트 인용 | 게이트는 100%인데 화면이 틀림 | 이 저장소의 주된 실패 양식이다. 근거 경로를 열어라 |
| 스텁 위 계측을 실측으로 읽기 | "고쳤다"가 ms 없이 머지된다 | C2 가 정확히 그 상태다 — L2 가 그것을 닫는다 |

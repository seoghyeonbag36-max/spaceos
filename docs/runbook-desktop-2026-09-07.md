# 데스크톱 런북 — 2026-09-07 미완 작업 실행

> 클라우드 세션(Claude Code on the web)에서 **구조적으로 못 한 것**만 모았다.
> 각 항목은 ① 왜 PC 여야 하는가 ② 붙여넣을 명령 ③ 붙여넣을 프롬프트 ④ 통과 조건 순이다.
> 근거: `docs/plan-design-upgrade-2026-09.md` §7 · `docs/plan-mvp-3hubs-2026-09.md` §3 ·
> `docs/finding-anchor-gap-2026-09.md` §5 · `design/planning/01-scenario-m1-yeonnam.md` §4

---

## 0. 왜 이것들이 PC 몫인가 (2026-09-07 클라우드 세션 실측)

| 막힌 것 | 확인 명령 | 클라우드 결과 |
|---|---|---|
| 브라우저 검증 | `python -c "import playwright"` | `ModuleNotFoundError` — 백엔드 venv 에 없다 |
| 네이버 지도 렌더 | `ls apps/frontend/.env` | 없다(`.env.example` 만 추적). 키 `VITE_NAVER_MAPS_KEY_ID` 가 PC 에만 있다 |
| 앵커 재계산 | `ls data/bronze data/silver` | bronze 0건 · silver 2건 |
| 3거점 공실 원본 | `git ls-files data/gold \| grep building_vacancy` | `garosugil` 1건뿐 |

반대로 **클라우드에서 이미 통과 확인한 것**(PC 에서 다시 안 해도 된다):
`pytest` 323 passed·6 skipped · `npm run build` OK(245.36KB) · `screen_loop.py --self-check` 실패 0건.

---

## 1. 준비 (5분)

PowerShell 3개. **터미널 3의 `PYTHONIOENCODING` 은 생략하지 말 것** — cp949 에 `—`(em dash)가
없어 로그 리다이렉트 순간 UnicodeEncodeError 로 죽는다(2026-08-19 실측).

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
```

준비 확인 — 셋 다 값이 나와야 다음으로 간다.

```powershell
curl http://localhost:8000/health
curl http://localhost:5173
type apps\frontend\.env | findstr VITE_NAVER_MAPS_KEY_ID
```

---

## 2. T1 · `/verify` — 제일 먼저 (20분)

**왜 먼저인가.** 마지막 `/verify` 가 **09-06 10:11** 인데 그 뒤 프론트가 8커밋 바뀌었다
(Pretendard 배치 · spacing 토큰 · 4트랙 색 · Card/Button 배선 · Verdict 신설).
**오늘 바꾼 화면을 아무도 눈으로 안 봤다.** 여기서 깨진 게 나오면 T2~T4 가 전부 헛일이다.

### 프롬프트 (Claude Code 에 붙여넣기)

```
/verify

추가로 이 네 가지를 픽셀에서 확인해줘. 09-06 10:11 이후 프론트 8커밋이
검증 없이 쌓였고, 아래는 전부 그 커밋들의 통과 조건인데 미확인 상태다.

1. Pretendard 가 실제로 먹었나
   - getComputedStyle(document.body).fontFamily 에 Pretendard 가 있는지
   - document.fonts.check('15px Pretendard') 가 true 인지
   - 전례: 이 저장소는 --font-sans 를 선언해두고 public/fonts 가 없어
     전 화면이 조용히 system-ui 로 떨어진 적이 있다. 선언이 아니라 실렌더를 봐라.

2. 4트랙 색이 같은 축인가 (D5-3 통과 조건)
   - 레일 아이콘 · 화면 헤더 · 지도 범례 세 자리가 --track-{platform,page,posting,program}
     같은 토큰에서 오는지. 하드코딩 hex 가 섞여 있으면 실패로 적어라.
   - AA 대비는 이미 계산했다(흰 배경 5.23~8.68, 4개 전부 통과). 다시 계산하지 말고
     "실제로 그 색이 쓰이는가"만 봐라.

3. Verdict 가 3초 안에 결론 한 줄을 띄우나 (D5-6)
   - Platform · Program 두 탭. 진입 후 3초 안에 결론 문장이 떠야 한다.
   - "상권 정체성을 불러오는 중이다" 가 3초 뒤에도 남아 있으면 실패.
   - 첫 화면에 vac_proxy · MAE 같은 모델 지표가 보이면 실패 (Fold 안에 있어야 한다).

4. red-dot 줌 전환 (D5-5 통과 조건 — 코드는 있는데 픽셀 미확인)
   - MapShell.tsx:52 PIN_MAX_ZOOM = 15.
   - 연남동에서 줌 15 → 핀(Marker)만, 줌 17 → 폴리곤. 콘솔 에러 0.

거점은 연남동으로 본다. 결과는 reports/full_verify.json 에 남기고,
실패한 항목은 고치지 말고 먼저 목록으로 보고해줘 — 고칠지는 내가 정한다.
```

**통과 조건**: 정적 4종 pass + 위 4항목 전부 확인. 실패가 나오면 **T2 로 넘어가지 말고 T1 에서 끝낸다.**

---

## 3. T2 · `screen_loop` 첫 실전 투입 (30분)

**왜 PC 인가.** 브라우저 + 네이버 지도 키가 필요하다.
**오늘 만들었는데 한 번도 안 돌렸다** — `reports/` 에 결과 파일이 없다(자기검사만 통과).

### 명령 (그대로 붙여넣기)

```powershell
set PYTHONIOENCODING=utf-8

# (1) 검사기가 진짜 화면을 보는지 먼저 — 없는 셀렉터를 넣어 실패가 나와야 정상
python -u scripts/screen_loop.py --hubs yeonnam --canary

# (2) 3거점 · 4탭 = 12조합
python -u scripts/screen_loop.py --hubs yeonnam,sinchon,hongdae

# (3) 실패만 다시
python -u scripts/screen_loop.py --retry-failed

# (4) (2)가 깨끗하면 66거점 — 264조합, 자리 비울 때 걸어둔다
if not exist reports\logs mkdir reports\logs
python -u scripts/screen_loop.py > reports\logs\screen_loop_2026-09-07.log 2>&1
```

산출물: `reports/screen_loop.json` · 스크린샷 `reports/screens/`.
기본 예산은 3000ms(KPI: 지도 로딩 3초). 창을 보고 싶으면 `--headed`.

### 프롬프트 (실패가 났을 때만)

```
scripts/screen_loop.py 를 3거점(yeonnam,sinchon,hongdae) × 4탭으로 돌렸고
reports/screen_loop.json 에 실패가 남았다. 아래 순서로 봐줘.

1. 실패를 S1(콘솔·5xx) / S2(캔버스·SDK) / S3(마커·결론문장·거점목록) / S4(3초 초과)
   네 단계로 분류해서 표로 보여줘.
2. 각 실패가 (a) 화면 버그인지 (b) 검사기 셀렉터 문제인지 판정해줘.
   판정 근거는 reports/screens/ 의 스크린샷과 실제 소스다 — 추측하지 말 것.
   전례: `.b-name` 이 목록행과 상세패널 양쪽에 있어 querySelector 가 목록 첫 행을
   집은 적이 있다(프로브는 `.b-detail .b-name` 로 좁혀야 했다). 같은 양식을 의심해라.
3. (b) 면 screen_loop.py 의 셀렉터를 고치고, (a) 면 고치지 말고 목록만 줘.
4. 4xx 는 실패로 세지 않는다 — 이 저장소에서 404 는 "아직 수집 안 함"인 자리가 있다
   (/ai/recommend-industry 404 = 400m 안에 노드 없음). 5xx 만 고장이다.

금지: @playwright/test 를 새로 설치하지 말 것. Python playwright 가 이미 있고
두 벌을 두면 검증 기준이 갈린다.
```

**통과 조건**: 3거점 12조합 실패 0 → 그 뒤 66거점 264조합. `reports/screen_loop.json` 커밋.

---

## 4. T3 · 앵커 격차 축별 분해 (30분)

**왜 PC 인가.** `data/bronze`·`data/silver` 가 클라우드에 없다.
`finding-anchor-gap-2026-09.md` §5 가 "데스크톱에서 막혔다"고 직접 지목한 자리다.

### 명령

```powershell
set PYTHONIOENCODING=utf-8

# (1) 3거점 앵커 재계산 — 인자 없이 돌리면 ACTIVE_HUBS 66거점 전부다. 3거점만 준다.
python -m data.pipelines.calibrate_vacancy yeonnam sinchon hongdae

# (2) 모집단 진단 — 산출물을 바꾸지 않는다(gold 무수정 · API 콜 0)
python -m data.analyze_anchor_population yeonnam sinchon hongdae

# (3) 결과 확인
type data\gold\yeonnam\calibration.json | findstr rone_aligned
```

### 프롬프트

```
docs/finding-anchor-gap-2026-09.md §5 가 데스크톱에서만 된다고 남긴 것을 지금 채운다.
방금 아래를 돌렸다:
  python -m data.pipelines.calibrate_vacancy yeonnam sinchon hongdae
  python -m data.analyze_anchor_population yeonnam sinchon hongdae

풀 것 하나: rone_aligned.mid 가 서빙 대표값보다 높은 이유가 세 축 중 어느 것인가.
  축A 모집단 확장(3층↑ 또는 330㎡ 초과 · 상가 주용도)
  축B 면적가중 (호실 기준 → 면적 기준)
  축C 층 단위 분자 (active_floors_lo/hi)

지금 문서 §3-1 은 층수만 쓴 근사라 330㎡ 조건이 빠져 있고, 그래서 어느 축이 얼마를
밀었는지 못 가른다. calibrate_vacancy 를 축별로 끄고 돌려 3거점에서 기여도를 갈라줘.

기준값(문서에 이미 적힌 것 — 재현되는지 먼저 대조):
  서빙 대표값  연남 12.53 · 신촌 17.19 · 홍대 14.97 %
  rone_aligned.mid  연남 20.8 · 신촌 19.8 · 홍대 20.1 %
  근사 절단값       연남 14.92 · 신촌 20.35 · 홍대 15.96 %
  ※ 신촌만 mid 가 절단값보다 낮다 — 여기가 축이 서로 상쇄되는 자리다. 먼저 봐라.

산출: reports/anchor_gap_axes_2026-09-07.json (기계가 읽을 값) +
docs/finding-anchor-gap-2026-09.md 에 §6 으로 추가.

금지: gold 산출물을 바꾸지 말 것. 이건 진단이지 재빌드가 아니다.
값이 문서와 다르게 나오면 문서를 고치지 말고 차이부터 보고해라.
```

**통과 조건**: 축 A/B/C 기여도가 3거점에서 %p 로 갈린다 + 신촌 역전이 설명된다.

---

## 5. T4 · PageDashboard 글자 정리 (시간 남으면 · 30분+)

PC 가 아니어도 되지만 **오늘 미완 중 가장 큰 덩어리**다. D5-6 통과 조건이 여기서 갈린다.

현재 텍스트 노드 실측(`node apps/frontend/scripts/count-text-nodes.mjs`):

| 화면 | 펼침 | 접힘 | 상태 |
|---|---|---|---|
| **PageDashboard.tsx** | **346** | **0** | 미착수 · 최대 |
| PlatformConsole.tsx | 123 | 326 | −64.3% ✅ |
| ProgramStudio.tsx | 99 | 54 | −31.3% ❌ |
| PostingConsole.tsx | 96 | 0 | 미착수 |
| MapShell.tsx | 86 | 0 | 미착수 |
| HubExplorer.tsx | 73 | 0 | 미착수 |

### 프롬프트

```
D5-6(화면당 결론 1줄 + 근거 3줄)을 PageDashboard.tsx 에 적용한다.
지금 펼침 텍스트 노드 346 · 접힘 0 으로, 손 안 댄 화면 중 가장 크다.

이미 있는 도구를 쓴다 — 새로 만들지 말 것:
  import Verdict, { Fold } from "@/components/Verdict";   ← Verdict 는 default export
  <Verdict>  eyebrow / 질문 / 결론 1줄 / 근거 3줄 / 출처 줄. 근거 넷째부터 자동으로 접힌다
  <Fold>     <details> 래퍼. 요약줄이 안에 무엇이 몇 개인지 말한다
  선례: PlatformConsole.tsx · ProgramStudio.tsx (커밋 139d8e0)

이 화면이 답하는 질문은 "어디가 비었나 — 건물·층" 이다.
결론 1줄 = 거점 대표 공실률 + 실측 배지 + 건물 수.
근거 3줄 = 어느 건물이 비었나 / 몇 층이 비었나 / 얼마나 확실한가.

지키는 것:
- 지운 것 0. 화면이 읽던 응답 필드를 전부 그대로 읽어야 한다. 접는 것과 지우는 것은 다르다.
- 출처 표기는 접지 않는다. 아래가 전부 접혀도 Verdict 출처 줄에 남아야 한다.
- 수치는 계산한 정밀도 그대로. 자리 아끼려고 반올림하지 말 것.
- confirmed(233) 와 probable(63) 을 같은 것으로 그리지 말 것 — 층 미상 점포
  배정 결과가 달라 의미가 다르다.

통과 조건:
- 펼침 346 → 173 이하 (−50%), 전체는 늘어도 된다(= 결론·근거를 얹고 지운 게 없다는 뜻)
- 측정: node apps/frontend/scripts/count-text-nodes.mjs src/pages/PageDashboard.tsx
- npm run build 통과
- 작업 후 /verify 로 이 화면을 실제로 열어 확인
```

시간이 더 남으면 같은 프롬프트로 PostingConsole(96) → MapShell(86) → HubExplorer(73).

---

## 6. 마무리 (10분)

```powershell
python scripts/pppp_status.py          # 게이트 재확인
git status
git add -A
git commit -m "test(verify): 09-07 화면 검증 실행 결과를 남긴다"
git push -u origin main                # main 푸시 → Cloud Run 자동 배포
```

⚠ `main` 푸시는 **프로덕션 배포를 태운다**(GitHub Actions → Cloud Run). 검증 결과 커밋만
올릴 때도 마찬가지다. T1 이 실패로 끝났으면 푸시 전에 `docs/deploy-cloud-run.md` 를 본다.

---

## 부록. 이 세션이 실제로 밟은 함정

| 함정 | 증상 | 처방 |
|---|---|---|
| `PYTHONIOENCODING` 누락 | 로그 리다이렉트 순간 UnicodeEncodeError | `set PYTHONIOENCODING=utf-8` 을 터미널마다 |
| `scripts/screen_loop.py` 를 하위 폴더에서 실행 | `No such file or directory` | 항상 저장소 루트에서 |
| `calibrate_vacancy` 인자 없이 실행 | `ACTIVE_HUBS` 66거점 전부 돈다 | slug 를 명시 |
| 선언 게이트 인용 | 게이트는 100%인데 화면이 틀림 | 이 저장소의 주된 실패 양식이다. 근거 경로를 열어라 |

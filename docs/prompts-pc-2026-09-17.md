# PC 작업 프롬프트 — 2026-09-17

> **클라우드 세션(claude.ai/code)에서 구조적으로 못 하는 것만** 모았다. 문서·화면·테스트는
> 클라우드에서 계속 돌아가니 여기 없다. 여기 있는 것은 **원천 데이터·GPU/CPU 학습·지도 키·픽셀**
> 넷 중 하나가 필요한 일이다.
>
> 상태는 이 문서가 아니라 스크립트에서 읽는다 — 이 문서의 숫자도 아래 두 줄이 이긴다.
> ```bash
> python scripts/pppp_status.py | grep -v '└'   # 진행률·게이트
> python scripts/kpi_baseline.py                # 실력 판정 (미달이면 종료코드 1)
> ```
> 형제 문서: [runbook-desktop-2026-09-07.md](runbook-desktop-2026-09-07.md)(09-07 판) ·
> [../PlaceOS_Mobile_Dispatch_Prompts.md](../PlaceOS_Mobile_Dispatch_Prompts.md)(클라우드/모바일 쪽)

---

## 0. 오늘 PC 가 필요한 이유 (2026-09-17 클라우드 세션 실측)

| 막힌 것 | 확인 명령 | 클라우드 결과 |
|---|---|---|
| 점포 소분류 어휘 실측 | `ls data/bronze` | **0건** — Bronze 는 `.gitignore` 로 안 실린다 |
| 수집으로 우회 | `.env` 의 `DATA_GO_KR_SERVICE_KEY` | 없음 · 네트워크 정책이 data.go.kr 을 막는다(CONNECT 403) |
| 네이버 지도 픽셀 | `ls apps/frontend/.env` | 없음(`.env.example` 만 추적) — `VITE_NAVER_MAPS_KEY_ID` 는 PC 에만 |
| 앵커·Silver 재계산 | `ls data/silver` | 3건(집계구 셋)뿐 |

반대로 **Gold 566파일은 git 에 실려 있어** 테스트·분석·서빙 코드는 클라우드에서 그대로 돈다.
PC 에서 그것들을 다시 돌리지 말 것 — 시간만 쓴다.

---

## 1. 첫 입력 — 이것 하나만 붙여넣고 시작한다

PowerShell 에서 `cd <저장소>` → `claude` 실행 후:

```
PlaceOS 저장소다. 나는 지금 PC(로컬)에 있고, 여기서는 클라우드 세션이 구조적으로
못 하는 일만 한다 — 원천 데이터(Bronze/Silver) · 모델 학습 · 네이버 지도 키 · 픽셀 검증.

## 1) 상태를 산출물에서 읽어라 (문서·기억으로 판단하지 말 것)
  git status --short ; git log --oneline -5
  python scripts/pppp_status.py | grep -v "└"
  python scripts/kpi_baseline.py          # 종료코드 1 이면 미달 축이 있다
  python scripts/chain_status.py --all

## 2) 이 머신에만 있는 것을 확인해서 표로 보고해라
  ls data\bronze  ·  ls data\silver              (원천 데이터 유무·건수)
  type apps\frontend\.env | findstr VITE_NAVER_MAPS_KEY_ID   (지도 키 — 값은 출력하지 말 것)
  python -c "import torch, playwright; print('ok')"          (학습·픽셀 가능 여부)
  .env 에 DATA_GO_KR_SERVICE_KEY 가 있는지 여부만 (값 출력 금지)

## 3) 그다음 오늘 할 일을 PC 에서만 가능한 것 3개로 좁혀 제안해라
docs/prompts-pc-2026-09-17.md 의 P1~P4 가 후보다. 각각 ① 왜 지금인가 ② 예상 소요
③ 통과 조건(숫자)을 붙여라. 내가 하나 고르면 그때 시작한다.

**승인 없이 학습·수집을 먼저 돌리지 말 것.** 클라우드에서 이미 통과한 것
(pytest · npm run build)을 PC 에서 되풀이하지도 말 것.
응답은 한국어로.
```

> 왜 "먼저 읽고 제안"인가: 이 저장소는 낡은 기준선에 대고 판정해 **기각이 뒤집힌 전례**가 있다
> (`docs/feature-platform.md` §0-Q). 첫 입력이 곧바로 실행이면 그 사고가 반복된다.

---

## 2. P1 · LSTM 재학습 — 새 학습 규약 (지금 유일한 ❌ 축)

**왜 지금인가.** `kpi_baseline` 이 오늘도 종료코드 1이다: 방향정확도 모델 **70.8%**(46/65) vs
무정보 상수('항상 하락') **78.5%** → **−7.7%p**. 진단은 끝나 있다 — 모델이 아니라 **표본 쏠림**이고
(균형정확도 65.8% · MCC +0.278), 홀드아웃 65건으로는 원리적으로 못 가른다(SE 5.7%p).
분할 코드는 롤링 오리진으로 이미 바뀌었는데 **산출물이 옛 규약**이라 재학습이 남았다.
→ [finding-lstm-direction-diagnosis-2026-09-16.md](finding-lstm-direction-diagnosis-2026-09-16.md)

### 붙여넣을 프롬프트

```
PlaceOS LSTM 을 새 학습 규약으로 재학습해줘. docs/finding-lstm-direction-diagnosis-2026-09-16.md
"무엇을 하면 되나"가 이 작업의 명세다. 먼저 읽고, 아래를 그대로 지킬 것.

## 확정된 사실 (다시 규명하지 말 것)
- 방향 축 미달(−7.7%p)의 원인은 표본 쏠림(51:14)이다. 모델 무용론이 아니다.
- 홀드아웃 65건 · SE 5.7%p. 거점 확대로는 못 푼다 — 거점당 test 원점을 늘려서 푼다.
- 균형정확도·MCC 는 **관측 항목**이다. 결과를 보고 판정 지표로 승격하지 말 것(metric shopping).

## 할 일
1. 두 팔을 **같은 런에서** 돌린다. 대조군을 같이 돌리는 것이 이 저장소의 규칙이다.
     python -m ml.training.train_lstm                                 # 롤링 3/2 (기본)
     python -m ml.training.train_lstm --test-quarters 1 --val-quarters 1   # 대조군(옛 규약)
2. 비교표: test 방향 실력(vs 상수) · MAE 기술점수(vs 지속성) · 구간 폭 · train 윈도우 수.
   train 축소(거점당 13→9)의 대가가 분해능 이득보다 크면 **대조군으로 되돌리고 그 이유를 적어라.**
3. 결정 임계값은 **val 에서** 보정한다. test 에서 고르면 09-16 에 막은 선택 누수와 같은 종류다.
4. 결과를 docs/finding-lstm-retrain-<오늘날짜>.md 에 남겨라 — 표 · 되돌림 여부 · 다음 레버.

## 통과 조건
- `python scripts/kpi_baseline.py` 가 두 팔 모두에 대해 돌고, 채택본의 출력이 문서 표와 일치한다.
- 저장소 루트에서 `pytest -q data/tests/test_lstm_leakage.py data/tests/test_kpi_baseline.py` 통과
  (2026-09-17 클라우드 실측: 31 passed · 5 skipped). `cd apps/backend` 로 들어가면 경로가 어긋난다.
- 채택본 산출물만 커밋하고, 기각본은 수치만 문서에 남긴다.

로그 리다이렉트 시 PYTHONIOENCODING=utf-8 필수(cp949 에 em dash 없음). 응답은 한국어로.
```

**통과 조건 요약**: `kpi_baseline` 종료코드가 0이 되거나, **되지 않은 이유가 숫자로 적힌다.**
(0이 되는 것 자체는 목표가 아니다 — 못 가르는 차이를 억지로 넘기면 그게 누수다.)

---

## 3. P2 · 점포 소분류 어휘 실측 — Bronze 가 있어야만 끝난다

**왜 지금인가.** `편의점` · `약국` · `커피전문점` 세 라벨이 **미검증 문자열 추측**으로 돌고 있다.
이 상태로 P3(GNN 재학습)을 하면 **라벨이 틀린 모델**이 나온다. API 콜은 0 — 이미 수집된
`stores_raw.json` 만 읽는다.

프롬프트 원문은 [prompt-store-taxonomy-scls-2026-09-15.md](prompt-store-taxonomy-scls-2026-09-15.md)
**§붙여 넣을 프롬프트** 를 그대로 쓴다. 여기서는 **PC 에서만 추가로 지킬 것** 두 줄만 덧붙인다:

```
(위 문서의 프롬프트를 붙여넣은 뒤 이어서)

추가 조건 — 이 머신에만 Bronze 가 있으니 다음 사람이 같은 벽에 부딪히지 않게 할 것:
1. `--audit` 산출물 data/gold/store_taxonomy_vocab.json (분류 삼단 + 등장 횟수, 점포
   레코드 없음)을 **반드시 같이 커밋한다.** 이 사이드카가 있어야 Bronze 없는 머신에서도
   `--vocab` 으로 소분류까지 감사된다.
2. Bronze 원본·점포 레코드는 커밋하지 않는다(.gitignore 확인). 커밋 전 git status 로
   data/bronze 가 안 섞였는지 눈으로 볼 것.
```

---

## 4. P3 · GNN 재학습 — P2 가 끝난 뒤에만

**왜 지금인가.** 서빙 배치 `gold/platform_industry_recommend.json` 은 아직 **옛 카카오 노드**로
만들어진 것이다. 노드 소스는 상가정보로 이미 갈아끼웠다.

프롬프트 원문: [prompt-gnn-retrain-scls-2026-09-15.md](prompt-gnn-retrain-scls-2026-09-15.md).
**P2 미완이면 열지 말 것** — 그 문서가 먼저 못박아 둔 선행 조건이다.

PC 에서만 덧붙일 것:

```
추가 조건:
- 장시간 작업이다. 절전 억제부터 걸어라: powershell -ExecutionPolicy Bypass -File scripts\keep_awake.ps1
- 학습은 스레드 1개 · UTF-8:
    set OMP_NUM_THREADS=1 & set PYTHONIOENCODING=utf-8
    python -u -m ml.training.train_gnn --epochs 600 --patience 80
- 이번 재학습은 **회귀 측정이 아니라 새 기준선 수립**이다(옛 그래프 소스가 설계상 사라졌다).
  문서에 그렇게 적어라 — 안 적으면 다음 사람이 또 낡은 기준선에 대고 판정한다.
- 산출물의 test_nodes 가 채워지는지 확인할 것. kpi_baseline 의 [검정력] 줄이 그걸 기다리고 있다.
```

---

## 5. P4 · `/verify` — 픽셀까지 (PC 에서만 가능한 마지막 구간)

정적 3종(pytest · npm run build · torch)은 클라우드/CI 가 매 푸시마다 증명한다. **PC 몫은 픽셀이다** —
지도 키가 여기에만 있다.

```
/verify

정적 3종은 CI 가 이미 통과시켰으니 빠르게만 확인하고, 시간은 **픽셀**에 써라.
백엔드(:8000) + Vite(:5173) 를 띄우고 Playwright 로 다음을 실제 렌더에서 확인:

1. 네이버 지도가 실제로 그려지는가 — 타일/파노라마 요청이 200 인가, 콘솔 에러 0인가.
   (VITE_NAVER_MAPS_KEY_ID 가 없는 환경에서는 조용히 빈 div 가 된 전례가 있다. 선언이 아니라 실렌더를 봐라.)
2. 히트맵 색이 디자인 토큰에서 오는가 — 하드코딩 hex 가 섞여 있으면 실패로 적어라.
3. 거리뷰 파노라마가 건물 클릭에 반응하는가.
4. 지도 로딩 시간을 client:map_ready 로 실제 전송하는가 — POST /api/v1/metrics/client 가 찍히는지.
   (KPI② 는 "배선 완료 · 표본 없음"이다. 표본을 만드는 것이 이 확인의 부수 효과다.)

실패는 스크린샷과 함께 reports/ 에 남기고, 고칠 수 있는 것은 고친 뒤 재확인까지 갈 것.
```

---

## 6. 마감 — 자리 뜨기 전에

```
오늘 PC 에서 한 것을 마감해줘.
1. git status --short 로 안 커밋된 것이 있는지 본다. Bronze/Silver/대용량 산출물이
   섞여 있으면 커밋하지 말고 왜 제외했는지 알려줘.
2. 변경을 작은 단위로 나눠 커밋(한국어 메시지, 무엇을 왜 바꿨는지).
3. git push -u origin <브랜치> — 실패하면 네트워크 재시도만 하고 다른 브랜치로 바꾸지 말 것.
4. 마지막으로 python scripts/pppp_status.py | grep -v "└" 와 python scripts/kpi_baseline.py
   를 다시 돌려, **오늘 아침 값과 달라진 줄만** 보여줘.
5. 클라우드에서 이어서 할 수 있는 일 2개를 남겨줘(원천 데이터가 필요 없는 것만).
```

> **클라우드 세션의 절대 조건**: 커밋·푸시 안 된 작업은 폰·웹에서 안 보인다. 4번까지 끝내고 자리를 뜬다.

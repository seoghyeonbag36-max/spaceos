# finding — 15거점 전유부는 **클라우드(모바일) 세션에서 시작할 수 없다**. 막는 것이 넷이다

- 날짜: 2026-09-22
- 브랜치: `claude/15-locations-mobile-work-check-9hazoq`
- 성격: **확인만.** 수집기·설정·거점 등록은 한 줄도 고치지 않았다. 이 문서 하나만 추가한다.
- 방법: 이 세션(클라우드 원격 컨테이너) 안에서 **직접 실측**했다. 문서의 주장
  ([prompts-mobile-hub-quota-2026-09-21.md](prompts-mobile-hub-quota-2026-09-21.md) §0 —
  "클라우드 세션은 `.env` 키와 `data/bronze` 가 없어 시작조차 못 한다")을 그대로 믿지 않고
  넷을 각각 쳐 봤다. **결론은 문서와 같지만, 문서가 모르던 셋째·넷째가 더 있다.**
- 건축HUB 콜: **0회**(쿼터를 태우지 않았다). 도달성 프로브 1콜은 프록시가 앞에서 잘라
  공공데이터포털에 닿지 않았다 — §3 참조.

---

## 0. 한 줄 결론

**불가.** 넷 중 하나만 있어도 못 하는데 넷이 다 있다. 그리고 **넷째(Gold·Bronze 부재)는
키를 넣어도 풀리지 않는다** — 데스크톱에 이미 있는 데이터를 클라우드에서 처음부터 다시 받는
것이 되고, 그건 09-20 에 쓴 하루치 쿼터를 한 번 더 태우는 일이다.

| # | 막는 것 | 실측 | 키를 받으면 풀리나 |
|---|---------|------|------------------|
| 1 | `.env` 없음 → `DATA_GO_KR_SERVICE_KEY` 미설정 | `test -f .env` → MISSING · `env \| grep` 에 관련 키 0개 | 풀린다 |
| 2 | 거점 15개가 이 브랜치에 **등록되어 있지 않다** | `grep SEOUL_BATCH3_HUBS data/config/page_hubs.py` → 0줄 | 브랜치 머지로 풀린다 |
| 3 | **네트워크 egress 허용목록에 `apis.data.go.kr` 가 없다** | `http=403` · `Host not in allowlist` | **환경 설정을 고쳐야 풀린다** |
| 4 | `data/bronze` 가 비었고 15거점 **Gold 가 0개** | bronze 파일 1개(`.gitkeep`) · gold 디렉터리 15/15 없음 | **안 풀린다** — 재수집뿐 |

---

## 1. `.env` 와 키 — 수집기가 첫 줄에서 빠진다

```
$ test -f .env && echo EXISTS || echo MISSING
MISSING
$ env | grep -iE "bld|hub|data_go|service_key|vworld|naver"
(GITHUB_TOKEN·GIT_CONFIG_* 뿐. 수집 키는 0개)
```

`building_vacancy.main()` 은 키가 없으면 아무것도 하지 않고 `return` 한다
([building_vacancy.py:667-671](../data/collectors/building_vacancy.py#L667)):

```
key = os.getenv("DATA_GO_KR_SERVICE_KEY")
if not key or requests is None:
    print("[bldg-vac] DATA_GO_KR_SERVICE_KEY 미설정(또는 requests 없음) — 건너뜀")
    return
```

⚠ 이 경로는 **exit 0 으로 끝난다.** 부르는 쪽(`run_hub_chain_batch`·loop-engine)이 보기에
"돌았는데 할 게 없었다"와 구분되지 않는다. 클라우드에서 무심코 돌리면 실패가 아니라
**조용한 무동작**으로 보인다는 뜻이다 — 이 문서가 남아야 하는 이유 중 하나다.

## 2. 거점 등록이 이 브랜치에 없다

15거점(`SEOUL_BATCH3_HUBS` 5 + `SEOUL_BATCH4_HUBS` 10)은 `main` 에도 이 브랜치에도 없다.
`origin/feat/seoul-hubs-batch3-4-20260921`(커밋 `9a02fa2`)에만 있다. 09-21 커밋 메시지대로
**Gold 없이 그것만 머지하면 데이터 pytest 47건이 깨진다.**

그래서 §1 스니펫(오늘몫 계산)은 이 세션에서 `ImportError` 로 죽는다. 대상 목록조차 못 만든다.

대상 15거점: `bangbang` `gildong` `nowon` `gurodigital` `ydp-gucheong` ·
`seochoyeok` `poi` `dogok` `yangjae` `jamsil-tour` `daerim` `guui` `maebong`
`gurojeonhwa` `bonseobu`

## 3. 프록시가 공공데이터포털을 막는다 — **문서가 모르던 것**

09-21 프롬프트 §0 은 막는 이유로 `.env` 와 `data/bronze` 둘만 든다. 셋째가 있다.
이 세션의 아웃바운드는 에이전트 프록시를 지나는데, 그 허용목록에 건축HUB 호스트가 없다:

```
$ curl -sS -w "http=%{http_code}\n" \
    "http://apis.data.go.kr/1613000/BldRgstHubService/getBrExposPubuseAreaInfo?serviceKey=PROBE&..."
http=403  time=0.005s
Host not in allowlist: apis.data.go.kr. Add this host to your network egress settings to allow access.
```

0.005초에 끊긴 것이 증거다 — 공공데이터포털이 키를 보고 거절한 게 아니라 **콜이 나가지도
못했다.** 키를 붙여도 이 줄은 그대로 403 이다. 풀려면 저장소가 아니라 **환경의 네트워크
egress 설정**을 고쳐야 한다(`apis.data.go.kr` 추가). 같은 이유로 `vworld.kr` ·
`openapi.seoul.go.kr` 도 미리 확인해야 한다 — 15거점 중 둘(`guui` · `poi`)은 점포부터
받아야 하는데 그쪽은 V-World 폴리곤이 먼저다.

## 4. Bronze·Gold 가 없다 — **키로도 안 풀리는 것**

```
$ find data/bronze -type f | wc -l
1                      # .gitkeep 뿐
$ 15거점 data/gold/<slug> 존재 여부
15/15 없음
```

`data/bronze/*` · `data/silver/*` · `data/gold/*/*` 는 `.gitignore` 에 있다
([.gitignore:27-29](../.gitignore#L27) · [:114](../.gitignore#L114)). 클론에 딸려 오는 Gold 는
화이트리스트 몇 종(`page_building_master.geojson` · `coverage.json` 등) 뿐이고, 15거점은
아직 그 산출물 자체가 없다. **09-20 에 받은 대장·점포는 전부 데스크톱 로컬에만 있다.**

여기서 오는 결과가 둘이다.

1. **오늘몫을 셀 수 없다.** 09-21 프롬프트 §1 은 `load_latest(slug,'stores_raw.json')` 으로
   후보 동수를 세는데([building_vacancy.py:567](../data/collectors/building_vacancy.py#L567)),
   bronze 가 비었으니 전 거점이 `점포먼저` 로 나온다 — 실제로는 09-20 에 상당수가 받혀 있다.
2. **§6(파이프라인·앵커)도 못 돈다.** 건축HUB 콜 0인 단계라 키가 필요 없지만, 입력인
   `building_vacancy.json` 이 없다. 클라우드에서 할 수 있는 "키 없는 잔여 작업"은 **없다.**

그래서 클라우드에 키와 허용목록을 다 줘도, 그건 **데스크톱이 이미 받아 둔 것을 처음부터
다시 받는 일**이다. 건축HUB 쿼터는 하루 단위로 회수되지 않으므로(09-20 실측: 8,103동째
전유부 10,000콜 소진) 같은 데이터에 두 번째 하루치를 태우게 된다.

---

## 5. 그래서 어디서 하나

**데스크톱 Dispatch 세션.** 09-21 프롬프트가 이미 그 전제로 쓰였고, 그 판단은 이번 실측으로
확인됐다(막는 이유가 둘이 아니라 넷이라는 점만 보태진다). 프롬프트는 고칠 필요가 없다 —
§0 의 중단 조건(`test -f .env && ls data/bronze | head -1`)이 이 세션을 정확히 걸러 낸다.
실제로 이 세션에서 그 줄은 첫 항에서 이미 거짓이다.

## 6. 남는 질문 (이 문서가 답하지 않은 것)

1. `apis.data.go.kr` 를 egress 에 넣으면 클라우드에서 수집이 서는가 — **안 쳐 봤다.**
   §4 때문에 서더라도 쓸 일이 없어서다. 나중에 클라우드 수집이 필요해지면 그때 §3 부터.
2. 데스크톱의 15거점 현재 단계(`chain_status`) — 여기서는 볼 수 없다. Gold 가 로컬에만 있다.

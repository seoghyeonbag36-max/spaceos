# PlaceOS Frontend (React + TypeScript + Vite)

공실 지도 UI. **네이버 지도**(지도 + 거리뷰 파노라마) + D3/Plotly.

⚠ **Three.js / @react-three/fiber 는 2026-09-05 에 제거됐다.** 3D 트윈이 그리던
절차적 박스는 실측 형상이 아니라 층 상태를 색으로 말하던 것뿐이라, 건물 상세를
**2D 층 스택 + 네이버 거리뷰**(`components/BuildingViewer.tsx`)로 갈았다
(번들 832KB → 4KB). 다시 끌어오지 말 것 — 경위는 `docs/feature-posting.md` §0-V.

## 실행

```bash
cd apps/frontend
npm install
npm run dev
```

- 개발 서버: http://localhost:5173 (`/api` → backend 8000 프록시)
- 네이버 지도 키는 `.env` 의 `VITE_NAVER_MAPS_KEY_ID` 로 주입한다 (`src/lib/naverMap.ts`).
  NCP 콘솔의 Web 서비스 URL 에 `http://localhost:5173` 을 등록해야 지도가 뜬다.
  ⚠ Mapbox 는 쓰지 않는다 — `mapbox-gl` 은 2026-08-25 에 의존성에서 제거됐다
  (경위: `docs/decision-infra-layer-2026-08-25.md`).

## 구조

- `src/components/` — 재사용 컴포넌트 (`BuildingViewer` = 2D 층 스택 + 거리뷰, 차트)
- `src/pages/` — 페이지
- `src/lib/api.ts` — 백엔드 API 클라이언트
- `src/hooks/` — 커스텀 훅

## 화면당 글자 수 — "결론 1줄 + 근거 3줄" (2026-09-07)

한 화면이 결론·근거·원자료를 동시에 펴면 어느 것도 읽히지 않는다. 그래서 규칙을
`src/components/Verdict.tsx` 하나로 고정했다 — 화면 맨 위가 **질문(그 탭이 답하는 것)
→ 결론 한 문장 → 근거 세 줄 → 출처 줄**이고, 나머지는 `Fold`(=`<details>`)로 **접는다**.

지키는 선 셋:

- **접은 것이지 지운 것이 아니다.** 접힌 요약줄이 안에 무엇이 몇 개 있는지 말하고,
  한 번 누르면 종전 화면이 그대로 펴진다.
- **출처는 접지 않는다.** 아래가 전부 접혀도 `Verdict` 의 출처 줄에 카카오 플레이스 ·
  TRDAR · 네이버 데이터랩 · LSTM · GNN · R-ONE 앵커 · ha_guard 가 남는다.
- **수치를 반올림해 자리를 아끼지 않는다.** 글자를 줄이자고 정확도를 깎으면 줄인 의미가 없다.

### 재는 법

```bash
node scripts/count-text-nodes.mjs [--detail] src/pages/PlatformConsole.tsx …
```

`펼침`(열자마자 깔리는 글자) / `접힘`(눌러야 보이는 자리) / `전체`를 낸다. 줄여야 하는
것은 **펼침**이고, **전체가 줄면 데이터를 지운 것**이라 두 숫자를 같이 본다.
정적 계측이라 `{err && …}` 같은 조건부 블록도 펼침으로 세므로 실제 화면 글자 수의 **상한**이다.

| 화면 | 펼침(전) | 펼침(후) | 변화 | 전체(전 → 후) |
|------|---------|---------|------|--------------|
| `PlatformConsole.tsx` | 345 | 123 | **−64.3%** | 352 → 449 |
| `ProgramStudio.tsx`   | 144 |  99 | **−31.3%** | 144 → 153 |

두 화면 모두 **전체가 늘었다** — 결론·근거 줄을 새로 얹었고 지운 것은 없다.
`ProgramStudio` 가 −50% 에 못 미치는 것은 남은 펼침이 대부분 **입력 컨트롤과
상용 온보딩 동의문, 그리고 생성된 채널 카드**여서다. 동의문은 읽지 않고 체크하게
만들면 동의가 아니고, 채널 카드는 이 화면의 답 자체라 둘 다 접지 않았다.

`PageDashboard.tsx` 는 손대지 않았다 — `#board` 해시로 밀려난 화면이고 층별 매물·입점·
마케팅 세 섹션의 이사가 아직 안 끝났다.

/**
 * HubExplorer(「거점」 탭) 회귀 그물.
 *
 * 이 화면은 지도를 소유하지 않는다 — MapHost 가 들고 있는 지도 위에 **실측 범위 경계**만
 * 그린다. 그래서 거점을 바꿀 때 이전 경계를 걷지 않으면 두 거점의 범위가 겹쳐 보이고,
 * 화면은 멀쩡해 보이는 채로 "여기까지 쟀다"는 거짓말을 한다. 그 자리를 여기서 막는다.
 *
 * 보는 것 셋:
 *   1. 거점 전환 시 이전 거점의 오버레이·리스너가 걷히는가
 *   2. 마운트·전환이 부르는 API 경로가 기대와 맞는가
 *   3. 요약 패널이 **데이터 없을 때 / 있을 때** 각각 무엇을 그리는가
 */
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import HubExplorer from "@/pages/HubExplorer";
import { installFetchStub, type FetchStub } from "@/test/fetchStub";
import { installNaverStub, removeNaverStub, type NaverStub } from "@/test/naverStub";
import { renderOnMap } from "@/test/renderMap";
import { district, vacancyHeatmap, cell } from "@/test/fixtures";

// SDK 로더만 목킹한다 — 실제 스크립트를 붙이지 않고, 지도 자체는 window.naver 스텁이 만든다.
vi.mock("@/lib/naverMap", () => ({
  loadNaverMaps: () => Promise.resolve(),
  describeNaverMapError: (e: unknown) => String(e),
}));

const HUBS = [
  district("garosugil", { name: "가로수길" }),
  district("yeonnam", { name: "연남동", gu: "마포구", vacancy_rate: 7.7 }),
  // 실측 히트맵이 없는 거점 — 라우트에 안 걸려 404 로 떨어진다(정상 상태다).
  district("banpo", { name: "반포", gu: "서초구", vacancy_rate: null, vacancy_withheld: true }),
];

let naver: NaverStub;
let api: FetchStub;

function mount() {
  api = installFetchStub([
    { match: /\/api\/v1\/commercial-districts$/, body: HUBS },
    // 연남동은 셀을 흩뜨려 조각이 2개가 되게 둔다 — 경계 배지가 조각 수를 밝히는지도 같이 본다.
    { match: /\/api\/v1\/heatmap\/vacancy\?district=garosugil/, body: vacancyHeatmap("garosugil") },
    {
      match: /\/api\/v1\/heatmap\/vacancy\?district=yeonnam/,
      body: vacancyHeatmap("yeonnam", [cell(0, 0), cell(1, 0), cell(5, 5)]),
    },
  ]);
  return renderOnMap(<HubExplorer />);
}

beforeEach(() => { naver = installNaverStub(); });
// ⚠ 순서가 중요하다 — 남아 있던 패시브 이펙트를 cleanup 으로 먼저 흘려보낸 **뒤에** SDK 를
//   걷는다. 반대로 하면 언마운트 도중 화면 코드가 `window.naver` 를 못 찾고 죽는다.
afterEach(() => { cleanup(); removeNaverStub(); });

/** 거점 목록 버튼(좌측 패널)에서 이름으로 하나 고른다. */
async function pickHub(name: string) {
  const list = await screen.findByLabelText("거점 목록");
  fireEvent.click(await within(list).findByRole("button", { name: new RegExp(name) }));
}

describe("HubExplorer — API 경로", () => {
  it("마운트하면 거점 목록만 부른다 — 고르기 전에는 실측 히트맵을 미리 당기지 않는다", async () => {
    mount();
    await screen.findByLabelText("거점 목록");
    await waitFor(() => expect(api.count(/commercial-districts$/)).toBe(1));

    expect(api.urls()).toEqual(["GET /api/v1/commercial-districts"]);
  });

  it("거점을 고르면 그 거점의 실측 히트맵을 부른다 — 목록은 다시 부르지 않는다", async () => {
    mount();
    await pickHub("가로수길");

    await waitFor(() =>
      expect(api.count(/\/heatmap\/vacancy\?district=garosugil$/)).toBe(1));
    expect(api.count(/commercial-districts$/)).toBe(1);

    await pickHub("연남동");
    await waitFor(() =>
      expect(api.count(/\/heatmap\/vacancy\?district=yeonnam$/)).toBe(1));
    // 거점을 바꿔도 목록은 한 번뿐 — 전환마다 목록을 다시 당기면 66거점이 매번 흐른다.
    expect(api.count(/commercial-districts$/)).toBe(1);
  });
});

describe("HubExplorer — 거점 전환 시 정리", () => {
  it("거점을 바꾸면 이전 거점의 경계 오버레이가 전부 걷힌다", async () => {
    mount();
    await pickHub("가로수길");

    // 가로수길 = 2×2 한 덩어리 → 경계 1조각 = 폴리곤 1개
    await waitFor(() => expect(naver.live().length).toBe(1));
    const first = naver.live();
    expect(first.every((o) => o.kind === "Polygon")).toBe(true);

    await pickHub("연남동");

    // 연남동 = 2칸 + 떨어진 1칸 → 2조각 = 폴리곤 2개
    await waitFor(() => expect(naver.live().length).toBe(2));
    // 이전 거점의 폴리곤은 **하나도 남지 않는다**. 남으면 두 거점의 범위가 겹쳐 보인다.
    expect(first.map((o) => o.map)).toEqual([null]);
    expect(first[0].setMapCalls).toContain(null);
  });

  it("언마운트하면 걸어 둔 window 리스너가 남지 않는다", async () => {
    const add = vi.spyOn(window, "addEventListener");
    const remove = vi.spyOn(window, "removeEventListener");
    const view = mount();
    await pickHub("가로수길");
    await waitFor(() => expect(naver.live().length).toBe(1));

    const watched = ["hashchange", "keydown"];
    const added = add.mock.calls.filter(([t]) => watched.includes(String(t))).length;
    expect(added).toBeGreaterThan(0);

    view.unmount();

    const removed = remove.mock.calls.filter(([t]) => watched.includes(String(t))).length;
    expect(removed).toBe(added);
    // 지도는 살아 있지만 이 탭이 그린 것은 전부 걷혀야 한다.
    expect(naver.live()).toEqual([]);
  });
});

describe("HubExplorer — 요약 패널", () => {
  it("고르기 전에는 안내만 있고 수치를 그리지 않는다", async () => {
    mount();
    const summary = await screen.findByLabelText("거점 요약");

    expect(within(summary).getByText(/거점을 고르면 실측 범위와 요약이 여기 뜬다/)).toBeTruthy();
    expect(within(summary).queryByText("거점 대표 공실률")).toBeNull();
  });

  it("고르면 실측값과 **미측정 축**을 갈라 그린다 — 감성은 0 이 아니라 '실측 없음'이다", async () => {
    mount();
    await pickHub("가로수길");

    const summary = await screen.findByLabelText("거점 요약");
    await waitFor(() => expect(within(summary).getByText("가로수길")).toBeTruthy());

    expect(within(summary).getByText("12.3%")).toBeTruthy();          // 대표 공실률(실측)
    expect(within(summary).getByText("실측(Gold)")).toBeTruthy();      // 출처 배지
    expect(within(summary).getByText("실측 없음")).toBeTruthy();        // 감성 = 미측정
    // 경계는 실측 셀의 외곽선이다 — 셀 수·조각 수를 숨기지 않는다.
    await waitFor(() => expect(within(summary).getByText("4셀 · 1조각")).toBeTruthy());
  });

  it("실측 히트맵이 없는 거점은 실패를 밝히고 경계를 '없음'으로 둔다", async () => {
    mount();
    await pickHub("반포");

    const summary = await screen.findByLabelText("거점 요약");
    await waitFor(() => expect(within(summary).getByText(/거점 요약을 못 불러왔다/)).toBeTruthy());

    expect(within(summary).getByText("대표값 미제공")).toBeTruthy();
    expect(within(summary).getByText("없음")).toBeTruthy();     // 실측 범위
    expect(screen.getByText("실측 범위 없음")).toBeTruthy();     // 범례 배지
    // 경계가 없으면 지도에 아무것도 그리지 않는다(빈 폴리곤을 그리지 않는다).
    expect(naver.live()).toEqual([]);
  });
});

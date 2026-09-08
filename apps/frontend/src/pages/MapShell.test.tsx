/**
 * MapShell(「Page」 탭) 회귀 그물.
 *
 * 이 화면은 지도 위에 4개 레이어(공실·유동인구·임대시세·인구밀도)를 갈아끼운다. 지도는
 * MapHost 소유라 탭을 옮겨도 죽지 않는다 — 그래서 **걷는 쪽을 빠뜨리면 아무도 모른다.**
 * 이전 거점의 건물 폴리곤 840~1,443개가 새 거점 위에 그대로 남아도 지도는 잘 그려진다.
 *
 * 보는 것 셋:
 *   1. 거점 전환 시 이전 거점의 오버레이·줌 리스너가 걷히는가
 *   2. 레이어별로 부르는 API 경로가 기대와 맞는가 — 보고 있지도 않은 레이어를 미리 부르지 않는가
 *   3. 사이드패널이 실측일 때 / 백엔드가 없을 때 각각 무엇을 그리는가
 */
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import MapShell from "@/pages/MapShell";
import { installFetchStub, type FetchStub, type Route } from "@/test/fetchStub";
import { installNaverStub, removeNaverStub, type NaverStub } from "@/test/naverStub";
import { renderOnMap } from "@/test/renderMap";
import { buildings, district, rentHeatmap } from "@/test/fixtures";

vi.mock("@/lib/naverMap", () => ({
  loadNaverMaps: () => Promise.resolve(),
  describeNaverMapError: (e: unknown) => String(e),
}));

const HUBS = [
  district("garosugil", { name: "가로수길" }),
  district("yeonnam", { name: "연남동", gu: "마포구" }),
  // 합성 거점은 건물 폴리곤이 없다 — 이 화면의 목록에 들어오면 안 된다.
  district("synthetic-hub", { name: "합성거점", vacancy_source: "synthetic" }),
];

const GAROSU_BUILDINGS = buildings([
  { id: "g1", name: "가로수 A", status: "empty" },
  { id: "g2", name: "가로수 B", status: "full" },
  { id: "g3", name: "가로수 C", status: "high" },
]);
const YEONNAM_BUILDINGS = buildings([
  { id: "y1", name: "연남 A", status: "empty" },
  { id: "y2", name: "연남 B", status: "partial" },
]);

let naver: NaverStub;
let api: FetchStub;

/** `withBuildings: false` 면 /heatmap/buildings 가 404 → 화면이 로컬 샘플로 폴백한다. */
function mount(opts: { withBuildings?: boolean } = {}) {
  const routes: Route[] = [
    { match: /\/api\/v1\/commercial-districts$/, body: HUBS },
    { match: /\/api\/v1\/heatmap\/rent\?district=/, body: rentHeatmap("garosugil") },
    {
      match: /\/api\/v1\/heatmap\/footfall\?/,
      body: {
        district: "garosugil", footfall_source: "flpop_jipgyegu", resolution: "jipgyegu",
        oa_count: 26, trdar_count: 0, hour: 18, band: "x", band_label: "18시",
        time_source: "jipgyegu_hourly", daytype: "weekday", share_basis: "hour24",
        hour_share: 0.05, unit: "명", min: 0, max: 100, note: "", cells: [],
      },
    },
  ];
  if (opts.withBuildings !== false) {
    routes.push(
      { match: /\/api\/v1\/heatmap\/buildings\?district=garosugil/, body: GAROSU_BUILDINGS },
      { match: /\/api\/v1\/heatmap\/buildings\?district=yeonnam/, body: YEONNAM_BUILDINGS },
    );
  }
  api = installFetchStub(routes);
  return renderOnMap(<MapShell />);
}

beforeEach(() => { naver = installNaverStub(); });
// ⚠ 순서가 중요하다 — 남아 있던 패시브 이펙트를 cleanup 으로 먼저 흘려보낸 **뒤에** SDK 를
//   걷는다. 반대로 하면 언마운트 도중 화면 코드가 `window.naver` 를 못 찾고 죽는다.
afterEach(() => { cleanup(); removeNaverStub(); });

const hubSelect = () => screen.getByRole("combobox");

describe("MapShell — API 경로", () => {
  it("마운트하면 목록·건물·임대만 부른다 — 보고 있지 않은 레이어는 부르지 않는다", async () => {
    mount();

    await waitFor(() =>
      expect(api.count(/\/heatmap\/buildings\?district=garosugil$/)).toBe(1));
    expect(api.count(/commercial-districts$/)).toBe(1);
    expect(api.count(/\/heatmap\/rent\?district=garosugil$/)).toBe(1);
    // 유동·밀도는 그 레이어를 눌렀을 때만 — 거점 전환마다 3번씩 부를 이유가 없다.
    expect(api.count(/\/heatmap\/footfall/)).toBe(0);
    expect(api.count(/\/heatmap\/density/)).toBe(0);
  });

  it("유동인구 레이어를 눌러야 그때 시간대 질의가 나간다", async () => {
    mount();
    await waitFor(() => expect(api.count(/\/heatmap\/buildings/)).toBe(1));

    fireEvent.click(screen.getByRole("button", { name: "유동인구" }));

    await waitFor(() => expect(api.count(/\/heatmap\/footfall/)).toBe(1));
    // 슬라이더 기본값 18시가 **실제 질의에 들어간다**(2026-08-23 이전엔 장식이었다).
    expect(api.matching(/\/heatmap\/footfall/)[0].url)
      .toBe("/api/v1/heatmap/footfall?district=garosugil&hour=18&daytype=weekday");
  });

  it("실측(gold) 거점만 고를 수 있다 — 합성 거점은 건물 폴리곤이 없어 빈 지도가 된다", async () => {
    mount();
    await waitFor(() => expect(api.count(/\/heatmap\/buildings/)).toBe(1));

    const options = Array.from(hubSelect().querySelectorAll("option")).map((o) => o.value);
    expect(options).toEqual(["garosugil", "yeonnam"]);
  });
});

describe("MapShell — 거점 전환 시 정리", () => {
  it("거점을 바꾸면 이전 거점 건물 폴리곤이 전부 걷히고 새 거점만 남는다", async () => {
    mount();
    await waitFor(() => expect(naver.live().length).toBe(3));   // 가로수길 3동
    const before = naver.live();

    fireEvent.change(hubSelect(), { target: { value: "yeonnam" } });

    await waitFor(() =>
      expect(api.count(/\/heatmap\/buildings\?district=yeonnam$/)).toBe(1));
    await waitFor(() => expect(naver.live().length).toBe(2));   // 연남동 2동
    expect(before.every((o) => o.map === null)).toBe(true);
    expect(naver.live().every((o) => o.kind === "Polygon")).toBe(true);
  });

  it("줌을 당기면 공실의심만 점으로 바뀐다 — 줌 리스너가 실제로 걸려 있다", async () => {
    mount();
    await waitFor(() => expect(naver.live().length).toBe(3));

    const map = naver.map();
    expect(map).not.toBeNull();
    map!.setZoom(14);                       // PIN_MAX_ZOOM(15) 이하 = 먼 축척
    naver.emit(map, "zoom_changed");

    // 840~1,443동을 전부 칠하면 "어디가 비었나"가 색에 묻힌다 → empty 한 동만 점으로.
    await waitFor(() => expect(naver.live().length).toBe(1));
    expect(naver.live()[0].kind).toBe("Marker");
  });

  it("언마운트하면 오버레이도 지도 리스너도 남지 않는다", async () => {
    const view = mount();
    await waitFor(() => expect(naver.live().length).toBe(3));
    expect(naver.liveListeners().length).toBeGreaterThan(0);

    view.unmount();

    // 지도는 MapHost 소유라 계속 살아 있다 — 그래서 걷는 것이 이 탭의 책임이다.
    expect(naver.live()).toEqual([]);
    // **지도 자체에 건** 리스너가 관건이다. 지도는 탭보다 오래 사니, 여기 남으면
    // 죽은 컴포넌트의 setState 가 다음 탭에서 계속 불린다.
    // (걷힌 폴리곤에 붙어 있던 click 리스너는 오버레이와 함께 버려지므로 세지 않는다.)
    const onMap = naver.liveListeners().filter((l) => l.target === naver.map());
    expect(onMap).toEqual([]);
  });
});

describe("MapShell — 사이드패널", () => {
  it("실측이 오면 건물 목록과 '실측' 표시를 그린다", async () => {
    mount();

    expect(await screen.findByText(/3동 · 실측\(추정\)/)).toBeTruthy();
    expect(screen.getByText("가로수 A")).toBeTruthy();
    expect(screen.getByText("가로수 C")).toBeTruthy();
    // 거점 대표값도 같이 밝힌다.
    expect(screen.getByText(/거점 12\.3%/)).toBeTruthy();
  });

  it("백엔드에 건물 산출물이 없으면 로컬 샘플로 폴백하고 '샘플(추정)'이라고 밝힌다", async () => {
    mount({ withBuildings: false });

    // 합성·샘플을 실측처럼 보이게 하지 않는 것이 이 저장소의 제1원칙이다(AGENTS.md §0).
    expect(await screen.findByText(/8동 · 샘플\(추정\)/)).toBeTruthy();
    expect(screen.getByText("가로수길 A빌딩")).toBeTruthy();
    expect(screen.queryByText("가로수 A")).toBeNull();
  });
});

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
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import MapShell, { PIN_MAX_ZOOM } from "@/pages/MapShell";
import { DEFAULT_ZOOM } from "@/components/MapHost";
import { installFetchStub, type FetchStub, type Route } from "@/test/fetchStub";
import { installNaverStub, removeNaverStub, type NaverStub } from "@/test/naverStub";
import { renderOnMap } from "@/test/renderMap";
import { buildings, district, rentHeatmap, rentListing } from "@/test/fixtures";
import type { RentHeatmap } from "@/lib/api";
import { createPageWorkspace } from "@/lib/workspaceState";

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
function mount(opts: { withBuildings?: boolean; rent?: RentHeatmap; onReview?: (selection: { districtId: string; buildingId: string; buildingName: string }) => void } = {}) {
  const routes: Route[] = [
    { match: /\/api\/v1\/commercial-districts$/, body: HUBS },
    { match: /\/api\/v1\/heatmap\/rent\?district=/, body: opts.rent ?? rentHeatmap("garosugil") },
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
  return renderOnMap(<MapShell onReview={opts.onReview} />);
}

beforeEach(() => { naver = installNaverStub(); });
// ⚠ 순서가 중요하다 — 남아 있던 패시브 이펙트를 cleanup 으로 먼저 흘려보낸 **뒤에** SDK 를
//   걷는다. 반대로 하면 언마운트 도중 화면 코드가 `window.naver` 를 못 찾고 죽는다.
afterEach(() => { cleanup(); removeNaverStub(); });

const hubSelect = () => screen.getByRole("combobox", { name: "상권 선택" });

/**
 * **폴리곤 모드로 들어간다** — 건물마다 도형이 하나씩 필요한 테스트용.
 *
 * 2026-09-13 부터 앱 기본 줌(DEFAULT_ZOOM=16)은 **점 모드**다(PIN_MAX_ZOOM=16 이하).
 * 그전에는 경계가 15 라 기본 화면이 폴리곤이었고 테스트도 그냥 마운트만 하면 됐다.
 * 이제는 확대해야 한다 — 안 그러면 공실의심(empty)만 그려져 수가 안 맞는다.
 */
async function polygonMode() {
  await waitFor(() => expect(naver.map()).not.toBeNull());
  const map = naver.map()!;
  map.setZoom(PIN_MAX_ZOOM + 1);
  naver.emit(map, "zoom_changed");
}

describe("MapShell — 후보 탐색과 비교", () => {
  beforeEach(() => {
    // jsdom에는 dialog의 top-layer 구현이 없다. 열림 상태만 재현한다.
    HTMLDialogElement.prototype.showModal = function () { this.open = true; };
    HTMLDialogElement.prototype.close = function () { this.open = false; };
  });

  it("검색과 상태 조건이 목록과 지도에 함께 적용되고 초기화된다", async () => {
    mount();
    await polygonMode();
    await waitFor(() => expect(naver.live()).toHaveLength(3));
    fireEvent.change(screen.getByRole("combobox", { name: "공실 상태 필터" }), { target: { value: "empty" } });
    expect(screen.queryByText("가로수 B")).toBeNull();
    await waitFor(() => expect(naver.live()).toHaveLength(1));
    fireEvent.change(screen.getByRole("textbox", { name: "건물 검색" }), { target: { value: "찾을 수 없는 건물" } });
    expect(screen.getByText("조건에 맞는 건물이 없습니다")).toBeTruthy();
    await waitFor(() => expect(naver.live()).toHaveLength(0));
    fireEvent.click(screen.getByRole("button", { name: "조건 초기화" }));
    await waitFor(() => expect(naver.live()).toHaveLength(3));
  });

  it("후보 저장·비교가 동일한 건물과 출처를 유지하며 메모를 편집한다", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "가로수 A 후보 저장" }));
    fireEvent.click(screen.getByRole("button", { name: "가로수 C 후보 저장" }));
    fireEvent.click(screen.getByRole("button", { name: "후보 비교" }));
    const dialog = within(screen.getByRole("dialog", { name: "가로수길에서 고른 건물" }));
    expect(dialog.getByRole("columnheader", { name: "가로수 A" })).toBeTruthy();
    expect(dialog.queryByRole("columnheader", { name: "가로수 B" })).toBeNull();
    expect(dialog.getByText(/실측 자료 기반 공실 추정/)).toBeTruthy();
    fireEvent.change(dialog.getByRole("textbox", { name: "가로수 A 선택 이유" }), { target: { value: "입구 동선 답사" } });
    fireEvent.click(dialog.getByRole("button", { name: "후보 비교 닫기" }));
    fireEvent.click(screen.getByRole("button", { name: "후보 비교" }));
    expect((screen.getByRole("textbox", { name: "가로수 A 선택 이유" }) as HTMLTextAreaElement).value).toBe("입구 동선 답사");
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "가로수 A 후보 해제" }));
    expect(within(screen.getByRole("dialog")).queryByRole("columnheader", { name: "가로수 A" })).toBeNull();
  });

  it("거점별 후보를 섞지 않고 원래 거점으로 돌아오면 저장 상태를 복원한다", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "가로수 A 후보 저장" }));
    fireEvent.change(hubSelect(), { target: { value: "yeonnam" } });
    await screen.findByText("연남 A");
    expect(screen.getByText("저장한 후보 0/3")).toBeTruthy();
    fireEvent.change(hubSelect(), { target: { value: "garosugil" } });
    expect(await screen.findByRole("button", { name: "가로수 A 후보 해제" })).toBeTruthy();
  });

  it("입점 검토에는 건물 식별자만 넘기고 샘플 자료는 넘기지 않는다", async () => {
    const review = vi.fn();
    const view = mount({ onReview: review });
    fireEvent.click(await screen.findByRole("button", { name: /^가로수 A 카페/ }));
    fireEvent.click(screen.getByRole("button", { name: "이 건물로 입점 검토 →" }));
    expect(review).toHaveBeenCalledWith({ districtId: "garosugil", buildingId: "g1", buildingName: "가로수 A" });
    view.unmount();
    mount({ withBuildings: false, onReview: review });
    fireEvent.click(await screen.findByRole("button", { name: /^가로수길 A빌딩 의류/ }));
    expect((screen.getByRole("button", { name: "이 건물로 입점 검토 →" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "가로수길 A빌딩 후보 저장" }) as HTMLButtonElement).disabled).toBe(true);
    expect(review).toHaveBeenCalledTimes(1);
  });
});

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

/**
 * 임대시세 = **금액** (2026-09-13).
 * 종전에는 100m 격자를 초록 5단계로 칠했다 — "진한 곳이 비싸다"만 있고 "얼마냐"가 없었다.
 * 이 그물이 잡는 회귀: 금액 칩 대신 색 칸(Polygon)이 돌아오는 것, 층별 표·건물 상세에서
 * 금액이 사라지는 것, 추정(probable) 공실이 확정과 같은 모양으로 그려지는 것.
 */
describe("MapShell — 임대시세는 금액으로 말한다", () => {
  const RENT = rentHeatmap("garosugil", [
    rentListing("g1", 0, { monthly_rent: 740 }),
    rentListing("g3", 2, { id: "vfu-g3-2", floor: 2, floor_label: "2F", monthly_rent: 333, rent_per_pyeong: 11.1, certainty: "probable" }),
  ]);
  const chips = () => naver.live().filter((o) => o.kind === "Marker")
    .map((o) => String((o.options.icon as { content?: string } | undefined)?.content ?? ""));

  it("격자를 칠하지 않고 층별 평당 표와 금액 칩을 건다", async () => {
    mount({ rent: RENT });
    await screen.findByText("가로수 A");
    fireEvent.click(screen.getByRole("button", { name: "임대시세" }));

    // 패널의 첫 답 — 층마다 평당 월 얼마.
    const table = await screen.findByLabelText("층별 평당 월 임대료");
    expect(within(table).getByText("24.7만")).toBeTruthy();
    expect(within(table).getByText("11.1만")).toBeTruthy();
    expect(table.textContent).toContain("보증금·권리금·관리비 제외");

    // 기본 줌(점 모드 축척)에서는 묶음 칩 하나 — 두 매물의 금액 범위와 개수를 글자로 말한다.
    await waitFor(() => expect(chips()).toHaveLength(1));
    expect(chips()[0]).toContain("월 333만~740만");
    expect(chips()[0]).toContain("2곳");
    // 색 칸(격자)은 한 장도 없다.
    expect(naver.live().filter((o) => o.kind === "Polygon")).toHaveLength(0);
  });

  it("확대하면 건물마다 가장 싼 빈 층 금액을 걸고, 추정 공실은 점선이다", async () => {
    mount({ rent: RENT });
    await screen.findByText("가로수 A");
    fireEvent.click(screen.getByRole("button", { name: "임대시세" }));
    await polygonMode();

    await waitFor(() => expect(chips()).toHaveLength(2));
    const g1 = chips().find((c) => c.includes("월 740만"))!;
    const g3 = chips().find((c) => c.includes("월 333만"))!;
    expect(g1).toContain("solid");
    expect(g3).toContain("dashed");
    // 목록 줄에도 같은 금액이 붙는다 — 지도와 목록이 다른 숫자를 말하면 둘 다 못 믿는다.
    const rentLines = screen.getAllByText(/빈 층 1개 · 월/).map((el) => el.textContent);
    expect(rentLines).toEqual(expect.arrayContaining([expect.stringContaining("740만원"), expect.stringContaining("333만원")]));
  });

  it("건물을 고르면 층마다 월 임대료를 표로 보여주고, 레이어는 임대시세에 머문다", async () => {
    mount({ rent: RENT });
    await screen.findByText("가로수 C");
    fireEvent.click(screen.getByRole("button", { name: "임대시세" }));
    fireEvent.click(screen.getByRole("button", { name: /^가로수 C 카페/ }));

    expect(await screen.findByText("빈 층 임대료(추정)")).toBeTruthy();
    // 목록 줄에도 "333만원"이 있으므로 상세 표 안에서만 찾는다.
    const row = within(screen.getByRole("table")).getByText("333만원").closest("tr")!;
    expect(row.className).toContain("is-probable");
    expect(within(row).getByText(/추정/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "임대시세" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("R-ONE 이 없는 거점은 금액을 지어내지 않고 없다고 말한다", async () => {
    installFetchStub([{ match: /\/api\/v1\/commercial-districts$/, body: HUBS },
      { match: /\/api\/v1\/heatmap\/buildings\?district=garosugil/, body: GAROSU_BUILDINGS }]);
    renderOnMap(<MapShell />);
    await screen.findByText("가로수 A");
    fireEvent.click(screen.getByRole("button", { name: "임대시세" }));
    expect(await screen.findByText(/이 거점에는 R-ONE 임대료가 없다/)).toBeTruthy();
    expect(screen.queryByLabelText("층별 평당 월 임대료")).toBeNull();
    expect(chips()).toHaveLength(0);
  });
});

/**
 * 화면설계서 2판 §Page 통과 조건 — PG-02(범례 기준) · PG-05(입력칸 Esc) · PG-07(선택 → 카메라·강조) ·
 * 인계받은 건물이 목록에 없을 때.
 */
describe("MapShell — 화면설계서 2판", () => {
  it("PG-02 범례 칩이 공실 상태의 점유율 기준을 말한다", async () => {
    mount();
    await polygonMode();
    await waitFor(() => expect(naver.live()).toHaveLength(3));
    const full = screen.getByTitle("만실 — 점유율 90% 이상");
    expect(full.textContent).toContain("점유율 90% 이상");   // 스크린리더용 글자
    expect(screen.getByTitle(/^공실의심 — 영업으로 확인된 호실 0/)).toBeTruthy();
  });

  it("PG-05 검색칸에서 Esc 를 눌러도 상세가 닫히지 않고, 검색칸 밖에서는 한 겹 닫힌다", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /^가로수 A 카페/ }));
    expect(screen.getByRole("button", { name: "← 건물 목록" })).toBeTruthy();
    const search = screen.getByRole("textbox", { name: "건물 검색" });
    search.focus();
    fireEvent.keyDown(search, { key: "Escape" });
    expect(screen.getByRole("button", { name: "← 건물 목록" })).toBeTruthy();
    fireEvent.keyDown(document.body, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("button", { name: "← 건물 목록" })).toBeNull());
  });

  it("PG-07 고른 건물은 호버를 떼도 강조가 남고, 도형을 다시 만들어도 강조가 다시 입혀진다", async () => {
    mount();
    await polygonMode();
    await waitFor(() => expect(naver.live()).toHaveLength(3));
    const row = await screen.findByRole("button", { name: /^가로수 A 카페/ });
    fireEvent.mouseEnter(row);
    fireEvent.click(row);
    fireEvent.mouseLeave(row);
    const g1 = () => naver.live().filter((o) => o.kind === "Polygon")[0];
    await waitFor(() => expect(g1().options.strokeWeight).toBe(4));
    expect(naver.map()!.moves.some((m) => m.kind === "panTo")).toBe(true);

    // 조건을 바꿔 도형을 새로 만들어도(1동만 남김) 고른 건물 강조가 유지된다.
    fireEvent.change(screen.getByRole("combobox", { name: "공실 상태 필터" }), { target: { value: "empty" } });
    await waitFor(() => expect(naver.live().filter((o) => o.kind === "Polygon")).toHaveLength(1));
    expect(g1().options.strokeWeight).toBe(4);
  });

  it("인계받은 건물이 이 상권 목록에 없으면 찾지 못했다고 말하고, 닫기로 선택을 푼다", async () => {
    installFetchStub([
      { match: /\/api\/v1\/commercial-districts$/, body: HUBS },
      { match: /\/api\/v1\/heatmap\/buildings\?district=garosugil/, body: GAROSU_BUILDINGS },
    ]);
    const change = vi.fn();
    renderOnMap(<MapShell workspace={{ ...createPageWorkspace(), selectedId: "no-such-building" }} onWorkspaceChange={change} />);
    expect(await screen.findByText("선택한 건물을 이 상권 건물 목록에서 찾지 못했습니다.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "닫기" }));
    expect(change).toHaveBeenCalled();
  });
});

describe("MapShell — 거점 전환 시 정리", () => {
  it("거점을 바꾸면 이전 거점 건물 폴리곤이 전부 걷히고 새 거점만 남는다", async () => {
    mount();
    await polygonMode();
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
    await polygonMode();
    await waitFor(() => expect(naver.live().length).toBe(3));

    const map = naver.map()!;
    map.setZoom(PIN_MAX_ZOOM);              // 경계 **이하** = 먼 축척
    naver.emit(map, "zoom_changed");

    // 840~1,443동을 전부 칠하면 "어디가 비었나"가 색에 묻힌다 → empty 한 동만 점으로.
    await waitFor(() => expect(naver.live().length).toBe(1));
    expect(naver.live()[0].kind).toBe("Marker");
  });

  /* 2026-09-13: 이 테스트가 이번 변경의 **본체**다.
     점 모드는 2026-09-06 부터 구현돼 있었지만 경계가 15 이고 앱 기본 줌이 16 이라
     **기본 화면에서는 한 번도 보인 적이 없다** — 사용자가 일부러 축소해야만 닿았고,
     열자마자 보이는 것은 840동이 4색으로 꽉 찬 지도였다(디자이너 피드백이 지적한 화면).
     경계를 16 으로 올려 기본 화면이 "어디가 비었나"에 먼저 답하게 했다.
     여기가 무너지면 그 회귀가 조용히 돌아온 것이다. */
  it("앱 기본 줌에서는 공실의심만 점으로 찍는다 — 열자마자 빈 자리가 보인다", async () => {
    mount();

    // 확대하지 않는다. MapHost 가 세운 그대로 = 사용자가 앱을 열었을 때의 화면.
    await waitFor(() => expect(naver.live().length).toBeGreaterThan(0));
    expect(naver.map()!.getZoom()).toBe(DEFAULT_ZOOM);

    // 3동 중 empty 는 g1 하나뿐이다(가로수 A). 만실·고공실은 이 축척에서 그리지 않는다.
    await waitFor(() => expect(naver.live().length).toBe(1));
    expect(naver.live()[0].kind).toBe("Marker");

    // 지도에 안 그렸다고 목록에서 빼지는 않는다 — 둘은 다른 질문에 답한다.
    expect(screen.getByText("가로수 B")).toBeTruthy();
    expect(screen.getByText("가로수 C")).toBeTruthy();
  });

  /* 이 부등식이 이번 버그의 재발 방지선이다. 두 값은 다른 파일에 있어 따로 움직이기
     쉽고(MapHost 의 지도 옵션 vs MapShell 의 표현 경계), 어긋나도 화면은 멀쩡해 보인다. */
  it("점 모드 경계는 앱 기본 줌을 포함한다 (PIN_MAX_ZOOM ≥ DEFAULT_ZOOM)", () => {
    expect(PIN_MAX_ZOOM).toBeGreaterThanOrEqual(DEFAULT_ZOOM);
  });

  it("언마운트하면 오버레이도 지도 리스너도 남지 않는다", async () => {
    const view = mount();
    await polygonMode();
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

/**
 * 레퍼런스 이식분(design/references/INDEX.md §2-3 Zillow·Redfin · §1-1 호갱노노)의 회귀 그물.
 *
 * 이 둘은 **조용히 비싸지는** 기능이라 눈으로 보면 멀쩡한데 성능이 죽는다:
 *   - 호버 강조를 오버레이 렌더 useEffect 의 deps 로 넣으면 마우스가 한 칸 움직일 때마다
 *     폴리곤 1,443개를 부수고 다시 만든다. 화면은 똑같이 보인다.
 *   - 뷰포트 필터를 오버레이까지 걸면 지도를 조금만 밀어도 전부 다시 그린다.
 * 그래서 "무엇이 보이나"만 보지 않고 **오버레이를 몇 개 다시 만들었나**를 같이 센다.
 */
describe("MapShell — 지도 ↔ 목록 동기화", () => {
  /** ⚠ `naver.overlays` 는 **걷힌 것도 들고 있다**(걷혔는지를 봐야 하므로).
   *  화면이 점 모드 → 폴리곤 모드로 한 번 갈아타는 동안 죽은 폴리곤이 앞에 쌓이는데,
   *  그걸 집으면 리스너가 이미 떨어져 있어 mouseover 를 쏴도 아무 일이 없다.
   *  **지금 지도에 붙어 있는 것만** 본다. */
  const polygons = () => naver.live().filter((o) => o.kind === "Polygon");

  it("목록을 가리키면 그 건물 도형만 강조하고, 도형을 다시 만들지 않는다", async () => {
    mount();
    await polygonMode();
    await waitFor(() => expect(naver.live()).toHaveLength(3));
    const made = naver.overlays.length;
    // 건물은 filtered 순서대로 그려진다 — g1·g2·g3.
    const [pg1, pg2] = polygons();
    // 호버 전 채움색을 받아 둔다. 아래에서 **이 값이 그대로인지**를 본다.
    const baseFill = pg1.options.fillColor;

    fireEvent.mouseEnter(await screen.findByRole("button", { name: /^가로수 A 카페/ }));

    // 강조는 **제자리에서** 일어난다. 새 오버레이가 생겼다면 렌더 경로를 탄 것이다.
    expect(naver.overlays.length).toBe(made);
    expect(pg1.setOptionsCalls.length).toBe(1);
    expect(pg1.options.strokeWeight).toBe(4);
    expect(pg1.options.zIndex).toBe(200);
    // 채움색은 공실 상태를 뜻한다 — 호버가 건드리면 화면이 거짓말을 한다.
    expect(pg1.options.fillColor).toBe(baseFill);
    // 가리키지 않은 건물은 손대지 않는다.
    expect(pg2.setOptionsCalls.length).toBe(0);

    fireEvent.mouseLeave(screen.getByRole("button", { name: /^가로수 A 카페/ }));
    expect(pg1.options.strokeWeight).toBe(2);
    expect(pg1.options.zIndex).toBe(50);
    expect(naver.overlays.length).toBe(made);
  });

  it("지도 쪽에서 가리켜도 목록의 같은 줄이 뜬다 — 왕복이 닫힌다", async () => {
    mount();
    await polygonMode();
    await waitFor(() => expect(naver.live()).toHaveLength(3));
    const [pg1] = polygons();

    naver.emit(pg1, "mouseover");

    const row = (await screen.findByText("가로수 A")).closest(".building-card");
    expect(row?.className).toContain("is-hot");

    naver.emit(pg1, "mouseout");
    expect((await screen.findByText("가로수 A")).closest(".building-card")?.className).not.toContain("is-hot");
  });

  it("지도를 움직이면 목록이 화면 범위로 좁혀지고, 「거점 전체」로 되돌릴 수 있다", async () => {
    mount();
    await polygonMode();
    await waitFor(() => expect(naver.live()).toHaveLength(3));
    expect(await screen.findByText("가로수 C")).toBeTruthy();
    const made = naver.overlays.length;

    // g1 만 담는 범위. fixtures 의 건물은 (37.52, 127.02)에서 0.0002 씩 어긋나 있다.
    const map = naver.map()!;
    map.bounds = new naver.LatLngBounds(new naver.LatLng(37.5199, 127.0199), new naver.LatLng(37.5201, 127.0201));
    naver.emit(map, "idle");

    await waitFor(() => expect(screen.queryByText("가로수 C")).toBeNull());
    expect(screen.getByText("가로수 A")).toBeTruthy();
    // 분모를 같이 말한다 — 조건에 맞는 3동 중 화면 안 1동.
    expect(screen.getByText(/조건에 맞는/)).toBeTruthy();
    // ⚠ 좁히는 건 **목록뿐이다.** 지도 도형까지 걸러 다시 그리면 이 수가 늘어난다.
    expect(naver.overlays.length).toBe(made);

    fireEvent.click(screen.getByRole("button", { name: "지도 범위만" }));
    expect(await screen.findByText("가로수 C")).toBeTruthy();
    expect(naver.overlays.length).toBe(made);
  });

  it("범위 밖이라 비었을 때와 조건이 안 맞아 비었을 때를 다르게 말한다", async () => {
    mount();
    await polygonMode();
    await waitFor(() => expect(naver.live()).toHaveLength(3));

    const map = naver.map()!;
    // 건물이 하나도 없는 바다 한가운데.
    map.bounds = new naver.LatLngBounds(new naver.LatLng(35.0, 125.0), new naver.LatLng(35.1, 125.1));
    naver.emit(map, "idle");

    // 필터를 지우라고 하면 안 된다 — 멀쩡한 조건을 지우게 된다.
    expect(await screen.findByText("이 화면 범위에는 없습니다")).toBeTruthy();
    expect(screen.queryByText("조건에 맞는 건물이 없습니다")).toBeNull();

    fireEvent.change(screen.getByRole("textbox", { name: "건물 검색" }), { target: { value: "찾을 수 없는 건물" } });
    expect(await screen.findByText("조건에 맞는 건물이 없습니다")).toBeTruthy();
  });
});

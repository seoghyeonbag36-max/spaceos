/**
 * 「내 사업」 흐름 — 화면설계서 3판(주요 고객 재정의) 회귀 그물.
 *
 * 잡는 회귀:
 *   - 처음 방문에 카드가 안 뜨거나, 필수 칸이 비었는데 「시작」이 눌리는 것(C-08)
 *   - 시작한 뒤 Platform 으로 넘어가지 않거나 칩·저장이 목적을 말하지 않는 것(C-09 · C-10)
 *   - 업종 바꾸기 표의 「이 업종으로 입점 계산 →」이 Posting 업종칸을 채우지 않는 것(PL-10 · PS-08)
 *   - 모델 7종 밖 업종에 순위를 지어 보여주는 것(PL-11)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "@/App";
import { installNaverStub, removeNaverStub } from "@/test/naverStub";
import { installFetchStub, type Route } from "@/test/fetchStub";
import { buildings, district } from "@/test/fixtures";
import type { IndustryOption } from "@/lib/api";
import { STORAGE_KEY } from "@/lib/businessProfile";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.resolve(), describeNaverMapError: String }));

beforeEach(() => { installNaverStub(); });
afterEach(() => { cleanup(); removeNaverStub(); });

const TAB_LOAD = { timeout: 20000 };

const INDUSTRIES: IndustryOption[] = [
  { key: "cafe", label: "카페·디저트", input: "카페", model_label: "카페" },
  { key: "restaurant", label: "음식점", input: "음식점", model_label: "음식점" },
  { key: "bar", label: "술집", input: "주점", model_label: null },
];

const fitRow = (id: string, name: string, fit: number | null, rank: number | null) => ({
  district_id: id, name, gu: "강남구", fit, fit_rank: rank,
  same_n: 30, sample_n: 100, same_share: 0.3, rent_1f_per_pyeong: 24.7, rent_shared: false,
});

function mount(extra: Route[] = []) {
  installFetchStub([
    ...extra,
    { match: /ai\/industries$/, body: { industries: INDUSTRIES } },
    { match: /commercial-districts$/, body: [district("garosugil", { name: "가로수길" }), district("yeonnam", { name: "연남동" })] },
    { match: /heatmap\/buildings\?/, body: buildings([{ id: "g1", name: "검토 건물", status: "empty" }]) },
    { match: /postings$/, body: [] },
  ]);
  render(<App />);
}

describe("「내 사업」 — 화면설계서 3판", { timeout: 60000 }, () => {
  it("C-08 · C-09 · C-10 처음 방문에 카드가 뜨고, 채워야 시작되며, 시작하면 Platform 이 내 업종 기준 상권 순위를 먼저 답한다", async () => {
    mount([{
      match: /ai\/industry-fit\?industry=cafe/,
      body: { industry: INDUSTRIES[0], model_covered: true, seoul_fit: 0.2, ranked_n: 2, source: "src", note: "note",
        districts: [fitRow("yeonnam", "연남동", 0.24, 1), fitRow("garosugil", "가로수길", 0.18, 2)] },
    }]);
    const card = await screen.findByRole("region", { name: "무엇을 하려고 하세요?" });
    const start = within(card).getByRole("button", { name: "시작" }) as HTMLButtonElement;
    expect(start.disabled).toBe(true);

    fireEvent.click(within(card).getByRole("radio", { name: /새로 창업/ }));
    expect(start.disabled).toBe(true);     // 업종이 아직 없다
    fireEvent.click(await within(card).findByRole("radio", { name: /카페·디저트/ }));
    expect(start.disabled).toBe(false);
    fireEvent.click(start);

    // Platform 으로 넘어가 맨 위 카드가 순위를 말한다
    await screen.findByRole("complementary", { name: "상권 정체성" }, TAB_LOAD);
    const head = await screen.findByRole("heading", { name: /카페·디저트 — 가로수길/ }, TAB_LOAD);
    expect(head.textContent).toContain("서울 2곳 중 2위");
    const table = screen.getByRole("table", { name: /카페·디저트 기준 상권 순위/ });
    expect(within(table).getByRole("button", { name: "연남동 상권 보기" })).toBeTruthy();
    expect(screen.getByText(/매출·생존율이 아닙니다/)).toBeTruthy();

    // 칩이 목적과 업종을 말하고, 카드가 접혔고, 브라우저에 남았다
    expect(screen.getByRole("button", { name: /카페·디저트 창업/ })).toBeTruthy();
    expect(screen.queryByRole("region", { name: "무엇을 하려고 하세요?" })).toBeNull();
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "null"))
      .toEqual({ status: "set", profile: { goal: "start", industryKey: "cafe", homeDistrictId: null } });
  });

  it("「그냥 둘러보기」는 언제나 눌리고, 다시 열어도 카드가 펴지지 않는다", async () => {
    mount();
    const card = await screen.findByRole("region", { name: "무엇을 하려고 하세요?" });
    fireEvent.click(within(card).getByRole("button", { name: "그냥 둘러보기" }));
    expect(screen.queryByRole("region", { name: "무엇을 하려고 하세요?" })).toBeNull();
    // 첫 화면이 Platform 이 된 뒤(2026-09-26)로 「내 사업 설정」은 **둘**이다 — 셸의 칩과
    // Platform 빈 카드(IndustryFitCard)의 버튼. 여기서 보려는 건 칩이라 aria-expanded 로 가른다.
    expect(screen.getByRole("button", { name: /내 사업 설정/, expanded: false })).toBeTruthy();
    cleanup();
    mount();
    await screen.findByRole("button", { name: /내 사업 설정/, expanded: false });
    expect(screen.queryByRole("region", { name: "무엇을 하려고 하세요?" })).toBeNull();
  });

  it("PL-10 · PS-08 업종 바꾸기면 이 상권 업종 순위에 지금 업종이 표시되고, 다른 업종으로 입점 계산하면 Posting 업종칸이 채워진다", async () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      status: "set", profile: { goal: "pivot", industryKey: "restaurant", homeDistrictId: "garosugil" },
    }));
    mount([{
      match: /ai\/district-industries\/garosugil$/,
      body: { district_id: "garosugil", sample_n: 100, source: "src", note: "note", rows: [
        { ...INDUSTRIES[1], fit: 0.6, fit_rank: 1, same_n: 30, same_share: 0.3 },
        { ...INDUSTRIES[0], fit: 0.2, fit_rank: 2, same_n: 25, same_share: 0.25 },
        { ...INDUSTRIES[2], fit: null, fit_rank: null, same_n: 5, same_share: 0.05 },
      ] },
    }]);
    fireEvent.click(screen.getByRole("button", { name: "Platform" }));
    const table = await screen.findByRole("table", { name: /가로수길 업종 순위/ }, TAB_LOAD);
    expect(screen.getByRole("heading", { name: /음식점은 1위/ })).toBeTruthy();
    const mineRow = within(table).getByRole("rowheader", { name: /음식점/ }).closest("tr")!;
    expect(mineRow.textContent).toContain("지금");
    expect(within(mineRow).queryByRole("button")).toBeNull();   // 지금 업종으로는 계산 버튼이 없다
    expect(within(table).getByText("모델 밖")).toBeTruthy();

    fireEvent.click(within(table).getByRole("button", { name: "카페·디저트로 입점 계산" }));
    await screen.findByRole("complementary", { name: "입점 계산" }, TAB_LOAD);
    const input = await screen.findByPlaceholderText(/예: 카페/) as HTMLInputElement;
    expect(input.value).toBe("카페");
    expect(screen.getByText(/Platform 에서 고른 업종으로 채웠습니다/)).toBeTruthy();
  });

  it("PL-11 모델 7종 밖 업종이면 순위를 지어 보여주지 않는다", async () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      status: "set", profile: { goal: "start", industryKey: "bar", homeDistrictId: null },
    }));
    mount([{
      match: /ai\/industry-fit\?industry=bar/,
      body: { industry: INDUSTRIES[2], model_covered: false, seoul_fit: null, ranked_n: 0, source: "src", note: "note",
        districts: [fitRow("garosugil", "가로수길", null, null), fitRow("yeonnam", "연남동", null, null)] },
    }]);
    fireEvent.click(screen.getByRole("button", { name: "Platform" }));
    await screen.findByText(/적합도 순위를 내지 않습니다/, undefined, TAB_LOAD);
    expect(screen.queryByRole("table", { name: /기준 상권 순위/ })).toBeNull();
    expect(screen.queryByText(/곳 중 \d+위/)).toBeNull();
    // 같은 업종 비중은 그대로 보여준다
    await waitFor(() => expect(screen.getAllByText("30.0% (30/100곳)").length).toBeGreaterThan(0));
  });
});

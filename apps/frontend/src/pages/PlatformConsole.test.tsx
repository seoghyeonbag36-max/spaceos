import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import PlatformConsole from "./PlatformConsole";
import type { OpeningSite, PlatformProfile } from "@/lib/api";
import { district } from "@/test/fixtures";
import { installFetchStub } from "@/test/fetchStub";

// 테스트 전용 합성 응답이다. TODO: 실제 연동은 getPlatformProfile의 /platform 응답을 사용한다.
const SOURCE = "테스트 fixture · Gold 공실 + GNN 노드 · 출처 원문";
const DISTINCT_NOTE = "테스트 fixture · Top-3 밖 업종은 0으로 보는 근사이며 자리 간 비교용";

function site(n: number, over: Partial<OpeningSite> = {}): OpeningSite {
  return {
    unit_id: `test-unit-${n}`, name: `테스트 자리 ${n}`,
    lat: null, lng: null, area_py: 31.23456, floor: "2층", capacity: 9,
    vacancy_rate: 12.34567, was: "직전 테스트 업종", matched_distance_m: 23.45678,
    recommendations: [{ industry: "카페", score: 0.4567891 }],
    distinct: { industry: "카페", score: 0.4567891, district_mean: 0.4135782, delta_pp: 4.32109 },
    ...over,
  };
}

function profile(id: string, sites: OpeningSite[]): PlatformProfile {
  return {
    district_id: id,
    identity: {
      archetype: null, archetype_rule: "테스트 fixture", categories: { total: 0, groups: [], ungrouped: [] },
      keywords: { words: [], dropped: 0, scanned: 0 }, trends: [], demand: {}, source: "테스트 정체성 출처",
    },
    openings: {
      sites, unit_count: sites.length,
      matched_count: sites.filter((candidate) => candidate.matched_distance_m != null).length,
      match_radius_m: 400, source: SOURCE, distinct_note: DISTINCT_NOTE,
    },
  };
}

function mount(sites = [site(1), site(2), site(3), site(4)]) {
  const api = installFetchStub([
    { match: /\/commercial-districts$/, body: [district("garosugil", { name: "가로수길" }), district("yeonnam", { name: "연남동" })] },
    { match: /\/commercial-districts\/garosugil\/platform$/, body: profile("garosugil", sites) },
    { match: /\/commercial-districts\/yeonnam\/platform$/, body: profile("yeonnam", [site(1, { name: "연남 새 자리" }), site(2)]) },
    { match: /\/commercial-districts\/[^/]+\/sentiment$/, body: [] },
  ]);
  render(<PlatformConsole />);
  return api;
}

async function openCandidates() {
  const title = await screen.findByText("어느 자리에 어떤 업소가 들어오면 좋나");
  const details = title.closest("details")!;
  if (!details.open) fireEvent.click(title.closest("summary")!);
  return screen.getByRole("group", { name: "비교할 자리 선택" });
}

function choose(n: number) {
  fireEvent.click(screen.getByRole("checkbox", { name: `테스트 자리 ${n} (test-unit-${n}) 비교 후보 선택` }));
}

function comparison() {
  return screen.getByRole("region", { name: /가로수길 · 선택한 \d곳 근거 비교/ });
}

function rowValue(region: HTMLElement, name: string) {
  return within(region).getByRole("row", { name: new RegExp(`^${name}`) });
}

describe("PlatformConsole — 동일 상권 후보 비교", () => {
  it("2곳부터 비교할 수 있고 최대 3곳을 고르며 해제하면 다른 후보를 선택할 수 있다", async () => {
    mount();
    const group = await openCandidates();
    expect((screen.getByRole("button", { name: "선택한 0곳 비교" }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(group).getAllByRole("checkbox").every((box) => !(box as HTMLInputElement).checked)).toBe(true);

    choose(1);
    expect((screen.getByRole("button", { name: "선택한 1곳 비교" }) as HTMLButtonElement).disabled).toBe(true);
    choose(2);
    expect((screen.getByRole("button", { name: "선택한 2곳 비교" }) as HTMLButtonElement).disabled).toBe(false);
    choose(3);
    const fourth = within(group).getByRole("checkbox", { name: /테스트 자리 4/ }) as HTMLInputElement;
    expect(fourth.disabled).toBe(true);
    expect(screen.getByRole("status").textContent).toBe("비교 후보 3/3곳");
    expect(screen.getByText(/최대 3곳을 선택했습니다/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "테스트 자리 2 (test-unit-2) 비교에서 제외" }));
    expect(fourth.disabled).toBe(false);
    fireEvent.click(fourth);
    fireEvent.click(screen.getByRole("button", { name: "선택한 3곳 비교" }));
    const table = within(comparison()).getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual([
      "비교 항목", "테스트 자리 1test-unit-1", "테스트 자리 3test-unit-3", "테스트 자리 4test-unit-4",
    ]);

    fireEvent.click(screen.getByRole("button", { name: "선택 초기화" }));
    expect(screen.queryByRole("region", { name: /근거 비교/ })).toBeNull();
    expect(screen.getByRole("status").textContent).toBe("비교 후보 0/3곳");
    expect(fourth.checked).toBe(false);
  });

  it("거점이 바뀌면 비교 후보·비교 결과·더보기 범위가 초기화된다", async () => {
    const api = mount(Array.from({ length: 10 }, (_, i) => site(i + 1)));
    await openCandidates();
    choose(1);
    fireEvent.click(screen.getByRole("button", { name: "자리 1곳 더 보기" }));
    choose(10);
    fireEvent.click(screen.getByRole("button", { name: "선택한 2곳 비교" }));
    expect(comparison()).toBeTruthy();

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "yeonnam" } });
    await screen.findByText("연남동의 자리 비교");
    await openCandidates();
    expect(screen.getByRole("status").textContent).toBe("비교 후보 0/3곳");
    expect(screen.queryByRole("region", { name: /가로수길 · 선택한/ })).toBeNull();
    expect((screen.getByRole("checkbox", { name: /연남 새 자리/ }) as HTMLInputElement).checked).toBe(false);
    expect(api.count(/\/yeonnam\/platform$/)).toBe(1);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "garosugil" } });
    await screen.findByText("가로수길의 자리 비교");
    await openCandidates();
    expect(screen.queryByRole("checkbox", { name: /테스트 자리 10/ })).toBeNull();
    expect(screen.getByRole("status").textContent).toBe("비교 후보 0/3곳");
  });

  it("출처·근사 주석·원값 정밀도·단위를 유지하고 미제공 값과 0을 구분한다", async () => {
    mount([
      site(1),
      site(2, {
        area_py: 0, capacity: 0, floor: null, vacancy_rate: 0, matched_distance_m: 0,
        recommendations: [{ industry: "카페", score: 0 }],
        distinct: { industry: "카페", score: 0, district_mean: 0, delta_pp: 0 },
      }),
      site(3, {
        area_py: null, capacity: null, floor: null, vacancy_rate: null, matched_distance_m: null,
        recommendations: [], distinct: null, was: null,
      }),
    ]);
    await openCandidates();
    choose(1); choose(2); choose(3);
    fireEvent.click(screen.getByRole("button", { name: "선택한 3곳 비교" }));
    const region = comparison();
    expect(within(region).getByText(SOURCE, { exact: false })).toBeTruthy();
    expect(within(region).getByText(DISTINCT_NOTE)).toBeTruthy();
    expect(within(rowValue(region, "면적")).getAllByRole("cell").map((cell) => cell.textContent))
      .toEqual(["31.23456평", "0평", "미제공"]);
    expect(within(rowValue(region, "공실률")).getAllByRole("cell").map((cell) => cell.textContent))
      .toEqual(["12.34567%", "0%", "미제공"]);
    expect(within(rowValue(region, "추천 노드까지 거리")).getAllByRole("cell").map((cell) => cell.textContent))
      .toEqual(["23.45678m", "0m", "매칭 거리 미제공"]);
    expect(within(rowValue(region, "GNN 추천 점수")).getAllByRole("cell").map((cell) => cell.textContent))
      .toEqual(["카페 0.4567891", "카페 0", "추천 없음"]);
    expect(within(rowValue(region, "상권 평균 대비 차이")).getAllByRole("cell").map((cell) => cell.textContent))
      .toEqual(["+4.32109p", "0p", "차이 미제공"]);
    // 미제공 자리에 가짜 막대를 만들지 않고 0은 실제로 폭 0인 값으로 남긴다.
    const bars = region.querySelectorAll("rect.platform-comparison-bar");
    expect(bars.length).toBe(2);
    expect(bars[1].getAttribute("width")).toBe("0");
  });

  it("음수 차이는 공통 기준선 왼쪽에 그리고 성공 확률로 환산하지 않는다", async () => {
    mount([site(1), site(2, { distinct: { industry: "소매", score: 0.2, district_mean: 0.22, delta_pp: -2 } })]);
    await openCandidates();
    choose(1); choose(2);
    fireEvent.click(screen.getByRole("button", { name: "선택한 2곳 비교" }));
    const region = comparison();
    const bars = region.querySelectorAll("rect.platform-comparison-bar");
    expect(bars[0].getAttribute("x")).toBe("200");
    expect(Number(bars[1].getAttribute("x"))).toBeLessThan(200);
    expect(Number(bars[1].getAttribute("x")) + Number(bars[1].getAttribute("width"))).toBeCloseTo(200);
    expect(within(rowValue(region, "상권 평균 대비 차이")).getByText("-2p")).toBeTruthy();
    expect(within(region).getByText(/GNN 점수는 입점 성공 확률이 아닙니다/)).toBeTruthy();
  });

  it("모든 차이가 미제공이면 비교표를 유지하고 차트를 지어내지 않는다", async () => {
    mount([site(1, { distinct: null }), site(2, { distinct: null })]);
    await openCandidates();
    choose(1); choose(2);
    fireEvent.click(screen.getByRole("button", { name: "선택한 2곳 비교" }));
    const region = comparison();
    expect(within(region).getByText("차이 비교에 필요한 값이 없습니다.")).toBeTruthy();
    expect(within(region).getByRole("table")).toBeTruthy();
    expect(region.querySelector("svg")).toBeNull();
    expect(within(region).getByText(DISTINCT_NOTE)).toBeTruthy();
  });

  it("실측 공실 자리가 없으면 선택 UI나 비교값을 만들지 않는다", async () => {
    mount([]);
    const title = await screen.findByText("어느 자리에 어떤 업소가 들어오면 좋나");
    fireEvent.click(title.closest("summary")!);
    expect(screen.getByText("이 상권에는 실측 공실 자리가 없다.")).toBeTruthy();
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByRole("region", { name: "현재 비교 후보" })).toBeNull();
  });
});

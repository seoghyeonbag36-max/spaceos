import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { installNaverStub, removeNaverStub, type NaverStub } from "@/test/naverStub";
import { installFetchStub, type ApiCall } from "@/test/fetchStub";
import { buildings, district, postings, rentHeatmap, simulateResult } from "@/test/fixtures";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.resolve(), describeNaverMapError: String }));
vi.mock("@/pages/SeoulDashboard", () => ({ default: () => <div>서울 대시보드</div> }));

let naver: NaverStub;
beforeEach(() => { naver = installNaverStub(); });
afterEach(() => { cleanup(); removeNaverStub(); });

function mount(matched: boolean) {
  const units = postings("garosugil", 2).map((u, i) => ({ ...u, id: matched && i === 1 ? "vu-g1" : `other-${i}` }));
  const api = installFetchStub([
    { match: /commercial-districts$/, body: [district("garosugil", { name: "가로수길" })] },
    { match: /heatmap\/buildings\?/, body: buildings([{ id: "g1", name: "검토 건물", status: "empty" }]) },
    { match: /heatmap\/rent\?/, body: rentHeatmap("garosugil") },
    { match: /garosugil\/postings$/, body: units },
    { match: /ai\/simulate-revenue$/, body: (_m: RegExpExecArray, call: ApiCall) => {
      const input = call.body as { district_id: string; unit_id: string };
      return simulateResult(input.district_id, input.unit_id);
    } },
  ]);
  render(<App />);
  return api;
}

describe("App — Page에서 입점 검토", () => {
  it("검증된 건물 유닛을 인계하고 Page 후보·검색·단일 지도를 보존한다", async () => {
    const api = mount(true);
    fireEvent.click(screen.getByRole("button", { name: "Page" }));
    fireEvent.click(await screen.findByRole("button", { name: "검토 건물 후보 저장" }));
    fireEvent.change(screen.getByRole("textbox", { name: "건물 검색" }), { target: { value: "검토" } });
    fireEvent.click(screen.getByRole("button", { name: /^검토 건물 카페/ }));
    const map = naver.map();
    fireEvent.click(screen.getByRole("button", { name: "이 건물로 입점 검토 →" }));
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    expect(api.matching(/simulate-revenue$/)[0].body).toMatchObject({ unit_id: "vu-g1", district_id: "garosugil" });
    fireEvent.click(screen.getByRole("button", { name: "Page" }));
    expect(await screen.findByRole("button", { name: "검토 건물 후보 해제" })).toBeTruthy();
    expect((screen.getByRole("textbox", { name: "건물 검색" }) as HTMLInputElement).value).toBe("검토");
    expect(naver.map()).toBe(map);
  });

  it("일치하는 유닛이 없으면 첫 자리를 자동 선택하거나 계산하지 않는다", async () => {
    const api = mount(false);
    fireEvent.click(screen.getByRole("button", { name: "Page" }));
    fireEvent.click(await screen.findByRole("button", { name: /^검토 건물 카페/ }));
    fireEvent.click(screen.getByRole("button", { name: "이 건물로 입점 검토 →" }));
    expect(await screen.findByText(/일치하는 입점 계산 유닛이 없습니다/)).toBeTruthy();
    expect(api.count(/simulate-revenue$/)).toBe(0);
    expect((screen.getByRole("button", { name: "시뮬레이션" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getAllByRole("combobox")[1] as HTMLSelectElement).value).toBe("");
  });
});

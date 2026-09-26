import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { installNaverStub, removeNaverStub, type NaverStub } from "@/test/naverStub";
import { installFetchStub, type ApiCall } from "@/test/fetchStub";
import { buildings, district, postings, rentHeatmap, simulateResult } from "@/test/fixtures";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.resolve(), describeNaverMapError: String }));

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

// ⚠ Page 화면은 lazy 청크 + 지도 로더 + API 를 거쳐야 목록이 선다. 전체 병렬 실행
//   부하에서는 findBy 기본 1초를 넘겨 스켈레톤이 떠 있는 채 실패했다(2026-09-13, 2회 중 1회).
//   첫 대기에만 여유를 준다 — 이후 단계는 이미 로드된 화면이라 기본값으로 충분하다.
const FIRST_LOAD = { timeout: 5000 };
// 트랙 화면(Platform·Posting·Program)은 2026-09-13 부터 lazy 청크다 — 탭을 처음 누르면 청크 변환·로드가
// 끼어든다. 부하가 걸린 PC 에서 5초를 넘겨 폴백("화면 불러오는 중…")이 떠 있는 채 실패했다(09-13 실측).
const TAB_LOAD = { timeout: 20000 };
// 여러 트랙 청크를 한 테스트에서 차례로 여는 묶음은 테스트 한도도 그만큼 준다. 기다림(TAB_LOAD)은
// 20초인데 테스트 기본 한도가 5초라, 네 화면을 연달아 여는 테스트가 판정 전에 잘렸다(09-13).
const MULTI_TAB = { timeout: 60000 };

describe("App — 레일과 지도 셸 (2026-09-13)", MULTI_TAB, () => {
  it("레일에는 PlaceOS 로고와 PPPP 네 트랙만 있다 — 서울·거점 탭은 없다", async () => {
    mount(true);
    const rail = screen.getByRole("navigation", { name: "주요 화면" });
    expect(rail.textContent).toContain("PlaceOS");
    expect(rail.textContent).not.toMatch(/SpaceOS/);
    const labels = Array.from(rail.querySelectorAll("button")).map((b) => b.textContent);
    // 레일 순서는 PPPP 프레임워크 순서 그대로다(2026-09-26).
    expect(labels).toEqual(["Platform", "Page", "Posting", "Program"]);
    expect(screen.queryByRole("button", { name: "서울" })).toBeNull();
    expect(screen.queryByRole("button", { name: "거점" })).toBeNull();
    // 레일 맨 위와 첫 화면은 같은 트랙이다(2026-09-26) — 어긋나면 여기가 운다.
    expect(screen.getByRole("button", { name: "Platform" }).getAttribute("aria-current")).toBe("page");
    await screen.findByRole("complementary", { name: "상권 정체성" }, TAB_LOAD);
  });

  it("Platform·Posting·Program 도 같은 지도 위 패널로 뜬다 — 탭을 옮겨도 지도는 하나다", async () => {
    mount(true);
    // 첫 화면이 Platform 이라(2026-09-26) Page 는 눌러서 연다 — 지도 한 개를 넷이 쓰는지 보는 테스트다.
    fireEvent.click(screen.getByRole("button", { name: "Page" }));
    await screen.findByRole("button", { name: "검토 건물 후보 저장" }, TAB_LOAD);
    const map = naver.map();
    expect(map).not.toBeNull();
    for (const [tab, panel] of [["Platform", "상권 정체성"], ["Posting", "입점 계산"], ["Program", "검증 program"]] as const) {
      fireEvent.click(screen.getByRole("button", { name: tab }));
      const aside = await screen.findByRole("complementary", { name: panel }, TAB_LOAD);
      // 패널은 지도 호스트 **안에** 뜬다 — 지도 없는 대시보드로 되돌아가면 여기가 운다.
      expect(aside.closest(".maphost")).not.toBeNull();
      expect(document.querySelector(".maphost")!.classList.contains("is-hidden")).toBe(false);
      expect(naver.map()).toBe(map);
    }
  });

  it("Posting 에서 상권을 바꾸면 Page 도 같은 상권을 본다", async () => {
    installFetchStub([
      { match: /commercial-districts$/, body: [district("garosugil", { name: "가로수길" }), district("yeonnam", { name: "연남동" })] },
      { match: /heatmap\/buildings\?district=yeonnam/, body: buildings([{ id: "y1", name: "연남 건물", status: "empty" }]) },
      { match: /heatmap\/buildings\?/, body: buildings([{ id: "g1", name: "검토 건물", status: "empty" }]) },
      { match: /postings$/, body: [] },
    ]);
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Posting" }));
    await screen.findByRole("complementary", { name: "입점 계산" }, TAB_LOAD);
    const hub = (await screen.findAllByRole("combobox"))[0] as HTMLSelectElement;
    await waitFor(() => expect(hub.querySelectorAll("option").length).toBeGreaterThan(1));
    fireEvent.change(hub, { target: { value: "yeonnam" } });
    fireEvent.click(screen.getByRole("button", { name: "Page" }));
    expect(await screen.findByText("연남 건물", {}, TAB_LOAD)).toBeTruthy();
    expect((screen.getByRole("combobox", { name: "상권 선택" }) as HTMLSelectElement).value).toBe("yeonnam");
  });
});

/** 화면설계서 2판 인계 표 — PL-05(Platform → Page) · PS-06 · PR-07(Posting → Program). */
describe("App — 트랙 간 인계 (화면설계서 2판)", MULTI_TAB, () => {
  it("PL-05 Platform 자리 카드의 「Page에서 이 건물 보기 →」가 Page 에서 그 건물 상세를 연다", async () => {
    installFetchStub([
      { match: /commercial-districts$/, body: [district("garosugil", { name: "가로수길" })] },
      { match: /heatmap\/buildings\?/, body: buildings([{ id: "g0", name: "다른 건물", status: "full" }, { id: "g1", name: "검토 건물", status: "empty" }]) },
      { match: /garosugil\/platform$/, body: {
        district_id: "garosugil",
        identity: null,
        openings: {
          // 테스트 전용 자리. unit_id 규약 vu-{건물 id} 로 Page 건물 g1 을 가리킨다.
          sites: [{ unit_id: "vu-g1", name: "검토 건물 자리", lat: 37.5202, lng: 127.0202, area_py: 30, floor: "1F",
            capacity: 2, vacancy_rate: 100, was: "카페", recommendations: [], matched_distance_m: null, distinct: null }],
          unit_count: 1, matched_count: 0, match_radius_m: 400, source: "테스트 fixture",
        },
      } },
    ]);
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Platform" }));
    const title = await screen.findByText("어느 자리에 어떤 업소가 들어오면 좋나", {}, TAB_LOAD);
    fireEvent.click(title.closest("summary")!);
    fireEvent.click(screen.getByRole("button", { name: "검토 건물 자리 Page에서 이 건물 보기" }));

    expect(await screen.findByRole("button", { name: "이 건물로 입점 검토 →" }, TAB_LOAD)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Page" }).getAttribute("aria-current")).toBe("page");
    expect(document.querySelector(".b-detail .b-name")!.textContent).toBe("검토 건물");
  });

  it("PS-06 · PR-07 「이 자리로 검증 program 만들기 →」가 Program 의 거점·업종·주소와 검증할 자리를 채우고, 비우기로 걷힌다", async () => {
    const api = mount(true);
    fireEvent.click(screen.getByRole("button", { name: "Posting" }));
    await screen.findByRole("complementary", { name: "입점 계산" }, TAB_LOAD);
    await waitFor(() => expect(api.count(/simulate-revenue$/)).toBe(1));
    fireEvent.click(await screen.findByRole("button", { name: "이 자리로 검증 program 만들기 →" }));

    const title = await screen.findByText("검증할 자리", { selector: "b" }, TAB_LOAD);
    const banner = title.closest(".arrival")!;
    expect(banner.textContent).toContain("garosugil 1번 자리");
    expect(banner.textContent).toContain("Posting 가성비 전략");
    expect((screen.getByPlaceholderText("예: 카페") as HTMLInputElement).value).toBe("카페");
    expect((screen.getByPlaceholderText("예: 서울 강남구 신사동 …") as HTMLInputElement).value).toBe("garosugil 1번 자리");
    const hub = document.querySelector(".progstudio form select") as HTMLSelectElement;
    await waitFor(() => expect(hub.value).toBe("garosugil"));
    // 지도에 검증할 자리 핀이 선다.
    await waitFor(() => expect(naver.live().some((o) => String((o.options.icon as { content?: string })?.content ?? "").includes("검증할 자리"))).toBe(true));

    fireEvent.click(screen.getByRole("button", { name: "비우기" }));
    expect(screen.queryByText("검증할 자리", { selector: "b" })).toBeNull();
    // 탭을 다녀와도 걷은 안내가 되살아나지 않는다.
    fireEvent.click(screen.getByRole("button", { name: "Posting" }));
    await screen.findByRole("complementary", { name: "입점 계산" }, TAB_LOAD);
    fireEvent.click(screen.getByRole("button", { name: "Program" }));
    await screen.findByRole("complementary", { name: "검증 program" }, TAB_LOAD);
    expect(screen.queryByText("검증할 자리", { selector: "b" })).toBeNull();
  });
});

describe("App — Page에서 입점 검토", () => {
  it("검증된 건물 유닛을 인계하고 Page 후보·검색·단일 지도를 보존한다", async () => {
    const api = mount(true);
    fireEvent.click(screen.getByRole("button", { name: "Page" }));
    fireEvent.click(await screen.findByRole("button", { name: "검토 건물 후보 저장" }, FIRST_LOAD));
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
    fireEvent.click(await screen.findByRole("button", { name: /^검토 건물 카페/ }, FIRST_LOAD));
    fireEvent.click(screen.getByRole("button", { name: "이 건물로 입점 검토 →" }));
    expect(await screen.findByText(/일치하는 입점 계산 유닛이 없습니다/)).toBeTruthy();
    expect(api.count(/simulate-revenue$/)).toBe(0);
    expect((screen.getByRole("button", { name: "시뮬레이션" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getAllByRole("combobox")[1] as HTMLSelectElement).value).toBe("");
  });
});

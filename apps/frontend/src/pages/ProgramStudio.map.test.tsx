/**
 * ProgramStudio 지도 쪽 — 화면설계서 2판 PR-01(종료 행사 제외) · PR-02(칩 ↔ 목록 같은 선택).
 * 지도가 있어야 행사를 부르므로 실제 MapHost 안에서 렌더한다(SDK 로더만 목킹).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import ProgramStudio, { eventRange, splitEvents } from "@/pages/ProgramStudio";
import type { MarketingEvent } from "@/lib/api";
import { installFetchStub, type FetchStub } from "@/test/fetchStub";
import { installNaverStub, removeNaverStub, type NaverStub } from "@/test/naverStub";
import { renderOnMap } from "@/test/renderMap";
import { district } from "@/test/fixtures";

vi.mock("@/lib/naverMap", () => ({ loadNaverMaps: () => Promise.resolve(), describeNaverMapError: String }));

// 테스트 전용 행사. 종료 여부가 오늘 날짜에 흔들리지 않게 과거는 2020년, 앞으로는 2099년으로 둔다.
function ev(id: string, n: string, when: string, over: Partial<MarketingEvent> = {}): MarketingEvent {
  return { id, n, when, lat: 37.52, lng: 127.02, ic: "", place: `${n} 장소`, org: "테스트 주최", fee: "무료", target: "누구나", link: "https://example.com/e", ...over };
}
const EVENTS = [
  ev("old", "지난 행사", "2020-05-18~2020-08-14"),
  ev("late", "늦은 행사", "2099-10-02~2099-10-02", { lat: 37.521, lng: 127.021 }),
  ev("soon", "가까운 행사", "2099-09-20~2099-09-27", { lat: 37.522, lng: 127.022 }),
];

let naver: NaverStub;
let api: FetchStub;
beforeEach(() => { naver = installNaverStub(); });
afterEach(() => { cleanup(); removeNaverStub(); });

function mount(source = "seoul-open-data", events = EVENTS) {
  api = installFetchStub([
    { match: /\/commercial-districts$/, body: [district("garosugil", { name: "가로수길" })] },
    { match: /\/marketing\/events\?district_id=garosugil$/, body: { district_id: "garosugil", events, events_source: source } },
  ]);
  return renderOnMap(<ProgramStudio mapDistrictId="garosugil" />);
}

const eventChips = () => naver.live().filter((o) => o.kind === "Marker"
  && String((o.options.icon as { content?: string })?.content ?? "").includes("행사"));

describe("splitEvents · eventRange", () => {
  it("종료일이 오늘보다 앞선 행사만 빼고 시작일 순으로 둔다 — 날짜를 모르면 거르지 않는다", () => {
    const odd = ev("odd", "날짜 모름", "프로그램별 상이");
    const { upcoming, ended } = splitEvents([...EVENTS, odd], "2026-09-13");
    expect(ended).toBe(1);
    expect(upcoming.map((e) => e.id)).toEqual(["soon", "late", "odd"]);
    expect(eventRange("2099-10-02")).toEqual({ start: "2099-10-02", end: "2099-10-02" });
    expect(eventRange("미정")).toBeNull();
  });
});

describe("ProgramStudio — 오프라인 홍보 장소", () => {
  it("PR-01 지도 칩과 목록이 같은 수이고, 종료된 행사는 둘 다에서 빠진다", async () => {
    mount();
    // 파일 첫 테스트는 모듈 변환·지도 로더를 같이 탄다 — 전체 병렬 실행에서 1초 기본값을 넘겼다(09-13).
    const section = await screen.findByRole("region", { name: "오프라인 홍보 장소" }, { timeout: 10000 });
    expect(within(section).getByText("오프라인 홍보 장소 · 2곳")).toBeTruthy();
    expect(within(section).getByText("종료된 행사 1곳은 뺐다")).toBeTruthy();
    expect(within(section).queryByText(/지난 행사/)).toBeNull();
    await waitFor(() => expect(eventChips()).toHaveLength(2));
    // 행사는 LLM 없는 경로로만 부른다.
    expect(api.count(/\/marketing\/garosugil$/)).toBe(0);
  });

  it("PR-02 칩을 누르면 목록에서 선택·상세가 뜨고, 목록을 누르면 지도가 그 행사로 간다", async () => {
    mount();
    await screen.findByRole("region", { name: "오프라인 홍보 장소" }, { timeout: 10000 });
    await waitFor(() => expect(eventChips()).toHaveLength(2));
    const soonChip = eventChips().find((o) => String((o.options.icon as { content: string }).content).includes("가까운 행사"))!;
    naver.emit(soonChip, "click");

    expect(await screen.findByLabelText("가까운 행사 상세")).toBeTruthy();
    expect(screen.getByRole("button", { name: /가까운 행사/ }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("link", { name: "행사 페이지 열기 ↗" }).getAttribute("rel")).toContain("noopener");

    const moves = naver.map()!.moves.length;
    fireEvent.click(screen.getByRole("button", { name: /늦은 행사/ }));
    expect(await screen.findByLabelText("늦은 행사 상세")).toBeTruthy();
    expect(naver.map()!.moves.length).toBeGreaterThan(moves);
    const lastMove = naver.map()!.moves[naver.map()!.moves.length - 1];
    expect(lastMove.kind).toBe("panTo");
  });

  it("실데이터가 0곳이면 예시로 채우지 않는다고 말한다", async () => {
    mount("seoul-open-data", []);
    expect(await screen.findByText("이 상권에 예정된 공공 문화행사가 없다 — 예시로 채우지 않는다.")).toBeTruthy();
  });

  it("지도가 없으면(단독 렌더) 행사를 부르지도 그리지도 않는다", async () => {
    // MapHost 밖 = useMapHost() 기본값(map null).
    api = installFetchStub([{ match: /\/commercial-districts$/, body: [] }]);
    render(<ProgramStudio mapDistrictId="garosugil" />);
    await waitFor(() => expect(api.count(/commercial-districts$/)).toBe(1));
    expect(api.count(/marketing\/events/)).toBe(0);
    expect(screen.queryByRole("region", { name: "오프라인 홍보 장소" })).toBeNull();
  });
});

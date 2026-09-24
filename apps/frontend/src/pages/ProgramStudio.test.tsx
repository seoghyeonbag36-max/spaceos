/** 검증 브리프 입력·판정표·채널 초안의 편집·출처 보존·폐기를 검증한다. 모든 생성 응답은 테스트 픽스처다.
 *
 * 2026-09-17 대상 재정의로 사라진 스위트: 상용 온보딩(점주 동의 4개·영수증)과 가게 조회
 * 응답 차단(상호 검색·블로그 스니펫). 특정할 영업 중인 가게도, 받을 점주 원문도 없다. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import ProgramStudio from "@/pages/ProgramStudio";
import type { ProgramPlan } from "@/lib/api";
import type { ProgramHandoff } from "@/lib/workspaceState";
import { installFetchStub, type Route } from "@/test/fetchStub";

const PLAN: ProgramPlan = {
  item: "테스트 원두 팝업", category: "카페", mode: "popup", stage: "pre_founder",
  source: "llm", ha_check: "브리프와 상권 수치만 참고했습니다.",
  ha_findings: [{ severity: "warning", code: "superlative", message: "최상급 표현을 확인하세요.", evidence: "최고" }],
  online: [
    { channel: "인스타그램", kind: "online", content: "팝업 준비 과정을 소개합니다.\n일정을 고정해 두세요.", rationale: "검증 기간이 짧아 사전 인지가 필요합니다.",
      target: "20~30대 직장인", budget_share: 60, kpi: "저장 수" },
    { channel: "블로그", kind: "online", content: "팝업 일정 안내 글을 준비하세요.", rationale: "지도 검색 동선을 엽니다.",
      target: "지역 검색 유입", budget_share: 40, kpi: "검색 클릭" },
  ],
  offline: [
    { channel: "단기 임대 협의", kind: "offline", content: "건물주에게 단기 사용을 제안하세요.", rationale: "공실을 빌리려면 소유자 동의가 먼저입니다.",
      timing: "검증 기간", actors: ["건물주"], mode: "propose" },
  ],
  signals: [
    { name: "일 방문객 수", method: "입장 카운터 일별 기록", target: "일 60명", decision: "누적 목표의 70% 미만이면 기각" },
  ],
};

let writeText: ReturnType<typeof vi.fn>;

beforeEach(() => {
  writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
});

function mount(options: {
  result?: ProgramPlan | Promise<ProgramPlan>; status?: number; routes?: Route[];
  props?: Parameters<typeof ProgramStudio>[0];
} = {}) {
  const result = options.result ?? structuredClone(PLAN);
  const api = installFetchStub([
    ...(options.routes ?? []),
    { match: /\/commercial-districts$/, body: [] },
    { match: /\/marketing\/generate$/, status: options.status, body: () => result },
  ]);
  render(<ProgramStudio {...options.props} />);
  return api;
}

const submitButton = () => screen.getByRole("button", { name: "검증 program 생성" }) as HTMLButtonElement;

function generate() {
  fireEvent.click(screen.getByRole("button", { name: "예시 채우기" }));
  fireEvent.click(submitButton());
}

async function generateAndFlush() {
  // 예시 입력 렌더를 먼저 끝낸 뒤 생성 클릭의 비동기 응답을 비운다.
  generate();
  await act(async () => {});
}

async function editor() {
  return screen.findByRole("textbox", { name: "초안 본문" }) as Promise<HTMLTextAreaElement>;
}

function deferred<T = ProgramPlan>() {
  let resolve!: (result: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("ProgramStudio — 검증 브리프", () => {
  // ⚠ 파일 첫 테스트라 모듈 변환 비용을 혼자 진다. 전체 병렬에서 5초 기본 한도를 넘긴 적이 있어
  //   (2026-09-13) 동작 판정이 아니라 대기 한도만 늘린다.
  it("아이템·업종·검증 방식·단계와 조건을 브리프 계약 그대로 보낸다", { timeout: 20000 }, async () => {
    const api = mount();
    fireEvent.change(screen.getByPlaceholderText("예: 산미 중심 원두 팝업"), { target: { value: "제철 과일 디저트" } });
    fireEvent.change(screen.getByPlaceholderText("예: 카페"), { target: { value: "디저트" } });
    fireEvent.click(screen.getByRole("radio", { name: "가오픈" }));
    fireEvent.click(screen.getByRole("radio", { name: /기창업자/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "검증 가설" }), { target: { value: "평일 저녁 수요가 있다" } });
    fireEvent.change(screen.getByRole("textbox", { name: "검증 기간(일)" }), { target: { value: "14" } });
    fireEvent.change(screen.getByRole("textbox", { name: "예산 하한(원)" }), { target: { value: "300,000" } });
    fireEvent.change(screen.getByRole("textbox", { name: "예산 상한(원)" }), { target: { value: "700000" } });
    fireEvent.change(screen.getByRole("textbox", { name: "차별점" }), { target: { value: "제철 과일만\n\n당일 생산" } });
    fireEvent.click(submitButton());
    await editor();
    expect(api.matching(/\/marketing\/generate$/)[0].body).toEqual({
      item: "제철 과일 디저트", category: "디저트", mode: "soft_open", stage: "founder",
      hypothesis: "평일 저녁 수요가 있다", run_days: 14,
      budget_krw_min: 300000, budget_krw_max: 700000, differentiators: ["제철 과일만", "당일 생산"],
    });
  });

  it("예산을 한쪽만 넣으면 이유를 말하고 생성하지 않는다", async () => {
    const api = mount();
    fireEvent.click(screen.getByRole("button", { name: "예시 채우기" }));
    fireEvent.change(screen.getByRole("textbox", { name: "예산 상한(원)" }), { target: { value: "" } });
    expect(screen.getByText(/하한·상한을 함께 넣거나 둘 다 비운다/)).toBeTruthy();
    expect(submitButton().disabled).toBe(true);
    fireEvent.click(submitButton());
    expect(api.count(/\/marketing\/generate$/)).toBe(0);
  });

  it("아이템이나 업종이 비면 생성 버튼이 꺼져 있다", () => {
    mount();
    expect(submitButton().disabled).toBe(true);
    fireEvent.change(screen.getByPlaceholderText("예: 산미 중심 원두 팝업"), { target: { value: "원두" } });
    expect(submitButton().disabled).toBe(true);
    fireEvent.change(screen.getByPlaceholderText("예: 카페"), { target: { value: "카페" } });
    expect(submitButton().disabled).toBe(false);
  });

  it.each([["start", "예비창업자"], ["pivot", "기창업자"], ["move", "기창업자"]] as const)(
    "「내 사업」이 %s 이면 기본 단계는 %s 다", (goal, label) => {
      mount({ props: { businessGoal: goal } });
      expect(screen.getByRole("radio", { name: new RegExp(label) }).getAttribute("aria-checked")).toBe("true");
    });

  it("Posting 에서 넘어온 자리는 같은 거점일 때만 unit_id·tier 로 싣고, 거점을 바꾸면 안내와 함께 걷는다", async () => {
    const handoff: ProgramHandoff = {
      districtId: "garosugil", unitId: "vu-g1", unitName: "가로수길 1번 자리", lat: 37.52, lng: 127.02,
      area: 20, floor: "1F", rent: 350, industry: "카페", strategy: "가성비",
    };
    const api = mount({
      props: { handoff },
      routes: [{ match: /\/commercial-districts$/, body: [
        { id: "garosugil", name: "가로수길", gu: "강남구", center: [37.52, 127.02] },
        { id: "yeonnam", name: "연남동", gu: "마포구", center: [37.56, 126.92] },
      ] }],
    });
    expect(screen.getByText("검증할 자리", { selector: "b" })).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("예: 산미 중심 원두 팝업"), { target: { value: "원두 팝업" } });
    fireEvent.click(submitButton());
    await editor();
    expect(api.matching(/\/marketing\/generate$/)[0].body).toMatchObject({
      district_id: "garosugil", unit_id: "vu-g1", tier: "가성비", category: "카페", address: "가로수길 1번 자리",
    });

    const hub = document.querySelector(".progstudio form select") as HTMLSelectElement;
    await waitFor(() => expect(hub.querySelectorAll("option").length).toBe(3));
    fireEvent.change(hub, { target: { value: "yeonnam" } });
    expect(screen.queryByText("검증할 자리", { selector: "b" })).toBeNull();
    fireEvent.click(submitButton());
    await editor();
    const second = api.matching(/\/marketing\/generate$/)[1].body as Record<string, unknown>;
    expect(second.district_id).toBe("yeonnam");
    expect(second.unit_id).toBeUndefined();
  });
});

describe("ProgramStudio — 판정표", () => {
  it("검증 지표를 초안보다 먼저 목표선·기각 조건과 함께 보여준다", async () => {
    mount(); generate();
    await editor();
    const table = screen.getByRole("region", { name: "검증 지표" });
    expect(within(table).getByText("일 방문객 수")).toBeTruthy();
    expect(within(table).getByText("일 60명")).toBeTruthy();
    expect(within(table).getByText("누적 목표의 70% 미만이면 기각")).toBeTruthy();
    const drafts = screen.getByRole("region", { name: "채널별 실행 초안" });
    expect(table.compareDocumentPosition(drafts) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("지표가 비면 비었다고 말한다 — 빈 표로 넘어가지 않는다", async () => {
    mount({ result: { ...PLAN, signals: [] } }); generate();
    await editor();
    expect(screen.getByText(/판정이 아니라 지출이다/)).toBeTruthy();
  });

  it("채널의 타겟·예산 비율·협업 주체를 초안 옆에 보여준다", async () => {
    mount(); generate();
    await editor();
    expect(screen.getByText("타겟 20~30대 직장인 · 예산 60% · KPI 저장 수")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "단기 임대 협의 초안" }));
    expect(screen.getByText("시기 검증 기간 · 함께 건물주")).toBeTruthy();
  });
});

describe("ProgramStudio — 채널별 초안", () => {
  it("온라인·오프라인 채널을 선택하고 본문만 편집해 미리 보며 원본으로 되돌린다", async () => {
    const result = structuredClone(PLAN);
    const api = mount({ result });
    const storage = vi.spyOn(Storage.prototype, "setItem");
    generate();
    expect((await editor()).value).toBe(PLAN.online[0].content);
    expect(screen.getByRole("button", { name: "인스타그램 초안" }).getAttribute("aria-pressed")).toBe("true");

    const changed = "수정한 초안\n두 번째 줄 <img src=x onerror=alert(1)>";
    fireEvent.change(await editor(), { target: { value: changed } });
    expect(screen.getByRole("button", { name: "인스타그램 편집됨" })).toBeTruthy();
    expect(screen.getByText(/수정한 본문은 서버 HA 검증을 거치지 않았습니다/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "미리보기" }));
    const preview = screen.getByRole("region", { name: "인스타그램 본문 미리보기" });
    expect(preview.textContent).toContain(changed);
    expect(preview.querySelector("img")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "단기 임대 협의 초안" }));
    expect(screen.getByRole("region", { name: "단기 임대 협의 본문 미리보기" }).textContent).toContain(PLAN.offline[0].content);
    fireEvent.click(screen.getByRole("button", { name: "인스타그램 편집됨" }));
    expect(screen.getByRole("region", { name: "인스타그램 본문 미리보기" }).textContent).toContain(changed);
    fireEvent.click(screen.getByRole("button", { name: "원본 되돌리기" }));
    fireEvent.click(screen.getByRole("button", { name: "편집" }));
    expect((await editor()).value).toBe(PLAN.online[0].content);
    expect((screen.getByRole("button", { name: "원본 되돌리기" }) as HTMLButtonElement).disabled).toBe(true);
    expect(result).toEqual(PLAN);
    expect(api.count(/\/marketing\/generate$/)).toBe(1);
    expect(storage).not.toHaveBeenCalled();
  });

  it("현재 편집 본문을 복사하고 실패를 표시하며 빈 본문은 복사하지 않는다", async () => {
    mount(); generate();
    fireEvent.change(await editor(), { target: { value: "복사할 수정 본문" } });
    fireEvent.click(screen.getByRole("button", { name: "본문 복사" }));
    expect(await screen.findByText("현재 초안 본문을 복사했습니다.")).toBeTruthy();
    expect(writeText).toHaveBeenLastCalledWith("복사할 수정 본문");
    writeText.mockRejectedValueOnce(new Error("클립보드 접근 거절"));
    fireEvent.click(screen.getByRole("button", { name: "본문 복사" }));
    expect((await screen.findByRole("alert")).textContent).toContain("복사하지 못했습니다");
    fireEvent.change(await editor(), { target: { value: "" } });
    expect(screen.queryByRole("alert")).toBeNull();
    expect((screen.getByRole("button", { name: "본문 복사" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "미리보기" }));
    expect(screen.getByText("본문이 비어 있습니다. 편집에서 내용을 입력하세요.")).toBeTruthy();
  });

  it("클립보드 API가 없어도 복사 실패를 안내한다", async () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    mount(); generate(); await editor();
    fireEvent.click(screen.getByRole("button", { name: "본문 복사" }));
    expect((await screen.findByRole("alert")).textContent).toContain("직접 복사하세요");
  });

  it("편집 후에도 생성 출처·원본 근거·HA 경고와 검증 범위를 보존한다", async () => {
    mount(); generate();
    fireEvent.change(await editor(), { target: { value: "근거를 다시 확인할 수정 본문" } });
    expect(screen.getByText("LLM 생성", { selector: ".srcbadge" })).toBeTruthy();
    expect(screen.getByText(PLAN.online[0].rationale, { exact: false })).toBeTruthy();
    expect(screen.getByText(/생성 후 편집한 초안은 이 검증에 포함되지 않는다/)).toBeTruthy();
    const fold = screen.getByText("생성 원본의 Humanistic Authority 검증").closest("details")!;
    fireEvent.click(within(fold).getByText("생성 원본의 Humanistic Authority 검증"));
    expect(within(fold).getByText("최상급 표현을 확인하세요.", { exact: false })).toBeTruthy();
    expect(within(fold).getByText("최고")).toBeTruthy();
    expect(within(fold).getByText(PLAN.ha_check)).toBeTruthy();
  });

  it("HA 폐기 응답은 편집해도 규칙 기반 폴백과 폐기 사유를 유지한다", async () => {
    mount({ result: { ...PLAN, source: "rule-stub", ha_findings: [
      { severity: "violation", code: "unproven_experience_claim", message: "있지도 않은 경험을 근거로 삼습니다.", evidence: "단골 고객" },
    ] } });
    generate();
    fireEvent.change(await editor(), { target: { value: "사용자가 수정한 스텁" } });
    expect(screen.getByText("규칙 기반 폴백", { selector: ".srcbadge" })).toBeTruthy();
    expect(screen.getByText(/LLM 생성물이 HA 검증에 걸려 폐기됐고/)).toBeTruthy();
    expect(screen.getByText("있지도 않은 경험을 근거로 삼습니다.")).toBeTruthy();
    expect(screen.getByText("단골 고객")).toBeTruthy();
  });

  it("다시 생성하면 편집 초안을 폐기하고 새 원본으로 시작한다", async () => {
    const api = mount(); generate();
    fireEvent.change(await editor(), { target: { value: "이전 편집 본문" } });
    fireEvent.click(submitButton());
    await waitFor(() => expect(api.count(/\/marketing\/generate$/)).toBe(2));
    expect((await editor()).value).toBe(PLAN.online[0].content);
    expect(screen.queryByRole("button", { name: "인스타그램 편집됨" })).toBeNull();
  });

  it("비우기는 기존 편집 초안을 폐기한다", async () => {
    mount(); generate();
    fireEvent.change(await editor(), { target: { value: "폐기할 편집 본문" } });
    fireEvent.click(screen.getByRole("button", { name: "비우기" }));
    expect(screen.queryByRole("textbox", { name: "초안 본문" })).toBeNull();
    expect(screen.queryByText("생성 원본의 Humanistic Authority 검증")).toBeNull();
  });

  it.each(["아이템", "가설", "검증 방식", "비우기", "예시 채우기"])("생성 대기 중 %s 변경 뒤 이전 입력의 응답을 표시하지 않는다", async (field) => {
    const pending = deferred();
    await act(async () => { mount({ result: pending.promise }); });
    await generateAndFlush();
    await screen.findByRole("button", { name: /생성 중/ });
    if (field === "아이템") {
      fireEvent.change(screen.getByPlaceholderText("예: 산미 중심 원두 팝업"), { target: { value: "다른 아이템" } });
    } else if (field === "가설") {
      fireEvent.change(screen.getByRole("textbox", { name: "검증 가설" }), { target: { value: "수정한 가설" } });
    } else if (field === "검증 방식") {
      fireEvent.click(screen.getByRole("radio", { name: "MVP 테스트" }));
    } else fireEvent.click(screen.getByRole("button", { name: field }));
    await act(async () => { pending.resolve(PLAN); await pending.promise; });
    expect(screen.queryByRole("textbox", { name: "초안 본문" })).toBeNull();
    expect(screen.queryByText("생성 원본의 Humanistic Authority 검증")).toBeNull();
  });

  it("생성 실패에 가짜 초안을 만들지 않는다", async () => {
    mount({ status: 503 }); generate();
    expect(await screen.findByText("생성에 실패했습니다.")).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: "초안 본문" })).toBeNull();
  });

  it("온라인·오프라인이 모두 없으면 원본 출처와 빈 상태를 표시한다", async () => {
    mount({ result: { ...PLAN, online: [], offline: [] } }); generate();
    expect(await screen.findByText("생성된 채널안이 없습니다. 입력 근거를 확인해 다시 생성하세요.")).toBeTruthy();
    expect(screen.getByText("LLM 생성", { selector: ".srcbadge" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "본문 복사" })).toBeNull();
  });
});

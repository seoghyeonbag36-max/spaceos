/** 채널 초안의 편집·출처 보존·폐기를 검증한다. 모든 생성 응답은 테스트 픽스처다. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import ProgramStudio from "@/pages/ProgramStudio";
import type { StoreMarketing, StorePlaceLookup, StoreReviewLookup } from "@/lib/api";
import { installFetchStub, type Route } from "@/test/fetchStub";

const MARKETING: StoreMarketing = {
  store_name: "테스트 카페", category: "카페", tone_keywords: ["원두", "드립"],
  source: "llm", ha_check: "제공된 메뉴와 리뷰를 참고했습니다.",
  ha_findings: [{ severity: "warning", code: "superlative", message: "최상급 표현을 확인하세요.", evidence: "최고" }],
  online: [
    { channel: "인스타그램", kind: "online", content: "오늘의 드립을 소개합니다.\n원두 이야기를 나눠요.", rationale: "제공 메뉴의 오늘의 드립을 반영했습니다." },
    { channel: "블로그", kind: "online", content: "원두를 소개하는 글을 준비하세요.", rationale: "제공 리뷰에서 원두 설명이 언급됐습니다." },
  ],
  offline: [
    { channel: "매장 안내문", kind: "offline", content: "오늘의 원두를 안내하세요.", rationale: "점주가 제공한 원두 메뉴를 안내합니다." },
  ],
};

let writeText: ReturnType<typeof vi.fn>;

beforeEach(() => {
  writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
});

function mount(options: { result?: StoreMarketing | Promise<StoreMarketing>; status?: number; routes?: Route[] } = {}) {
  const result = options.result ?? structuredClone(MARKETING);
  const api = installFetchStub([
    ...(options.routes ?? []),
    { match: /\/commercial-districts$/, body: [] },
    { match: /\/marketing\/generate$/, status: options.status, body: () => result },
    { match: /\/marketing\/onboarding\/generate$/, body: {
      onboarding_id: "test-receipt", org_id: "test-org", accepted_at: "2026-09-09T00:00:00Z",
      contract_version: "spaceos.program-onboarding/1", input_source: "merchant-provided",
      raw_input_persisted: false, marketing: result,
    } },
  ]);
  render(<ProgramStudio />);
  return api;
}

function generate() {
  fireEvent.click(screen.getByRole("button", { name: "예시 채우기" }));
  fireEvent.click(screen.getByRole("button", { name: "마케팅 솔루션 생성" }));
}

async function generateAndFlush() {
  // 예시 입력 렌더를 먼저 끝낸 뒤 생성 클릭의 비동기 응답을 비운다.
  generate();
  await act(async () => {});
}

async function editor() {
  return screen.findByRole("textbox", { name: "초안 본문" }) as Promise<HTMLTextAreaElement>;
}

function deferred<T = StoreMarketing>() {
  let resolve!: (result: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("ProgramStudio — 채널별 초안", () => {
  it("온라인·오프라인 채널을 선택하고 본문만 편집해 미리 보며 원본으로 되돌린다", async () => {
    const result = structuredClone(MARKETING);
    const api = mount({ result });
    const storage = vi.spyOn(Storage.prototype, "setItem");
    generate();
    expect((await editor()).value).toBe(MARKETING.online[0].content);
    expect(screen.getByRole("button", { name: "인스타그램 초안" }).getAttribute("aria-pressed")).toBe("true");

    const changed = "수정한 초안\n두 번째 줄 <img src=x onerror=alert(1)>";
    fireEvent.change(await editor(), { target: { value: changed } });
    expect(screen.getByRole("button", { name: "인스타그램 편집됨" })).toBeTruthy();
    expect(screen.getByText(/수정한 본문은 서버 HA 검증을 거치지 않았습니다/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "미리보기" }));
    const preview = screen.getByRole("region", { name: "인스타그램 본문 미리보기" });
    expect(preview.textContent).toContain(changed);
    expect(preview.querySelector("img")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "매장 안내문 초안" }));
    expect(screen.getByRole("region", { name: "매장 안내문 본문 미리보기" }).textContent).toContain(MARKETING.offline[0].content);
    fireEvent.click(screen.getByRole("button", { name: "인스타그램 편집됨" }));
    expect(screen.getByRole("region", { name: "인스타그램 본문 미리보기" }).textContent).toContain(changed);
    fireEvent.click(screen.getByRole("button", { name: "원본 되돌리기" }));
    fireEvent.click(screen.getByRole("button", { name: "편집" }));
    expect((await editor()).value).toBe(MARKETING.online[0].content);
    expect((screen.getByRole("button", { name: "원본 되돌리기" }) as HTMLButtonElement).disabled).toBe(true);
    expect(result).toEqual(MARKETING);
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
    expect(screen.getByText(MARKETING.online[0].rationale, { exact: false })).toBeTruthy();
    expect(screen.getByText(/생성 후 편집한 초안은 이 검증에 포함되지 않는다/)).toBeTruthy();
    const fold = screen.getByText("생성 원본의 Humanistic Authority 검증").closest("details")!;
    fireEvent.click(within(fold).getByText("생성 원본의 Humanistic Authority 검증"));
    expect(within(fold).getByText("최상급 표현을 확인하세요.", { exact: false })).toBeTruthy();
    expect(within(fold).getByText("최고")).toBeTruthy();
    expect(within(fold).getByText(MARKETING.ha_check)).toBeTruthy();
  });

  it("HA 폐기 응답은 편집해도 규칙 기반 폴백과 폐기 사유를 유지한다", async () => {
    mount({ result: { ...MARKETING, source: "rule-stub", ha_findings: [
      { severity: "violation", code: "invented-price", message: "입력에 없는 금액입니다.", evidence: "999원" },
    ] } });
    generate();
    fireEvent.change(await editor(), { target: { value: "사용자가 수정한 스텁" } });
    expect(screen.getByText("규칙 기반 폴백", { selector: ".srcbadge" })).toBeTruthy();
    expect(screen.getByText(/LLM 생성물이 HA 검증에 걸려 폐기됐고/)).toBeTruthy();
    expect(screen.getByText("입력에 없는 금액입니다.")).toBeTruthy();
    expect(screen.getByText("999원")).toBeTruthy();
  });

  it("다시 생성하면 편집 초안을 폐기하고 새 원본으로 시작한다", async () => {
    const api = mount(); generate();
    fireEvent.change(await editor(), { target: { value: "이전 편집 본문" } });
    fireEvent.click(screen.getByRole("button", { name: "마케팅 솔루션 생성" }));
    await waitFor(() => expect(api.count(/\/marketing\/generate$/)).toBe(2));
    expect((await editor()).value).toBe(MARKETING.online[0].content);
    expect(screen.queryByRole("button", { name: "인스타그램 편집됨" })).toBeNull();
  });

  it.each(["비우기", "상용 온보딩"])("%s 동작은 기존 편집 초안을 폐기한다", async (action) => {
    mount(); generate();
    fireEvent.change(await editor(), { target: { value: "폐기할 편집 본문" } });
    fireEvent.click(screen.getByRole("button", { name: action }));
    expect(screen.queryByRole("textbox", { name: "초안 본문" })).toBeNull();
    expect(screen.queryByText("생성 원본의 Humanistic Authority 검증")).toBeNull();
  });

  it.each(["비우기", "상용 온보딩"])("%s 후 늦게 도착한 응답은 초안을 되살리지 않는다", async (action) => {
    const pending = deferred();
    mount({ result: pending.promise }); generate();
    await screen.findByRole("button", { name: /생성 중/ });
    fireEvent.click(screen.getByRole("button", { name: action }));
    await act(async () => { pending.resolve(MARKETING); await pending.promise; });
    expect(screen.queryByRole("textbox", { name: "초안 본문" })).toBeNull();
    expect(screen.queryByText("생성 원본의 Humanistic Authority 검증")).toBeNull();
  });

  it.each(["가게명", "리뷰", "예시 채우기"])("생성 대기 중 %s 변경 뒤 이전 입력의 응답을 표시하지 않는다", async (field) => {
    const pending = deferred();
    await act(async () => { mount({ result: pending.promise }); });
    await generateAndFlush();
    if (field === "가게명") {
      fireEvent.change(screen.getByPlaceholderText("예: 맡기다"), { target: { value: "다른 가게" } });
    } else if (field === "리뷰") {
      fireEvent.change(screen.getByRole("textbox", { name: /직접 입력 리뷰/ }), { target: { value: "수정한 입력 근거" } });
    } else fireEvent.click(screen.getByRole("button", { name: field }));
    await act(async () => { pending.resolve(MARKETING); await pending.promise; });
    expect(screen.queryByRole("textbox", { name: "초안 본문" })).toBeNull();
    expect(screen.queryByText("생성 원본의 Humanistic Authority 검증")).toBeNull();
    expect((screen.getByRole("button", { name: "마케팅 솔루션 생성" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("프로필 입력을 바꾸면 기존 편집 초안과 원본 검증도 함께 비운다", async () => {
    await act(async () => { mount(); });
    await generateAndFlush();
    fireEvent.change(await editor(), { target: { value: "이전 가게에서 편집한 초안" } });
    fireEvent.change(screen.getByPlaceholderText("예: 맡기다"), { target: { value: "새 가게" } });
    expect(screen.queryByRole("textbox", { name: "초안 본문" })).toBeNull();
    expect(screen.queryByText("생성 원본의 Humanistic Authority 검증")).toBeNull();
  });

  it("생성 실패와 채널이 없는 응답에 가짜 초안을 만들지 않는다", async () => {
    mount({ status: 503 }); generate();
    expect(await screen.findByText("생성에 실패했습니다.")).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: "초안 본문" })).toBeNull();
  });

  it("온라인·오프라인이 모두 없으면 원본 출처와 빈 상태를 표시한다", async () => {
    mount({ result: { ...MARKETING, online: [], offline: [] } }); generate();
    expect(await screen.findByText("생성된 채널안이 없습니다. 입력 근거를 확인해 다시 생성하세요.")).toBeTruthy();
    expect(screen.getByText("LLM 생성", { selector: ".srcbadge" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "본문 복사" })).toBeNull();
  });

  it("상용 경로는 네 가지 동의 이후 점주 입력만 보내고 영수증과 원본 출처를 보존한다", async () => {
    const api = mount();
    fireEvent.click(screen.getByRole("button", { name: "상용 온보딩" }));
    fireEvent.change(screen.getByPlaceholderText("점주 확인 상호"), { target: { value: "점주 카페" } });
    fireEvent.change(screen.getByPlaceholderText("예: 카페"), { target: { value: "카페" } });
    fireEvent.change(screen.getByRole("textbox", { name: /점주 제공 리뷰/ }), { target: { value: "점주가 제공한 원문" } });
    fireEvent.change(screen.getByPlaceholderText("sk_placeos_…"), { target: { value: "sk_placeos_test" } });
    const submit = screen.getByRole("button", { name: "동의하고 상용 생성" }) as HTMLButtonElement;
    const consents = screen.getAllByRole("checkbox");
    expect(consents).toHaveLength(4);
    for (const consent of consents) {
      expect(submit.disabled).toBe(true);
      fireEvent.click(consent);
    }
    expect(submit.disabled).toBe(false);
    fireEvent.click(submit); await editor();
    expect(api.matching(/\/marketing\/onboarding\/generate$/)[0].body).toMatchObject({
      profile: { name: "점주 카페", reviews: ["점주가 제공한 원문"] },
      consent: { consent_to_process: true, rights_confirmed: true, allow_external_model_processing: true,
        data_origin: "merchant-provided", raw_input_retention: "request-only" },
    });
    expect(api.count(/\/marketing\/generate$/)).toBe(0);
    fireEvent.change(await editor(), { target: { value: "점주가 수정한 초안" } });
    expect(screen.getByText("test-receipt")).toBeTruthy();
    expect(screen.getByText("점주 제공 원문(B2B 온보딩 동의)")).toBeTruthy();
    expect(screen.getByText("LLM 생성", { selector: ".srcbadge" })).toBeTruthy();
  });
});

// 조회 응답도 테스트 전용 픽스처다. 실제 점포·리뷰를 외부에 조회하지 않는다.
const PLACES: StorePlaceLookup = {
  query: "테스트 검색", source: "kakao-local", note: null,
  places: [{ name: "이전 후보 카페", category: "카페", address: "테스트 주소", road_address: null,
    phone: null, lat: null, lng: null, place_url: null, distance_m: null }],
};
const REVIEWS: StoreReviewLookup = {
  query: "이전 후보 카페", source: "naver-blog", note: null, reviews: ["이전 가게의 공개 리뷰 픽스처"],
};

describe("ProgramStudio — 이전 가게 조회 응답 차단", () => {
  it("상호 변경 후 새 검색이 끝나면 늦게 온 이전 후보가 덮어쓰지 않는다", async () => {
    const oldSearch = deferred<StorePlaceLookup>();
    let count = 0;
    const next = { ...PLACES, places: [{ ...PLACES.places[0], name: "새 후보 카페" }] };
    await act(async () => { mount({ routes: [
      { match: /\/marketing\/places\?/, body: () => ++count === 1 ? oldSearch.promise : next },
    ] }); });
    fireEvent.change(screen.getByPlaceholderText("예: 맡기다"), { target: { value: "이전 상호" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "검색" })); });
    fireEvent.change(screen.getByPlaceholderText("예: 맡기다"), { target: { value: "새 상호" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "검색" })); });
    expect(screen.getByRole("button", { name: /새 후보 카페/ })).toBeTruthy();
    await act(async () => { oldSearch.resolve(PLACES); await oldSearch.promise; });
    expect(screen.getByRole("button", { name: /새 후보 카페/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /이전 후보 카페/ })).toBeNull();
  });

  it.each(["비우기", "상용 온보딩", "예시 채우기", "상호 변경"])("리뷰 조회 중 %s 이후 이전 스니펫을 합치지 않는다", async (action) => {
    const oldReviews = deferred<StoreReviewLookup>();
    await act(async () => { mount({ routes: [
      { match: /\/marketing\/places\?/, body: PLACES },
      { match: /\/marketing\/reviews\?/, body: () => oldReviews.promise },
    ] }); });
    fireEvent.change(screen.getByPlaceholderText("예: 맡기다"), { target: { value: "검색할 가게" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "검색" })); });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /이전 후보 카페/ })); });
    if (action === "상호 변경") {
      fireEvent.change(screen.getByPlaceholderText("예: 맡기다"), { target: { value: "새 가게" } });
    } else fireEvent.click(screen.getByRole("button", { name: action }));
    await act(async () => { oldReviews.resolve(REVIEWS); await oldReviews.promise; });
    expect(screen.queryByText("공개 검색 스니펫 1건")).toBeNull();
    expect(screen.queryByText(/1건 주입/)).toBeNull();
    expect(screen.queryByRole("textbox", { name: "초안 본문" })).toBeNull();
  });

  it("후보 선택은 기존 생성 결과를 비우고 공개 리뷰만 분리해 합친다", async () => {
    let api!: ReturnType<typeof mount>;
    await act(async () => { api = mount({ routes: [
      { match: /\/marketing\/places\?/, body: PLACES },
      { match: /\/marketing\/reviews\?/, body: REVIEWS },
    ] }); });
    await generateAndFlush();
    expect(await editor()).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "검색" })); });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /이전 후보 카페/ })); });
    expect(screen.queryByRole("textbox", { name: "초안 본문" })).toBeNull();
    expect(screen.getByText("공개 검색 스니펫 1건")).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "마케팅 솔루션 생성" })); });
    expect(api.matching(/\/marketing\/generate$/).slice(-1)[0].body).toMatchObject({
      name: PLACES.places[0].name, reviews: expect.arrayContaining(REVIEWS.reviews),
    });
    // 다른 가게로 바꾸면 이미 들어온 공개 스니펫도 다음 생성에 재사용하지 않는다.
    fireEvent.change(screen.getByPlaceholderText("예: 맡기다"), { target: { value: "또 다른 가게" } });
    expect(screen.queryByText("공개 검색 스니펫 1건")).toBeNull();
  });
});

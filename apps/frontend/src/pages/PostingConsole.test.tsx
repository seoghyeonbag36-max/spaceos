/**
 * PostingConsole(「Posting」 탭) 회귀 그물 — 지도가 없는 탭의 API 배선을 본다.
 *
 * 이 화면은 네 단계가 사슬로 이어진다: 거점 목록 → 그 거점의 실측 공실 자리 →
 * 고른 자리의 GNN 업종 추천 → 시뮬레이션. 한 고리만 끊겨도 화면은 "자리를 고르면
 * 계산한다" 를 띄운 채 조용히 멈추므로, **부른 경로와 순서**를 여기서 못 박는다.
 *
 * 보는 것 셋:
 *   1. 거점을 바꾸면 이전 거점의 자리·결과가 남지 않는가
 *   2. 마운트가 부르는 API 경로가 기대와 맞는가
 *   3. 자리가 없을 때 / 있을 때 각각 무엇을 그리는가
 */
import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import PostingConsole from "@/pages/PostingConsole";
import { installFetchStub, type FetchStub } from "@/test/fetchStub";
import { district, postings, simulateResult } from "@/test/fixtures";

const HUBS = [
  district("garosugil", { name: "가로수길" }),
  district("yeonnam", { name: "연남동", gu: "마포구" }),
  // 실측 공실 인벤토리가 아직 없는 거점 — /postings 가 빈 배열로 온다.
  district("banpo", { name: "반포", gu: "서초구" }),
];

let api: FetchStub;

function mount() {
  api = installFetchStub([
    { match: /\/api\/v1\/commercial-districts$/, body: HUBS },
    { match: /\/api\/v1\/commercial-districts\/garosugil\/postings$/, body: postings("garosugil", 2) },
    { match: /\/api\/v1\/commercial-districts\/yeonnam\/postings$/, body: postings("yeonnam", 1) },
    { match: /\/api\/v1\/commercial-districts\/banpo\/postings$/, body: [] },
    {
      match: /\/api\/v1\/ai\/simulate-revenue$/,
      body: (_m: RegExpExecArray) => simulateResult("garosugil", "garosugil-u1"),
    },
    // GNN 추천은 400m 안에 노드가 없으면 404 다 — 여기서는 그 정상 상태를 쓴다.
  ]);
  return render(<PostingConsole />);
}

beforeEach(() => { mount(); });

const hubSelect = () => screen.getAllByRole("combobox")[0] as HTMLSelectElement;
const unitSelect = () => screen.getAllByRole("combobox")[1] as HTMLSelectElement;
/** 결과 쪽 3-Tier 카드 영역. "가성비" 같은 라벨은 입력 폼(전략 select)에도 있어 좁혀 본다. */
const tierPanel = () => document.querySelector(".tiers") as HTMLElement;

describe("PostingConsole — API 경로", () => {
  it("마운트하면 목록 → 그 거점의 실측 자리 → 시뮬레이션 순으로 부른다", async () => {
    await waitFor(() => expect(api.count(/\/ai\/simulate-revenue$/)).toBe(1));

    expect(api.urls().slice(0, 2)).toEqual([
      "GET /api/v1/commercial-districts",
      "GET /api/v1/commercial-districts/garosugil/postings",
    ]);
    // 자리가 잡히면 **입력 없이** 한 번 돌려 빈 화면을 만들지 않는다.
    // 이때 권리금(prem)은 보내지 않는다 — 안 보낸 것과 0 을 보낸 것은 다른 정보다.
    const sim = api.matching(/\/ai\/simulate-revenue$/)[0];
    expect(sim.method).toBe("POST");
    expect(sim.body).toMatchObject({ district_id: "garosugil", unit_id: "garosugil-u1" });
    expect((sim.body as Record<string, unknown>).prem).toBeUndefined();
  });

  it("자리를 고르면 그 자리 좌표로 GNN 업종 추천을 묻는다", async () => {
    await waitFor(() => expect(api.count(/\/ai\/recommend-industry$/)).toBe(1));

    const rec = api.matching(/\/ai\/recommend-industry$/)[0];
    expect(rec.method).toBe("POST");
    expect(rec.body).toMatchObject({ district_id: "garosugil" });
    // 그래프 노드는 건물 대장 키와 join 되지 않는다 → **좌표**로 묻는다.
    expect(rec.body).toHaveProperty("lat");
    expect(rec.body).toHaveProperty("lon");
  });
});

describe("PostingConsole — 거점 전환", () => {
  it("거점을 바꾸면 새 거점의 자리를 부르고 이전 거점의 자리가 남지 않는다", async () => {
    await waitFor(() => expect(api.count(/garosugil\/postings$/)).toBe(1));
    expect(within(unitSelect()).getByText(/garosugil 1번 자리/)).toBeTruthy();

    fireEvent.change(hubSelect(), { target: { value: "yeonnam" } });

    await waitFor(() => expect(api.count(/yeonnam\/postings$/)).toBe(1));
    await waitFor(() =>
      expect(within(unitSelect()).getByText(/yeonnam 1번 자리/)).toBeTruthy());
    // 이전 거점의 자리가 목록에 남으면 다른 상권의 임대료로 계산하게 된다.
    expect(within(unitSelect()).queryByText(/garosugil/)).toBeNull();
    // 거점 목록은 전환마다 다시 부르지 않는다.
    expect(api.count(/commercial-districts$/)).toBe(1);
  });
});

describe("PostingConsole — 결과 패널", () => {
  it("자리가 있으면 세 전략과 입력 출처 배지를 그린다", async () => {
    await waitFor(() => expect(tierPanel()).not.toBeNull());
    const tiers = within(tierPanel());
    expect(tiers.getByText("고급화")).toBeTruthy();
    expect(tiers.getByText("가성비")).toBeTruthy();
    expect(tiers.getByText("기능중심")).toBeTruthy();
    // 순익이 양수라 회수기간이 정의된다 — "모른다"와 "안 된다"를 뭉개지 않는다.
    expect(tiers.getAllByText("14개월").length).toBe(3);
    // 권리금을 안 넣었으면 0 은 관측이 아니라 **전제**다 — 화면이 그 사실을 밝힌다.
    expect(screen.getByText("전제(0)")).toBeTruthy();
    expect(screen.getByText("R-ONE 실측")).toBeTruthy();
    expect(screen.getByText("내부 3-Tier 폴백")).toBeTruthy();
  });

  it("실측 자리가 0곳인 거점은 계산하지 않고 안내만 남긴다", async () => {
    await waitFor(() => expect(api.count(/garosugil\/postings$/)).toBe(1));
    api.clear();

    fireEvent.change(hubSelect(), { target: { value: "banpo" } });

    await waitFor(() => expect(api.count(/banpo\/postings$/)).toBe(1));
    await waitFor(() => expect(screen.getByText("자리를 고르면 계산한다.")).toBeTruthy());
    expect(tierPanel()).toBeNull();
    expect(unitSelect().disabled).toBe(true);
    expect(screen.getByText(/실측 0곳/)).toBeTruthy();
    // 자리가 없으면 시뮬레이션을 부르지 않는다 — 부르면 없는 자리로 값을 만들어 낸다.
    expect(api.count(/\/ai\/simulate-revenue$/)).toBe(0);
  });
});

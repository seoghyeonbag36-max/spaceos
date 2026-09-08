/**
 * vitest 전역 셋업 — 모든 테스트 파일보다 먼저 한 번 돈다.
 *
 * 여기서 하는 일은 셋뿐이다.
 *  1. 각 테스트 뒤 DOM 정리(RTL 자동 cleanup 은 `globals: true` 일 때만 걸린다.
 *     이 저장소는 `describe`·`it` 을 명시 import 하므로 직접 건다).
 *  2. jsdom 에 없는 브라우저 API 를 최소한만 채운다 — `matchMedia` 는 HubExplorer 가
 *     좁은 화면 판정에 쓰고, 없으면 렌더 자체가 죽는다.
 *  3. 실제 네트워크 차단. 개별 테스트가 `installFetchStub()` 으로 갈아끼우기 전까지는
 *     fetch 를 부르는 순간 **테스트가 실패한다** — 목킹을 깜빡한 채 초록을 보는 것이
 *     이 그물이 막아야 할 첫 번째 거짓말이다.
 */
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

/** jsdom 은 matchMedia 를 구현하지 않는다. 항상 "넓은 화면"으로 답한다. */
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

beforeEach(() => {
  // 목킹하지 않은 fetch 는 통과시키지 않는다(실호출·행 방지).
  vi.stubGlobal("fetch", () => {
    throw new Error("테스트가 실제 fetch 를 불렀다 — installFetchStub() 을 빠뜨렸다");
  });
  window.location.hash = "";
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

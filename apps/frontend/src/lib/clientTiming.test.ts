/**
 * 화면 구간 계측 잠금 — 계측이 화면을 해치지 않고, 표본을 오염시키지 않는다.
 *
 * KPI② 는 2026-09-16 이전에 재는 코드가 0줄이라 '선언만' 이었다. 여기서 잠그는 것은
 * 숫자가 아니라 성질이다: 던지지 않는다 · 기다리지 않는다 · 한 번만 보낸다.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { _resetTiming, endTiming, startTiming } from "@/lib/clientTiming";

describe("clientTiming", () => {
  beforeEach(() => {
    _resetTiming();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(null, { status: 204 }))));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("구간을 재서 한 건 보낸다", () => {
    startTiming("map_ready");
    endTiming("map_ready");
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe("/api/v1/metrics/client");
    const body = JSON.parse(init.body);
    expect(body.metric).toBe("map_ready");
    expect(body.ms).toBeGreaterThanOrEqual(0);
    // keepalive 가 없으면 탭을 닫는 순간 비콘이 날아간다.
    expect(init.keepalive).toBe(true);
  });

  it("같은 이름은 한 번만 보낸다 — 리렌더마다 쌓이면 표본이 오염된다", () => {
    startTiming("map_ready");
    endTiming("map_ready");
    startTiming("map_ready");
    endTiming("map_ready");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("시작 없이 끝내면 아무것도 안 보낸다", () => {
    endTiming("building_detail");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("비콘이 거부돼도 던지지 않는다 — 계측 실패가 화면을 깨지 않는다", () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("blocked"))));
    startTiming("map_ready");
    expect(() => endTiming("map_ready")).not.toThrow();
  });

  it("fetch 자체가 없어도 던지지 않는다", () => {
    vi.stubGlobal("fetch", undefined);
    startTiming("map_ready");
    expect(() => endTiming("map_ready")).not.toThrow();
  });

  it("Performance API 가 없으면 조용히 물러난다", () => {
    vi.stubGlobal("performance", undefined);
    startTiming("map_ready");
    endTiming("map_ready");
    expect(fetch).not.toHaveBeenCalled();
  });
});

/**
 * fetch 스텁 — 테스트는 **실제 백엔드를 부르지 않는다**.
 *
 * 이 그물이 지켜야 하는 성질 중 하나가 "각 탭이 마운트될 때 부르는 API 경로가 기대와
 * 맞는가" 다. 그래서 스텁은 응답만 주는 것이 아니라 **부른 경로를 순서대로 기록**한다.
 * 화면이 경로를 잘못 만들면(질의 파라미터 이름이 바뀌거나, 거점 전환에 재요청이 빠지거나,
 * 보고 있지도 않은 레이어를 미리 부르거나) 그 자리가 그대로 실패로 뜬다.
 *
 * 라우트에 안 걸린 경로는 **404** 로 답한다. 지우지 말 것 — 화면들이 404 를 정상 상태로
 * 다루는 곳이 많고(폴백·"실측 없음"), 그 분기도 테스트 대상이다.
 */
import { vi } from "vitest";

export interface ApiCall {
  method: string;
  /** `/api/v1/...` 전체 경로(질의 문자열 포함) */
  url: string;
  /** POST 본문(JSON 파싱). GET 이면 undefined */
  body: unknown;
}

export interface Route {
  /** 경로 매칭 — 질의 문자열까지 포함해 검사한다 */
  match: RegExp;
  /** 기본 200. 404 를 주면 화면의 폴백 분기를 태울 수 있다 */
  status?: number;
  /** 응답 본문. 함수면 매칭 결과를 받아 만든다(거점 id 별 응답 등) */
  body?: unknown | ((m: RegExpExecArray, call: ApiCall) => unknown);
}

export interface FetchStub {
  /** 부른 순서대로 전부 */
  calls: ApiCall[];
  /** 경로만 뽑아 본다 — 실패 메시지에 그대로 실려 원인을 바로 보여준다 */
  urls(): string[];
  matching(re: RegExp): ApiCall[];
  count(re: RegExp): number;
  /** 기록만 지운다(라우트는 유지) — "전환 이후에 무엇을 불렀나"를 볼 때 쓴다 */
  clear(): void;
}

export function installFetchStub(routes: Route[]): FetchStub {
  const calls: ApiCall[] = [];

  const impl = (input: unknown, init?: { method?: string; body?: string }) => {
    const url = typeof input === "string" ? input : String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    let body: unknown;
    if (init?.body) { try { body = JSON.parse(init.body); } catch { body = init.body; } }
    calls.push({ method, url, body });

    for (const r of routes) {
      const m = new RegExp(r.match.source, r.match.flags.replace("g", "")).exec(url);
      if (!m) continue;
      const status = r.status ?? 200;
      const payload = typeof r.body === "function"
        ? (r.body as (mm: RegExpExecArray, call: ApiCall) => unknown)(m, { method, url, body })
        : r.body;
      return Promise.resolve({
        ok: status < 400,
        status,
        json: () => Promise.resolve(payload ?? null),
        text: () => Promise.resolve(JSON.stringify(payload ?? null)),
      });
    }
    // 라우트에 없는 경로 = 백엔드에 그 산출물이 없는 상태. 화면의 폴백을 태운다.
    return Promise.resolve({
      ok: false, status: 404,
      json: () => Promise.resolve({ detail: "not found" }),
      text: () => Promise.resolve("not found"),
    });
  };

  vi.stubGlobal("fetch", impl);

  return {
    calls,
    urls: () => calls.map((c) => `${c.method} ${c.url}`),
    matching: (re) => calls.filter((c) => re.test(c.url)),
    count: (re) => calls.filter((c) => re.test(c.url)).length,
    clear: () => { calls.length = 0; },
  };
}

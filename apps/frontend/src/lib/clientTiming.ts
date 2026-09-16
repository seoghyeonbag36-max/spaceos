/**
 * 화면 구간 시간 계측 — KPI② 의 화면 쪽(`지도·건물 상세 로딩 3초`).
 *
 * ## 왜 있나
 *
 * 2026-09-16 에 세어 보니 이 목표를 재는 코드가 저장소 전체에 **0줄**이었다. 서버
 * 미들웨어는 처리시간만 재고, 사용자가 체감하는 "지도가 뜨기까지"는 SDK 내려받기·
 * 렌더까지 포함하므로 브라우저에서만 잴 수 있다.
 *
 * ## 규칙 — 계측이 화면을 해치지 않는다
 *
 * - **절대 throw 하지 않는다.** Performance API 가 없거나 비콘이 막혀도 화면은 그대로다.
 * - **기다리지 않는다.** `keepalive` fetch 로 띄워 보내고 결과를 안 본다.
 * - **한 번만 보낸다.** 같은 이름은 첫 측정만 — 리렌더마다 쌓이면 표본이 오염된다.
 *
 * ⚠ 이 값은 **클라이언트 자가보고**라 서버 실측과 등급이 다르다. 서버가 `client:`
 *   접두사로 구분해 저장한다(apps/backend/app/api/v1/metrics.py §신뢰 경계).
 */

/** 서버 `ALLOWED` 와 같은 목록. 늘릴 때는 양쪽을 같이 고친다. */
export type ClientMetric = "map_ready" | "building_detail";

const started = new Map<ClientMetric, number>();
const sent = new Set<ClientMetric>();

function now(): number | null {
  try {
    return typeof performance !== "undefined" && typeof performance.now === "function"
      ? performance.now()
      : null;
  } catch {
    return null;
  }
}

/** 구간 시작. 같은 이름을 다시 시작하면 마지막 것이 이긴다. */
export function startTiming(metric: ClientMetric): void {
  const t = now();
  if (t !== null && !sent.has(metric)) started.set(metric, t);
}

/** 구간 종료 + 전송. 시작이 없거나 이미 보냈으면 아무것도 하지 않는다. */
export function endTiming(metric: ClientMetric): void {
  if (sent.has(metric)) return;
  const t0 = started.get(metric);
  const t1 = now();
  if (t0 === undefined || t1 === null) return;
  sent.add(metric);
  started.delete(metric);
  report(metric, Math.max(0, t1 - t0));
}

function report(metric: ClientMetric, ms: number): void {
  try {
    // api.ts 와 같은 상대경로 규약(`/api/v1`) — 오리진이 갈리지 않는다.
    void fetch("/api/v1/metrics/client", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ metric, ms: Math.round(ms) }),
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    /* 계측 실패는 화면과 무관하다 */
  }
}

/** 테스트용 — 모듈 상태를 비운다. */
export function _resetTiming(): void {
  started.clear();
  sent.clear();
}

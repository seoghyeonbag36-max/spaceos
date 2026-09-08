/**
 * 네이버 지도 SDK 스텁 — 테스트는 **실제 지도를 부르지 않는다**.
 *
 * ## 왜 필요한가
 *
 * 이 앱의 지도 표면은 두 층이다. `MapHost` 가 지도를 하나 만들어 앱 수명 동안 들고 있고,
 * 탭(Page·거점)은 그 위에 **오버레이만 갈아끼운다**. 그래서 회귀는 거의 같은 자리에서
 * 난다 — 거점을 바꿨는데 이전 거점의 폴리곤·마커가 안 걷히거나, 리스너가 안 떨어진다.
 * 스텁은 그 둘을 **셀 수 있게** 만든다:
 *   - 오버레이마다 지금 어느 지도에 붙어 있는지(`map`)를 들고 있다. `setMap(null)` 로
 *     걷히면 `null` 이 된다 → `live()` 로 세면 화면에 남은 것만 나온다.
 *   - `Event.addListener` 로 건 핸들러는 `removeListener` 전까지 `liveListeners()` 에 남는다.
 *
 * ⚠ 이 스텁은 **관측용**이지 SDK 재구현이 아니다. 좌표 계산·투영은 하지 않는다.
 *   화면이 값을 어떻게 그리는지는 DOM 으로 보고, 여기서는 "무엇을 몇 개 붙였고 걷었나"만 본다.
 */

type Handler = (...args: unknown[]) => void;

export interface StubOverlay {
  /** Polygon · Marker · Circle · Rectangle · HeatMap … */
  readonly kind: string;
  readonly options: Record<string, unknown>;
  /** 지금 붙어 있는 지도. `setMap(null)` 이면 null 이다. */
  map: unknown;
  /** setMap 호출 이력 — 걷혔는지뿐 아니라 몇 번 걷혔는지도 본다. */
  readonly setMapCalls: unknown[];
  setMap(m: unknown): void;
  getMap(): unknown;
}

export interface StubListener {
  target: unknown;
  type: string;
  handler: Handler;
  removed: boolean;
}

export interface StubMap {
  el: unknown;
  options: Record<string, unknown>;
  /** setCenter / panTo / fitBounds 로 카메라를 옮긴 이력 */
  moves: Array<{ kind: "setCenter" | "panTo" | "fitBounds"; arg: unknown }>;
  zoom: number;
  setCenter(v: unknown): void;
  panTo(v: unknown): void;
  fitBounds(v: unknown, padding?: unknown): void;
  setZoom(z: number): void;
  getZoom(): number;
  getCenter(): unknown;
  setOptions(): void;
  refresh(): void;
  destroy(): void;
}

export interface NaverStub {
  /** 만들어진 순서대로 전부. 걷힌 것도 남는다(걷혔는지를 봐야 하므로). */
  overlays: StubOverlay[];
  listeners: StubListener[];
  maps: StubMap[];
  /** 아직 지도에 붙어 있는 오버레이만 */
  live(): StubOverlay[];
  /** 아직 떨어지지 않은 SDK 리스너만 */
  liveListeners(): StubListener[];
  /** 마지막으로 만들어진 지도(= MapHost 가 들고 있는 그것) */
  map(): StubMap | null;
  /** SDK 이벤트 발화 — 줌 변경 같은 사용자 조작을 흉내낸다 */
  emit(target: unknown, type: string, ...args: unknown[]): void;
}

/** `window.naver` 에 스텁을 심고 관측 핸들을 돌려준다. 각 테스트 beforeEach 에서 부른다. */
export function installNaverStub(): NaverStub {
  const overlays: StubOverlay[] = [];
  const listeners: StubListener[] = [];
  const maps: StubMap[] = [];

  class LatLng {
    constructor(private readonly _lat: number, private readonly _lng: number) {}
    lat() { return this._lat; }
    lng() { return this._lng; }
  }

  class LatLngBounds {
    constructor(public sw: unknown, public ne: unknown) {}
  }

  class Point {
    constructor(public x: number, public y: number) {}
  }

  class Overlay implements StubOverlay {
    readonly setMapCalls: unknown[] = [];
    map: unknown;
    constructor(readonly kind: string, readonly options: Record<string, unknown> = {}) {
      this.map = options.map ?? null;
      overlays.push(this);
    }
    setMap(m: unknown) { this.setMapCalls.push(m); this.map = m ?? null; }
    getMap() { return this.map; }
  }

  /** 오버레이 종류마다 생성자를 하나씩 — 화면 코드는 `new naver.maps.Polygon({...})` 그대로 쓴다. */
  const overlayCtor = (kind: string) =>
    class extends Overlay {
      constructor(options: Record<string, unknown> = {}) { super(kind, options); }
    };

  class NaverMap implements StubMap {
    moves: StubMap["moves"] = [];
    zoom: number;
    constructor(public el: unknown, public options: Record<string, unknown> = {}) {
      // 폴리곤/점 표현이 갈리는 줌 경계는 15 다(MapShell 의 PIN_MAX_ZOOM).
      // 기본 16 = 가까이 본 상태 → 건물 폴리곤이 그려진다.
      this.zoom = typeof options.zoom === "number" ? (options.zoom as number) : 16;
      maps.push(this);
    }
    setCenter(v: unknown) { this.moves.push({ kind: "setCenter", arg: v }); }
    panTo(v: unknown) { this.moves.push({ kind: "panTo", arg: v }); }
    fitBounds(v: unknown) { this.moves.push({ kind: "fitBounds", arg: v }); }
    setZoom(z: number) { this.zoom = z; }
    getZoom() { return this.zoom; }
    getCenter() { return new LatLng(37.5205, 127.023); }
    setOptions() {}
    refresh() {}
    destroy() {}
  }

  const Event = {
    addListener(target: unknown, type: string, handler: Handler): StubListener {
      const l: StubListener = { target, type, handler, removed: false };
      listeners.push(l);
      return l;
    },
    removeListener(h: StubListener | StubListener[]) {
      for (const l of Array.isArray(h) ? h : [h]) if (l) l.removed = true;
    },
    clearListeners(target: unknown) {
      for (const l of listeners) if (l.target === target) l.removed = true;
    },
  };

  const naver = {
    maps: {
      LatLng, LatLngBounds, Point, Map: NaverMap, Event,
      Polygon: overlayCtor("Polygon"),
      Marker: overlayCtor("Marker"),
      Circle: overlayCtor("Circle"),
      Rectangle: overlayCtor("Rectangle"),
      InfoWindow: overlayCtor("InfoWindow"),
      visualization: { HeatMap: overlayCtor("HeatMap") },
    },
  };

  (window as unknown as { naver: unknown }).naver = naver;

  return {
    overlays, listeners, maps,
    live: () => overlays.filter((o) => o.map != null),
    liveListeners: () => listeners.filter((l) => !l.removed),
    map: () => maps[maps.length - 1] ?? null,
    emit(target, type, ...args) {
      for (const l of listeners) {
        if (!l.removed && l.target === target && l.type === type) l.handler(...args);
      }
    },
  };
}

/** 테스트가 끝나면 전역을 원래대로 — 파일 간에 지도가 새지 않게. */
export function removeNaverStub(): void {
  delete (window as unknown as { naver?: unknown }).naver;
}

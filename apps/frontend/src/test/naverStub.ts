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
  /** 생성 옵션 + 이후 `setOptions` 로 덮인 값이 합쳐진 현재 상태. */
  readonly options: Record<string, unknown>;
  /** 지금 붙어 있는 지도. `setMap(null)` 이면 null 이다. */
  map: unknown;
  /** setMap 호출 이력 — 걷혔는지뿐 아니라 몇 번 걷혔는지도 본다. */
  readonly setMapCalls: unknown[];
  /** setOptions 호출 이력 — 호버 강조처럼 **다시 그리지 않고 고치는** 경로를 본다. */
  readonly setOptionsCalls: Record<string, unknown>[];
  setMap(m: unknown): void;
  getMap(): unknown;
  setOptions(o: Record<string, unknown>): void;
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
  /**
   * 현재 화면 범위. **기본값은 null** 이다 — 실제 SDK 는 지도가 붙기 전 null 을 준다.
   * 화면 코드는 그때 뷰포트 필터를 걸지 않아야 한다(범위를 모르는데 거르면 목록이 빈다).
   * 테스트에서 뷰포트 동기화를 보려면 여기에 LatLngBounds 를 넣고 `idle` 을 발화한다.
   */
  bounds: unknown;
  setCenter(v: unknown): void;
  panTo(v: unknown): void;
  fitBounds(v: unknown, padding?: unknown): void;
  setZoom(z: number): void;
  getZoom(): number;
  getBounds(): unknown;
  getCenter(): unknown;
  setOptions(): void;
  refresh(): void;
  destroy(): void;
}

export interface NaverStub {
  /** 화면 코드가 좌표를 만들 때 쓰는 것과 같은 생성자 — 테스트가 뷰포트를 짤 때 쓴다. */
  LatLng: new (lat: number, lng: number) => { lat(): number; lng(): number };
  LatLngBounds: new (sw: unknown, ne: unknown) => { hasLatLng(ll: unknown): boolean };
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

  /**
   * 뷰포트 판정만 **진짜로** 한다. 좌표 투영은 여전히 안 하지만, 목록이 화면 범위로
   * 좁혀지는지(R2 뷰포트 동기화)는 포함 여부를 실제로 계산해야 볼 수 있다.
   * 경도 180도 경계(dateline)는 다루지 않는다 — 우리 거점은 전부 한국이다.
   */
  class LatLngBounds {
    constructor(public sw: any, public ne: any) {}
    hasLatLng(ll: any) {
      const lat = typeof ll?.lat === "function" ? ll.lat() : ll?.lat;
      const lng = typeof ll?.lng === "function" ? ll.lng() : ll?.lng;
      return lat >= this.sw.lat() && lat <= this.ne.lat()
        && lng >= this.sw.lng() && lng <= this.ne.lng();
    }
  }

  class Point {
    constructor(public x: number, public y: number) {}
  }

  class Overlay implements StubOverlay {
    readonly setMapCalls: unknown[] = [];
    readonly setOptionsCalls: Record<string, unknown>[] = [];
    map: unknown;
    constructor(readonly kind: string, readonly options: Record<string, unknown> = {}) {
      this.map = options.map ?? null;
      overlays.push(this);
    }
    setMap(m: unknown) { this.setMapCalls.push(m); this.map = m ?? null; }
    getMap() { return this.map; }
    /** 실제 SDK 와 같이 **제자리에서** 옵션을 덮는다 — 오버레이를 새로 만들지 않는다. */
    setOptions(o: Record<string, unknown>) {
      this.setOptionsCalls.push(o);
      Object.assign(this.options, o);
    }
  }

  /** 오버레이 종류마다 생성자를 하나씩 — 화면 코드는 `new naver.maps.Polygon({...})` 그대로 쓴다. */
  const overlayCtor = (kind: string) =>
    class extends Overlay {
      constructor(options: Record<string, unknown> = {}) { super(kind, options); }
    };

  class NaverMap implements StubMap {
    moves: StubMap["moves"] = [];
    zoom: number;
    bounds: unknown = null;
    constructor(public el: unknown, public options: Record<string, unknown> = {}) {
      // 앱 기본 줌과 같은 값(MapHost.DEFAULT_ZOOM). 다만 **이 기본값은 거의 안 쓰인다** —
      // MapHost 가 지도를 만들 때 zoom 을 명시해 넘기므로 options.zoom 쪽으로 들어온다.
      // 여기 값이 쓰이는 건 zoom 없이 지도를 만드는 경우뿐이다.
      //
      // ⚠ 줌 16 은 이제 **점 모드**다(MapShell 의 PIN_MAX_ZOOM, 2026-09-13 에 15→16).
      //   건물마다 도형이 하나씩 필요한 테스트는 스스로 확대해야 한다 →
      //   MapShell.test.tsx 의 `polygonMode()`.
      this.zoom = typeof options.zoom === "number" ? (options.zoom as number) : 16;
      maps.push(this);
    }
    setCenter(v: unknown) { this.moves.push({ kind: "setCenter", arg: v }); }
    panTo(v: unknown) { this.moves.push({ kind: "panTo", arg: v }); }
    fitBounds(v: unknown) { this.moves.push({ kind: "fitBounds", arg: v }); }
    setZoom(z: number) { this.zoom = z; }
    getZoom() { return this.zoom; }
    getBounds() { return this.bounds; }
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
    LatLng: LatLng as unknown as NaverStub["LatLng"],
    LatLngBounds: LatLngBounds as unknown as NaverStub["LatLngBounds"],
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

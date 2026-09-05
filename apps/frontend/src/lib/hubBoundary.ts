/**
 * 거점 실측 범위(경계) 산출 — 설계서 `docs/screen-hub-explorer.md` 부록 A(B안).
 *
 * ## 왜 이 계산이 필요한가
 *
 * 시스템에 "거점 경계 폴리곤"이라는 데이터는 없다. `gold/{거점}/district_zones.json` 은
 * 행정동 **이름과 중심점**만 갖는다. 그래서 경계는 이미 있는 실측 산출물 —
 * `/heatmap/vacancy` 의 100m 격자 셀 — 의 **외곽선**으로 만든다. 추가 수집이 없고,
 * "이 안이 실제로 재어진 곳"이라는 참말을 한다.
 *
 * ⚠ **`v > 0` 으로 셀을 거르지 말 것.** 응답의 모든 셀이 `capacity > 0` 이라 배열에
 * 있다는 것이 곧 "재어진 곳"이다. `v > 0` 으로 거르면 66거점 4,501셀 중 1,598셀
 * (35.5%)이 빠지는데 그건 공실이 0인 = **가장 꽉 찬 블록**들이다. 경계에 구멍이 나되
 * 하필 제일 건강한 자리에 난다(2026-09-05 실측).
 *
 * ## 입력의 성질 (2026-09-05 실측)
 * - 셀은 정수 인덱스 `i,j` 의 균일 격자. `dlat 0.0009` · `dlng 0.00113`(100m)이
 *   66거점 전부에서 같다.
 * - `lat/lng` 는 셀의 **남서 모서리**, `c_lat/c_lng` 는 중심(`c_lat − lat === dlat/2`).
 * - 셀이 한 덩어리라는 보장이 없다 — **42/66 거점이 조각 2개 이상**이고, 최대 조각
 *   비중이 30% 인 거점도 있다(yeouido 10조각·mullae 9조각). 조각을 감싸 하나로
 *   덮으면 **안 잰 곳을 잰 것처럼** 그리게 되므로, 조각은 조각대로 그리고 몇 조각인지
 *   화면이 밝힌다.
 */
import type { HeatCell } from "@/lib/api";

/** 경계 한 조각(4-이웃 연결요소) — 외곽 링 1개 + 구멍 링 N개. */
export interface BoundaryPiece {
  /** 이 조각이 품은 셀 수 — 스타일을 가르는 기준(1칸짜리 섬은 경계로 읽히지 않는다). */
  cells: number;
  /** 외곽 링. `[lat, lng]` 의 닫힌 고리(첫 점 == 끝 점 아님 — 폴리곤이 알아서 닫는다). */
  outer: Array<[number, number]>;
  /** 구멍 링들. 채우기가 구멍을 덮으면 "저기도 쟀다"로 읽힌다. */
  holes: Array<Array<[number, number]>>;
}

export interface HubBoundary {
  /** 셀 수 내림차순. */
  pieces: BoundaryPiece[];
  /** 조각 수(4-이웃 기준). */
  components: number;
  /** 최대 조각이 전체 셀에서 차지하는 비율(0~100). 70 미만이면 화면이 경고한다. */
  largestShare: number;
  cellCount: number;
  bbox: { south: number; west: number; north: number; east: number } | null;
}

export const EMPTY_BOUNDARY: HubBoundary = {
  pieces: [], components: 0, largestShare: 0, cellCount: 0, bbox: null,
};

const NB: Array<[number, number]> = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const kx = (i: number, j: number) => `${i},${j}`;

/** 방향 — 0 동(+x) · 1 북(+y) · 2 서(−x) · 3 남(−y). */
type Dir = 0 | 1 | 2 | 3;
interface Edge { fx: number; fy: number; tx: number; ty: number; dir: Dir; used: boolean }

/**
 * 실측 셀 목록 → 경계.
 *
 * 셀이 없으면 `EMPTY_BOUNDARY` 를 돌려준다(예외 아님 — 호출부가 "실측 범위 없음"을 그린다).
 */
export function computeHubBoundary(cells: HeatCell[] | null | undefined): HubBoundary {
  if (!cells || cells.length === 0) return EMPTY_BOUNDARY;
  const { dlat, dlng } = cells[0];
  if (!dlat || !dlng) return EMPTY_BOUNDARY;

  // 격자 원점. i=0,j=0 셀이 응답에 없을 수 있으므로(가로수길 j 는 −1 부터다) 역산한다.
  const lat0 = cells[0].lat - cells[0].j * dlat;
  const lng0 = cells[0].lng - cells[0].i * dlng;

  const filled = new Set<string>();
  for (const c of cells) filled.add(kx(c.i, c.j));

  // ── 4-이웃 연결요소 ──────────────────────────────────────────────────────
  // 8-이웃으로 묶으면 대각으로만 맞닿은 조각이 한 덩어리로 보여 조각 수가 줄어든다.
  // 사람 눈에도 그 둘은 떨어져 있으므로 4-이웃으로 센다.
  const seen = new Set<string>();
  const groups: Array<Array<[number, number]>> = [];
  for (const c of cells) {
    const start = kx(c.i, c.j);
    if (seen.has(start)) continue;
    seen.add(start);
    const stack: Array<[number, number]> = [[c.i, c.j]];
    const group: Array<[number, number]> = [];
    while (stack.length) {
      const [i, j] = stack.pop()!;
      group.push([i, j]);
      for (const [di, dj] of NB) {
        const nk = kx(i + di, j + dj);
        if (filled.has(nk) && !seen.has(nk)) {
          seen.add(nk);
          stack.push([i + di, j + dj]);
        }
      }
    }
    groups.push(group);
  }

  const pieces: BoundaryPiece[] = [];
  for (const group of groups) {
    const rings = ringsOf(group, filled);
    // 외곽은 반시계(양수 면적), 구멍은 시계(음수). 핀치(대각 접점)로 외곽이 둘이 될 수
    // 있으므로 외곽을 배열로 받고, 구멍은 자기를 감싸는 외곽에 붙인다.
    const outers = rings.filter((r) => shoelace(r) > 0);
    const holes = rings.filter((r) => shoelace(r) < 0);
    if (outers.length === 0) continue;   // 이론상 없음 — 방어

    const built: BoundaryPiece[] = outers.map((o) => ({
      cells: 0, outer: o.map((p) => toLatLng(p, lat0, lng0, dlat, dlng)), holes: [],
    }));
    // 조각 셀 수는 외곽이 하나일 때만 정확히 갈린다. 핀치로 둘 이상이면 셀 수를 나누는
    // 대신 첫 외곽에 몰아준다 — 스타일 판정(1칸 섬인가)만 쓰는 값이라 충분하다.
    built[0].cells = group.length;

    for (const h of holes) {
      const idx = outers.findIndex((o) => bboxContains(bboxOf(o), bboxOf(h)));
      built[idx >= 0 ? idx : 0].holes.push(h.map((p) => toLatLng(p, lat0, lng0, dlat, dlng)));
    }
    pieces.push(...built);
  }

  pieces.sort((a, b) => b.cells - a.cells);

  const cellCount = filled.size;
  const largest = groups.reduce((m, g) => Math.max(m, g.length), 0);

  let south = Infinity, west = Infinity, north = -Infinity, east = -Infinity;
  for (const c of cells) {
    if (c.lat < south) south = c.lat;
    if (c.lng < west) west = c.lng;
    if (c.lat + dlat > north) north = c.lat + dlat;
    if (c.lng + dlng > east) east = c.lng + dlng;
  }

  return {
    pieces,
    components: groups.length,
    largestShare: cellCount ? (100 * largest) / cellCount : 0,
    cellCount,
    bbox: Number.isFinite(south) ? { south, west, north, east } : null,
  };
}

/**
 * 한 조각의 경계 링들 — marching edges.
 *
 * 셀의 네 변 중 **이웃이 없는 변만** 경계다. 방향은 내부가 항상 왼쪽에 오도록 준다
 * (반시계). 그러면 외곽 링은 양수 면적, 구멍 링은 음수 면적이 되어 둘을 면적 부호로
 * 가를 수 있다.
 */
function ringsOf(group: Array<[number, number]>, filled: Set<string>): Array<Array<[number, number]>> {
  const edges: Edge[] = [];
  for (const [i, j] of group) {
    // 남쪽 이웃 없음 → (i,j) → (i+1,j)  동
    if (!filled.has(kx(i, j - 1))) edges.push({ fx: i, fy: j, tx: i + 1, ty: j, dir: 0, used: false });
    // 동쪽 이웃 없음 → (i+1,j) → (i+1,j+1)  북
    if (!filled.has(kx(i + 1, j))) edges.push({ fx: i + 1, fy: j, tx: i + 1, ty: j + 1, dir: 1, used: false });
    // 북쪽 이웃 없음 → (i+1,j+1) → (i,j+1)  서
    if (!filled.has(kx(i, j + 1))) edges.push({ fx: i + 1, fy: j + 1, tx: i, ty: j + 1, dir: 2, used: false });
    // 서쪽 이웃 없음 → (i,j+1) → (i,j)  남
    if (!filled.has(kx(i - 1, j))) edges.push({ fx: i, fy: j + 1, tx: i, ty: j, dir: 3, used: false });
  }

  const out = new Map<string, Edge[]>();
  for (const e of edges) {
    const k = kx(e.fx, e.fy);
    const bucket = out.get(k);
    if (bucket) bucket.push(e);
    else out.set(k, [e]);
  }

  const rings: Array<Array<[number, number]>> = [];
  for (const seed of edges) {
    if (seed.used) continue;
    seed.used = true;
    const ring: Array<[number, number]> = [[seed.fx, seed.fy]];
    let cx = seed.tx, cy = seed.ty, dir = seed.dir;

    // 한 꼭짓점에서 나가는 변이 둘일 수 있다(대각으로만 맞닿은 핀치 지점).
    // 그때는 **오른쪽으로 가장 많이 도는 변**을 먼저 고른다 — 내부를 바짝 끼고 돌아야
    // 링이 8자로 꼬이지 않고 둘로 깔끔히 갈린다.
    while (!(cx === seed.fx && cy === seed.fy)) {
      ring.push([cx, cy]);
      const cands = out.get(kx(cx, cy));
      if (!cands) break;                       // 열린 사슬 — 이론상 없음
      const order: Dir[] = [((dir + 3) % 4) as Dir, dir, ((dir + 1) % 4) as Dir, ((dir + 2) % 4) as Dir];
      let next: Edge | undefined;
      for (const want of order) {
        next = cands.find((e) => !e.used && e.dir === want);
        if (next) break;
      }
      if (!next) break;
      next.used = true;
      cx = next.tx; cy = next.ty; dir = next.dir;
    }
    if (ring.length >= 4) rings.push(ring);
  }
  return rings;
}

/** 신발끈 — 부호가 방향을 말한다(양수 = 반시계 = 외곽). */
function shoelace(ring: Array<[number, number]>): number {
  let s = 0;
  for (let n = 0; n < ring.length; n++) {
    const [x1, y1] = ring[n];
    const [x2, y2] = ring[(n + 1) % ring.length];
    s += x1 * y2 - x2 * y1;
  }
  return s / 2;
}

interface BBox { minx: number; miny: number; maxx: number; maxy: number }

function bboxOf(ring: Array<[number, number]>): BBox {
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  for (const [x, y] of ring) {
    if (x < minx) minx = x;
    if (y < miny) miny = y;
    if (x > maxx) maxx = x;
    if (y > maxy) maxy = y;
  }
  return { minx, miny, maxx, maxy };
}

const bboxContains = (o: BBox, h: BBox) =>
  o.minx <= h.minx && o.miny <= h.miny && o.maxx >= h.maxx && o.maxy >= h.maxy;

/** 격자 꼭짓점 (x,y) → [lat, lng]. 셀 (i,j) 의 남서 모서리가 꼭짓점 (i,j) 다. */
function toLatLng(
  [x, y]: [number, number], lat0: number, lng0: number, dlat: number, dlng: number,
): [number, number] {
  return [lat0 + y * dlat, lng0 + x * dlng];
}

/**
 * 범례에 붙는 경계 근거 배지 문구 — 설계서 §6.
 *
 * 조각을 숨기지 않는다. 최대 조각이 70% 미만이면 그 비중까지 적는다(yeouido 는
 * 10조각에 최대 30% 라, "실측 범위"라고만 하면 한 덩어리처럼 읽힌다).
 */
export function boundaryBadge(b: HubBoundary): string {
  if (b.cellCount === 0) return "실측 범위 없음";
  if (b.components <= 1) return "실측 범위";
  if (b.largestShare >= 70) return `실측 범위 · ${b.components}조각`;
  return `실측 범위 · ${b.components}조각(최대 ${Math.round(b.largestShare)}%)`;
}

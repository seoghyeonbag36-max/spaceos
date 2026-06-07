/**
 * SpaceOS PPPP 통합 뷰 데이터 모듈 (라페스타·웨스턴돔).
 * 정적 HTML 프로토타입(SpaceOS_Lafesta_PPPP_Platform_Naver.html)을 타입 안전하게 이식.
 * TODO: 실데이터 연동 시 이 모듈을 API(/api/v1/...) 응답으로 대체.
 *  - zones  → GET /api/v1/commercial-districts/{id}/sentiment
 *  - cells  → GET /api/v1/heatmap/vacancy?grid=100m
 *  - units  → GET /api/v1/buildings/vacancies
 *  - events → GET /api/v1/marketing/programs
 */

export type PKey = "P1" | "P2" | "P3" | "P4";
export type TierKey = "premium" | "value" | "factory";

export interface Zone {
  id: string; n: string; grp: string; lat: number; lng: number;
  s: number; d: number; r: number; f: [string, string, "up" | "dn"][];
}
export interface Cell {
  i: number; j: number; lat: number; lng: number; cLat: number; cLng: number;
  v: number; stores: number; vacN: number;
}
export interface Unit {
  id: string; n: string; grp: string; lat: number; lng: number;
  area: number; rent: number; prem: number; floor: string; was: string;
  rec: TierKey; foot: "저" | "중" | "고"; persona: string; note: string;
}
export interface EventItem {
  id: string; n: string; lat: number; lng: number; ic: string; when: string;
  k2: string; desc: string; roles: string[]; ha: string;
}

/* ===== 색상 헬퍼 ===== */
export const fgHex = (s: number) => (s < 40 ? "#d9716a" : s < 60 ? "#e3b95e" : s < 80 ? "#7faa55" : "#3a5a98");
export const fgV = (s: number) => (s < 40 ? "#b23b39" : s < 60 ? "#9a7b1e" : s < 80 ? "#4f7a31" : "#3a5a98");
export const vacColor = (v: number) => (v < 5 ? "#cfe3cf" : v < 10 ? "#fbe7a6" : v < 18 ? "#f6b96b" : v < 28 ? "#e8743b" : "#c0392b");
export const arrow = (d: number) => (d > 0 ? "↑" + d.toFixed(1) : d < 0 ? "↓" + Math.abs(d).toFixed(1) : "→" + d.toFixed(1));
export const rev = (n: number) => (n >= 1000 ? (n / 1000).toFixed(1) + "K" : String(n));
export const rad = (r: number) => 12 + Math.sqrt(r) / 3;

/* ===== P1 감성 구역 ===== */
export const zones: Zone[] = [
  { id: "laf-jm", n: "라페스타 정문광장", grp: "라페스타", lat: 37.65945, lng: 126.76935, s: 74.2, d: 1.8, r: 856, f: [["인스타 노출량", "+58%", "up"], ["주말 유입", "+33%", "up"], ["이벤트 언급", "+21%", "up"]] },
  { id: "laf-cc", n: "라페스타 중앙상가", grp: "라페스타", lat: 37.65880, lng: 126.77010, s: 68.4, d: -0.6, r: 1900, f: [["공실 점포 언급", "+44%", "up"], ["가격 만족도", "-12%", "dn"], ["브랜드 다양성", "+8%", "up"]] },
  { id: "laf-rt", n: "라페스타 레스토랑거리", grp: "라페스타", lat: 37.65820, lng: 126.77085, s: 76.8, d: 2.4, r: 1100, f: [["맛집 재방문", "+61%", "up"], ["웨이팅 불만", "+19%", "up"], ["SNS 인증샷", "+47%", "up"]] },
  { id: "laf-pk", n: "라페스타 후면주차장", grp: "라페스타", lat: 37.65775, lng: 126.77150, s: 38.9, d: -4.2, r: 287, f: [["주차 불편", "+276%", "up"], ["야간 안전 우려", "+148%", "up"], ["접근성 평가", "-39%", "dn"]] },
  { id: "laf-cv", n: "라페스타 편의시설", grp: "라페스타", lat: 37.65845, lng: 126.76960, s: 65.3, d: 0.2, r: 642, f: [["생활 편의", "+27%", "up"], ["노후 시설", "+31%", "up"], ["청결도", "+14%", "up"]] },
  { id: "wes-1", n: "웨스턴돔 1F (요식)", grp: "웨스턴돔", lat: 37.66055, lng: 126.77205, s: 62.1, d: 0.4, r: 824, f: [["F&B 만족도", "+22%", "up"], ["혼잡도 불만", "+18%", "up"], ["접근 편의", "+6%", "up"]] },
  { id: "wes-2", n: "웨스턴돔 2F", grp: "웨스턴돔", lat: 37.66085, lng: 126.77245, s: 43.7, d: -2.1, r: 412, f: [["공실 확대", "+187%", "up"], ["동선 혼란", "+92%", "up"], ["체류시간", "-28%", "dn"]] },
  { id: "wes-3", n: "웨스턴돔 3F", grp: "웨스턴돔", lat: 37.66110, lng: 126.77285, s: 31.5, d: -5.8, r: 168, f: [["관리필요", "+312%", "up"], ["접근불편", "+184%", "up"], ["인스타 노출", "-47%", "dn"]] },
];
export const zoneById: Record<string, Zone> = Object.fromEntries(zones.map((z) => [z.id, z]));

/* ===== P2 공실 그리드 (100m 격자 합성) ===== */
export const BB = { s: 37.6565, n: 37.6620, w: 126.7685, e: 126.7745 };
export const DLAT = 0.0009;
export const DLNG = 0.001135;
const hot = [
  { lat: 37.65775, lng: 126.77150, r: 90, pk: 34 }, { lat: 37.66085, lng: 126.77245, r: 80, pk: 31 },
  { lat: 37.66110, lng: 126.77285, r: 85, pk: 42 }, { lat: 37.65880, lng: 126.77010, r: 70, pk: 16 },
  { lat: 37.65945, lng: 126.76935, r: 60, pk: 6 }, { lat: 37.65820, lng: 126.77085, r: 60, pk: 5 },
];
const coreC = { lat: 37.6594, lng: 126.7711 };
const distM = (aLat: number, aLng: number, bLat: number, bLng: number) => {
  const dy = (aLat - bLat) * 111000, dx = (aLng - bLng) * 88800;
  return Math.sqrt(dx * dx + dy * dy);
};
const seed = (i: number, j: number) => { const x = Math.sin(i * 12.9898 + j * 78.233) * 43758.5453; return x - Math.floor(x); };

function buildCells() {
  const out: Cell[] = []; let sumStores = 0, sumVac = 0;
  for (let lat = BB.s, i = 0; lat < BB.n - 1e-9; lat += DLAT, i++) {
    for (let lng = BB.w, j = 0; lng < BB.e - 1e-9; lng += DLNG, j++) {
      const cLat = lat + DLAT / 2, cLng = lng + DLNG / 2;
      let v = 2.5, infl = 0;
      hot.forEach((h) => { const d = distM(cLat, cLng, h.lat, h.lng), w = Math.exp(-(d * d) / (2 * h.r * h.r)); v += h.pk * w; infl += w; });
      v += (seed(i, j) - 0.5) * 4;
      const dc = distM(cLat, cLng, coreC.lat, coreC.lng);
      if (!(infl > 0.12 && dc < 340)) continue;
      v = Math.max(2, Math.min(46, v));
      const stores = Math.round(8 + 22 * Math.min(1, infl) + seed(j, i) * 10);
      const vacN = Math.round((stores * v) / 100);
      out.push({ i, j, lat, lng, cLat, cLng, v, stores, vacN });
      sumStores += stores; sumVac += vacN;
    }
  }
  return { cells: out, sumStores, sumVac };
}
const built = buildCells();
export const cells = built.cells;
export const sumStores = built.sumStores;
export const sumVac = built.sumVac;
export const cellById: Record<string, Cell> = Object.fromEntries(cells.map((c) => [`${c.i}_${c.j}`, c]));

export const mixHi: [string, number, string][] = [["요식", 24, "#e8743b"], ["공실", 38, "#c0392b"], ["생활편의", 14, "#9aa3af"], ["뷰티", 8, "#c98bbf"], ["기타", 16, "#cbd2d9"]];
export const mixMid: [string, number, string][] = [["요식", 34, "#e8743b"], ["공실", 16, "#c0392b"], ["패션", 14, "#7a9ad6"], ["뷰티", 12, "#c98bbf"], ["생활편의", 12, "#9aa3af"], ["기타", 12, "#cbd2d9"]];
export const mixLo: [string, number, string][] = [["요식", 42, "#e8743b"], ["카페", 18, "#b07a4a"], ["패션", 14, "#7a9ad6"], ["뷰티", 10, "#c98bbf"], ["공실", 5, "#c0392b"], ["기타", 11, "#cbd2d9"]];
export const mixFor = (v: number) => (v >= 24 ? mixHi : v >= 10 ? mixMid : mixLo);

/* ===== P3 입점 3-Tier ===== */
export const TIER: Record<TierKey, { nm: string; sub: string; c: string; bg: string }> = {
  premium: { nm: "고급화", sub: "Premium", c: "#7a4f9a", bg: "#efe7f5" },
  value: { nm: "가성비", sub: "Value", c: "#2f7d4f", bg: "#e0f0e6" },
  factory: { nm: "공장제", sub: "Standardized", c: "#b06a1e", bg: "#f6e9d4" },
};
export const units: Unit[] = [
  { id: "u-cc", n: "중앙상가 B동 1F", grp: "라페스타", lat: 37.65882, lng: 126.77012, area: 40, rent: 330, prem: 1200, floor: "1F", was: "휴대폰", rec: "premium", foot: "고", persona: "20대 여성·데이트", note: "핵심 보행축 1F → 고급화 브랜드 입점가치 최고" },
  { id: "u-rt", n: "레스토랑거리 A동 1F", grp: "라페스타", lat: 37.65822, lng: 126.77088, area: 52, rent: 380, prem: 1500, floor: "1F", was: "액세서리", rec: "premium", foot: "고", persona: "20·30대 외식", note: "맛집거리 집객 → 고객단가 높은 다이닝" },
  { id: "u-wes2", n: "웨스턴돔 2F 211호", grp: "웨스턴돔", lat: 37.66088, lng: 126.77248, area: 46, rent: 240, prem: 300, floor: "2F", was: "의류매장", rec: "value", foot: "중", persona: "20대 여성·직장인", note: "중층·동선 개선 시 회전형 F&B 적합" },
  { id: "u-pk", n: "라페스타 후면동 1F", grp: "라페스타", lat: 37.65778, lng: 126.77148, area: 28, rent: 210, prem: 500, floor: "1F", was: "분식", rec: "value", foot: "중", persona: "야간·주차이용", note: "주차 접근성 활용 픽업형 가성비 업종" },
  { id: "u-wes3", n: "웨스턴돔 3F 304호", grp: "웨스턴돔", lat: 37.66112, lng: 126.77288, area: 33, rent: 165, prem: 0, floor: "3F", was: "노래연습장", rec: "factory", foot: "저", persona: "가족·학원수요", note: "상층부·접근성 약 → 목적형 무인/표준 업종" },
  { id: "u-cv", n: "편의시설동 2F", grp: "라페스타", lat: 37.65847, lng: 126.76962, area: 60, rent: 190, prem: 0, floor: "2F", was: "학원", rec: "factory", foot: "중", persona: "생활밀착", note: "넓은 면적·저임대 → 공유주방/무인 표준 운영" },
];
export const unitById: Record<string, Unit> = Object.fromEntries(units.map((u) => [u.id, u]));

export interface Scenario { invest: number; monthCost: number; monthRev: number; }
export function scenarios(u: Unit): Record<TierKey, Scenario> {
  const fK = { 저: 0.8, 중: 1.0, 고: 1.25 }[u.foot];
  const base = u.area * fK;
  return {
    premium: { invest: Math.round(u.prem / 100 + u.area * 0.55 + 4), monthCost: Math.round(u.rent + u.area * 1.8 + 180), monthRev: Math.round(base * 42 + 1200) },
    value: { invest: Math.round(u.prem / 100 + u.area * 0.32 + 2.2), monthCost: Math.round(u.rent + u.area * 1.1 + 95), monthRev: Math.round(base * 30 + 780) },
    factory: { invest: Math.round(u.prem / 100 + u.area * 0.2 + 1.1), monthCost: Math.round(u.rent + u.area * 0.45 + 25), monthRev: Math.round(base * 18 + 430) },
  };
}
export const roiM = (s: Scenario) => { const net = s.monthRev - s.monthCost; return net <= 0 ? 99 : s.invest / net; };

/* ===== P4 마케팅 ===== */
export const events: EventItem[] = [
  { id: "e1", n: "라페스타 골목 페스타", lat: 37.65900, lng: 126.76980, ic: "🎪", when: "2026.09 · 주말 3일", k2: "유입 +38%", desc: "정문광장~중앙상가 200개 점포 연계 거리 축제. 스탬프 투어로 공실 인접 구역까지 동선 유도.", roles: ["상인회: 부스", "건물주: 공실 개방", "소비자: 스탬프"], ha: "<b>공생</b> — 공실을 팝업 부스로 임시 개방, 임대인-임차인 접점·입점 매칭." },
  { id: "e2", n: "웨스턴돔 빈공간 팝업위크", lat: 37.66095, lng: 126.77260, ic: "🛍", when: "2026.07 · 2주", k2: "전환 12%", desc: "고공실 2·3F를 2주 단기 팝업으로 운영. 브랜드 입점 테스트 + 반응 데이터 수집.", roles: ["건물주: 단기임대", "브랜드: 팝업", "SpaceOS: 데이터"], ha: "<b>균형</b> — 로컬·신생 브랜드에 공정한 노출 기회 배분." },
  { id: "e3", n: "정발산 나이트 마켓", lat: 37.65800, lng: 126.77120, ic: "🌙", when: "매월 마지막 금요일", k2: "야간 +22%", desc: "후면주차장 야간 이슈 구역을 플리마켓·푸드트럭 존으로 전환. 야간 체류시간 확대.", roles: ["상인회: 야시장", "지자체: 안전", "소비자: 야간콘텐츠"], ha: "<b>공감</b> — 라페스타 고유 야간 상권 분위기를 살린 로컬 감성 행사." },
];
export const eventById: Record<string, EventItem> = Object.fromEntries(events.map((e) => [e.id, e]));
export const insta = [
  "📍라페스타 레스토랑거리, 줄 서는 이유\n\n정발산역 도보 5분. 주말 저녁 웨이팅 핫플 골목. 인증샷 남기면 디저트 1+1 🍰\n\n#일산맛집 #라페스타 #정발산역맛집",
  "🌿웨스턴돔 3F가 달라졌어요\n\n비어있던 공간이 무인 디저트·플리마켓 존으로! 24시간 오픈 ☕\n\n#웨스턴돔 #무인카페 #일산가볼만한곳",
];

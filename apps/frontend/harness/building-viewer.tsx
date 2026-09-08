/**
 * BuildingViewer 렌더 하네스 — **개발 전용**. 프로덕션 번들에 들어가지 않는다
 * (vite build 의 input 은 루트 index.html 하나뿐이라 이 엔트리는 dev 에서만 서빙된다).
 *
 * ## 왜 필요한가
 *
 * BuildingViewer 는 앱 안에서 **네이버 지도 마커 클릭으로만** 열린다
 * (MapShell·PageDashboard 둘 다 `naver.maps.Event.addListener(dot,"click")` 안에서
 * setSel 을 부른다). 그래서 지도 SDK 가 막힌 환경에서는 이 컴포넌트에 닿을 길이
 * 아예 없다 — 렌더가 깨져 있어도 알 수 없다는 뜻이다.
 *
 * 여기서는 그 클릭이 넘기던 것과 **같은 props** 를 백엔드 gold 응답에서 직접 만들어
 * 붙인다. 고정된 픽스처를 쓰지 않는다 — `/api/v1/heatmap/buildings` 를 실제로 불러
 * 실측 층 근거(com_floors·occ_floors·unknown_n)를 그대로 넘긴다. 그래야 파이프라인이
 * 바뀌어 층 배치 규칙이 어긋나면 이 화면에서 드러난다.
 *
 * 두 갈래를 **둘 다** 세운다. 하나만 보면 나머지 절반은 검증되지 않는다:
 *   measured — com_floors 가 있는 건물. placeFloors() 의 실배치 경로
 *   approx   — 층 근거가 없는 건물. approxFloors() 폴백 경로
 *
 * ⚠ 거리뷰(StreetView)는 지도 SDK 를 타므로 이 하네스에서도 뜨지 않는다. 그건 정상이고,
 *   여기서 검증하는 것은 **층 스택과 범례**다.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import BuildingViewer, { placeFloors, type ViewerBuilding } from "@/components/BuildingViewer";
import { getBuildingVacancy, type BuildingProps } from "@/lib/api";
import { colors } from "@/design/tokens/colors";
import "@/styles/tokens.css";

/** PageDashboard.B_STATUS 와 같은 표 — 상태색을 한 곳에서만 정한다는 규칙이 있으나
 *  하네스가 화면 코드를 수정하게 만들지 않으려고 여기서 같은 값을 든다. */
const B_STATUS: Record<string, { color: string; label: string }> = {
  full: { color: colors.vacancy[0], label: "만실" },
  partial: { color: colors.vacancy[2], label: "부분공실" },
  high: { color: colors.vacancy[3], label: "고공실" },
  empty: { color: colors.vacancy[4], label: "공실의심" },
};

/** 폴리곤 외곽선의 무게중심 — 지도에서 마커가 앉던 자리와 같게 계산한다. */
function centroid(ring: [number, number][]): { lat: number; lng: number } {
  const lats = ring.map((r) => r[1]);
  const lngs = ring.map((r) => r[0]);
  return {
    lat: (Math.min(...lats) + Math.max(...lats)) / 2,
    lng: (Math.min(...lngs) + Math.max(...lngs)) / 2,
  };
}

function toViewer(p: BuildingProps, center: { lat: number; lng: number }): ViewerBuilding {
  return {
    name: p.name || "건물",
    capacity: p.capacity,
    active: p.active,
    floors: p.floors,
    statusColor: B_STATUS[p.status]?.color ?? colors.vacancy[4],
    statusLabel: B_STATUS[p.status]?.label,
    center,
    comFloors: p.com_floors ?? undefined,
    occFloors: p.occ_floors ?? undefined,
    unknownN: p.unknown_n ?? undefined,
  };
}

const DISTRICT = new URLSearchParams(location.search).get("district") ?? "garosugil";

function Harness() {
  const [rows, setRows] = React.useState<{ kind: string; b: ViewerBuilding }[] | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    let live = true;
    getBuildingVacancy(DISTRICT)
      .then((fc) => {
        if (!live) return;
        const feats = fc.features as any[];
        const all = feats.map((f) => toViewer(f.properties, centroid(f.geometry.coordinates[0])));

        // 실배치 경로는 **스택의 네 가지 상태(영업·층 미상·공실·비상업)가 가장 많이
        // 나오는 건물**을 고른다. 조건을 손으로 적지 않고 placeFloors() 를 그대로 돌려
        // 세는 이유는, 층 배치 규칙이 바뀌면 고르는 기준도 같이 따라오게 하려는 것이다
        // (규칙을 하네스에 베껴 두면 둘이 갈라진 걸 아무도 모른다).
        // 한 상태만 나오는 건물을 집으면 나머지 세 갈래는 검증되지 않는다 — 실제로
        // 첫 판에 occ_floors 가 빈 건물이 뽑혀 '영업' 층이 한 칸도 없었다.
        const score = (b: ViewerBuilding) => {
          const kinds = placeFloors(b);
          if (!kinds) return -1;
          return new Set(kinds).size * 100 + kinds.length;   // 상태 가짓수 우선, 동률이면 높은 건물
        };
        const measured = all.reduce<ViewerBuilding | null>(
          (best, b) => (score(b) > (best ? score(best) : 0) ? b : best), null);
        const approx = all.find((b) => !b.comFloors || b.comFloors.length === 0) ?? null;

        const out: { kind: string; b: ViewerBuilding }[] = [];
        if (measured) out.push({ kind: "measured", b: measured });
        if (approx) out.push({ kind: "approx", b: approx });
        if (out.length === 0) setErr(`${DISTRICT} 응답에 건물이 없다 — gold 배포 여부를 확인할 것`);
        setRows(out);
      })
      .catch((e) => live && setErr(String(e?.message ?? e)));
    return () => { live = false; };
  }, []);

  if (err) return <div data-testid="harness-error" style={{ padding: 24, color: "#c0392b" }}>{err}</div>;
  if (!rows) return <div data-testid="harness-loading" style={{ padding: 24 }}>불러오는 중…</div>;

  return (
    <div data-testid="harness-ready" style={{ padding: 20, display: "grid", gap: 28, maxWidth: 1100 }}>
      <h1 style={{ font: "700 16px/1.4 Pretendard, sans-serif", margin: 0 }}>
        BuildingViewer 렌더 하네스 · 거점 {DISTRICT} · 실데이터
      </h1>
      {rows.map(({ kind, b }) => (
        <section key={kind} data-testid={`viewer-${kind}`} data-building={b.name}>
          <h2 style={{ font: "700 13px/1.4 Pretendard, sans-serif", margin: "0 0 8px" }}>
            {kind === "measured" ? "실배치(층 근거 있음)" : "근사(층 근거 없음)"} · {b.name}
            {" · "}영업 {b.active}/{b.capacity}호{b.floors ? ` · 지상 ${b.floors}층` : ""}
          </h2>
          <BuildingViewer b={b} />
        </section>
      ))}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Harness />
  </React.StrictMode>,
);

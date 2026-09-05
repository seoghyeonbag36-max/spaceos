// BuildingViewer — 건물 하나를 **2D 층 스택 + 네이버 거리뷰**로 본다 (Page).
//
// 2026-09-05 에 3D 디지털 트윈(BuildingTwin, @react-three/fiber)을 걷어내고 이 자리를
// 대신한다. 트윈이 그리던 절차적 박스는 실측 형상이 아니었다 — 층 상태만 색으로
// 말하고 있었고, 그건 2D 로 더 정확하고 더 싸게 그려진다(번들 832KB → 0).
//
// **3D 를 없앤 것이지 층 표현을 없앤 것이 아니다.** 층 근거(com_floors·occ_floors)를
// 가진 건물이 31,782동이라, 층을 못 그리면 그 실측이 화면에서 통째로 사라진다.
//
// 거리뷰가 채우는 자리는 다른 것이다: "가보지 않고 그 자리의 성격을 본다".
// ⚠ 촬영 시점이 몇 년 전일 수 있어 **공실 판정의 근거가 아니다.** 그래서 촬영일을
//   반드시 같이 그린다 — 안 밝히면 사용자가 눈으로 본 셔터를 현재 상태로 읽는다.
import { useEffect, useRef, useState } from "react";
import { describeNaverMapError, renderStreetView, type PanoramaInfo } from "@/lib/naverMap";
import "./BuildingViewer.css";

export interface ViewerBuilding {
  name: string;
  capacity: number;    // 상가 수용 **호** 수(분모). 층 근거가 있으면 상업 **층** 수
  active: number;      // 영업 **호** 수(분자)
  floors?: number;     // 건축물대장 지상 **층** 수 — 스택의 실제 높이
  statusColor: string; // 공실 상태색
  statusLabel?: string;
  center?: { lat: number; lng: number };   // 거리뷰가 바라볼 대상
  // ── 층 실배치 근거 (gold page_building_master.geojson, 층 근거가 있는 건물만) ──
  comFloors?: number[];
  occFloors?: number[];
  unknownN?: number;
}

const OCCUPIED = "#22B07D";  // 영업(녹색)
const UNCERTAIN = "#F2B441"; // 층 미상 점포가 앉을 수 있는 층
const NON_COM = "#C7D0DB";   // 비상업 층 — 공실률 분모 밖
const MAX_STACK = 20;        // 렌더 상한 (실측 p99 = 20층, 최대 37층)

type FloorKind = "occupied" | "uncertain" | "vacant" | "noncom";

/** 층 번호 → 상태. 층 근거가 없으면 null 을 돌려 근사 렌더로 폴백시킨다.
 *  규칙은 파이프라인(build_page_master._aggregate)과 **같아야** 한다 — 갈라지면
 *  스택의 녹색 층 수와 카드의 공실률이 서로 안 맞는다. */
export function placeFloors(b: ViewerBuilding): FloorKind[] | null {
  const com = b.comFloors;
  if (!com || com.length === 0) return null;

  const occ = new Set(b.occFloors ?? []);
  const comSet = new Set(com);
  const top = Math.max(b.floors || 0, ...com);
  const stack = Math.max(1, Math.min(top, MAX_STACK));

  // 층 미상 점포는 빈 상업층에 낮은 층부터 앉힌다 — 파이프라인과 같은 규칙.
  const uncertain = new Set<number>();
  let spare = b.unknownN ?? 0;
  for (const f of com) {
    if (spare <= 0) break;
    if (!occ.has(f)) { uncertain.add(f); spare -= 1; }
  }

  return Array.from({ length: stack }, (_, i) => {
    const floorNo = i + 1;
    if (!comSet.has(floorNo)) return "noncom";
    if (occ.has(floorNo)) return "occupied";
    if (uncertain.has(floorNo)) return "uncertain";
    return "vacant";
  });
}

/** 층 근거가 없는 건물 — 근사. 점유율만큼 아래부터 채운다. */
function approxFloors(b: ViewerBuilding): FloorKind[] {
  const stack = Math.max(1, Math.min(b.floors || b.capacity, MAX_STACK));
  const ratio = b.capacity > 0 ? Math.min(b.active / b.capacity, 1) : 0;
  const occ = Math.max(0, Math.min(Math.round(stack * ratio), stack));
  return Array.from({ length: stack }, (_, i) => (i < occ ? "occupied" : "vacant"));
}

/** 스택이 실배치인지 근사인지 — 캡션이 근거를 밝히는 데 쓴다. */
export function stackBasis(b: ViewerBuilding): "measured" | "approx" {
  return b.comFloors && b.comFloors.length > 0 ? "measured" : "approx";
}

/** 2D 층 스택 — 위가 꼭대기 층이다(건물과 같은 방향으로 읽히도록 역순으로 그린다). */
export function FloorStack({ b }: { b: ViewerBuilding }) {
  const kinds = placeFloors(b) ?? approxFloors(b);
  const colorOf = (k: FloorKind) =>
    k === "occupied" ? OCCUPIED
      : k === "uncertain" ? UNCERTAIN
        : k === "noncom" ? NON_COM
          : b.statusColor;
  const labelOf = (k: FloorKind) =>
    k === "occupied" ? "영업" : k === "uncertain" ? "층 미상" : k === "noncom" ? "비상업" : "공실";

  return (
    <div className="fstack">
      {kinds.map((_, i) => {
        // 배열은 1층부터인데 화면은 꼭대기부터 그린다 — 건물과 같은 방향으로 읽히도록.
        const floorNo = kinds.length - i;
        const kind = kinds[floorNo - 1];
        return (
          <div key={floorNo} className={"fstack-row " + kind}>
            <span className="fstack-no">{floorNo}F</span>
            <span className="fstack-bar" style={{ background: colorOf(kind) }} />
            <span className="fstack-lb">{labelOf(kind)}</span>
          </div>
        );
      })}
    </div>
  );
}

/** 네이버 거리뷰. 파노라마가 없는 좌표는 정상 상태이므로 폴백 문구를 그린다. */
export function StreetView({ center, name }: { center?: { lat: number; lng: number }; name: string }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [info, setInfo] = useState<PanoramaInfo | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "none" | "error">("loading");
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    if (!center || !ref.current) { setState("none"); return; }
    let live = true;
    let cleanup: (() => void) | null = null;
    setState("loading");
    renderStreetView(ref.current, center)
      .then(({ info: i, destroy }) => {
        cleanup = destroy;
        if (!live) { destroy(); return; }
        setInfo(i);
        setState(i ? "ok" : "none");
      })
      .catch((e) => { if (live) { setErr(describeNaverMapError(e)); setState("error"); } });
    return () => { live = false; cleanup?.(); };
  }, [center?.lat, center?.lng]);

  return (
    <div className="sview">
      <div ref={ref} className="sview-canvas" style={{ display: state === "ok" ? "block" : "none" }} />
      {state === "loading" && <div className="sview-msg">거리뷰 불러오는 중…</div>}
      {state === "none" && (
        <div className="sview-msg">
          이 자리에는 거리뷰가 없다 — 도로에서 떨어진 골목·부지에서 정상적으로 일어난다.
        </div>
      )}
      {state === "error" && <div className="sview-msg err">{err}</div>}
      {state === "ok" && (
        <div className="sview-meta">
          {/* 촬영일을 안 밝히면 사용자가 본 셔터를 현재 상태로 읽는다. 이 목록의
              공실 판정은 대장·점포 데이터에서 나오지 실사에서 나오지 않는다. */}
          {info?.photodate
            ? <><b>{String(info.photodate).slice(0, 10)}</b> 촬영</>
            : <>촬영 시점 미상</>}
          {info?.distanceM != null && <> · {name} 에서 {info.distanceM}m</>}
          {info?.address && <> · {info.address}</>}
          <br />
          <span className="dim">
            거리뷰는 <b>과거 시점의 실사</b>다 — 공실 여부의 근거가 아니다(그건 대장·점포 데이터에서 온다).
          </span>
        </div>
      )}
    </div>
  );
}

/** 층 스택 + 거리뷰를 한 화면에. 두 호출부(MapShell·PageDashboard)가 같은 것을 본다. */
export default function BuildingViewer({ b }: { b: ViewerBuilding }) {
  const measured = stackBasis(b) === "measured";
  return (
    <div className="bviewer">
      <div className="bviewer-cols">
        <div className="bviewer-stack">
          <FloorStack b={b} />
        </div>
        <div className="bviewer-street">
          <StreetView center={b.center} name={b.name} />
        </div>
      </div>
      <div className="bviewer-legend">
        {measured ? (
          <>
            <b style={{ color: OCCUPIED }}>영업</b> = 점포·인허가로 확인된 층
            ({b.occFloors?.join("·") || "없음"})
            {b.unknownN ? <> · <b style={{ color: UNCERTAIN }}>층 미상</b> = 층을 모르는 점포 {b.unknownN}곳이 앉을 수 있는 층</> : null}
            {" · "}<b style={{ color: b.statusColor }}>공실</b>
            {" · "}<b style={{ color: NON_COM }}>비상업</b> = 공실률 분모 밖
            {" · "}상업 {b.comFloors?.length}개 층 중 {b.active}개 영업
            {b.floors ? ` · 지상 ${b.floors}층` : ""}
            <br />
            <span className="dim">근거: 건축물대장 층별개요 + 상가정보 층 표기 — 층 배치는 실측이다</span>
          </>
        ) : (
          <>
            <b style={{ color: OCCUPIED }}>영업</b>(점유율 환산) · <b style={{ color: b.statusColor }}>공실</b>(추정)
            {" · "}{b.active}/{b.capacity}호{b.floors ? ` · 지상 ${b.floors}층` : ""}
            <br />
            <span className="dim">
              이 건물은 층 근거가 없어 <b>아래부터 채운 근사</b>다 — 실제 공실 층과 다를 수 있다
            </span>
          </>
        )}
      </div>
    </div>
  );
}

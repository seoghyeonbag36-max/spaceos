// BuildingTwin — 건물 단위 공실 3D 디지털 트윈 (Page).
// 층 스택으로 건물을 표현한다. 층 근거(com_floors/occ_floors)가 있으면 **실배치**로,
// 없으면 종전 근사(아래부터 채우기)로 폴백한다.
// @react-three/fiber + drei(three) 사용. glTF 실측 모델은 추후 교체(현재 절차적).
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

export interface TwinBuilding {
  name: string;
  capacity: number;    // 상가 수용 **호** 수 (분모) — 층 근거가 있으면 상업 **층** 수
  active: number;      // 영업 **호** 수 (분자)
  floors?: number;     // 건축물대장 지상 **층** 수 — 층 스택의 실제 높이
  statusColor: string; // 공실 상태색
  // ── 층 실배치 근거 (gold page_building_master.geojson, 층 근거가 있는 건물만) ──
  comFloors?: number[]; // 상업 용도 층 번호 — 공실률의 분모가 되는 층
  occFloors?: number[]; // 점포·인허가로 **확인된** 영업 층 번호 (분자 하한)
  unknownN?: number;    // 층 미상 점포로 배정된 층 수 (상한 − 하한)
}

const OCCUPIED = "#22B07D"; // 영업(녹색) — vacancy 색계열 저위험
const UNCERTAIN = "#F2B441"; // 층 미상 점포가 앉을 수 있는 층 (영업∼공실 사이)
const NON_COM = "#C7D0DB";  // 비상업 층 — 공실률 분모 밖이라 회색 처리
const MAX_STACK = 20;       // 렌더 상한 (실측 p99 = 20층, 최대 37층)

type FloorKind = "occupied" | "uncertain" | "vacant" | "noncom";

/** 층 번호 → 상태. 층 근거가 없으면 null 을 돌려 근사 렌더로 폴백시킨다. */
function placeFloors(b: TwinBuilding): FloorKind[] | null {
  const com = b.comFloors;
  if (!com || com.length === 0) return null;

  const occ = new Set(b.occFloors ?? []);
  const comSet = new Set(com);
  // 스택 높이 = 대장 지상층수. 상업층이 그보다 위에 있으면(집합건물 등) 거기까지 그린다.
  const top = Math.max(b.floors || 0, ...com);
  const stack = Math.max(1, Math.min(top, MAX_STACK));

  // 층 미상 점포는 파이프라인과 **같은 규칙**으로 앉힌다: 빈 상업층에 낮은 층부터.
  // 규칙이 어긋나면 트윈의 녹색 층 수와 카드의 vacancy_rate 가 서로 안 맞는다.
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

/** 층 근거가 없는 건물 — 종전 근사. 점유율만큼 아래부터 채운다. */
function approxFloors(b: TwinBuilding): FloorKind[] {
  // 층 수는 대장 지상층수를 쓴다. 예전에는 capacity 를 그대로 층 수로 썼는데 capacity 는
  // **호** 수라 단위가 다르다. 층당 2호 근사(STORES_PER_FLOOR=2) 시절엔 모든 건물이
  // 실제의 2배 높이로 그려졌고, 집합건물은 지금도 어긋난다(낙원상가 267호 = 15층).
  // floors 가 0/누락인 건물만 예전처럼 capacity 로 근사한다.
  const stack = Math.max(1, Math.min(b.floors || b.capacity, MAX_STACK));
  const ratio = b.capacity > 0 ? Math.min(b.active / b.capacity, 1) : 0;
  const occ = Math.max(0, Math.min(Math.round(stack * ratio), stack));
  return Array.from({ length: stack }, (_, i) => (i < occ ? "occupied" : "vacant"));
}

export default function BuildingTwin({ b }: { b: TwinBuilding }) {
  const placed = placeFloors(b);
  const kinds = placed ?? approxFloors(b);
  const H = 1;
  const GAP = 0.06;

  const colorOf = (k: FloorKind) =>
    k === "occupied" ? OCCUPIED
      : k === "uncertain" ? UNCERTAIN
        : k === "noncom" ? NON_COM
          : b.statusColor;
  const opacityOf = (k: FloorKind) =>
    k === "occupied" ? 1 : k === "noncom" ? 0.45 : k === "uncertain" ? 0.7 : 0.82;

  return (
    <Canvas camera={{ position: [6, 6.5, 8], fov: 45 }} dpr={[1, 2]}>
      <ambientLight intensity={0.75} />
      <directionalLight position={[6, 12, 6]} intensity={1.1} />

      {kinds.map((k, i) => (
        <mesh key={i} position={[0, i * (H + GAP) + H / 2, 0]} castShadow>
          {/* 비상업 층은 살짝 좁게 — 색만으로는 분모 밖이라는 게 안 읽힌다 */}
          <boxGeometry args={k === "noncom" ? [2.6, H, 2.6] : [3, H, 3]} />
          <meshStandardMaterial
            color={colorOf(k)}
            transparent
            opacity={opacityOf(k)}
            roughness={0.6}
            metalness={0.05}
          />
        </mesh>
      ))}

      {/* 지면 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
        <planeGeometry args={[24, 24]} />
        <meshStandardMaterial color="#e9eef5" />
      </mesh>

      <OrbitControls enablePan={false} minDistance={5} maxDistance={20} />
    </Canvas>
  );
}

/** 트윈이 실배치인지 근사인지 — 패널 캡션이 근거를 밝히는 데 쓴다. */
export function twinBasis(b: TwinBuilding): "measured" | "approx" {
  return b.comFloors && b.comFloors.length > 0 ? "measured" : "approx";
}

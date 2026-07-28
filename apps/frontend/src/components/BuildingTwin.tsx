// BuildingTwin — 건물 단위 공실 3D 디지털 트윈 (Page).
// 층 스택으로 건물을 표현: 아래 active개 층 = 영업(녹색), 나머지 = 공실(상태색).
// @react-three/fiber + drei(three) 사용. glTF 실측 모델은 추후 교체(현재 절차적 플레이스홀더).
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

export interface TwinBuilding {
  name: string;
  capacity: number;    // 상가 수용 **호** 수 (분모)
  active: number;      // 영업 **호** 수 (분자)
  floors?: number;     // 건축물대장 지상 **층** 수 — 층 스택의 실제 높이
  statusColor: string; // 공실 상태색
}

const OCCUPIED = "#22B07D"; // 영업(녹색) — vacancy 색계열 저위험
const MAX_STACK = 20;       // 렌더 상한 (실측 p99 = 20층, 최대 37층)

export default function BuildingTwin({ b }: { b: TwinBuilding }) {
  // 층 수는 대장 지상층수를 쓴다. 예전에는 capacity 를 그대로 층 수로 썼는데 capacity 는
  // **호** 수라 단위가 다르다. 층당 2호 근사(STORES_PER_FLOOR=2) 시절엔 모든 건물이
  // 실제의 2배 높이로 그려졌고, 집합건물은 지금도 어긋난다(낙원상가 267호 = 15층).
  // floors 가 0/누락인 건물(실측 585/4,502동)만 예전처럼 capacity 로 근사한다.
  const stack = Math.max(1, Math.min(b.floors || b.capacity, MAX_STACK));
  // 점유 층 = 층수 × 점유율. active(호)를 층 인덱스에 그대로 쓰면 단위가 안 맞는다.
  const ratio = b.capacity > 0 ? Math.min(b.active / b.capacity, 1) : 0;
  const occ = Math.max(0, Math.min(Math.round(stack * ratio), stack));
  const H = 1;
  const GAP = 0.06;

  return (
    <Canvas camera={{ position: [6, 6.5, 8], fov: 45 }} dpr={[1, 2]}>
      <ambientLight intensity={0.75} />
      <directionalLight position={[6, 12, 6]} intensity={1.1} />

      {Array.from({ length: stack }).map((_, i) => {
        const occupied = i < occ;
        return (
          <mesh key={i} position={[0, i * (H + GAP) + H / 2, 0]} castShadow>
            <boxGeometry args={[3, H, 3]} />
            <meshStandardMaterial
              color={occupied ? OCCUPIED : b.statusColor}
              transparent
              opacity={occupied ? 1 : 0.82}
              roughness={0.6}
              metalness={0.05}
            />
          </mesh>
        );
      })}

      {/* 지면 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
        <planeGeometry args={[24, 24]} />
        <meshStandardMaterial color="#e9eef5" />
      </mesh>

      <OrbitControls enablePan={false} minDistance={5} maxDistance={20} />
    </Canvas>
  );
}

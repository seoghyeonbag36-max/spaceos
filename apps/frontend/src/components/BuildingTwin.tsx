// BuildingTwin — 건물 단위 공실 3D 디지털 트윈 (Page).
// 층 스택으로 건물을 표현: 아래 active개 층 = 영업(녹색), 나머지 = 공실(상태색).
// @react-three/fiber + drei(three) 사용. glTF 실측 모델은 추후 교체(현재 절차적 플레이스홀더).
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

export interface TwinBuilding {
  name: string;
  capacity: number;   // 상가 수용 호/층 수 (분모)
  active: number;     // 영업 호/층 수 (분자)
  statusColor: string; // 공실 상태색
}

const OCCUPIED = "#22B07D"; // 영업(녹색) — vacancy 색계열 저위험

export default function BuildingTwin({ b }: { b: TwinBuilding }) {
  const floors = Math.max(1, Math.min(b.capacity, 14));
  const occ = Math.max(0, Math.min(b.active, floors));
  const H = 1;
  const GAP = 0.06;

  return (
    <Canvas camera={{ position: [6, 6.5, 8], fov: 45 }} dpr={[1, 2]}>
      <ambientLight intensity={0.75} />
      <directionalLight position={[6, 12, 6]} intensity={1.1} />

      {Array.from({ length: floors }).map((_, i) => {
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

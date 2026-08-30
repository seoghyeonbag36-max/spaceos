/** 거점 선택 — 도시로 묶고, 예외 거점을 표식으로 밝힌다.
 *
 * ## 왜 공용인가
 *
 * 2026-08-30 이전에는 다섯 화면(MapShell·PageDashboard·PlatformConsole·PostingConsole·
 * ProgramStudio)이 각자 `<select>` 를 직접 그렸다. 서울 54거점뿐일 때는 그래도 됐지만
 * 고양·파주가 섞이면서 두 가지가 필요해졌다 — **도시 구분**과 **예외 표시**.
 * 다섯 곳에 흩어 두면 한 곳만 고치고 나머지를 잊는다.
 *
 * ## 무엇을 밝히는가
 *
 * 1. **도시** — `<optgroup>` 으로 묶는다. 서울과 경기 거점을 한 목록에 평평하게 늘어놓으면
 *    사용자가 지금 어느 도시를 보는지 모른다.
 * 2. **예외**(`caveat`) — 두 종류다. 계획상가 밀집(공실 분모가 재고 일부만 덮는다)과
 *    단일시설(공실률이 건물 한 채에 좌우된다). 성격이 다르면 대응도 달라야 하므로
 *    아이콘을 가른다. 문구 전문은 `CaveatNote` 가 상세에서 보여준다.
 * 3. **실측 없음**(`measured_only` + `sentiment === null`) — 0 이 아니라 **재지 않은 것**이다.
 *    옵션 라벨에서 공실률만 보여주고 감성은 아예 적지 않는다.
 */
import type { DistrictSummary } from "@/lib/api";

/** 예외의 종류 — `caveat` 문구 앞머리로 가른다(백엔드가 그렇게 쓴다). */
export type CaveatKind = "mall" | "planned" | null;

export function caveatKind(d: Pick<DistrictSummary, "caveat">): CaveatKind {
  const t = d.caveat ?? "";
  if (!t) return null;
  if (t.startsWith("단일시설")) return "mall";
  return "planned";                    // 계획상가 밀집 · 대표값 한계 등
}

const MARK: Record<Exclude<CaveatKind, null>, string> = {
  mall: "▣",        // 시설 한 채
  planned: "▤",     // 계획상가 밀집
};

/** 목록의 표식이 무엇을 뜻하는지 알려주는 짧은 꼬리표.
 *  `caveat` 문구 자체가 이미 "예외 서빙 —" · "단일시설 상권 —" 처럼 자기 종류를 밝히므로
 *  여기서 같은 말을 반복하지 않는다("▤ 표본 한계 — 대표값 한계 — …" 가 됐던 자리다). */
const KIND_HINT: Record<Exclude<CaveatKind, null>, string> = {
  mall: "이 표식은 시설 한 채가 상권 전체를 좌우한다는 뜻이다",
  planned: "이 표식은 공실 분모가 상업 재고의 일부만 덮는다는 뜻이다",
};

/** 도시 순서 — 서울을 먼저, 나머지는 이름순. 거점 수가 아니라 **원년 도시**가 기준이다. */
function cityOrder(a: string, b: string): number {
  if (a === b) return 0;
  if (a === "seoul") return -1;
  if (b === "seoul") return 1;
  return a.localeCompare(b);
}

export interface DistrictPickerProps {
  districts: DistrictSummary[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
  /** 옵션 라벨 뒤에 붙일 보조 정보. 기본은 공실률. */
  suffix?: (d: DistrictSummary) => string;
  disabled?: boolean;
}

export default function DistrictPicker({
  districts, value, onChange, className, suffix, disabled,
}: DistrictPickerProps) {
  const byCity = new Map<string, DistrictSummary[]>();
  for (const d of districts) {
    const key = d.city ?? "seoul";
    const bucket = byCity.get(key);
    if (bucket) bucket.push(d);
    else byCity.set(key, [d]);
  }
  const cities = [...byCity.keys()].sort(cityOrder);

  const tail = suffix ?? ((d: DistrictSummary) =>
    // 공실률은 실측이 있을 때만. 없는 값을 0 으로 그리지 않는다.
    Number.isFinite(d.vacancy_rate) ? `공실 ${d.vacancy_rate.toFixed(1)}%` : "실측 없음");

  return (
    <select
      className={className}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      {cities.map((city) => {
        const rows = byCity.get(city)!;
        // 도시가 하나뿐이면 묶음 라벨이 소음이다 — 그때는 평평하게 그린다.
        const label = `${rows[0]?.city_name ?? city} (${rows.length})`;
        const options = rows.map((d) => {
          const kind = caveatKind(d);
          const mark = kind ? `${MARK[kind]} ` : "";
          return (
            <option key={d.id} value={d.id}>
              {mark}{d.name} · {tail(d)}
            </option>
          );
        });
        return cities.length === 1
          ? <optgroup key={city} label={label}>{options}</optgroup>
          : <optgroup key={city} label={label}>{options}</optgroup>;
      })}
    </select>
  );
}

/** 선택된 거점의 예외 문구 — 목록의 표식이 무엇을 뜻하는지 여기서 전문으로 밝힌다.
 *
 * 배지만 달고 문구를 숨기면 사용자는 표식의 뜻을 모른 채 숫자를 그대로 믿는다.
 * 이 저장소가 `vacancy_source` · 시드 배지로 지켜 온 원칙 — **합성값을 실측처럼 보이지
 * 않게 한다** — 의 화면 쪽 절반이다.
 */
export function CaveatNote({ district }: { district?: DistrictSummary | null }) {
  if (!district?.caveat) return null;
  const kind = caveatKind(district);
  if (!kind) return null;
  return (
    <p className={`caveat-note caveat-${kind}`} role="note">
      <strong title={KIND_HINT[kind]}>{MARK[kind]}</strong> {district.caveat}
    </p>
  );
}

/** 실측이 없는 축을 그리는 자리. `0` 과 `재지 않음` 을 절대 같게 그리지 않는다.
 *
 * 경기 거점은 감성구역·LSTM 예측 소스가 없어 `sentiment` · `predicted_rate` 가 null 이다.
 * 그 자리에 0 을 찍으면 "쟀더니 0" 으로 읽힌다 — 서울 거점과 나란히 놓이면 특히 그렇다.
 */
export function MeasuredValue({
  value, unit = "", digits = 1, absent = "실측 없음",
}: { value?: number | null; unit?: string; digits?: number; absent?: string }) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return <span className="value-absent" title="이 거점에는 해당 소스가 없다">{absent}</span>;
  }
  return <span>{value.toFixed(digits)}{unit}</span>;
}

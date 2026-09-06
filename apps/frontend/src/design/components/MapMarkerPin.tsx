// 공실 위험도 마커 — 네이버 지도 위 커스텀 오버레이. vacancy 색계열 사용.
//
// ⚠ 2026-09-06: 이 파일은 두 형태를 **같은 출처**에서 낸다.
//   - `vacancyDotHTML()` — 네이버 SDK 용. `naver.maps.Marker` 의 `icon.content` 는
//     React 엘리먼트가 아니라 **HTML 문자열**을 받으므로 컴포넌트를 그대로 못 쓴다.
//     지도 위 실제 마커는 이쪽이다.
//   - `MapMarkerPin` — Storybook·일반 DOM 용 React 컴포넌트.
//   둘이 갈라지면 지도와 문서의 마커가 달라지므로 색·크기 계산을 한 곳에 둔다.
//
// ⚠ 종전 이 컴포넌트는 Tailwind 유틸리티 클래스(`flex flex-col items-center`,
//   `px-2 h-6`, `text-[11px]`)로 짜여 있었는데 이 저장소에는 **tailwindcss 가 설치돼
//   있지 않다**(`@tailwind` 지시문 0개). 설정만 남아 있던 `tailwind.config.ts` 는
//   2026-09-06 에 삭제했다. 그래서 그 클래스들은
//   아무것도 하지 않았고 컴포넌트는 스타일 없이 그려졌다. 인라인 스타일로 바꿨다.
import { colors } from "../tokens/colors";

/** level: 0(저위험)~4(고위험) — colors.vacancy 색계열의 인덱스 */
export type VacancyLevel = 0 | 1 | 2 | 3 | 4;

/**
 * 지도 위 공실 점(red dot)의 HTML. 네이버 SDK `icon.content` 에 그대로 넣는다.
 * 흰 테두리 + 이중 그림자는 위성/일반 지도 어느 배경에서도 점이 묻히지 않게 한다.
 */
export function vacancyDotHTML(color: string, size = 13): string {
  return (
    `<div style="width:${size}px;height:${size}px;border-radius:50%;`
    + `background:${color};border:1.5px solid #fff;`
    + `box-shadow:0 0 0 1px rgba(0,0,0,.12),0 1px 3px rgba(0,0,0,.35);opacity:.92"></div>`
  );
}

/** 점의 앵커 오프셋 — 테두리 1.5px 를 포함한 중심. SDK 의 `icon.anchor` 에 쓴다. */
export const vacancyDotAnchor = (size = 13) => size / 2 + 1.5;

export function MapMarkerPin({ level = 0, label }: { level?: VacancyLevel; label?: string }) {
  const c = colors.vacancy[level];
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
      filter: "drop-shadow(0 2px 6px rgba(0,0,0,.25))" }}>
      <div style={{ background: c, borderRadius: 999, height: 24, padding: "0 8px",
        display: "flex", alignItems: "center", color: "#fff", fontSize: 11, fontWeight: 600 }}>
        {label ?? ""}
      </div>
      <div style={{ width: 0, height: 0, borderLeft: "6px solid transparent",
        borderRight: "6px solid transparent", borderTop: `8px solid ${c}` }} />
    </div>
  );
}

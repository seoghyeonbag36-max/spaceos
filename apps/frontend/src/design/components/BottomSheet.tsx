// 바텀시트 — 지도 위에서 상권/상가 정보를 끌어올리는 한국형 앱 패턴.
//
// 2026-09-13: Card·Button 과 **같은 병**을 앓고 있었다. `fixed inset-x-0 bottom-0
// bg-surface rounded-t-lg p-4` 같은 Tailwind 유틸리티 클래스만 들고 있는데 이 저장소에는
// tailwindcss 가 없어(2026-09-06 에 죽은 설정을 삭제) 스타일이 **하나도 걸리지 않았다**.
// 2026-09-06 에 Card·Button 을 design.css 로 옮길 때 여기는 남았고, 그래서 이 컴포넌트는
// 만들어진 뒤로 어느 화면에도 투입되지 못했다. 스타일을 design.css 로 옮겨 되살린다.
//
// 왜 되살리는가 — 토스 TDS 는 다이얼로그/바텀시트 중 무엇인지를 컴포넌트 체크리스트
// 항목으로 둘 만큼 이 선택을 중요하게 본다. 안드로이드에서 **바텀시트가 메뉴보다
// 아이템 클릭율 10% 높았다**. MapShell 의 모바일 표면이 여기에 선다
// → design/references/INDEX.md §1-6(토스 TDS) · §2-6(Airbnb).
//
// ⚠ 닫힌 상태는 화면 밖으로 내리는 것만으로 부족하다. 그 자리에 남아 지도 클릭을
//   가로채므로 `pointer-events: none` 이 같이 걸린다(design.css).
import React from "react";
import "./design.css";

export function BottomSheet({
  open, title, className = "", children, ...rest
}: {
  open: boolean;
  title?: string;
  className?: string;
  children: React.ReactNode;
} & Omit<React.HTMLAttributes<HTMLDivElement>, "title" | "className" | "children">) {
  return (
    <div
      role="dialog"
      aria-hidden={!open}
      aria-label={title}
      className={`ds-sheet ${className}`.trim()}
      {...rest}
    >
      {/* 끌어올리는 손잡이. 실제 드래그 제스처는 아직 없다 — 시각 단서만 둔다. */}
      <div className="ds-sheet-grip" aria-hidden />
      {title && <h2 className="ds-sheet-title">{title}</h2>}
      {children}
    </div>
  );
}

// 바텀시트 — 지도 위에서 상권/상가 정보를 끌어올리는 한국형 앱 패턴.
import React from "react";
export function BottomSheet({ open, title, children }:
  { open: boolean; title?: string; children: React.ReactNode }) {
  return (
    <div
      role="dialog" aria-hidden={!open}
      className="fixed inset-x-0 bottom-0 bg-surface rounded-t-lg p-4 transition-transform"
      style={{ boxShadow: "var(--shadow-sheet)", transform: open ? "translateY(0)" : "translateY(100%)" }}
    >
      <div className="mx-auto mb-3 h-1 w-10 rounded-pill bg-line" style={{ borderRadius: 999 }} />
      {title && <h2 className="text-[20px] font-bold text-ink mb-2">{title}</h2>}
      {children}
    </div>
  );
}

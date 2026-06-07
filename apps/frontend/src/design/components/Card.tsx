// 카드 — 지도 위 정보 패널/리스트 기본 컨테이너
import React from "react";
export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-surface rounded-lg shadow-card border border-line p-4 ${className}`}>
      {children}
    </div>
  );
}

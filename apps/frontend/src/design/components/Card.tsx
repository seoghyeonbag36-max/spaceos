// 카드 — 지도 위 정보 패널/리스트 기본 컨테이너
// 2026-09-06: Tailwind 유틸리티 클래스(bg-surface/rounded-lg/p-4 …)로만 짜여 있었는데
// 이 저장소에는 tailwindcss 가 없어 스타일이 하나도 걸리지 않았다 → design.css 로 옮겼다.
// 공개 props 는 그대로다({ children, className }).
import React from "react";
import "./design.css";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`ds-card ${className}`.trim()}>{children}</div>;
}

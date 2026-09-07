// SpaceOS 기본 버튼 — 토큰 기반. variant 로 네이버/브랜드 맥락 구분.
// naver variant 는 '네이버 연동 액션'(길찾기 등)에만 사용. 네이버페이 결제는 NaverPayButton 사용.
//
// 2026-09-06: Tailwind 유틸리티 클래스로만 짜여 있었는데 이 저장소에는 tailwindcss 가
// 없어 스타일이 하나도 걸리지 않았다 → design.css 로 옮겼다. 공개 props 는 그대로다.
// 또한 종전에는 className 을 `{...rest}` 로 뒤에 펴서, 호출부가 className 을 넘기면
// 버튼 자기 스타일이 **통째로 지워졌다**(JSX 스프레드는 뒤가 이긴다). 이제 병합한다.
import React from "react";
import "./design.css";

type Variant = "brand" | "naver" | "ghost";

export function Button({
  variant = "brand", children, className = "", ...rest
}: { variant?: Variant } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={`ds-btn ds-btn-${variant} ${className}`.trim()} {...rest}>
      {children}
    </button>
  );
}

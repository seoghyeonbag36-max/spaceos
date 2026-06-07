// SpaceOS 기본 버튼 — 토큰 기반. variant 로 네이버/브랜드 맥락 구분.
// naver variant 는 '네이버 연동 액션'(길찾기 등)에만 사용. 네이버페이 결제는 NaverPayButton 사용.
import React from "react";

type Variant = "brand" | "naver" | "ghost";
const styles: Record<Variant, string> = {
  brand: "bg-brand text-white hover:bg-brand-pressed",
  naver: "bg-naver text-white hover:bg-naver-pressed",
  ghost: "bg-transparent text-ink border border-line hover:bg-bg",
};

export function Button({
  variant = "brand", children, ...rest
}: { variant?: Variant } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 h-11 px-5 rounded-md
        text-[15px] font-semibold transition-colors disabled:opacity-50 ${styles[variant]}`}
      {...rest}
    >
      {children}
    </button>
  );
}

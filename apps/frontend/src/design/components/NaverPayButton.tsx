// ⚠ 네이버페이 결제 버튼 — 공식 디자인 고정 슬롯.
// 네이버페이 정책상 버튼 색·모양·문구를 임의 변경하면 패널티. 공식 에셋/스크립트만 사용한다.
// 우리는 주변 여백·정렬만 토큰으로 맞춘다. (결제 플로우는 backend payments.py 와 연동)
import React from "react";

export function NaverPayButton({ onPay }: { onPay?: () => void }) {
  // TODO: 네이버페이 공식 버튼 SDK/에셋으로 교체 (design/assets/naverpay/ 의 원본 사용)
  // 아래는 위치·간격 확인용 자리표시자 — 실제 배포에서는 공식 버튼으로 대체할 것.
  return (
    <div className="w-full" data-naverpay-slot>
      <button
        onClick={onPay}
        className="w-full h-12 rounded-md bg-naver text-white text-[15px] font-bold"
        aria-label="네이버페이로 결제"
      >
        {/* TODO: 공식 'N Pay' 로고 에셋 삽입 */}
        네이버페이 결제 (공식 버튼으로 교체 예정)
      </button>
    </div>
  );
}

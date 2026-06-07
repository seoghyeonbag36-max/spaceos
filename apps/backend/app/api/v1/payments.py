"""네이버페이 결제 연동 (스텁) — DaaS 구독 / 리포트 단건 / 성공보수 정산.

플로우: reserve(예약) → 사용자 인증 → apply(승인, paymentId) → 정산 조회
개발자센터: https://developer.pay.naver.com/
"""
import os
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

# TODO: .env 에서 로드
NAVER_PAY_CLIENT_ID = os.getenv("NAVER_PAY_CLIENT_ID", "")
NAVER_PAY_CLIENT_SECRET = os.getenv("NAVER_PAY_CLIENT_SECRET", "")


class ReserveRequest(BaseModel):
    product_name: str          # 예: "SpaceOS DaaS 월 구독" / "성수동 상권 리포트"
    total_pay_amount: int      # 결제 금액(원)
    return_url: str            # 인증 후 콜백


@router.post("/reserve")
async def reserve_payment(req: ReserveRequest):
    """① 결제 예약 → reserveId 반환. TODO: 네이버페이 reserve API 호출."""
    # TODO: POST https://dev.apis.naver.com/{partner}/naverpay/payments/v2.2/reserve
    return {"reserveId": "STUB-RESERVE-ID", "echo": req.model_dump()}


@router.post("/apply/{payment_id}")
async def apply_payment(payment_id: str):
    """③ 결제 승인. TODO: paymentId 로 apply 호출 후 거래완료 처리."""
    # TODO: POST .../payments/v2.2/apply/payment  body={paymentId}
    return {"paymentId": payment_id, "status": "STUB-APPLIED"}

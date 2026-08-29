"""Program 상용 입력 온보딩 — 조직 동의 영수증만 남기고 원문은 저장하지 않는다."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.security import Principal
from app.models.auth import AuditLog
from app.schemas.marketing import ProgramCommercialOnboardingRequest
from app.services import marketing

CONTRACT_VERSION = "spaceos.program-onboarding/1"
AUDIT_ACTION = "program.onboarding.accepted"


def generate(
    db: Session,
    principal: Principal,
    request: ProgramCommercialOnboardingRequest,
) -> dict:
    """점주 제공 입력으로 생성하고 최소 동의 메타데이터만 감사로그에 남긴다.

    리뷰·사진 URL·메뉴·키워드 원문은 ``AuditLog.detail`` 에 넣지 않는다. LLM 호출을
    포함한 생성 요청이 끝난 뒤에도 애플리케이션 DB에는 조직, 계약 버전, 입력 종류별
    **건수**만 남는다. 감사로그 기록이 실패하면 영수증 없는 상용 처리가 되므로 요청을
    성공시키지 않고 예외를 그대로 올린다.
    """
    profile = request.profile
    counts = {
        "reviews": len(profile.reviews),
        "image_urls": len(profile.image_urls),
        "menu": len(profile.menu),
        "keywords": len(profile.keywords),
        "venture": int(profile.venture is not None),
    }
    detail = json.dumps({
        "contract_version": CONTRACT_VERSION,
        "input_source": "merchant-provided",
        "processing_purpose": request.consent.processing_purpose,
        "raw_input_retention": request.consent.raw_input_retention,
        "consents": {
            "process": request.consent.consent_to_process,
            "rights": request.consent.rights_confirmed,
            "external_model": request.consent.allow_external_model_processing,
        },
        "district_id": profile.district_id,
        "counts": counts,
        "raw_input_persisted": False,
    }, ensure_ascii=False, separators=(",", ":"))

    receipt = AuditLog(
        org_id=principal.org.id,
        user_id=principal.user.id if principal.user else None,
        action=AUDIT_ACTION,
        detail=detail,
    )
    db.add(receipt)
    try:
        db.commit()
        db.refresh(receipt)
    except Exception:
        db.rollback()
        raise

    # 감사 영수증을 먼저 확정한다. 외부 모델 호출 뒤 commit 이 실패하면 요청은 5xx 여도
    # 원문은 이미 외부로 나간 상태가 된다. 순서를 뒤집어 영수증 없는 처리를 막는다.
    generated = marketing.generate_store_marketing(profile.model_dump())

    return {
        "onboarding_id": receipt.id,
        "org_id": principal.org.id,
        "accepted_at": receipt.created_at,
        "contract_version": CONTRACT_VERSION,
        "input_source": "merchant-provided",
        "raw_input_persisted": False,
        "marketing": generated,
    }

from fastapi import APIRouter

from .register_user import router as register_router
from .verify_email import router as verify_email_router

router = APIRouter()
router.include_router(register_router, prefix="/register", tags=["register"])
router.include_router(verify_email_router, prefix="/verify_email", tags=["register"])
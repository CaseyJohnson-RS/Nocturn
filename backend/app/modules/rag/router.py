from fastapi import APIRouter

from app.common.dependencies import DBSession
from app.middleware.auth import AuthUser
from app.modules.rag.schemas import SearchRequest, SearchResponse
from app.modules.rag.service import RAGService

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/search", response_model=SearchResponse)
async def search(body: SearchRequest, user: AuthUser, db: DBSession):
    service = RAGService(db)
    return await service.search(user.id, body.query, body.limit)

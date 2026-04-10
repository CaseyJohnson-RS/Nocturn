from typing import Annotated

from fastapi import APIRouter, Depends

from app.common.dependencies import DBSession
from app.middleware.auth import AuthUser
from app.modules.rag.schemas import SearchRequest, SearchResponse
from app.modules.rag.service import RAGService

router = APIRouter(prefix="/api/rag", tags=["rag"])


async def get_rag_service(db: DBSession) -> RAGService:
    return RAGService(db)


RAGServiceDep = Annotated[RAGService, Depends(get_rag_service)]


@router.post("/search", response_model=SearchResponse)
async def search(body: SearchRequest, user: AuthUser, service: RAGServiceDep):
    return await service.search(user.id, body.query, body.limit)
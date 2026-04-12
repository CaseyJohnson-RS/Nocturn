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


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic search",
)
async def search(body: SearchRequest, user: AuthUser, service: RAGServiceDep):
    """Search the user's notes using semantic (vector) similarity.

    The query is embedded and compared against pre-computed note chunk
    embeddings using cosine similarity. Only the current user's notes
    are searched.

    Returns up to `limit` results ordered by relevance score (highest first).
    Each result contains the matching chunk text and its parent `note_id`,
    which can be used to fetch the full note.

    **Note:** embeddings are computed asynchronously by the background
    worker. Newly created or recently edited notes may take up to 30
    seconds to become searchable.
    """
    return await service.search(user.id, body.query, body.limit)

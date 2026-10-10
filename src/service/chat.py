"""
Chat service — wraps the streaming RAG chain with workspace-scoped retrieval.
"""

from typing import AsyncGenerator, Optional

from core.retriever import HybridRetriever, get_vector_store
from core.chain import stream_rag_response
import structlog

log = structlog.get_logger()


class ChatService:
    @staticmethod
    async def stream(
            query: str,
            conversation_id: str,
            workspace_id: str,
            user_id: Optional[str] = None,
            filename: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream SSE tokens for a RAG chat response.
        Yields SSE-formatted strings.
        """
        vs = get_vector_store()
        retriever = HybridRetriever(vector_store=vs)

        async for token in stream_rag_response(
                query=query,
                conversation_id=conversation_id,
                retriever=retriever,
                workspace_id=workspace_id,
                user_id=user_id,
                filename=filename,
        ):
            yield token
"""
Streaming RAG chain.

Flow:
  query → HybridRetriever → format context → build prompt
       → Ollama Cloud LLM (streaming) → SSE tokens

Memory: RedisChatMessageHistory keyed by conversation_id.
"""
from typing import AsyncGenerator, List, Optional
import json
import structlog

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.documents import Document
from langchain_community.chat_message_histories import RedisChatMessageHistory

from config.settings import settings
from core.retriever import HybridRetriever

log = structlog.get_logger()

SYSTEM_PROMPT = """You are Pico, a helpful AI assistant that answers questions based on the provided document context.

Rules:
- Answer ONLY using the provided context. Do not make up information.
- If the context does not contain enough information, say so clearly.
- Be concise and structured. Use markdown formatting when helpful.
- At the end of your answer, list the source documents you used in this exact format:
  [source: filename.md | Section: heading]
- Keep your answer focused and relevant to the question.
"""


def _get_llm(streaming: bool = True) -> ChatOpenAI:
    """Return the Ollama Cloud LLM (OpenAI-compatible endpoint)."""
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.ollama_cloud_url,
        api_key=settings.ollama_api_key or "ollama",
        temperature=settings.llm_temperature,
        streaming=streaming,
        max_retries=2,
    )


def _get_history(conversation_id: str) -> RedisChatMessageHistory:
    """Return a RedisChatMessageHistory for the given conversation."""
    return RedisChatMessageHistory(
        session_id=f"pico:chat:{conversation_id}",
        url=settings.redis_url,
        ttl=settings.redis_ttl_hours * 3600,
    )


def _trim_history(history: RedisChatMessageHistory) -> List[BaseMessage]:
    """Return at most redis_max_messages recent messages from history."""
    try:
        messages = history.messages
        max_msgs = settings.redis_max_messages
        if len(messages) > max_msgs:
            return messages[-max_msgs:]
        return messages
    except Exception as e:
        log.warning("redis_get_messages_failed", error=str(e))
        return []


def _format_context(docs: List[Document]) -> str:
    """Format retrieved documents into a context string."""
    if not docs:
        return "No relevant context found."
    parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        filename = meta.get("filename", "unknown")
        heading = meta.get("heading", "")
        header = f"[{i}] Source: {filename}"
        if heading:
            header += f" | Section: {heading}"
        parts.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


async def stream_rag_response(
        query: str,
        conversation_id: str,
        retriever: HybridRetriever,
        workspace_id: str,
        user_id: Optional[str] = None,
        filename: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream RAG response as SSE-compatible strings.
    Yields:
      data: {"token": "..."}\n\n  — for each token
      data: [SOURCES]<json>\n\n    — after last token with source list
      data: [DONE]\n\n             — sentinel
    """
    # 1. Retrieve context
    docs = retriever.retrieve(
        query=query,
        workspace_id=workspace_id,
        user_id=user_id,
        filename=filename,
    )
    context = _format_context(docs)

    # 2. Build messages
    history = _get_history(conversation_id)
    past_messages = _trim_history(history)

    messages: List[BaseMessage] = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=f"Context:\n{context}"),
        *past_messages,
        HumanMessage(content=query),
    ]

    log.info("LLM message as request: ", messages=messages)

    # 3. Stream LLM response
    llm = _get_llm(streaming=True)
    full_response = ""

    try:
        async for chunk in llm.astream(messages):
            token = chunk.content
            if token:
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"
    except Exception as e:
        log.error("llm_stream_error", error=str(e))
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # 4. Save to Redis history
    try:
        history.add_user_message(query)
        history.add_ai_message(full_response)
    except Exception as e:
        log.warning("redis_history_save_failed", error=str(e))

    # 5. Build and emit sources
    sources = []
    seen = set()
    for doc in docs:
        meta = doc.metadata
        key = (meta.get("filename", ""), meta.get("heading", ""), meta.get("chunk_index", 0))
        if key not in seen:
            seen.add(key)
            sources.append({
                "filename": meta.get("filename", "unknown"),
                "heading": meta.get("heading"),
                "chunk_index": meta.get("chunk_index", 0),
                "score": 1.0,
            })

    yield f"data: [SOURCES]{json.dumps(sources)}\n\n"
    yield "data: [DONE]\n\n"

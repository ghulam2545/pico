"""
Redis chat memory service.
Wraps langchain_community RedisChatMessageHistory.
"""
from typing import List
import redis
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import BaseMessage

from config.settings import settings
import structlog

log = structlog.get_logger()


def _session_key(conversation_id: str) -> str:
    """Builds the Redis key for a conversation."""
    return f"pico:chat:{conversation_id}"


class RedisMemoryService:

    @staticmethod
    def get_history(conversation_id: str) -> RedisChatMessageHistory:
        """Returns the Redis chat history for a conversation."""
        return RedisChatMessageHistory(
            session_id=_session_key(conversation_id),
            url=settings.redis_url,
            ttl=settings.redis_ttl_hours * 3600,
        )

    @staticmethod
    def get_messages(conversation_id: str) -> List[BaseMessage]:
        """Returns the latest messages from a conversation."""
        try:
            history = RedisMemoryService.get_history(conversation_id)
            messages = history.messages
            max_msgs = settings.redis_max_messages
            return messages[-max_msgs:] if len(messages) > max_msgs else messages
        except Exception as e:
            log.warning("redis_get_messages_failed", error=str(e))
            return []

    @staticmethod
    def clear(conversation_id: str) -> None:
        """Clears all messages from a conversation."""
        try:
            history = RedisMemoryService.get_history(conversation_id)
            history.clear()
            log.info("redis_history_cleared", conversation_id=conversation_id)
        except Exception as e:
            log.warning("redis_clear_failed", error=str(e))

    @staticmethod
    def ping() -> bool:
        """Returns True if Redis is reachable."""
        try:
            r = redis.from_url(settings.redis_url, socket_timeout=2)
            return bool(r.ping())
        except Exception as e:
            log.warning("redis_ping_ping_failed", error=str(e))
            return False

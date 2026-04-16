"""
Service for managing chat interactions and history.
"""

import logging
from typing import List

from runestone.agents.manager import AgentsManager
from runestone.agents.schemas import ChatHistoryResponse
from runestone.agents.schemas import ChatMessage as ChatMessageSchema
from runestone.agents.schemas import TeacherEmotion
from runestone.config import Settings
from runestone.core.exceptions import RunestoneError
from runestone.core.observability import timed_operation
from runestone.core.processor import RunestoneProcessor
from runestone.db.chat_repository import ChatRepository
from runestone.services.agent_side_effect_service import AgentSideEffectService
from runestone.services.tts_service import TTSService
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService

logger = logging.getLogger(__name__)


def _process_message_timing_fields(args, kwargs, _result, _error) -> dict[str, int | None]:
    """Extract stable log fields for the per-turn timing decorator."""
    user_id = kwargs.get("user_id") if "user_id" in kwargs else (args[1] if len(args) > 1 else None)
    message_text = kwargs.get("message_text") if "message_text" in kwargs else (args[2] if len(args) > 2 else "")
    return {
        "user_id": user_id,
        "message_chars": len(message_text),
    }


class ChatService:
    """
    Service layer for chat-turn orchestration and history APIs.

    `ChatService` owns request-level workflow: resolving the active chat session,
    persisting messages, loading agent context, and returning API-facing history
    metadata. Agent planning/execution stays in `AgentsManager`; persistence stays
    in repository and domain services.
    """

    def __init__(
        self,
        settings: Settings,
        repository: ChatRepository,
        side_effect_service: AgentSideEffectService,
        user_service: UserService,
        agent_service: AgentsManager,
        processor: RunestoneProcessor,
        vocabulary_service: VocabularyService,
        tts_service: TTSService,
        memory_item_service,
    ):
        """
        Wire together the collaborators needed for a full chat turn.

        The service itself stays intentionally thin: it coordinates request flow
        and business rules, while delegating persistence, OCR, TTS, and agent
        execution to dedicated services.
        """
        self.settings = settings
        self.repository = repository
        self.side_effect_service = side_effect_service
        self.user_service = user_service
        self.agent_service = agent_service
        self.processor = processor
        self.vocabulary_service = vocabulary_service
        self.tts_service = tts_service
        self.memory_item_service = memory_item_service

    @timed_operation(logger, "[chat:service] Message turn completed", fields_factory=_process_message_timing_fields)
    async def process_message(
        self,
        user_id: int,
        message_text: str,
        tts_expected: bool = False,
        speed: float = 1.0,
    ) -> tuple[str, list[dict] | None, TeacherEmotion]:
        """
        Process one text chat turn end to end.

        The method persists the user message first so the database remains the
        source of truth for the turn, then loads history for the agent and hands
        orchestration to `AgentsManager`. The manager returns the assistant reply
        immediately and schedules any post-turn specialist work in the background.

        Args:
            user_id: Authenticated user whose active chat session should receive the turn.
            message_text: Raw user message content for the current turn.
            tts_expected: Whether the caller expects audio for the assistant reply.
            speed: Speech playback multiplier passed to TTS generation, where `1.0`
                means normal playback speed.
        """

        # 1. Resolve current chat session and save user message
        chat_id = await self.get_or_create_current_chat_id(user_id)
        await self.repository.add_message(user_id, chat_id, "user", message_text)

        # 2. Truncate old messages
        await self.repository.truncate_history(
            user_id, self.settings.chat_history_retention_days, preserve_chat_id=chat_id
        )

        # 3. Fetch context for agent
        context_models = await self.repository.get_context_for_agent(user_id, chat_id)

        # Convert models to schemas for the agent service
        history = [
            ChatMessageSchema(
                id=m.id,
                role=m.role,
                content=m.content,
                sources=m.sources,
                teacher_emotion=m.teacher_emotion,
                created_at=m.created_at,
            )
            for m in context_models
        ]

        # 4. Get user and build memory context
        user = await self.user_service.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # 5. Generate response using agents
        assistant_text, sources, teacher_emotion = await self.agent_service.process_turn(
            message=message_text,
            chat_id=chat_id,
            history=history[:-1],
            user=user,
            memory_item_service=self.memory_item_service,
            side_effect_service=self.side_effect_service,
        )

        # 6. Save assistant message
        await self.repository.add_message(
            user_id,
            chat_id,
            "assistant",
            assistant_text,
            sources=sources,
            teacher_emotion=teacher_emotion,
        )

        # 7. Push TTS audio if client expects it (non-blocking)
        if tts_expected:
            await self.tts_service.push_audio_to_client(user_id, assistant_text, speed=speed)

        return assistant_text, sources, teacher_emotion

    async def process_image_message(self, user_id: int, image_content: bytes) -> tuple[str, TeacherEmotion]:
        """
        OCR an uploaded image and route the extracted text through the teacher flow.

        Image uploads do not create a separate user chat message today. Instead we
        build an explicit translation prompt from OCR output and process it as a
        normal agent turn so post-turn specialist handling stays consistent.

        Args:
            user_id: Authenticated user whose active chat session should receive the reply.
            image_content: Uploaded image bytes that will be sent through OCR.
        """
        # 1. Run OCR on image content (async)
        ocr_result = await self.processor.run_ocr(image_content)

        if not ocr_result.transcribed_text or not ocr_result.transcribed_text.strip():
            logger.warning("OCR returned empty text")
            raise RunestoneError("Could not recognize text from image")

        logger.info(f"OCR extracted {len(ocr_result.transcribed_text)} characters")
        ocr_text = ocr_result.transcribed_text

        # 2. Resolve current chat session and truncate old messages
        chat_id = await self.get_or_create_current_chat_id(user_id)
        await self.repository.truncate_history(
            user_id, self.settings.chat_history_retention_days, preserve_chat_id=chat_id
        )

        # 3. Fetch context for agent
        context_models = await self.repository.get_context_for_agent(user_id, chat_id)

        # Convert models to schemas for the agent service
        history = [
            ChatMessageSchema(
                id=m.id,
                role=m.role,
                content=m.content,
                teacher_emotion=m.teacher_emotion,
                created_at=m.created_at,
            )
            for m in context_models
        ]

        # 4. Get user and build memory context
        user = await self.user_service.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # 5. Build translation prompt with OCR text
        mother_tongue = user.mother_tongue or "English"
        translation_prompt = f"""User uploaded an image with Swedish text. Please translate it phrase-by-phrase.

OCR Text:
{ocr_text}

Instructions:
1. Start your response with an intro like "Here's the translated text from your image:" (in {mother_tongue})
2. Then provide phrase-by-phrase translation in format: "Swedish phrase (translation). Next phrase (translation)."
3. Use {mother_tongue} for all translations."""

        assistant_text, _sources, teacher_emotion = await self.agent_service.process_turn(
            message=translation_prompt,
            chat_id=chat_id,
            history=history,
            user=user,
            memory_item_service=self.memory_item_service,
            side_effect_service=self.side_effect_service,
        )

        await self.repository.add_message(
            user_id,
            chat_id,
            "assistant",
            assistant_text,
            teacher_emotion=teacher_emotion,
        )

        return assistant_text, teacher_emotion

    # ------------------------------------------------------------------
    # Chat session management
    # ------------------------------------------------------------------

    async def get_or_create_current_chat_id(self, user_id: int) -> str:
        """Return the active chat session id, creating one if needed."""
        return await self.user_service.get_or_create_current_chat_id(user_id)

    async def start_new_chat(self, user_id: int) -> str:
        """Rotate the user onto a fresh chat session id."""
        return await self.user_service.rotate_current_chat_id(user_id)

    async def clear_history(self, user_id: int) -> str:
        """Backward-compatible alias for starting a new chat session."""
        return await self.start_new_chat(user_id)

    async def get_latest_id(self, user_id: int, chat_id: str) -> int:
        """Return the newest persisted message id for a chat session."""
        return await self.repository.get_latest_id(user_id, chat_id)

    async def get_oldest_id(self, user_id: int, chat_id: str) -> int:
        """Return the oldest persisted message id still retained for a chat session."""
        return await self.repository.get_oldest_id(user_id, chat_id)

    async def get_history(
        self, user_id: int, chat_id: str, after_id: int = 0, limit: int = 200
    ) -> List[ChatMessageSchema]:
        """
        Load validated chat history records for one session.

        Repository models are converted into API-facing schemas here so callers do
        not need to care about persistence details.

        Args:
            user_id: Authenticated user who owns the chat session.
            chat_id: Chat session identifier to read from.
            after_id: Optional cursor; only messages with a larger id are returned.
            limit: Maximum number of messages to return.
        """
        history = await self.repository.get_history_after_id(user_id, chat_id, after_id=after_id, limit=limit)
        return [ChatMessageSchema.model_validate(message) for message in history]

    async def get_history_response(
        self,
        user_id: int,
        after_id: int = 0,
        limit: int = 200,
        client_chat_id: str | None = None,
    ) -> ChatHistoryResponse:
        """
        Build a complete history response for API consumers.

        This centralizes the chat-history rules that the frontend relies on:
        active-session resolution, stale client chat detection, incremental
        pagination metadata, and a best-effort signal that retention truncated
        earlier messages.

        Args:
            user_id: Authenticated user requesting history.
            after_id: Incremental history cursor from the client.
            limit: Maximum number of messages to include in the response.
            client_chat_id: Client-side active chat id used to detect session drift.
        """
        chat_id = await self.get_or_create_current_chat_id(user_id)
        chat_mismatch = bool(client_chat_id and client_chat_id != chat_id)
        effective_after_id = 0 if chat_mismatch else after_id

        messages = await self.get_history(user_id, chat_id=chat_id, after_id=effective_after_id, limit=limit)
        latest_id = await self.get_latest_id(user_id, chat_id)
        oldest_id = await self.get_oldest_id(user_id, chat_id)

        last_returned_id = messages[-1].id if messages else effective_after_id
        has_more = latest_id > last_returned_id
        history_truncated = (
            not chat_mismatch and effective_after_id > 0 and oldest_id > 0 and oldest_id > (effective_after_id + 1)
        )

        return ChatHistoryResponse(
            chat_id=chat_id,
            chat_mismatch=chat_mismatch,
            latest_id=latest_id,
            has_more=has_more,
            history_truncated=history_truncated,
            messages=messages,
        )

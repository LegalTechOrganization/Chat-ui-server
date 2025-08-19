"""
Обработчики Kafka событий для чат-сервиса
"""
import logging
import time
from typing import Dict, Any
from datetime import datetime
from django.forms.models import model_to_dict
from asgiref.sync import sync_to_async

from .models import Conversation, Message, Prompt, EmbeddingDocument
from .kafka_service import kafka_service
from .kafka_models import (
    KafkaEvent, EventType, EventStatus,
    ChatSendMessagePayload, ChatSendMessageResponsePayload,
    ChatGetConversationsPayload, ChatGetConversationsResponsePayload,
    ChatCreateConversationPayload, ChatCreateConversationResponsePayload,
    ChatDeleteConversationPayload,
    ChatGetMessagesPayload, ChatGetMessagesResponsePayload,
    ChatUploadDocumentPayload, ChatUploadDocumentResponsePayload,
    ChatCreatePromptPayload, ChatCreatePromptResponsePayload,
    ChatGenerateTitlePayload, ChatGenerateTitleResponsePayload,
    ConversationData, MessageData, PromptData,
    AuditEventType
)
from .kafka_service import (
    send_message_sent_event, send_conversation_created_event, send_error_event
)

logger = logging.getLogger(__name__)


class ChatEventHandler:
    """Обработчик событий чат-сервиса"""
    
    def __init__(self):
        logger.info("🎯 ChatEventHandler initialized")
        
    def _get_conversations_sync(self, user_id: str, org_id: str, offset: int, limit: int):
        """Синхронный метод для получения диалогов"""
        queryset = Conversation.objects.filter(user_sub=user_id)
        if org_id:
            queryset = queryset.filter(org_id=org_id)
        
        total_count = queryset.count()
        conversations = queryset.order_by('-created_at')[offset:offset + limit]
        
        conversation_list = []
        for conv in conversations:
            # Подсчитываем количество сообщений
            message_count = Message.objects.filter(conversation=conv).count()
            
            conversation_list.append({
                'id': conv.id,
                'topic': conv.topic,
                'created_at': conv.created_at.isoformat(),
                'message_count': message_count
            })
        
        return {
            'conversations': conversation_list,
            'total_count': total_count
        }
    
    def _delete_conversation_sync(self, conversation_id: str, user_id: str, org_id: str):
        """Синхронный метод для удаления диалога"""
        queryset = Conversation.objects.filter(
            id=conversation_id,
            user_sub=user_id
        )
        if org_id:
            queryset = queryset.filter(org_id=org_id)
        
        conversation = queryset.first()
        if conversation:
            conversation.delete()
            return True
        return False
    
    def _delete_prompt_sync(self, prompt_id: str, user_id: str):
        """Синхронный метод для удаления промпта"""
        prompt = Prompt.objects.filter(id=prompt_id, user_sub=user_id).first()
        if prompt:
            prompt.delete()
            return True
        return False
    
    def _get_messages_sync(self, conversation_id: str, user_id: str, org_id: str, offset: int, limit: int):
        """Синхронный метод для получения сообщений диалога"""
        # Проверяем доступ к диалогу
        conv_queryset = Conversation.objects.filter(
            id=conversation_id,
            user_sub=user_id
        )
        if org_id:
            conv_queryset = conv_queryset.filter(org_id=org_id)
        
        conversation = conv_queryset.first()
        if not conversation:
            return None
        
        # Получаем сообщения
        messages_queryset = Message.objects.filter(
            conversation=conversation
        ).order_by('created_at')
        
        total_count = messages_queryset.count()
        messages = messages_queryset[offset:offset + limit]
        
        message_list = []
        for msg in messages:
            message_list.append({
                'id': msg.id,
                'message': msg.message,
                'is_bot': msg.is_bot,
                'tokens': msg.tokens,
                'message_type': msg.message_type,
                'created_at': msg.created_at.isoformat()
            })
        
        return {
            'messages': message_list,
            'total_count': total_count
        }
    
    def _generate_title_sync(self, conversation_id: str, user_id: str):
        """Синхронный метод для генерации заголовка диалога"""
        # Проверяем доступ к диалогу
        conversation = Conversation.objects.filter(
            id=conversation_id,
            user_sub=user_id
        ).first()
        
        if not conversation:
            return None
        
        # Простая генерация заголовка (без OpenAI для MVP)
        generated_title = f"Generated Title {conversation_id[:8]}"
        
        # Обновляем диалог
        conversation.topic = generated_title
        conversation.save()
        
        return generated_title
    
    def _create_conversation_sync(self, user_id: str, org_id: str, topic: str):
        """Синхронный метод для создания диалога"""
        return Conversation.objects.create(
            user_sub=user_id,
            org_id=org_id,
            topic=topic
        )
    
    def _create_prompt_sync(self, user_id: str, title: str, prompt: str):
        """Синхронный метод для создания промпта"""
        return Prompt.objects.create(
            user_sub=user_id,
            title=title,
            prompt=prompt
        )
    
    def _create_document_sync(self, user_id: str, org_id: str, title: str):
        """Синхронный метод для создания документа"""
        return EmbeddingDocument.objects.create(
            user_sub=user_id,
            org_id=org_id,
            title=title,
            faiss_store=b""  # Заглушка для MVP
        )
        
    async def handle_send_message(self, event_data: Dict[str, Any]):
        """Обработка отправки сообщения"""
        start_time = time.time()
        request_id = None
        
        try:
            # 1. Парсим входящее событие
            event = KafkaEvent(**event_data)
            request_id = event.request_id
            payload = ChatSendMessagePayload(**event.payload)
            
            user_id = payload.user_context.email  # Используем email как user_id
            org_id = payload.user_context.active_org_id
            
            logger.info("💬 Processing chat message for user %s, request %s", user_id, request_id)
            
            # 2. Выполняем бизнес-логику отправки сообщения
            # Это асинхронный процесс, поэтому отправляем базовый ответ
            response_payload = ChatSendMessageResponsePayload(
                message_id="temp_id",  # Временный ID
                conversation_id=payload.conversation_id or "new_conversation",
                response="Message processing started",
                tokens_used=0,
                model=payload.model,
                streaming=True  # Указываем, что это streaming ответ
            )
            
            # 3. Отправляем успешный ответ в Gateway
            await kafka_service.send_response(
                request_id=event.request_id,
                operation=EventType.CHAT_SEND_MESSAGE_RESPONSE,
                status=EventStatus.SUCCESS,
                payload=response_payload.dict()
            )
            
            # 4. Отправляем аудит событие
            response_time_ms = int((time.time() - start_time) * 1000)
            await send_message_sent_event(
                user_id=user_id,
                conversation_id=payload.conversation_id or "new",
                message_id="temp_id",
                model=payload.model,
                tokens_used=0,
                org_id=org_id,
                response_time_ms=response_time_ms
            )
            
            logger.info("✅ Chat message processed for user %s", user_id)
            
        except Exception as e:
            logger.error("❌ Error processing chat message: %s", e)
            
            # Отправляем ответ об ошибке
            if request_id:
                await kafka_service.send_response(
                    request_id=request_id,
                    operation=EventType.CHAT_SEND_MESSAGE_RESPONSE,
                    status=EventStatus.ERROR,
                    error=f"Internal error: {str(e)}"
                )

    async def handle_get_conversations(self, event_data: Dict[str, Any]):
        """Обработка получения списка диалогов"""
        start_time = time.time()
        request_id = None
        
        try:
            event = KafkaEvent(**event_data)
            request_id = event.request_id
            payload = ChatGetConversationsPayload(**event.payload)
            
            user_id = payload.user_context.email
            org_id = payload.user_context.active_org_id
            
            logger.info("📂 Getting conversations for user %s", user_id)
            
            # Получаем диалоги пользователя (асинхронно)
            conversations_data = await sync_to_async(self._get_conversations_sync)(
                user_id, org_id, payload.offset, payload.limit
            )
            
            conversation_list = []
            for conv_data in conversations_data['conversations']:
                conversation_list.append(ConversationData(
                    id=str(conv_data['id']),
                    topic=conv_data['topic'],
                    created_at=conv_data['created_at'],
                    message_count=conv_data['message_count']
                ))
            
            total_count = conversations_data['total_count']
            
            response_payload = ChatGetConversationsResponsePayload(
                conversations=conversation_list,
                total_count=total_count,
                has_more=(payload.offset + payload.limit) < total_count
            )
            
            await kafka_service.send_response(
                request_id=event.request_id,
                operation=EventType.CHAT_GET_CONVERSATIONS_RESPONSE,
                status=EventStatus.SUCCESS,
                payload=response_payload.dict()
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info("✅ Retrieved %d conversations for user %s in %d ms", 
                       len(conversation_list), user_id, response_time_ms)
            
        except Exception as e:
            logger.error("❌ Error getting conversations: %s", e)
            
            if request_id:
                await kafka_service.send_response(
                    request_id=request_id,
                    operation=EventType.CHAT_GET_CONVERSATIONS_RESPONSE,
                    status=EventStatus.ERROR,
                    error=f"Internal error: {str(e)}"
                )

    async def handle_create_conversation(self, event_data: Dict[str, Any]):
        """Обработка создания диалога"""
        start_time = time.time()
        request_id = None
        
        try:
            event = KafkaEvent(**event_data)
            request_id = event.request_id
            payload = ChatCreateConversationPayload(**event.payload)
            
            user_id = payload.user_context.email
            org_id = payload.user_context.active_org_id
            
            logger.info("➕ Creating conversation for user %s", user_id)
            
            # Создаем новый диалог (асинхронно)
            conversation = await sync_to_async(self._create_conversation_sync)(
                user_id, org_id, payload.topic or "New Conversation"
            )
            
            response_payload = ChatCreateConversationResponsePayload(
                id=str(conversation.id),
                topic=conversation.topic,
                created_at=conversation.created_at.isoformat()
            )
            
            await kafka_service.send_response(
                request_id=event.request_id,
                operation=EventType.CHAT_CREATE_CONVERSATION_RESPONSE,
                status=EventStatus.SUCCESS,
                payload=response_payload.dict()
            )
            
            # Аудит событие
            await send_conversation_created_event(
                user_id=user_id,
                conversation_id=str(conversation.id),
                org_id=org_id
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info("✅ Created conversation %s for user %s in %d ms", 
                       conversation.id, user_id, response_time_ms)
            
        except Exception as e:
            logger.error("❌ Error creating conversation: %s", e)
            
            if request_id:
                await kafka_service.send_response(
                    request_id=request_id,
                    operation=EventType.CHAT_CREATE_CONVERSATION_RESPONSE,
                    status=EventStatus.ERROR,
                    error=f"Internal error: {str(e)}"
                )

    async def handle_delete_conversation(self, event_data: Dict[str, Any]):
        """Обработка удаления диалога"""
        start_time = time.time()
        request_id = None
        
        try:
            event = KafkaEvent(**event_data)
            request_id = event.request_id
            payload = ChatDeleteConversationPayload(**event.payload)
            
            user_id = payload.user_context.email
            org_id = payload.user_context.active_org_id
            
            logger.info("🗑️ Deleting conversation %s for user %s", 
                       payload.conversation_id, user_id)
            
            # Проверяем права доступа и удаляем (асинхронно)
            deleted = await sync_to_async(self._delete_conversation_sync)(
                payload.conversation_id, user_id, org_id
            )
            
            if not deleted:
                raise ValueError("Conversation not found or access denied")
            
            await kafka_service.send_response(
                request_id=event.request_id,
                operation=EventType.CHAT_DELETE_CONVERSATION_RESPONSE,
                status=EventStatus.SUCCESS,
                payload={"deleted": True}
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info("✅ Deleted conversation %s for user %s in %d ms", 
                       payload.conversation_id, user_id, response_time_ms)
            
        except Exception as e:
            logger.error("❌ Error deleting conversation: %s", e)
            
            if request_id:
                await kafka_service.send_response(
                    request_id=request_id,
                    operation=EventType.CHAT_DELETE_CONVERSATION_RESPONSE,
                    status=EventStatus.ERROR,
                    error=f"Internal error: {str(e)}"
                )

    async def handle_get_messages(self, event_data: Dict[str, Any]):
        """Обработка получения сообщений диалога"""
        start_time = time.time()
        request_id = None
        
        try:
            event = KafkaEvent(**event_data)
            request_id = event.request_id
            payload = ChatGetMessagesPayload(**event.payload)
            
            user_id = payload.user_context.email
            org_id = payload.user_context.active_org_id
            
            logger.info("💬 Getting messages for conversation %s, user %s", 
                       payload.conversation_id, user_id)
            
            # Получаем сообщения диалога (асинхронно)
            messages_data = await sync_to_async(self._get_messages_sync)(
                payload.conversation_id, user_id, org_id, payload.offset, payload.limit
            )
            
            if not messages_data:
                raise ValueError("Conversation not found or access denied")
            
            message_list = []
            for msg_data in messages_data['messages']:
                message_list.append(MessageData(
                    id=str(msg_data['id']),
                    message=msg_data['message'],
                    is_bot=msg_data['is_bot'],
                    tokens=msg_data['tokens'],
                    message_type=msg_data['message_type'],
                    created_at=msg_data['created_at']
                ))
            
            total_count = messages_data['total_count']
            
            response_payload = ChatGetMessagesResponsePayload(
                messages=message_list,
                conversation_id=payload.conversation_id,
                total_count=total_count
            )
            
            await kafka_service.send_response(
                request_id=event.request_id,
                operation=EventType.CHAT_GET_MESSAGES_RESPONSE,
                status=EventStatus.SUCCESS,
                payload=response_payload.dict()
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info("✅ Retrieved %d messages for conversation %s in %d ms", 
                       len(message_list), payload.conversation_id, response_time_ms)
            
        except Exception as e:
            logger.error("❌ Error getting messages: %s", e)
            
            if request_id:
                await kafka_service.send_response(
                    request_id=request_id,
                    operation=EventType.CHAT_GET_MESSAGES_RESPONSE,
                    status=EventStatus.ERROR,
                    error=f"Internal error: {str(e)}"
                )

    async def handle_get_prompts(self, event_data: Dict[str, Any]):
        """Обработка получения промптов пользователя"""
        start_time = time.time()
        request_id = None
        
        try:
            event = KafkaEvent(**event_data)
            request_id = event.request_id
            # payload можно расширить для фильтрации промптов
            user_context = event.payload.get('user_context', {})
            user_id = user_context.get('email')
            
            logger.info("📝 Getting prompts for user %s", user_id)
            
            prompts = await sync_to_async(list)(
                Prompt.objects.filter(user_sub=user_id).order_by('-created_at')
            )
            
            prompt_list = []
            for prompt in prompts:
                prompt_list.append(PromptData(
                    id=str(prompt.id),
                    title=prompt.title,
                    prompt=prompt.prompt,
                    created_at=prompt.created_at.isoformat(),
                    updated_at=prompt.updated_at.isoformat()
                ))
            
            await kafka_service.send_response(
                request_id=event.request_id,
                operation=EventType.CHAT_GET_PROMPTS_RESPONSE,
                status=EventStatus.SUCCESS,
                payload={"prompts": [p.dict() for p in prompt_list]}
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info("✅ Retrieved %d prompts for user %s in %d ms", 
                       len(prompt_list), user_id, response_time_ms)
            
        except Exception as e:
            logger.error("❌ Error getting prompts: %s", e)
            
            if request_id:
                await kafka_service.send_response(
                    request_id=request_id,
                    operation=EventType.CHAT_GET_PROMPTS_RESPONSE,
                    status=EventStatus.ERROR,
                    error=f"Internal error: {str(e)}"
                )

    async def handle_create_prompt(self, event_data: Dict[str, Any]):
        """Обработка создания промпта"""
        start_time = time.time()
        request_id = None
        
        try:
            event = KafkaEvent(**event_data)
            request_id = event.request_id
            payload = ChatCreatePromptPayload(**event.payload)
            
            user_id = payload.user_context.email
            
            logger.info("➕ Creating prompt for user %s", user_id)
            
            prompt = await sync_to_async(self._create_prompt_sync)(
                user_id, payload.title, payload.prompt
            )
            
            response_payload = ChatCreatePromptResponsePayload(
                id=str(prompt.id),
                title=prompt.title,
                prompt=prompt.prompt,
                created_at=prompt.created_at.isoformat()
            )
            
            await kafka_service.send_response(
                request_id=event.request_id,
                operation=EventType.CHAT_CREATE_PROMPT_RESPONSE,
                status=EventStatus.SUCCESS,
                payload=response_payload.dict()
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info("✅ Created prompt %s for user %s in %d ms", 
                       prompt.id, user_id, response_time_ms)
            
        except Exception as e:
            logger.error("❌ Error creating prompt: %s", e)
            
            if request_id:
                await kafka_service.send_response(
                    request_id=request_id,
                    operation=EventType.CHAT_CREATE_PROMPT_RESPONSE,
                    status=EventStatus.ERROR,
                    error=f"Internal error: {str(e)}"
                )

    async def handle_delete_prompt(self, event_data: Dict[str, Any]):
        """Обработка удаления промпта"""
        start_time = time.time()
        request_id = None
        
        try:
            event = KafkaEvent(**event_data)
            request_id = event.request_id
            prompt_id = event.payload.get('prompt_id')
            user_context = event.payload.get('user_context', {})
            user_id = user_context.get('email')
            
            logger.info("🗑️ Deleting prompt %s for user %s", prompt_id, user_id)
            
            # Проверяем права доступа и удаляем
            deleted = await sync_to_async(self._delete_prompt_sync)(prompt_id, user_id)
            if not deleted:
                raise ValueError("Prompt not found or access denied")
            
            await kafka_service.send_response(
                request_id=event.request_id,
                operation=EventType.CHAT_DELETE_PROMPT_RESPONSE,
                status=EventStatus.SUCCESS,
                payload={"deleted": True, "prompt_id": prompt_id}
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info("✅ Deleted prompt %s for user %s in %d ms", 
                       prompt_id, user_id, response_time_ms)
            
        except Exception as e:
            logger.error("❌ Error deleting prompt: %s", e)
            
            if request_id:
                await kafka_service.send_response(
                    request_id=request_id,
                    operation=EventType.CHAT_DELETE_PROMPT_RESPONSE,
                    status=EventStatus.ERROR,
                    error=f"Internal error: {str(e)}"
                )

    async def handle_upload_document(self, event_data: Dict[str, Any]):
        """Обработка загрузки документа"""
        start_time = time.time()
        request_id = None
        
        try:
            event = KafkaEvent(**event_data)
            request_id = event.request_id
            payload = ChatUploadDocumentPayload(**event.payload)
            
            user_id = payload.user_context.email
            org_id = payload.user_context.active_org_id
            
            logger.info("📎 Uploading document '%s' for user %s", payload.title, user_id)
            
            # Создаем документ (без фактической обработки файла для MVP)
            document = await sync_to_async(self._create_document_sync)(
                user_id, org_id, payload.title
            )
            
            response_payload = ChatUploadDocumentResponsePayload(
                id=str(document.id),
                title=document.title,
                created_at=document.created_at.isoformat()
            )
            
            await kafka_service.send_response(
                request_id=event.request_id,
                operation=EventType.CHAT_UPLOAD_DOCUMENT_RESPONSE,
                status=EventStatus.SUCCESS,
                payload=response_payload.dict()
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info("✅ Uploaded document %s for user %s in %d ms", 
                       document.id, user_id, response_time_ms)
            
        except Exception as e:
            logger.error("❌ Error uploading document: %s", e)
            
            if request_id:
                await kafka_service.send_response(
                    request_id=request_id,
                    operation=EventType.CHAT_UPLOAD_DOCUMENT_RESPONSE,
                    status=EventStatus.ERROR,
                    error=f"Internal error: {str(e)}"
                )

    async def handle_generate_title(self, event_data: Dict[str, Any]):
        """Обработка генерации заголовка диалога"""
        start_time = time.time()
        request_id = None
        
        try:
            event = KafkaEvent(**event_data)
            request_id = event.request_id
            payload = ChatGenerateTitlePayload(**event.payload)
            
            user_id = payload.user_context.email
            
            logger.info("✨ Generating title for conversation %s", payload.conversation_id)
            
            # Генерируем и обновляем заголовок (асинхронно)
            generated_title = await sync_to_async(self._generate_title_sync)(
                payload.conversation_id, user_id
            )
            
            if not generated_title:
                raise ValueError("Conversation not found or access denied")
            
            response_payload = ChatGenerateTitleResponsePayload(
                title=generated_title,
                conversation_id=payload.conversation_id
            )
            
            await kafka_service.send_response(
                request_id=event.request_id,
                operation=EventType.CHAT_GENERATE_TITLE_RESPONSE,
                status=EventStatus.SUCCESS,
                payload=response_payload.dict()
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info("✅ Generated title for conversation %s in %d ms", 
                       payload.conversation_id, response_time_ms)
            
        except Exception as e:
            logger.error("❌ Error generating title: %s", e)
            
            if request_id:
                await kafka_service.send_response(
                    request_id=request_id,
                    operation=EventType.CHAT_GENERATE_TITLE_RESPONSE,
                    status=EventStatus.ERROR,
                    error=f"Internal error: {str(e)}"
                )


# Глобальный экземпляр обработчика
event_handler = ChatEventHandler()

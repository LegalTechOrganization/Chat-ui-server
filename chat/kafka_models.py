"""
Модели Kafka событий для чат-сервиса
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


# Статусы событий
class EventStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


# Типы операций чат-сервиса
class EventType(str, Enum):
    # Входящие операции
    CHAT_SEND_MESSAGE = "chat_send_message"
    CHAT_GET_CONVERSATIONS = "chat_get_conversations"
    CHAT_CREATE_CONVERSATION = "chat_create_conversation"
    CHAT_DELETE_CONVERSATION = "chat_delete_conversation"
    CHAT_GET_MESSAGES = "chat_get_messages"
    CHAT_STREAM_MESSAGE = "chat_stream_message"
    CHAT_UPLOAD_DOCUMENT = "chat_upload_document"
    CHAT_DELETE_DOCUMENT = "chat_delete_document"
    CHAT_GET_PROMPTS = "chat_get_prompts"
    CHAT_CREATE_PROMPT = "chat_create_prompt"
    CHAT_DELETE_PROMPT = "chat_delete_prompt"
    CHAT_GENERATE_TITLE = "chat_generate_title"
    
    # Ответы
    CHAT_SEND_MESSAGE_RESPONSE = "chat_send_message_response"
    CHAT_GET_CONVERSATIONS_RESPONSE = "chat_get_conversations_response"
    CHAT_CREATE_CONVERSATION_RESPONSE = "chat_create_conversation_response"
    CHAT_DELETE_CONVERSATION_RESPONSE = "chat_delete_conversation_response"
    CHAT_GET_MESSAGES_RESPONSE = "chat_get_messages_response"
    CHAT_STREAM_MESSAGE_RESPONSE = "chat_stream_message_response"
    CHAT_UPLOAD_DOCUMENT_RESPONSE = "chat_upload_document_response"
    CHAT_DELETE_DOCUMENT_RESPONSE = "chat_delete_document_response"
    CHAT_GET_PROMPTS_RESPONSE = "chat_get_prompts_response"
    CHAT_CREATE_PROMPT_RESPONSE = "chat_create_prompt_response"
    CHAT_DELETE_PROMPT_RESPONSE = "chat_delete_prompt_response"
    CHAT_GENERATE_TITLE_RESPONSE = "chat_generate_title_response"


# Контекст пользователя от Gateway
class UserContext(BaseModel):
    """Контекст пользователя от Auth Service через Gateway"""
    email: str = Field(..., description="Email пользователя")
    full_name: Optional[str] = Field(None, description="Полное имя")
    active_org_id: Optional[str] = Field(None, description="ID активной организации")
    org_role: Optional[str] = Field(None, description="Роль в организации")
    is_org_owner: bool = Field(False, description="Владелец организации")


# Метаданные запроса
class RequestMetadata(BaseModel):
    """Метаданные запроса от Gateway"""
    source_ip: Optional[str] = Field(None, description="IP адрес")
    user_agent: Optional[str] = Field(None, description="User Agent")
    gateway_request_id: Optional[str] = Field(None, description="ID запроса в Gateway")
    timestamp: Optional[str] = Field(None, description="Временная метка")


# Базовое Kafka событие
class KafkaEvent(BaseModel):
    """Базовое входящее событие от Gateway"""
    message_id: str = Field(..., description="Уникальный ID сообщения")
    request_id: str = Field(..., description="ID запроса для корреляции")
    operation: EventType = Field(..., description="Тип операции")
    timestamp: str = Field(..., description="Временная метка ISO")
    payload: Dict[str, Any] = Field(..., description="Полезная нагрузка")


# Ответное событие
class KafkaResponse(BaseModel):
    """Ответ в Kafka для Gateway"""
    message_id: str = Field(..., description="Уникальный ID ответа")
    request_id: str = Field(..., description="ID оригинального запроса")
    operation: EventType = Field(..., description="Тип операции ответа")
    timestamp: str = Field(..., description="Временная метка ответа")
    status: EventStatus = Field(..., description="Статус обработки")
    payload: Optional[Dict[str, Any]] = Field(None, description="Данные ответа")
    error: Optional[str] = Field(None, description="Ошибка при status=error")


# === Специфичные модели операций ===

# Отправка сообщения
class ChatSendMessagePayload(BaseModel):
    """Payload для отправки сообщения в чат"""
    message: str = Field(..., description="Текст сообщения")
    conversation_id: Optional[str] = Field(None, description="ID диалога")
    model: Optional[str] = Field("gpt-3.5-turbo", description="Модель ИИ")
    max_tokens: Optional[int] = Field(None, description="Максимальное количество токенов")
    temperature: Optional[float] = Field(0.7, description="Температура генерации")
    top_p: Optional[float] = Field(1.0, description="Top-p параметр")
    frequency_penalty: Optional[float] = Field(0.0, description="Частотная штраф")
    presence_penalty: Optional[float] = Field(0.0, description="Штраф за присутствие")
    system_content: Optional[str] = Field("You are a helpful assistant.", description="Системный промпт")
    web_search: Optional[Dict[str, Any]] = Field(None, description="Параметры веб-поиска")
    frugal_mode: bool = Field(False, description="Экономный режим")
    tool: Optional[Dict[str, Any]] = Field(None, description="Инструмент для выполнения")
    openai_api_key: Optional[str] = Field(None, description="API ключ OpenAI")
    user_context: UserContext = Field(..., description="Контекст пользователя")
    request_metadata: Optional[RequestMetadata] = Field(None, description="Метаданные")


class ChatSendMessageResponsePayload(BaseModel):
    """Ответ на отправку сообщения"""
    message_id: str = Field(..., description="ID созданного сообщения")
    conversation_id: str = Field(..., description="ID диалога")
    user_message_id: Optional[str] = Field(None, description="ID пользовательского сообщения")
    response: str = Field(..., description="Ответ ИИ")
    tokens_used: int = Field(..., description="Использованные токены")
    model: str = Field(..., description="Использованная модель")
    streaming: bool = Field(False, description="Был ли ответ в streaming режиме")


# Получение диалогов
class ChatGetConversationsPayload(BaseModel):
    """Payload для получения списка диалогов"""
    limit: int = Field(50, description="Количество диалогов")
    offset: int = Field(0, description="Смещение")
    user_context: UserContext = Field(..., description="Контекст пользователя")
    request_metadata: Optional[RequestMetadata] = Field(None, description="Метаданные")


class ConversationData(BaseModel):
    """Данные диалога"""
    id: str = Field(..., description="ID диалога")
    topic: str = Field(..., description="Тема диалога")
    created_at: str = Field(..., description="Дата создания")
    message_count: Optional[int] = Field(None, description="Количество сообщений")


class ChatGetConversationsResponsePayload(BaseModel):
    """Ответ со списком диалогов"""
    conversations: List[ConversationData] = Field(..., description="Список диалогов")
    total_count: int = Field(..., description="Общее количество")
    has_more: bool = Field(..., description="Есть ли еще диалоги")


# Создание диалога
class ChatCreateConversationPayload(BaseModel):
    """Payload для создания диалога"""
    topic: Optional[str] = Field(None, description="Тема диалога")
    user_context: UserContext = Field(..., description="Контекст пользователя")
    request_metadata: Optional[RequestMetadata] = Field(None, description="Метаданные")


class ChatCreateConversationResponsePayload(BaseModel):
    """Ответ на создание диалога"""
    id: str = Field(..., description="ID созданного диалога")
    topic: str = Field(..., description="Тема диалога")
    created_at: str = Field(..., description="Дата создания")


# Удаление диалога
class ChatDeleteConversationPayload(BaseModel):
    """Payload для удаления диалога"""
    conversation_id: str = Field(..., description="ID диалога для удаления")
    user_context: UserContext = Field(..., description="Контекст пользователя")
    request_metadata: Optional[RequestMetadata] = Field(None, description="Метаданные")


# Получение сообщений
class ChatGetMessagesPayload(BaseModel):
    """Payload для получения сообщений диалога"""
    conversation_id: str = Field(..., description="ID диалога")
    limit: int = Field(100, description="Количество сообщений")
    offset: int = Field(0, description="Смещение")
    user_context: UserContext = Field(..., description="Контекст пользователя")
    request_metadata: Optional[RequestMetadata] = Field(None, description="Метаданные")


class MessageData(BaseModel):
    """Данные сообщения"""
    id: str = Field(..., description="ID сообщения")
    message: str = Field(..., description="Текст сообщения")
    is_bot: bool = Field(..., description="Сообщение от бота")
    tokens: int = Field(0, description="Количество токенов")
    message_type: int = Field(0, description="Тип сообщения")
    created_at: str = Field(..., description="Дата создания")


class ChatGetMessagesResponsePayload(BaseModel):
    """Ответ со списком сообщений"""
    messages: List[MessageData] = Field(..., description="Список сообщений")
    conversation_id: str = Field(..., description="ID диалога")
    total_count: int = Field(..., description="Общее количество")


# Работа с документами
class ChatUploadDocumentPayload(BaseModel):
    """Payload для загрузки документа"""
    title: str = Field(..., description="Название документа")
    file: str = Field(..., description="Файл в base64")
    openai_api_key: Optional[str] = Field(None, description="API ключ OpenAI")
    user_context: UserContext = Field(..., description="Контекст пользователя")
    request_metadata: Optional[RequestMetadata] = Field(None, description="Метаданные")


class ChatUploadDocumentResponsePayload(BaseModel):
    """Ответ на загрузку документа"""
    id: str = Field(..., description="ID созданного документа")
    title: str = Field(..., description="Название документа")
    created_at: str = Field(..., description="Дата создания")


# Работа с промптами
class ChatCreatePromptPayload(BaseModel):
    """Payload для создания промпта"""
    title: Optional[str] = Field(None, description="Название промпта")
    prompt: str = Field(..., description="Текст промпта")
    user_context: UserContext = Field(..., description="Контекст пользователя")
    request_metadata: Optional[RequestMetadata] = Field(None, description="Метаданные")


class PromptData(BaseModel):
    """Данные промпта"""
    id: str = Field(..., description="ID промпта")
    title: Optional[str] = Field(None, description="Название промпта")
    prompt: str = Field(..., description="Текст промпта")
    created_at: str = Field(..., description="Дата создания")
    updated_at: str = Field(..., description="Дата обновления")


class ChatCreatePromptResponsePayload(BaseModel):
    """Ответ на создание промпта"""
    id: str = Field(..., description="ID созданного промпта")
    title: Optional[str] = Field(None, description="Название промпта")
    prompt: str = Field(..., description="Текст промпта")
    created_at: str = Field(..., description="Дата создания")


# Генерация заголовка
class ChatGenerateTitlePayload(BaseModel):
    """Payload для генерации заголовка диалога"""
    conversation_id: str = Field(..., description="ID диалога")
    prompt: Optional[str] = Field(None, description="Промпт для генерации")
    openai_api_key: Optional[str] = Field(None, description="API ключ OpenAI")
    user_context: UserContext = Field(..., description="Контекст пользователя")
    request_metadata: Optional[RequestMetadata] = Field(None, description="Метаданные")


class ChatGenerateTitleResponsePayload(BaseModel):
    """Ответ на генерацию заголовка"""
    title: str = Field(..., description="Сгенерированный заголовок")
    conversation_id: str = Field(..., description="ID диалога")


# === Аудит события ===

class AuditEventType(str, Enum):
    MESSAGE_SENT = "message_sent"
    CONVERSATION_CREATED = "conversation_created"
    CONVERSATION_DELETED = "conversation_deleted"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DELETED = "document_deleted"
    PROMPT_CREATED = "prompt_created"
    PROMPT_DELETED = "prompt_deleted"
    TITLE_GENERATED = "title_generated"
    ERROR_OCCURRED = "error_occurred"
    STREAMING_STARTED = "streaming_started"
    STREAMING_COMPLETED = "streaming_completed"


class AuditEventData(BaseModel):
    """Данные для аудита"""
    user_id: str
    org_id: Optional[str] = None
    operation: str
    status: str
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    document_id: Optional[str] = None
    prompt_id: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    response_time_ms: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class AuditEvent(BaseModel):
    """Событие для аудита"""
    event_type: AuditEventType
    timestamp: float  # Unix timestamp
    data: AuditEventData

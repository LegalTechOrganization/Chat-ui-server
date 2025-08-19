"""
Сервис для работы с Kafka в чат-сервисе
"""
import asyncio
import json
import logging
import uuid
import os
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError

from .kafka_models import (
    KafkaResponse, EventStatus, EventType, 
    AuditEvent, AuditEventType, AuditEventData
)

logger = logging.getLogger(__name__)


class KafkaService:
    """Сервис для работы с Kafka"""
    
    def __init__(self):
        self.bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9095')
        self.service_name = os.getenv('SERVICE_NAME', 'chat-service')
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.running = False
        
    async def start_producer(self):
        """Запуск Kafka producer с повторными попытками"""
        max_retries = 10
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                self.producer = AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                    retry_backoff_ms=1000,
                    request_timeout_ms=30000,
                    acks='all'
                )
                await self.producer.start()
                logger.info("✅ Kafka producer started for %s", self.service_name)
                return
            except Exception as e:
                logger.warning("⚠️ Kafka producer attempt %d/%d failed: %s", attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    logger.info("🔄 Retrying in %d seconds...", retry_delay)
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("❌ Failed to start Kafka producer after %d attempts", max_retries)
                    raise

    async def start_consumer(self, topic: str, group_id: str, handler: Callable):
        """Запуск consumer для топика с повторными попытками"""
        max_retries = 5
        retry_delay = 3
        
        for attempt in range(max_retries):
            try:
                consumer = AIOKafkaConsumer(
                    topic,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=group_id,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8-sig')),  # Убираем BOM
                    auto_offset_reset='latest',
                    enable_auto_commit=True,
                    consumer_timeout_ms=1000
                )
                
                await consumer.start()
                self.consumers[topic] = consumer
                self.message_handlers[topic] = handler
                
                logger.info("✅ Started consumer for topic: %s", topic)
                
                # Запускаем обработку в фоне
                asyncio.create_task(self._consume_messages(topic))
                return
                
            except Exception as e:
                logger.warning("⚠️ Consumer %s attempt %d/%d failed: %s", topic, attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    logger.info("🔄 Retrying consumer for %s in %d seconds...", topic, retry_delay)
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("❌ Failed to start consumer for %s after %d attempts", topic, max_retries)
                    raise

    async def _consume_messages(self, topic: str):
        """Обработка сообщений из топика"""
        consumer = self.consumers[topic]
        handler = self.message_handlers[topic]
        
        try:
            while self.running:
                try:
                    msg_pack = await consumer.getmany(timeout_ms=1000)
                    
                    for tp, messages in msg_pack.items():
                        for message in messages:
                            try:
                                logger.info("📥 Processing message from %s", topic)
                                await handler(message.value)
                            except Exception as e:
                                logger.error("❌ Error processing message: %s", e)
                                
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error("❌ Consumer error for %s: %s", topic, e)
                    await asyncio.sleep(5)
                    
        except Exception as e:
            logger.error("💥 Fatal consumer error for %s: %s", topic, e)

    async def send_response(self, request_id: str, operation: EventType, 
                          status: EventStatus, payload: Optional[Dict[str, Any]] = None,
                          error: Optional[str] = None):
        """Отправка ответа в chat-service-responses топик"""
        response = KafkaResponse(
            message_id=str(uuid.uuid4()),
            request_id=request_id,
            operation=operation,
            timestamp=datetime.utcnow().isoformat() + "Z",
            status=status,
            payload=payload,
            error=error
        )
        
        await self.send_message(
            topic="chat-service-responses",
            message=response.dict(),
            key=request_id
        )
        
        logger.info("📤 Sent response for request %s: %s", request_id, status)

    async def send_audit_event(self, event_type: AuditEventType, data: AuditEventData):
        """Отправка события для аудита"""
        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow().timestamp(),
            data=data
        )
        
        await self.send_message(
            topic="chat-service-events",
            message=event.dict(),
            key=data.user_id
        )
        
        logger.info("📊 Sent audit event: %s for user %s", event_type, data.user_id)

    async def send_message(self, topic: str, message: Dict[str, Any], key: Optional[str] = None):
        """Отправка сообщения в топик"""
        if not self.producer:
            logger.warning("⚠️ Kafka producer not started, skipping message")
            return
            
        try:
            await self.producer.send(
                topic=topic,
                value=message,
                key=key.encode('utf-8') if key else None
            )
            logger.debug("📤 Sent message to %s", topic)
        except KafkaError as e:
            logger.error("❌ Failed to send to %s: %s", topic, e)
            raise

    async def start(self):
        """Запуск Kafka сервиса"""
        self.running = True
        await self.start_producer()
        logger.info("🚀 Kafka service started for %s", self.service_name)

    async def stop(self):
        """Остановка Kafka сервиса"""
        self.running = False
        
        # Останавливаем consumers
        for topic, consumer in self.consumers.items():
            try:
                await consumer.stop()
                logger.info("🛑 Stopped consumer for %s", topic)
            except Exception as e:
                logger.error("❌ Error stopping consumer for %s: %s", topic, e)
        
        # Останавливаем producer
        if self.producer:
            await self.producer.stop()
            logger.info("🛑 Stopped Kafka producer")
            
        logger.info("🛑 Kafka service stopped")


# Глобальный экземпляр сервиса
kafka_service = KafkaService()


# Вспомогательные функции для отправки специфичных событий
async def send_chat_audit_event(event_type: AuditEventType, user_id: str, 
                               org_id: Optional[str] = None, **kwargs):
    """Упрощенная отправка аудит события чата"""
    data = AuditEventData(
        user_id=user_id,
        org_id=org_id,
        operation=kwargs.get('operation', event_type.value),
        status=kwargs.get('status', 'success'),
        **{k: v for k, v in kwargs.items() if k not in ['operation', 'status']}
    )
    await kafka_service.send_audit_event(event_type, data)


async def send_message_sent_event(user_id: str, conversation_id: str, 
                                 message_id: str, model: str, tokens_used: int,
                                 org_id: Optional[str] = None, 
                                 response_time_ms: Optional[int] = None):
    """Отправка события об отправке сообщения"""
    await send_chat_audit_event(
        event_type=AuditEventType.MESSAGE_SENT,
        user_id=user_id,
        org_id=org_id,
        conversation_id=conversation_id,
        message_id=message_id,
        model=model,
        tokens_used=tokens_used,
        response_time_ms=response_time_ms
    )


async def send_conversation_created_event(user_id: str, conversation_id: str,
                                        org_id: Optional[str] = None):
    """Отправка события о создании диалога"""
    await send_chat_audit_event(
        event_type=AuditEventType.CONVERSATION_CREATED,
        user_id=user_id,
        org_id=org_id,
        conversation_id=conversation_id
    )


async def send_error_event(user_id: str, operation: str, error_message: str,
                          org_id: Optional[str] = None, **kwargs):
    """Отправка события об ошибке"""
    await send_chat_audit_event(
        event_type=AuditEventType.ERROR_OCCURRED,
        user_id=user_id,
        org_id=org_id,
        operation=operation,
        status='error',
        error_message=error_message,
        **kwargs
    )

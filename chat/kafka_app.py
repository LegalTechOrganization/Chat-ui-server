"""
Инициализация и управление Kafka для chat-service
"""
import asyncio
import logging
import os
import threading
from typing import Optional
from django.apps import AppConfig

from .kafka_service import kafka_service
from .event_handlers import event_handler

logger = logging.getLogger(__name__)


class KafkaManager:
    """Менеджер для управления Kafka интеграцией"""
    
    def __init__(self):
        self.kafka_task: Optional[asyncio.Task] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

    async def start_kafka_service(self):
        """Запуск Kafka сервиса с регистрацией всех consumers"""
        try:
            logger.info("🚀 Starting Kafka service for chat-service...")
            
            # Инициализируем Kafka сервис
            await kafka_service.start()
            
            # Регистрируем consumers для всех топиков
            consumers_config = [
                # Основные операции
                ("chat-service-send-message", "chat-service", event_handler.handle_send_message),
                ("chat-service-get-conversations", "chat-service", event_handler.handle_get_conversations),
                ("chat-service-create-conversation", "chat-service", event_handler.handle_create_conversation),
                ("chat-service-delete-conversation", "chat-service", event_handler.handle_delete_conversation),
                ("chat-service-get-messages", "chat-service", event_handler.handle_get_messages),
                
                # Операции с промптами
                ("chat-service-get-prompts", "chat-service", event_handler.handle_get_prompts),
                ("chat-service-create-prompt", "chat-service", event_handler.handle_create_prompt),
                ("chat-service-delete-prompt", "chat-service", event_handler.handle_delete_prompt),
                
                # Операции с документами
                ("chat-service-upload-document", "chat-service", event_handler.handle_upload_document),
                
                # Дополнительные операции
                ("chat-service-generate-title", "chat-service", event_handler.handle_generate_title),
            ]
            
            # Регистрируем каждый consumer
            for topic, group_id, handler in consumers_config:
                try:
                    await kafka_service.start_consumer(topic, group_id, handler)
                    logger.info("✅ Registered consumer for topic: %s", topic)
                except Exception as e:
                    logger.error("❌ Failed to register consumer for %s: %s", topic, e)
            
            logger.info("🎯 All Kafka consumers registered successfully")
            
            # Держим сервис запущенным
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error("💥 Fatal error in Kafka service: %s", e)
        finally:
            await kafka_service.stop()

    def start_in_thread(self):
        """Запуск Kafka в отдельном потоке"""
        def run_kafka():
            # Создаем новый event loop для этого потока
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            try:
                self.running = True
                self.kafka_task = self.loop.create_task(self.start_kafka_service())
                self.loop.run_until_complete(self.kafka_task)
            except Exception as e:
                logger.error("❌ Error in Kafka thread: %s", e)
            finally:
                self.loop.close()

        self.thread = threading.Thread(target=run_kafka, daemon=True)
        self.thread.start()
        logger.info("🧵 Kafka service started in background thread")

    def stop(self):
        """Остановка Kafka сервиса"""
        self.running = False
        
        if self.kafka_task and not self.kafka_task.done():
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(self.kafka_task.cancel)
        
        if self.thread and self.thread.is_alive():
            logger.info("🛑 Stopping Kafka thread...")
            self.thread.join(timeout=5)
        
        logger.info("🛑 Kafka manager stopped")


# Глобальный экземпляр менеджера
kafka_manager = KafkaManager()


class ChatKafkaConfig(AppConfig):
    """Конфигурация для интеграции Kafka в chat app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'

    def ready(self):
        """Инициализация при старте Django приложения"""
        # Проверяем, что Kafka должен быть запущен
        if os.getenv('DISABLE_KAFKA', '').lower() not in ['true', '1', 'yes']:
            import django
            if django.VERSION >= (3, 2):
                # Запускаем Kafka только если это не миграции или другие команды
                import sys
                if 'runserver' in sys.argv or 'runserver_plus' in sys.argv:
                    logger.info("🔧 Django ready - starting Kafka integration")
                    kafka_manager.start_in_thread()
                else:
                    logger.info("🔧 Django ready - Kafka disabled for this command")
            else:
                logger.warning("⚠️ Django version < 3.2, Kafka integration may not work properly")
        else:
            logger.info("🔧 Kafka integration disabled by DISABLE_KAFKA environment variable")


# Функции для управления Kafka из других частей приложения
def start_kafka():
    """Публичная функция для запуска Kafka"""
    if not kafka_manager.running:
        kafka_manager.start_in_thread()


def stop_kafka():
    """Публичная функция для остановки Kafka"""
    kafka_manager.stop()


def is_kafka_running():
    """Проверка состояния Kafka"""
    return kafka_manager.running

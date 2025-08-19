import os
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'

    def ready(self):
        import chat.signals
        
        # Инициализация Kafka интеграции
        try:
            from .kafka_app import kafka_manager
            
            # Простая проверка - запускаем Kafka только если не отключен явно
            disable_kafka = os.getenv('DISABLE_KAFKA', '').lower() in ['true', '1', 'yes']
            
            if not disable_kafka:
                # Запускаем Kafka для всех случаев, кроме явно запрещенных команд
                import sys
                command_line = ' '.join(sys.argv).lower()
                
                # НЕ запускаем Kafka только для этих команд
                skip_commands = ['migrate', 'makemigrations', 'collectstatic', 'createsuperuser', 'shell']
                should_skip = any(cmd in command_line for cmd in skip_commands)
                
                if not should_skip:
                    logger.info("🚀 Starting Kafka integration for chat-service")
                    kafka_manager.start_in_thread()
                else:
                    logger.info("🔧 Kafka disabled for management command: %s", ' '.join(sys.argv))
            else:
                logger.info("🔧 Kafka integration disabled by DISABLE_KAFKA environment variable")
                
        except Exception as e:
            logger.error("❌ Failed to initialize Kafka integration: %s", e)

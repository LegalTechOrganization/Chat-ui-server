"""
Internal HTTP endpoints для интеграции с Gateway
Эти endpoints будут использоваться только Gateway'ем для проксирования Kafka запросов
"""
import os
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json

from .kafka_service import kafka_service

logger = logging.getLogger(__name__)


def verify_internal_key(request):
    """Проверка внутреннего ключа Gateway"""
    internal_key = request.headers.get('x-internal-key')
    expected_key = os.getenv('SERVICE_TOKEN', 'chat-service-secret-key')
    
    if internal_key != expected_key:
        logger.warning("❌ Invalid internal key from %s", request.META.get('REMOTE_ADDR'))
        return False
    return True


def extract_user_data(request):
    """Извлечение данных пользователя из заголовка X-User-Data"""
    user_data_header = request.headers.get('X-User-Data')
    if not user_data_header:
        return None
    
    try:
        user_data = json.loads(user_data_header)
        # Возвращаем весь объект user_data, а не только jwt_token
        return user_data
    except (json.JSONDecodeError, AttributeError):
        logger.warning("⚠️ Invalid X-User-Data header format")
        return None


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint"""
    kafka_status = "running" if kafka_service.running else "stopped"
    
    return JsonResponse({
        "status": "healthy",
        "service": "chat-service",
        "kafka": kafka_status,
        "version": "1.0.0"
    })


@api_view(['POST'])
def verify_token(request):
    """Верификация токена пользователя (для Gateway)"""
    if not verify_internal_key(request):
        return Response(
            {"error": "Unauthorized"}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    user_data = extract_user_data(request)
    if not user_data:
        return Response(
            {"error": "No user data provided"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Здесь можно добавить валидацию токена через Auth Service
    # Пока возвращаем успешный ответ
    return Response({
        "valid": True,
        "service": "chat-service"
    })


@api_view(['GET'])
def service_info(request):
    """Информация о сервисе для Gateway"""
    if not verify_internal_key(request):
        return Response(
            {"error": "Unauthorized"}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    return Response({
        "service_name": "chat-service",
        "version": "1.0.0",
        "kafka_topics": {
            "incoming": [
                "chat-service-send-message",
                "chat-service-get-conversations", 
                "chat-service-create-conversation",
                "chat-service-delete-conversation",
                "chat-service-get-messages",
                "chat-service-get-prompts",
                "chat-service-create-prompt",
                "chat-service-delete-prompt",
                "chat-service-upload-document",
                "chat-service-generate-title"
            ],
            "outgoing": [
                "chat-service-responses",
                "chat-service-events"
            ]
        },
        "kafka_status": "running" if kafka_service.running else "stopped"
    })


@api_view(['POST'])
def kafka_status(request):
    """Статус Kafka интеграции"""
    if not verify_internal_key(request):
        return Response(
            {"error": "Unauthorized"}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    return Response({
        "kafka_running": kafka_service.running,
        "bootstrap_servers": kafka_service.bootstrap_servers,
        "active_consumers": list(kafka_service.consumers.keys()),
        "producer_ready": kafka_service.producer is not None
    })


@api_view(['GET'])
def service_metrics(request):
    """Метрики сервиса для мониторинга"""
    if not verify_internal_key(request):
        return Response(
            {"error": "Unauthorized"}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Базовые метрики
    from .models import Conversation, Message, Prompt, EmbeddingDocument
    
    try:
        total_conversations = Conversation.objects.count()
        total_messages = Message.objects.count()
        total_prompts = Prompt.objects.count()
        total_documents = EmbeddingDocument.objects.count()
        
        return Response({
            "service": "chat-service",
            "kafka_status": "running" if kafka_service.running else "stopped",
            "database_metrics": {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "total_prompts": total_prompts,
                "total_documents": total_documents
            },
            "kafka_metrics": {
                "active_consumers": len(kafka_service.consumers),
                "topics": list(kafka_service.consumers.keys())
            }
        })
    except Exception as e:
        logger.error("❌ Error getting metrics: %s", e)
        return Response(
            {"error": "Internal server error"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Fallback HTTP endpoints (legacy поддержка)
# Эти endpoints можно использовать для тестирования без Gateway

@api_view(['POST'])
def test_kafka_integration(request):
    """Тестовый endpoint для проверки полной Kafka интеграции"""
    if not verify_internal_key(request):
        return Response(
            {"error": "Unauthorized"}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    logger.info("🧪 Testing full Kafka integration")
    
    try:
        import uuid
        import json
        from datetime import datetime
        from .kafka_models import KafkaEvent, EventType
        
        # Извлекаем данные пользователя из X-User-Data header (как делает Gateway)
        user_data = extract_user_data(request)
        if not user_data:
            return Response(
                {"error": "X-User-Data header required for testing"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Получаем тело запроса (если есть)
        request_body = {}
        if hasattr(request, 'data') and request.data:
            request_body = request.data
        
        # Симулируем Kafka событие от Gateway с реальными данными пользователя
        test_request_id = str(uuid.uuid4())
        test_event = {
            "message_id": str(uuid.uuid4()),
            "request_id": test_request_id,
            "event_type": "CHAT_CREATE_CONVERSATION",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "user_context": {
                    "email": user_data.get("email", "test.kafka@example.com"),
                    "full_name": user_data.get("full_name", "Kafka Test User"),
                    "active_org_id": user_data.get("active_org_id", "test-org"),
                    "roles": user_data.get("roles", ["user"])
                },
                "request_metadata": {
                    "source_ip": request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    "user_agent": request.META.get('HTTP_USER_AGENT', 'Kafka Test/1.0'),
                    "gateway_request_id": str(uuid.uuid4())
                },
                "topic": request_body.get("topic", "Kafka Integration Test")
            }
        }
        
        # Отправляем событие в наш собственный Kafka
        from .event_handlers import event_handler
        import asyncio
        
        # Запускаем тест асинхронно
        async def run_test():
            try:
                await event_handler.handle_create_conversation(test_event)
                return {"status": "success", "request_id": test_request_id}
            except Exception as e:
                logger.error("❌ Kafka test failed: %s", e)
                return {"status": "error", "error": str(e)}
        
        # Выполняем тест
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_test())
        loop.close()
        
        return Response({
            "test_name": "Kafka Integration Test",
            "kafka_status": "running" if kafka_service.running else "stopped",
            "result": result,
            "message": "Direct Kafka event processing test completed"
        })
        
    except Exception as e:
        logger.error("❌ Kafka integration test failed: %s", e)
        return Response(
            {
                "test_name": "Kafka Integration Test",
                "status": "error", 
                "error": str(e),
                "kafka_status": "running" if kafka_service.running else "stopped"
            }, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def fallback_send_message(request):
    """Fallback endpoint для отправки сообщения (без Kafka)"""
    logger.info("⚠️ Using fallback HTTP endpoint for send_message")
    
    # Базовая реализация без Kafka
    return Response({
        "message": "Fallback response - Kafka integration required for full functionality",
        "status": "fallback",
        "conversation_id": "fallback-conv-id",
        "message_id": "fallback-msg-id"
    })


@api_view(['GET'])
def fallback_get_conversations(request):
    """Fallback endpoint для получения диалогов"""
    logger.info("⚠️ Using fallback HTTP endpoint for get_conversations")
    
    user_id = getattr(request, 'user_id', None)
    if not user_id:
        return Response(
            {"error": "X-User-Id header required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from .models import Conversation
        conversations = Conversation.objects.filter(user_sub=user_id).order_by('-created_at')[:10]
        
        conv_list = []
        for conv in conversations:
            conv_list.append({
                "id": str(conv.id),
                "topic": conv.topic,
                "created_at": conv.created_at.isoformat()
            })
        
        return Response({
            "conversations": conv_list,
            "status": "fallback"
        })
    except Exception as e:
        logger.error("❌ Fallback conversations error: %s", e)
        return Response(
            {"error": "Internal error"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

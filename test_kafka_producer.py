#!/usr/bin/env python3
"""
Тестовый producer для отправки событий в chat-service
"""
import asyncio
import json
import uuid
from datetime import datetime
from aiokafka import AIOKafkaProducer


async def send_test_event(topic: str, event_data: dict):
    """Отправка тестового события"""
    
    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9095",  # Порт chat-service Kafka
        value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
    )
    
    try:
        await producer.start()
        
        await producer.send(
            topic=topic,
            value=event_data,
            key=event_data['request_id'].encode('utf-8')
        )
        
        print(f"✅ Sent test event to {topic}: {event_data['request_id']}")
        
    finally:
        await producer.stop()


async def test_send_message():
    """Тест отправки сообщения"""
    
    event_data = {
        "message_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "operation": "chat_send_message",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "message": "Привет! Как дела?",
            "conversation_id": None,
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "system_content": "You are a helpful assistant.",
            "user_context": {
                "email": "test@example.com",
                "full_name": "Test User",
                "active_org_id": "test-org-123",
                "org_role": "admin",
                "is_org_owner": True
            },
            "request_metadata": {
                "source_ip": "127.0.0.1",
                "user_agent": "TestAgent/1.0",
                "gateway_request_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
    }
    
    await send_test_event("chat-service-send-message", event_data)


async def test_get_conversations():
    """Тест получения диалогов"""
    
    event_data = {
        "message_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "operation": "chat_get_conversations",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "limit": 10,
            "offset": 0,
            "user_context": {
                "email": "test@example.com",
                "full_name": "Test User",
                "active_org_id": "test-org-123",
                "org_role": "admin",
                "is_org_owner": True
            },
            "request_metadata": {
                "source_ip": "127.0.0.1",
                "user_agent": "TestAgent/1.0"
            }
        }
    }
    
    await send_test_event("chat-service-get-conversations", event_data)


async def test_create_conversation():
    """Тест создания диалога"""
    
    event_data = {
        "message_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "operation": "chat_create_conversation",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "topic": "Тестовый диалог",
            "user_context": {
                "email": "test@example.com",
                "full_name": "Test User",
                "active_org_id": "test-org-123",
                "org_role": "admin",
                "is_org_owner": True
            },
            "request_metadata": {
                "source_ip": "127.0.0.1",
                "user_agent": "TestAgent/1.0"
            }
        }
    }
    
    await send_test_event("chat-service-create-conversation", event_data)


async def test_create_prompt():
    """Тест создания промпта"""
    
    event_data = {
        "message_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "operation": "chat_create_prompt",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "title": "Тестовый промпт",
            "prompt": "Ты полезный ассистент, который отвечает на русском языке.",
            "user_context": {
                "email": "test@example.com",
                "full_name": "Test User",
                "active_org_id": "test-org-123",
                "org_role": "admin",
                "is_org_owner": True
            },
            "request_metadata": {
                "source_ip": "127.0.0.1",
                "user_agent": "TestAgent/1.0"
            }
        }
    }
    
    await send_test_event("chat-service-create-prompt", event_data)


async def test_upload_document():
    """Тест загрузки документа"""
    
    event_data = {
        "message_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "operation": "chat_upload_document",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "title": "Тестовый документ",
            "file": "data:text/plain;base64,VGVzdCBkb2N1bWVudCBjb250ZW50",
            "user_context": {
                "email": "test@example.com",
                "full_name": "Test User",
                "active_org_id": "test-org-123",
                "org_role": "admin",
                "is_org_owner": True
            },
            "request_metadata": {
                "source_ip": "127.0.0.1",
                "user_agent": "TestAgent/1.0"
            }
        }
    }
    
    await send_test_event("chat-service-upload-document", event_data)


async def test_generate_title():
    """Тест генерации заголовка"""
    
    event_data = {
        "message_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "operation": "chat_generate_title",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "conversation_id": "1",  # Предполагаем, что диалог с ID 1 существует
            "prompt": "Generate a short title for this conversation",
            "user_context": {
                "email": "test@example.com",
                "full_name": "Test User",
                "active_org_id": "test-org-123",
                "org_role": "admin",
                "is_org_owner": True
            },
            "request_metadata": {
                "source_ip": "127.0.0.1",
                "user_agent": "TestAgent/1.0"
            }
        }
    }
    
    await send_test_event("chat-service-generate-title", event_data)


async def main():
    """Запуск всех тестов"""
    print("🧪 Запуск тестов Kafka для chat-service...")
    
    tests = [
        ("Создание диалога", test_create_conversation),
        ("Получение диалогов", test_get_conversations),
        ("Отправка сообщения", test_send_message),
        ("Создание промпта", test_create_prompt),
        ("Загрузка документа", test_upload_document),
        ("Генерация заголовка", test_generate_title),
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\n🔄 {test_name}...")
            await test_func()
            await asyncio.sleep(1)  # Небольшая пауза между тестами
        except Exception as e:
            print(f"❌ Ошибка в тесте '{test_name}': {e}")
    
    print("\n✅ Все тесты завершены!")
    print("📊 Проверьте логи chat-service для подтверждения обработки событий")


if __name__ == "__main__":
    asyncio.run(main())

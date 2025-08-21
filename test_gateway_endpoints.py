#!/usr/bin/env python3
"""
Скрипт для тестирования эндпоинтов Chat Service через Gateway
"""

import requests
import json
import os

# Базовые URL
GATEWAY_URL = "http://localhost:8002"
# Определяем URL в зависимости от того, где запущен скрипт
if os.path.exists('/.dockerenv'):
    # Внутри контейнера
    CHAT_SERVICE_URL = "http://127.0.0.1:8010"
else:
    # Снаружи контейнера
    CHAT_SERVICE_URL = "http://localhost:8003"

# Тестовые данные
test_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXN1Yi0xMjMiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJmdWxsX25hbWUiOiJUZXN0IFVzZXIiLCJvcmdfaWQiOiJ0ZXN0LW9yZy0xMjMiLCJyb2xlcyI6WyJ1c2VyIl0sImlhdCI6MTYzNDU2Nzg5MCwiZXhwIjoxOTQ5OTI3ODkwfQ.test-signature"

user_data = {
    "jwt_token": test_jwt,
    "user_data": {
        "sub": "test-sub-123",
        "email": "test@example.com",
        "full_name": "Test User",
        "org_id": "test-org-123",
        "roles": ["user"]
    }
}

headers = {
    "X-User-Data": json.dumps(user_data),
    "Content-Type": "application/json"
}

def test_chat_service_direct():
    """Тестируем Chat Service напрямую"""
    print("🔍 Тестируем Chat Service напрямую...")
    print("=" * 60)
    
    # 1. Получаем список бесед
    print("1. GET /api/chat/conversations/")
    response = requests.get(f"{CHAT_SERVICE_URL}/api/chat/conversations/", headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        conversations = response.json()
        print(f"   Бесед: {len(conversations)}")
        for conv in conversations:
            print(f"   - ID: {conv['id']}, Topic: {conv['topic']}, Sub: {conv['sub']}")
    
    # 2. Создаем новую беседу
    print("\n2. POST /api/chat/conversations/")
    conversation_data = {"topic": "Test Conversation via Gateway"}
    response = requests.post(f"{CHAT_SERVICE_URL}/api/chat/conversations/", 
                           headers=headers, json=conversation_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 201:
        conversation = response.json()
        conv_id = conversation['id']
        print(f"   Создана беседа ID: {conv_id}")
        
        # 3. Получаем конкретную беседу
        print(f"\n3. GET /api/chat/conversations/{conv_id}/")
        response = requests.get(f"{CHAT_SERVICE_URL}/api/chat/conversations/{conv_id}/", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            conv = response.json()
            print(f"   Беседа: {conv['topic']}")
        
        # 4. Создаем сообщение в беседе
        print(f"\n4. POST /api/chat/messages/")
        message_data = {
            "conversation": conv_id,
            "message": "Test message from Gateway testing"
        }
        response = requests.post(f"{CHAT_SERVICE_URL}/api/chat/messages/", 
                               headers=headers, json=message_data)
        print(f"   Status: {response.status_code}")
        if response.status_code == 201:
            message = response.json()
            print(f"   Создано сообщение ID: {message['id']}")
        
        # 5. Получаем сообщения беседы
        print(f"\n5. GET /api/chat/messages/?conversationId={conv_id}")
        response = requests.get(f"{CHAT_SERVICE_URL}/api/chat/messages/?conversationId={conv_id}", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            messages = response.json()
            print(f"   Сообщений: {len(messages)}")
            for msg in messages:
                print(f"   - ID: {msg['id']}, Message: {msg['message'][:50]}...")
    
    print("\n" + "=" * 60)

def test_gateway_endpoints():
    """Тестируем эндпоинты через Gateway"""
    print("🔍 Тестируем эндпоинты через Gateway...")
    print("=" * 60)
    
    # 1. Получаем список бесед через Gateway
    print("1. GET /api/chat/conversations/ (через Gateway)")
    response = requests.get(f"{GATEWAY_URL}/api/chat/conversations/")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        conversations = response.json()
        print(f"   Бесед: {len(conversations)}")
        for conv in conversations:
            print(f"   - ID: {conv['id']}, Topic: {conv['topic']}")
    
    print("\n" + "=" * 60)

def main():
    """Основная функция"""
    print("🚀 Начинаем тестирование эндпоинтов...")
    print(f"📍 Gateway URL: {GATEWAY_URL}")
    print(f"📍 Chat Service URL: {CHAT_SERVICE_URL}")
    print("=" * 60)
    
    # Тестируем Chat Service напрямую
    test_chat_service_direct()
    
    # Тестируем через Gateway
    test_gateway_endpoints()
    
    print("✅ Тестирование завершено!")

if __name__ == "__main__":
    main()

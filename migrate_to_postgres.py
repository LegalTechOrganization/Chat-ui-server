#!/usr/bin/env python3
"""
Скрипт для миграции на PostgreSQL с новой схемой, использующей sub как уникальный идентификатор пользователя.
"""

import os
import sys
import django
from pathlib import Path

# Добавляем путь к проекту
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Устанавливаем настройки PostgreSQL
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatgpt_ui_server.settings_postgres')

# Инициализируем Django
django.setup()

from django.core.management import execute_from_command_line
from django.db import connection
from chat.models_postgres import Conversation, Message, Prompt, EmbeddingDocument, Setting, TokenUsage


def create_initial_settings():
    """Создаем начальные настройки"""
    print("🔧 Создаем начальные настройки...")
    
    settings_data = [
        {'name': 'open_registration', 'value': 'True'},
        {'name': 'open_web_search', 'value': 'False'},
        {'name': 'open_api_key_setting', 'value': 'False'},
        {'name': 'open_frugal_mode_control', 'value': 'True'},
    ]
    
    for setting_data in settings_data:
        Setting.objects.get_or_create(
            name=setting_data['name'],
            defaults={'value': setting_data['value']}
        )
    
    print("✅ Настройки созданы")


def create_sample_data():
    """Создаем тестовые данные"""
    print("📝 Создаем тестовые данные...")
    
    # Тестовый sub (из JWT токена)
    test_sub = "c8410440-99ed-4e52-af5d-9156434571b4"
    test_org_id = "123e4567-e89b-12d3-a456-426614174000"
    
    # Создаем тестовую беседу
    conversation, created = Conversation.objects.get_or_create(
        sub=test_sub,
        topic="Тестовая беседа в PostgreSQL",
        defaults={
            'org_id': test_org_id,
        }
    )
    
    if created:
        print(f"✅ Создана беседа: {conversation.topic}")
        
        # Создаем тестовое сообщение
        message = Message.objects.create(
            sub=test_sub,
            conversation=conversation,
            message="Привет! Это тестовое сообщение в PostgreSQL.",
            is_bot=False,
            message_type=0
        )
        print(f"✅ Создано сообщение: {message.message[:50]}...")
        
        # Создаем тестовый промпт
        prompt = Prompt.objects.create(
            sub=test_sub,
            title="Тестовый промпт",
            content="Это тестовый промпт для проверки работы PostgreSQL."
        )
        print(f"✅ Создан промпт: {prompt.title}")
        
        # Создаем запись использования токенов
        token_usage, created = TokenUsage.objects.get_or_create(
            sub=test_sub,
            defaults={'tokens': 100}
        )
        print(f"✅ Создана запись токенов: {token_usage.tokens} токенов")
    
    else:
        print(f"ℹ️ Беседа уже существует: {conversation.topic}")


def verify_database_structure():
    """Проверяем структуру базы данных"""
    print("🔍 Проверяем структуру базы данных...")
    
    with connection.cursor() as cursor:
        # Проверяем таблицы
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('conversations', 'messages', 'prompts', 'embedding_documents', 'settings', 'token_usage')
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📋 Найденные таблицы: {', '.join(tables)}")
        
        # Проверяем индексы для conversations
        cursor.execute("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'conversations'
        """)
        
        indexes = cursor.fetchall()
        print(f"🔗 Индексы для conversations:")
        for index_name, index_def in indexes:
            print(f"  - {index_name}: {index_def}")


def main():
    """Основная функция миграции"""
    print("🚀 Начинаем миграцию на PostgreSQL...")
    
    try:
        # Применяем миграции
        print("📦 Применяем миграции...")
        execute_from_command_line(['manage.py', 'makemigrations', 'chat'])
        execute_from_command_line(['manage.py', 'migrate'])
        
        # Создаем начальные настройки
        create_initial_settings()
        
        # Создаем тестовые данные
        create_sample_data()
        
        # Проверяем структуру БД
        verify_database_structure()
        
        print("🎉 Миграция на PostgreSQL завершена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

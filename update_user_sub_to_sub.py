#!/usr/bin/env python3
"""
Скрипт для автоматического обновления всех user_sub на sub в файлах
"""

import os
import re

def update_file(file_path):
    """Обновляет user_sub на sub в файле"""
    print(f"Обновляем {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Заменяем user_sub на sub в различных контекстах
    updated_content = content
    
    # В моделях Django
    updated_content = re.sub(r'user_sub\s*=\s*models\.CharField', 'sub = models.CharField', updated_content)
    updated_content = re.sub(r'user_sub\s*=\s*models\.TextField', 'sub = models.CharField', updated_content)
    
    # В фильтрах Django ORM
    updated_content = re.sub(r'\.filter\(user_sub=', '.filter(sub=', updated_content)
    updated_content = re.sub(r'\.objects\.filter\(user_sub=', '.objects.filter(sub=', updated_content)
    
    # В создании объектов
    updated_content = re.sub(r'user_sub\s*=\s*user_sub', 'sub=user_sub', updated_content)
    updated_content = re.sub(r'user_sub\s*=\s*getattr', 'sub=getattr', updated_content)
    
    # В сериализаторах
    updated_content = re.sub(r"'user_sub'", "'sub'", updated_content)
    updated_content = re.sub(r'"user_sub"', '"sub"', updated_content)
    
    # В validated_data
    updated_content = re.sub(r"serializer\.validated_data\['user_sub'\]", "serializer.validated_data['sub']", updated_content)
    
    # В get_or_create
    updated_content = re.sub(r'TokenUsage\.objects\.get_or_create\(user_sub=', 'TokenUsage.objects.get_or_create(sub=', updated_content)
    
    # В комментариях
    updated_content = re.sub(r'# Внешний идентификатор пользователя \(UUID в строковом виде\)', '# Уникальный идентификатор пользователя из JWT токена', updated_content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"✅ {file_path} обновлен")

def main():
    """Основная функция"""
    files_to_update = [
        'chat/views.py',
        'chat/serializers.py',
        'chat/models.py',
        'chat/event_handlers.py',
        'chat/internal_views.py',
    ]
    
    for file_path in files_to_update:
        if os.path.exists(file_path):
            update_file(file_path)
        else:
            print(f"⚠️ Файл {file_path} не найден")

if __name__ == '__main__':
    main()

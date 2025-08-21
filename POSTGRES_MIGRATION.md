# Миграция на PostgreSQL с использованием sub как уникального идентификатора

## 🎯 Цель

Адаптировать Chat Service для использования `sub` (из JWT токена) как уникального идентификатора пользователя, аналогично Tarrification service, и перейти с SQLite на PostgreSQL для сохранения данных.

## 📊 Сравнение с Tarrification

### Tarrification (balance_transactions):
- `id` - автоинкремент
- `sub` - уникальный идентификатор пользователя (UUID)
- `direction` - направление транзакции
- `units` - количество единиц
- `ref` - ссылка
- `reason` - причина
- `source_service` - источник
- `created_at` - время создания

### Chat Service (адаптированный):
- `id` - автоинкремент
- `sub` - уникальный идентификатор пользователя (UUID из JWT)
- `org_id` - идентификатор организации (опционально)
- `topic` / `message` / `title` - содержимое
- `created_at` - время создания
- `updated_at` - время обновления

## 🔧 Изменения в схеме

### 1. Замена `user_sub` на `sub`
- Все модели теперь используют `sub` как основной идентификатор пользователя
- `sub` извлекается из JWT токена (поле `sub` в payload)
- Добавлены индексы для оптимизации запросов по `sub`

### 2. Новые индексы
```sql
-- conversations
CREATE INDEX ON conversations (sub, created_at);
CREATE INDEX ON conversations (sub, org_id);

-- messages
CREATE INDEX ON messages (sub, created_at);
CREATE INDEX ON messages (sub, conversation);
CREATE INDEX ON messages (conversation, created_at);

-- prompts
CREATE INDEX ON prompts (sub, created_at);

-- embedding_documents
CREATE INDEX ON embedding_documents (sub, created_at);
CREATE INDEX ON embedding_documents (sub, org_id);

-- token_usage
CREATE INDEX ON token_usage (sub);
```

## 🚀 Запуск PostgreSQL версии

### 1. Запуск контейнеров
```bash
docker-compose -f docker-compose-postgres.yml up -d
```

### 2. Применение миграций
```bash
# В контейнере
docker exec -it chat-service-wsgi-postgres python migrate_to_postgres.py

# Или вручную
docker exec -it chat-service-wsgi-postgres python manage.py makemigrations
docker exec -it chat-service-wsgi-postgres python manage.py migrate
```

### 3. Проверка подключения
```bash
# Подключение к PostgreSQL
docker exec -it chat-service-postgres psql -U chat_service_user -d chat_service_db

# Проверка таблиц
\dt

# Проверка данных
SELECT * FROM conversations LIMIT 5;
```

## 📋 Структура базы данных

### Таблицы:
1. **conversations** - беседы пользователей
2. **messages** - сообщения в беседах
3. **prompts** - промпты пользователей
4. **embedding_documents** - документы для эмбеддинга
5. **settings** - настройки системы
6. **token_usage** - использование токенов

### Ключевые поля:
- `sub` - уникальный идентификатор пользователя (UUID)
- `org_id` - идентификатор организации (опционально)
- `created_at` - время создания записи
- `updated_at` - время последнего обновления

## 🔍 Проверка уникальности sub

### Тест с разными пользователями:
```bash
# Пользователь 1
curl -X POST http://localhost:8002/v1/client/sign-up \
  -H "Content-Type: application/json" \
  -d '{"email": "user1@example.com", "password": "password"}'

# Пользователь 2
curl -X POST http://localhost:8002/v1/client/sign-up \
  -H "Content-Type: application/json" \
  -d '{"email": "user2@example.com", "password": "password"}'
```

### Результат:
- Пользователь 1: `sub = "c8410440-99ed-4e52-af5d-9156434571b4"`
- Пользователь 2: `sub = "eaf55af9-0467-44dc-8f13-8af689b97a09"`

**Вывод:** `sub` уникален для каждого пользователя ✅

## 🧪 Тестирование

### 1. Создание беседы
```bash
curl -X POST http://localhost:8003/api/chat/conversations/ \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"topic": "Тест PostgreSQL"}'
```

### 2. Получение бесед
```bash
curl -X GET http://localhost:8003/api/chat/conversations/ \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### 3. Проверка в базе данных
```sql
SELECT c.id, c.sub, c.topic, c.created_at 
FROM conversations c 
WHERE c.sub = 'c8410440-99ed-4e52-af5d-9156434571b4';
```

## 🔄 Миграция данных (если нужно)

Если есть данные в SQLite, которые нужно перенести:

```python
# Скрипт миграции данных
from django.db import connections

def migrate_data_from_sqlite():
    # Подключение к SQLite
    with connections['sqlite'].cursor() as cursor:
        cursor.execute("SELECT * FROM chat_conversation")
        conversations = cursor.fetchall()
    
    # Перенос в PostgreSQL
    for conv in conversations:
        Conversation.objects.create(
            sub=conv['user_sub'],  # старый user_sub
            topic=conv['topic'],
            created_at=conv['created_at']
        )
```

## ✅ Преимущества новой схемы

1. **Совместимость с Tarrification** - одинаковая структура данных
2. **Уникальность sub** - гарантированная уникальность пользователей
3. **Производительность** - оптимизированные индексы
4. **Надежность** - PostgreSQL вместо SQLite
5. **Масштабируемость** - поддержка больших объемов данных

## 🎉 Результат

Chat Service теперь полностью адаптирован под использование `sub` как уникального идентификатора пользователя и готов к работе с PostgreSQL на порту 5457!

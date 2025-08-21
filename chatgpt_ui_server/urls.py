"""chatgpt_ui_server URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from chat.views import conversation, gen_title, upload_conversations
from utils import external_auth as auth_client

def health_check(request):
    return JsonResponse({"status": "healthy"})

def test_api(request):
    return JsonResponse({
        "message": "API is working!",
        "endpoints": [
            "/api/chat/conversations/",
            "/api/chat/messages/",
            "/api/chat/prompts/",
            "/api/conversation/",
            "/health/"
        ],
        "mock_me": auth_client.me(None),
        "mock_org_members": auth_client.org_members(None, getattr(request, 'active_org_id', '123e4567-e89b-12d3-a456-426614174000')),
    })

def test_db(request):
    try:
        return JsonResponse({
            "message": "Database is working!",
            "user_sub": getattr(request, 'user_id', None),
            "active_org_id": getattr(request, 'active_org_id', None)
        })
    except Exception as e:
        return JsonResponse({
            "error": str(e),
            "message": "Database error"
        }, status=500)

def test_conversations(request):
    try:
        from chat.models import Conversation
        import json
        
        if request.method == 'GET':
            conversations = Conversation.objects.filter(sub=getattr(request, 'user_id', None)).order_by('-created_at')
            conversation_list = []
            for conv in conversations:
                conversation_list.append({
                    "id": conv.id,
                    "topic": conv.topic,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None
                })
            return JsonResponse(conversation_list, safe=False)
        
        elif request.method == 'POST':
            data = json.loads(request.body)
            topic = data.get('topic', 'New Conversation')
            conversation = Conversation.objects.create(
                sub=getattr(request, 'user_id', None),
                org_id=getattr(request, 'active_org_id', None),
                topic=topic
            )
            return JsonResponse({
                "id": conversation.id,
                "topic": conversation.topic,
                "created_at": conversation.created_at.isoformat() if conversation.created_at else None
            }, status=201)
            
    except Exception as e:
        return JsonResponse({
            "error": str(e),
            "message": "Conversation error"
        }, status=500)

urlpatterns = [
    # Legacy health check
    path('health/', health_check, name='health'),
    
    # Internal endpoints для Gateway интеграции
    path('internal/', include('chat.internal_urls')),
    
    # Kafka-based API (основные endpoints остаются для совместимости)
    path('api/chat/', include('chat.urls')),
    
    # Legacy endpoints (будут заменены на Kafka)
    path('api/conversation/', conversation, name='conversation'),
    path('api/upload_conversations/', upload_conversations, name='upload_conversations'),
    path('api/gen_title/', gen_title, name='gen_title'),
    
    # Development/testing endpoints
    path('test/', test_api, name='test'),
    path('test-db/', test_db, name='test_db'),
    path('test-conversations/', test_conversations, name='test_conversations'),
    
    # Admin
    path('admin/', admin.site.urls),
]

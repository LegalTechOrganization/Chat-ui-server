"""
Internal URLs для интеграции с Gateway
"""
from django.urls import path
from . import internal_views

urlpatterns = [
    # Health check и служебные endpoints
    path('health/', internal_views.health_check, name='health_check'),
    path('verify-token/', internal_views.verify_token, name='verify_token'),
    path('service-info/', internal_views.service_info, name='service_info'),
    path('kafka-status/', internal_views.kafka_status, name='kafka_status'),
    path('metrics/', internal_views.service_metrics, name='service_metrics'),
    
    # Fallback HTTP endpoints (legacy поддержка)
    path('test-kafka/', internal_views.test_kafka_integration, name='test_kafka_integration'),
    path('fallback/send-message/', internal_views.fallback_send_message, name='fallback_send_message'),
    path('fallback/conversations/', internal_views.fallback_get_conversations, name='fallback_get_conversations'),
]

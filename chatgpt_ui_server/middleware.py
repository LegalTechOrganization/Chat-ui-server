import os
import logging
from chat.auth_utils import verify_gateway_auth

logger = logging.getLogger(__name__)

class UserIdMiddleware:
    """
    Middleware для извлечения заголовков идентичности, проброшенных из Gateway.
    Использует только новый формат: X-User-Data с JWT токеном и данными пользователя.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Используем только новый формат с X-User-Data
        x_user_data = request.headers.get('X-User-Data')
        logger.info(f"🔍 Middleware: X-User-Data header = {x_user_data}")
        
        if x_user_data:
            # Используем новую систему аутентификации
            auth_data = verify_gateway_auth(x_user_data)
            logger.info(f"🔍 Middleware: auth_data.is_valid = {auth_data.is_valid}")
            logger.info(f"🔍 Middleware: auth_data.user_id = {auth_data.user_id}")
            
            if auth_data.is_valid:
                request.user_id = auth_data.user_id
                request.active_org_id = auth_data.active_org_id
                request.user_email = auth_data.user_email
                request.user_roles = auth_data.user_roles
                request.jwt_payload = auth_data.jwt_payload
                logger.info(f"✅ Middleware: Установлены данные пользователя: user_id={request.user_id}")
            else:
                # Если JWT невалидный, сбрасываем данные
                request.user_id = None
                request.active_org_id = None
                request.user_email = None
                request.user_roles = []
                request.jwt_payload = None
                logger.warning("❌ Middleware: JWT невалидный, данные сброшены")
        else:
            # Если нет X-User-Data, сбрасываем все данные
            request.user_id = None
            request.active_org_id = None
            request.user_email = None
            request.user_roles = []
            request.jwt_payload = None
            logger.warning("❌ Middleware: Нет X-User-Data заголовка")

        # Убираем mock логику - если нет токена, возвращаем 401
        if not request.user_id:
            logger.warning("❌ Middleware: Аутентификация не пройдена - нет валидного токена")

        return self.get_response(request)
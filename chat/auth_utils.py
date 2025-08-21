import json
import logging
import jwt
from typing import Optional
from .auth_models import AuthUser, UserOrganization, GatewayAuthContext, ParsedAuthData

logger = logging.getLogger(__name__)


def verify_gateway_auth(x_user_data: Optional[str]) -> ParsedAuthData:
    """
    Проверка аутентификации через Gateway.
    Gateway передает JWT токен в заголовке X-User-Data.
    Мы сами декодируем токен и извлекаем sub.
    
    Ожидаемый формат:
    {
        "jwt_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
        "user_data": {
            "email": "string", 
            "full_name": "string",
            "orgs": [{"org_id": "string", "name": "string", "role": "string"}],
            "active_org_id": "string"
        }
    }
    """
    if not x_user_data:
        # Если нет X-User-Data, возвращаем невалидные данные
        return ParsedAuthData(
            user_id="",
            is_valid=False
        )
    
    try:
        # Парсим JSON из заголовка
        auth_data = json.loads(x_user_data)
        
        # Получаем JWT токен
        jwt_token = auth_data.get("jwt_token")
        if not jwt_token:
            # Если нет JWT токена, возвращаем невалидные данные
            logger.error("Missing JWT token in X-User-Data header")
            return ParsedAuthData(
                user_id="",
                is_valid=False
            )
        
        # Декодируем JWT токен (без проверки подписи для демо)
        # В продакшене нужно добавить проверку подписи
        try:
            jwt_payload = jwt.decode(jwt_token, options={"verify_signature": False})
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid JWT token: {e}")
            return ParsedAuthData(
                user_id="",
                is_valid=False
            )
        
        # Извлекаем sub из JWT токена
        sub = jwt_payload.get("sub")
        if not sub:
            logger.error("Missing sub claim in JWT token")
            return ParsedAuthData(
                user_id="",
                is_valid=False
            )
        
        # Получаем дополнительные данные пользователя
        user_data = auth_data.get("user_data", {})
        
        # Извлекаем роли из организаций
        user_roles = []
        active_org_id = user_data.get("active_org_id")
        
        for org_data in user_data.get("orgs", []):
            if isinstance(org_data, dict) and "role" in org_data:
                user_roles.append(org_data["role"])
        
        return ParsedAuthData(
            user_id=sub,
            active_org_id=active_org_id,
            user_email=user_data.get("email", ""),
            user_roles=user_roles,
            jwt_payload=jwt_payload,
            is_valid=True
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse X-User-Data header: {e}")
        # Если не удалось распарсить JSON, возвращаем невалидные данные
        return ParsedAuthData(
            user_id="",
            is_valid=False
        )
    except Exception as e:
        logger.error(f"Error processing authentication data: {e}")
        return ParsedAuthData(
            user_id="",
            is_valid=False
        )


def verify_internal_key(x_internal_key: Optional[str]) -> bool:
    """
    Проверка внутреннего ключа для прямых вызовов.
    """
    if not x_internal_key:
        return False
    
    # Проверяем ключ (в продакшене должен быть в настройках)
    valid_keys = [
        "chat-service-secret-key",
        "gateway-secret-key-2024"
    ]
    
    return x_internal_key in valid_keys


def create_gateway_auth_context(auth_data: ParsedAuthData) -> GatewayAuthContext:
    """Создать контекст аутентификации Gateway"""
    if not auth_data.is_valid:
        raise ValueError("Invalid authentication data")
    
    # Создаем объекты организаций
    orgs = []
    if auth_data.jwt_payload:
        user_data = auth_data.jwt_payload.get("user_data", {})
        for org_data in user_data.get("orgs", []):
            if isinstance(org_data, dict) and all(k in org_data for k in ["org_id", "name", "role"]):
                orgs.append(UserOrganization(**org_data))
    
    # Создаем объект пользователя
    user = AuthUser(
        sub=auth_data.user_id,
        email=auth_data.user_email,
        full_name=auth_data.jwt_payload.get("full_name") if auth_data.jwt_payload else None,
        orgs=orgs,
        active_org_id=auth_data.active_org_id
    )
    
    # Создаем контекст аутентификации
    return GatewayAuthContext(
        user=user,
        jwt_payload=auth_data.jwt_payload or {},
        token_valid=auth_data.is_valid
    )

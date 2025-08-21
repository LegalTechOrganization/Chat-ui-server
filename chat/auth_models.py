from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


class UserOrganization(BaseModel):
    """Модель организации пользователя"""
    org_id: str
    name: str
    role: str


class AuthUser(BaseModel):
    """Модель аутентифицированного пользователя"""
    sub: str  # sub из JWT токена
    email: str = ""
    full_name: Optional[str] = None
    orgs: List[UserOrganization] = []
    active_org_id: Optional[str] = None


class GatewayAuthContext(BaseModel):
    """Контекст аутентификации от Gateway"""
    user: AuthUser
    jwt_payload: Dict[str, Any]
    token_valid: bool = True


@dataclass
class ParsedAuthData:
    """Результат парсинга аутентификационных данных"""
    user_id: str
    active_org_id: Optional[str] = None
    user_email: str = ""
    user_roles: List[str] = None
    jwt_payload: Optional[Dict[str, Any]] = None
    is_valid: bool = True
    
    def __post_init__(self):
        if self.user_roles is None:
            self.user_roles = []

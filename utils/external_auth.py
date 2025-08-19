import os
from typing import Any, Dict, List, Optional

import requests


AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "http://auth-service")
API_PREFIX = "/v1"


def _mock_enabled() -> bool:
    return os.getenv("MOCK_AUTH", "true").lower() == "true"


def _auth_headers(token: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def sign_up(email: str, password: str) -> Dict[str, Any]:
    if _mock_enabled():
        return {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "token_type": "Bearer",
            "expires_in": 300,
        }
    resp = requests.post(f"{AUTH_BASE_URL}{API_PREFIX}/client/sign-up", json={"email": email, "password": password})
    resp.raise_for_status()
    return resp.json()


def sign_in_password(email: str, password: str) -> Dict[str, Any]:
    if _mock_enabled():
        return {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "token_type": "Bearer",
            "expires_in": 300,
        }
    resp = requests.post(f"{AUTH_BASE_URL}{API_PREFIX}/client/sign-in/password", json={"email": email, "password": password})
    resp.raise_for_status()
    return resp.json()


def refresh_token(refresh_token_value: str) -> Dict[str, Any]:
    if _mock_enabled():
        return {
            "access_token": "new_mock_access_token",
            "refresh_token": "new_mock_refresh_token",
            "token_type": "Bearer",
            "expires_in": 300,
        }
    resp = requests.post(f"{AUTH_BASE_URL}{API_PREFIX}/client/refresh_token", json={"refresh_token": refresh_token_value})
    resp.raise_for_status()
    return resp.json()


def logout(token: Optional[str]) -> None:
    if _mock_enabled():
        return None
    resp = requests.post(f"{AUTH_BASE_URL}{API_PREFIX}/client/logout", headers=_auth_headers(token))
    if resp.status_code not in (200, 204):
        resp.raise_for_status()
    return None


def validate_token(token: str) -> Dict[str, Any]:
    if _mock_enabled():
        return {
            "valid": True,
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "exp": 4733728000,
        }
    resp = requests.get(f"{AUTH_BASE_URL}{API_PREFIX}/auth/validate", params={"token": token})
    resp.raise_for_status()
    return resp.json()


def me(token: Optional[str]) -> Dict[str, Any]:
    if _mock_enabled():
        return {
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "email": "user@example.com",
            "orgs": [
                {
                    "org_id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "ООО Рога и Копыта",
                    "role": "owner",
                    "is_owner": True,
                },
                {
                    "org_id": "987fcdeb-51a2-43d1-9f12-345678901234",
                    "name": "ИП Иванов",
                    "role": "member",
                    "is_owner": False,
                },
            ],
            "active_org_id": "123e4567-e89b-12d3-a456-426614174000",
        }
    resp = requests.get(f"{AUTH_BASE_URL}{API_PREFIX}/client/me", headers=_auth_headers(token))
    resp.raise_for_status()
    return resp.json()


def switch_org(token: Optional[str], org_id: str) -> Dict[str, Any]:
    if _mock_enabled():
        return {"active_org_id": org_id}
    resp = requests.patch(
        f"{AUTH_BASE_URL}{API_PREFIX}/client/switch-org",
        headers=_auth_headers(token),
        json={"org_id": org_id},
    )
    resp.raise_for_status()
    return resp.json()


def org_create(token: Optional[str], name: str) -> Dict[str, Any]:
    if _mock_enabled():
        return {"org_id": "123e4567-e89b-12d3-a456-426614174000"}
    resp = requests.post(f"{AUTH_BASE_URL}{API_PREFIX}/org", headers=_auth_headers(token), json={"name": name})
    resp.raise_for_status()
    return resp.json()


def org_get(token: Optional[str], org_id: str) -> Dict[str, Any]:
    if _mock_enabled():
        return {"org_id": org_id, "name": "ООО Рога и Копыта", "owner_id": "550e8400-e29b-41d4-a716-446655440000"}
    resp = requests.get(f"{AUTH_BASE_URL}{API_PREFIX}/org/{org_id}", headers=_auth_headers(token))
    resp.raise_for_status()
    return resp.json()


def org_members(token: Optional[str], org_id: str) -> List[Dict[str, Any]]:
    if _mock_enabled():
        return [
            {"user_id": "550e8400-e29b-41d4-a716-446655440000", "email": "owner@example.com", "role": "owner"},
            {"user_id": "987fcdeb-51a2-43d1-9f12-345678901234", "email": "member@example.com", "role": "member"},
        ]
    resp = requests.get(f"{AUTH_BASE_URL}{API_PREFIX}/org/{org_id}/members", headers=_auth_headers(token))
    resp.raise_for_status()
    return resp.json()


def org_invite(token: Optional[str], org_id: str, email: str) -> Dict[str, Any]:
    if _mock_enabled():
        return {"invite_token": "mock_invite_token"}
    resp = requests.post(f"{AUTH_BASE_URL}{API_PREFIX}/org/{org_id}/invite", headers=_auth_headers(token), json={"email": email})
    resp.raise_for_status()
    return resp.json()


def org_update_role(token: Optional[str], org_id: str, user_id: str, role: str) -> Dict[str, Any]:
    if _mock_enabled():
        return {"user_id": user_id, "role": role}
    resp = requests.patch(
        f"{AUTH_BASE_URL}{API_PREFIX}/org/{org_id}/member/{user_id}/role",
        headers=_auth_headers(token),
        json={"role": role},
    )
    resp.raise_for_status()
    return resp.json()


def org_remove_member(token: Optional[str], org_id: str, user_id: str) -> None:
    if _mock_enabled():
        return None
    resp = requests.delete(f"{AUTH_BASE_URL}{API_PREFIX}/org/{org_id}/member/{user_id}", headers=_auth_headers(token))
    if resp.status_code not in (200, 204):
        resp.raise_for_status()
    return None


def invite_accept(token: Optional[str], invite_token_value: str) -> Dict[str, Any]:
    if _mock_enabled():
        return {
            "org_id": "123e4567-e89b-12d3-a456-426614174000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "role": "member",
        }
    resp = requests.post(
        f"{AUTH_BASE_URL}{API_PREFIX}/invite/accept",
        headers=_auth_headers(token),
        json={"invite_token": invite_token_value},
    )
    resp.raise_for_status()
    return resp.json()


def service_health() -> Dict[str, Any]:
    if _mock_enabled():
        return {"status": "healthy"}
    resp = requests.get(f"{AUTH_BASE_URL}/health")
    resp.raise_for_status()
    return resp.json()


def service_root() -> Dict[str, Any]:
    if _mock_enabled():
        return {"message": "Authentication Service", "version": "1.0.0", "docs": "/docs"}
    resp = requests.get(f"{AUTH_BASE_URL}/")
    resp.raise_for_status()
    return resp.json()



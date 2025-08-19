import os


class UserIdMiddleware:
    """
    Middleware для извлечения заголовков идентичности, проброшенных из Gateway:
      - X-User-Id: внешний UUID пользователя (sub)
      - X-Active-Org-Id: активная организация (UUID)
      - X-User-Email: e-mail пользователя (опционально)
      - X-User-Roles: запятая-разделённый список ролей (опционально)
    Никакой работы с БД здесь нет.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user_id = request.headers.get('X-User-Id')
        request.active_org_id = request.headers.get('X-Active-Org-Id')
        request.user_email = request.headers.get('X-User-Email')
        roles_header = request.headers.get('X-User-Roles')
        request.user_roles = [r.strip() for r in roles_header.split(',')] if roles_header else []

        # Dev mock: подставляем фиктивные данные, если заголовки отсутствуют
        use_mock = os.getenv('MOCK_AUTH', 'true').lower() == 'true'
        if use_mock and not request.user_id:
            request.user_id = '550e8400-e29b-41d4-a716-446655440000'
            request.active_org_id = '123e4567-e89b-12d3-a456-426614174000'
            request.user_email = 'user@example.com'
            request.user_roles = ['member']

        return self.get_response(request)
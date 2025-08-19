from django.db import models


class TokenUsage(models.Model):
    # Внешний идентификатор пользователя (UUID строкой)
    user_sub = models.CharField(max_length=36, blank=True, default="")
    tokens = models.IntegerField(default=0)

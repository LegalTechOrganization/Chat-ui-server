from django.contrib import admin

from .models import Conversation, Message, Setting, EmbeddingDocument, Prompt


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_sub', 'org_id', 'topic', 'created_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_sub', 'get_conversation_topic', 'message', 'is_bot', 'tokens','created_at')

    def get_conversation_topic(self, obj):
        return obj.conversation.topic

    get_conversation_topic.short_description = 'Conversation Topic'


@admin.register(EmbeddingDocument)
class EmbeddingDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_sub', 'org_id', 'title', 'created_at')


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_sub', 'title', 'created_at', 'updated_at')


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ('name', 'value')
from django.db import models
from rest_framework import serializers
from .models import Conversation, Message, Prompt, EmbeddingDocument, Setting

class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ['id', 'sub', 'org_id', 'conversation_id', 'topic', 'created_at', 'updated_at']
        read_only_fields = ('sub', 'org_id', 'conversation_id')

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'sub', 'conversation', 'message_id', 'message', 'is_bot', 'message_type', 'embedding_message_doc', 'messages', 'tokens', 'created_at']
        read_only_fields = ('sub', 'message_id')


class PromptSerializer(serializers.ModelSerializer):

    content = serializers.CharField(trim_whitespace=False, allow_blank=True)

    class Meta:
        model = Prompt
        fields = ['id', 'sub', 'prompt_id', 'title', 'content', 'created_at']
        read_only_fields = ('sub', 'prompt_id')


class EmbeddingDocumentSerializer(serializers.ModelSerializer):
    '''embedding document store'''
    class Meta:
        ''' select fields'''
        model = EmbeddingDocument
        fields = ['id', 'sub', 'org_id', 'document_id', 'title', 'created_at']
        read_only_fields = ('sub', 'org_id', 'document_id', 'faiss_store', 'created_at')


class SettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setting
        fields = ('name', 'value')
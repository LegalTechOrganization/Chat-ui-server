import os
import sys
import asyncio
import json
from hashlib import sha256
import tempfile
import base64
import uuid
import openai
import time
import datetime
try:
    import tiktoken
except Exception:
    tiktoken = None
import logging

from provider.models import ApiKey
from stats.models import TokenUsage
from .models import Conversation, Message, EmbeddingDocument, Setting, Prompt
from django.conf import settings
from django.http import StreamingHttpResponse
from django.forms.models import model_to_dict
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
try:
    from rest_framework_simplejwt.authentication import JWTAuthentication  # optional
except Exception:
    JWTAuthentication = None
from rest_framework.decorators import api_view, authentication_classes, permission_classes, action
from rest_framework.exceptions import ValidationError
from .serializers import ConversationSerializer, MessageSerializer, PromptSerializer, EmbeddingDocumentSerializer, SettingSerializer
from utils.search_prompt import compile_prompt
from utils.duckduckgo_search import web_search, SearchRequest
from .tools import TOOL_LIST
from .llm import get_embedding_document, unpick_faiss, langchain_doc_chat
from .llm import setup_openai_env as llm_openai_env
from .llm import setup_openai_model as llm_openai_model


logger = logging.getLogger(__name__)

class SettingViewSet(viewsets.ModelViewSet):
    serializer_class = SettingSerializer
    # permission_classes = [IsAuthenticated]

    def get_queryset(self):
        available_names = [
            'open_registration',
            'open_web_search',
            'open_api_key_setting',
            'open_frugal_mode_control',
        ]
        return Setting.objects.filter(name__in=available_names)

    def http_method_not_allowed(self, request, *args, **kwargs):
        if request.method != 'GET':
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return super().http_method_not_allowed(request, *args, **kwargs)


class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Используем внешний sub из middleware
        user_sub = getattr(self.request, 'user_id', None)
        active_org_id = getattr(self.request, 'active_org_id', None)
        queryset = Conversation.objects.none()
        if user_sub:
            queryset = Conversation.objects.filter(sub=user_sub)
            if active_org_id:
                queryset = queryset.filter(org_id=active_org_id)
            queryset = queryset.order_by('-created_at')
        return queryset

    def perform_create(self, serializer):
        # Создаем запись, используя внешний идентификатор и организацию
        user_sub = getattr(self.request, 'user_id', None)
        if not user_sub:
            raise ValidationError({"error": "Authentication required. X-User-Data header with valid JWT token is required"})
        
        # Получаем следующий conversation_id для пользователя
        # Ищем максимальный conversation_id только для этого пользователя
        last_conversation = Conversation.objects.filter(sub=user_sub).order_by('-conversation_id').first()
        next_conversation_id = 1 if not last_conversation else last_conversation.conversation_id + 1
        
        serializer.save(
            sub=user_sub, 
            org_id=getattr(self.request, 'active_org_id', None),
            conversation_id=next_conversation_id
        )

    def retrieve(self, request, *args, **kwargs):
        """Получаем беседу по conversation_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        conversation_id = kwargs.get('pk')
        try:
            conversation = Conversation.objects.get(sub=user_sub, conversation_id=conversation_id)
            serializer = self.get_serializer(conversation)
            return Response(serializer.data)
        except Conversation.DoesNotExist:
            return Response({"error": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, *args, **kwargs):
        """Обновляем беседу по conversation_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        conversation_id = kwargs.get('pk')
        try:
            conversation = Conversation.objects.get(sub=user_sub, conversation_id=conversation_id)
            serializer = self.get_serializer(conversation, data=request.data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        except Conversation.DoesNotExist:
            return Response({"error": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, *args, **kwargs):
        """Удаляем беседу по conversation_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        conversation_id = kwargs.get('pk')
        try:
            conversation = Conversation.objects.get(sub=user_sub, conversation_id=conversation_id)
            conversation.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Conversation.DoesNotExist:
            return Response({"error": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['delete'])
    def delete_all(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        queryset.delete()
        return Response(status=204)


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]
    # queryset = Message.objects.all()

    def get_queryset(self):
        # Используем внешний sub и, опционально, org
        user_sub = getattr(self.request, 'user_id', None)
        active_org_id = getattr(self.request, 'active_org_id', None)
        queryset = Message.objects.none()
        if user_sub:
            queryset = Message.objects.filter(sub=user_sub)
            if active_org_id:
                # Для org_id нужно будет добавить логику, если потребуется
                pass
            queryset = queryset.order_by('-created_at')
        conversationId = self.request.query_params.get('conversationId')
        if conversationId:
            queryset = queryset.filter(conversation=conversationId).order_by('created_at')
        return queryset

    def create(self, request, *args, **kwargs):
        # Используем внешний sub из middleware
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required. X-User-Data header with valid JWT token is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Проверяем, передан ли conversation_id или conversation
        conversation_id = request.data.get('conversation_id')
        conversation_value = request.data.get('conversation')
        
        if conversation_id:
            # Если передан conversation_id, проверяем что беседа существует
            try:
                Conversation.objects.get(sub=user_sub, conversation_id=conversation_id)
                data = request.data.copy()
                data['conversation'] = conversation_id
            except Conversation.DoesNotExist:
                return Response({"error": f"Conversation with conversation_id {conversation_id} not found for user"}, status=status.HTTP_404_NOT_FOUND)
        elif conversation_value:
            # Если передан conversation, интерпретируем его как conversation_id
            try:
                Conversation.objects.get(sub=user_sub, conversation_id=conversation_value)
                data = request.data.copy()
                data['conversation'] = conversation_value
            except Conversation.DoesNotExist:
                return Response({"error": f"Conversation with conversation_id {conversation_value} not found for user"}, status=status.HTTP_404_NOT_FOUND)
        else:
            data = request.data
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data['sub'] = user_sub

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        user_sub = getattr(self.request, 'user_id', None)
        if not user_sub:
            raise ValidationError({"error": "Authentication required. X-User-Data header with valid JWT token is required"})
        
        # Получаем следующий message_id для пользователя
        last_message = Message.objects.filter(sub=user_sub).order_by('-message_id').first()
        next_message_id = 1 if not last_message else last_message.message_id + 1
        
        serializer.save(sub=user_sub, message_id=next_message_id)

    def retrieve(self, request, *args, **kwargs):
        """Получаем сообщение по message_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        message_id = kwargs.get('pk')
        try:
            message = Message.objects.get(sub=user_sub, message_id=message_id)
            serializer = self.get_serializer(message)
            return Response(serializer.data)
        except Message.DoesNotExist:
            return Response({"error": "Message not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, *args, **kwargs):
        """Обновляем сообщение по message_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        message_id = kwargs.get('pk')
        try:
            message = Message.objects.get(sub=user_sub, message_id=message_id)
            serializer = self.get_serializer(message, data=request.data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        except Message.DoesNotExist:
            return Response({"error": "Message not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, *args, **kwargs):
        """Удаляем сообщение по message_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        message_id = kwargs.get('pk')
        try:
            message = Message.objects.get(sub=user_sub, message_id=message_id)
            message.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Message.DoesNotExist:
            return Response({"error": "Message not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['delete'])
    def delete_all(self, request):
        """Удаляем все сообщения конкретной беседы"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Получаем conversation_id из query параметров
        conversation_id = request.query_params.get('conversationId')
        if not conversation_id:
            return Response({"error": "conversationId parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Проверяем, что беседа существует
            Conversation.objects.get(sub=user_sub, conversation_id=conversation_id)
            
            # Удаляем все сообщения этой беседы
            deleted_count = Message.objects.filter(sub=user_sub, conversation=conversation_id).delete()[0]
            
            return Response({
                "deleted": True,
                "conversation_id": conversation_id,
                "deleted_count": deleted_count
            }, status=status.HTTP_200_OK)
            
        except Conversation.DoesNotExist:
            return Response({"error": f"Conversation with conversation_id {conversation_id} not found for user"}, status=status.HTTP_404_NOT_FOUND)


class PromptViewSet(viewsets.ModelViewSet):
    serializer_class = PromptSerializer
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_sub = getattr(self.request, 'user_id', None)
        if user_sub:
            return Prompt.objects.filter(sub=user_sub).order_by('-created_at')
        else:
            return Prompt.objects.none()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Используем внешний sub из middleware
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required. X-User-Data header with valid JWT token is required"}, status=status.HTTP_400_BAD_REQUEST)
        serializer.validated_data['sub'] = user_sub

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        user_sub = getattr(self.request, 'user_id', None)
        if not user_sub:
            raise ValidationError({"error": "Authentication required. X-User-Data header with valid JWT token is required"})
        
        # Получаем следующий prompt_id для пользователя
        last_prompt = Prompt.objects.filter(sub=user_sub).order_by('-prompt_id').first()
        next_prompt_id = 1 if not last_prompt else last_prompt.prompt_id + 1
        
        serializer.save(sub=user_sub, prompt_id=next_prompt_id)

    def retrieve(self, request, *args, **kwargs):
        """Получаем промпт по prompt_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        prompt_id = kwargs.get('pk')
        try:
            prompt = Prompt.objects.get(sub=user_sub, prompt_id=prompt_id)
            serializer = self.get_serializer(prompt)
            return Response(serializer.data)
        except Prompt.DoesNotExist:
            return Response({"error": "Prompt not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, *args, **kwargs):
        """Обновляем промпт по prompt_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        prompt_id = kwargs.get('pk')
        try:
            prompt = Prompt.objects.get(sub=user_sub, prompt_id=prompt_id)
            serializer = self.get_serializer(prompt, data=request.data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        except Prompt.DoesNotExist:
            return Response({"error": "Prompt not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, *args, **kwargs):
        """Удаляем промпт по prompt_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        prompt_id = kwargs.get('pk')
        try:
            prompt = Prompt.objects.get(sub=user_sub, prompt_id=prompt_id)
            prompt.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Prompt.DoesNotExist:
            return Response({"error": "Prompt not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['delete'])
    def delete_all(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        queryset.delete()
        return Response(status=204)


class EmbeddingDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = EmbeddingDocumentSerializer
    # authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_sub = getattr(self.request, 'user_id', None)
        active_org_id = getattr(self.request, 'active_org_id', None)
        if user_sub:
            qs = EmbeddingDocument.objects.filter(sub=user_sub)
            if active_org_id:
                qs = qs.filter(org_id=active_org_id)
            return qs.order_by('-created_at')
        else:
            return EmbeddingDocument.objects.none()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Используем внешний sub/org_id из middleware
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required. X-User-Data header with valid JWT token is required"}, status=status.HTTP_400_BAD_REQUEST)
        serializer.validated_data['sub'] = user_sub
        serializer.validated_data['org_id'] = getattr(request, 'active_org_id', None)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_embedding(self):
        """get the faiss_store of uploaded file"""

        openai_api_key = self.request.data.get('openaiApiKey', None)
        api_key = None

        if openai_api_key is None:
            openai_api_key = get_api_key_from_setting()

        if openai_api_key is None:
            api_key = get_api_key()
            if api_key:
                openai_api_key = api_key.key
            else:
                return Response(
                    {
                        'error': 'There is no available API key'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        my_openai = get_openai(openai_api_key)
        llm_openai_env(my_openai.api_base, my_openai.api_key)

        # Get the uploaded file from the request
        file_data = self.request.data.get('file')
        file_mime, file_url = file_data.split(',')
        file_mime = file_mime.split(':')[1].split(';')[0]
        file_bytes = base64.b64decode(file_url)

        logger.debug('user_sub %s upload a file %s %s', getattr(self.request, 'user_id', None), file_mime, self.request.data['title'])

        with tempfile.TemporaryDirectory() as tmpdirname:
            dump_basename = 'fh' + str(uuid.uuid4()).replace('-', '')
            dump_name = os.path.join(tmpdirname, dump_basename)
            if 'text/' in file_mime:
                file_content = file_bytes.decode('utf-8')
                mode = 'w'
            else:
                file_content = file_bytes
                mode = 'wb'
            # dump_basename = 'fh' + str(uuid.uuid4()).replace('-', '')
            # dump_name = os.path.join(tmpdirname, dump_basename)
            with open(dump_name, mode) as f:
                f.write(file_content)

            faiss_store = get_embedding_document(dump_name, file_mime)

        return faiss_store

    def perform_create(self, serializer):
        faiss_store = self.get_embedding()

        # Set the `value` field on the serializer instance
        serializer.validated_data['faiss_store'] = faiss_store

        # Получаем следующий document_id для пользователя
        user_sub = getattr(self.request, 'user_id', None)
        last_document = EmbeddingDocument.objects.filter(sub=user_sub).order_by('-document_id').first()
        next_document_id = 1 if not last_document else last_document.document_id + 1
        
        # Call the serializer's `save` method to create the new instance
        serializer.save(document_id=next_document_id)

    def retrieve(self, request, *args, **kwargs):
        """Получаем документ по document_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        document_id = kwargs.get('pk')
        try:
            document = EmbeddingDocument.objects.get(sub=user_sub, document_id=document_id)
            serializer = self.get_serializer(document)
            return Response(serializer.data)
        except EmbeddingDocument.DoesNotExist:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, *args, **kwargs):
        """Обновляем документ по document_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        document_id = kwargs.get('pk')
        try:
            document = EmbeddingDocument.objects.get(sub=user_sub, document_id=document_id)
            serializer = self.get_serializer(document, data=request.data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        except EmbeddingDocument.DoesNotExist:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, *args, **kwargs):
        """Удаляем документ по document_id вместо id"""
        user_sub = getattr(request, 'user_id', None)
        if not user_sub:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        document_id = kwargs.get('pk')
        try:
            document = EmbeddingDocument.objects.get(sub=user_sub, document_id=document_id)
            document.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except EmbeddingDocument.DoesNotExist:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)

    def perform_update(self, serializer):
        faiss_store = self.get_embedding()

        # Set the `value` field on the serializer instance
        serializer.validated_data['faiss_store'] = faiss_store

        # Call the serializer's `save` method to update the instance
        serializer.save()

    @action(detail=False, methods=['delete'])
    def delete_all(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        queryset.delete()
        return Response(status=204)


MODELS = {
    'gpt-3.5-turbo': {
        'name': 'gpt-3.5-turbo',
        'max_tokens': 4096,
        'max_prompt_tokens': 3096,
        'max_response_tokens': 1000
    },
    'gpt-4': {
        'name': 'gpt-4',
        'max_tokens': 8192,
        'max_prompt_tokens': 6192,
        'max_response_tokens': 2000
    },
    'gpt-3.5-turbo-16k': {
        'name': 'gpt-3.5-turbo-16k',
        'max_tokens': 16384,
        'max_prompt_tokens': 12384,
        'max_response_tokens': 4000
    },
    'gpt-4-32k': {
        'name': 'gpt-4-32k',
        'max_tokens': 32768,
        'max_prompt_tokens': 24768,
        'max_response_tokens': 8000
    },
    'gpt-4-1106-preview': {
        'name': 'gpt-4-1106-preview',
        'max_tokens': 131072,
        'max_prompt_tokens': 123072,
        'max_response_tokens': 8000,
    },
    'gpt-4o': {
        'name': 'gpt-4o',
        'max_tokens': 131072,
        'max_prompt_tokens': 123072,
        'max_response_tokens': 8000,
    }    
}


def sse_pack(event, data):
    # Format data as an SSE message
    packet = "event: %s\n" % event
    packet += "data: %s\n" % json.dumps(data)
    packet += "\n"
    return packet


@api_view(['POST'])
def gen_title(request):
    conversation_id = request.data.get('conversationId')
    prompt = request.data.get('prompt')
    conversation_obj = Conversation.objects.get(id=conversation_id)
    message = Message.objects.filter(conversation_id=conversation_id).order_by('created_at').first()
    openai_api_key = request.data.get('openaiApiKey')
    api_key = None

    if openai_api_key is None:
        openai_api_key = get_api_key_from_setting()

    if openai_api_key is None:
        api_key = get_api_key()
        if api_key:
            openai_api_key = api_key.key
        else:
            return Response(
                {
                    'error': 'There is no available API key'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

    if prompt is None:
        prompt = 'Generate a short title for the following content, no more than 10 words. \n\nContent: '

    messages = [
        {"role": "user", "content": prompt + message.message},
    ]

    my_openai = get_openai(openai_api_key)
    try:
        openai_response = my_openai.ChatCompletion.create(
            model='gpt-3.5-turbo-0301',
            messages=messages,
            max_tokens=256,
            temperature=0.5,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
        completion_text = openai_response['choices'][0]['message']['content']
        title = completion_text.strip().replace('"', '')

        # increment the token count
        increase_token_usage(getattr(request, 'user_id', None), openai_response['usage']['total_tokens'], api_key)
    except Exception as e:
        print(e)
        title = 'Untitled Conversation'
    # update the conversation title
    conversation_obj.topic = title
    conversation_obj.save()

    return Response({
        'title': title
    })


@api_view(['POST'])
def upload_conversations(request):
    """allow user to import a list of conversations"""
    user_sub = getattr(request, 'user_id', None)
    import_err_msg = 'bad_import'
    conversation_ids = []
    try:
        imports = request.data.get('imports')
        # verify
        conversations = []
        for conversation in imports:
            topic = conversation.get('conversation_topic', None)
            messages = []
            for message in conversation.get('messages'):
                msg = {}
                msg['role'] = message['role']
                msg['content'] = message['content']
                messages.append(msg)
            if len(messages) > 0:
                conversations.append({
                    'topic': topic,
                    'messages': messages,
                })
        # dump
        for conversation in conversations:
            topic = conversation['topic']
            messages = conversation['messages']
            cobj = Conversation(
                topic=topic if topic else '',
                user_sub=user_sub,
                org_id=getattr(request, 'active_org_id', None),
            )
            cobj.save()
            conversation_ids.append(cobj.id)
            for idx, msg in enumerate(messages):
                try:
                    Message._meta.get_field('user_sub')
                    mobj = Message(
                        user_sub=user_sub,
                        conversation=cobj,
                        message=msg['content'],
                        is_bot=msg['role'] != 'user',
                        messages=messages[:idx + 1],
                    )
                except:
                    mobj = Message(
                        conversation=cobj,
                        user_sub=user_sub,
                        message=msg['content'],
                        is_bot=msg['role'] != 'user',
                        messages=messages[:idx + 1],
                    )
                mobj.save()
    except Exception as e:
        logger.debug(e)
        return Response(
            {'error': import_err_msg},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # return a list of new conversation id
    return Response(conversation_ids)


@api_view(['POST'])
def conversation(request):
    model_name = request.data.get('name')
    message_object_list = request.data.get('message')
    conversation_id = request.data.get('conversationId')
    request_max_response_tokens = request.data.get('max_tokens')
    system_content = request.data.get('system_content')
    if not system_content:
        system_content = "You are a helpful assistant."
    temperature = request.data.get('temperature', 0.7)
    top_p = request.data.get('top_p', 1)
    frequency_penalty = request.data.get('frequency_penalty', 0)
    presence_penalty = request.data.get('presence_penalty', 0)
    web_search_params = request.data.get('web_search')
    openai_api_key = request.data.get('openaiApiKey')
    frugal_mode = request.data.get('frugalMode', False)

    message_object = message_object_list[-1]
    message_type = message_object.get('message_type', 0)
    tool_name = message_object.get('tool', None)
    tool_args = message_object.get('tool_args', None)
    if tool_name:
        tool = {'name': tool_name, 'args': tool_args}
    else:
        tool = None

    logger.debug('conversation_id = %s message_objects = %s', conversation_id, message_object_list)

    api_key = None

    if openai_api_key is None:
        openai_api_key = get_api_key_from_setting()

    if openai_api_key is None:
        api_key = get_api_key()
        if api_key:
            openai_api_key = api_key.key
        else:
            return Response(
                {
                    'error': 'There is no available API key'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

    my_openai = get_openai(openai_api_key)
    llm_openai_env(my_openai.api_base, my_openai.api_key)

    model = get_current_model(model_name, request_max_response_tokens)
    llm_openai_model(model)

    try:
        messages = build_messages(model, getattr(request, 'user_id', None), conversation_id, message_object_list, web_search_params, system_content, frugal_mode, tool, message_type)
        # message_object_list will be changed in build_messages

        new_doc_id = messages.get('doc_id', None)
        new_doc_title = messages.get('doc_title', None)
        logger.debug('messages: %s\n%s\n%s', messages, new_doc_id, new_doc_title)
    except Exception as e:
        print(e)
        return Response(
            {
                'error': e
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    def stream_content():
        try:
            if messages['renew']:
                openai_response = my_openai.ChatCompletion.create(
                    model=model['name'],
                    messages=messages['messages'],
                    max_tokens=model['max_response_tokens'],
                    temperature=temperature,
                    top_p=top_p,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                    stream=True,
                )
        except Exception as e:
            yield sse_pack('error', {
                'error': str(e)
            })
            print('openai error', e)
            return

        if conversation_id:
            # get the conversation
            conversation_obj = Conversation.objects.get(id=conversation_id)
        else:
            # create a new conversation
            conversation_obj = Conversation(user_sub=getattr(request, 'user_id', None), org_id=getattr(request, 'active_org_id', None))
            conversation_obj.save()

        # insert new messages
        try:
            for m in message_object_list:
                message_obj = create_message(
                    user_sub=getattr(request, 'user_id', None),
                    conversation_id=conversation_obj.id,
                    message=m['content'],
                    message_type=m.get('message_type', 0),
                    embedding_doc_id=m.get('embedding_message_doc', 0),
                    messages=messages['messages'],
                    tokens=messages['tokens'],
                    api_key=api_key
                )
                yield sse_pack('userMessageId', {
                    'userMessageId': message_obj.id,
                })
        except Exception as e:
            return Response(
                {
                    'error': e
                },
                status=status.HTTP_400_BAD_REQUEST
            ) 

        collected_events = []
        completion_text = ''
        if messages['renew']:  # return LLM answer
            # iterate through the stream of events
            for event in openai_response:
                collected_events.append(event)  # save the event response
                # print(event)
                if event['choices'][0]['finish_reason'] is not None:
                    break
                if 'content' in event['choices'][0]['delta']:
                    event_text = event['choices'][0]['delta']['content']
                    completion_text += event_text  # append the text
                    yield sse_pack('message', {'content': event_text})
            bot_message_type = Message.plain_message_type
            ai_message_token = num_tokens_from_text(completion_text, model['name'])
        else:  # wait for process context
            if new_doc_title:
                completion_text = f'{new_doc_title} added.'
            else:
                completion_text = 'Context added.'
            yield sse_pack('message', {'content': completion_text})
            bot_message_type = Message.temp_message_type
            ai_message_token = 0

        ai_message_obj = create_message(
            user_sub=getattr(request, 'user_id', None),
            conversation_id=conversation_obj.id,
            message=completion_text,
            message_type=bot_message_type,
            is_bot=True,
            tokens=ai_message_token,
            api_key=api_key
        )
        yield sse_pack('done', {
            'messageId': ai_message_obj.id,
            'conversationId': conversation_obj.id,
            'newDocId': new_doc_id,
        })

    def stream_langchain():
        if messages['renew']:  # if the new user message is sending to AI
            try:
                # get a results generator
                gen = langchain_doc_chat(messages)
            except Exception as e:
                yield sse_pack('error', {
                    'error': str(e)
                })
                logger.debug('langchain error %s', e)
        # create conversation
        if conversation_id:
            # get the conversation
            conversation_obj = Conversation.objects.get(id=conversation_id)
        else:
            # create a new conversation
            conversation_obj = Conversation(user_sub=getattr(request, 'user_id', None), org_id=getattr(request, 'active_org_id', None))
            conversation_obj.save()
        # insert new user messages
        try:
            for m in message_object_list:
                message_obj = create_message(
                    user_sub=getattr(request, 'user_id', None),
                    conversation_id=conversation_obj.id,
                    message=m['content'],
                    message_type=m.get('message_type', 0),
                    embedding_doc_id=m.get('embedding_message_doc', 0),
                    messages=messages['messages'],
                    tokens=messages['tokens'],
                    api_key=api_key
                )
                yield sse_pack('userMessageId', {
                    'userMessageId': message_obj.id,
                })
        except Exception as e:
            return Response({'error': e}, status=status.HTTP_400_BAD_REQUEST)

        completion_text = ''
        if messages['renew']:  # if AI has read and replied this message
            for event in gen:
                if event['status'] == 'done':
                    pass
                else:
                    text = event['content']
                    if text:
                        completion_text += str(text)
                        yield sse_pack('message', {'content': str(text)})
            bot_message_type = Message.plain_message_type
        else:   # else, this message was not produced by AI
            if new_doc_title:
                completion_text = f'{new_doc_title} added.'
            else:
                completion_text = 'Context added.'
            yield sse_pack('message', {'content': completion_text})
            bot_message_type = Message.temp_message_type

        logger.debug('return message is: %s', completion_text)
        ai_message_token = num_tokens_from_text(completion_text, model['name'])
        ai_message_obj = create_message(
            user_sub=getattr(request, 'user_id', None),
            conversation_id=conversation_obj.id,
            message=completion_text,
            message_type=bot_message_type,
            is_bot=True,
            tokens=ai_message_token,
            api_key=api_key
        )
        yield sse_pack('done', {
            'messageId': ai_message_obj.id,
            'conversationId': conversation_obj.id,
            'newDocId': new_doc_id,
        })

    if messages.get('faiss_store', None) and not web_search_params:
        # this conversation has contexts, and this is not a web search
        response = StreamingHttpResponse(
            stream_langchain(),  # response generator
            content_type='text/event-stream'
        )
    else:
        response = StreamingHttpResponse(
            stream_content(),
            content_type='text/event-stream'
        )
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-cache'
    return response


@api_view(['POST'])
def documents(request):
    pass


def create_message(user_sub, conversation_id, message, is_bot=False, message_type=0, embedding_doc_id=None, messages='', tokens=0, api_key=None):
    message_obj = Message(
        conversation_id=conversation_id,
        user_sub=user_sub,
        message=message,
        is_bot=is_bot,
        message_type=message_type,
        embedding_message_doc=EmbeddingDocument.objects.get(pk=embedding_doc_id) if embedding_doc_id else None,
        messages=messages,
        tokens=tokens,
    )
    if message_type != Message.temp_message_type:
        message_obj.save()

    increase_token_usage(user_sub, tokens, api_key)

    return message_obj


def increase_token_usage(user_sub, tokens, api_key=None):
    token_usage, created = TokenUsage.objects.get_or_create(user_sub=user_sub)
    token_usage.tokens += tokens
    token_usage.save()

    if api_key:
        api_key.token_used += tokens
        api_key.save()


def build_messages(model, user_sub, conversation_id, new_messages, web_search_params, system_content, frugal_mode = False, tool = None, message_type=0):
    if conversation_id:
        ordered_messages = Message.objects.filter(conversation_id=conversation_id).order_by('created_at')
        ordered_messages_list = list(ordered_messages)
    else:
        ordered_messages_list = []

    ordered_messages_list += [{
        'is_bot': False,
        'message': msg['content'], 
        'message_type': message_type,
        'embedding_message_doc': msg.get('embedding_message_doc', None),
    } for msg in new_messages]

    if frugal_mode:
        ordered_messages_list = ordered_messages_list[-1:]

    system_messages = [{"role": "system", "content": system_content}]

    current_token_count = num_tokens_from_messages(system_messages, model['name'])

    max_token_count = model['max_prompt_tokens']

    messages = []

    result = {
        'renew': True,
        'messages': messages,
        'tokens': 0,
        'faiss_store': None,
        'doc_id': None,  # new doc id
    }

    faiss_store = None

    logger.debug('new message is: %s', new_messages)
    logger.debug('messages are: %s', ordered_messages_list)
    first_msg = True

    while current_token_count < max_token_count and len(ordered_messages_list) > 0:
        message = ordered_messages_list.pop()
        if isinstance(message, Message):
            message = model_to_dict(message)
        role = "assistant" if message['is_bot'] else "user"
        message_content = message['message']
        message_type = message['message_type']
        if web_search_params is not None and first_msg:
            search_results = web_search(SearchRequest(message['message'], ua=web_search_params['ua']), num_results=5)
            message_content = compile_prompt(search_results, message['message'], default_prompt=web_search_params['default_prompt'])
        if tool and first_msg:  # apply to latest message only
            tool_name = tool['name']
            func = TOOL_LIST.get(tool_name, None)
            if tool_name == 'arxiv':
                if not tool.get('args', None):
                    tool['args'] = {}
                args = tool['args']
                args['conversation_id'] = conversation_id
                args['user_sub'] = user_sub
            if func:
                message_content = func(message['message'], tool['args'])
        if message_type in [
            Message.hidden_message_type,
            Message.arxiv_context_message_type,
            Message.doc_context_message_type,
        ]:
            # these messages only attached context to the conversation
            # they should not be sent to the LLM
            if first_msg:  # if the new message is a contextual message
                result['renew'] = False
            if message_type == Message.doc_context_message_type:
                doc_id = message["embedding_message_doc"]
                logger.debug('get a document %s', message_content)
                if doc_id:
                    logger.debug('get the document id %s', doc_id)
                    doc_obj = EmbeddingDocument.objects.get(id=doc_id)
                    if doc_obj:
                        logger.debug('get the document obj %s %s', doc_id, doc_obj.title)
                        vector_store = unpick_faiss(doc_obj.faiss_store)
                        if faiss_store:
                            faiss_store.merge_from(vector_store)
                        else:
                            faiss_store = vector_store
                        logger.debug('document obj %s %s loaded', doc_id, doc_obj.title)
            elif message_type == Message.arxiv_context_message_type:
                if first_msg:
                    doc_id = tool['args'].get('embedding_doc_id', None)
                    doc_title = tool['args'].get('doc_title', None)
                    new_messages[-1]['content'] = message_content
                    new_messages[-1]['embedding_message_doc'] = doc_id
                    result['doc_id'] = doc_id
                    result['doc_title'] = doc_title
                else:
                    doc_id = message['embedding_message_doc']
                if doc_id:
                    message['embedding_message_doc'] = doc_id
                    logger.debug('get the arxiv document id %s', doc_id)
                    doc_obj = EmbeddingDocument.objects.get(id=doc_id)
                    if doc_obj:
                        logger.debug('get the document obj %s %s', doc_id, doc_obj.title)
                        vector_store = unpick_faiss(doc_obj.faiss_store)
                        if faiss_store:
                            faiss_store.merge_from(vector_store)
                        else:
                            faiss_store = vector_store
                        logger.debug('document obj %s %s loaded', doc_id, doc_obj.title)
                else:
                    raise RuntimeError('ArXiv document failed to download or embed')
        else:
            new_message = {"role": role, "content": message_content}
            new_token_count = num_tokens_from_messages(system_messages + messages + [new_message], model['name'])
            if new_token_count > max_token_count:
                if len(messages) > 0:
                    break
                raise ValueError(
                    f"Prompt is too long. Max token count is {max_token_count}, but prompt is {new_token_count} tokens long.")
            messages.insert(0, new_message)
            current_token_count = new_token_count
        first_msg = False

    result['messages'] = system_messages + messages
    result['tokens'] = current_token_count
    result['faiss_store'] = faiss_store

    return result


def get_current_model(model_name, request_max_response_tokens):
    if model_name is None:
        model_name ="gpt-3.5-turbo"
    model = MODELS[model_name]
    if request_max_response_tokens is not None:
        model['max_response_tokens'] = int(request_max_response_tokens)
        model['max_prompt_tokens'] = model['max_tokens'] - model['max_response_tokens']
    return model


def get_api_key_from_setting():
    row = Setting.objects.filter(name='openai_api_key').first()
    if row and row.value != '':
        return row.value
    return None


def get_api_key():
    return ApiKey.objects.filter(is_enabled=True).order_by('token_used').first()


def num_tokens_from_text(text, model="gpt-3.5-turbo-0301"):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    if model in ["gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4", "gpt-4-32k"]:
        print(
            f"Warning: {model} may change over time.",
            f"Returning num tokens assuming {model}-0613."
        )
        return num_tokens_from_text(text, model=f"{model}-0613")

    if model not in [
        "gpt-3.5-turbo-0613",
        "gpt-4-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-32k-0613",
        "gpt-4-1106-preview",
        "gpt-4o"
    ]:
        raise NotImplementedError(
            f"num_tokens_from_text() is not implemented for model {model}.")

    return len(encoding.encode(text))


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    if model in ["gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4", "gpt-4-32k"]:
        print(
            f"Warning: {model} may change over time.",
            f"Returning num tokens assuming {model}-0613."
        )
        return num_tokens_from_messages(messages, model=f"{model}-0613")

    if model in [
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-32k-0613",
        "gpt-4-1106-preview",
        "gpt-4o"
    ]:
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1    # if there's a name, the role is omitted
    elif model in ["gpt-4-0613"]:
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        raise NotImplementedError((
            f"num_tokens_from_messages() is not implemented for model {model}. "
            "See https://github.com/openai/openai-python/blob/main/chatml.md "
            "for information on how messages are converted to tokens."
        ))

    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def get_openai(openai_api_key):
    openai.api_key = openai_api_key
    proxy = os.getenv('OPENAI_API_PROXY')
    if proxy:
        openai.api_base = proxy
    return openai

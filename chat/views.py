from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Conversation, Message
from .crypto import encrypt_message


@login_required
def conversation_list(request):
    conversations = Conversation.objects.filter(
        participants=request.user
    ).prefetch_related('participants').order_by('-created_at')

    return render(request, 'chat/conversation_list.html', {
        'conversations': conversations,
    })


@login_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user,
    )


    chat_messages = conversation.messages.select_related('sender').order_by('created_at')

    return render(request, 'chat/conversation_detail.html', {
        'conversation': conversation,
        'chat_messages': chat_messages,
    })

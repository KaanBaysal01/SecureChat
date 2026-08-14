from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Conversation, Message
from .crypto import encrypt_message
from .forms import NewConversationForm


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

@login_required
def new_conversation(request):
    if request.method == 'POST':
        form = NewConversationForm(request.POST,current_user = request.user)
        if form.is_valid():
            participants = form.cleaned_data['participants']
            name = form.cleaned_data['name']

            conversation = Conversation.objects.create(
                name = name or None,
                is_group = len(participants) > 1 ,
            )
            conversation.participants.add(request.user,*participants)

            return redirect('chat:conversation_detail',conversation_id = conversation.id)

    else:
            form = NewConversationForm(current_user = request.user)

    return render(request, 'chat/new_conversation.html',{'form':form})
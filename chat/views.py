from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Conversation, Message
from .crypto import encrypt_message
from .forms import NewConversationForm
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

class ConversationListView(LoginRequiredMixin,View):
    def get(self, request):
        conversations = Conversation.objects.filter(
        participants=request.user
            ).prefetch_related('participants').order_by('-created_at')

        items = []
        for c in conversations:
            last = c.messages.select_related('sender').last()

            unread = c.messages.exclude(sender=request.user).exclude(
                read_statuses__user=request.user
            ).count()

            others = [p for p in c.participants.all() if p != request.user]

            if c.is_group:
                title = c.name or f"Grup #{c.id}"
            elif others:
                title = others[0].username
            else:
                title = f"Sohbet #{c.id}"

            items.append({
                'conversation': c,
                'last': last,
                'unread': unread,
                'others': others,
                'title': title,
            })

        return render(request, 'chat/conversation_list.html', {
            'items': items,
        })


class ConversationDetailView(LoginRequiredMixin, View):
    def get(self, request, conversation_id):
        conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user,
        )
        chat_messages = conversation.messages.select_related('sender').order_by('created_at')

        others = [p for p in conversation.participants.all() if p != request.user]

        if conversation.is_group:
                title = conversation.name or f"Grup #{conversation.id}"
                subtitle = ", ".join(p.username for p in others)
        elif others:
                title = others[0].username
                subtitle = ""
        else:
                title = f"Sohbet #{conversation.id}"
                subtitle = ""

        return render(request, 'chat/conversation_detail.html', {
                'conversation': conversation,
                'chat_messages': chat_messages,
                'others': others,
                'title': title,
                'subtitle': subtitle,
        })

class NewConversationView(LoginRequiredMixin, View):
    def get(self, request):
        form = NewConversationForm(current_user=request.user)
        return render(request, 'chat/new_conversation.html', {'form': form})

    def post(self, request):
        form = NewConversationForm(request.POST, current_user=request.user)

        if form.is_valid():
            participants = form.cleaned_data['participants']
            name = form.cleaned_data['name']

            conversation = Conversation.objects.create(
                name=name or None,
                is_group=len(participants) > 1,
            )
            conversation.participants.add(request.user, *participants)

            return redirect('chat:conversation_detail', conversation_id=conversation.id)

        return render(request, 'chat/new_conversation.html', {'form': form})
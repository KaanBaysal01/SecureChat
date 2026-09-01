from django.shortcuts import render, redirect, get_object_or_404
from .models import Conversation, Message
from .forms import NewConversationForm
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
import uuid
from pathlib import Path
from urllib.parse import quote
from django.conf import settings
from django.db.models import Sum
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.urls import reverse
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .forms import FileUploadForm
from .filecrypto import encrypt_to_file, decrypt_from_file
from django.template.defaultfilters import filesizeformat
from django.core import signing

class ConversationListView(LoginRequiredMixin, View):
    def get(self, request):
        conversations = (
            Conversation.objects.filter(participants=request.user)
            .prefetch_related("participants")
            .order_by("-created_at")
        )

        items = []
        for c in conversations:
            last = c.messages.select_related("sender").last()

            unread = (
                c.messages.exclude(sender=request.user)
                .exclude(read_statuses__user=request.user)
                .count()
            )

            others = [p for p in c.participants.all() if p != request.user]

            if c.is_group:
                title = c.name or f"Grup #{c.id}"
            elif others:
                title = others[0].username
            else:
                title = f"Sohbet #{c.id}"

            items.append(
                {
                    "conversation": c,
                    "last": last,
                    "unread": unread,
                    "others": others,
                    "title": title,
                }
            )

        return render(
            request,
            "chat/conversation_list.html",
            {
                "items": items,
            },
        )


class ConversationDetailView(LoginRequiredMixin, View):
    def get(self, request, conversation_id):
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user,
        )
        chat_messages = conversation.messages.select_related("sender").order_by(
            "created_at"
        )

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

        return render(
            request,
            "chat/conversation_detail.html",
            {
                "conversation": conversation,
                "chat_messages": chat_messages,
                "others": others,
                "title": title,
                "subtitle": subtitle,
                "can_unpin": conversation.can_unpin(request.user),
                "is_admin": conversation.is_group and conversation.is_admin(request.user),
            },
        )


class NewConversationView(LoginRequiredMixin, View):
    def get(self, request):
        form = NewConversationForm(current_user=request.user)
        return render(
            request,
            "chat/new_conversation.html",
            {"form": form, "users": form.fields["participants"].queryset.order_by("username")},
        )

    def post(self, request):
        form = NewConversationForm(request.POST, current_user=request.user)

        if form.is_valid():
            participants = form.cleaned_data["participants"]
            name = form.cleaned_data["name"]

            conversation = Conversation.objects.create(
                name=name or None,
                is_group=len(participants) > 1,
            )
            conversation.participants.add(request.user, *participants)
            if conversation.is_group:
                conversation.admins.add(request.user)

            return redirect("chat:conversation_detail", conversation_id=conversation.id)

        return render(
            request,
            "chat/new_conversation.html",
            {"form": form, "users": form.fields["participants"].queryset.order_by("username")},
        )

class GroupSettingsView(LoginRequiredMixin, View):
    def get(self, request, conversation_id):
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user,
            is_group=True,
        )

        admin_ids = set(conversation.admins.values_list("id", flat=True))
        members = conversation.participants.order_by("username")

        addable = request.user.get_friends().exclude(
            id__in=conversation.participants.values_list("id", flat=True)
        ).order_by("username")

        related_ids = request.user.get_related_ids()

        invite_url = None
        if request.user.id in admin_ids:
            token = signing.dumps(
                {
                    "conversation_id": conversation.id,
                    "v": conversation.invite_version,
                },
                salt="group-invite",
            )
            invite_url = request.build_absolute_uri(
                reverse("chat:join_group", args=[token])
            )

        return render(
            request,
            "chat/group_settings.html",
            {
                "conversation": conversation,
                "members": members,
                "admin_ids": admin_ids,
                "is_admin": request.user.id in admin_ids,
                "addable": addable,
                "related_ids": related_ids,
                "invite_url": invite_url,
            },
        )


class MakeAdminView(LoginRequiredMixin, View):
    def post(self, request, conversation_id, user_id):
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user,
            is_group=True,
        )

        if not conversation.is_admin(request.user):
            messages.error(request, "Bu işlem için yönetici olmalısın.")
            return redirect("chat:group_settings", conversation_id=conversation.id)

        target = conversation.participants.filter(id=user_id).first()
        if not target:
            messages.error(request, "Kullanıcı bu grupta değil.")
            return redirect("chat:group_settings", conversation_id=conversation.id)

        conversation.admins.add(target)
        messages.success(request, f"{target.username} artık yönetici.")
        return redirect("chat:group_settings", conversation_id=conversation.id)


class RemoveMemberView(LoginRequiredMixin, View):
    def post(self, request, conversation_id, user_id):
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user,
            is_group=True,
        )

        if not conversation.is_admin(request.user):
            messages.error(request, "Bu işlem için yönetici olmalısın.")
            return redirect("chat:group_settings", conversation_id=conversation.id)

        if user_id == request.user.id:
            messages.error(request, "Kendini çıkaramazsın, gruptan ayrılabilirsin.")
            return redirect("chat:group_settings", conversation_id=conversation.id)

        target = conversation.participants.filter(id=user_id).first()
        if not target:
            messages.error(request, "Kullanıcı bu grupta değil.")
            return redirect("chat:group_settings", conversation_id=conversation.id)

        conversation.participants.remove(target)
        conversation.admins.remove(target)

        broadcast_system_event(conversation, request.user, f"{request.user.username}, {target.username} kullanıcısını çıkardı.")
        messages.info(request, f"{target.username} gruptan çıkarıldı.")

        messages.info(request, f"{target.username} gruptan çıkarıldı.")
        return redirect("chat:group_settings", conversation_id=conversation.id)


class LeaveGroupView(LoginRequiredMixin, View):
    def post(self, request, conversation_id):
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user,
            is_group=True,
        )

        conversation.participants.remove(request.user)
        conversation.admins.remove(request.user)

        if conversation.participants.count() == 0:
            conversation.delete()
            messages.info(request, "Gruptan ayrıldın, grup kapandı.")
            return redirect("chat:conversation_list")

        broadcast_system_event(conversation, request.user, f"{request.user.username} gruptan ayrıldı.")

        if conversation.admins.count() == 0:
            new_admin = conversation.participants.order_by("id").first()
            conversation.admins.add(new_admin)

        messages.info(request, "Gruptan ayrıldın.")
        return redirect("chat:conversation_list")

class DeleteConversationView(LoginRequiredMixin, View):
    def post(self, request, conversation_id):
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user,
        )

        if conversation.is_group and not conversation.is_admin(request.user):
            messages.error(request, "Grubu sadece yönetici silebilir.")
            return redirect("chat:group_settings", conversation_id=conversation.id)

        conversation.delete()
        messages.info(request, "Sohbet silindi.")
        return redirect("chat:conversation_list")

class AddMemberView(LoginRequiredMixin, View):
    def post(self, request, conversation_id, user_id):
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user,
            is_group=True,
        )

        if not conversation.is_admin(request.user):
            messages.error(request, "Bu işlem için yönetici olmalısın.")
            return redirect("chat:group_settings", conversation_id=conversation.id)

        target = request.user.get_friends().filter(id=user_id).first()

        if not target:
            messages.error(request, "Sadece arkadaşlarını ekleyebilirsin.")
            return redirect("chat:group_settings", conversation_id=conversation.id)

        conversation.participants.add(target)
        broadcast_system_event(conversation, request.user, f"{request.user.username}, {target.username} kullanıcısını ekledi.")
        messages.success(request, f"{target.username} gruba eklendi.")
        return redirect("chat:group_settings", conversation_id=conversation.id)

def broadcast_system_event(conversation, actor, text):
    message = conversation.log_event(actor, text)

    async_to_sync(get_channel_layer().group_send)(
        f"chat_{conversation.id}",
        {
            "type": "chat_message",
            "message_id": message.id,
            "message": message.content,
            "sender_username": actor.username,
            "is_system": True,
        },
    )

class FileUploadView(LoginRequiredMixin, View):
    def post(self, request, conversation_id):
        conversation = Conversation.objects.filter(
            id=conversation_id, participants=request.user
        ).first()

        if conversation is None:
            raise Http404

        form = FileUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return JsonResponse({"error": form.errors["file"][0]}, status=400)

        upload = form.cleaned_data["file"]

        used = Message.objects.filter(sender=request.user).aggregate(
            total=Sum("file_size")
        )["total"] or 0

        if used + upload.size > settings.USER_STORAGE_QUOTA:
            return JsonResponse({"error": "Depolama kotan dolu."}, status=400)

        relative = f"{uuid.uuid4().hex}.scf"
        destination = Path(settings.SECURE_FILE_ROOT) / relative
        destination.parent.mkdir(parents=True, exist_ok=True)

        wrapped_key = encrypt_to_file(upload, destination)

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            file_name=form.safe_name,
            file_size=upload.size,
            file_type=form.content_type,
            file_path=relative,
            file_key=wrapped_key,
        )

        async_to_sync(get_channel_layer().group_send)(
            f"chat_{conversation.id}",
            {
                "type": "chat_message",
                "message_id": message.id,
                "message": "",
                "sender_username": request.user.username,
                "file_name": message.file_name,
                "file_size": message.file_size,
                "file_url": reverse("chat:file", args=[message.id]),
                "is_image": message.is_image,
                "file_size_display": filesizeformat(message.file_size),
            },
        )

        return JsonResponse({"ok": True})

class ChatFileView(LoginRequiredMixin, View):
    def get(self, request, message_id):
        message = (
            Message.objects.filter(
                id=message_id,
                conversation__participants=request.user,
            )
            .exclude(file_path="")
            .first()
        )

        if message is None:
            raise Http404

        path = Path(settings.SECURE_FILE_ROOT) / message.file_path
        if not path.exists():
            raise Http404

        response = StreamingHttpResponse(
            decrypt_from_file(path, message.file_key),
            content_type=message.file_type,
        )
        disposition = "inline" if message.is_image else "attachment"
        response["Content-Disposition"] = (
            f"{disposition}; filename*=UTF-8''{quote(message.file_name)}"
        )
        response["Content-Length"] = message.file_size
        response["X-Content-Type-Options"] = "nosniff"
        return response
class RegenerateInviteView(LoginRequiredMixin, View):
    def post(self, request, conversation_id):
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user,
            is_group=True,
        )

        if not conversation.is_admin(request.user):
            messages.error(request, "Bu işlem için yönetici olmalısın.")
            return redirect("chat:group_settings", conversation_id=conversation.id)

        conversation.invite_version += 1
        conversation.save(update_fields=["invite_version"])

        messages.success(request, "Yeni davet linki oluşturuldu, eski link artık geçersiz.")
        return redirect("chat:group_settings", conversation_id=conversation.id)
        
class JoinGroupView(LoginRequiredMixin, View):
    MAX_AGE = 60 * 60 * 24 * 7

    def _conversation_from_token(self, token):
        try:
            data = signing.loads(token, salt="group-invite", max_age=self.MAX_AGE)
        except signing.SignatureExpired:
            return None, "Bu davet linkinin süresi dolmuş."
        except signing.BadSignature:
            return None, "Davet linki geçersiz."

        conversation = Conversation.objects.filter(
            id=data["conversation_id"], is_group=True
        ).first()

        if conversation is None:
            return None, "Bu grup artık mevcut değil."

        if data.get("v") != conversation.invite_version:
            return None, "Bu davet linki artık geçerli değil, yöneticiden yeni link iste."

        return conversation, None

    def get(self, request, token):
        conversation, error = self._conversation_from_token(token)

        if error:
            messages.error(request, error)
            return redirect("chat:conversation_list")

        if conversation.participants.filter(id=request.user.id).exists():
            return redirect("chat:conversation_detail", conversation_id=conversation.id)

        return render(
            request,
            "chat/join_group.html",
            {"conversation": conversation, "token": token},
        )

    def post(self, request, token):
        conversation, error = self._conversation_from_token(token)

        if error:
            messages.error(request, error)
            return redirect("chat:conversation_list")

        conversation.participants.add(request.user)
        broadcast_system_event(conversation, request.user, f"{request.user.username} davet linkiyle katıldı.")
        messages.success(request, f"{conversation.name} grubuna katıldın.")
        return redirect("chat:conversation_detail", conversation_id=conversation.id)

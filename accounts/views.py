from django.shortcuts import render, redirect, get_object_or_404
from .models import User, VerificationCode, FriendRequest
from django.contrib.auth import login
from django.contrib import messages
from .forms import RegisterForm, VerificationForm, ProfileForm
from .utils import create_and_send_code
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator


class RegisterView(View):
    def get(self, request):
        form = RegisterForm()
        return render(request, "accounts/register.html", {"form": form})

    def post(self, request):
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            create_and_send_code(user)

            request.session["pending_user_id"] = user.id
            return redirect("accounts:verify")

        return render(request, "accounts/register.html", {"form": form})


class VerifyView(View):
    def dispatch(self, request, *args, **kwargs):
        user_id = request.session.get("pending_user_id")
        if not user_id:
            return redirect("accounts:register")

        self.user = User.objects.filter(id=user_id, is_active=False).first()
        if not self.user:
            return redirect("accounts:register")

        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = VerificationForm()
        return render(
            request, "accounts/verify.html", {"form": form, "email": self.user.email}
        )

    def post(self, request):
        form = VerificationForm(request.POST)

        if form.is_valid():
            entered_code = form.cleaned_data["code"]

            code_obj = (
                VerificationCode.objects.filter(user=self.user, is_used=False)
                .order_by("-created_at")
                .first()
            )

            if not code_obj:
                messages.error(request, "Geçerli bir kod bulunamadı. Yeni kod isteyin.")
            elif code_obj.is_expired():
                messages.error(request, "Kodun süresi doldu. Yeni kod isteyin.")
            elif code_obj.attempt_count >= 5:
                messages.error(request, "Çok fazla hatalı deneme. Yeni kod isteyin.")
            elif code_obj.code == entered_code:
                code_obj.is_used = True
                code_obj.save()

                self.user.is_active = True
                self.user.save()

                del request.session["pending_user_id"]
                login(request, self.user)
                messages.success(request, "Hesabınız doğrulandı.")
                return redirect("/")
            else:
                code_obj.attempt_count += 1
                code_obj.save()
                kalan = 5 - code_obj.attempt_count
                messages.error(request, f"Kod hatalı. Kalan deneme hakkı: {kalan}")

        return render(
            request, "accounts/verify.html", {"form": form, "email": self.user.email}
        )


class ResendCodeView(View):
    def post(self, request):
        user_id = request.session.get("pending_user_id")
        if not user_id:
            return redirect("accounts:register")

        user = User.objects.filter(id=user_id, is_active=False).first()
        if not user:
            return redirect("accounts:register")

        VerificationCode.objects.filter(user=user, is_used=False).update(is_used=True)
        create_and_send_code(user)

        messages.success(request, "Yeni kod gönderildi.")
        return redirect("accounts:verify")


class UserListView(LoginRequiredMixin, View):
    def get(self, request):
        q = request.GET.get("q", "").strip()

        users = User.objects.exclude(id=request.user.id)
        if q:
            users = users.filter(username__icontains=q)

        users = users.order_by("username")

        paginator = Paginator(users, 10)
        page_obj = paginator.get_page(request.GET.get("page"))

        sent_ids = FriendRequest.objects.filter(
            from_user=request.user,
            status__in=["pending", "accepted"],
        ).values_list("to_user_id", flat=True)

        received_ids = FriendRequest.objects.filter(
            to_user=request.user,
            status__in=["pending", "accepted"],
        ).values_list("from_user_id", flat=True)

        related_ids = set(sent_ids) | set(received_ids)

        return render(
            request,
            "accounts/user_list.html",
            {
                "page_obj": page_obj,
                "related_ids": related_ids,
                "q": q,
            },
        )


class SendFriendRequestView(LoginRequiredMixin, View):
    def post(self, request, user_id):
        target = get_object_or_404(User, id=user_id)

        if target == request.user:
            messages.error(request, "Kendine istek gönderemezsin.")
            return redirect("accounts:user_list")

        friend_request, created = FriendRequest.objects.get_or_create(
            from_user=request.user,
            to_user=target,
        )

        if created:
            messages.success(
                request, f"{target.username} kullanıcısına istek gönderildi."
            )
        elif friend_request.status == "rejected":
            friend_request.status = "pending"
            friend_request.save()
            messages.success(
                request, f"{target.username} kullanıcısına istek tekrar gönderildi."
            )
        elif friend_request.status == "accepted":
            messages.info(request, f"{target.username} ile zaten arkadaşsınız.")
        else:
            messages.info(request, "Zaten istek göndermişsin.")

        return redirect("accounts:user_list")


class FriendRequestView(LoginRequiredMixin, View):
    def get(self, request):
        incoming = FriendRequest.objects.filter(
            to_user=request.user,
            status="pending",
        ).select_related("from_user")

        return render(
            request,
            "accounts/friend_requests.html",
            {
                "incoming": incoming,
            },
        )


class AcceptFriendRequestView(LoginRequiredMixin, View):
    def post(self, request, request_id):

        friend_request = get_object_or_404(
            FriendRequest,
            id=request_id,
            to_user=request.user,
            status="pending",
        )

        friend_request.status = "accepted"
        friend_request.save()

        messages.success(
            request, f"{friend_request.from_user.username} artık arkadaşın."
        )
        return redirect("accounts:friend_requests")


class RejectFriendRequestView(LoginRequiredMixin, View):
    def post(self, request, request_id):

        friend_request = get_object_or_404(
            FriendRequest,
            id=request_id,
            to_user=request.user,
            status="pending",
        )

        friend_request.status = "rejected"
        friend_request.save()

        messages.info(
            request,
            f"{friend_request.from_user.username} kullanıcısının isteği reddedildi.",
        )
        return redirect("accounts:friend_requests")


class FriendListView(LoginRequiredMixin, View):
    def get(self, request):
        sent = FriendRequest.objects.filter(
            from_user=request.user,
            status="accepted",
        ).select_related("to_user")

        received = FriendRequest.objects.filter(
            to_user=request.user,
            status="accepted",
        ).select_related("from_user")

        friends = []
        for fr in sent:
            friends.append(fr.to_user)
        for fr in received:
            friends.append(fr.from_user)

        return render(
            request,
            "accounts/friend_list.html",
            {
                "friends": friends,
            },
        )


class RemoveFriendView(LoginRequiredMixin, View):
    def post(self, request, user_id):

        target = get_object_or_404(User, id=user_id)

        FriendRequest.objects.filter(
            from_user=request.user,
            to_user=target,
            status="accepted",
        ).delete()

        FriendRequest.objects.filter(
            from_user=target,
            to_user=request.user,
            status="accepted",
        ).delete()

        messages.info(request, f"{target.username} arkadaş listenden çıkarıldı.")
        return redirect("accounts:friend_list")


class ProfileView(LoginRequiredMixin, View):
    def get(self, request):
        form = ProfileForm(instance=request.user)
        return render(request, "accounts/profile.html", {"form": form})

    def post(self, request):
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil güncellendi.")
            return redirect("accounts:profile")

        return render(request, "accounts/profile.html", {"form": form})

from django.shortcuts import render, redirect
from .utils import create_and_send_code
from django.contrib.auth import login
from django.contrib import messages
from .forms import RegisterForm, VerificationForm
from .models import User, VerificationCode


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            create_and_send_code(user)

            request.session['pending_user_id'] = user.id
            return redirect('accounts:verify')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def verify(request):
    user_id = request.session.get('pending_user_id')
    if not user_id:
        return redirect('accounts:register')

    user = User.objects.filter(id=user_id, is_active=False).first()
    if not user:
        return redirect('accounts:register')

    if request.method == 'POST':
        form = VerificationForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data['code']

            code_obj = VerificationCode.objects.filter(
                user=user, is_used=False
            ).order_by('-created_at').first()

            if not code_obj:
                messages.error(request, 'Geçerli bir kod bulunamadı. Yeni kod isteyin.')
            elif code_obj.is_expired():
                messages.error(request, 'Kodun süresi doldu. Yeni kod isteyin.')
            elif code_obj.attempt_count >= 5:
                messages.error(request, 'Çok fazla hatalı deneme. Yeni kod isteyin.')
            elif code_obj.code == entered_code:
                code_obj.is_used = True
                code_obj.save()

                user.is_active = True
                user.save()

                del request.session['pending_user_id']
                login(request, user)
                messages.success(request, 'Hesabınız doğrulandı.')
                return redirect('/')
            else:
                code_obj.attempt_count += 1
                code_obj.save()
                kalan = 5 - code_obj.attempt_count
                messages.error(request, f'Kod hatalı. Kalan deneme hakkı: {kalan}')
    else:
        form = VerificationForm()

    return render(request, 'accounts/verify.html', {'form': form, 'email': user.email})

def resend_code(request):
    user_id = request.session.get('pending_user_id')
    if not user_id:
        return redirect('accounts:register')

    user = User.objects.filter(id=user_id, is_active=False).first()
    if not user:
        return redirect('accounts:register')

    VerificationCode.objects.filter(user=user, is_used=False).update(is_used=True)
    create_and_send_code(user)

    messages.success(request, 'Yeni kod gönderildi.')
    return redirect('accounts:verify')
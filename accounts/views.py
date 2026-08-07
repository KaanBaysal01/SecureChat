from django.shortcuts import render, redirect
from .forms import RegisterForm
from .utils import create_and_send_code


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
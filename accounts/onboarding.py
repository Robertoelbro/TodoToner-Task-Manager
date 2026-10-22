from django.contrib.auth import logout
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import resolve, Resolver404
from .models import User


class AccountAuthenticationForm(AuthenticationForm):
    def clean(self):
        username, password = self.cleaned_data.get('username'), self.cleaned_data.get('password')
        if username and password:
            user = User.objects.filter(username=username).first()
            if user and (not user.is_active or user.deletion_due_at or user.deleted_at) and user.check_password(password):
                raise ValidationError('Cuenta desactivada. Contacta a gerencia.', code='inactive')
        return super().clean()


class OnboardingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if request.user.deletion_due_at or request.user.deleted_at or not request.user.is_active:
                logout(request)
                return render(request, 'accounts/inactive.html', status=403)
            if request.user.must_complete_profile:
                try:
                    match = resolve(request.path_info)
                except Resolver404:
                    return redirect('complete-profile')
                if match.url_name not in ('complete-profile', 'logout', 'server-time'):
                    return redirect('complete-profile')
        return self.get_response(request)

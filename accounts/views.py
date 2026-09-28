from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from .forms import RegistrationForm


@require_http_methods(['GET', 'POST'])
def register(request):
    if request.user.is_authenticated:
        return redirect('task-list')
    form = RegistrationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        form.save()  # No se aceptan privilegios desde el registro.
        messages.success(request, 'Cuenta creada. Ya puedes iniciar sesión.')
        return redirect('login')
    return render(request, 'accounts/register.html', {'form': form})


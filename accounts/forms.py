from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class UniqueEmailMixin:
    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if not email:
            return email
        users = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            users = users.exclude(pk=self.instance.pk)
        if users.exists():
            raise forms.ValidationError('Este correo ya está asociado a otra cuenta.')
        return email


class RegistrationForm(UniqueEmailMixin, UserCreationForm):
    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellido', max_length=150)
    email = forms.EmailField(label='Correo electrónico')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')



class ManagedUserForm(UniqueEmailMixin, forms.ModelForm):
    email = forms.EmailField(label='Correo electrónico', required=False)
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'is_supervisor')
        labels = {'is_supervisor': 'Puede supervisar y reasignar tareas'}


class DeletionConfirmationForm(forms.Form):
    password = forms.CharField(label='Tu contraseña de gerencia', strip=False,
                              widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.actor.check_password(password):
            raise forms.ValidationError('La contraseña de gerencia no es correcta.')
        return password


class ProfileForm(UniqueEmailMixin, forms.ModelForm):
    email = forms.EmailField(label='Correo electrónico')
    current_password = forms.CharField(label='Contraseña actual (solo si cambias el correo)',
        required=False, strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        labels = {'first_name': 'Nombres', 'last_name': 'Apellidos'}

    def clean(self):
        data = super().clean()
        if data.get('email', '').lower() != self.instance.email.lower():
            if not self.instance.check_password(data.get('current_password', '')):
                self.add_error('current_password', 'Confirma tu contraseña actual para cambiar el correo.')
        return data


class RecoveryEmailForm(forms.Form):
    email = forms.EmailField(label='Correo de tu cuenta', widget=forms.EmailInput(attrs={'autocomplete': 'email'}))


class RecoveryCodeForm(forms.Form):
    code = forms.RegexField(label='Código de confirmación', regex=r'^\d{6}$',
        error_messages={'invalid': 'Ingresa los seis dígitos del código.'},
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code', 'maxlength': '6'}))

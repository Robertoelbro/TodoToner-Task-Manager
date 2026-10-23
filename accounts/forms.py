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



class ManagedUserForm(forms.ModelForm):
    role = forms.ChoiceField(label='Rol', choices=[('base', 'Usuario base'), ('supervisor', 'Supervisor'), ('management', 'Gerencia')])
    class Meta:
        model = User
        fields = ('area',)
        labels = {'is_supervisor': 'Puede supervisar y reasignar tareas'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['area'].required = True
        self.fields['role'].initial = 'management' if self.instance.is_superuser else ('supervisor' if self.instance.is_supervisor else 'base')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_superuser = self.cleaned_data['role'] == 'management'
        user.is_supervisor = self.cleaned_data['role'] == 'supervisor'
        user.is_staff = user.is_superuser
        if commit:
            user.save()
        return user


class ManagedCreationForm(forms.ModelForm):
    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellido', max_length=150)
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'area')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['area'].required = True

from django.contrib.auth.forms import SetPasswordForm


class CompleteProfileForm(SetPasswordForm):
    field_order = ('email', 'new_password1', 'new_password2')
    email = forms.EmailField(label='Correo electrónico', widget=forms.EmailInput(attrs={'autocomplete': 'email'}))

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError('Este correo ya está asociado a otra cuenta.')
        return email

    def clean_new_password1(self):
        password = self.cleaned_data['new_password1']
        if self.user.check_password(password):
            raise forms.ValidationError('Elige una contraseña distinta de la temporal.')
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.must_complete_profile = False
        user.must_change_password = False
        user.onboarding_nonce = ''
        if commit:
            user.save()
        return user


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


from django.contrib.auth.forms import PasswordChangeForm


class DifferentPasswordMixin:
    def clean_new_password1(self):
        password = self.cleaned_data['new_password1']
        if self.user.check_password(password):
            raise forms.ValidationError('Elige una contraseña distinta de la actual o temporal.')
        return password


class ForcedPasswordForm(DifferentPasswordMixin, SetPasswordForm):
    pass


class SelfPasswordChangeForm(DifferentPasswordMixin, PasswordChangeForm):
    pass

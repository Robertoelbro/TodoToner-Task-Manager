from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellido', max_length=150)
    email = forms.EmailField(label='Correo electrónico')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')



class ManagedUserForm(forms.ModelForm):
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

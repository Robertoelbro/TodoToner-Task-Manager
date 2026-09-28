from django import forms
from django.utils import timezone
from accounts.models import User
from .models import Task


class AssigneesMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignees'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'username')
        self.fields['assignees'].widget = forms.CheckboxSelectMultiple()
        self.fields['assignees'].widget.choices = self.fields['assignees'].choices
        self.fields['assignees'].help_text = 'Selecciona una o más personas.'


class TaskForm(AssigneesMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ('title', 'description', 'deadline', 'assignees')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'deadline': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def clean_deadline(self):
        deadline = self.cleaned_data['deadline']
        if deadline < timezone.localdate():
            raise forms.ValidationError('La fecha límite no puede ser anterior a hoy.')
        return deadline


class ReassignmentForm(AssigneesMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ('assignees',)


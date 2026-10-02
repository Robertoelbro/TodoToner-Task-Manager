from django import forms
from django.utils import timezone
from accounts.models import User
from .models import Task, Zone


class AssigneesMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignees'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'username')
        self.fields['assignees'].widget = forms.CheckboxSelectMultiple()
        self.fields['assignees'].widget.choices = self.fields['assignees'].choices
        self.fields['assignees'].help_text = 'Selecciona una o más personas.'


class ScheduleValidationMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('start_time', 'deadline_time'):
            self.fields[name].required = False
            self.fields[name].widget = forms.TimeInput(attrs={'type': 'time', 'step': '1'}, format='%H:%M:%S')
        self.fields['deadline_time'].help_text = 'Hora de Chile. Si se omite, se conserva la hora actual o se usa 23:59:59.'

    def clean(self):
        data = super().clean()
        start, end = data.get('start_date'), data.get('deadline')
        if start and end and start > end:
            self.add_error('deadline', 'La fecha límite debe ser igual o posterior al inicio.')
        for name in ('start_time', 'deadline_time'):
            data[name] = data.get(name) or getattr(self.instance, name)
        if start and end and start == end and data['start_time'] >= data['deadline_time']:
            self.add_error('deadline_time', 'La hora límite debe ser posterior al inicio.')
        return data


class TaskForm(ScheduleValidationMixin, AssigneesMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ('title', 'description', 'start_date', 'start_time', 'deadline', 'deadline_time', 'zones', 'priority', 'supervisor', 'assignees')
        widgets = {
            'zones': forms.CheckboxSelectMultiple(),
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
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



class TaskTrackingForm(ScheduleValidationMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ('priority', 'status', 'supervisor', 'start_date', 'start_time', 'deadline', 'deadline_time', 'zones')
        widgets = {
            'zones': forms.CheckboxSelectMultiple(),
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'deadline': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }



class DashboardFilterForm(forms.Form):
    zone = forms.ModelChoiceField(label='Zona', queryset=Zone.objects.all(), required=False, empty_label='Todas las zonas')
    worker = forms.ModelChoiceField(label='Trabajador', queryset=User.objects.filter(deleted_at__isnull=True).order_by('first_name', 'username'), required=False, empty_label='Todos los trabajadores')
    date_from = forms.DateField(label='Desde', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(label='Hasta', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    priority = forms.ChoiceField(label='Prioridad', required=False, choices=[('', 'Todas las prioridades')] + list(Task.Priority.choices))
    supervisor = forms.ModelChoiceField(label='Supervisor a cargo', queryset=User.objects.filter(is_supervisor=True, deleted_at__isnull=True).order_by('first_name', 'username'), required=False, empty_label='Todos los supervisores')
    status = forms.ChoiceField(label='Estado', required=False, choices=[('', 'Todos los estados')] + list(Task.Status.choices))
    multiple = forms.BooleanField(label='Más de un responsable', required=False)

    def clean(self):
        data = super().clean()
        if data.get('date_from') and data.get('date_to') and data['date_from'] > data['date_to']:
            raise forms.ValidationError('La fecha Desde no puede ser posterior a Hasta.')
        return data

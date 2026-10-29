from django import forms
from django.utils import timezone
from accounts.models import User
from .models import Task, Zone


class AreaCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        user = getattr(value, 'instance', None)
        option['attrs']['data-area-id'] = str(user.area_id or '') if user else ''
        return option


class AssigneesMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignees'].queryset = User.objects.filter(is_active=True, deleted_at__isnull=True, deletion_due_at__isnull=True).order_by('first_name', 'username')
        self.fields['assignees'].widget = AreaCheckboxSelectMultiple()
        self.fields['assignees'].widget.choices = self.fields['assignees'].choices
        self.fields['assignees'].help_text = 'Selecciona una o más personas.'
        self.fields['assignees'].required = False
        self.fields['assignee_areas'] = forms.ModelMultipleChoiceField(label='Asignar a toda un área',
            queryset=Zone.objects.all(), required=False, widget=forms.CheckboxSelectMultiple,
            help_text='Los usuarios activos del área se incluyen como responsables. Desmarca el área para quitarlos de la selección automática.')
        names = list(self.fields)
        names.remove('assignee_areas')
        names.insert(names.index('assignees'), 'assignee_areas')
        self.order_fields(names)

    def clean(self):
        data = super().clean()
        people = data.get('assignees')
        areas = data.get('assignee_areas')
        if people is not None:
            ids = set(people.values_list('pk', flat=True))
            if areas:
                ids.update(User.objects.filter(is_active=True, deleted_at__isnull=True,
                    deletion_due_at__isnull=True, area__in=areas).values_list('pk', flat=True))
            data['assignees'] = self.fields['assignees'].queryset.filter(pk__in=ids)
            if not ids:
                self.add_error('assignees', 'Selecciona al menos un responsable o un área con usuarios activos.')
        return data


class ScheduleValidationMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['zones'].required = False
        self.fields['zones'].label = 'Añadir etiqueta de zona (opcional)'
        self.fields['zones'].help_text = 'Puedes guardar la tarea sin seleccionar zonas.'
        for name in ('start_time', 'deadline_time'):
            self.fields[name].required = False
            self.fields[name].widget = forms.TimeInput(attrs={'type': 'time', 'step': '60'}, format='%H:%M')
        self.fields['deadline_time'].help_text = 'Hora de Chile (horas y minutos). Si se omite, se conserva la hora actual o se usa el final del día.'

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


class AudienceMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['spectators'].label = 'Quién puede visualizar mi tarea'
        self.fields['spectator_areas'].label = 'Áreas que pueden visualizar mi tarea'
        self.fields['spectators'].queryset = User.objects.filter(is_active=True, deleted_at__isnull=True,
            deletion_due_at__isnull=True).order_by('first_name', 'last_name', 'username')
        self.fields['spectators'].widget = AreaCheckboxSelectMultiple()
        self.fields['spectators'].widget.choices = self.fields['spectators'].choices
        self.fields['spectator_areas'].widget = forms.CheckboxSelectMultiple()
        self.fields['spectator_areas'].widget.choices = self.fields['spectator_areas'].choices
        self.fields['spectator_areas'].help_text = 'Acceso de lectura para los miembros actuales de estas áreas. Si cambian de área, cambia su acceso.'
        names = list(self.fields)
        names.remove('spectator_areas')
        names.insert(names.index('spectators'), 'spectator_areas')
        self.order_fields(names)
        self.fields['spectators'].help_text = 'Solo lectura. Las tareas exclusivas de gerencia siguen siendo privadas para gerencia.'


class TaskAudienceForm(AudienceMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ('spectators', 'spectator_areas')


class TaskForm(ScheduleValidationMixin, AssigneesMixin, AudienceMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ('title', 'description', 'start_date', 'start_time', 'deadline', 'deadline_time', 'zones', 'priority', 'supervisor', 'assignees', 'spectators', 'spectator_areas')
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



class TaskStatusForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ('status',)


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
    month = forms.TypedChoiceField(label='Mes', required=False, coerce=int, empty_value=None,
        choices=[('', 'Todos los meses')] + list(enumerate(['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'], 1)))
    year = forms.IntegerField(label='Año', required=False, min_value=1900, max_value=9998,
        widget=forms.Select(choices=[('', 'Todos los años')] + [(year, year) for year in range(2000, 2101)]))
    priority = forms.ChoiceField(label='Prioridad', required=False, choices=[('', 'Todas las prioridades')] + list(Task.Priority.choices))
    supervisor = forms.ModelChoiceField(label='Supervisor a cargo', queryset=User.objects.filter(is_supervisor=True, deleted_at__isnull=True).order_by('first_name', 'username'), required=False, empty_label='Todos los supervisores')
    status = forms.ChoiceField(label='Estado', required=False, choices=[('', 'Todos los estados')] + list(Task.Status.choices))
    multiple = forms.BooleanField(label='Más de un responsable', required=False)

    def clean(self):
        data = super().clean()
        if data.get('month') and not data.get('year'):
            self.add_error('year', 'Selecciona el año para consultar ese mes.')
        return data


class HistoryFilterForm(DashboardFilterForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('priority', 'supervisor', 'multiple'):
            self.fields.pop(name)
        self.fields['worker'].queryset = User.objects.all().order_by('first_name', 'username')


from .models import MonthlyGoal


class MonthlyGoalForm(forms.ModelForm):
    month = forms.DateField(label='Mes de la meta', input_formats=['%Y-%m'],
        widget=forms.DateInput(format='%Y-%m', attrs={'type': 'month'}))

    class Meta:
        model = MonthlyGoal
        fields = ('title', 'description', 'month', 'zones')
        widgets = {'description': forms.Textarea(attrs={'rows': 3}), 'zones': forms.CheckboxSelectMultiple()}

    def clean_month(self):
        return self.cleaned_data['month'].replace(day=1)

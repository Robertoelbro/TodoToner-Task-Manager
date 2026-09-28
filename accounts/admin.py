from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class TurnoUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Turno', {'fields': ('is_supervisor',)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Turno', {'fields': ('is_supervisor',)}),)
    list_display = ('username', 'first_name', 'last_name', 'is_supervisor', 'is_active')
    list_filter = UserAdmin.list_filter + ('is_supervisor',)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


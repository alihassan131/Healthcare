from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Doctor, Patient


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Extra', {'fields': ('role', 'phone')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra', {'fields': ('email', 'role', 'phone')}),
    )
    list_display = ('username', 'email', 'role', 'is_staff')


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('user', 'hospital', 'specialization')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.user.role != User.Role.DOCTOR:
            obj.user.role = User.Role.DOCTOR
            obj.user.save(update_fields=['role'])


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('user', 'doctor', 'hospital', 'is_rpm', 'is_ccm')
    list_filter = ('is_rpm', 'is_ccm', 'hospital')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.user.role != User.Role.PATIENT:
            obj.user.role = User.Role.PATIENT
            obj.user.save(update_fields=['role'])

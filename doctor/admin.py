from django.contrib import admin
from .models import (
    DoctorProfile, Patient, PatientJoiningCode,
    ClinicalRecord, TreatmentPlan, PhotoMonitoring,
    EmergencyAlert, Appointment, Notification, PatientActivityLog
)

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'clinic_name', 'phone_number', 'dental_qualification', 'created_at')
    search_fields = ('full_name', 'clinic_name', 'phone_number', 'user__username')


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('patient_id', 'full_name', 'age', 'gender', 'doctor', 'treatment_status', 'created_at')
    list_filter = ('treatment_status', 'doctor', 'gender')
    search_fields = ('patient_id', 'first_name', 'last_name', 'phone', 'email')


@admin.register(PatientJoiningCode)
class PatientJoiningCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'patient', 'doctor', 'status', 'expires_at', 'created_at')
    list_filter = ('status', 'doctor')
    search_fields = ('code', 'patient__first_name', 'patient__last_name')


@admin.register(ClinicalRecord)
class ClinicalRecordAdmin(admin.ModelAdmin):
    list_display = ('patient', 'teeth_present', 'overbite', 'deep_bite', 'molar_relationship', 'updated_at')
    search_fields = ('patient__first_name', 'patient__last_name', 'patient__patient_id')


@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    list_display = ('patient', 'total_aligners', 'current_aligner', 'aligner_frequency_days', 'status', 'compliance_score')
    list_filter = ('status',)
    search_fields = ('patient__first_name', 'patient__last_name')


@admin.register(PhotoMonitoring)
class PhotoMonitoringAdmin(admin.ModelAdmin):
    list_display = ('patient', 'week_number', 'aligner_stage', 'tracking_status', 'upload_date')
    list_filter = ('tracking_status',)
    search_fields = ('patient__first_name', 'patient__last_name')


@admin.register(EmergencyAlert)
class EmergencyAlertAdmin(admin.ModelAdmin):
    list_display = ('patient', 'issue_type', 'severity', 'status', 'reported_at')
    list_filter = ('issue_type', 'severity', 'status')
    search_fields = ('patient__first_name', 'patient__last_name')


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'appointment_type', 'scheduled_date', 'scheduled_time', 'status')
    list_filter = ('status', 'appointment_type', 'doctor')
    search_fields = ('patient__first_name', 'patient__last_name')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'doctor', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'doctor')


@admin.register(PatientActivityLog)
class PatientActivityLogAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'activity_type', 'created_at')
    list_filter = ('doctor', 'activity_type')

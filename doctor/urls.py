from django.urls import path
from . import views

app_name = 'doctor'

urlpatterns = [
    # Dashboard & Auth
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.doctor_login_view, name='login'),
    path('register/', views.doctor_register_view, name='register'),
    path('logout/', views.doctor_logout_view, name='logout'),
    path('forgot-password/', views.doctor_forgot_password_view, name='forgot_password'),
    path('reset-password/', views.doctor_reset_password_view, name='reset_password'),

    # Public Joining Portal
    path('join/', views.patient_join_portal_view, name='patient_join_portal'),

    # Patients Management
    path('patients/', views.patient_list_view, name='patient_list'),
    path('patients/create/', views.patient_create_view, name='patient_create'),
    path('patients/<int:patient_id>/', views.patient_detail_view, name='patient_detail'),
    path('patients/<int:patient_id>/edit/', views.patient_edit_view, name='patient_edit'),
    path('patients/<int:patient_id>/delete/', views.patient_delete_view, name='patient_delete'),
    path('patients/<int:patient_id>/regenerate-code/', views.regenerate_joining_code_view, name='regenerate_code'),
    path('patients/<int:patient_id>/advance-aligner/', views.advance_aligner_stage_view, name='advance_aligner'),
    path('patients/<int:patient_id>/clinical/edit/', views.clinical_record_edit_view, name='clinical_record_edit'),
    path('patients/<int:patient_id>/treatment-plan/edit/', views.treatment_plan_edit_view, name='treatment_plan_edit'),
    path('patients/<int:patient_id>/photos/upload/', views.photo_upload_view, name='photo_upload'),
    path('patients/<int:patient_id>/photos/compare/', views.photo_compare_view, name='photo_compare'),

    # Patient Joining Requests (Code verification & Approval)
    path('requests/', views.patient_requests_view, name='patient_requests'),
    path('requests/<int:code_id>/approve/', views.approve_patient_request_view, name='approve_patient_request'),
    path('requests/<int:code_id>/reject/', views.reject_patient_request_view, name='reject_patient_request'),

    # Clinical Intake & Examination
    path('clinical-records/', views.clinical_records_view, name='clinical_records'),

    # Treatment Plans
    path('treatment-plans/', views.treatment_plans_view, name='treatment_plans'),

    # Photo Monitoring
    path('photos/', views.photo_monitoring_view, name='photo_monitoring'),
    path('photos/<int:photo_id>/review/', views.photo_review_view, name='photo_review'),

    # Progress Tracking
    path('progress/', views.progress_tracking_view, name='progress_tracking'),

    # Emergency Alerts
    path('emergencies/', views.emergency_alerts_view, name='emergency_alerts'),
    path('emergencies/create/', views.emergency_create_view, name='emergency_create'),
    path('emergencies/<int:alert_id>/respond/', views.emergency_respond_view, name='emergency_respond'),
    path('emergencies/<int:alert_id>/resolve-quick/', views.emergency_resolve_quick_view, name='emergency_resolve_quick'),

    # Appointments
    path('appointments/', views.appointments_view, name='appointments'),
    path('appointments/create/', views.appointment_create_view, name='appointment_create'),
    path('appointments/<int:appt_id>/status/', views.appointment_status_update_view, name='appointment_status_update'),

    # Notifications & Reminders
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read_view, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read_view, name='mark_all_notifications_read'),

    # Reports & Analytics
    path('reports/', views.reports_analytics_view, name='reports_analytics'),
    path('reports/export-csv/', views.export_patients_csv_view, name='export_patients_csv'),
    path('reports/print/', views.print_report_view, name='print_report'),

    # Doctor Profile & Settings
    path('settings/', views.doctor_settings_view, name='settings'),
]

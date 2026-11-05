from django.urls import path
from . import views

app_name = 'patient'

urlpatterns = [
    # Dashboard & Authentication
    path('', views.patient_dashboard_view, name='dashboard'),
    path('login/', views.patient_login_view, name='login'),
    path('register/', views.patient_register_view, name='register'),
    path('logout/', views.patient_logout_view, name='logout'),
    path('forgot-password/', views.patient_forgot_password_view, name='forgot_password'),

    # Connect with Doctor (Joining Code)
    path('connect/', views.connect_doctor_view, name='connect_doctor'),
    path('api/connection-status/', views.check_connection_status_api, name='api_connection_status'),

    # Core Treatment & Care
    path('treatment/', views.my_treatment_view, name='my_treatment'),
    path('prescriptions/<int:presc_id>/', views.prescription_view, name='prescription_view'),
    path('prescriptions/<int:presc_id>/print/', views.prescription_print_view, name='prescription_print'),
    path('photos/upload/', views.upload_photos_view, name='upload_photos'),
    path('progress/', views.treatment_progress_view, name='progress'),

    # Appointments
    path('appointments/', views.appointments_view, name='appointments'),
    path('appointments/request/', views.appointment_request_view, name='appointment_request'),
    path('appointments/<int:appt_id>/reschedule/', views.appointment_reschedule_view, name='appointment_reschedule'),

    # Notifications
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read_view, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read_view, name='mark_all_notifications_read'),

    # Emergency & Profile
    path('emergency/', views.emergency_help_view, name='emergency'),
    path('profile/', views.my_profile_view, name='profile'),
    path('profile/password/', views.change_password_view, name='change_password'),
]


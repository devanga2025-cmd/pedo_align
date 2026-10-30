from .models import DoctorProfile, PatientJoiningCode, EmergencyAlert, Notification

def doctor_context(request):
    context = {
        'current_doctor': None,
        'pending_requests_count': 0,
        'unresolved_emergencies_count': 0,
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }

    if request.user.is_authenticated:
        try:
            doctor = request.user.doctor_profile
            context['current_doctor'] = doctor
            context['pending_requests_count'] = PatientJoiningCode.objects.filter(
                doctor=doctor, status='PENDING_APPROVAL'
            ).count()
            context['unresolved_emergencies_count'] = EmergencyAlert.objects.filter(
                patient__doctor=doctor, status__in=['PENDING', 'IN_REVIEW']
            ).count()
            notifications_qs = Notification.objects.filter(doctor=doctor)
            context['unread_notifications_count'] = notifications_qs.filter(is_read=False).count()
            context['recent_notifications'] = notifications_qs[:5]
        except DoctorProfile.DoesNotExist:
            pass

    return context

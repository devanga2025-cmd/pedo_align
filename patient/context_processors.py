def patient_context(request):
    if not request.user.is_authenticated:
        return {}
    
    patient_profile = getattr(request.user, 'patient_profile', None)
    if not patient_profile:
        return {}

    unread_notifications_count = patient_profile.notifications.filter(is_read=False).count()
    return {
        'current_patient': patient_profile,
        'patient_unread_notifs': unread_notifications_count,
    }


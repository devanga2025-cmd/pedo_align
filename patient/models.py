from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import secrets
import string


def generate_patient_id():
    num = secrets.randbelow(90000) + 10000
    return f"PA-PT-{num}"


class PatientProfile(models.Model):
    CONNECTION_STATUS_CHOICES = [
        ('NOT_CONNECTED', 'Not Connected'),
        ('PENDING_APPROVAL', 'Pending Doctor Approval'),
        ('CONNECTED', 'Connected to Doctor'),
        ('REJECTED', 'Connection Rejected'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    patient_id = models.CharField(max_length=30, unique=True, default=generate_patient_id)
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=50)
    avatar = models.ImageField(upload_to='patient_avatars/', blank=True, null=True)

    # Connection with Doctor and Clinical Patient Record
    connected_patient_record = models.OneToOneField(
        'doctor.Patient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='portal_profile'
    )
    connection_status = models.CharField(
        max_length=30,
        choices=CONNECTION_STATUS_CHOICES,
        default='NOT_CONNECTED'
    )
    pending_code = models.ForeignKey(
        'doctor.PatientJoiningCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requesting_patient_profiles'
    )
    requested_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} ({self.patient_id})"

    @property
    def is_connected(self):
        return self.connection_status == 'CONNECTED' and self.connected_patient_record is not None

    @property
    def doctor(self):
        if self.is_connected and self.connected_patient_record:
            return self.connected_patient_record.doctor
        return None

    @property
    def treatment_plan(self):
        if self.is_connected and self.connected_patient_record:
            return getattr(self.connected_patient_record, 'treatment_plan', None)
        return None

    @property
    def current_treatment_status(self):
        if self.is_connected and self.connected_patient_record:
            return self.connected_patient_record.treatment_status
        return 'PENDING'


class PatientNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('ALIGNER_CHANGE', 'Aligner Change Reminder'),
        ('PHOTO_SUBMISSION', 'Weekly Photo Upload Reminder'),
        ('APPOINTMENT', 'Appointment Reminder'),
        ('DOCTOR_INSTRUCTION', 'Doctor Instructions'),
        ('TREATMENT_UPDATE', 'Treatment Updates'),
        ('DOCTOR_FEEDBACK', 'Doctor Feedback'),
    ]

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=40, choices=NOTIFICATION_TYPES, default='TREATMENT_UPDATE')
    title = models.CharField(max_length=200)
    message = models.TextField()
    link_url = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.patient.full_name} - {self.title}"

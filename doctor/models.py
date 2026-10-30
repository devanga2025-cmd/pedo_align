from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import secrets
import string


def generate_joining_code():
    chars = string.ascii_uppercase + string.digits
    # Exclude ambiguous characters like O, 0, I, 1
    safe_chars = [c for c in chars if c not in ('O', '0', 'I', '1')]
    random_part = ''.join(secrets.choice(safe_chars) for _ in range(6))
    return f"PA-{random_part}"


class DoctorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    full_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=50)
    dental_qualification = models.CharField(max_length=200, help_text="e.g. BDS, MDS Orthodontics, Pediatric Dentist")
    clinic_name = models.CharField(max_length=250)
    clinic_address = models.TextField()
    license_number = models.CharField(max_length=100, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='doctor_profiles/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    email_notifications = models.BooleanField(default=True)
    sms_alerts = models.BooleanField(default=True)
    emergency_push = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dr. {self.full_name} - {self.clinic_name}"


class Patient(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('PENDING_CONNECTION', 'Pending Connection'),
        ('ACTIVE', 'Active Treatment'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('DISCONTINUED', 'Discontinued'),
    ]

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='patients')
    patient_id = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(blank=True, null=True)
    parent_guardian_name = models.CharField(max_length=150, blank=True, null=True, help_text="Parent / Guardian Name")
    parent_guardian_phone = models.CharField(max_length=50, blank=True, null=True)
    treatment_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_CONNECTION')
    treatment_start_date = models.DateField(blank=True, null=True)
    treatment_duration_months = models.PositiveIntegerField(default=12)
    profile_photo = models.ImageField(upload_to='patient_profiles/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.patient_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class PatientJoiningCode(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active / Unclaimed'),
        ('PENDING_APPROVAL', 'Claimed / Awaiting Approval'),
        ('APPROVED', 'Approved / Connected'),
        ('EXPIRED', 'Expired'),
        ('REJECTED', 'Rejected'),
    ]

    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='joining_code')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='generated_codes')
    code = models.CharField(max_length=30, unique=True, default=generate_joining_code)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    claimed_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    patient_request_notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.patient.full_name} ({self.status})"

    def is_expired(self):
        return timezone.now() > self.expires_at and self.status == 'ACTIVE'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=14)
        super().save(*args, **kwargs)


class ClinicalRecord(models.Model):
    OVERBITE_CHOICES = [
        ('Normal (2-3mm)', 'Normal (2-3mm)'),
        ('Increased (>3mm)', 'Increased (>3mm)'),
        ('Decreased (<1mm)', 'Decreased (<1mm)'),
        ('Edge to Edge (0mm)', 'Edge to Edge (0mm)'),
        ('Negative / Anterior Open Bite', 'Negative / Anterior Open Bite'),
    ]

    DEEP_BITE_CHOICES = [
        ('None', 'None'),
        ('Mild (25-50% overlap)', 'Mild (25-50% overlap)'),
        ('Moderate (50-75% overlap)', 'Moderate (50-75% overlap)'),
        ('Severe (>75% / Palatal Impingement)', 'Severe (>75% / Palatal Impingement)'),
    ]

    MOLAR_RELATIONSHIP_CHOICES = [
        ('Class I', 'Class I'),
        ('Class II Division 1', 'Class II Division 1'),
        ('Class II Division 2', 'Class II Division 2'),
        ('Class III', 'Class III'),
    ]

    CANINE_RELATIONSHIP_CHOICES = [
        ('Class I', 'Class I'),
        ('Class II', 'Class II'),
        ('Class III', 'Class III'),
    ]

    CROSSBITE_CHOICES = [
        ('None', 'None'),
        ('Anterior Crossbite', 'Anterior Crossbite'),
        ('Posterior Unilateral (Right)', 'Posterior Unilateral (Right)'),
        ('Posterior Unilateral (Left)', 'Posterior Unilateral (Left)'),
        ('Posterior Bilateral', 'Posterior Bilateral'),
    ]

    ORAL_HABITS_CHOICES = [
        ('None', 'None'),
        ('Thumb Sucking', 'Thumb Sucking'),
        ('Tongue Thrusting', 'Tongue Thrusting'),
        ('Mouth Breathing', 'Mouth Breathing'),
        ('Bruxism (Teeth Grinding)', 'Bruxism (Teeth Grinding)'),
        ('Lip Biting / Sucking', 'Lip Biting / Sucking'),
        ('Multiple Oral Habits', 'Multiple Oral Habits'),
    ]

    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='clinical_record')
    medical_history = models.TextField(blank=True, null=True, help_text="Allergies, systemic illnesses, ongoing medications")
    dental_history = models.TextField(blank=True, null=True, help_text="Previous dental/ortho treatments, trauma, fluoride history")
    teeth_present = models.CharField(max_length=250, default='Complete Mixed Dentition', help_text="e.g. Primary, Mixed, Permanent, missing teeth")
    overbite = models.CharField(max_length=100, choices=OVERBITE_CHOICES, default='Normal (2-3mm)')
    deep_bite = models.CharField(max_length=100, choices=DEEP_BITE_CHOICES, default='None')
    molar_relationship = models.CharField(max_length=100, choices=MOLAR_RELATIONSHIP_CHOICES, default='Class I')
    canine_relationship = models.CharField(max_length=100, choices=CANINE_RELATIONSHIP_CHOICES, default='Class I')
    crossbite = models.CharField(max_length=100, choices=CROSSBITE_CHOICES, default='None')
    molar_occlusion = models.CharField(max_length=150, default='Flush Terminal Plane', help_text="Flush terminal plane, mesial step, or distal step")
    oral_habits = models.CharField(max_length=100, choices=ORAL_HABITS_CHOICES, default='None')
    skeletal_notes = models.TextField(blank=True, null=True, help_text="Skeletal classification, facial symmetry, profile (straight, convex, concave)")
    doctor_clinical_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Clinical Record - {self.patient.full_name}"


class TreatmentPlan(models.Model):
    STATUS_CHOICES = [
        ('Planning', 'Planning Stage'),
        ('Active / In Progress', 'Active / In Progress'),
        ('Refinement', 'Refinement Stage'),
        ('Retention', 'Retention Phase'),
        ('Completed', 'Treatment Completed'),
    ]

    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='treatment_plan')
    estimated_duration_months = models.PositiveIntegerField(default=12)
    total_aligners = models.PositiveIntegerField(default=24)
    current_aligner = models.PositiveIntegerField(default=1)
    aligner_frequency_days = models.PositiveIntegerField(default=10, help_text="Days per aligner set (e.g. 7, 10, 14)")
    start_date = models.DateField(blank=True, null=True)
    expected_completion_date = models.DateField(blank=True, null=True)
    treatment_instructions = models.TextField(
        default="Wear aligners 20-22 hours daily. Change aligners strictly as per scheduled frequency. Clean with soft brush and lukewarm water.",
        blank=True
    )
    next_review_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Active / In Progress')
    compliance_score = models.PositiveIntegerField(default=92, help_text="Compliance percentage (0-100)")
    daily_wear_hours = models.DecimalField(max_digits=4, decimal_places=1, default=21.5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Treatment Plan - {self.patient.full_name} ({self.current_aligner}/{self.total_aligners})"

    @property
    def progress_percentage(self):
        if self.total_aligners > 0:
            pct = int((self.current_aligner / self.total_aligners) * 100)
            return min(pct, 100)
        return 0


class PhotoMonitoring(models.Model):
    TRACKING_STATUS_CHOICES = [
        ('PENDING_REVIEW', 'Pending Review'),
        ('TRACKING_WELL', 'Tracking Well / On Schedule'),
        ('NEEDS_ATTENTION', 'Needs Attention / Minor Misfit'),
        ('ALIGNER_MISFIT', 'Significant Misfit / Escalated'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='photo_uploads')
    week_number = models.PositiveIntegerField(default=1)
    aligner_stage = models.PositiveIntegerField(default=1)
    upload_date = models.DateField(default=timezone.now)
    front_bite_photo = models.ImageField(upload_to='monitoring_photos/', blank=True, null=True)
    upper_arch_photo = models.ImageField(upload_to='monitoring_photos/', blank=True, null=True)
    lower_arch_photo = models.ImageField(upload_to='monitoring_photos/', blank=True, null=True)
    right_occlusion_photo = models.ImageField(upload_to='monitoring_photos/', blank=True, null=True)
    left_occlusion_photo = models.ImageField(upload_to='monitoring_photos/', blank=True, null=True)
    patient_notes = models.TextField(blank=True, null=True)
    tracking_status = models.CharField(max_length=50, choices=TRACKING_STATUS_CHOICES, default='PENDING_REVIEW')
    doctor_feedback = models.TextField(blank=True, null=True)
    doctor_rating = models.PositiveIntegerField(default=5, help_text="Rating out of 5")
    reviewed_at = models.DateTimeField(blank=True, null=True)
    is_before_sample = models.BooleanField(default=False)
    is_after_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-upload_date', '-created_at']

    def __str__(self):
        return f"Photos - {self.patient.full_name} (Week {self.week_number}, Aligner #{self.aligner_stage})"


class EmergencyAlert(models.Model):
    ISSUE_CHOICES = [
        ('TOOTH_PAIN', 'Tooth Pain'),
        ('ALIGNER_DISCOMFORT', 'Aligner Discomfort'),
        ('BROKEN_ALIGNER', 'Broken Aligner'),
        ('LOOSE_ALIGNER', 'Loose Aligner'),
        ('OTHER', 'Other Treatment Difficulties'),
    ]

    SEVERITY_CHOICES = [
        ('LOW', 'Low - Minor Discomfort'),
        ('MEDIUM', 'Moderate - Needs Guidance'),
        ('HIGH', 'High - Urgent Attention'),
        ('CRITICAL', 'Critical - Same-day Visit Required'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Doctor Review'),
        ('IN_REVIEW', 'In Review / Doctor Responded'),
        ('RESOLVED', 'Resolved'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='emergency_alerts')
    issue_type = models.CharField(max_length=60, choices=ISSUE_CHOICES)
    severity = models.CharField(max_length=30, choices=SEVERITY_CHOICES, default='MEDIUM')
    description = models.TextField()
    reported_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    doctor_response = models.TextField(blank=True, null=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-reported_at']

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.get_issue_type_display()} - {self.patient.full_name}"


class Appointment(models.Model):
    APPOINTMENT_TYPE_CHOICES = [
        ('ROUTINE_CHECKUP', 'Routine Checkup'),
        ('ALIGNER_COLLECTION', 'Aligner Delivery / Next Set'),
        ('EMERGENCY', 'Emergency Evaluation'),
        ('TREATMENT_PLAN_REVIEW', 'Treatment Plan Review'),
        ('ATTACHMENT_PLACEMENT', 'Attachment Placement / IPR'),
        ('REFINEMENT_SCAN', 'Refinement Digital Scan'),
        ('FINISHING', 'Debonding / Retainer Delivery'),
    ]

    STATUS_CHOICES = [
        ('UPCOMING', 'Upcoming'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('RESCHEDULED', 'Rescheduled'),
    ]

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='appointments')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    appointment_type = models.CharField(max_length=60, choices=APPOINTMENT_TYPE_CHOICES, default='ROUTINE_CHECKUP')
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='UPCOMING')
    notes = models.TextField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_date', 'scheduled_time']

    def __str__(self):
        return f"{self.patient.full_name} - {self.get_appointment_type_display()} on {self.scheduled_date} at {self.scheduled_time}"


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ('PATIENT_REQUEST', 'New Patient Request'),
        ('PHOTO_UPLOAD', 'New Photo Upload'),
        ('APPOINTMENT', 'Appointment Alert'),
        ('EMERGENCY', 'Emergency Report'),
        ('PROGRESS', 'Progress Update'),
        ('FOLLOWUP', 'Treatment Follow-up'),
    ]

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='notifications')
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, blank=True, null=True, related_name='notifications')
    notification_type = models.CharField(max_length=40, choices=NOTIFICATION_TYPE_CHOICES, default='PROGRESS')
    title = models.CharField(max_length=200)
    message = models.TextField()
    link_url = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - Dr. {self.doctor.full_name}"


class PatientActivityLog(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='activity_logs')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='activity_logs')
    activity_type = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.activity_type} - {self.patient.full_name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

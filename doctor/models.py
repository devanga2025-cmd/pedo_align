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
    SPECIALIZATION_CHOICES = [
        ('Orthodontist', 'Orthodontist'),
        ('Pedodontist', 'Pedodontist'),
        ('Orthodontist & Pedodontist', 'Orthodontist & Pedodontist'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    full_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=50)
    dental_qualification = models.CharField(max_length=200, help_text="e.g. BDS, MDS Orthodontics, Pediatric Dentist")
    specialization = models.CharField(max_length=150, default='Orthodontist', help_text="Specialization entered by the doctor")
    ksdc_registration_number = models.CharField(max_length=100, blank=True, null=True, help_text="Karnataka State Dental Council (KSDC) Registration Number")
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

    @property
    def display_name(self):
        name = (self.full_name or '').strip()
        if name.lower().startswith('dr.') or name.lower().startswith('dr '):
            return name
        return f"Dr. {name}" if name else "Dr. Doctor"

    def __str__(self):
        return f"{self.display_name} ({self.specialization}) - {self.clinic_name}"

    @property
    def email(self):
        return self.user.email if self.user else ''


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

    CATEGORY_CHOICES = [
        ('CHILD', 'Child Patient'),
        ('ADULT', 'Adult Patient'),
    ]

    FREQUENCY_CHOICES = [
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('CUSTOM', 'Custom Date'),
    ]

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='patients')
    patient_id = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    patient_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='CHILD', blank=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(blank=True, null=True)
    parent_guardian_name = models.CharField(max_length=150, blank=True, null=True, help_text="Parent / Guardian Name")
    parent_guardian_phone = models.CharField(max_length=50, blank=True, null=True)
    parent_guardian_email = models.EmailField(blank=True, null=True, help_text="Parent / Guardian Email")
    parent_guardian_relationship = models.CharField(max_length=50, blank=True, null=True, default='Parent', help_text="Father, Mother, Guardian")
    appointment_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='MONTHLY', blank=True)
    MONITORING_FREQUENCY_CHOICES = [
        ('DAILY', 'Daily Update'),
        ('WEEKLY', 'Weekly Update'),
        ('MONTHLY', 'Monthly Update'),
    ]
    monitoring_frequency = models.CharField(
        max_length=20,
        choices=MONITORING_FREQUENCY_CHOICES,
        default='WEEKLY',
        blank=True,
        help_text="Patient dental monitoring photo cadence (Daily, Weekly, Monthly)"
    )
    current_operation = models.CharField(max_length=200, default='Turn Quest', blank=True, null=True)
    diagnosed_problem = models.TextField(blank=True, null=True, help_text="Patient's primary dental problem diagnosed by doctor")
    treatment_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_CONNECTION')
    treatment_start_date = models.DateField(blank=True, null=True)
    treatment_duration_months = models.PositiveIntegerField(default=12)
    profile_photo = models.ImageField(upload_to='patient_profiles/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)
    archived_reason = models.TextField(blank=True, null=True)
    is_deactivated = models.BooleanField(default=False)
    deactivated_at = models.DateTimeField(blank=True, null=True)
    deactivation_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.patient_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def has_completed_step3(self):
        """
        Patient is strictly eligible for Step 4 (Turn Quest & Problem Diagnosis) only if:
        1. Step 1: Pre-op Photos (at least 3 compulsory photos uploaded)
        2. Step 2: Radiographs (at least 1 OPG or Lateral Cephalograph uploaded)
        3. Step 3: Next Visit (hospital appointment scheduled)
        """
        has_3_preop = self.preoperative_photos.count() >= 3
        has_radiographs = self.radiographs.exists()
        has_appointments = self.appointments.exists()
        return bool(has_3_preop and has_radiographs and has_appointments)

    def calculate_current_treatment_month(self):
        if not self.treatment_start_date:
            return 1
        today = timezone.localdate()
        if today < self.treatment_start_date:
            return 1
        months = (today.year - self.treatment_start_date.year) * 12 + (today.month - self.treatment_start_date.month) + 1
        return max(1, months)

    def get_timeline_stages(self):
        has_clinical = hasattr(self, 'clinical_record') and bool(
            self.clinical_record.medical_history or self.clinical_record.dental_history or self.clinical_record.skeletal_notes
        )
        has_preop = self.preoperative_photos.exists()
        has_radiographs = self.radiographs.exists()
        has_appointments = self.appointments.exists()
        is_treatment_started = bool(self.treatment_start_date or self.treatment_status in ['ACTIVE', 'COMPLETED'])
        has_prescriptions = self.prescriptions.exists()
        has_monthly_notes = self.monthly_notes.exists()
        has_turns = self.treatment_turns.exists()
        has_patient_photos = self.photo_uploads.exists()
        has_doctor_reviews = self.photo_uploads.filter(reviewed_at__isnull=False).exists()
        is_completed = (self.treatment_status == 'COMPLETED')

        flags = [
            (True, "Patient Registration", "Patient profile and joining credentials established."),
            (has_clinical, "Initial Clinical Examination", "Comprehensive clinical assessment & dentition records."),
            (has_preop, "Preoperative Photo Upload", "Baseline photographic documentation archived."),
            (has_radiographs, "Radiograph Upload", "Type 1 & Type 2 diagnostic radiograph records."),
            (has_appointments, "Appointment Scheduling", "Follow-up consultations & treatment visit planning."),
            (is_treatment_started, "Treatment Started", "Orthodontic / pedodontic treatment actively initiated."),
            (has_prescriptions, "Prescription Generated", "Digital clinical prescription & medication directions."),
            (has_monthly_notes, "Monthly Treatment Updates", "Ongoing monthly clinical progression & milestones."),
            (has_turns, "Turn / Treatment Sequence Updates", "Turn quest individual therapy stages executed."),
            (has_patient_photos, "Weekly Patient Photo Updates", "5-angle weekly progress photos submitted."),
            (has_doctor_reviews, "Doctor Reviews", "Doctor feedback, ratings & alignment monitoring."),
            (is_completed, "Treatment Completed", "Clinical treatment goals achieved & retention initiated."),
        ]

        stages = []
        found_current = False
        for idx, (completed, name, desc) in enumerate(flags, start=1):
            if completed:
                status = 'COMPLETED'
            elif not found_current:
                status = 'CURRENT'
                found_current = True
            else:
                status = 'UPCOMING'
            stages.append({
                'stage_number': idx,
                'name': name,
                'description': desc,
                'status': status,
                'is_completed': (status == 'COMPLETED'),
                'is_current': (status == 'CURRENT'),
                'is_upcoming': (status == 'UPCOMING'),
            })
        return stages


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
        ('Paused / Under Review', 'Paused / Under Review'),
        ('Refinement', 'Refinement Stage'),
        ('Retention', 'Retention Phase'),
        ('Completed', 'Treatment Completed'),
    ]

    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='treatment_plan')
    estimated_duration_months = models.PositiveIntegerField(default=12, blank=True)
    total_aligners = models.PositiveIntegerField(default=24)
    current_aligner = models.PositiveIntegerField(default=1)
    aligner_frequency_days = models.PositiveIntegerField(default=10, help_text="Days per aligner set (e.g. 7, 10, 14)")
    start_date = models.DateField(blank=True, null=True)
    expected_completion_date = models.DateField(blank=True, null=True)
    next_tray_change_date = models.DateField(blank=True, null=True, help_text="Doctor prescribed next tray changing date")
    is_paused = models.BooleanField(default=False)
    pause_reason = models.TextField(blank=True, null=True)

    # Upper Arch Monitoring
    upper_arch_status = models.CharField(max_length=100, default='Aligning & Leveling')
    upper_arch_notes = models.TextField(blank=True, null=True)
    upper_arch_photo = models.ImageField(upload_to='treatment_plans/upper_arch/', blank=True, null=True)

    # Lower Arch Monitoring
    lower_arch_status = models.CharField(max_length=100, default='Aligning & Leveling')
    lower_arch_notes = models.TextField(blank=True, null=True)
    lower_arch_photo = models.ImageField(upload_to='treatment_plans/lower_arch/', blank=True, null=True)

    treatment_instructions = models.TextField(
        default="Wear aligners 20-22 hours daily. Change aligners strictly as per scheduled frequency. Clean with soft brush and lukewarm water.",
        blank=True
    )
    next_review_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Active / In Progress')
    compliance_score = models.PositiveIntegerField(default=92, blank=True, help_text="Compliance percentage (0-100)")
    daily_wear_hours = models.DecimalField(max_digits=4, decimal_places=1, default=21.5, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Treatment Plan - {self.patient.full_name} ({self.current_aligner}/{self.total_aligners})"

    @property
    def next_aligner(self):
        if self.current_aligner < self.total_aligners:
            return self.current_aligner + 1
        return self.total_aligners

    @property
    def computed_next_change_date(self):
        if self.next_tray_change_date:
            return self.next_tray_change_date
        if self.start_date:
            from datetime import timedelta
            return self.start_date + timedelta(days=self.current_aligner * self.aligner_frequency_days)
        return None

    @property
    def progress_percentage(self):
        if self.total_aligners > 0:
            pct = int((self.current_aligner / self.total_aligners) * 100)
            return min(pct, 100)
        return 0


class ArchProgressHistory(models.Model):
    ARCH_CHOICES = [
        ('UPPER', 'Upper Arch'),
        ('LOWER', 'Lower Arch'),
    ]

    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='arch_histories')
    arch = models.CharField(max_length=10, choices=ARCH_CHOICES)
    stage_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=100)
    notes = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='arch_progress/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_arch_display()} - Stage {self.stage_number} ({self.treatment_plan.patient.full_name})"


class TrayHistory(models.Model):
    treatment_plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name='tray_histories')
    tray_number = models.PositiveIntegerField()
    started_on = models.DateField(default=timezone.now)
    completed_on = models.DateField(null=True, blank=True)
    doctor_notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-tray_number', '-created_at']

    def __str__(self):
        return f"Tray #{self.tray_number} - {self.treatment_plan.patient.full_name} ({self.status})"


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
        ('GUM_PROBLEMS', 'Gum Problems'),
        ('OTHER', 'Other Issues'),
    ]

    SEVERITY_CHOICES = [
        ('LOW', 'Low - Minor Discomfort'),
        ('MEDIUM', 'Moderate - Needs Guidance'),
        ('HIGH', 'High - Urgent Attention'),
        ('CRITICAL', 'Critical - Same-day Visit Required'),
    ]

    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('UNDER_REVIEW', 'Under Review'),
        ('RESPONDED', 'Responded'),
        ('RESOLVED', 'Resolved'),
        ('PENDING', 'Pending Doctor Review'),
        ('IN_REVIEW', 'In Review / Doctor Responded'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='emergency_alerts')
    issue_type = models.CharField(max_length=60, choices=ISSUE_CHOICES)
    severity = models.CharField(max_length=30, choices=SEVERITY_CHOICES, default='MEDIUM')
    description = models.TextField()
    photo = models.ImageField(upload_to='emergency_photos/', blank=True, null=True)
    reported_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='NEW')
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
        ('RESCHEDULE_REQUESTED', 'Reschedule Requested'),
        ('REQUESTED', 'Requested by Patient'),
    ]

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='appointments')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    appointment_type = models.CharField(max_length=60, choices=APPOINTMENT_TYPE_CHOICES, default='ROUTINE_CHECKUP')
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    instructions = models.TextField(blank=True, null=True, help_text="Doctor appointment preparation instructions")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='UPCOMING')
    reschedule_requested = models.BooleanField(default=False)
    reschedule_requested_date = models.DateField(blank=True, null=True)
    reschedule_requested_time = models.TimeField(blank=True, null=True)
    reschedule_reason = models.TextField(blank=True, null=True)
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


class PreoperativePhoto(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='preoperative_photos')
    photo = models.ImageField(upload_to='preoperative_photos/')
    title = models.CharField(max_length=200, default='Preoperative Dental View', blank=True)
    description = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Pre-op Photo ({self.title}) - {self.patient.full_name}"


class RadiographRecord(models.Model):
    TYPE_CHOICES = [
        ('OPG', 'OPG (Orthopantomogram / Panoramic)'),
        ('LATERAL_CEPHALOGRAPH', 'Lateral Cephalograph'),
        ('TYPE_1', 'OPG (First Radiograph)'),
        ('TYPE_2', 'Lateral Cephalograph (Second Radiograph)'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='radiographs')
    radiograph_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='OPG')
    title = models.CharField(max_length=200, blank=True, help_text="e.g. Panoramic OPG, Lateral Cephalogram")
    image = models.ImageField(upload_to='radiographs/')
    description = models.TextField(blank=True, null=True)
    examination_date = models.DateField(default=timezone.localdate)
    version = models.PositiveIntegerField(default=1)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-examination_date', '-uploaded_at']

    def __str__(self):
        return f"{self.get_radiograph_type_display()} - {self.title or 'Radiograph'} (v{self.version}) - {self.patient.full_name}"


class TreatmentOperationRecord(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='operation_records')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='operation_records')
    record_date = models.DateTimeField(default=timezone.now)
    current_condition = models.TextField(help_text="Patient's Current Dental Condition")
    examination_findings = models.TextField(help_text="Examination Findings")
    identified_problems = models.TextField(help_text="Identified Dental Problems")
    operation_performed = models.CharField(max_length=250, help_text="Treatment or Operation Performed")
    treatment_description = models.TextField(help_text="Treatment Description")
    doctor_observations = models.TextField(blank=True, null=True, help_text="Doctor's Observations")
    next_treatment_steps = models.TextField(blank=True, null=True, help_text="Next Treatment Steps")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-record_date', '-created_at']

    def __str__(self):
        return f"{self.operation_performed} on {self.record_date.strftime('%Y-%m-%d')} - {self.patient.full_name}"


class Prescription(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='prescriptions')
    prescription_date = models.DateField(default=timezone.localdate)
    diagnosis = models.TextField(help_text="Diagnosis / Clinical Findings")
    medicines_data = models.TextField(help_text="Prescribed Medicines, Dosage, Frequency, Duration")
    special_instructions = models.TextField(blank=True, null=True, help_text="Special Instructions")
    next_followup_date = models.DateField(blank=True, null=True, help_text="Next Follow-up Date")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-prescription_date', '-created_at']

    def __str__(self):
        return f"Prescription #{self.id} for {self.patient.full_name} ({self.prescription_date})"


class TreatmentTurn(models.Model):
    STATUS_CHOICES = [
        ('UPCOMING', 'Upcoming'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('PAUSED', 'Paused'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='treatment_turns')
    turn_number = models.PositiveIntegerField()
    start_date = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    instructions = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='UPCOMING')
    next_turn_date = models.DateField(blank=True, null=True)
    doctor_remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['turn_number', 'created_at']

    def __str__(self):
        return f"Turn #{self.turn_number} ({self.get_status_display()}) - {self.patient.full_name}"


class DoctorTreatmentMedia(models.Model):
    OPERATION_TYPE_CHOICES = [
        ('TURN_QUEST', 'Turn Quest'),
        ('OTHER', 'Other Operation'),
    ]
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily Update'),
        ('WEEKLY', 'Weekly Update'),
        ('MONTHLY', 'Monthly Update'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='treatment_media')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='treatment_media')
    operation_type = models.CharField(max_length=50, choices=OPERATION_TYPE_CHOICES, default='TURN_QUEST')
    operation_name = models.CharField(max_length=200, default='Turn Quest')
    patient_problem = models.TextField(blank=True, null=True, help_text="What is the problem of the patient")
    update_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='WEEKLY')
    video = models.FileField(upload_to='treatment_media/videos/', blank=True, null=True)
    video_description = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='treatment_media/photos/', blank=True, null=True)
    photo_description = models.TextField(blank=True, null=True)
    treatment_stage = models.CharField(max_length=150, default='Active Treatment Stage')
    doctor_instructions = models.TextField(blank=True, null=True)
    upload_date = models.DateField(default=timezone.localdate)
    version = models.PositiveIntegerField(default=1)
    is_current = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version', '-created_at']

    def __str__(self):
        return f"Treatment Media v{self.version} - {self.patient.full_name} ({self.treatment_stage})"


class MonthlyTreatmentNote(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='monthly_notes')
    month_number = models.PositiveIntegerField(default=1)
    note_date = models.DateField(default=timezone.localdate)
    status_update = models.CharField(max_length=100, default='On Track / Normal Progress')
    notes = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-month_number', '-created_at']

    def __str__(self):
        return f"Month #{self.month_number} Note - {self.patient.full_name}"


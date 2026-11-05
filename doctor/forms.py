from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    DoctorProfile, Patient, PatientJoiningCode,
    ClinicalRecord, TreatmentPlan, PhotoMonitoring,
    EmergencyAlert, Appointment, Notification,
    PreoperativePhoto, RadiographRecord, TreatmentOperationRecord,
    Prescription, TreatmentTurn, DoctorTreatmentMedia, MonthlyTreatmentNote
)


class DoctorRegistrationForm(forms.Form):
    full_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Dr. Sarah Jenkins, DDS'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'doctor@example.com'})
    )
    phone_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+1 (555) 234-5678'})
    )
    dental_qualification = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'BDS, MDS - Pediatric Dentistry & Orthodontics'})
    )
    specialization = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Orthodontist, Pedodontist'})
    )
    ksdc_registration_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. KSDC-12345-A'})
    )
    clinic_name = forms.CharField(
        max_length=250,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'PedoAlign Orthodontic Clinic'})
    )
    clinic_address = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': '123 Medical Boulevard, Suite 400, City, State'})
    )
    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Create a secure password (min 8 chars)'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm your password'})
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get("password")
        pwd_confirm = cleaned_data.get("confirm_password")
        if pwd and pwd_confirm and pwd != pwd_confirm:
            self.add_error('confirm_password', "Passwords do not match.")
        if pwd and len(pwd) < 8:
            self.add_error('password', "Password must be at least 8 characters.")
        return cleaned_data


class DoctorLoginForm(forms.Form):
    email = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Registered Email Address'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Enter your password'})
    )


class DoctorProfileForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'doctor@example.com'})
    )

    class Meta:
        model = DoctorProfile
        fields = [
            'full_name', 'phone_number', 'dental_qualification', 'specialization',
            'ksdc_registration_number', 'clinic_name', 'clinic_address', 'license_number', 'bio',
            'profile_picture', 'email_notifications', 'sms_alerts', 'emergency_push'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'dental_qualification': forms.TextInput(attrs={'class': 'form-input'}),
            'specialization': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Orthodontist, Pedodontist'}),
            'ksdc_registration_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. KSDC-12345-A'}),
            'clinic_name': forms.TextInput(attrs={'class': 'form-input'}),
            'clinic_address': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'license_number': forms.TextInput(attrs={'class': 'form-input'}),
            'bio': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'rounded text-blue-600 focus:ring-blue-500 h-4 w-4'}),
            'sms_alerts': forms.CheckboxInput(attrs={'class': 'rounded text-blue-600 focus:ring-blue-500 h-4 w-4'}),
            'emergency_push': forms.CheckboxInput(attrs={'class': 'rounded text-blue-600 focus:ring-blue-500 h-4 w-4'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'user') and self.instance.user:
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=commit)
        new_email = self.cleaned_data.get('email')
        if new_email and profile.user and profile.user.email != new_email:
            profile.user.email = new_email
            profile.user.save()
        return profile


class PatientForm(forms.ModelForm):
    patient_category = forms.ChoiceField(
        choices=Patient.CATEGORY_CHOICES,
        required=False,
        initial='CHILD',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    appointment_frequency = forms.ChoiceField(
        choices=Patient.FREQUENCY_CHOICES,
        required=False,
        initial='MONTHLY',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    age = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=120,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Age (years)', 'min': 0, 'max': 120})
    )
    medical_history = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Allergies, systemic illnesses, ongoing medications...'})
    )
    dental_history = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Previous dental/ortho treatments, dental trauma, habits...'})
    )
    schedule_20day_followup = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-blue-600 rounded focus:ring-blue-500'})
    )
    custom_followup_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )

    class Meta:
        model = Patient
        fields = [
            'first_name', 'last_name', 'patient_category', 'email', 'phone',
            'age', 'gender', 'date_of_birth',
            'parent_guardian_name', 'parent_guardian_phone', 'parent_guardian_email', 'parent_guardian_relationship',
            'appointment_frequency', 'treatment_duration_months', 'notes', 'profile_photo'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'patient@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Primary Phone / WhatsApp'}),
            'age': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Age (years)', 'min': 1, 'max': 99}),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'parent_guardian_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Parent or Legal Guardian'}),
            'parent_guardian_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Parent Contact Phone'}),
            'parent_guardian_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'parent@example.com'}),
            'parent_guardian_relationship': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Mother, Father, Guardian'}),
            'treatment_duration_months': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 60}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Initial clinical notes or case overview...'}),
        }

    def clean_patient_category(self):
        return self.cleaned_data.get('patient_category') or 'CHILD'

    def clean_appointment_frequency(self):
        return self.cleaned_data.get('appointment_frequency') or 'MONTHLY'

    def clean(self):
        cleaned_data = super().clean()
        dob = cleaned_data.get('date_of_birth')
        age = cleaned_data.get('age')
        if dob:
            today = timezone.localdate()
            calc_age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age is None:
                cleaned_data['age'] = max(0, calc_age)
        elif age is None:
            self.add_error('age', 'Please enter patient Age or select Date of Birth.')
        return cleaned_data


class PatientEditForm(forms.ModelForm):
    patient_category = forms.ChoiceField(
        choices=Patient.CATEGORY_CHOICES,
        required=False,
        initial='CHILD',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    appointment_frequency = forms.ChoiceField(
        choices=Patient.FREQUENCY_CHOICES,
        required=False,
        initial='MONTHLY',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    age = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=120,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Age (years)', 'min': 0, 'max': 120})
    )
    medical_history = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Allergies, systemic illnesses, ongoing medications...'})
    )
    dental_history = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Previous dental/ortho treatments, trauma, habits...'})
    )

    class Meta:
        model = Patient
        fields = [
            'first_name', 'last_name', 'patient_category', 'email', 'phone',
            'age', 'gender', 'date_of_birth',
            'parent_guardian_name', 'parent_guardian_phone', 'parent_guardian_email', 'parent_guardian_relationship',
            'appointment_frequency', 'treatment_status', 'treatment_start_date', 'treatment_duration_months',
            'notes', 'profile_photo'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'age': forms.NumberInput(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'parent_guardian_name': forms.TextInput(attrs={'class': 'form-input'}),
            'parent_guardian_phone': forms.TextInput(attrs={'class': 'form-input'}),
            'parent_guardian_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'parent_guardian_relationship': forms.TextInput(attrs={'class': 'form-input'}),
            'treatment_status': forms.Select(attrs={'class': 'form-input'}),
            'treatment_start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'treatment_duration_months': forms.NumberInput(attrs={'class': 'form-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }

    def clean_patient_category(self):
        return self.cleaned_data.get('patient_category') or 'CHILD'

    def clean_appointment_frequency(self):
        return self.cleaned_data.get('appointment_frequency') or 'MONTHLY'

    def clean(self):
        cleaned_data = super().clean()
        dob = cleaned_data.get('date_of_birth')
        age = cleaned_data.get('age')
        if dob:
            today = timezone.localdate()
            calc_age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age is None:
                cleaned_data['age'] = max(0, calc_age)
        elif age is None:
            self.add_error('age', 'Please enter patient Age or select Date of Birth.')
        return cleaned_data


class ClinicalRecordForm(forms.ModelForm):
    class Meta:
        model = ClinicalRecord
        fields = [
            'teeth_present', 'overbite', 'deep_bite',
            'molar_relationship', 'canine_relationship', 'crossbite',
            'molar_occlusion', 'oral_habits',
            'medical_history', 'dental_history',
            'skeletal_notes', 'doctor_clinical_notes'
        ]
        widgets = {
            'teeth_present': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Full Mixed Dentition (Class II, 24 erupted)'}),
            'overbite': forms.Select(attrs={'class': 'form-input'}),
            'deep_bite': forms.Select(attrs={'class': 'form-input'}),
            'molar_relationship': forms.Select(attrs={'class': 'form-input'}),
            'canine_relationship': forms.Select(attrs={'class': 'form-input'}),
            'crossbite': forms.Select(attrs={'class': 'form-input'}),
            'molar_occlusion': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Flush terminal plane / Mesial step'}),
            'oral_habits': forms.Select(attrs={'class': 'form-input'}),
            'medical_history': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Systemic medical conditions, drug allergies, asthma, etc.'}),
            'dental_history': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Previous extractions, restorations, dental trauma...'}),
            'skeletal_notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Skeletal pattern, jaw profile, facial symmetry, crowding notes...'}),
            'doctor_clinical_notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Key clinical diagnoses and recommendations...'}),
        }


class TreatmentPlanForm(forms.ModelForm):
    estimated_duration_months = forms.IntegerField(
        required=False,
        initial=12,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'min': 1})
    )
    compliance_score = forms.IntegerField(
        required=False,
        initial=92,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100})
    )
    daily_wear_hours = forms.DecimalField(
        required=False,
        initial=21.5,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.5', 'min': 0, 'max': 24})
    )

    class Meta:
        model = TreatmentPlan
        fields = [
            'estimated_duration_months', 'total_aligners', 'current_aligner',
            'aligner_frequency_days', 'start_date', 'expected_completion_date',
            'next_tray_change_date', 'is_paused', 'pause_reason',
            'upper_arch_status', 'upper_arch_notes', 'upper_arch_photo',
            'lower_arch_status', 'lower_arch_notes', 'lower_arch_photo',
            'status', 'compliance_score', 'daily_wear_hours',
            'next_review_date', 'treatment_instructions'
        ]
        widgets = {
            'total_aligners': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'current_aligner': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'aligner_frequency_days': forms.NumberInput(attrs={'class': 'form-input', 'min': 3, 'max': 30}),
            'start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'expected_completion_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'next_tray_change_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'is_paused': forms.CheckboxInput(attrs={'class': 'rounded text-amber-600 focus:ring-amber-500 h-4 w-4'}),
            'pause_reason': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Reason for pausing (e.g. gingival recovery, aligner lost)'}),
            'upper_arch_status': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Aligning, Expanding, Space Closure, On Track'}),
            'upper_arch_notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Specific clinical progress notes for upper arch...'}),
            'upper_arch_photo': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'lower_arch_status': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Aligning, De-crowding, Finishing, On Track'}),
            'lower_arch_notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Specific clinical progress notes for lower arch...'}),
            'lower_arch_photo': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'next_review_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'treatment_instructions': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }

    def clean_estimated_duration_months(self):
        return self.cleaned_data.get('estimated_duration_months') or 12

    def clean_compliance_score(self):
        val = self.cleaned_data.get('compliance_score')
        return 92 if val is None else val

    def clean_daily_wear_hours(self):
        val = self.cleaned_data.get('daily_wear_hours')
        return 21.5 if val is None else val


class PhotoMonitoringReviewForm(forms.ModelForm):
    class Meta:
        model = PhotoMonitoring
        fields = ['tracking_status', 'doctor_rating', 'doctor_feedback']
        widgets = {
            'tracking_status': forms.Select(attrs={'class': 'form-input'}),
            'doctor_rating': forms.Select(
                choices=[(5, '⭐⭐⭐⭐⭐ 5/5 - Perfect fit & tracking'),
                         (4, '⭐⭐⭐⭐ 4/5 - Good tracking'),
                         (3, '⭐⭐⭐ 3/5 - Acceptable with minor gaps'),
                         (2, '⭐⭐ 2/5 - Poor tracking / chewier recommended'),
                         (1, '⭐ 1/5 - Urgent Clinic Review Required')],
                attrs={'class': 'form-input'}
            ),
            'doctor_feedback': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Write clinical feedback for the patient...'}),
        }


class PhotoUploadForm(forms.ModelForm):
    class Meta:
        model = PhotoMonitoring
        fields = [
            'week_number', 'aligner_stage',
            'front_bite_photo', 'upper_arch_photo', 'lower_arch_photo',
            'right_occlusion_photo', 'left_occlusion_photo',
            'patient_notes', 'is_before_sample', 'is_after_sample'
        ]
        widgets = {
            'week_number': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'aligner_stage': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'patient_notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Notes about this photo set...'}),
            'is_before_sample': forms.CheckboxInput(attrs={'class': 'rounded text-blue-600'}),
            'is_after_sample': forms.CheckboxInput(attrs={'class': 'rounded text-blue-600'}),
        }


class EmergencyResponseForm(forms.ModelForm):
    status = forms.ChoiceField(
        choices=[
            ('NEW', 'New'),
            ('UNDER_REVIEW', 'Under Review'),
            ('RESPONDED', 'Responded'),
            ('RESOLVED', 'Resolved'),
        ],
        widget=forms.Select(attrs={'class': 'form-input'})
    )

    class Meta:
        model = EmergencyAlert
        fields = ['status', 'doctor_response']
        widgets = {
            'doctor_response': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Enter doctor advice, prescription, or clinical appointment instruction...'}),
        }


class EmergencyCreateForm(forms.ModelForm):
    class Meta:
        model = EmergencyAlert
        fields = ['patient', 'issue_type', 'severity', 'description', 'photo']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-input'}),
            'issue_type': forms.Select(attrs={'class': 'form-input'}),
            'severity': forms.Select(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Describe the patient emergency or issue in detail...'}),
            'photo': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        if doctor:
            self.fields['patient'].queryset = Patient.objects.filter(doctor=doctor)


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['patient', 'appointment_type', 'scheduled_date', 'scheduled_time', 'duration_minutes', 'instructions', 'status', 'notes']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-input'}),
            'appointment_type': forms.Select(attrs={'class': 'form-input'}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'scheduled_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-input', 'min': 10, 'step': 5}),
            'instructions': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Preparation instructions for patient (e.g. bring tray #4 and chewies)...'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Appointment agenda or notes...'}),
        }

    def __init__(self, *args, **kwargs):
        doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        if doctor:
            self.fields['patient'].queryset = Patient.objects.filter(doctor=doctor)


class SendReminderInstructionForm(forms.Form):
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.none(),
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    instruction_type = forms.ChoiceField(
        choices=[
            ('ALIGNER_CHANGE', 'Aligner Change Reminder'),
            ('PHOTO_SUBMISSION', 'Weekly Photo Submission Due'),
            ('COMPLIANCE_ENCOURAGEMENT', 'Aligner Wear Time Encouragement (22 hrs)'),
            ('APPOINTMENT_REMINDER', 'Upcoming In-Clinic Appointment'),
            ('CUSTOM_MESSAGE', 'Custom Clinical Instruction'),
        ],
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Subject / Alert Title'})
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Message to be sent to patient / parent...'})
    )

    def __init__(self, *args, **kwargs):
        doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        if doctor:
            self.fields['patient'].queryset = Patient.objects.filter(doctor=doctor)


class PatientJoinCodeForm(forms.Form):
    joining_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-input text-center text-2xl font-bold tracking-widest uppercase text-blue-700 py-3',
            'placeholder': 'PA-XXXXXX',
            'autofocus': True,
        })
    )
    patient_first_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Patient First Name (Optional)'})
    )
    patient_last_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Patient Last Name (Optional)'})
    )
    phone = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Your Phone / WhatsApp (Optional)'})
    )
    request_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Optional message or notes for your doctor'})
    )


class PreoperativePhotoForm(forms.ModelForm):
    class Meta:
        model = PreoperativePhoto
        fields = ['photo', 'title', 'description']
        widgets = {
            'photo': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*', 'capture': 'environment'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Frontal smile view, Upper occlusal'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Clinical notes or photographic description...'}),
        }


class CompulsoryPreoperativePhotosForm(forms.Form):
    photo_1 = forms.ImageField(
        label="Preoperative Photo 1 (Frontal View)",
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*', 'capture': 'environment', 'id': 'preop_file_1'})
    )
    description_1 = forms.CharField(
        label="Photo 1 Description",
        required=False,
        initial="Frontal View - Teeth in Centric Occlusion",
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Frontal View - Teeth in Centric Occlusion'})
    )
    photo_2 = forms.ImageField(
        label="Preoperative Photo 2 (Upper Arch)",
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*', 'capture': 'environment', 'id': 'preop_file_2'})
    )
    description_2 = forms.CharField(
        label="Photo 2 Description",
        required=False,
        initial="Upper Arch (Maxillary) Occlusal View",
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Upper Arch (Maxillary) Occlusal View'})
    )
    photo_3 = forms.ImageField(
        label="Preoperative Photo 3 (Lower Arch / Lateral)",
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*', 'capture': 'environment', 'id': 'preop_file_3'})
    )
    description_3 = forms.CharField(
        label="Photo 3 Description",
        required=False,
        initial="Lower Arch (Mandibular) / Lateral View",
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Lower Arch (Mandibular) or Lateral View'})
    )


class RadiographRecordForm(forms.ModelForm):
    class Meta:
        model = RadiographRecord
        fields = ['radiograph_type', 'title', 'image', 'examination_date', 'description']
        widgets = {
            'radiograph_type': forms.Select(attrs={'class': 'form-input'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Panoramic OPG, Lateral Cephalogram'}),
            'image': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'examination_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Radiograph findings, cephalometric notes...'}),
        }


class TreatmentOperationRecordForm(forms.ModelForm):
    class Meta:
        model = TreatmentOperationRecord
        fields = [
            'record_date', 'current_condition', 'examination_findings',
            'identified_problems', 'operation_performed', 'treatment_description',
            'doctor_observations', 'next_treatment_steps'
        ]
        widgets = {
            'record_date': forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
            'current_condition': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': "Patient's current dental condition"}),
            'examination_findings': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Examination findings'}),
            'identified_problems': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Identified dental problems'}),
            'operation_performed': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Aligner IPR, Attachment Placement, Extraction'}),
            'treatment_description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Procedure and treatment details'}),
            'doctor_observations': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': "Doctor's clinical observations"}),
            'next_treatment_steps': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Next clinical treatment steps'}),
        }


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['prescription_date', 'diagnosis', 'medicines_data', 'special_instructions', 'next_followup_date']
        widgets = {
            'prescription_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'diagnosis': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Diagnosis / Clinical Findings'}),
            'medicines_data': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': "1. Paracetamol 250mg - 1 tab - Twice daily - 3 days (after food)\n2. Chlorhexidine Mouthwash 0.2% - 10ml - Twice daily - 7 days\n3. Orthodontic Wax - Apply to aligner edge as needed"}),
            'special_instructions': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Diet cautions, oral hygiene, aligner wear instructions'}),
            'next_followup_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }


class TreatmentTurnForm(forms.ModelForm):
    class Meta:
        model = TreatmentTurn
        fields = ['turn_number', 'start_date', 'completion_date', 'instructions', 'status', 'next_turn_date', 'doctor_remarks']
        widgets = {
            'turn_number': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'completion_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'instructions': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Turn instructions, wear schedule, elastics'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'next_turn_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'doctor_remarks': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Doctor clinical remarks'}),
        }


class DoctorTreatmentMediaForm(forms.ModelForm):
    class Meta:
        model = DoctorTreatmentMedia
        fields = ['treatment_stage', 'photo', 'photo_description', 'video', 'video_description', 'doctor_instructions']
        widgets = {
            'treatment_stage': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Stage 1: Arch Expansion'}),
            'photo': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'photo_description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Photo description'}),
            'video': forms.FileInput(attrs={'class': 'form-input', 'accept': 'video/*'}),
            'video_description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Video description'}),
            'doctor_instructions': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Doctor instructions for patient'}),
        }


class MonthlyTreatmentNoteForm(forms.ModelForm):
    class Meta:
        model = MonthlyTreatmentNote
        fields = ['month_number', 'note_date', 'status_update', 'notes']
        widgets = {
            'month_number': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'note_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'status_update': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Good progress, midline corrected'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Monthly evaluation notes'}),
        }


class ArchivePatientForm(forms.Form):
    ACTION_CHOICES = [
        ('COMPLETE', 'Mark Treatment Completed (Keep account active for permitted historical info)'),
        ('DEACTIVATE', 'Deactivate Patient (Soft-delete/Archive; patient can no longer log in)'),
    ]
    action_type = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'text-blue-600 focus:ring-blue-500'})
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Reason or clinical notes for this archive action...'})
    )


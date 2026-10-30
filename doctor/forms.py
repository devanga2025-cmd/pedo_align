from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    DoctorProfile, Patient, PatientJoiningCode,
    ClinicalRecord, TreatmentPlan, PhotoMonitoring,
    EmergencyAlert, Appointment, Notification
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
    class Meta:
        model = DoctorProfile
        fields = [
            'full_name', 'phone_number', 'dental_qualification',
            'clinic_name', 'clinic_address', 'license_number', 'bio',
            'profile_picture', 'email_notifications', 'sms_alerts', 'emergency_push'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'dental_qualification': forms.TextInput(attrs={'class': 'form-input'}),
            'clinic_name': forms.TextInput(attrs={'class': 'form-input'}),
            'clinic_address': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'license_number': forms.TextInput(attrs={'class': 'form-input'}),
            'bio': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'rounded text-blue-600 focus:ring-blue-500 h-4 w-4'}),
            'sms_alerts': forms.CheckboxInput(attrs={'class': 'rounded text-blue-600 focus:ring-blue-500 h-4 w-4'}),
            'emergency_push': forms.CheckboxInput(attrs={'class': 'rounded text-blue-600 focus:ring-blue-500 h-4 w-4'}),
        }


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'age', 'gender', 'date_of_birth',
            'parent_guardian_name', 'parent_guardian_phone',
            'treatment_duration_months', 'notes', 'profile_photo'
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
            'treatment_duration_months': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 60}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Initial clinical notes or case overview...'}),
        }


class PatientEditForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'age', 'gender', 'date_of_birth',
            'parent_guardian_name', 'parent_guardian_phone',
            'treatment_status', 'treatment_start_date', 'treatment_duration_months',
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
            'treatment_status': forms.Select(attrs={'class': 'form-input'}),
            'treatment_start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'treatment_duration_months': forms.NumberInput(attrs={'class': 'form-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }


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
    class Meta:
        model = TreatmentPlan
        fields = [
            'estimated_duration_months', 'total_aligners', 'current_aligner',
            'aligner_frequency_days', 'start_date', 'expected_completion_date',
            'status', 'compliance_score', 'daily_wear_hours',
            'next_review_date', 'treatment_instructions'
        ]
        widgets = {
            'estimated_duration_months': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'total_aligners': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'current_aligner': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'aligner_frequency_days': forms.NumberInput(attrs={'class': 'form-input', 'min': 3, 'max': 30}),
            'start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'expected_completion_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'next_review_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'compliance_score': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100}),
            'daily_wear_hours': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.5', 'min': 0, 'max': 24}),
            'treatment_instructions': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }


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
    class Meta:
        model = EmergencyAlert
        fields = ['status', 'doctor_response']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-input'}),
            'doctor_response': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Enter doctor advice, prescription, or clinical appointment instruction...'}),
        }


class EmergencyCreateForm(forms.ModelForm):
    class Meta:
        model = EmergencyAlert
        fields = ['patient', 'issue_type', 'severity', 'description']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-input'}),
            'issue_type': forms.Select(attrs={'class': 'form-input'}),
            'severity': forms.Select(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Describe the patient emergency or issue in detail...'}),
        }

    def __init__(self, *args, **kwargs):
        doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        if doctor:
            self.fields['patient'].queryset = Patient.objects.filter(doctor=doctor)


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['patient', 'appointment_type', 'scheduled_date', 'scheduled_time', 'duration_minutes', 'status', 'notes']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-input'}),
            'appointment_type': forms.Select(attrs={'class': 'form-input'}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'scheduled_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-input', 'min': 10, 'step': 5}),
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
            'placeholder': 'PA-XXXXXX'
        })
    )
    patient_first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Patient First Name'})
    )
    patient_last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Patient Last Name'})
    )
    phone = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Your Phone / WhatsApp Number'})
    )
    request_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Optional message or notes for your doctor'})
    )

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import PatientProfile


class PatientCodeLoginForm(forms.Form):
    joining_code = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-input-patient uppercase font-black tracking-widest text-center text-blue-700 text-lg py-3',
            'placeholder': 'PA-XXXXXX',
            'autocomplete': 'off',
            'autofocus': True
        })
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input-patient',
            'placeholder': 'Your Gmail or Email (Optional)',
            'autocomplete': 'email',
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'rounded text-blue-600 focus:ring-blue-400 h-4 w-4'
        })
    )


class PatientLoginForm(forms.Form):
    login_identifier = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input-patient',
            'placeholder': 'Enter Email or Patient ID (e.g. PA-PT-12345)',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input-patient',
            'placeholder': '••••••••'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'rounded text-blue-600 focus:ring-blue-400 h-4 w-4'
        })
    )


class PatientRegistrationForm(forms.Form):
    patient_category = forms.ChoiceField(
        choices=PatientProfile.CATEGORY_CHOICES,
        required=False,
        initial='CHILD',
        widget=forms.Select(attrs={'class': 'form-input-patient', 'id': 'id_patient_category', 'onchange': 'toggleParentFields()'})
    )
    full_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-input-patient',
            'placeholder': 'e.g. Alexander Brooks'
        })
    )
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-input-patient',
            'type': 'date'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input-patient',
            'placeholder': 'patient@example.com'
        })
    )
    mobile_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-input-patient',
            'placeholder': '+1 (555) 987-6543'
        })
    )
    parent_guardian_name = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input-patient',
            'placeholder': 'Parent or Guardian Full Name (for Child Patient)'
        })
    )
    parent_guardian_phone = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-input-patient',
            'placeholder': 'Parent Contact Phone'
        })
    )
    parent_guardian_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input-patient',
            'placeholder': 'parent@example.com'
        })
    )
    parent_guardian_relationship = forms.CharField(
        required=False,
        max_length=50,
        initial='Parent',
        widget=forms.TextInput(attrs={
            'class': 'form-input-patient',
            'placeholder': 'e.g. Mother, Father, Guardian'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input-patient',
            'placeholder': 'Create password (min 8 chars)'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input-patient',
            'placeholder': 'Re-enter password'
        })
    )

    def clean_patient_category(self):
        return self.cleaned_data.get('patient_category') or 'CHILD'

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists. Please log in.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get('password')
        pwd_confirm = cleaned_data.get('confirm_password')
        if pwd and pwd_confirm and pwd != pwd_confirm:
            self.add_error('confirm_password', "Passwords do not match.")
        if pwd and len(pwd) < 8:
            self.add_error('password', "Password must be at least 8 characters.")
        return cleaned_data


class DoctorConnectCodeForm(forms.Form):
    joining_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-input-patient text-center text-2xl font-black uppercase tracking-widest text-blue-600 py-3.5',
            'placeholder': 'PA-XXXXXX',
            'autocomplete': 'off'
        })
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input-patient',
            'rows': 2,
            'placeholder': 'Optional: Say hi to your doctor or add any message...'
        })
    )


class TeethPhotoUploadForm(forms.Form):
    week_number = forms.IntegerField(
        min_value=1,
        max_value=150,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-input-patient'})
    )
    photo_front = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*', 'id': 'photo_front_input'})
    )
    photo_left = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*', 'id': 'photo_left_input'})
    )
    photo_right = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*', 'id': 'photo_right_input'})
    )
    photo_upper = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*', 'id': 'photo_upper_input'})
    )
    photo_lower = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*', 'id': 'photo_lower_input'})
    )
    patient_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input-patient',
            'rows': 2,
            'placeholder': 'How are your aligners feeling this week? Any tightness or comments for your doctor?'
        })
    )


class PatientAppointmentRequestForm(forms.Form):
    appointment_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-input-patient', 'type': 'date'})
    )
    preferred_time = forms.ChoiceField(
        choices=[
            ('09:00', '09:00 AM - Morning'),
            ('10:30', '10:30 AM - Morning'),
            ('12:00', '12:00 PM - Noon'),
            ('14:30', '02:30 PM - Afternoon'),
            ('16:00', '04:00 PM - Evening'),
            ('17:30', '05:30 PM - Evening'),
        ],
        widget=forms.Select(attrs={'class': 'form-input-patient'})
    )
    reason = forms.ChoiceField(
        choices=[
            ('ALIGNER_CHECKUP', 'Routine Aligner Checkup & Tracking'),
            ('NEW_ALIGNER_BOX', 'Pick Up New Aligner Trays'),
            ('ATTACHMENT_CHECK', 'Attachment / Button Check'),
            ('DISCOMFORT_REVIEW', 'Consultation for Discomfort or Fitting Issue'),
            ('RETAINER_CONSULT', 'Post-Treatment Retainer Consultation'),
            ('OTHER', 'Other In-Clinic Visit'),
        ],
        widget=forms.Select(attrs={'class': 'form-input-patient'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input-patient',
            'rows': 2,
            'placeholder': 'Add any notes for clinic staff...'
        })
    )


class PatientEmergencyReportForm(forms.Form):
    PROBLEM_CHOICES = [
        ('TOOTH_PAIN', 'Tooth Pain'),
        ('ALIGNER_DISCOMFORT', 'Aligner Discomfort'),
        ('BROKEN_ALIGNER', 'Broken Aligner'),
        ('LOOSE_ALIGNER', 'Loose Aligner'),
        ('GUM_PROBLEMS', 'Gum Problems'),
        ('OTHER', 'Other Issues'),
    ]

    problem_type = forms.ChoiceField(
        choices=PROBLEM_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input-patient'})
    )
    severity = forms.ChoiceField(
        choices=[
            ('MEDIUM', 'Moderate - Needs Attention Soon'),
            ('HIGH', 'Urgent / Painful - Needs Doctor Response Today'),
        ],
        widget=forms.Select(attrs={'class': 'form-input-patient'})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-input-patient',
            'rows': 4,
            'placeholder': 'Please describe what happened, which tooth is hurting or which aligner tray is damaged...'
        })
    )
    photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-input-patient', 'accept': 'image/*'})
    )


class AppointmentRescheduleRequestForm(forms.Form):
    appointment_id = forms.IntegerField(widget=forms.HiddenInput())
    preferred_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-input-patient', 'type': 'date'})
    )
    preferred_time = forms.ChoiceField(
        choices=[
            ('09:00', '09:00 AM - Morning'),
            ('10:30', '10:30 AM - Morning'),
            ('12:00', '12:00 PM - Noon'),
            ('14:30', '02:30 PM - Afternoon'),
            ('16:00', '04:00 PM - Evening'),
            ('17:30', '05:30 PM - Evening'),
        ],
        widget=forms.Select(attrs={'class': 'form-input-patient'})
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-input-patient',
            'rows': 3,
            'placeholder': 'Reason for requesting reschedule (e.g. school exam, family travel)...'
        })
    )


class PatientProfileEditForm(forms.ModelForm):
    class Meta:
        model = PatientProfile
        fields = [
            'full_name', 'patient_category', 'phone_number', 'date_of_birth',
            'parent_guardian_name', 'parent_guardian_phone', 'parent_guardian_email', 'parent_guardian_relationship',
            'avatar'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input-patient'}),
            'patient_category': forms.Select(attrs={'class': 'form-input-patient'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input-patient'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input-patient', 'type': 'date'}),
            'parent_guardian_name': forms.TextInput(attrs={'class': 'form-input-patient', 'placeholder': 'Parent or Guardian Full Name'}),
            'parent_guardian_phone': forms.TextInput(attrs={'class': 'form-input-patient', 'placeholder': 'Parent Contact Phone'}),
            'parent_guardian_email': forms.EmailInput(attrs={'class': 'form-input-patient', 'placeholder': 'parent@example.com'}),
            'parent_guardian_relationship': forms.TextInput(attrs={'class': 'form-input-patient', 'placeholder': 'Father, Mother, Guardian'}),
        }


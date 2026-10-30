from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import PatientProfile


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
        ('TOOTH_PAIN', 'Severe Tooth Pain'),
        ('ALIGNER_DISCOMFORT', 'Aligner Discomfort / Cutting Gums'),
        ('BROKEN_ALIGNER', 'Broken / Cracked Aligner Tray'),
        ('LOST_ALIGNER', 'Lost / Loose Aligner'),
        ('GUM_PROBLEMS', 'Bleeding or Swollen Gums'),
        ('ATTACHMENT_LOST', 'Tooth Button / Attachment Came Off'),
        ('OTHER', 'Other Urgent Dental Problem'),
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


class PatientProfileEditForm(forms.ModelForm):
    class Meta:
        model = PatientProfile
        fields = ['full_name', 'phone_number', 'date_of_birth', 'avatar']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input-patient'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input-patient'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input-patient', 'type': 'date'}),
        }


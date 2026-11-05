from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Avg
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
import csv
import json

from .models import (
    DoctorProfile, Patient, PatientJoiningCode,
    ClinicalRecord, TreatmentPlan, ArchProgressHistory, TrayHistory,
    PhotoMonitoring, EmergencyAlert, Appointment, Notification,
    PatientActivityLog, generate_joining_code,
    PreoperativePhoto, RadiographRecord, TreatmentOperationRecord,
    Prescription, TreatmentTurn, DoctorTreatmentMedia, MonthlyTreatmentNote
)
from .forms import (
    DoctorRegistrationForm, DoctorLoginForm, DoctorProfileForm,
    PatientForm, PatientEditForm, ClinicalRecordForm, TreatmentPlanForm,
    PhotoMonitoringReviewForm, PhotoUploadForm, EmergencyResponseForm,
    EmergencyCreateForm, AppointmentForm, SendReminderInstructionForm,
    PatientJoinCodeForm, PreoperativePhotoForm, RadiographRecordForm,
    TreatmentOperationRecordForm, PrescriptionForm, TreatmentTurnForm,
    DoctorTreatmentMediaForm, MonthlyTreatmentNoteForm, ArchivePatientForm,
    CompulsoryPreoperativePhotosForm
)
from patient.models import PatientNotification


# Helper: get doctor or redirect
def get_doctor_or_none(user):
    if not user.is_authenticated:
        return None
    try:
        return user.doctor_profile
    except DoctorProfile.DoesNotExist:
        return None


def notify_patient_profile(patient, notification_type, title, message, link_url='/patient/'):
    """
    Safely delivers a notification to the patient portal profile linked to a ClinicalPatient.
    Matches via:
    1. patient.portal_profile
    2. PatientProfile.connected_patient_record
    3. PatientProfile with matching email or phone
    """
    from patient.models import PatientProfile, PatientNotification
    if not patient:
        return None

    profile = getattr(patient, 'portal_profile', None)
    if not profile:
        profile = PatientProfile.objects.filter(connected_patient_record=patient).first()
    if not profile and patient.email:
        profile = PatientProfile.objects.filter(
            Q(user__email__iexact=patient.email) | Q(parent_guardian_email__iexact=patient.email)
        ).first()
    if not profile and patient.phone:
        profile = PatientProfile.objects.filter(phone_number=patient.phone).first()

    if profile:
        return PatientNotification.objects.create(
            patient=profile,
            notification_type=notification_type,
            title=title,
            message=message,
            link_url=link_url
        )
    return None


# ----------------- PUBLIC LANDING & AUTHENTICATION -----------------

def landing_view(request):
    """
    Root / Landing view: The Login Page IS the landing page!
    If doctor or patient is already logged in, automatically redirect straight to their dashboard.
    Never show the login page to an already logged-in user!
    """
    if request.user.is_authenticated:
        if hasattr(request.user, 'doctor_profile'):
            return redirect('doctor:dashboard')
        return redirect('patient:dashboard')
    
    from patient.views import patient_login_view
    return patient_login_view(request)


def doctor_login_view(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'doctor_profile'):
            return redirect('doctor:dashboard')
        return redirect('patient:dashboard')

    form = DoctorLoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        password = form.cleaned_data['password']

        # Try finding user by email or username
        user_obj = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).first()
        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
            if user is not None:
                if hasattr(user, 'doctor_profile'):
                    login(request, user)
                    request.session.set_expiry(60 * 60 * 24 * 90)  # Keep logged in for 90 days
                    messages.success(request, f"Welcome back, Dr. {user.doctor_profile.full_name}!")
                    next_url = request.GET.get('next')
                    return redirect(next_url or 'doctor:dashboard')
                elif hasattr(user, 'patient_profile'):
                    login(request, user)
                    request.session.set_expiry(60 * 60 * 24 * 90)  # Keep logged in for 90 days
                    messages.success(request, f"Welcome back, {user.patient_profile.full_name}!")
                    return redirect('patient:dashboard')
                else:
                    messages.error(request, "This account is not registered as a doctor profile.")
            else:
                messages.error(request, "Invalid password. Please try again.")
        else:
            messages.error(request, "No doctor account found with this email.")

    return render(request, 'doctor/auth/login.html', {'form': form})


def doctor_register_view(request):
    if request.user.is_authenticated and hasattr(request.user, 'doctor_profile'):
        return redirect('doctor:dashboard')

    form = DoctorRegistrationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        password = form.cleaned_data['password']
        full_name = form.cleaned_data['full_name']
        phone_number = form.cleaned_data['phone_number']
        dental_qualification = form.cleaned_data['dental_qualification']
        clinic_name = form.cleaned_data['clinic_name']
        clinic_address = form.cleaned_data['clinic_address']
        profile_picture = form.cleaned_data.get('profile_picture')

        # Create auth user
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=full_name.split()[0] if full_name else '',
            last_name=' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else ''
        )

        # Create doctor profile
        doctor = DoctorProfile.objects.create(
            user=user,
            full_name=full_name,
            phone_number=phone_number,
            dental_qualification=dental_qualification,
            clinic_name=clinic_name,
            clinic_address=clinic_address,
            profile_picture=profile_picture
        )

        # Welcome notification
        Notification.objects.create(
            doctor=doctor,
            notification_type='GENERAL' if False else 'PROGRESS',
            title='Welcome to PEDO ALIGN Doctor Portal!',
            message=f'Your doctor profile for {clinic_name} has been successfully created. Start by adding your first patient.'
        )

        login(request, user)
        request.session.set_expiry(60 * 60 * 24 * 90)  # Persistent login for 90 days
        messages.success(request, f"Registration successful! Welcome to PEDO ALIGN, Dr. {doctor.full_name}.")
        return redirect('doctor:dashboard')

    return render(request, 'doctor/auth/register.html', {'form': form})


def doctor_logout_view(request):
    logout(request)
    messages.info(request, "You have been safely logged out of PEDO ALIGN.")
    return redirect('doctor:login')


def doctor_forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        user_obj = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).first()
        if user_obj and hasattr(user_obj, 'doctor_profile'):
            messages.success(request, f"Password reset instructions have been dispatched to {email}. (Development mode: you can reset directly below).")
            return redirect('doctor:reset_password')
        else:
            messages.error(request, "No doctor account found with that email address.")
    return render(request, 'doctor/auth/forgot_password.html')


def doctor_reset_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not new_password or len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, 'doctor/auth/reset_password.html', {'email': email})

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'doctor/auth/reset_password.html', {'email': email})

        user_obj = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).first()
        if user_obj:
            user_obj.set_password(new_password)
            user_obj.save()
            messages.success(request, "Your password has been successfully reset. Please log in with your new password.")
            return redirect('doctor:login')
        else:
            messages.error(request, "Account not found.")

    return render(request, 'doctor/auth/reset_password.html')


# ----------------- DOCTOR DASHBOARD -----------------

@login_required
def dashboard_view(request):
    if hasattr(request.user, 'patient_profile'):
        return redirect('patient:dashboard')
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        messages.error(request, "Doctor profile required.")
        return redirect('doctor:login')

    # Strict doctor isolation
    patients_qs = Patient.objects.filter(doctor=doctor)
    total_patients = patients_qs.count()
    active_patients = patients_qs.filter(treatment_status='ACTIVE', is_archived=False).count()
    completed_treatments = patients_qs.filter(treatment_status='COMPLETED').count()

    pending_approvals = PatientJoiningCode.objects.filter(
        doctor=doctor, status='PENDING_APPROVAL'
    ).count()

    pending_photo_reviews = PhotoMonitoring.objects.filter(
        patient__doctor=doctor, tracking_status='PENDING_REVIEW'
    ).count()

    archived_patients_count = patients_qs.filter(is_archived=True).count()

    today = timezone.localdate()
    upcoming_appointments_qs = Appointment.objects.filter(
        doctor=doctor,
        scheduled_date__gte=today,
        status='UPCOMING'
    ).order_by('scheduled_date', 'scheduled_time')
    upcoming_appointments_count = upcoming_appointments_qs.count()

    # Recent lists
    recent_patients = patients_qs.filter(is_archived=False).order_by('-created_at')[:5]
    recent_activities = PatientActivityLog.objects.filter(doctor=doctor).order_by('-created_at')[:6]
    upcoming_appointments_list = upcoming_appointments_qs[:5]
    pending_photos_list = PhotoMonitoring.objects.filter(
        patient__doctor=doctor, tracking_status='PENDING_REVIEW'
    ).select_related('patient').order_by('-upload_date')[:4]
    archived_patients_list = patients_qs.filter(is_archived=True).order_by('-archived_at')[:4]

    # Chart data
    # 1. Patient status breakdown
    status_counts = {
        'Active': active_patients,
        'Pending Connection': patients_qs.filter(treatment_status='PENDING_CONNECTION', is_archived=False).count(),
        'On Hold': patients_qs.filter(treatment_status='ON_HOLD', is_archived=False).count(),
        'Completed': completed_treatments,
    }

    # 2. Compliance distribution
    plans = TreatmentPlan.objects.filter(patient__doctor=doctor)
    high_compliance = plans.filter(compliance_score__gte=85).count()
    medium_compliance = plans.filter(compliance_score__gte=70, compliance_score__lt=85).count()
    low_compliance = plans.filter(compliance_score__lt=70).count()

    context = {
        'doctor': doctor,
        'total_patients': total_patients,
        'active_patients': active_patients,
        'active_treatments': active_patients,
        'completed_treatments': completed_treatments,
        'pending_approvals': pending_approvals,
        'pending_photo_reviews': pending_photo_reviews,
        'archived_patients_count': archived_patients_count,
        'upcoming_appointments_count': upcoming_appointments_count,
        'recent_patients': recent_patients,
        'recent_activities': recent_activities,
        'upcoming_appointments_list': upcoming_appointments_list,
        'pending_photos_list': pending_photos_list,
        'archived_patients_list': archived_patients_list,
        'status_counts_json': json.dumps(status_counts),
        'compliance_data_json': json.dumps({
            'Excellent (>85%)': high_compliance,
            'Good (70-84%)': medium_compliance,
            'Needs Attention (<70%)': low_compliance,
        }),
    }
    return render(request, 'doctor/dashboard.html', context)


# ----------------- PATIENT MANAGEMENT -----------------

@login_required
def patient_list_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patients_qs = Patient.objects.filter(doctor=doctor)

    # Search query
    query = request.GET.get('q', '').strip()
    if query:
        patients_qs = patients_qs.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(patient_id__icontains=query) |
            Q(phone__icontains=query) |
            Q(email__icontains=query) |
            Q(joining_code__code__icontains=query)
        ).distinct()

    # Filter status
    status_filter = request.GET.get('status', 'ALL')
    archived_count = Patient.objects.filter(doctor=doctor, is_archived=True).count()
    active_count = Patient.objects.filter(doctor=doctor, is_archived=False).count()
    lifetime_count = Patient.objects.filter(doctor=doctor).count()

    if status_filter == 'ARCHIVED':
        patients_qs = patients_qs.filter(is_archived=True)
    elif status_filter != 'ALL' and status_filter in dict(Patient.STATUS_CHOICES):
        patients_qs = patients_qs.filter(treatment_status=status_filter, is_archived=False)
    else:
        patients_qs = patients_qs.filter(is_archived=False)

    # View style: table or grid
    view_mode = request.GET.get('view', 'grid')

    context = {
        'doctor': doctor,
        'patients': patients_qs,
        'query': query,
        'status_filter': status_filter,
        'view_mode': view_mode,
        'total_count': active_count,
        'lifetime_count': lifetime_count,
        'archived_count': archived_count,
        'status_choices': Patient.STATUS_CHOICES,
    }
    return render(request, 'doctor/patients/patient_list.html', context)


@login_required
def patient_create_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    form = PatientForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        patient = form.save(commit=False)
        patient.doctor = doctor

        # Auto-generate unique Patient ID e.g. PA-PT-2026-001
        count = Patient.objects.count() + 1
        patient.patient_id = f"PA-PT-{timezone.now().year}-{count:04d}"
        patient.treatment_status = 'PENDING_CONNECTION'
        patient.save()

        # Generate unique Joining Code (expires in 14 days)
        code_obj = PatientJoiningCode.objects.create(
            patient=patient,
            doctor=doctor,
            code=generate_joining_code(),
            status='ACTIVE',
            expires_at=timezone.now() + timezone.timedelta(days=14)
        )

        # Initialize Default Clinical Record with entered medical/dental history
        med_history = form.cleaned_data.get('medical_history', '')
        dent_history = form.cleaned_data.get('dental_history', '')
        ClinicalRecord.objects.create(
            patient=patient,
            medical_history=med_history,
            dental_history=dent_history,
            teeth_present='Complete Mixed Dentition',
            molar_relationship='Class I',
            canine_relationship='Class I',
            overbite='Normal (2-3mm)',
            deep_bite='None',
            crossbite='None',
            oral_habits='None'
        )

        # Initialize Default Treatment Plan
        TreatmentPlan.objects.create(
            patient=patient,
            estimated_duration_months=patient.treatment_duration_months or 12,
            total_aligners=int((patient.treatment_duration_months or 12) * 2),
            current_aligner=1,
            aligner_frequency_days=10,
            status='Planning',
            compliance_score=95
        )

        # Optional 20-Day Follow-up scheduling workflow
        if form.cleaned_data.get('schedule_20day_followup'):
            custom_date = form.cleaned_data.get('custom_followup_date')
            followup_date = custom_date if custom_date else (timezone.localdate() + timezone.timedelta(days=20))
            appt_time = timezone.datetime.strptime('10:00', '%H:%M').time()
            appt_instructions = f"Initial 20-Day clinical follow-up examination & treatment assessment with Dr. {doctor.full_name} at {doctor.clinic_name}."

            Appointment.objects.create(
                doctor=doctor,
                patient=patient,
                appointment_type='ROUTINE_CHECKUP',
                scheduled_date=followup_date,
                scheduled_time=appt_time,
                instructions=appt_instructions,
                status='UPCOMING'
            )

            Notification.objects.create(
                doctor=doctor,
                patient=patient,
                notification_type='APPOINTMENT',
                title=f"20-Day Follow-Up Booked: {patient.full_name}",
                message=f"Follow-up visit set for {followup_date} at 10:00 AM."
            )

        # Activity log
        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Patient Enrolled',
            description=f"Patient {patient.full_name} enrolled. Joining code {code_obj.code} generated."
        )

        messages.success(
            request,
            f"Patient {patient.full_name} registered successfully! Unique Joining Code: {code_obj.code}"
        )
        return redirect('doctor:patient_detail', patient_id=patient.id)

    return render(request, 'doctor/patients/patient_create.html', {
        'form': form,
        'doctor': doctor,
        'default_20day_date': (timezone.localdate() + timezone.timedelta(days=20)).isoformat(),
    })


@login_required
def patient_detail_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    # Strict isolation: doctor can ONLY access their own patient
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    active_tab = request.GET.get('tab', 'overview')

    # Ensure related models exist
    clinical_record, _ = ClinicalRecord.objects.get_or_create(patient=patient)
    treatment_plan, _ = TreatmentPlan.objects.get_or_create(patient=patient)
    joining_code = getattr(patient, 'joining_code', None)

    # Preoperative photos
    preop_photos = patient.preoperative_photos.all()

    # Radiographs (Type 1 and Type 2)
    radiographs_type1 = patient.radiographs.filter(radiograph_type='TYPE_1')
    radiographs_type2 = patient.radiographs.filter(radiograph_type='TYPE_2')
    all_radiographs = patient.radiographs.all()

    # Treatment / Operation records
    operation_records = patient.operation_records.all()

    # Prescriptions
    prescriptions = patient.prescriptions.all()

    # Turn Quest stages
    treatment_turns = patient.treatment_turns.all()

    # Doctor Treatment Media
    current_media = patient.treatment_media.filter(is_current=True).first()
    media_history = patient.treatment_media.all()

    # Monthly Treatment Notes
    monthly_notes = patient.monthly_notes.all()

    # 12-Stage Visual Treatment Timeline
    timeline_stages = patient.get_timeline_stages()

    # Photos
    photo_uploads = PhotoMonitoring.objects.filter(patient=patient).order_by('-upload_date')
    before_photos = photo_uploads.filter(is_before_sample=True)
    after_photos = photo_uploads.filter(is_after_sample=True)

    # Appointments
    appointments = Appointment.objects.filter(patient=patient).order_by('-scheduled_date')

    # Emergency Alerts
    emergencies = EmergencyAlert.objects.filter(patient=patient).order_by('-reported_at')

    # Activity logs
    activity_logs = PatientActivityLog.objects.filter(patient=patient).order_by('-created_at')

    # Modal Forms
    preop_form = PreoperativePhotoForm()
    radiograph_form = RadiographRecordForm(initial={'examination_date': timezone.localdate()})
    operation_form = TreatmentOperationRecordForm(initial={'record_date': timezone.now().strftime('%Y-%m-%dT%H:%M')})
    prescription_form = PrescriptionForm(initial={
        'prescription_date': timezone.localdate(),
        'next_followup_date': timezone.localdate() + timezone.timedelta(days=20)
    })
    turn_form = TreatmentTurnForm(initial={
        'turn_number': treatment_turns.count() + 1,
        'start_date': timezone.localdate()
    })
    media_form = DoctorTreatmentMediaForm()
    monthly_note_form = MonthlyTreatmentNoteForm(initial={
        'month_number': patient.calculate_current_treatment_month(),
        'note_date': timezone.localdate()
    })
    archive_form = ArchivePatientForm()

    context = {
        'doctor': doctor,
        'patient': patient,
        'clinical_record': clinical_record,
        'treatment_plan': treatment_plan,
        'joining_code': joining_code,
        'preop_photos': preop_photos,
        'radiographs_type1': radiographs_type1,
        'radiographs_type2': radiographs_type2,
        'all_radiographs': all_radiographs,
        'operation_records': operation_records,
        'prescriptions': prescriptions,
        'treatment_turns': treatment_turns,
        'current_media': current_media,
        'media_history': media_history,
        'monthly_notes': monthly_notes,
        'timeline_stages': timeline_stages,
        'photo_uploads': photo_uploads,
        'before_photos': before_photos,
        'after_photos': after_photos,
        'appointments': appointments,
        'emergencies': emergencies,
        'activity_logs': activity_logs,
        'active_tab': active_tab,
        'preop_form': preop_form,
        'radiograph_form': radiograph_form,
        'operation_form': operation_form,
        'prescription_form': prescription_form,
        'turn_form': turn_form,
        'media_form': media_form,
        'monthly_note_form': monthly_note_form,
        'archive_form': archive_form,
        'default_20day_date': (timezone.localdate() + timezone.timedelta(days=20)).isoformat(),
    }
    return render(request, 'doctor/patients/patient_detail.html', context)


# --- CLINICAL ACTION VIEWS ---

@login_required
def preop_photo_upload_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        files = request.FILES.getlist('photos')
        if not files and 'photo' in request.FILES:
            files = [request.FILES['photo']]

        title = request.POST.get('title', 'Preoperative Dental View') or 'Preoperative Dental View'
        description = request.POST.get('description', '')

        count = 0
        for f in files:
            PreoperativePhoto.objects.create(
                patient=patient,
                photo=f,
                title=title,
                description=description
            )
            count += 1

        if count > 0:
            PatientActivityLog.objects.create(
                patient=patient,
                doctor=doctor,
                activity_type='Preoperative Photos Uploaded',
                description=f"{count} preoperative photograph(s) uploaded by Dr. {doctor.full_name}."
            )
            messages.success(request, f"{count} Preoperative photograph(s) permanently saved in patient clinical record.")
        else:
            messages.error(request, "No photos were selected for upload.")

    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=preop_photos")


@login_required
def preop_photo_delete_view(request, patient_id, photo_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    photo = get_object_or_404(PreoperativePhoto, id=photo_id, patient=patient)
    photo.delete()
    messages.success(request, "Preoperative photograph removed.")
    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=preop_photos")


@login_required
def radiograph_upload_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        form = RadiographRecordForm(request.POST, request.FILES)
        if form.is_valid():
            radio = form.save(commit=False)
            radio.patient = patient
            prev_count = RadiographRecord.objects.filter(
                patient=patient, radiograph_type=radio.radiograph_type
            ).count()
            radio.version = prev_count + 1
            radio.save()

            PatientActivityLog.objects.create(
                patient=patient,
                doctor=doctor,
                activity_type='Radiograph Uploaded',
                description=f"{radio.get_radiograph_type_display()} (v{radio.version}) uploaded: {radio.title}"
            )
            messages.success(request, f"{radio.get_radiograph_type_display()} (v{radio.version}) successfully uploaded.")
        else:
            messages.error(request, "Please check radiograph upload form errors.")

    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=radiographs")


@login_required
def radiograph_delete_view(request, patient_id, radio_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    radio = get_object_or_404(RadiographRecord, id=radio_id, patient=patient)
    radio.delete()
    messages.success(request, "Radiograph record removed.")
    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=radiographs")


@login_required
def operation_record_create_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        form = TreatmentOperationRecordForm(request.POST)
        if form.is_valid():
            op = form.save(commit=False)
            op.patient = patient
            op.doctor = doctor
            op.save()

            PatientActivityLog.objects.create(
                patient=patient,
                doctor=doctor,
                activity_type='Operation / Treatment Recorded',
                description=f"Treatment procedure recorded: {op.operation_performed}"
            )
            messages.success(request, f"Treatment & Operation record for '{op.operation_performed}' saved successfully.")
        else:
            messages.error(request, "Please correct errors in the treatment operation form.")

    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=operations")


@login_required
def prescription_create_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            presc = form.save(commit=False)
            presc.patient = patient
            presc.doctor = doctor
            presc.save()

            # Automatic notification to patient
            if hasattr(patient, 'portal_profile') and patient.portal_profile:
                PatientNotification.objects.create(
                    patient=patient.portal_profile,
                    notification_type='PRESCRIPTION',
                    title='New Digital Prescription Issued',
                    message=f"Dr. {doctor.full_name} ({doctor.clinic_name}) has generated a digital prescription dated {presc.prescription_date}. You can view and download it now.",
                    link_url=reverse('patient:my_treatment')
                )

            PatientActivityLog.objects.create(
                patient=patient,
                doctor=doctor,
                activity_type='Prescription Generated',
                description=f"Prescription #{presc.id} generated by Dr. {doctor.full_name}."
            )
            messages.success(request, f"Prescription #{presc.id} created successfully.")
            return redirect('doctor:prescription_detail', patient_id=patient.id, presc_id=presc.id)
        else:
            messages.error(request, "Please check the prescription form fields.")

    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=prescriptions")


@login_required
def prescription_detail_view(request, patient_id, presc_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    prescription = get_object_or_404(Prescription, id=presc_id, patient=patient)

    context = {
        'doctor': doctor,
        'patient': patient,
        'prescription': prescription,
    }
    return render(request, 'doctor/prescriptions/prescription_detail.html', context)


@login_required
def prescription_print_view(request, patient_id, presc_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    prescription = get_object_or_404(Prescription, id=presc_id, patient=patient)

    context = {
        'doctor': doctor,
        'patient': patient,
        'prescription': prescription,
    }
    return render(request, 'doctor/prescriptions/prescription_print.html', context)


@login_required
def treatment_duration_update_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        duration_months = request.POST.get('treatment_duration_months')
        start_date = request.POST.get('treatment_start_date')
        status = request.POST.get('treatment_status')

        if duration_months:
            try:
                patient.treatment_duration_months = int(duration_months)
            except ValueError:
                pass
        if start_date:
            patient.treatment_start_date = start_date
        if status:
            patient.treatment_status = status
        patient.save()

        # Update TreatmentPlan
        plan, _ = TreatmentPlan.objects.get_or_create(patient=patient)
        plan.estimated_duration_months = patient.treatment_duration_months
        if start_date:
            plan.start_date = start_date
            from datetime import datetime
            try:
                s_date = datetime.strptime(str(start_date), '%Y-%m-%d').date()
                plan.expected_completion_date = s_date + timezone.timedelta(days=int(patient.treatment_duration_months * 30))
            except Exception:
                pass
        plan.save()

        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Treatment Duration Updated',
            description=f"Duration set to {patient.treatment_duration_months} months. Status: {patient.get_treatment_status_display()}."
        )
        messages.success(request, f"Treatment duration and schedule updated to {patient.treatment_duration_months} months.")

    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=duration")


@login_required
def monthly_note_create_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        form = MonthlyTreatmentNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.patient = patient
            note.save()

            PatientActivityLog.objects.create(
                patient=patient,
                doctor=doctor,
                activity_type='Monthly Note Recorded',
                description=f"Month #{note.month_number} evaluation: {note.status_update}"
            )
            messages.success(request, f"Month #{note.month_number} treatment evaluation note recorded.")
        else:
            messages.error(request, "Please check errors in the monthly note form.")

    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=duration")


@login_required
def turn_quest_create_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        form = TreatmentTurnForm(request.POST)
        if form.is_valid():
            turn = form.save(commit=False)
            turn.patient = patient
            turn.save()

            # Automatic notification to patient
            if hasattr(patient, 'portal_profile') and patient.portal_profile:
                PatientNotification.objects.create(
                    patient=patient.portal_profile,
                    notification_type='TREATMENT_UPDATE',
                    title=f"Turn #{turn.turn_number} Prescribed",
                    message=f"Dr. {doctor.full_name} has updated your treatment turn #{turn.turn_number} ({turn.get_status_display()}). Instructions: {turn.instructions or 'Follow prescribed aligner sequence'}.",
                    link_url=reverse('patient:my_treatment')
                )

            PatientActivityLog.objects.create(
                patient=patient,
                doctor=doctor,
                activity_type='Turn Quest Stage Added',
                description=f"Turn #{turn.turn_number} added with status: {turn.get_status_display()}."
            )
            messages.success(request, f"Turn #{turn.turn_number} added to treatment sequence.")
        else:
            messages.error(request, "Please check the turn quest form.")

    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=turn_quest")


@login_required
def turn_quest_update_view(request, patient_id, turn_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    turn = get_object_or_404(TreatmentTurn, id=turn_id, patient=patient)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        doctor_remarks = request.POST.get('doctor_remarks')
        completion_date = request.POST.get('completion_date')
        instructions = request.POST.get('instructions')
        next_turn_date = request.POST.get('next_turn_date')

        if new_status:
            turn.status = new_status
        if doctor_remarks is not None:
            turn.doctor_remarks = doctor_remarks
        if instructions is not None:
            turn.instructions = instructions
        if completion_date:
            turn.completion_date = completion_date
        if next_turn_date:
            turn.next_turn_date = next_turn_date
        turn.save()

        messages.success(request, f"Turn #{turn.turn_number} updated to {turn.get_status_display()}.")

    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=turn_quest")


@login_required
def treatment_media_upload_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        form = DoctorTreatmentMediaForm(request.POST, request.FILES)
        if form.is_valid():
            patient.treatment_media.filter(is_current=True).update(is_current=False)

            media = form.save(commit=False)
            media.patient = patient
            media.doctor = doctor
            prev_count = patient.treatment_media.count()
            media.version = prev_count + 1
            media.is_current = True
            media.save()

            notify_patient_profile(
                patient=patient,
                notification_type='DOCTOR_INSTRUCTION',
                title="New Clinical Media & Demonstration Uploaded",
                message=f"Dr. {doctor.display_name} has shared treatment demonstration media/instructions for {media.treatment_stage}.",
                link_url='/patient/#step4Section'
            )

            PatientActivityLog.objects.create(
                patient=patient,
                doctor=doctor,
                activity_type='Treatment Media Uploaded',
                description=f"Treatment video & photograph (v{media.version}) uploaded for stage: {media.treatment_stage}."
            )
            messages.success(request, f"Treatment video & photograph (v{media.version}) successfully published to patient timeline.")
        else:
            messages.error(request, "Please check the treatment media form.")

    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=doctor_media")


@login_required
def schedule_20day_followup_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        followup_date_str = request.POST.get('followup_date')
        if followup_date_str:
            from datetime import datetime
            followup_date = datetime.strptime(followup_date_str, '%Y-%m-%d').date()
        else:
            followup_date = timezone.localdate() + timezone.timedelta(days=20)

        time_str = request.POST.get('followup_time', '10:00')
        try:
            from datetime import datetime
            appt_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            appt_time = timezone.datetime.strptime('10:00', '%H:%M').time()

        instructions = request.POST.get('instructions') or (
            f"20-Day clinical follow-up examination & progress review with Dr. {doctor.full_name} at {doctor.clinic_name}."
        )

        Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            appointment_type='ROUTINE_CHECKUP',
            scheduled_date=followup_date,
            scheduled_time=appt_time,
            instructions=instructions,
            status='UPCOMING'
        )

        Notification.objects.create(
            doctor=doctor,
            patient=patient,
            notification_type='APPOINTMENT',
            title=f"20-Day Follow-Up Booked: {patient.full_name}",
            message=f"Appointment on {followup_date} at {appt_time.strftime('%I:%M %p')} for {patient.full_name}."
        )

        if hasattr(patient, 'portal_profile') and patient.portal_profile:
            PatientNotification.objects.create(
                patient=patient.portal_profile,
                notification_type='APPOINTMENT',
                title="Upcoming Appointment: 20-Day Clinical Follow-Up",
                message=f"Doctor Name: Dr. {doctor.full_name}\nClinic: {doctor.clinic_name}\nDate: {followup_date.strftime('%b %d, %Y')}\nTime: {appt_time.strftime('%I:%M %p')}\nInstructions: {instructions}",
                link_url=reverse('patient:appointments')
            )

        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Appointment Scheduled',
            description=f"20-Day follow-up scheduled for {followup_date} at {appt_time.strftime('%I:%M %p')}."
        )
        messages.success(request, f"20-Day follow-up appointment scheduled for {followup_date.strftime('%b %d, %Y')} at {appt_time.strftime('%I:%M %p')}. Notification dispatched to patient.")

    return redirect(f"{reverse('doctor:patient_detail', kwargs={'patient_id': patient.id})}?tab=appointments")


@login_required
def delete_patient_account_view(request, patient_id):
    """
    Deletes the patient account following treatment completion:
    - Permanently deactivates and archives the patient record.
    - Sets patient user credentials to inactive so patient can never log in.
    - Expires all joining codes.
    - Preserves all clinical history (pre-op photos, radiographs, prescriptions, notes, aligners)
      in the Doctor Portal under Archived Patients and in lifetime monitored patient counts.
    """
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip() or 'Treatment completed - Patient account closed'

        # 1. Soft-delete / Archive Patient Record with Completed Status
        patient.is_deactivated = True
        patient.is_archived = True
        patient.treatment_status = 'COMPLETED'
        patient.deactivated_at = timezone.now()
        patient.archived_at = timezone.now()
        patient.deactivation_reason = reason
        patient.archived_reason = reason
        patient.save()

        # 2. Deactivate linked User credentials so patient cannot log in
        if hasattr(patient, 'portal_profile') and patient.portal_profile:
            prof = patient.portal_profile
            prof.connection_status = 'DISCONNECTED'
            prof.save()
            if prof.user:
                prof.user.is_active = False
                prof.user.save()

        if patient.email:
            for u in User.objects.filter(email__iexact=patient.email):
                if not hasattr(u, 'doctor_profile'):
                    u.is_active = False
                    u.save()

        # 3. Expire any joining codes
        PatientJoiningCode.objects.filter(patient=patient).update(status='EXPIRED')

        # 4. Record Activity Log for doctor's monitoring history
        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Patient Account Deleted / Treatment Completed',
            description=f"Patient account for {patient.full_name} ({patient.patient_id}) deleted following treatment completion. Login credentials disabled. Complete clinical history retained for doctor monitoring statistics. Notes: {reason}"
        )

        messages.warning(
            request, 
            f"Patient account for {patient.full_name} ({patient.patient_id}) has been deleted. The patient can no longer log in. Complete clinical history remains preserved under Archived Patients."
        )
        return redirect('doctor:patient_list')

    return redirect('doctor:patient_detail', patient_id=patient.id)


@login_required
def archive_patient_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        action_type = request.POST.get('action_type', 'DEACTIVATE')
        reason = request.POST.get('reason', '').strip()

        if action_type == 'COMPLETE':
            patient.treatment_status = 'COMPLETED'
            patient.is_archived = False
            patient.is_deactivated = False
            patient.notes = f"{patient.notes or ''}\n[Treatment Completed on {timezone.localdate()}]: {reason}".strip()
            patient.save()

            PatientActivityLog.objects.create(
                patient=patient,
                doctor=doctor,
                activity_type='Treatment Completed',
                description=f"Treatment marked as COMPLETED. Patient account remains active for permitted history. Notes: {reason}"
            )
            messages.success(request, f"Treatment for {patient.full_name} marked as COMPLETED. Clinical history preserved.")

        else: # DEACTIVATE
            patient.is_deactivated = True
            patient.is_archived = True
            patient.deactivated_at = timezone.now()
            patient.archived_at = timezone.now()
            patient.deactivation_reason = reason
            patient.archived_reason = reason
            patient.save()

            if hasattr(patient, 'portal_profile') and patient.portal_profile:
                prof = patient.portal_profile
                if prof.user:
                    prof.user.is_active = False
                    prof.user.save()

            PatientActivityLog.objects.create(
                patient=patient,
                doctor=doctor,
                activity_type='Patient Deactivated / Archived',
                description=f"Patient deactivated (soft-deleted/archived). Login access blocked. Reason: {reason}"
            )
            messages.warning(request, f"Patient {patient.full_name} has been deactivated and archived. Clinical records remain safely accessible under Archived Patients.")
            return redirect('doctor:archived_patients')

    return redirect('doctor:patient_detail', patient_id=patient.id)


@login_required
def restore_patient_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    if request.method == 'POST':
        patient.is_deactivated = False
        patient.is_archived = False
        patient.save()

        if hasattr(patient, 'portal_profile') and patient.portal_profile:
            prof = patient.portal_profile
            if prof.user:
                prof.user.is_active = True
                prof.user.save()

        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Patient Restored',
            description=f"Patient {patient.full_name} restored from archive to active care."
        )
        messages.success(request, f"Patient {patient.full_name} restored to active clinical care.")

    return redirect('doctor:patient_detail', patient_id=patient.id)


@login_required
def archived_patients_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    search_query = request.GET.get('q', '').strip()
    qs = Patient.objects.filter(doctor=doctor, is_archived=True).order_by('-archived_at', '-updated_at')

    if search_query:
        qs = qs.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(patient_id__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(deactivation_reason__icontains=search_query)
        )

    context = {
        'doctor': doctor,
        'archived_patients': qs,
        'archived_count': qs.count(),
        'search_query': search_query,
    }
    return render(request, 'doctor/patients/archived_patients.html', context)


@login_required
def patient_edit_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    form = PatientEditForm(request.POST or None, request.FILES or None, instance=patient)

    if request.method == 'POST' and form.is_valid():
        form.save()
        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Patient Details Updated',
            description="Doctor updated patient personal and treatment parameters."
        )
        messages.success(request, f"Patient record for {patient.full_name} updated successfully.")
        return redirect('doctor:patient_detail', patient_id=patient.id)

    return render(request, 'doctor/patients/patient_edit.html', {'form': form, 'patient': patient, 'doctor': doctor})


@login_required
def patient_delete_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    if request.method == 'POST':
        name = patient.full_name
        patient.delete()
        messages.success(request, f"Patient record for {name} has been removed.")
        return redirect('doctor:patient_list')

    return render(request, 'doctor/patients/patient_confirm_delete.html', {'patient': patient, 'doctor': doctor})


# ----------------- UNIQUE PATIENT JOINING CODE SYSTEM -----------------

@login_required
def patient_requests_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    # All codes generated by this doctor
    codes_qs = PatientJoiningCode.objects.filter(doctor=doctor)

    status_filter = request.GET.get('status', 'ALL')
    if status_filter != 'ALL':
        codes_qs = codes_qs.filter(status=status_filter)

    pending_count = PatientJoiningCode.objects.filter(doctor=doctor, status='PENDING_APPROVAL').count()
    active_count = PatientJoiningCode.objects.filter(doctor=doctor, status='ACTIVE').count()
    approved_count = PatientJoiningCode.objects.filter(doctor=doctor, status='APPROVED').count()

    context = {
        'doctor': doctor,
        'codes': codes_qs,
        'status_filter': status_filter,
        'pending_count': pending_count,
        'active_count': active_count,
        'approved_count': approved_count,
    }
    return render(request, 'doctor/requests/patient_requests.html', context)


@login_required
def approve_patient_request_view(request, code_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    code_obj = get_object_or_404(PatientJoiningCode, id=code_id, doctor=doctor)

    if request.method == 'POST':
        code_obj.status = 'APPROVED'
        code_obj.approved_at = timezone.now()
        code_obj.save()

        # Update patient status to ACTIVE
        patient = code_obj.patient
        patient.treatment_status = 'ACTIVE'
        if not patient.treatment_start_date:
            patient.treatment_start_date = timezone.localdate()
        patient.save()

        # Update Treatment Plan status
        treatment_plan, _ = TreatmentPlan.objects.get_or_create(patient=patient)
        treatment_plan.status = 'Active / In Progress'
        if not treatment_plan.start_date:
            treatment_plan.start_date = timezone.localdate()
        treatment_plan.save()

        # Activity log & Notification
        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Connection Approved',
            description=f"Doctor approved connection request for patient {patient.full_name}. Treatment status is now ACTIVE."
        )

        Notification.objects.create(
            doctor=doctor,
            patient=patient,
            notification_type='PATIENT_REQUEST',
            title='Patient Connected!',
            message=f"You approved connection for {patient.full_name}. Aligner monitoring is now active."
        )

        # Also connect any PatientProfile waiting on this joining code
        try:
            from patient.models import PatientProfile, PatientNotification
            profiles_to_link = set(code_obj.requesting_patient_profiles.all())
            
            if patient.email:
                for ep in PatientProfile.objects.filter(user__email__iexact=patient.email):
                    profiles_to_link.add(ep)
            
            for pp in PatientProfile.objects.filter(pending_code=code_obj):
                profiles_to_link.add(pp)

            for p_profile in profiles_to_link:
                p_profile.connected_patient_record = patient
                p_profile.pending_code = code_obj
                p_profile.connection_status = 'CONNECTED'
                p_profile.save()
                PatientNotification.objects.create(
                    patient=p_profile,
                    notification_type='TREATMENT_UPDATE',
                    title='Doctor Approved Connection!',
                    message=f'Dr. {doctor.full_name} has approved your connection request. Your treatment plan and photo tracking are now active!'
                )
        except Exception:
            pass

        messages.success(request, f"Patient request approved! {patient.full_name} is now connected as an Active Treatment patient.")

    return redirect('doctor:patient_requests')


@login_required
def reject_patient_request_view(request, code_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    code_obj = get_object_or_404(PatientJoiningCode, id=code_id, doctor=doctor)
    if request.method == 'POST':
        code_obj.status = 'REJECTED'
        code_obj.save()

        PatientActivityLog.objects.create(
            patient=code_obj.patient,
            doctor=doctor,
            activity_type='Connection Rejected',
            description=f"Connection request for {code_obj.patient.full_name} was rejected by doctor."
        )

        try:
            from patient.models import PatientNotification
            for p_profile in code_obj.requesting_patient_profiles.all():
                p_profile.connection_status = 'REJECTED'
                p_profile.save()
                PatientNotification.objects.create(
                    patient=p_profile,
                    notification_type='TREATMENT_UPDATE',
                    title='Connection Request Declined',
                    message=f'Your connection request with code {code_obj.code} was declined by the clinic. Please reach out to your doctor for guidance.'
                )
        except Exception:
            pass

        messages.warning(request, f"Connection request for {code_obj.patient.full_name} rejected.")

    return redirect('doctor:patient_requests')


@login_required
def regenerate_joining_code_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    # Get or create code
    code_obj, created = PatientJoiningCode.objects.get_or_create(patient=patient, defaults={'doctor': doctor})
    code_obj.code = generate_joining_code()
    code_obj.status = 'ACTIVE'
    code_obj.created_at = timezone.now()
    code_obj.expires_at = timezone.now() + timezone.timedelta(days=14)
    code_obj.save()

    messages.success(request, f"New Joining Code generated for {patient.full_name}: {code_obj.code} (Valid for 14 days)")
    return redirect('doctor:patient_detail', patient_id=patient.id)


# Public patient joining page
def patient_join_portal_view(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'patient_profile'):
            return redirect('patient:dashboard')
        elif hasattr(request.user, 'doctor_profile'):
            return redirect('doctor:dashboard')

    form = PatientJoinCodeForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        code_str = form.cleaned_data['joining_code'].strip().upper()
        first_name = form.cleaned_data.get('patient_first_name', '').strip()
        last_name = form.cleaned_data.get('patient_last_name', '').strip()
        phone = form.cleaned_data.get('phone', '').strip()
        notes = form.cleaned_data.get('request_notes', '')

        code_obj = PatientJoiningCode.objects.filter(code__iexact=code_str).first()

        if not code_obj:
            form.add_error('joining_code', "Invalid Joining Code. Please double-check the code provided by your orthodontist.")
        elif code_obj.is_expired():
            form.add_error('joining_code', "This joining code has expired. Please contact your doctor for a new code.")
        else:
            clinical_patient = code_obj.patient

            # Update patient record with latest details if provided
            if first_name and not clinical_patient.first_name:
                clinical_patient.first_name = first_name
            if last_name and not clinical_patient.last_name:
                clinical_patient.last_name = last_name
            if phone and not clinical_patient.phone:
                clinical_patient.phone = phone
            clinical_patient.save()

            # Ensure Treatment Plan exists
            if not hasattr(clinical_patient, 'treatment_plan'):
                TreatmentPlan.objects.create(
                    patient=clinical_patient,
                    total_aligners=20,
                    current_aligner=1,
                    aligner_frequency_days=14,
                    status='Active / In Progress'
                )

            # Resolve User and PatientProfile
            user_email = clinical_patient.email or (f"{first_name.lower()}@pedoalign.local" if first_name else f"patient_{clinical_patient.id}@pedoalign.com")
            user = User.objects.filter(Q(email__iexact=user_email) | Q(username__iexact=user_email)).first()
            if not user:
                p_first = clinical_patient.first_name or first_name or user_email.split('@')[0].capitalize()
                p_last = clinical_patient.last_name or last_name or ''
                user = User.objects.create_user(
                    username=user_email,
                    email=user_email,
                    first_name=p_first,
                    last_name=p_last
                )
                user.set_unusable_password()
                user.save()

            from patient.models import PatientProfile
            profile, _ = PatientProfile.objects.get_or_create(
                user=user,
                defaults={
                    'patient_id': 'PA-P' + str(clinical_patient.id).zfill(4),
                    'full_name': clinical_patient.full_name,
                    'phone_number': clinical_patient.phone or phone or '',
                }
            )
            profile.connected_patient_record = clinical_patient
            profile.pending_code = code_obj

            # If already APPROVED by doctor -> Immediately open dashboard!
            if code_obj.status == 'APPROVED':
                profile.connection_status = 'CONNECTED'
                profile.save()
                login(request, user)
                request.session.set_expiry(60 * 60 * 24 * 90)  # Persistent login for 90 days
                messages.success(request, f"Welcome back, {clinical_patient.full_name}! Dr. {code_obj.doctor.full_name} has approved your connection. Your Treatment Dashboard is open!")
                return redirect('patient:dashboard')

            # If ACTIVE (new submission) or PENDING_APPROVAL
            else:
                if code_obj.status != 'PENDING_APPROVAL':
                    code_obj.status = 'PENDING_APPROVAL'
                    code_obj.claimed_at = timezone.now()
                    code_obj.patient_request_notes = notes
                    code_obj.save()

                    Notification.objects.create(
                        doctor=code_obj.doctor,
                        patient=clinical_patient,
                        notification_type='PATIENT_REQUEST',
                        title=f'New Connection Request: {clinical_patient.full_name}',
                        message=f'Patient entered Joining Code {code_obj.code}. Please review and approve their connection.',
                        link_url='/requests/'
                    )

                    PatientActivityLog.objects.create(
                        patient=clinical_patient,
                        doctor=code_obj.doctor,
                        activity_type='Joining Code Entered',
                        description=f"Patient registered joining code {code_obj.code}. Connection request sent to doctor."
                    )

                profile.connection_status = 'PENDING_APPROVAL'
                profile.save()

                login(request, user)
                request.session.set_expiry(60 * 60 * 24 * 90)  # Persistent login for 90 days

                success_info = {
                    'doctor_name': code_obj.doctor.full_name,
                    'clinic_name': code_obj.doctor.clinic_name,
                    'patient_name': clinical_patient.full_name,
                    'code': code_obj.code,
                }
                return render(request, 'doctor/public/join_portal.html', {'form': form, 'success_info': success_info})

    return render(request, 'doctor/public/join_portal.html', {'form': form})


# ----------------- CLINICAL INTAKE FORM -----------------

@login_required
def clinical_records_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    records_qs = ClinicalRecord.objects.filter(patient__doctor=doctor).select_related('patient')

    query = request.GET.get('q', '').strip()
    if query:
        records_qs = records_qs.filter(
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__patient_id__icontains=query) |
            Q(molar_relationship__icontains=query) |
            Q(oral_habits__icontains=query)
        )

    context = {
        'doctor': doctor,
        'records': records_qs,
        'query': query,
    }
    return render(request, 'doctor/clinical/clinical_records_list.html', context)


@login_required
def clinical_record_edit_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    record, _ = ClinicalRecord.objects.get_or_create(patient=patient)

    form = ClinicalRecordForm(request.POST or None, instance=record)
    if request.method == 'POST' and form.is_valid():
        form.save()
        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Clinical Record Updated',
            description="Clinical intake details and skeletal examination updated."
        )
        messages.success(request, f"Clinical examination record for {patient.full_name} saved successfully.")
        return redirect('doctor:patient_detail', patient_id=patient.id)

    return render(request, 'doctor/clinical/clinical_record_edit.html', {
        'form': form,
        'patient': patient,
        'record': record,
        'doctor': doctor
    })


# ----------------- TREATMENT PLAN MANAGEMENT -----------------

@login_required
def treatment_plans_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    plans_qs = TreatmentPlan.objects.filter(patient__doctor=doctor).select_related('patient')
    total_plans_count = plans_qs.count()

    status_filter = request.GET.get('status', 'ALL')
    if status_filter != 'ALL':
        plans_qs = plans_qs.filter(status=status_filter)

    query = request.GET.get('q', '').strip()
    if query:
        plans_qs = plans_qs.filter(
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__patient_id__icontains=query) |
            Q(patient__phone__icontains=query)
        )

    view_mode = request.GET.get('view', 'grid')

    context = {
        'doctor': doctor,
        'plans': plans_qs,
        'status_filter': status_filter,
        'query': query,
        'view_mode': view_mode,
        'total_plans_count': total_plans_count,
        'status_choices': TreatmentPlan.STATUS_CHOICES,
    }
    return render(request, 'doctor/treatment/treatment_plans_list.html', context)


@login_required
def treatment_plan_edit_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    plan, _ = TreatmentPlan.objects.get_or_create(patient=patient)

    old_upper_status = plan.upper_arch_status
    old_upper_notes = plan.upper_arch_notes
    old_lower_status = plan.lower_arch_status
    old_lower_notes = plan.lower_arch_notes
    old_current_aligner = plan.current_aligner

    form = TreatmentPlanForm(request.POST or None, request.FILES or None, instance=plan)
    if request.method == 'POST' and form.is_valid():
        updated_plan = form.save()

        # Upper Arch History snapshot
        if (updated_plan.upper_arch_status != old_upper_status or 
            updated_plan.upper_arch_notes != old_upper_notes or 
            'upper_arch_photo' in request.FILES):
            ArchProgressHistory.objects.create(
                treatment_plan=updated_plan,
                arch='UPPER',
                stage_number=updated_plan.current_aligner,
                status=updated_plan.upper_arch_status,
                notes=updated_plan.upper_arch_notes,
                photo=updated_plan.upper_arch_photo
            )

        # Lower Arch History snapshot
        if (updated_plan.lower_arch_status != old_lower_status or 
            updated_plan.lower_arch_notes != old_lower_notes or 
            'lower_arch_photo' in request.FILES):
            ArchProgressHistory.objects.create(
                treatment_plan=updated_plan,
                arch='LOWER',
                stage_number=updated_plan.current_aligner,
                status=updated_plan.lower_arch_status,
                notes=updated_plan.lower_arch_notes,
                photo=updated_plan.lower_arch_photo
            )

        # Dedicated Tray Management History snapshot
        tray_entry, _ = TrayHistory.objects.get_or_create(
            treatment_plan=updated_plan,
            tray_number=updated_plan.current_aligner,
            defaults={
                'started_on': updated_plan.start_date or timezone.localdate(),
                'doctor_notes': updated_plan.treatment_instructions,
                'status': 'Paused' if updated_plan.is_paused else 'Active'
            }
        )
        if updated_plan.is_paused:
            tray_entry.status = 'Paused'
            tray_entry.doctor_notes = f"[PAUSED: {updated_plan.pause_reason}] {updated_plan.treatment_instructions}"
            tray_entry.save()

        # If aligner reached total, could mark as completed
        if updated_plan.current_aligner >= updated_plan.total_aligners and updated_plan.status == 'Completed':
            patient.treatment_status = 'COMPLETED'
            patient.save()

        # Auto calculate next changing date if missing
        if not updated_plan.next_tray_change_date and updated_plan.start_date:
            from datetime import timedelta
            updated_plan.next_tray_change_date = updated_plan.start_date + timedelta(days=updated_plan.current_aligner * updated_plan.aligner_frequency_days)
            updated_plan.save()

        # Notify Patient
        if hasattr(patient, 'portal_profile') and patient.portal_profile:
            from patient.models import PatientNotification
            PatientNotification.objects.create(
                patient=patient.portal_profile,
                notification_type='TREATMENT_UPDATE',
                title='Treatment Plan & Arch Update',
                message=f'Dr. {doctor.full_name} updated your upper/lower arch prescription and Tray #{updated_plan.current_aligner} schedule.'
            )

        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Treatment Plan Updated',
            description=f"Tray #{updated_plan.current_aligner}/{updated_plan.total_aligners}. Upper Arch: {updated_plan.upper_arch_status}, Lower Arch: {updated_plan.lower_arch_status}."
        )
        messages.success(request, f"Treatment plan for {patient.full_name} updated successfully.")
        return redirect('doctor:patient_detail', patient_id=patient.id)

    upper_history = plan.arch_histories.filter(arch='UPPER')
    lower_history = plan.arch_histories.filter(arch='LOWER')
    tray_history = plan.tray_histories.all()

    return render(request, 'doctor/treatment/treatment_plan_edit.html', {
        'form': form,
        'patient': patient,
        'plan': plan,
        'doctor': doctor,
        'upper_history': upper_history,
        'lower_history': lower_history,
        'tray_history': tray_history,
    })


@login_required
def advance_aligner_stage_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    plan, _ = TreatmentPlan.objects.get_or_create(patient=patient)

    if request.method == 'POST':
        if plan.current_aligner < plan.total_aligners:
            # Mark old tray completed in TrayHistory
            old_tray = TrayHistory.objects.filter(treatment_plan=plan, tray_number=plan.current_aligner).first()
            if old_tray:
                old_tray.completed_on = timezone.localdate()
                old_tray.status = 'Completed'
                old_tray.save()

            plan.current_aligner += 1
            from datetime import timedelta
            plan.next_tray_change_date = timezone.localdate() + timedelta(days=plan.aligner_frequency_days)
            plan.save()

            # Create new TrayHistory
            TrayHistory.objects.create(
                treatment_plan=plan,
                tray_number=plan.current_aligner,
                started_on=timezone.localdate(),
                status='Active',
                doctor_notes=f"Advanced to Tray #{plan.current_aligner} by Dr. {doctor.full_name}"
            )

            # Notify Patient
            if hasattr(patient, 'portal_profile') and patient.portal_profile:
                from patient.models import PatientNotification
                PatientNotification.objects.create(
                    patient=patient.portal_profile,
                    notification_type='TRAY_CHANGE',
                    title=f'Tray Advanced to #{plan.current_aligner}',
                    message=f'Dr. {doctor.full_name} has advanced your aligner to Tray #{plan.current_aligner}. Next scheduled switch date: {plan.next_tray_change_date.strftime("%b %d, %Y")}.'
                )

            PatientActivityLog.objects.create(
                patient=patient,
                doctor=doctor,
                activity_type='Aligner Advanced',
                description=f"Doctor advanced patient to Aligner #{plan.current_aligner} of {plan.total_aligners}."
            )
            messages.success(request, f"Patient {patient.full_name} advanced to Aligner #{plan.current_aligner}!")
        else:
            messages.info(request, f"Patient has reached the final aligner (#{plan.total_aligners}).")

    return redirect('doctor:patient_detail', patient_id=patient.id)


# ----------------- PHOTO MONITORING -----------------

@login_required
def photo_monitoring_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    # Eligible patients for Step 4: ONLY patients who have completed Steps 1, 2, and 3
    all_doctor_patients = Patient.objects.filter(
        doctor=doctor,
        is_archived=False
    ).prefetch_related('preoperative_photos', 'radiographs', 'appointments')
    eligible_patients = [p for p in all_doctor_patients if p.has_completed_step3]

    # Resolve selected patient for Step 4
    selected_patient_id = request.GET.get('patient_id') or request.POST.get('patient_id')
    selected_patient = None
    if selected_patient_id:
        selected_patient = next((p for p in eligible_patients if str(p.id) == str(selected_patient_id)), None)
    if not selected_patient and eligible_patients:
        selected_patient = eligible_patients[0]

    # Handle POST actions (Step 4 save operation, delete media)
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_step4_operation':
            target_patient_id = request.POST.get('patient_id')
            target_patient = get_object_or_404(Patient, id=target_patient_id, doctor=doctor, is_archived=False)

            if not target_patient.has_completed_step3:
                messages.error(
                    request,
                    f"Patient {target_patient.full_name} is not eligible for Step 4 yet. "
                    f"Step 1 (3 Pre-op Photos), Step 2 (Radiographs), and Step 3 (Hospital Appointment) must all be completed first."
                )
                return redirect(f"{reverse('doctor:photo_monitoring')}?patient_id={target_patient.id}")

            patient_problem = request.POST.get('patient_problem', '').strip()
            if not patient_problem:
                messages.error(request, "Please enter what the clinical problem of the patient is (Diagnosis / Clinical Condition).")
                return redirect(f"{reverse('doctor:photo_monitoring')}?patient_id={target_patient.id}")

            operation_type = request.POST.get('operation_type', 'TURN_QUEST').strip()
            custom_op_name = request.POST.get('custom_operation_name', '').strip()

            if operation_type == 'OTHER':
                if not custom_op_name:
                    messages.error(request, "Please specify the custom operation name.")
                    return redirect(f"{reverse('doctor:photo_monitoring')}?patient_id={target_patient.id}")
                operation_name = custom_op_name
            else:
                operation_name = "Turn Quest"

            update_frequency = request.POST.get('update_frequency', 'WEEKLY').strip()
            if update_frequency not in ['DAILY', 'WEEKLY', 'MONTHLY']:
                update_frequency = 'WEEKLY'

            doctor_instructions = request.POST.get('doctor_instructions', '').strip()
            treatment_stage = request.POST.get('treatment_stage', '').strip() or f"{operation_name} Initiation Stage"

            photo = request.FILES.get('photo')
            photo_desc = request.POST.get('photo_description', '').strip() or f"{operation_name} Reference / Appliance Photograph"
            video = request.FILES.get('video')
            video_desc = request.POST.get('video_description', '').strip() or f"{operation_name} Demonstration Video"

            prev_media = target_patient.treatment_media.order_by('-version').first()

            # Photo validation: 1 photo required for both Turn Quest and Other Operation
            if not photo and not (prev_media and prev_media.photo):
                messages.error(request, f"Please upload or paste (Ctrl+V) 1 reference photograph for {operation_name}.")
                return redirect(f"{reverse('doctor:photo_monitoring')}?patient_id={target_patient.id}")

            # For Turn Quest: 1 small video is required
            if operation_type == 'TURN_QUEST' and not video and not (prev_media and prev_media.video):
                messages.error(request, "Turn Quest operation requires 1 small demonstration video (demonstrating appliance wear / key turns).")
                return redirect(f"{reverse('doctor:photo_monitoring')}?patient_id={target_patient.id}")

            # Final files to use (if updating and no new file was chosen, keep previous)
            final_photo = photo or (prev_media.photo if prev_media else None)
            final_video = video or (prev_media.video if prev_media else None)

            # Determine next version & deactivate older records
            next_version = (prev_media.version + 1) if prev_media else 1
            target_patient.treatment_media.update(is_current=False)

            # Create DoctorTreatmentMedia
            DoctorTreatmentMedia.objects.create(
                patient=target_patient,
                doctor=doctor,
                operation_type=operation_type,
                operation_name=operation_name,
                patient_problem=patient_problem,
                update_frequency=update_frequency,
                photo=final_photo,
                photo_description=photo_desc,
                video=final_video,
                video_description=video_desc,
                treatment_stage=treatment_stage,
                doctor_instructions=doctor_instructions,
                version=next_version,
                is_current=True,
                upload_date=timezone.localdate()
            )

            # Permanent audit record in TreatmentOperationRecord
            TreatmentOperationRecord.objects.create(
                patient=target_patient,
                doctor=doctor,
                operation_performed=operation_name,
                identified_problems=patient_problem,
                current_condition=patient_problem,
                examination_findings=f"Step 4: Prescribed {operation_name} with {update_frequency.title()} Photo Monitoring protocol.",
                treatment_description=f"Initiated {operation_name}. Demonstration media v{next_version} uploaded.",
                doctor_observations=doctor_instructions,
                next_treatment_steps=f"Patient instructed to submit {update_frequency.lower()} dental tracking photos."
            )

            # Update patient model fields
            target_patient.monitoring_frequency = update_frequency
            target_patient.current_operation = operation_name
            target_patient.diagnosed_problem = patient_problem
            if target_patient.treatment_status == 'PENDING_CONNECTION':
                target_patient.treatment_status = 'ACTIVE'
            target_patient.save()

            # Activity Log
            PatientActivityLog.objects.create(
                doctor=doctor,
                patient=target_patient,
                activity_type='Step 4 Operation Prescribed',
                description=f"Prescribed {operation_name} ({update_frequency.title()} updates) with problem: {patient_problem[:80]}"
            )

            # Patient Notification
            media_items = []
            if final_photo:
                media_items.append("photograph")
            if final_video:
                media_items.append("demonstration video")
            media_str = f" with {' and '.join(media_items)}" if media_items else ""

            notify_patient_profile(
                patient=target_patient,
                notification_type='TREATMENT_UPDATE',
                title=f'Step 4 Operation Prescribed: {operation_name}',
                message=f'Dr. {doctor.display_name} diagnosed "{patient_problem}" and prescribed {operation_name}{media_str}. Monitoring update frequency: {update_frequency.title()}. Please view demonstration media and clinical guidance.',
                link_url='/patient/#step4Section'
            )

            messages.success(
                request,
                f"Step 4 Completed: '{operation_name}' successfully prescribed for {target_patient.full_name}! "
                f"{update_frequency.title()} monitoring cadence and demonstration media are now active."
            )
            return redirect(f"{reverse('doctor:photo_monitoring')}?patient_id={target_patient.id}")

        elif action == 'delete_operation_media':
            media_id = request.POST.get('media_id')
            target_patient_id = request.POST.get('patient_id')
            target_patient = get_object_or_404(Patient, id=target_patient_id, doctor=doctor)
            media_item = target_patient.treatment_media.filter(id=media_id).first()
            if media_item:
                if media_item.photo:
                    media_item.photo.delete(save=False)
                if media_item.video:
                    media_item.video.delete(save=False)
                media_item.delete()
                latest = target_patient.treatment_media.first()
                if latest:
                    latest.is_current = True
                    latest.save()
                messages.info(request, "Operation media record removed.")
            return redirect(f"{reverse('doctor:photo_monitoring')}?patient_id={target_patient.id}")

    # Patient weekly/daily monitoring submissions feed
    uploads_qs = PhotoMonitoring.objects.filter(patient__doctor=doctor).select_related('patient')

    status_filter = request.GET.get('status', 'ALL')
    if status_filter != 'ALL':
        uploads_qs = uploads_qs.filter(tracking_status=status_filter)

    query = request.GET.get('q', '').strip()
    if query:
        uploads_qs = uploads_qs.filter(
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__patient_id__icontains=query)
        )

    selected_patient_media = selected_patient.treatment_media.filter(is_current=True).first() if selected_patient else None
    selected_patient_media_history = selected_patient.treatment_media.all() if selected_patient else []
    active_operations = DoctorTreatmentMedia.objects.filter(doctor=doctor, is_current=True).select_related('patient')

    context = {
        'doctor': doctor,
        'uploads': uploads_qs,
        'status_filter': status_filter,
        'query': query,
        'status_choices': PhotoMonitoring.TRACKING_STATUS_CHOICES,
        'eligible_patients': eligible_patients,
        'selected_patient': selected_patient,
        'selected_patient_media': selected_patient_media,
        'selected_patient_media_history': selected_patient_media_history,
        'active_operations': active_operations,
    }
    return render(request, 'doctor/photos/photo_monitoring_list.html', context)


@login_required
def step4_operation_view(request, patient_id):
    """
    Dedicated Step 4 Clinical Operation & Problem Diagnosis Page:
    Doctor prescribes Turn Quest or custom operation, diagnoses patient's clinical problem,
    chooses Daily/Weekly/Monthly photo update cadence, and uploads 1 photo + 1 small video.
    """
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor, is_archived=False)

    if not patient.has_completed_step3:
        messages.error(
            request,
            f"Patient {patient.full_name} is not eligible for Step 4 yet. "
            f"Step 1 (3 Pre-op Photos), Step 2 (Radiographs), and Step 3 (Hospital Appointment) must all be completed first."
        )
        return redirect('doctor:photo_monitoring')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_step4_operation':
            patient_problem = request.POST.get('patient_problem', '').strip()
            if not patient_problem:
                messages.error(request, "Please enter what the clinical problem of the patient is (Diagnosis / Clinical Condition).")
                return redirect('doctor:step4_operation', patient_id=patient.id)

            operation_type = request.POST.get('operation_type', 'TURN_QUEST').strip()
            custom_op_name = request.POST.get('custom_operation_name', '').strip()

            if operation_type == 'OTHER':
                if not custom_op_name:
                    messages.error(request, "Please specify the custom operation name.")
                    return redirect('doctor:step4_operation', patient_id=patient.id)
                operation_name = custom_op_name
            else:
                operation_name = "Turn Quest"

            update_frequency = request.POST.get('update_frequency', 'WEEKLY').strip()
            if update_frequency not in ['DAILY', 'WEEKLY', 'MONTHLY']:
                update_frequency = 'WEEKLY'

            doctor_instructions = request.POST.get('doctor_instructions', '').strip()
            treatment_stage = request.POST.get('treatment_stage', '').strip() or f"{operation_name} Initiation Stage"

            photo = request.FILES.get('photo')
            photo_desc = request.POST.get('photo_description', '').strip() or f"{operation_name} Reference / Appliance Photograph"
            video = request.FILES.get('video')
            video_desc = request.POST.get('video_description', '').strip() or f"{operation_name} Demonstration Video"

            prev_media = patient.treatment_media.order_by('-version').first()

            # Photo validation: 1 photo required for both Turn Quest and Other Operation
            if not photo and not (prev_media and prev_media.photo):
                messages.error(request, f"Please upload or paste (Ctrl+V) 1 reference photograph for {operation_name}.")
                return redirect('doctor:step4_operation', patient_id=patient.id)

            # For Turn Quest: 1 small video is required
            if operation_type == 'TURN_QUEST' and not video and not (prev_media and prev_media.video):
                messages.error(request, "Turn Quest operation requires 1 small demonstration video (demonstrating appliance wear / key turns).")
                return redirect('doctor:step4_operation', patient_id=patient.id)

            # Final files to use (if updating and no new file was chosen, keep previous)
            final_photo = photo or (prev_media.photo if prev_media else None)
            final_video = video or (prev_media.video if prev_media else None)

            # Determine next version & deactivate older records
            next_version = (prev_media.version + 1) if prev_media else 1
            patient.treatment_media.update(is_current=False)

            # Create DoctorTreatmentMedia
            DoctorTreatmentMedia.objects.create(
                patient=patient,
                doctor=doctor,
                operation_type=operation_type,
                operation_name=operation_name,
                patient_problem=patient_problem,
                update_frequency=update_frequency,
                photo=final_photo,
                photo_description=photo_desc,
                video=final_video,
                video_description=video_desc,
                treatment_stage=treatment_stage,
                doctor_instructions=doctor_instructions,
                version=next_version,
                is_current=True,
                upload_date=timezone.localdate()
            )

            # Permanent audit record in TreatmentOperationRecord
            TreatmentOperationRecord.objects.create(
                patient=patient,
                doctor=doctor,
                operation_performed=operation_name,
                identified_problems=patient_problem,
                current_condition=patient_problem,
                examination_findings=f"Step 4: Prescribed {operation_name} with {update_frequency.title()} Photo Monitoring protocol.",
                treatment_description=f"Initiated {operation_name}. Demonstration media v{next_version} uploaded.",
                doctor_observations=doctor_instructions,
                next_treatment_steps=f"Patient instructed to submit {update_frequency.lower()} dental tracking photos."
            )

            # Update patient model fields
            patient.monitoring_frequency = update_frequency
            patient.current_operation = operation_name
            patient.diagnosed_problem = patient_problem
            if patient.treatment_status == 'PENDING_CONNECTION':
                patient.treatment_status = 'ACTIVE'
            patient.save()

            # Activity Log
            PatientActivityLog.objects.create(
                doctor=doctor,
                patient=patient,
                activity_type='Step 4 Operation Prescribed',
                description=f"Prescribed {operation_name} ({update_frequency.title()} updates) with problem: {patient_problem[:80]}"
            )

            # Patient Notification
            media_items = []
            if final_photo:
                media_items.append("photograph")
            if final_video:
                media_items.append("demonstration video")
            media_str = f" with {' and '.join(media_items)}" if media_items else ""

            notify_patient_profile(
                patient=patient,
                notification_type='TREATMENT_UPDATE',
                title=f'Step 4 Operation Prescribed: {operation_name}',
                message=f'Dr. {doctor.display_name} diagnosed "{patient_problem}" and prescribed {operation_name}{media_str}. Monitoring update frequency: {update_frequency.title()}. Please view demonstration media and clinical guidance.',
                link_url='/patient/#step4Section'
            )

            messages.success(
                request,
                f"Step 4 Completed: '{operation_name}' successfully prescribed for {patient.full_name}! "
                f"{update_frequency.title()} monitoring cadence and demonstration media are now active."
            )
            return redirect('doctor:step4_operation', patient_id=patient.id)

        elif action == 'delete_operation_media':
            media_id = request.POST.get('media_id')
            media_item = patient.treatment_media.filter(id=media_id).first()
            if media_item:
                if media_item.photo:
                    media_item.photo.delete(save=False)
                if media_item.video:
                    media_item.video.delete(save=False)
                media_item.delete()
                latest = patient.treatment_media.first()
                if latest:
                    latest.is_current = True
                    latest.save()
                messages.info(request, "Operation media record removed.")
            return redirect('doctor:step4_operation', patient_id=patient.id)

    current_media = patient.treatment_media.filter(is_current=True).first()
    media_history = patient.treatment_media.all()
    next_appointment = patient.appointments.filter(scheduled_date__gte=timezone.localdate()).order_by('scheduled_date', 'scheduled_time').first() or patient.appointments.first()

    context = {
        'doctor': doctor,
        'patient': patient,
        'current_media': current_media,
        'media_history': media_history,
        'next_appointment': next_appointment,
    }
    return render(request, 'doctor/photos/step4_operation.html', context)


@login_required
def photo_upload_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    form = PhotoUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        photo_obj = form.save(commit=False)
        photo_obj.patient = patient
        photo_obj.tracking_status = 'TRACKING_WELL'
        photo_obj.reviewed_at = timezone.now()
        photo_obj.save()

        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Photos Uploaded',
            description=f"Dental monitoring photos logged for Week {photo_obj.week_number} (Aligner #{photo_obj.aligner_stage})."
        )
        messages.success(request, f"Photos for {patient.full_name} uploaded successfully.")
        return redirect('doctor:patient_detail', patient_id=patient.id)

    return render(request, 'doctor/photos/photo_upload.html', {'form': form, 'patient': patient, 'doctor': doctor})


@login_required
def photo_review_view(request, photo_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    photo_obj = get_object_or_404(PhotoMonitoring, id=photo_id, patient__doctor=doctor)
    form = PhotoMonitoringReviewForm(request.POST or None, instance=photo_obj)

    if request.method == 'POST' and form.is_valid():
        reviewed = form.save(commit=False)
        reviewed.reviewed_at = timezone.now()
        reviewed.save()

        # Notify / Log
        PatientActivityLog.objects.create(
            patient=photo_obj.patient,
            doctor=doctor,
            activity_type='Photo Monitoring Reviewed',
            description=f"Doctor reviewed Week {photo_obj.week_number} photos. Status: {reviewed.get_tracking_status_display()}."
        )

        Notification.objects.create(
            doctor=doctor,
            patient=photo_obj.patient,
            notification_type='PHOTO_UPLOAD',
            title=f"Review Completed: {photo_obj.patient.full_name}",
            message=f"Feedback sent for Week {photo_obj.week_number} ({reviewed.get_tracking_status_display()})."
        )

        notify_patient_profile(
            patient=photo_obj.patient,
            notification_type='DOCTOR_FEEDBACK',
            title=f"Doctor Reviewed Week #{photo_obj.week_number} Photos ({reviewed.get_tracking_status_display()})",
            message=f"Dr. {doctor.display_name} has reviewed your Week #{photo_obj.week_number} progress photos. Status: {reviewed.get_tracking_status_display()}. Remarks: {reviewed.doctor_comments or 'Good progression.'}",
            link_url='/patient/#patientProgressSection'
        )

        messages.success(request, f"Feedback and rating for {photo_obj.patient.full_name}'s photos submitted successfully.")
        return redirect('doctor:patient_detail', patient_id=photo_obj.patient.id)

    return render(request, 'doctor/photos/photo_review.html', {
        'form': form,
        'photo': photo_obj,
        'patient': photo_obj.patient,
        'doctor': doctor
    })


@login_required
def photo_compare_view(request, patient_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    photos = PhotoMonitoring.objects.filter(patient=patient).order_by('upload_date', 'created_at')

    # Categories
    pre_treatment_photos = photos.filter(is_before_sample=True)
    if not pre_treatment_photos.exists() and photos.exists():
        pre_treatment_photos = photos[:1]

    latest_photos = photos.filter(is_after_sample=True)
    if not latest_photos.exists() and photos.exists():
        latest_photos = photos.order_by('-upload_date', '-created_at')[:1]

    # Intermediate during-treatment photos
    during_treatment_photos = photos.exclude(id__in=pre_treatment_photos.values_list('id', flat=True)).exclude(id__in=latest_photos.values_list('id', flat=True))

    # Selected sets to compare
    left_id = request.GET.get('left_id')
    right_id = request.GET.get('right_id')

    left_photo = None
    right_photo = None

    if left_id:
        left_photo = photos.filter(id=left_id).first()
    if not left_photo:
        left_photo = pre_treatment_photos.first() or photos.first()

    if right_id:
        right_photo = photos.filter(id=right_id).first()
    if not right_photo:
        right_photo = latest_photos.first() or photos.last()

    # Active angle to compare: front, right, left, upper, lower
    angle = request.GET.get('angle', 'front')

    # Handle Doctor Comment on comparison
    if request.method == 'POST' and 'save_comment' in request.POST:
        target_id = request.POST.get('target_photo_id')
        comment_text = request.POST.get('doctor_comment', '').strip()
        target_obj = photos.filter(id=target_id).first()
        if target_obj:
            target_obj.doctor_feedback = comment_text
            target_obj.reviewed_at = timezone.now()
            target_obj.tracking_status = 'TRACKING_WELL'
            target_obj.save()
            messages.success(request, f"Clinical comparison comment saved for Week {target_obj.week_number} photo.")
            return redirect(f"{request.path}?left_id={left_photo.id}&right_id={right_photo.id}&angle={angle}")

    context = {
        'doctor': doctor,
        'patient': patient,
        'photos': photos,
        'pre_treatment_photos': pre_treatment_photos,
        'during_treatment_photos': during_treatment_photos,
        'latest_photos': latest_photos,
        'left_photo': left_photo,
        'right_photo': right_photo,
        'angle': angle,
    }
    return render(request, 'doctor/photos/photo_compare.html', context)


# ----------------- PROGRESS TRACKING -----------------

@login_required
def progress_tracking_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patients_qs = Patient.objects.filter(doctor=doctor).select_related('treatment_plan')
    treatment_plans = TreatmentPlan.objects.filter(patient__doctor=doctor).select_related('patient')

    avg_compliance = treatment_plans.aggregate(avg=Avg('compliance_score'))['avg'] or 0
    avg_duration = treatment_plans.aggregate(avg=Avg('estimated_duration_months'))['avg'] or 0

    context = {
        'doctor': doctor,
        'patients': patients_qs,
        'treatment_plans': treatment_plans,
        'avg_compliance': round(avg_compliance, 1),
        'avg_duration': round(avg_duration, 1),
    }
    return render(request, 'doctor/progress/progress_tracking.html', context)


# ----------------- EMERGENCY MANAGEMENT -----------------

@login_required
def emergency_alerts_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    alerts_qs = EmergencyAlert.objects.filter(patient__doctor=doctor).select_related('patient')

    status_filter = request.GET.get('status', 'ALL')
    if status_filter != 'ALL':
        alerts_qs = alerts_qs.filter(status=status_filter)

    severity_filter = request.GET.get('severity', 'ALL')
    if severity_filter != 'ALL':
        alerts_qs = alerts_qs.filter(severity=severity_filter)

    pending_count = EmergencyAlert.objects.filter(patient__doctor=doctor, status='PENDING').count()
    in_review_count = EmergencyAlert.objects.filter(patient__doctor=doctor, status='IN_REVIEW').count()
    resolved_count = EmergencyAlert.objects.filter(patient__doctor=doctor, status='RESOLVED').count()

    context = {
        'doctor': doctor,
        'alerts': alerts_qs,
        'status_filter': status_filter,
        'severity_filter': severity_filter,
        'pending_count': pending_count,
        'in_review_count': in_review_count,
        'resolved_count': resolved_count,
        'severity_choices': EmergencyAlert.SEVERITY_CHOICES,
        'status_choices': EmergencyAlert.STATUS_CHOICES,
    }
    return render(request, 'doctor/emergency/emergency_alerts_list.html', context)


@login_required
def emergency_create_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    form = EmergencyCreateForm(request.POST or None, doctor=doctor)
    if request.method == 'POST' and form.is_valid():
        alert = form.save()
        PatientActivityLog.objects.create(
            patient=alert.patient,
            doctor=doctor,
            activity_type='Emergency Alert Logged',
            description=f"[{alert.get_severity_display()}] {alert.get_issue_type_display()} recorded."
        )
        Notification.objects.create(
            doctor=doctor,
            patient=alert.patient,
            notification_type='EMERGENCY',
            title=f"Emergency: {alert.get_issue_type_display()} ({alert.patient.full_name})",
            message=alert.description[:120]
        )
        messages.success(request, f"Emergency alert for {alert.patient.full_name} logged successfully.")
        return redirect('doctor:emergency_alerts')

    return render(request, 'doctor/emergency/emergency_create.html', {'form': form, 'doctor': doctor})


@login_required
def emergency_respond_view(request, alert_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    alert = get_object_or_404(EmergencyAlert, id=alert_id, patient__doctor=doctor)
    form = EmergencyResponseForm(request.POST or None, instance=alert)

    if request.method == 'POST' and form.is_valid():
        updated_alert = form.save(commit=False)
        if updated_alert.status == 'RESOLVED' and not updated_alert.resolved_at:
            updated_alert.resolved_at = timezone.now()
        updated_alert.save()

        PatientActivityLog.objects.create(
            patient=alert.patient,
            doctor=doctor,
            activity_type='Emergency Alert Responded',
            description=f"Doctor updated emergency status to {updated_alert.get_status_display()} with guidance."
        )

        if hasattr(alert.patient, 'portal_profile') and alert.patient.portal_profile:
            from patient.models import PatientNotification
            PatientNotification.objects.create(
                patient=alert.patient.portal_profile,
                notification_type='EMERGENCY_RESPONSE',
                title=f"Doctor Responded: {alert.get_issue_type_display()}",
                message=f"Dr. {doctor.full_name} provided instructions: {updated_alert.doctor_response or 'Status updated to ' + updated_alert.get_status_display()}",
                link_url='/emergency/'
            )

        messages.success(request, f"Emergency response saved for {alert.patient.full_name}.")
        return redirect('doctor:emergency_alerts')

    return render(request, 'doctor/emergency/emergency_respond.html', {
        'form': form,
        'alert': alert,
        'patient': alert.patient,
        'doctor': doctor
    })


@login_required
def emergency_resolve_quick_view(request, alert_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    alert = get_object_or_404(EmergencyAlert, id=alert_id, patient__doctor=doctor)
    if request.method == 'POST':
        alert.status = 'RESOLVED'
        alert.resolved_at = timezone.now()
        if not alert.doctor_response:
            alert.doctor_response = "Resolved in clinic / via consultation."
        alert.save()

        if hasattr(alert.patient, 'portal_profile') and alert.patient.portal_profile:
            from patient.models import PatientNotification
            PatientNotification.objects.create(
                patient=alert.patient.portal_profile,
                notification_type='EMERGENCY_RESPONSE',
                title=f"Emergency Resolved: {alert.get_issue_type_display()}",
                message=f"Dr. {doctor.full_name} marked your emergency issue as Resolved.",
                link_url='/emergency/'
            )

        messages.success(request, f"Emergency issue for {alert.patient.full_name} marked as Resolved.")

    return redirect('doctor:emergency_alerts')


# ----------------- APPOINTMENT MANAGEMENT -----------------

@login_required
def appointments_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    appointments_qs = Appointment.objects.filter(doctor=doctor).select_related('patient')

    status_filter = request.GET.get('status', 'ALL')
    if status_filter != 'ALL':
        appointments_qs = appointments_qs.filter(status=status_filter)

    view_mode = request.GET.get('view', 'list')  # 'list' or 'calendar'

    today = timezone.localdate()
    upcoming_count = Appointment.objects.filter(doctor=doctor, status='UPCOMING', scheduled_date__gte=today).count()
    completed_count = Appointment.objects.filter(doctor=doctor, status='COMPLETED').count()

    context = {
        'doctor': doctor,
        'appointments': appointments_qs,
        'status_filter': status_filter,
        'view_mode': view_mode,
        'today': today,
        'upcoming_count': upcoming_count,
        'completed_count': completed_count,
        'status_choices': Appointment.STATUS_CHOICES,
    }
    return render(request, 'doctor/appointments/appointments_list.html', context)


@login_required
def appointment_create_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patient_id = request.GET.get('patient')
    initial_data = {}
    if patient_id:
        patient = Patient.objects.filter(id=patient_id, doctor=doctor).first()
        if patient:
            initial_data['patient'] = patient

    form = AppointmentForm(request.POST or None, initial=initial_data, doctor=doctor)

    if request.method == 'POST' and form.is_valid():
        appointment = form.save(commit=False)
        appointment.doctor = doctor
        appointment.save()

        PatientActivityLog.objects.create(
            patient=appointment.patient,
            doctor=doctor,
            activity_type='Appointment Scheduled',
            description=f"{appointment.get_appointment_type_display()} scheduled on {appointment.scheduled_date} at {appointment.scheduled_time}."
        )

        Notification.objects.create(
            doctor=doctor,
            patient=appointment.patient,
            notification_type='APPOINTMENT',
            title=f"Appointment Booked: {appointment.patient.full_name}",
            message=f"{appointment.get_appointment_type_display()} on {appointment.scheduled_date} at {appointment.scheduled_time}."
        )

        if hasattr(appointment.patient, 'portal_profile') and appointment.patient.portal_profile:
            from patient.models import PatientNotification
            PatientNotification.objects.create(
                patient=appointment.patient.portal_profile,
                notification_type='APPOINTMENT',
                title=f"New Appointment: {appointment.get_appointment_type_display()}",
                message=f"Dr. {doctor.full_name} scheduled a visit on {appointment.scheduled_date} at {appointment.scheduled_time}. {appointment.instructions or ''}",
                link_url='/appointments/'
            )

        messages.success(request, f"Appointment for {appointment.patient.full_name} scheduled successfully!")
        return redirect('doctor:appointments')

    return render(request, 'doctor/appointments/appointment_create.html', {'form': form, 'doctor': doctor})


@login_required
def appointment_status_update_view(request, appt_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    appointment = get_object_or_404(Appointment, id=appt_id, doctor=doctor)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Appointment.STATUS_CHOICES):
            appointment.status = new_status
            if new_status == 'CANCELLED':
                appointment.cancellation_reason = request.POST.get('cancellation_reason', 'Cancelled by doctor/patient')
            appointment.save()

            PatientActivityLog.objects.create(
                patient=appointment.patient,
                doctor=doctor,
                activity_type='Appointment Status Updated',
                description=f"Appointment on {appointment.scheduled_date} marked as {appointment.get_status_display()}."
            )

            if hasattr(appointment.patient, 'portal_profile') and appointment.patient.portal_profile:
                from patient.models import PatientNotification
                status_title = "Appointment Confirmed by Doctor" if new_status == 'UPCOMING' else f"Appointment {appointment.get_status_display()}"
                PatientNotification.objects.create(
                    patient=appointment.patient.portal_profile,
                    notification_type='APPOINTMENT',
                    title=status_title,
                    message=f"Dr. {doctor.full_name} updated your appointment on {appointment.scheduled_date} at {appointment.scheduled_time} to {appointment.get_status_display()}.",
                    link_url='/appointments/'
                )

            messages.success(request, f"Appointment status updated to {appointment.get_status_display()}.")

    return redirect('doctor:appointments')


# ----------------- NOTIFICATIONS & REMINDERS -----------------

@login_required
def notifications_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    notifications_qs = Notification.objects.filter(doctor=doctor)

    type_filter = request.GET.get('type', 'ALL')
    if type_filter != 'ALL':
        notifications_qs = notifications_qs.filter(notification_type=type_filter)

    reminder_form = SendReminderInstructionForm(request.POST or None, doctor=doctor)

    if request.method == 'POST' and 'send_reminder' in request.POST and reminder_form.is_valid():
        patient = reminder_form.cleaned_data['patient']
        title = reminder_form.cleaned_data['title']
        msg_text = reminder_form.cleaned_data['message']

        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Instruction Sent to Patient',
            description=f"Title: {title} | Message: {msg_text}"
        )
        Notification.objects.create(
            doctor=doctor,
            patient=patient,
            notification_type='FOLLOWUP',
            title=f"Sent to {patient.full_name}: {title}",
            message=msg_text
        )
        messages.success(request, f"Instructions & reminders successfully sent to {patient.full_name}!")
        return redirect('doctor:notifications')

    context = {
        'doctor': doctor,
        'notifications': notifications_qs,
        'type_filter': type_filter,
        'reminder_form': reminder_form,
        'type_choices': Notification.NOTIFICATION_TYPE_CHOICES,
    }
    return render(request, 'doctor/notifications/notifications_list.html', context)


@login_required
def mark_notification_read_view(request, notif_id):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    notif = get_object_or_404(Notification, id=notif_id, doctor=doctor)
    notif.is_read = True
    notif.save()

    if notif.link_url:
        return redirect(notif.link_url)
    return redirect('doctor:notifications')


@login_required
def mark_all_notifications_read_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    Notification.objects.filter(doctor=doctor, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('doctor:notifications')


# ----------------- REPORTS & ANALYTICS -----------------

@login_required
def reports_analytics_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patients_qs = Patient.objects.filter(doctor=doctor)
    total_patients = patients_qs.count()
    active_count = patients_qs.filter(treatment_status='ACTIVE').count()
    completed_count = patients_qs.filter(treatment_status='COMPLETED').count()
    pending_count = patients_qs.filter(treatment_status='PENDING_CONNECTION').count()

    plans_qs = TreatmentPlan.objects.filter(patient__doctor=doctor)
    avg_compliance = plans_qs.aggregate(avg=Avg('compliance_score'))['avg'] or 0
    avg_duration = plans_qs.aggregate(avg=Avg('estimated_duration_months'))['avg'] or 0

    # Success rate
    resolved_emergencies = EmergencyAlert.objects.filter(patient__doctor=doctor, status='RESOLVED').count()
    total_emergencies = EmergencyAlert.objects.filter(patient__doctor=doctor).count()
    emergency_resolution_rate = int((resolved_emergencies / total_emergencies) * 100) if total_emergencies > 0 else 100

    context = {
        'doctor': doctor,
        'total_patients': total_patients,
        'active_count': active_count,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'avg_compliance': round(avg_compliance, 1),
        'avg_duration': round(avg_duration, 1),
        'emergency_resolution_rate': emergency_resolution_rate,
        'patients': patients_qs[:10],
    }
    return render(request, 'doctor/reports/reports_dashboard.html', context)


@login_required
def export_patients_csv_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="PedoAlign_Clinical_Report_{timezone.localdate()}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Patient ID', 'First Name', 'Last Name', 'Category', 'Age', 'Gender',
        'Phone', 'Email', 'Parent/Guardian', 'Treatment Status',
        'Teeth Present', 'Overbite', 'Deep Bite', 'Molar Relationship', 'Canine Relationship', 'Crossbite', 'Oral Habits',
        'Current Aligner', 'Total Aligners', 'Compliance Score (%)',
        'Joining Code', 'Created Date'
    ])

    patients = Patient.objects.filter(doctor=doctor).select_related('treatment_plan', 'joining_code', 'clinical_record')
    for p in patients:
        plan = getattr(p, 'treatment_plan', None)
        code = getattr(p, 'joining_code', None)
        clin = getattr(p, 'clinical_record', None)
        writer.writerow([
            p.patient_id,
            p.first_name,
            p.last_name,
            p.get_patient_category_display(),
            p.age,
            p.gender,
            p.phone,
            p.email or 'N/A',
            p.parent_guardian_name or 'N/A',
            p.get_treatment_status_display(),
            clin.teeth_present if clin else 'N/A',
            clin.overbite if clin else 'N/A',
            clin.deep_bite if clin else 'N/A',
            clin.molar_relationship if clin else 'N/A',
            clin.canine_relationship if clin else 'N/A',
            clin.crossbite if clin else 'N/A',
            clin.oral_habits if clin else 'N/A',
            plan.current_aligner if plan else 'N/A',
            plan.total_aligners if plan else 'N/A',
            f"{plan.compliance_score}%" if plan else 'N/A',
            code.code if code else 'N/A',
            p.created_at.strftime('%Y-%m-%d')
        ])

    return response


@login_required
def print_report_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    patients = Patient.objects.filter(doctor=doctor).select_related('treatment_plan', 'clinical_record')
    total_count = patients.count()
    active_count = patients.filter(treatment_status='ACTIVE').count()
    completed_count = patients.filter(treatment_status='COMPLETED').count()

    context = {
        'doctor': doctor,
        'patients': patients,
        'total_count': total_count,
        'active_count': active_count,
        'completed_count': completed_count,
        'generated_date': timezone.now(),
    }
    return render(request, 'doctor/reports/print_report.html', context)


# ----------------- DOCTOR PROFILE & SETTINGS -----------------

@login_required
def doctor_settings_view(request):
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')

    profile_form = DoctorProfileForm(request.POST or None, request.FILES or None, instance=doctor)

    if request.method == 'POST' and 'remove_picture' in request.POST:
        if doctor.profile_picture:
            doctor.profile_picture.delete(save=False)
            doctor.profile_picture = None
            doctor.save()
            messages.success(request, "Your profile picture has been removed.")
            return redirect('doctor:settings')

    if request.method == 'POST' and 'update_profile' in request.POST:
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Your clinic profile and profile picture have been updated successfully.")
            return redirect('doctor:settings')

    if request.method == 'POST' and 'change_password' in request.POST:
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not request.user.check_password(old_password):
            messages.error(request, "Current password is incorrect.")
        elif len(new_password) < 8:
            messages.error(request, "New password must be at least 8 characters long.")
        elif new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password updated successfully!")
            return redirect('doctor:settings')

    return render(request, 'doctor/settings/settings.html', {
        'doctor': doctor,
        'profile_form': profile_form
    })


# ----------------- PATIENT CLINICAL JOURNEY (3-STEP GUIDED INTAKE) -----------------

@login_required(login_url='doctor:login')
def patient_clinical_journey_view(request, patient_id):
    """
    Dedicated 3-Step Clinical Intake & Journey Page:
    Step 1: Preoperative Photographs (3 Compulsory photos with descriptions)
    Step 2: Radiographs (OPG & Lateral Cephalograph)
    Step 3: Schedule Next Hospital / Clinic Appointment
    """
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        return redirect('doctor:login')
    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    treatment_plan = getattr(patient, 'treatment_plan', None)

    active_step = request.GET.get('step', '1')

    preop_form = CompulsoryPreoperativePhotosForm()
    radiograph_form = RadiographRecordForm()

    import datetime
    default_20day_date = (timezone.localdate() + datetime.timedelta(days=20)).strftime('%Y-%m-%d')

    if request.method == 'POST':
        action = request.POST.get('action')

        # ----------------- STEP 1: PREOPERATIVE PHOTOS (3 COMPULSORY + OPTIONAL EXTRAS) -----------------
        if action == 'save_preop':
            form = CompulsoryPreoperativePhotosForm(request.POST, request.FILES)
            if form.is_valid():
                p1 = form.cleaned_data['photo_1']
                d1 = form.cleaned_data.get('description_1', '').strip() or 'Preoperative Frontal View'
                p2 = form.cleaned_data['photo_2']
                d2 = form.cleaned_data.get('description_2', '').strip() or 'Preoperative Upper Arch View'
                p3 = form.cleaned_data['photo_3']
                d3 = form.cleaned_data.get('description_3', '').strip() or 'Preoperative Lower Arch / Lateral View'

                PreoperativePhoto.objects.create(patient=patient, photo=p1, title='Preoperative Photo #1 (Frontal View)', description=d1)
                PreoperativePhoto.objects.create(patient=patient, photo=p2, title='Preoperative Photo #2 (Upper Arch)', description=d2)
                PreoperativePhoto.objects.create(patient=patient, photo=p3, title='Preoperative Photo #3 (Lower Arch)', description=d3)

                saved_count = 3
                # Save any extra photos added dynamically via "+" button
                extra_photos = request.FILES.getlist('extra_photos')
                extra_descriptions = request.POST.getlist('extra_descriptions')
                for idx, extra_photo in enumerate(extra_photos, start=4):
                    if extra_photo:
                        desc = ''
                        if idx - 4 < len(extra_descriptions):
                            desc = extra_descriptions[idx - 4].strip()
                        if not desc:
                            desc = f'Preoperative Photo #{idx} (Additional Angle)'
                        PreoperativePhoto.objects.create(
                            patient=patient,
                            photo=extra_photo,
                            title=f'Preoperative Photo #{idx}',
                            description=desc
                        )
                        saved_count += 1

                extra_note = f" (3 compulsory + {saved_count - 3} additional)" if saved_count > 3 else ""
                PatientActivityLog.objects.create(
                    doctor=doctor,
                    patient=patient,
                    activity_type='Preoperative Photos Saved',
                    description=f'Uploaded {saved_count} preoperative photographs{extra_note} for {patient.full_name}'
                )
                notify_patient_profile(
                    patient=patient,
                    notification_type='DOCTOR_INSTRUCTION',
                    title='New Preoperative Photographs Uploaded',
                    message=f'Dr. {doctor.display_name} uploaded {saved_count} initial clinical preoperative photographs to your treatment file.',
                    link_url='/patient/#step1Section'
                )
                messages.success(request, f"Step 1 Complete: {saved_count} Preoperative photographs saved successfully! Proceeding to Step 2: Radiographs (OPG & Lateral Cephalograph).")
                return redirect(f"{reverse('doctor:patient_clinical_journey', kwargs={'patient_id': patient.id})}?step=2")
            else:
                messages.error(request, "3 preoperative photos are compulsory! Please provide all 3 photographs and descriptions before saving.")
                active_step = '1'
                preop_form = form

        elif action == 'add_extra_preop':
            photo = request.FILES.get('photo')
            description = request.POST.get('description', '').strip()
            title = request.POST.get('title', '').strip()
            if photo:
                current_num = patient.preoperative_photos.count() + 1
                if not title:
                    title = f'Preoperative Photo #{current_num}'
                if not description:
                    description = f'Additional Preoperative Dental View #{current_num}'
                PreoperativePhoto.objects.create(
                    patient=patient,
                    photo=photo,
                    title=title,
                    description=description
                )
                PatientActivityLog.objects.create(
                    doctor=doctor,
                    patient=patient,
                    activity_type='Preoperative Photo Added',
                    description=f'Added additional preoperative photo ({title}) for {patient.full_name}'
                )
                notify_patient_profile(
                    patient=patient,
                    notification_type='DOCTOR_INSTRUCTION',
                    title='New Preoperative Photograph Added',
                    message=f'Dr. {doctor.display_name} added an additional preoperative photograph ({title}) to your clinical record.',
                    link_url='/patient/#step1Section'
                )
                messages.success(request, f"Additional preoperative photo '{title}' added successfully!")
            else:
                messages.error(request, "Please select an image file to upload as an additional photograph.")
            return redirect(f"{reverse('doctor:patient_clinical_journey', kwargs={'patient_id': patient.id})}?step=1")

        # ----------------- STEP 2: RADIOGRAPH RECORDS (OPG & LATERAL CEPHALOGRAPH) -----------------
        elif action == 'save_radiograph':
            form = RadiographRecordForm(request.POST, request.FILES)
            if form.is_valid():
                rad = form.save(commit=False)
                rad.patient = patient
                prev = patient.radiographs.filter(radiograph_type=rad.radiograph_type).order_by('-version').first()
                if prev:
                    rad.version = prev.version + 1
                if not rad.title:
                    rad.title = rad.get_radiograph_type_display()
                rad.save()

                PatientActivityLog.objects.create(
                    doctor=doctor,
                    patient=patient,
                    activity_type='Radiograph Uploaded',
                    description=f'Saved {rad.get_radiograph_type_display()} radiograph (v{rad.version}) for {patient.full_name}'
                )
                notify_patient_profile(
                    patient=patient,
                    notification_type='DOCTOR_INSTRUCTION',
                    title=f'New {rad.get_radiograph_type_display()} Radiograph Uploaded',
                    message=f'Dr. {doctor.display_name} uploaded a diagnostic radiograph ({rad.get_radiograph_type_display()}, v{rad.version}) to your clinical record.',
                    link_url='/patient/#step2Section'
                )
                messages.success(request, f"Step 2 Progress: {rad.get_radiograph_type_display()} radiograph saved! You can upload another radiograph or proceed to Step 3 for the Next Hospital Appointment.")
                return redirect(f"{reverse('doctor:patient_clinical_journey', kwargs={'patient_id': patient.id})}?step=2")
            else:
                messages.error(request, "Please select a valid radiograph image file and type (OPG or Lateral Cephalograph).")
                active_step = '2'
                radiograph_form = form

        # ----------------- STEP 3: NEXT HOSPITAL APPOINTMENT SCHEDULING -----------------
        elif action == 'save_appointment':
            scheduled_date_str = request.POST.get('scheduled_date')
            scheduled_time_str = request.POST.get('scheduled_time', '10:00')
            appointment_type = request.POST.get('appointment_type', 'ROUTINE_CHECKUP')
            instructions = request.POST.get('instructions', '').strip()
            duration_minutes = int(request.POST.get('duration_minutes', 30))

            if not scheduled_date_str:
                messages.error(request, "Please select an appointment date for the next hospital visit.")
                active_step = '3'
            else:
                try:
                    scheduled_date = datetime.date.fromisoformat(scheduled_date_str)
                    appt = Appointment.objects.create(
                        doctor=doctor,
                        patient=patient,
                        appointment_type=appointment_type,
                        scheduled_date=scheduled_date,
                        scheduled_time=scheduled_time_str,
                        duration_minutes=duration_minutes,
                        status='UPCOMING',
                        instructions=instructions
                    )

                    notify_patient_profile(
                        patient=patient,
                        notification_type='APPOINTMENT',
                        title=f'Next Hospital Visit Scheduled: {scheduled_date.strftime("%B %d, %Y")}',
                        message=f'Dr. {doctor.display_name} from {doctor.clinic_name} scheduled your next visit on {scheduled_date.strftime("%A, %B %d, %Y")} at {scheduled_time_str}. Instructions: {instructions or "Please bring previous X-rays and aligner sets."}',
                        link_url='/patient/appointments/'
                    )

                    PatientActivityLog.objects.create(
                        doctor=doctor,
                        patient=patient,
                        activity_type='Appointment Scheduled',
                        description=f'Scheduled next hospital appointment on {scheduled_date} at {scheduled_time_str}'
                    )
                    messages.success(request, f"Step 3 Complete: Hospital appointment scheduled for {scheduled_date.strftime('%B %d, %Y')} at {scheduled_time_str}. Patient notification sent!")
                    return redirect(f"{reverse('doctor:patient_clinical_journey', kwargs={'patient_id': patient.id})}?step=3")
                except Exception as e:
                    messages.error(request, f"Error scheduling appointment: {str(e)}")
                    active_step = '3'

        # Delete actions from within the journey page
        elif action == 'delete_preop_inline':
            photo_id = request.POST.get('photo_id')
            p_obj = patient.preoperative_photos.filter(id=photo_id).first()
            if p_obj:
                p_obj.photo.delete(save=False)
                p_obj.delete()
                messages.info(request, "Preoperative photo removed.")
            return redirect(f"{reverse('doctor:patient_clinical_journey', kwargs={'patient_id': patient.id})}?step=1")

        elif action == 'delete_radiograph_inline':
            radio_id = request.POST.get('radio_id')
            r_obj = patient.radiographs.filter(id=radio_id).first()
            if r_obj:
                r_obj.image.delete(save=False)
                r_obj.delete()
                messages.info(request, "Radiograph record removed.")
            return redirect(f"{reverse('doctor:patient_clinical_journey', kwargs={'patient_id': patient.id})}?step=2")

    preop_photos = patient.preoperative_photos.all()
    radiographs = patient.radiographs.all()
    upcoming_appointments = patient.appointments.filter(scheduled_date__gte=timezone.localdate()).order_by('scheduled_date', 'scheduled_time')

    opg_radiographs = radiographs.filter(radiograph_type__in=['OPG', 'TYPE_1'])
    ceph_radiographs = radiographs.filter(radiograph_type__in=['LATERAL_CEPHALOGRAPH', 'TYPE_2'])

    context = {
        'patient': patient,
        'treatment_plan': treatment_plan,
        'doctor': doctor,
        'active_step': str(active_step),
        'preop_form': preop_form,
        'radiograph_form': radiograph_form,
        'preop_photos': preop_photos,
        'radiographs': radiographs,
        'opg_radiographs': opg_radiographs,
        'ceph_radiographs': ceph_radiographs,
        'upcoming_appointments': upcoming_appointments,
        'default_20day_date': default_20day_date,
        'preop_count': preop_photos.count(),
        'has_3_preop': preop_photos.count() >= 3,
        'has_radiograph': radiographs.exists(),
        'has_next_appt': upcoming_appointments.exists(),
    }
    return render(request, 'doctor/treatment/patient_clinical_journey.html', context)


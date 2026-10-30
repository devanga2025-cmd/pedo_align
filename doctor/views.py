from django.shortcuts import render, redirect, get_object_or_404
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
    ClinicalRecord, TreatmentPlan, PhotoMonitoring,
    EmergencyAlert, Appointment, Notification, PatientActivityLog,
    generate_joining_code
)
from .forms import (
    DoctorRegistrationForm, DoctorLoginForm, DoctorProfileForm,
    PatientForm, PatientEditForm, ClinicalRecordForm, TreatmentPlanForm,
    PhotoMonitoringReviewForm, PhotoUploadForm, EmergencyResponseForm,
    EmergencyCreateForm, AppointmentForm, SendReminderInstructionForm,
    PatientJoinCodeForm
)


# Helper: get doctor or redirect
def get_doctor_or_none(user):
    if not user.is_authenticated:
        return None
    try:
        return user.doctor_profile
    except DoctorProfile.DoesNotExist:
        return None


# ----------------- AUTHENTICATION -----------------

def doctor_login_view(request):
    if request.user.is_authenticated and hasattr(request.user, 'doctor_profile'):
        return redirect('doctor:dashboard')

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
                    messages.success(request, f"Welcome back, Dr. {user.doctor_profile.full_name}!")
                    next_url = request.GET.get('next')
                    return redirect(next_url or 'doctor:dashboard')
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
    doctor = get_doctor_or_none(request.user)
    if not doctor:
        messages.error(request, "Doctor profile required.")
        return redirect('doctor:login')

    # Strict doctor isolation
    patients_qs = Patient.objects.filter(doctor=doctor)
    total_patients = patients_qs.count()
    active_treatments = patients_qs.filter(treatment_status='ACTIVE').count()
    completed_treatments = patients_qs.filter(treatment_status='COMPLETED').count()

    pending_approvals = PatientJoiningCode.objects.filter(
        doctor=doctor, status='PENDING_APPROVAL'
    ).count()

    emergency_alerts_count = EmergencyAlert.objects.filter(
        patient__doctor=doctor, status__in=['PENDING', 'IN_REVIEW']
    ).count()

    today = timezone.localdate()
    upcoming_appointments_qs = Appointment.objects.filter(
        doctor=doctor,
        scheduled_date__gte=today,
        status='UPCOMING'
    ).order_by('scheduled_date', 'scheduled_time')
    upcoming_appointments_count = upcoming_appointments_qs.count()

    # Recent lists
    recent_patients = patients_qs.order_by('-created_at')[:5]
    recent_activities = PatientActivityLog.objects.filter(doctor=doctor).order_by('-created_at')[:6]
    upcoming_appointments_list = upcoming_appointments_qs[:5]
    recent_emergencies = EmergencyAlert.objects.filter(
        patient__doctor=doctor
    ).order_by('-reported_at')[:4]

    # Chart data
    # 1. Patient status breakdown
    status_counts = {
        'Active': active_treatments,
        'Pending Connection': patients_qs.filter(treatment_status='PENDING_CONNECTION').count(),
        'On Hold': patients_qs.filter(treatment_status='ON_HOLD').count(),
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
        'active_treatments': active_treatments,
        'completed_treatments': completed_treatments,
        'pending_approvals': pending_approvals,
        'emergency_alerts_count': emergency_alerts_count,
        'upcoming_appointments_count': upcoming_appointments_count,
        'recent_patients': recent_patients,
        'recent_activities': recent_activities,
        'upcoming_appointments_list': upcoming_appointments_list,
        'recent_emergencies': recent_emergencies,
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
    if status_filter != 'ALL' and status_filter in dict(Patient.STATUS_CHOICES):
        patients_qs = patients_qs.filter(treatment_status=status_filter)

    # View style: table or grid
    view_mode = request.GET.get('view', 'grid')

    context = {
        'doctor': doctor,
        'patients': patients_qs,
        'query': query,
        'status_filter': status_filter,
        'view_mode': view_mode,
        'total_count': Patient.objects.filter(doctor=doctor).count(),
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

        # Initialize Default Clinical Record
        ClinicalRecord.objects.create(
            patient=patient,
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

    return render(request, 'doctor/patients/patient_create.html', {'form': form, 'doctor': doctor})


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

    context = {
        'doctor': doctor,
        'patient': patient,
        'clinical_record': clinical_record,
        'treatment_plan': treatment_plan,
        'joining_code': joining_code,
        'photo_uploads': photo_uploads,
        'before_photos': before_photos,
        'after_photos': after_photos,
        'appointments': appointments,
        'emergencies': emergencies,
        'activity_logs': activity_logs,
        'active_tab': active_tab,
    }
    return render(request, 'doctor/patients/patient_detail.html', context)


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
            from patient.models import PatientNotification
            for p_profile in code_obj.requesting_patient_profiles.all():
                p_profile.connected_patient_record = patient
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
    form = PatientJoinCodeForm(request.POST or None)
    success_info = None

    if request.method == 'POST' and form.is_valid():
        code_str = form.cleaned_data['joining_code'].strip().upper()
        first_name = form.cleaned_data['patient_first_name'].strip()
        last_name = form.cleaned_data['patient_last_name'].strip()
        phone = form.cleaned_data['phone'].strip()
        notes = form.cleaned_data.get('request_notes', '')

        code_obj = PatientJoiningCode.objects.filter(code__iexact=code_str).first()

        if not code_obj:
            form.add_error('joining_code', "Invalid Joining Code. Please double check the code provided by your orthodontist.")
        elif code_obj.status == 'APPROVED':
            form.add_error('joining_code', "This joining code has already been claimed and approved.")
        elif code_obj.status == 'PENDING_APPROVAL':
            form.add_error('joining_code', "This code is already pending approval from the doctor.")
        elif code_obj.is_expired():
            form.add_error('joining_code', "This joining code has expired. Please contact your doctor for a new code.")
        else:
            # Code is valid and active!
            code_obj.status = 'PENDING_APPROVAL'
            code_obj.claimed_at = timezone.now()
            code_obj.patient_request_notes = notes
            code_obj.save()

            # Update patient record with latest details if provided
            patient = code_obj.patient
            if first_name:
                patient.first_name = first_name
            if last_name:
                patient.last_name = last_name
            if phone:
                patient.phone = phone
            patient.save()

            # Notify doctor
            Notification.objects.create(
                doctor=code_obj.doctor,
                patient=patient,
                notification_type='PATIENT_REQUEST',
                title=f'New Connection Request: {patient.full_name}',
                message=f'Patient entered Joining Code {code_obj.code}. Please review and approve their connection.',
                link_url=f'/requests/'
            )

            PatientActivityLog.objects.create(
                patient=patient,
                doctor=code_obj.doctor,
                activity_type='Joining Code Entered',
                description=f"Patient registered joining code {code_obj.code}. Connection request sent to doctor."
            )

            success_info = {
                'doctor_name': code_obj.doctor.full_name,
                'clinic_name': code_obj.doctor.clinic_name,
                'patient_name': patient.full_name,
                'code': code_obj.code,
            }

    return render(request, 'doctor/public/join_portal.html', {'form': form, 'success_info': success_info})


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

    status_filter = request.GET.get('status', 'ALL')
    if status_filter != 'ALL':
        plans_qs = plans_qs.filter(status=status_filter)

    query = request.GET.get('q', '').strip()
    if query:
        plans_qs = plans_qs.filter(
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__patient_id__icontains=query)
        )

    context = {
        'doctor': doctor,
        'plans': plans_qs,
        'status_filter': status_filter,
        'query': query,
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

    form = TreatmentPlanForm(request.POST or None, instance=plan)
    if request.method == 'POST' and form.is_valid():
        updated_plan = form.save()
        # If aligner reached total, could mark as completed
        if updated_plan.current_aligner >= updated_plan.total_aligners and updated_plan.status == 'Completed':
            patient.treatment_status = 'COMPLETED'
            patient.save()

        PatientActivityLog.objects.create(
            patient=patient,
            doctor=doctor,
            activity_type='Treatment Plan Updated',
            description=f"Aligner stage set to #{updated_plan.current_aligner}/{updated_plan.total_aligners}. Status: {updated_plan.status}"
        )
        messages.success(request, f"Treatment plan for {patient.full_name} saved successfully.")
        return redirect('doctor:patient_detail', patient_id=patient.id)

    return render(request, 'doctor/treatment/treatment_plan_edit.html', {
        'form': form,
        'patient': patient,
        'plan': plan,
        'doctor': doctor
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
            plan.current_aligner += 1
            plan.save()
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

    context = {
        'doctor': doctor,
        'uploads': uploads_qs,
        'status_filter': status_filter,
        'query': query,
        'status_choices': PhotoMonitoring.TRACKING_STATUS_CHOICES,
    }
    return render(request, 'doctor/photos/photo_monitoring_list.html', context)


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
    photos = PhotoMonitoring.objects.filter(patient=patient).order_by('upload_date')

    before_photo = photos.filter(is_before_sample=True).first() or photos.first()
    latest_photo = photos.filter(is_after_sample=True).first() or photos.last()

    context = {
        'doctor': doctor,
        'patient': patient,
        'photos': photos,
        'before_photo': before_photo,
        'latest_photo': latest_photo,
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
    response['Content-Disposition'] = f'attachment; filename="PedoAlign_Patients_{timezone.localdate()}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Patient ID', 'First Name', 'Last Name', 'Age', 'Gender',
        'Phone', 'Email', 'Parent/Guardian', 'Treatment Status',
        'Current Aligner', 'Total Aligners', 'Compliance Score (%)',
        'Joining Code', 'Created Date'
    ])

    patients = Patient.objects.filter(doctor=doctor).select_related('treatment_plan', 'joining_code')
    for p in patients:
        plan = getattr(p, 'treatment_plan', None)
        code = getattr(p, 'joining_code', None)
        writer.writerow([
            p.patient_id,
            p.first_name,
            p.last_name,
            p.age,
            p.gender,
            p.phone,
            p.email or 'N/A',
            p.parent_guardian_name or 'N/A',
            p.get_treatment_status_display(),
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

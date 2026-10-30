from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from .models import PatientProfile, PatientNotification
from .forms import (
    PatientLoginForm, PatientRegistrationForm, DoctorConnectCodeForm,
    TeethPhotoUploadForm, PatientAppointmentRequestForm, PatientEmergencyReportForm,
    PatientProfileEditForm
)
from doctor.models import (
    DoctorProfile, Patient as ClinicalPatient, PatientJoiningCode,
    TreatmentPlan, PhotoMonitoring, EmergencyAlert, Appointment, Notification as DoctorNotification
)


def get_patient_profile_or_none(user):
    if not user.is_authenticated:
        return None
    return getattr(user, 'patient_profile', None)


# ----------------- AUTHENTICATION -----------------

def patient_login_view(request):
    if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
        return redirect('patient:dashboard')

    form = PatientLoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ident = form.cleaned_data['login_identifier'].strip()
        pwd = form.cleaned_data['password']
        remember = form.cleaned_data.get('remember_me', False)

        # Look up by email or patient_id
        user_obj = None
        if '@' in ident:
            user_obj = User.objects.filter(Q(email__iexact=ident) | Q(username__iexact=ident)).first()
        else:
            profile = PatientProfile.objects.filter(patient_id__iexact=ident).first()
            if profile:
                user_obj = profile.user

        if user_obj:
            user = authenticate(request, username=user_obj.username, password=pwd)
            if user:
                if not hasattr(user, 'patient_profile'):
                    messages.error(request, "This account is registered as a Doctor. Please log in through the Doctor Portal.")
                    return redirect('doctor:login')

                login(request, user)
                if not remember:
                    request.session.set_expiry(0)
                messages.success(request, f"Welcome back, {user.patient_profile.full_name}!")
                return redirect('patient:dashboard')
            else:
                messages.error(request, "Incorrect password. Please verify and try again.")
        else:
            messages.error(request, "No patient account found with that Email or Patient ID.")

    return render(request, 'patient/auth/login.html', {'form': form})


def patient_register_view(request):
    if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
        return redirect('patient:dashboard')

    form = PatientRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        full_name = form.cleaned_data['full_name'].strip()
        email = form.cleaned_data['email'].strip().lower()
        dob = form.cleaned_data['date_of_birth']
        phone = form.cleaned_data['mobile_number'].strip()
        pwd = form.cleaned_data['password']

        user = User.objects.create_user(
            username=email,
            email=email,
            password=pwd,
            first_name=full_name.split()[0] if full_name else '',
            last_name=' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else ''
        )

        patient_profile = PatientProfile.objects.create(
            user=user,
            full_name=full_name,
            date_of_birth=dob,
            phone_number=phone
        )

        # Welcome notification
        PatientNotification.objects.create(
            patient=patient_profile,
            notification_type='TREATMENT_UPDATE',
            title='Welcome to PEDO ALIGN!',
            message=f'Your Patient ID is {patient_profile.patient_id}. Connect with your doctor using your unique joining code to activate aligner tracking.'
        )

        login(request, user)
        messages.success(request, f"Registration complete! Your Patient ID is {patient_profile.patient_id}.")
        return redirect('patient:dashboard')

    return render(request, 'patient/auth/register.html', {'form': form})


def patient_logout_view(request):
    logout(request)
    messages.info(request, "You have been safely signed out.")
    return redirect('patient:login')


def patient_forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        messages.success(request, f"If an account exists for {email}, password recovery instructions have been sent.")
        return redirect('patient:login')
    return render(request, 'patient/auth/forgot_password.html')


# ----------------- PATIENT DASHBOARD & DOCTOR CONNECTION -----------------

@login_required(login_url='patient:login')
def patient_dashboard_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        messages.error(request, "Patient profile not found. Please log in as a patient.")
        return redirect('patient:login')

    # Doctor connection status
    doctor = patient.doctor
    treatment_plan = patient.treatment_plan
    connected_record = patient.connected_patient_record

    next_appointment = None
    latest_photos = None
    days_until_next_change = None
    progress_percent = 0

    if patient.is_connected and connected_record:
        # Appointments
        next_appointment = Appointment.objects.filter(
            patient=connected_record,
            scheduled_date__gte=timezone.now().date(),
            status__in=['CONFIRMED', 'SCHEDULED', 'REQUESTED']
        ).order_by('scheduled_date', 'scheduled_time').first()

        # Latest Photo upload
        latest_photos = PhotoMonitoring.objects.filter(
            patient=connected_record
        ).order_by('-week_number', '-upload_date').first()

        # Treatment metrics
        if treatment_plan:
            total = treatment_plan.total_aligners or 1
            curr = treatment_plan.current_aligner or 1
            progress_percent = min(100, int((curr / total) * 100))

            if treatment_plan.next_review_date:
                diff = (treatment_plan.next_review_date - timezone.now().date()).days
                days_until_next_change = max(0, diff)

    context = {
        'patient': patient,
        'doctor': doctor,
        'treatment_plan': treatment_plan,
        'connected_record': connected_record,
        'next_appointment': next_appointment,
        'latest_photos': latest_photos,
        'days_until_next_change': days_until_next_change,
        'progress_percent': progress_percent,
        'today': timezone.now().date(),
    }
    return render(request, 'patient/dashboard.html', context)


@login_required(login_url='patient:login')
def connect_doctor_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return redirect('patient:login')

    if patient.is_connected:
        messages.info(request, f"You are already connected to Dr. {patient.doctor.full_name}.")
        return redirect('patient:dashboard')

    form = DoctorConnectCodeForm(request.POST or None)
    verified_code = None

    if request.method == 'POST' and form.is_valid():
        code_str = form.cleaned_data['joining_code'].strip().upper()
        notes = form.cleaned_data.get('notes', '')

        code_obj = PatientJoiningCode.objects.filter(code__iexact=code_str).first()
        is_expired = False
        if code_obj:
            is_expired = code_obj.is_expired() if callable(getattr(code_obj, 'is_expired', None)) else getattr(code_obj, 'is_expired', False)

        if not code_obj:
            form.add_error('joining_code', "Invalid joining code. Please double-check the code provided by your clinic.")
        elif code_obj.status == 'EXPIRED' or is_expired:
            form.add_error('joining_code', "This joining code has expired. Please ask your orthodontist to generate a new code.")
        elif code_obj.status in ['APPROVED', 'PENDING_APPROVAL']:
            form.add_error('joining_code', "This joining code has already been claimed.")
        elif code_obj.status == 'REVOKED':
            form.add_error('joining_code', "This joining code has been revoked.")
        else:
            # Code is valid and pending claim
            code_obj.status = 'PENDING_APPROVAL'
            code_obj.claimed_at = timezone.now()
            code_obj.patient_request_notes = notes
            code_obj.save()

            patient.pending_code = code_obj
            patient.connection_status = 'PENDING_APPROVAL'
            patient.requested_at = timezone.now()
            patient.save()

            # Notify the treating doctor in Doctor Portal
            DoctorNotification.objects.create(
                doctor=code_obj.doctor,
                patient=code_obj.patient,
                notification_type='PATIENT_REQUEST',
                title=f'Connection Request: {patient.full_name}',
                message=f'Patient {patient.full_name} entered joining code {code_obj.code}. Please approve the connection to grant access to treatment monitoring.',
                link_url='/requests/'
            )

            # Notify the patient
            PatientNotification.objects.create(
                patient=patient,
                notification_type='TREATMENT_UPDATE',
                title='Connection Request Sent!',
                message=f'Your joining code {code_obj.code} was verified for Dr. {code_obj.doctor.full_name}. We have notified the doctor for final approval.'
            )

            messages.success(request, f"Code verified! Request sent to Dr. {code_obj.doctor.full_name}. Once approved by the doctor, your treatment plan will be accessible.")
            return redirect('patient:dashboard')

    context = {
        'patient': patient,
        'form': form,
    }
    return render(request, 'patient/connect_doctor.html', context)


# ----------------- MY TREATMENT -----------------

@login_required(login_url='patient:login')
def my_treatment_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return redirect('patient:login')

    if not patient.is_connected:
        messages.warning(request, "Please connect with your doctor to access your treatment plan.")
        return redirect('patient:connect_doctor')

    plan = patient.treatment_plan
    record = patient.connected_patient_record

    # Build stage timeline
    stages = []
    if plan and plan.total_aligners:
        total = plan.total_aligners
        curr = plan.current_aligner or 1
        freq = getattr(plan, 'aligner_frequency_days', None) or getattr(plan, 'aligner_changing_frequency_days', 14) or 14

        start_date = getattr(plan, 'start_date', None) or getattr(plan, 'treatment_start_date', None) or (timezone.now().date() - timedelta(days=curr * freq))

        for i in range(1, total + 1):
            stage_date = start_date + timedelta(days=(i - 1) * freq)
            if i < curr:
                status = 'COMPLETED'
            elif i == curr:
                status = 'ACTIVE'
            else:
                status = 'UPCOMING'
            stages.append({
                'aligner_number': i,
                'status': status,
                'target_date': stage_date,
            })

    context = {
        'patient': patient,
        'doctor': patient.doctor,
        'record': record,
        'plan': plan,
        'stages': stages,
    }
    return render(request, 'patient/my_treatment.html', context)


# ----------------- UPLOAD TEETH PHOTOS -----------------

@login_required(login_url='patient:login')
def upload_photos_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return redirect('patient:login')

    if not patient.is_connected:
        messages.warning(request, "Please connect with your doctor before uploading teeth photos.")
        return redirect('patient:connect_doctor')

    record = patient.connected_patient_record
    plan = patient.treatment_plan

    initial_week = 1
    latest = PhotoMonitoring.objects.filter(patient=record).order_by('-week_number').first()
    if latest:
        initial_week = latest.week_number + 1
    elif plan and plan.current_aligner:
        initial_week = plan.current_aligner

    form = TeethPhotoUploadForm(request.POST or None, request.FILES or None, initial={'week_number': initial_week})

    if request.method == 'POST' and form.is_valid():
        week_num = form.cleaned_data['week_number']
        notes = form.cleaned_data.get('patient_notes', '')

        # Create photo monitoring record
        curr_stage = getattr(plan, 'current_aligner', 1) or 1
        photo_record = PhotoMonitoring.objects.create(
            patient=record,
            week_number=week_num,
            aligner_stage=curr_stage,
            front_bite_photo=form.cleaned_data['photo_front'],
            left_occlusion_photo=form.cleaned_data.get('photo_left'),
            right_occlusion_photo=form.cleaned_data.get('photo_right'),
            upper_arch_photo=form.cleaned_data.get('photo_upper'),
            lower_arch_photo=form.cleaned_data.get('photo_lower'),
            patient_notes=notes,
            upload_date=timezone.now().date(),
            tracking_status='PENDING_REVIEW'
        )

        # Notify the treating doctor in Doctor Portal
        DoctorNotification.objects.create(
            doctor=patient.doctor,
            patient=record,
            notification_type='PHOTO_SUBMITTED',
            title=f'New Photos: {patient.full_name} (Week {week_num})',
            message=f'Patient {patient.full_name} submitted week {week_num} aligner tracking photos for review.',
            link_url=f'/photos/{photo_record.id}/review/'
        )

        # Notify the patient
        PatientNotification.objects.create(
            patient=patient,
            notification_type='PHOTO_SUBMISSION',
            title=f'Week {week_num} Photos Received!',
            message=f'Your photos were successfully sent to Dr. {patient.doctor.full_name}. You will be notified once the doctor completes review.'
        )

        messages.success(request, f"Awesome job! Your Week {week_num} photos have been sent to Dr. {patient.doctor.full_name}.")
        return redirect('patient:progress')

    recent_uploads = PhotoMonitoring.objects.filter(patient=record).order_by('-week_number')[:5]

    context = {
        'patient': patient,
        'doctor': patient.doctor,
        'form': form,
        'recent_uploads': recent_uploads,
    }
    return render(request, 'patient/upload_photos.html', context)


# ----------------- TREATMENT PROGRESS -----------------

@login_required(login_url='patient:login')
def treatment_progress_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return redirect('patient:login')

    if not patient.is_connected:
        messages.warning(request, "Please connect with your doctor to view progress.")
        return redirect('patient:connect_doctor')

    record = patient.connected_patient_record
    plan = patient.treatment_plan

    all_photos = PhotoMonitoring.objects.filter(patient=record).order_by('week_number')
    baseline_photo = all_photos.first()
    latest_photo = all_photos.last()

    total_aligners = plan.total_aligners if plan else 20
    current_aligner = plan.current_aligner if plan else 1
    completed_stages = max(0, current_aligner - 1)
    remaining_stages = max(0, total_aligners - current_aligner)
    progress_percent = min(100, int((current_aligner / total_aligners) * 100))

    # Badges calculation
    badges = [
        {
            'name': 'Starter Smile',
            'desc': 'Connected with doctor & started treatment',
            'earned': True,
            'icon': 'fa-solid fa-seedling',
            'color': 'bg-emerald-500'
        },
        {
            'name': 'Photo Pro',
            'desc': 'Submitted first weekly teeth photo',
            'earned': all_photos.count() >= 1,
            'icon': 'fa-solid fa-camera',
            'color': 'bg-blue-500'
        },
        {
            'name': 'Consistency Star',
            'desc': 'Submitted 3+ tracking photo reviews',
            'earned': all_photos.count() >= 3,
            'icon': 'fa-solid fa-star',
            'color': 'bg-amber-500'
        },
        {
            'name': 'Halfway Hero',
            'desc': 'Completed 50% or more of aligner therapy',
            'earned': progress_percent >= 50,
            'icon': 'fa-solid fa-medal',
            'color': 'bg-purple-500'
        },
        {
            'name': 'Alignment Champion',
            'desc': 'Completed full orthodontic aligner series',
            'earned': progress_percent >= 100,
            'icon': 'fa-solid fa-trophy',
            'color': 'bg-rose-500'
        },
    ]

    context = {
        'patient': patient,
        'doctor': patient.doctor,
        'plan': plan,
        'all_photos': all_photos,
        'baseline_photo': baseline_photo,
        'latest_photo': latest_photo,
        'total_aligners': total_aligners,
        'current_aligner': current_aligner,
        'completed_stages': completed_stages,
        'remaining_stages': remaining_stages,
        'progress_percent': progress_percent,
        'badges': badges,
    }
    return render(request, 'patient/progress.html', context)


# ----------------- APPOINTMENTS -----------------

@login_required(login_url='patient:login')
def appointments_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return redirect('patient:login')

    if not patient.is_connected:
        messages.warning(request, "Please connect with your doctor to manage appointments.")
        return redirect('patient:connect_doctor')

    record = patient.connected_patient_record
    today = timezone.now().date()

    upcoming_appointments = Appointment.objects.filter(
        patient=record,
        scheduled_date__gte=today
    ).order_by('scheduled_date', 'scheduled_time')

    past_appointments = Appointment.objects.filter(
        patient=record,
        scheduled_date__lt=today
    ).order_by('-scheduled_date', '-scheduled_time')

    context = {
        'patient': patient,
        'doctor': patient.doctor,
        'upcoming_appointments': upcoming_appointments,
        'past_appointments': past_appointments,
    }
    return render(request, 'patient/appointments/appointments.html', context)


@login_required(login_url='patient:login')
def appointment_request_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient or not patient.is_connected:
        return redirect('patient:appointments')

    form = PatientAppointmentRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        appt_date = form.cleaned_data['appointment_date']
        appt_time = form.cleaned_data['preferred_time']
        reason = form.cleaned_data['reason']
        notes = form.cleaned_data.get('notes', '')

        appt = Appointment.objects.create(
            doctor=patient.doctor,
            patient=patient.connected_patient_record,
            scheduled_date=appt_date,
            scheduled_time=appt_time,
            appointment_type=reason,
            status='REQUESTED',
            notes=f"Requested by patient via portal: {notes}"
        )

        DoctorNotification.objects.create(
            doctor=patient.doctor,
            patient=patient.connected_patient_record,
            notification_type='APPOINTMENT',
            title=f'Appointment Request: {patient.full_name}',
            message=f'{patient.full_name} requested an appointment on {appt_date} at {appt_time}.',
            link_url='/appointments/'
        )

        PatientNotification.objects.create(
            patient=patient,
            notification_type='APPOINTMENT',
            title='Appointment Request Submitted',
            message=f'Your request for an appointment on {appt_date} has been sent to Dr. {patient.doctor.full_name}. The clinic will confirm shortly.'
        )

        messages.success(request, f"Appointment request sent for {appt_date}! The clinic will confirm your booking.")
        return redirect('patient:appointments')

    return render(request, 'patient/appointments/request.html', {'patient': patient, 'form': form})


@login_required(login_url='patient:login')
def appointment_reschedule_view(request, appt_id):
    patient = get_patient_profile_or_none(request.user)
    if not patient or not patient.is_connected:
        return redirect('patient:appointments')

    appt = get_object_or_404(Appointment, id=appt_id, patient=patient.connected_patient_record)

    if request.method == 'POST':
        new_date = request.POST.get('new_date')
        new_time = request.POST.get('new_time', '10:00')
        reason = request.POST.get('reason', '')

        appt.scheduled_date = new_date
        appt.scheduled_time = new_time
        appt.notes += f"\n[Reschedule Request to {new_date} {new_time}: {reason}]"
        appt.status = 'REQUESTED'
        appt.save()

        DoctorNotification.objects.create(
            doctor=patient.doctor,
            patient=patient.connected_patient_record,
            notification_type='APPOINTMENT',
            title=f'Reschedule Request: {patient.full_name}',
            message=f'{patient.full_name} requested rescheduling appointment #{appt.id} to {new_date}.',
            link_url='/appointments/'
        )

        messages.success(request, "Your rescheduling request has been submitted to the clinic.")
        return redirect('patient:appointments')

    return render(request, 'patient/appointments/reschedule.html', {'patient': patient, 'appointment': appt})


# ----------------- NOTIFICATIONS -----------------

@login_required(login_url='patient:login')
def notifications_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return redirect('patient:login')

    notifications = patient.notifications.all()
    unread_count = notifications.filter(is_read=False).count()

    context = {
        'patient': patient,
        'notifications': notifications,
        'unread_count': unread_count,
    }
    return render(request, 'patient/notifications.html', context)


@login_required(login_url='patient:login')
def mark_notification_read_view(request, notif_id):
    patient = get_patient_profile_or_none(request.user)
    if patient:
        notif = get_object_or_404(PatientNotification, id=notif_id, patient=patient)
        notif.is_read = True
        notif.save()
    return redirect('patient:notifications')


# ----------------- EMERGENCY & HELP -----------------

@login_required(login_url='patient:login')
def emergency_help_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return redirect('patient:login')

    if not patient.is_connected:
        messages.warning(request, "Please connect with your doctor to submit emergency clinical alerts.")
        return redirect('patient:connect_doctor')

    form = PatientEmergencyReportForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        prob = form.cleaned_data['problem_type']
        sev = form.cleaned_data['severity']
        desc = form.cleaned_data['description']
        photo = form.cleaned_data.get('photo')

        # Map problem to choices
        valid_issues = ['TOOTH_PAIN', 'ALIGNER_DISCOMFORT', 'BROKEN_ALIGNER', 'LOOSE_ALIGNER', 'OTHER']
        mapped_issue = prob if prob in valid_issues else 'OTHER'

        alert = EmergencyAlert.objects.create(
            patient=patient.connected_patient_record,
            issue_type=mapped_issue,
            severity=sev if sev in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] else 'MEDIUM',
            description=f"Patient Report via Portal: {desc}",
            status='PENDING'
        )

        # Notify Doctor
        DoctorNotification.objects.create(
            doctor=patient.doctor,
            patient=patient.connected_patient_record,
            notification_type='EMERGENCY',
            title=f'URGENT: {patient.full_name} reported {mapped_issue.replace("_", " ")}',
            message=f'Emergency issue reported: {desc[:120]}...',
            link_url='/emergencies/'
        )

        PatientNotification.objects.create(
            patient=patient,
            notification_type='DOCTOR_INSTRUCTION',
            title='Emergency Alert Received by Clinic',
            message=f'Dr. {patient.doctor.full_name} has been alerted to your {mapped_issue.replace("_", " ")} report.'
        )

        messages.success(request, "Your emergency alert has been sent directly to your doctor.")
        return redirect('patient:dashboard')

    recent_alerts = EmergencyAlert.objects.filter(
        patient=patient.connected_patient_record
    ).order_by('-reported_at')[:3]

    context = {
        'patient': patient,
        'doctor': patient.doctor,
        'form': form,
        'recent_alerts': recent_alerts,
    }
    return render(request, 'patient/emergency.html', context)


# ----------------- MY PROFILE & SETTINGS -----------------

@login_required(login_url='patient:login')
def my_profile_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return redirect('patient:login')

    form = PatientProfileEditForm(request.POST or None, request.FILES or None, instance=patient)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Profile details updated successfully!")
        return redirect('patient:profile')

    treatment_history = []
    if patient.is_connected and patient.connected_patient_record:
        treatment_history = PhotoMonitoring.objects.filter(
            patient=patient.connected_patient_record
        ).order_by('-week_number')

    context = {
        'patient': patient,
        'doctor': patient.doctor,
        'form': form,
        'treatment_history': treatment_history,
    }
    return render(request, 'patient/profile.html', context)


@login_required(login_url='patient:login')
def change_password_view(request):
    if request.method == 'POST':
        old_pwd = request.POST.get('old_password')
        new_pwd = request.POST.get('new_password')
        confirm_pwd = request.POST.get('confirm_password')

        if not request.user.check_password(old_pwd):
            messages.error(request, "Current password is incorrect.")
        elif len(new_pwd) < 8:
            messages.error(request, "New password must be at least 8 characters.")
        elif new_pwd != confirm_pwd:
            messages.error(request, "New passwords do not match.")
        else:
            request.user.set_password(new_pwd)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully!")
            return redirect('patient:profile')

    return redirect('patient:profile')

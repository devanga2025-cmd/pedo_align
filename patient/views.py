from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from .models import PatientProfile, PatientNotification
from .forms import (
    PatientLoginForm, PatientCodeLoginForm, PatientRegistrationForm, DoctorConnectCodeForm,
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
    try:
        profile = getattr(user, 'patient_profile', None)
        if profile:
            return profile
    except Exception:
        pass

    profile = PatientProfile.objects.filter(user=user).first()
    if profile:
        return profile

    # If this user is not a doctor, auto-create patient profile so dashboard opens directly
    if not hasattr(user, 'doctor_profile'):
        profile = PatientProfile.objects.create(
            user=user,
            patient_id=f'PA-P{str(user.id).zfill(4)}',
            full_name=user.get_full_name() or user.username,
            phone_number=''
        )
        auto_connect_patient_profile(profile)
        return profile
    return None


def auto_connect_patient_profile(profile):
    """
    Ensures that when a patient logs in, their profile is automatically connected
    to their clinical record in the doctor portal so they directly open the dashboard.
    """
    if not profile:
        return None

    # 1. Already connected with valid clinical record
    if profile.connected_patient_record and profile.connection_status == 'CONNECTED':
        return profile.connected_patient_record

    # 2. Record linked but connection_status was not 'CONNECTED'
    if profile.connected_patient_record:
        if not profile.connected_patient_record.is_archived and not profile.connected_patient_record.is_deactivated:
            profile.connection_status = 'CONNECTED'
            if profile.pending_code:
                profile.pending_code.status = 'APPROVED'
                profile.pending_code.save()
            profile.save()
            return profile.connected_patient_record

    # 3. Code attached to profile
    if profile.pending_code and profile.pending_code.patient:
        clin = profile.pending_code.patient
        if not clin.is_archived and not clin.is_deactivated:
            profile.connected_patient_record = clin
            profile.connection_status = 'CONNECTED'
            profile.pending_code.status = 'APPROVED'
            profile.pending_code.save()
            profile.save()
            return clin

    # 4. Search by email or phone
    user_email = (profile.user.email or '').strip().lower()
    clinical = None
    if user_email:
        clinical = ClinicalPatient.objects.filter(email__iexact=user_email, is_archived=False).first()
    if not clinical and profile.phone_number:
        clinical = ClinicalPatient.objects.filter(phone=profile.phone_number, is_archived=False).first()

    if clinical and not clinical.is_archived and not clinical.is_deactivated:
        profile.connected_patient_record = clinical
        profile.connection_status = 'CONNECTED'
        joining_code = getattr(clinical, 'joining_code', None)
        if joining_code:
            joining_code.status = 'APPROVED'
            joining_code.save()
            profile.pending_code = joining_code
        profile.save()
        return clinical

    return profile.connected_patient_record


# ----------------- AUTHENTICATION -----------------

def patient_login_view(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'doctor_profile'):
            return redirect('doctor:dashboard')
        return redirect('patient:dashboard')

    login_type = request.POST.get('login_type')
    if not login_type:
        if 'joining_code' in request.POST:
            login_type = 'code'
        elif 'password' in request.POST and 'login_identifier' in request.POST:
            login_type = 'password'
        else:
            login_type = 'code'
    code_form = PatientCodeLoginForm(request.POST if request.method == 'POST' and login_type == 'code' else None)
    pwd_form = PatientLoginForm(request.POST if request.method == 'POST' and login_type == 'password' else None)

    if request.method == 'POST':
        # 1. Easy & Instant Login with Gmail + Joining Code
        if login_type == 'code':
            if code_form.is_valid():
                email = (code_form.cleaned_data.get('email', '') or '').strip().lower()
                code_str = code_form.cleaned_data['joining_code'].strip().upper()
                remember = code_form.cleaned_data.get('remember_me', True)

                code_obj = PatientJoiningCode.objects.filter(code__iexact=code_str).first()
                if not code_obj:
                    code_form.add_error('joining_code', "Invalid joining code. Please double-check the code provided by your dental clinic.")
                elif code_obj.is_expired():
                    code_form.add_error('joining_code', "This joining code has expired. Please ask your doctor to generate a new code.")
                elif code_obj.patient.is_deactivated or code_obj.patient.is_archived:
                    code_form.add_error('joining_code', "This patient account has been deleted / closed following treatment completion. Login credentials are no longer active.")
                else:
                    clinical_patient = code_obj.patient

                    # Determine primary user email
                    if email:
                        if not clinical_patient.email:
                            clinical_patient.email = email
                            clinical_patient.save()
                        user_email = email
                    else:
                        user_email = clinical_patient.email or f"patient{clinical_patient.id}@pedoalign.com"

                    # Get or create User
                    user = User.objects.filter(Q(email__iexact=user_email) | Q(username__iexact=user_email)).first()
                    if not user:
                        first = clinical_patient.first_name or user_email.split('@')[0].capitalize()
                        last = clinical_patient.last_name or ''
                        user = User.objects.create_user(
                            username=user_email,
                            email=user_email,
                            first_name=first,
                            last_name=last
                        )
                        user.set_unusable_password()
                        user.save()

                    # Get or create PatientProfile
                    profile, _ = PatientProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'patient_id': 'PA-P' + str(clinical_patient.id).zfill(4),
                            'full_name': clinical_patient.full_name,
                            'phone_number': clinical_patient.phone or '',
                        }
                    )

                    profile.connected_patient_record = clinical_patient
                    profile.pending_code = code_obj
                    profile.connection_status = 'CONNECTED'
                    code_obj.status = 'APPROVED'
                    code_obj.claimed_at = timezone.now()
                    code_obj.save()
                    profile.save()

                    # Ensure treatment plan exists
                    if not hasattr(clinical_patient, 'treatment_plan'):
                        TreatmentPlan.objects.create(
                            patient=clinical_patient,
                            total_aligners=20,
                            current_aligner=1,
                            aligner_frequency_days=14,
                            status='Active / In Progress'
                        )

                    login(request, user)
                    request.session.set_expiry(60 * 60 * 24 * 90)  # Persistent login for 90 days

                    messages.success(request, f"Welcome, {profile.full_name}! Your Treatment Dashboard is open.")
                    return redirect('patient:dashboard')

        # 2. Traditional Password Login
        elif login_type == 'password':
            if pwd_form.is_valid():
                ident = pwd_form.cleaned_data['login_identifier'].strip()
                pwd = pwd_form.cleaned_data['password']
                remember = pwd_form.cleaned_data.get('remember_me', True)

                user_obj = None
                if '@' in ident:
                    user_obj = User.objects.filter(Q(email__iexact=ident) | Q(username__iexact=ident)).first()
                else:
                    profile = PatientProfile.objects.filter(patient_id__iexact=ident).first()
                    if profile:
                        user_obj = profile.user

                if user_obj:
                    if not user_obj.is_active:
                        pwd_form.add_error(None, "This patient account has been deleted / closed following treatment completion. Login credentials are no longer active.")
                    else:
                        user = authenticate(request, username=user_obj.username, password=pwd)
                        if user:
                            if hasattr(user, 'doctor_profile'):
                                login(request, user)
                                request.session.set_expiry(60 * 60 * 24 * 90)  # 90 days
                                messages.success(request, f"Welcome back, Dr. {user.doctor_profile.full_name}!")
                                return redirect('doctor:dashboard')
                            elif hasattr(user, 'patient_profile'):
                                prof = user.patient_profile
                                if prof.connected_patient_record and (prof.connected_patient_record.is_deactivated or prof.connected_patient_record.is_archived):
                                    pwd_form.add_error(None, "This patient account has been deleted / closed following treatment completion. Login credentials are no longer active.")
                                else:
                                    auto_connect_patient_profile(prof)
                                    login(request, user)
                                    request.session.set_expiry(60 * 60 * 24 * 90)  # 90 days
                                    messages.success(request, f"Welcome back, {prof.full_name}!")
                                    return redirect('patient:dashboard')
                            else:
                                messages.error(request, "Account found but neither a doctor nor a patient profile is connected.")
                        else:
                            pwd_form.add_error('password', "Incorrect password. If you don't have a password yet, use the 'Joining Code' tab above!")
                else:
                    pwd_form.add_error('login_identifier', "No account found with that Email or Patient ID.")

    return render(request, 'patient/auth/login.html', {
        'code_form': code_form or PatientCodeLoginForm(),
        'pwd_form': pwd_form or PatientLoginForm(),
        'active_tab': login_type
    })


def patient_register_view(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'patient_profile'):
            return redirect('patient:dashboard')
        elif hasattr(request.user, 'doctor_profile'):
            return redirect('doctor:dashboard')

    form = PatientRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        full_name = form.cleaned_data['full_name'].strip()
        patient_category = form.cleaned_data.get('patient_category', 'CHILD')
        email = form.cleaned_data['email'].strip().lower()
        dob = form.cleaned_data['date_of_birth']
        phone = form.cleaned_data['mobile_number'].strip()
        parent_name = form.cleaned_data.get('parent_guardian_name', '').strip()
        parent_phone = form.cleaned_data.get('parent_guardian_phone', '').strip()
        parent_email = (form.cleaned_data.get('parent_guardian_email', '') or '').strip()
        parent_rel = form.cleaned_data.get('parent_guardian_relationship', 'Parent').strip()
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
            patient_category=patient_category,
            date_of_birth=dob,
            phone_number=phone,
            parent_guardian_name=parent_name,
            parent_guardian_phone=parent_phone,
            parent_guardian_email=parent_email,
            parent_guardian_relationship=parent_rel
        )

        # Check if doctor already created and approved a patient with this email or phone
        matching_clinical = ClinicalPatient.objects.filter(
            Q(email__iexact=email) | (Q(phone=phone) & ~Q(phone=''))
        ).first()

        if matching_clinical:
            # Sync category and parent info
            matching_clinical.patient_category = patient_category
            if parent_name and not matching_clinical.parent_guardian_name:
                matching_clinical.parent_guardian_name = parent_name
            if parent_phone and not matching_clinical.parent_guardian_phone:
                matching_clinical.parent_guardian_phone = parent_phone
            if parent_email and not matching_clinical.parent_guardian_email:
                matching_clinical.parent_guardian_email = parent_email
            matching_clinical.save()

            patient_profile.connected_patient_record = matching_clinical
            patient_profile.connection_status = 'CONNECTED'
            joining_code = getattr(matching_clinical, 'joining_code', None)
            if joining_code:
                joining_code.status = 'APPROVED'
                joining_code.save()
                patient_profile.pending_code = joining_code
            patient_profile.save()

        # Welcome notification
        if patient_profile.is_connected:
            PatientNotification.objects.create(
                patient=patient_profile,
                notification_type='TREATMENT_UPDATE',
                title='Welcome to Your Treatment Portal!',
                message=f'Your account is connected with Dr. {patient_profile.doctor.full_name}. Your aligner plan is active.'
            )
            messages.success(request, f"Welcome, {full_name}! You are connected with Dr. {patient_profile.doctor.full_name}.")
        else:
            PatientNotification.objects.create(
                patient=patient_profile,
                notification_type='TREATMENT_UPDATE',
                title='Welcome to PEDO ALIGN!',
                message=f'Your Patient ID is {patient_profile.patient_id}. Connect with your doctor using your unique joining code to activate aligner tracking.'
            )
            messages.success(request, f"Registration complete! Your Patient ID is {patient_profile.patient_id}.")

        login(request, user)
        request.session.set_expiry(60 * 60 * 24 * 90)  # Persistent login for 90 days
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


def sync_patient_reminders_from_schedule(patient):
    """
    Dynamically generates schedule-based notifications based on doctor's prescribed dates:
    1. Weekly Photo Upload Reminder
    2. Appointment Reminders (upcoming within 48h)
    3. Tray Changing Reminders (upcoming or due today)
    """
    if not patient or not patient.is_connected or not patient.connected_patient_record:
        return

    today = timezone.localdate()
    plan = getattr(patient.connected_patient_record, 'treatment_plan', None)
    doctor = patient.doctor
    if not doctor:
        return

    # 1. Tray Changing Reminder (Doctor prescribed next_tray_change_date)
    if plan:
        change_date = plan.computed_next_change_date
        if change_date and not plan.is_paused:
            days_to_change = (change_date - today).days
            if days_to_change <= 2:
                notif_title = f"Tray Change Alert: Tray #{plan.next_aligner}"
                already_exists = PatientNotification.objects.filter(
                    patient=patient,
                    notification_type='TRAY_CHANGE',
                    title=notif_title,
                    created_at__date__gte=today - timedelta(days=3)
                ).exists()

                if not already_exists:
                    if days_to_change == 0:
                        msg = f"Today is your scheduled tray change date! Dr. {doctor.full_name} prescribed switching to Tray #{plan.next_aligner}. Ensure your teeth are thoroughly cleaned before switching."
                    elif days_to_change > 0:
                        msg = f"Reminder: Your next tray change to Tray #{plan.next_aligner} is in {days_to_change} day(s) on {change_date.strftime('%b %d, %Y')}."
                    else:
                        msg = f"Your prescribed switch to Tray #{plan.next_aligner} was due on {change_date.strftime('%b %d, %Y')}. If you have switched, verify fit with your chewie."

                    PatientNotification.objects.create(
                        patient=patient,
                        notification_type='TRAY_CHANGE',
                        title=notif_title,
                        message=msg,
                        link_url='/treatment/'
                    )

    # 2. Weekly Photo Upload Reminder
    recent_photo = PhotoMonitoring.objects.filter(
        patient=patient.connected_patient_record
    ).order_by('-upload_date').first()

    should_remind_photos = False
    if not recent_photo:
        if (timezone.now() - patient.created_at).days >= 3:
            should_remind_photos = True
    else:
        if (today - recent_photo.upload_date).days >= 7:
            should_remind_photos = True

    if should_remind_photos:
        already_reminded = PatientNotification.objects.filter(
            patient=patient,
            notification_type='PHOTO_SUBMISSION',
            title__icontains='Weekly Photo',
            created_at__date__gte=today - timedelta(days=4)
        ).exists()

        if not already_reminded:
            PatientNotification.objects.create(
                patient=patient,
                notification_type='PHOTO_SUBMISSION',
                title='Weekly Teeth Photo Upload Due',
                message=f'It is time for your weekly 5-angle dental monitoring photos. Dr. {doctor.full_name} tracks your alignment progression each week.',
                link_url='/photos/upload/'
            )

    # 3. Upcoming Appointment Reminders (within 48 hours)
    upcoming_appts = Appointment.objects.filter(
        patient=patient.connected_patient_record,
        status__in=['UPCOMING', 'SCHEDULED'],
        scheduled_date__gte=today,
        scheduled_date__lte=today + timedelta(days=2)
    )
    for appt in upcoming_appts:
        appt_title = f"Reminder: Appointment on {appt.scheduled_date.strftime('%b %d')}"
        already_alerted = PatientNotification.objects.filter(
            patient=patient,
            notification_type='APPOINTMENT',
            title=appt_title
        ).exists()
        if not already_alerted:
            PatientNotification.objects.create(
                patient=patient,
                notification_type='APPOINTMENT',
                title=appt_title,
                message=f"You have an upcoming appointment ({appt.get_appointment_type_display()}) on {appt.scheduled_date.strftime('%A, %b %d')} at {appt.scheduled_time.strftime('%I:%M %p')} with Dr. {doctor.full_name}. {appt.instructions or ''}",
                link_url='/appointments/'
            )


# ----------------- PATIENT DASHBOARD & DOCTOR CONNECTION -----------------

@login_required(login_url='patient:login')
def patient_dashboard_view(request):
    if hasattr(request.user, 'doctor_profile') and not hasattr(request.user, 'patient_profile'):
        return redirect('doctor:dashboard')
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        messages.error(request, "Patient profile not found. Please log in as a patient.")
        return redirect('patient:login')

    connected_record = auto_connect_patient_profile(patient) or patient.connected_patient_record
    if connected_record and (connected_record.is_deactivated or connected_record.is_archived):
        logout(request)
        messages.error(request, "Your patient account has been deleted / closed following treatment completion. Please contact your doctor for assistance.")
        return redirect('patient:login')

    # Auto-resolve if pending_code has been approved by doctor
    if not patient.is_connected and patient.pending_code and patient.pending_code.status == 'APPROVED':
        patient.connected_patient_record = patient.pending_code.patient
        patient.connection_status = 'CONNECTED'
        patient.save()
        messages.success(request, f"Congratulations! Dr. {patient.doctor.full_name} has approved your connection. Your Treatment Dashboard is now active!")

    # Synchronize scheduled reminders
    sync_patient_reminders_from_schedule(patient)

    # Doctor connection status
    doctor = patient.doctor
    treatment_plan = patient.treatment_plan
    connected_record = patient.connected_patient_record

    next_appointment = None
    latest_photos = None
    days_until_next_change = None
    progress_percent = 0
    prescriptions = []
    timeline_stages = []
    current_turn = None
    doctor_media = None
    media_history = []
    monthly_notes = []
    preop_photos = []
    radiographs = []
    opg_radiographs = []
    ceph_radiographs = []
    appointments = []
    upcoming_appointments = []
    past_appointments = []
    current_operation = 'Turn Quest'
    diagnosed_problem = None
    monitoring_frequency = 'WEEKLY'
    patient_photos = []

    if patient.is_connected and connected_record:
        # Step 1: Preoperative Photos uploaded by Doctor
        preop_photos = connected_record.preoperative_photos.all().order_by('uploaded_at')

        # Step 2: Diagnostic Radiographs uploaded by Doctor
        radiographs = connected_record.radiographs.all().order_by('examination_date', 'version')
        opg_radiographs = radiographs.filter(radiograph_type__in=['OPG', 'TYPE_1'])
        ceph_radiographs = radiographs.filter(radiograph_type__in=['LATERAL_CEPHALOGRAPH', 'TYPE_2'])

        # Step 3: Hospital Consultation Appointments (20-day follow-up)
        appointments = connected_record.appointments.all().order_by('-scheduled_date', '-scheduled_time')
        today_date = timezone.localdate()
        next_appointment = appointments.filter(
            scheduled_date__gte=today_date,
            status__in=['UPCOMING', 'REQUESTED', 'RESCHEDULED', 'RESCHEDULE_REQUESTED']
        ).order_by('scheduled_date', 'scheduled_time').first() or appointments.first()
        upcoming_appointments = [a for a in appointments if a.scheduled_date >= today_date]
        past_appointments = [a for a in appointments if a.scheduled_date < today_date]

        # Step 4: Clinical Problem Diagnosis & Prescribed Operation (Turn Quest / Custom)
        doctor_media = connected_record.treatment_media.filter(is_current=True).first()
        media_history = connected_record.treatment_media.all()
        current_operation = doctor_media.operation_name if doctor_media else (connected_record.current_operation or 'Turn Quest')
        diagnosed_problem = doctor_media.patient_problem if (doctor_media and doctor_media.patient_problem) else connected_record.diagnosed_problem
        monitoring_frequency = doctor_media.update_frequency if doctor_media else (connected_record.monitoring_frequency or 'WEEKLY')

        # Patient submitted progress photos
        patient_photos = PhotoMonitoring.objects.filter(patient=connected_record).order_by('-week_number', '-upload_date')
        latest_photos = patient_photos.first()

        # Prescriptions
        prescriptions = connected_record.prescriptions.all()[:4]

        # 12-Stage Visual Treatment Timeline
        timeline_stages = connected_record.get_timeline_stages()

        # Current Turn Quest Stage
        current_turn = connected_record.treatment_turns.filter(status__in=['IN_PROGRESS', 'UPCOMING']).first()

        # Monthly Notes
        monthly_notes = connected_record.monthly_notes.all()[:3]

        # Treatment metrics
        if treatment_plan:
            total = treatment_plan.total_aligners or 1
            curr = treatment_plan.current_aligner or 1
            progress_percent = min(100, int((curr / total) * 100))

            change_date = treatment_plan.computed_next_change_date
            if change_date:
                days_until_next_change = max(0, (change_date - timezone.localdate()).days)
            elif treatment_plan.next_review_date:
                diff = (treatment_plan.next_review_date - timezone.localdate()).days
                days_until_next_change = max(0, diff)

    context = {
        'patient': patient,
        'doctor': doctor,
        'treatment_plan': treatment_plan,
        'connected_record': connected_record,
        'preop_photos': preop_photos,
        'radiographs': radiographs,
        'opg_radiographs': opg_radiographs,
        'ceph_radiographs': ceph_radiographs,
        'appointments': appointments,
        'all_appointments': appointments,
        'upcoming_appointments': upcoming_appointments,
        'past_appointments': past_appointments,
        'next_appointment': next_appointment,
        'doctor_media': doctor_media,
        'media_history': media_history,
        'current_operation': current_operation,
        'diagnosed_problem': diagnosed_problem,
        'monitoring_frequency': monitoring_frequency,
        'patient_photos': patient_photos,
        'latest_photos': latest_photos,
        'prescriptions': prescriptions,
        'timeline_stages': timeline_stages,
        'current_turn': current_turn,
        'monthly_notes': monthly_notes,
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
        elif code_obj.status == 'REVOKED':
            form.add_error('joining_code', "This joining code has been revoked.")
        elif code_obj.status == 'APPROVED':
            # Code is already approved by the doctor!
            patient.connected_patient_record = code_obj.patient
            patient.pending_code = code_obj
            patient.connection_status = 'CONNECTED'
            patient.save()

            if not hasattr(code_obj.patient, 'treatment_plan'):
                TreatmentPlan.objects.create(
                    patient=code_obj.patient,
                    total_aligners=20,
                    current_aligner=1,
                    aligner_frequency_days=14,
                    status='Active / In Progress'
                )

            messages.success(request, f"Congratulations {patient.full_name}! Your connection with Dr. {code_obj.doctor.full_name} is approved. Your Treatment Dashboard is now active!")
            return redirect('patient:dashboard')
        elif code_obj.status == 'PENDING_APPROVAL':
            # Code is submitted and pending
            patient.connected_patient_record = code_obj.patient
            patient.pending_code = code_obj
            patient.connection_status = 'PENDING_APPROVAL'
            patient.save()
            messages.info(request, f"Your joining request for code {code_obj.code} is waiting for Dr. {code_obj.doctor.full_name} to approve.")
            return redirect('patient:dashboard')
        else:
            # Code is valid and pending claim
            code_obj.status = 'PENDING_APPROVAL'
            code_obj.claimed_at = timezone.now()
            code_obj.patient_request_notes = notes
            code_obj.save()

            patient.connected_patient_record = code_obj.patient
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


@login_required(login_url='patient:login')
def check_connection_status_api(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return JsonResponse({'is_connected': False, 'status': 'NOT_AUTHENTICATED'})

    # Auto-link if code approved
    if not patient.is_connected and patient.pending_code and patient.pending_code.status == 'APPROVED':
        patient.connected_patient_record = patient.pending_code.patient
        patient.connection_status = 'CONNECTED'
        patient.save()

    return JsonResponse({
        'is_connected': patient.is_connected,
        'connection_status': patient.connection_status,
        'doctor_name': patient.doctor.full_name if patient.doctor else None,
        'clinic_name': patient.doctor.clinic_name if patient.doctor else None,
        'dashboard_url': '/patient/',
    })


# ----------------- MY TREATMENT -----------------

@login_required(login_url='patient:login')
@login_required(login_url='patient:login')
def my_treatment_view(request):
    """Consolidated into unified Clinical Journey Home page."""
    return redirect('patient:dashboard')


@login_required(login_url='patient:login')
def prescription_view(request, presc_id):
    patient = get_patient_profile_or_none(request.user)
    if not patient or not patient.connected_patient_record:
        return redirect('patient:login')
    from doctor.models import Prescription
    prescription = get_object_or_404(Prescription, id=presc_id, patient=patient.connected_patient_record)

    context = {
        'patient': patient.connected_patient_record,
        'doctor': patient.doctor,
        'prescription': prescription,
        'base_template': 'patient/base.html',
    }
    return render(request, 'doctor/prescriptions/prescription_detail.html', context)


@login_required(login_url='patient:login')
def prescription_print_view(request, presc_id):
    patient = get_patient_profile_or_none(request.user)
    if not patient or not patient.connected_patient_record:
        return redirect('patient:login')
    from doctor.models import Prescription
    prescription = get_object_or_404(Prescription, id=presc_id, patient=patient.connected_patient_record)

    context = {
        'patient': patient.connected_patient_record,
        'doctor': patient.doctor,
        'prescription': prescription,
        'base_template': 'patient/base.html',
    }
    return render(request, 'doctor/prescriptions/prescription_print.html', context)


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
    doctor = patient.doctor

    # Step 4 doctor settings & cadence
    doctor_media = record.treatment_media.filter(is_current=True).first() if record else None
    cadence = (doctor_media.update_frequency if doctor_media else getattr(record, 'monitoring_frequency', 'WEEKLY')) or 'WEEKLY'
    current_op = doctor_media.operation_name if doctor_media else (getattr(record, 'current_operation', None) or 'Turn Quest')
    diagnosed_problem = doctor_media.patient_problem if doctor_media else getattr(record, 'diagnosed_problem', '')

    cadence_label = {
        'DAILY': 'Daily',
        'WEEKLY': 'Weekly',
        'MONTHLY': 'Monthly',
    }.get(cadence, 'Weekly')

    cadence_unit = {
        'DAILY': 'Day',
        'WEEKLY': 'Week',
        'MONTHLY': 'Month',
    }.get(cadence, 'Week')

    initial_cycle = 1
    latest = PhotoMonitoring.objects.filter(patient=record).order_by('-week_number').first() if record else None
    if latest:
        initial_cycle = latest.week_number + 1
    elif plan and plan.current_aligner:
        initial_cycle = plan.current_aligner

    form = TeethPhotoUploadForm(request.POST or None, request.FILES or None, initial={'week_number': initial_cycle})

    if request.method == 'POST' and form.is_valid():
        cycle_num = form.cleaned_data['week_number']
        notes = form.cleaned_data.get('patient_notes', '')

        # Create photo monitoring record
        curr_stage = getattr(plan, 'current_aligner', 1) or 1
        photo_record = PhotoMonitoring.objects.create(
            patient=record,
            week_number=cycle_num,
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
        target_doctor = patient.doctor or (record.doctor if record else None)
        if target_doctor:
            DoctorNotification.objects.create(
                doctor=target_doctor,
                patient=record,
                notification_type='PHOTO_UPLOAD',
                title=f'New Progress Photos: {patient.full_name} ({cadence_unit} #{cycle_num})',
                message=f'Patient {patient.full_name} submitted new {cadence_label.lower()} ({cadence_unit} #{cycle_num}) progress monitoring photos for {current_op} review.',
                link_url=f'/photos/{photo_record.id}/review/'
            )
            from doctor.models import PatientActivityLog
            PatientActivityLog.objects.create(
                doctor=target_doctor,
                patient=record,
                activity_type='Progress Photos Submitted',
                description=f'Patient {patient.full_name} submitted {cadence_label} ({cadence_unit} #{cycle_num}) progress photos for {current_op}.'
            )

        # Notify the patient
        PatientNotification.objects.create(
            patient=patient,
            notification_type='PHOTO_SUBMISSION',
            title=f'{cadence_label} ({cadence_unit} #{cycle_num}) Photos Received!',
            message=f'Your photos were successfully sent to Dr. {patient.doctor.full_name if patient.doctor else "your doctor"}. You will be notified once the doctor completes review.'
        )

        messages.success(request, f"Awesome job! Your {cadence_label} ({cadence_unit} #{cycle_num}) progress photos have been sent to Dr. {patient.doctor.full_name}.")
        return redirect(f"{reverse('patient:dashboard')}#patientProgressSection")

    recent_uploads = PhotoMonitoring.objects.filter(patient=record).order_by('-week_number')[:8] if record else []

    context = {
        'patient': patient,
        'doctor': patient.doctor,
        'form': form,
        'recent_uploads': recent_uploads,
        'doctor_media': doctor_media,
        'cadence': cadence,
        'cadence_label': cadence_label,
        'cadence_unit': cadence_unit,
        'current_op': current_op,
        'diagnosed_problem': diagnosed_problem,
    }
    return render(request, 'patient/upload_photos.html', context)


# ----------------- TREATMENT PROGRESS -----------------

@login_required(login_url='patient:login')
def treatment_progress_view(request):
    """Consolidated into unified Clinical Journey Home page."""
    return redirect(f"{reverse('patient:dashboard')}#patientProgressSection")


# ----------------- APPOINTMENTS -----------------

@login_required(login_url='patient:login')
def appointments_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return redirect('patient:login')

    auto_connect_patient_profile(patient)
    record = patient.connected_patient_record
    doctor = patient.doctor
    today = timezone.localdate()

    all_appointments = Appointment.objects.filter(patient=record).order_by('-scheduled_date', '-scheduled_time') if record else []
    upcoming_appointments = [a for a in all_appointments if a.scheduled_date >= today]
    past_appointments = [a for a in all_appointments if a.scheduled_date < today]

    context = {
        'patient': patient,
        'doctor': doctor,
        'all_appointments': all_appointments,
        'upcoming_appointments': upcoming_appointments,
        'past_appointments': past_appointments,
    }
    return render(request, 'patient/appointments/appointments.html', context)


@login_required(login_url='patient:login')
def appointment_request_view(request):
    patient = get_patient_profile_or_none(request.user)
    if not patient:
        return redirect('patient:login')

    auto_connect_patient_profile(patient)
    if not patient.is_connected or not patient.connected_patient_record:
        messages.warning(request, "Please connect with your doctor to request an appointment.")
        return redirect('patient:dashboard')

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
    if not patient:
        return redirect('patient:login')

    auto_connect_patient_profile(patient)
    if not patient.is_connected or not patient.connected_patient_record:
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

    sync_patient_reminders_from_schedule(patient)

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


@login_required(login_url='patient:login')
def mark_all_notifications_read_view(request):
    patient = get_patient_profile_or_none(request.user)
    if patient:
        patient.notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
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
        valid_issues = ['TOOTH_PAIN', 'ALIGNER_DISCOMFORT', 'BROKEN_ALIGNER', 'LOOSE_ALIGNER', 'GUM_PROBLEMS', 'OTHER']
        mapped_issue = prob if prob in valid_issues else 'OTHER'

        alert = EmergencyAlert.objects.create(
            patient=patient.connected_patient_record,
            issue_type=mapped_issue,
            severity=sev if sev in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] else 'MEDIUM',
            description=f"Patient Report via Portal: {desc}",
            photo=photo,
            status='NEW'
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

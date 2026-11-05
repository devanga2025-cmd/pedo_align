from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import io
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

from patient.models import PatientProfile, PatientNotification
from doctor.models import (
    DoctorProfile, Patient as ClinicalPatient, PatientJoiningCode,
    TreatmentPlan, PhotoMonitoring, Appointment, EmergencyAlert, Notification as DoctorNotification,
    PreoperativePhoto, RadiographRecord, DoctorTreatmentMedia
)


def create_test_image():
    file = io.BytesIO()
    image = Image.new('RGB', (100, 100), 'white')
    image.save(file, 'jpeg')
    file.seek(0)
    return SimpleUploadedFile('test.jpg', file.read(), content_type='image/jpeg')


class PatientPortalTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create doctor
        self.doc_user = User.objects.create_user(
            username='doctor@pedoalign.com',
            email='doctor@pedoalign.com',
            password='Password123!',
            first_name='Arthur',
            last_name='Smith'
        )
        self.doctor = DoctorProfile.objects.create(
            user=self.doc_user,
            full_name='Dr. Arthur Smith',
            dental_qualification='BDS, MDS Orthodontics',
            clinic_name='Pedo Align Ortho Care',
            clinic_address='123 Dental Way'
        )

        # Create clinical patient record for doctor
        self.clinical_patient = ClinicalPatient.objects.create(
            doctor=self.doctor,
            patient_id='PA-P1001',
            first_name='Rohan',
            last_name='Kumar',
            email='rohan@example.com',
            phone='9876543210',
            age=14,
            gender='M',
            treatment_status='ACTIVE'
        )

        # Generate Joining Code
        self.joining_code = PatientJoiningCode.objects.create(
            doctor=self.doctor,
            patient=self.clinical_patient,
            code='PA-TEST99',
            expires_at=timezone.now() + timedelta(days=7),
            status='ACTIVE'
        )

        # Create Treatment Plan
        self.treatment_plan = TreatmentPlan.objects.create(
            patient=self.clinical_patient,
            total_aligners=20,
            current_aligner=3,
            aligner_frequency_days=14,
            start_date=timezone.now().date() - timedelta(days=42),
            expected_completion_date=timezone.now().date() + timedelta(days=238),
            treatment_instructions='Wear 22 hours daily. Use chewies twice daily.'
        )

    def test_patient_registration_and_login(self):
        # 1. Register new patient
        register_url = reverse('patient:register')
        reg_data = {
            'full_name': 'Rohan Kumar',
            'email': 'rohan@example.com',
            'date_of_birth': '2010-05-15',
            'mobile_number': '9876543210',
            'password': 'SecurePatientPass123!',
            'confirm_password': 'SecurePatientPass123!',
        }
        res = self.client.post(register_url, reg_data)
        self.assertEqual(res.status_code, 302)

        # Profile created and auto-connected to clinical record matching email/phone
        patient_profile = PatientProfile.objects.filter(user__email='rohan@example.com').first()
        self.assertIsNotNone(patient_profile)
        self.assertTrue(patient_profile.patient_id.startswith('PA-P'))
        self.assertEqual(patient_profile.connection_status, 'CONNECTED')

        # 2. Logout
        self.client.get(reverse('patient:logout'))

        # 3. Login with Email
        login_url = reverse('patient:login')
        res = self.client.post(login_url, {
            'login_identifier': 'rohan@example.com',
            'password': 'SecurePatientPass123!'
        })
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, reverse('patient:dashboard'))

        # 4. Logout and Login with Patient ID
        self.client.get(reverse('patient:logout'))
        res = self.client.post(login_url, {
            'login_identifier': patient_profile.patient_id,
            'password': 'SecurePatientPass123!'
        })
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, reverse('patient:dashboard'))

    def test_connect_with_doctor_workflow(self):
        # Register and log in patient
        user = User.objects.create_user(username='kid@example.com', email='kid@example.com', password='Password123!')
        profile = PatientProfile.objects.create(user=user, full_name='Kid Patient')
        self.client.login(username='kid@example.com', password='Password123!')

        connect_url = reverse('patient:connect_doctor')

        # Test invalid code
        res = self.client.post(connect_url, {'joining_code': 'INVALID99'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Invalid joining code')

        # Test valid code
        res = self.client.post(connect_url, {
            'joining_code': 'PA-TEST99',
            'notes': 'Hello Doctor Arthur!'
        })
        self.assertEqual(res.status_code, 302)

        # Refresh objects
        profile.refresh_from_db()
        self.joining_code.refresh_from_db()

        self.assertEqual(profile.connection_status, 'PENDING_APPROVAL')
        self.assertEqual(self.joining_code.status, 'PENDING_APPROVAL')
        self.assertEqual(profile.pending_code, self.joining_code)

        # Verify Doctor Notification was sent
        doc_notif = DoctorNotification.objects.filter(doctor=self.doctor, notification_type='PATIENT_REQUEST').first()
        self.assertIsNotNone(doc_notif)
        self.assertIn('PA-TEST99', doc_notif.message)

        # Now simulate Doctor approving request from Doctor Portal
        self.client.logout()
        self.client.login(username='doctor@pedoalign.com', password='Password123!')
        approve_url = reverse('doctor:approve_patient_request', kwargs={'code_id': self.joining_code.id})
        res = self.client.post(approve_url)
        self.assertEqual(res.status_code, 302)

        # Verify PatientProfile is now fully connected
        profile.refresh_from_db()
        self.assertEqual(profile.connection_status, 'CONNECTED')
        self.assertEqual(profile.doctor, self.doctor)
        self.assertEqual(profile.connected_patient_record, self.clinical_patient)

        # Verify Patient Notification for approval
        pat_notif = PatientNotification.objects.filter(patient=profile, notification_type='TREATMENT_UPDATE').first()
        self.assertIsNotNone(pat_notif)
        self.assertTrue('Approved' in pat_notif.title)

    def test_patient_pages_and_features(self):
        # Setup connected patient
        user = User.objects.create_user(username='connected@example.com', email='connected@example.com', password='Password123!')
        profile = PatientProfile.objects.create(
            user=user,
            full_name='Connected Patient',
            connected_patient_record=self.clinical_patient,
            connection_status='CONNECTED'
        )
        self.client.login(username='connected@example.com', password='Password123!')

        # 1. Dashboard
        res = self.client.get(reverse('patient:dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Connected Patient')
        self.assertContains(res, 'Dr. Arthur Smith')
        self.assertContains(res, 'My 4-Step Clinical Journey')

        # 2. My Treatment (redirects to unified Clinical Journey page)
        res = self.client.get(reverse('patient:my_treatment'))
        self.assertEqual(res.status_code, 302)

        # 3. Treatment Progress (redirects to unified Clinical Journey page)
        res = self.client.get(reverse('patient:progress'))
        self.assertEqual(res.status_code, 302)

        # 4. Upload Photos
        upload_url = reverse('patient:upload_photos')
        res = self.client.get(upload_url)
        self.assertEqual(res.status_code, 200)

        test_img = create_test_image()
        res = self.client.post(upload_url, {
            'week_number': 3,
            'photo_front': test_img,
            'patient_notes': 'Feeling snug on teeth.'
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(PhotoMonitoring.objects.filter(patient=self.clinical_patient, week_number=3).exists())
        # Verify doctor received notification for patient photo upload
        self.assertTrue(DoctorNotification.objects.filter(doctor=self.doctor, notification_type='PHOTO_UPLOAD').exists())

        # 5. Dedicated Appointments Section & Request Page
        res = self.client.get(reverse('patient:appointments'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Appointments')

        req_url = reverse('patient:appointment_request')
        res = self.client.post(req_url, {
            'appointment_date': (timezone.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
            'preferred_time': '10:30',
            'reason': 'ALIGNER_CHECKUP',
            'notes': 'Checking tray fit'
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Appointment.objects.filter(patient=self.clinical_patient, status='REQUESTED').exists())

        # 6. Emergency Help
        emg_url = reverse('patient:emergency')
        res = self.client.get(emg_url)
        self.assertEqual(res.status_code, 200)

        res = self.client.post(emg_url, {
            'problem_type': 'BROKEN_ALIGNER',
            'severity': 'HIGH',
            'description': 'Small hairline crack in lower right aligner.'
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(EmergencyAlert.objects.filter(patient=self.clinical_patient, issue_type='BROKEN_ALIGNER').exists())

        # 7. Notifications
        res = self.client.get(reverse('patient:notifications'))
        self.assertEqual(res.status_code, 200)

        # 8. Profile
        res = self.client.get(reverse('patient:profile'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Personal Details')

    def test_auto_open_dashboard_after_approval(self):
        # Patient with pending code
        user = User.objects.create_user(username='pending_pat@test.com', email='pending_pat@test.com', password='pwd')
        profile = PatientProfile.objects.create(
            user=user,
            full_name='Pending Patient',
            pending_code=self.joining_code,
            connection_status='PENDING_APPROVAL'
        )
        self.client.login(username='pending_pat@test.com', password='pwd')

        # 1. Check API while pending
        api_url = reverse('patient:api_connection_status')
        res = self.client.get(api_url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data['is_connected'])
        self.assertEqual(data['connection_status'], 'PENDING_APPROVAL')

        # 2. Doctor approves the code
        self.joining_code.status = 'APPROVED'
        self.joining_code.save()

        # 3. Patient checks API again (or visits dashboard)
        res = self.client.get(api_url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['is_connected'])
        self.assertEqual(data['connection_status'], 'CONNECTED')
        self.assertEqual(data['doctor_name'], 'Dr. Arthur Smith')

        # 4. Patient opens dashboard -> unlocked with full treatment information
        dash_res = self.client.get(reverse('patient:dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, 'Dr. Arthur Smith')
        self.assertContains(dash_res, 'Clinical Journey & Records')
        self.assertContains(dash_res, 'My 4-Step Clinical Journey')

    def test_patient_category_and_guardian_support(self):
        """Requirement 2: Child and Adult Patient categories with parent/guardian contact info."""
        # 1. Register Child Patient
        res = self.client.post(reverse('patient:register'), {
            'patient_category': 'CHILD',
            'full_name': 'Leo Anderson',
            'date_of_birth': '2016-03-20',
            'email': 'leo.parent@example.com',
            'mobile_number': '+91 9900112233',
            'parent_guardian_name': 'Sarah Anderson',
            'parent_guardian_phone': '+91 9900112233',
            'parent_guardian_email': 'sarah.anderson@example.com',
            'parent_guardian_relationship': 'Mother',
            'password': 'SecureChildPassword123!',
            'confirm_password': 'SecureChildPassword123!',
        })
        self.assertEqual(res.status_code, 302)
        child_profile = PatientProfile.objects.filter(user__email='leo.parent@example.com').first()
        self.assertIsNotNone(child_profile)
        self.assertEqual(child_profile.patient_category, 'CHILD')
        self.assertEqual(child_profile.parent_guardian_name, 'Sarah Anderson')
        self.assertEqual(child_profile.parent_guardian_relationship, 'Mother')

        # 2. Register Adult Patient
        self.client.logout()
        res_adult = self.client.post(reverse('patient:register'), {
            'patient_category': 'ADULT',
            'full_name': 'Victoria Sterling',
            'date_of_birth': '1995-11-10',
            'email': 'victoria@example.com',
            'mobile_number': '+91 9887766554',
            'password': 'SecureAdultPassword123!',
            'confirm_password': 'SecureAdultPassword123!',
        })
        self.assertEqual(res_adult.status_code, 302)
        adult_profile = PatientProfile.objects.filter(user__email='victoria@example.com').first()
        self.assertIsNotNone(adult_profile)
        self.assertEqual(adult_profile.patient_category, 'ADULT')

    def test_schedule_based_notifications_and_mark_as_read(self):
        """Requirement 9: Schedule-based notifications generation and mark as read."""
        user = User.objects.create_user(username='notif_pat@test.com', email='notif_pat@test.com', password='pwd')
        profile = PatientProfile.objects.create(
            user=user,
            full_name='Notification Patient',
            connected_patient_record=self.clinical_patient,
            connection_status='CONNECTED'
        )
        self.client.login(username='notif_pat@test.com', password='pwd')

        # Set next tray change date to tomorrow
        self.treatment_plan.next_tray_change_date = timezone.localdate() + timedelta(days=1)
        self.treatment_plan.save()

        # Create upcoming appointment tomorrow
        Appointment.objects.create(
            doctor=self.doctor,
            patient=self.clinical_patient,
            scheduled_date=timezone.localdate() + timedelta(days=1),
            scheduled_time='11:00',
            appointment_type='ROUTINE_CHECKUP',
            status='UPCOMING'
        )

        # Patient visits notifications page -> triggers sync_patient_reminders_from_schedule
        res = self.client.get(reverse('patient:notifications'))
        self.assertEqual(res.status_code, 200)

        # Check tray change reminder was generated
        tray_notif = PatientNotification.objects.filter(patient=profile, notification_type='TRAY_CHANGE').first()
        self.assertIsNotNone(tray_notif)
        self.assertFalse(tray_notif.is_read)

        # Check appointment reminder was generated
        appt_notif = PatientNotification.objects.filter(patient=profile, notification_type='APPOINTMENT').first()
        self.assertIsNotNone(appt_notif)

        # 1. Mark single notification as read
        read_res = self.client.get(reverse('patient:mark_notification_read', kwargs={'notif_id': tray_notif.id}))
        self.assertEqual(read_res.status_code, 302)
        tray_notif.refresh_from_db()
        self.assertTrue(tray_notif.is_read)

        # 2. Mark all notifications as read
        read_all_res = self.client.get(reverse('patient:mark_all_notifications_read'))
        self.assertEqual(read_all_res.status_code, 302)
        unread = PatientNotification.objects.filter(patient=profile, is_read=False).count()
        self.assertEqual(unread, 0)

    def test_emergency_hub_patient_reads_doctor_response(self):
        """Requirement 7: Patient reads doctor's instructions in Emergency Hub."""
        user = User.objects.create_user(username='emg_user@test.com', email='emg_user@test.com', password='pwd')
        profile = PatientProfile.objects.create(
            user=user,
            full_name='Emergency Patient',
            connected_patient_record=self.clinical_patient,
            connection_status='CONNECTED'
        )
        self.client.login(username='emg_user@test.com', password='pwd')

        # Create emergency alert responded by doctor
        alert = EmergencyAlert.objects.create(
            patient=self.clinical_patient,
            issue_type='TOOTH_PAIN',
            severity='HIGH',
            description='Severe molar sensitivity with current aligner set.',
            status='RESPONDED',
            doctor_response='Apply sensitivity gel twice daily. Wear aligners 20 hours for 2 days.'
        )

        res = self.client.get(reverse('patient:emergency'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Apply sensitivity gel twice daily')
        self.assertContains(res, 'Important Medical Notice')

    def test_patient_four_step_clinical_records(self):
        """Verify that all 4 steps of clinical records uploaded by doctor appear on the patient home page."""
        user = User.objects.create_user(username='step_patient@test.com', email='step_patient@test.com', password='pwd')
        profile = PatientProfile.objects.create(
            user=user,
            full_name='Maya Angel',
            connected_patient_record=self.clinical_patient,
            connection_status='CONNECTED'
        )
        self.client.login(username='step_patient@test.com', password='pwd')

        # 1. Doctor Step 1: Pre-op Photos
        PreoperativePhoto.objects.create(
            patient=self.clinical_patient,
            photo=create_test_image(),
            title='Frontal Occlusion View',
            description='Centric relation baseline view'
        )
        PreoperativePhoto.objects.create(
            patient=self.clinical_patient,
            photo=create_test_image(),
            title='Upper Arch Maxillary View',
            description='Occlusal view showing arch width'
        )

        # 2. Doctor Step 2: Diagnostic Radiographs
        RadiographRecord.objects.create(
            patient=self.clinical_patient,
            radiograph_type='OPG',
            title='Baseline OPG Radiograph',
            description='Panoramic scan for bone structure',
            image=create_test_image()
        )
        RadiographRecord.objects.create(
            patient=self.clinical_patient,
            radiograph_type='LATERAL_CEPHALOGRAPH',
            title='Lateral Cephalometric View',
            description='Skeletal pattern assessment',
            image=create_test_image()
        )

        # 3. Doctor Step 3: Hospital Consultation Appointment
        Appointment.objects.create(
            doctor=self.doctor,
            patient=self.clinical_patient,
            scheduled_date=timezone.localdate() + timedelta(days=20),
            scheduled_time='11:00',
            appointment_type='FIRST_FOLLOWUP',
            status='UPCOMING',
            instructions='Bring previous appliances and maintain oral hygiene.'
        )

        # 4. Doctor Step 4: Problem Diagnosis & Prescribed Turn Quest Operation with Cadence
        DoctorTreatmentMedia.objects.create(
            patient=self.clinical_patient,
            doctor=self.doctor,
            operation_type='TURN_QUEST',
            operation_name='Turn Quest',
            patient_problem='Severe bilateral anterior crossbite with maxillary constriction',
            update_frequency='WEEKLY',
            photo=create_test_image(),
            photo_description='Appliance key position reference',
            treatment_stage='Turn Quest Active Stage 1',
            doctor_instructions='Turn key clockwise twice per scheduled turn cycle.',
            is_current=True
        )
        self.clinical_patient.current_operation = 'Turn Quest'
        self.clinical_patient.diagnosed_problem = 'Severe bilateral anterior crossbite with maxillary constriction'
        self.clinical_patient.monitoring_frequency = 'WEEKLY'
        self.clinical_patient.save()

        # Patient visits Home Page (patient:dashboard)
        res = self.client.get(reverse('patient:dashboard'))
        self.assertEqual(res.status_code, 200)

        # Check Step 1 appears
        self.assertContains(res, 'Step 1')
        self.assertContains(res, 'Frontal Occlusion View')
        self.assertContains(res, 'Upper Arch Maxillary View')
        self.assertContains(res, 'Uploaded by Dr. Arthur Smith')

        # Check Step 2 appears
        self.assertContains(res, 'Step 2')
        self.assertContains(res, 'Baseline OPG Radiograph')
        self.assertContains(res, 'Lateral Cephalometric View')

        # Verify Hospital Consultation & Follow-up Appointment card is removed from clinical journey page
        self.assertNotContains(res, 'Hospital Consultation & Follow-up Appointment')
        
        # Verify appointments are viewable in the dedicated Appointments section
        appts_res = self.client.get(reverse('patient:appointments'))
        self.assertEqual(appts_res.status_code, 200)
        self.assertContains(appts_res, 'Bring previous appliances')

        # Check Step 4 appears
        self.assertContains(res, 'Step 4')
        self.assertContains(res, 'Severe bilateral anterior crossbite')
        self.assertContains(res, 'Turn Quest')
        self.assertContains(res, 'Appliance key position reference')

        # Check patient upload page adapts to doctor cadence
        upload_res = self.client.get(reverse('patient:upload_photos'))
        self.assertEqual(upload_res.status_code, 200)
        self.assertContains(upload_res, 'Weekly Cadence')
        self.assertContains(upload_res, 'Severe bilateral anterior crossbite')
        self.assertContains(upload_res, 'Turn Quest')
        self.assertContains(upload_res, 'Appliance key position reference')

    def test_persistent_login_direct_dashboard_redirect_for_patient(self):
        """Once a patient logs in, any request to root, login, or portal entry must redirect directly to their dashboard."""
        patient_user = User.objects.create_user(
            username='rohan@example.com',
            email='rohan@example.com',
            password='Password123!'
        )
        PatientProfile.objects.create(
            user=patient_user,
            full_name='Rohan Kumar',
            phone_number='9876543210',
            connected_patient_record=self.clinical_patient,
            connection_status='CONNECTED'
        )
        self.client.login(username='rohan@example.com', password='Password123!')

        # 1. Visiting root URL '/' directly opens patient dashboard
        root_res = self.client.get('/')
        self.assertRedirects(root_res, reverse('patient:dashboard'))

        # 2. Visiting patient login directly opens patient dashboard (never shows login form again)
        pt_login_res = self.client.get(reverse('patient:login'))
        self.assertRedirects(pt_login_res, reverse('patient:dashboard'))

        # 3. Visiting doctor login directly opens patient dashboard
        doc_login_res = self.client.get(reverse('doctor:login'))
        self.assertRedirects(doc_login_res, reverse('patient:dashboard'))

        # 4. Visiting join portal directly opens patient dashboard
        join_res = self.client.get(reverse('doctor:patient_join_portal'))
        self.assertRedirects(join_res, reverse('patient:dashboard'))

    def test_persistent_login_direct_dashboard_redirect_for_doctor(self):
        """Once a doctor logs in, any request to root or login must redirect directly to their doctor dashboard."""
        self.client.login(username=self.doc_user.username, password='Password123!')

        # 1. Visiting root URL '/' directly opens doctor dashboard
        root_res = self.client.get('/')
        self.assertRedirects(root_res, reverse('doctor:dashboard'))

        # 2. Visiting doctor login directly opens doctor dashboard
        doc_login_res = self.client.get(reverse('doctor:login'))
        self.assertRedirects(doc_login_res, reverse('doctor:dashboard'))

        # 3. Visiting patient login directly opens doctor dashboard
        pt_login_res = self.client.get(reverse('patient:login'))
        self.assertRedirects(pt_login_res, reverse('doctor:dashboard'))

    def test_pwa_endpoints_and_modal_cleanup(self):
        """Verify Service Worker & Manifest return 200 with proper scope headers and modal has no device url or desktop button."""
        # 1. /sw.js endpoint
        sw_res = self.client.get('/sw.js')
        self.assertEqual(sw_res.status_code, 200)
        self.assertEqual(sw_res['Content-Type'], 'application/javascript')
        self.assertEqual(sw_res['Service-Worker-Allowed'], '/')

        # 2. /manifest.json endpoint
        manifest_res = self.client.get('/manifest.json')
        self.assertEqual(manifest_res.status_code, 200)
        self.assertEqual(manifest_res['Content-Type'], 'application/manifest+json')
        self.assertIn('"start_url": "/"', manifest_res.content.decode())

        # 3. Modal does not contain "DEVICE ACCESS URL" or "Desktop" tab
        login_res = self.client.get(reverse('patient:login'))
        self.assertNotContains(login_res, 'DEVICE ACCESS URL')
        self.assertNotContains(login_res, 'pwaTabDesktop')
        self.assertContains(login_res, 'Install Directly on Phone')



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
    TreatmentPlan, PhotoMonitoring, Appointment, EmergencyAlert, Notification as DoctorNotification
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

        # Profile created
        patient_profile = PatientProfile.objects.filter(user__email='rohan@example.com').first()
        self.assertIsNotNone(patient_profile)
        self.assertTrue(patient_profile.patient_id.startswith('PA-P'))
        self.assertEqual(patient_profile.connection_status, 'NOT_CONNECTED')

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

        # 2. My Treatment
        res = self.client.get(reverse('patient:my_treatment'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Treatment Stage Timeline')
        self.assertContains(res, 'Aligner')

        # 3. Treatment Progress
        res = self.client.get(reverse('patient:progress'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Milestone Tracker')

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

        # 5. Appointments Page & Request
        res = self.client.get(reverse('patient:appointments'))
        self.assertEqual(res.status_code, 200)

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

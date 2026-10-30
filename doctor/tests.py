from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from .models import (
    DoctorProfile, Patient, PatientJoiningCode,
    ClinicalRecord, TreatmentPlan, PhotoMonitoring,
    EmergencyAlert, Appointment, Notification
)
import datetime


class DoctorPortalComprehensiveTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Doctor 1: Dr. Smith
        self.user_smith = User.objects.create_user(
            username='dr.smith@test.com',
            email='dr.smith@test.com',
            password='password123'
        )
        self.doc_smith = DoctorProfile.objects.create(
            user=self.user_smith,
            full_name='Arthur Smith',
            phone_number='1234567890',
            dental_qualification='MDS Orthodontics',
            clinic_name='Smith Ortho Clinic',
            clinic_address='123 Dental Ave'
        )

        # Doctor 2: Dr. Kumar (for isolation testing)
        self.user_kumar = User.objects.create_user(
            username='dr.kumar@test.com',
            email='dr.kumar@test.com',
            password='password123'
        )
        self.doc_kumar = DoctorProfile.objects.create(
            user=self.user_kumar,
            full_name='Rajesh Kumar',
            phone_number='9876543210',
            dental_qualification='BDS, MDS Pedodontics',
            clinic_name='Kumar Pediatric Dental',
            clinic_address='456 Health St'
        )

        # Patient for Dr. Smith
        self.patient_smith = Patient.objects.create(
            doctor=self.doc_smith,
            patient_id='PA-PT-TEST-001',
            first_name='Tommy',
            last_name='Clark',
            age=10,
            gender='Male',
            phone='555-1111',
            treatment_status='ACTIVE'
        )
        self.code_smith = PatientJoiningCode.objects.create(
            patient=self.patient_smith,
            doctor=self.doc_smith,
            code='PA-TEST01',
            status='APPROVED',
            expires_at=timezone.now() + datetime.timedelta(days=14)
        )
        self.plan_smith = TreatmentPlan.objects.create(
            patient=self.patient_smith,
            total_aligners=20,
            current_aligner=4,
            status='Active / In Progress'
        )
        self.clinical_smith = ClinicalRecord.objects.create(
            patient=self.patient_smith,
            overbite='Increased (>3mm)',
            molar_relationship='Class II Division 1'
        )

        # Patient for Dr. Kumar
        self.patient_kumar = Patient.objects.create(
            doctor=self.doc_kumar,
            patient_id='PA-PT-TEST-002',
            first_name='Anaya',
            last_name='Rao',
            age=8,
            gender='Female',
            phone='555-2222',
            treatment_status='ACTIVE'
        )

    def test_doctor_login(self):
        """Test doctor authentication via email and password."""
        response = self.client.post(reverse('doctor:login'), {
            'email': 'dr.smith@test.com',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('doctor:dashboard'))

    def test_strict_doctor_isolation(self):
        """Test Dr. Smith CANNOT view or access Dr. Kumar's patients."""
        self.client.login(username='dr.smith@test.com', password='password123')

        # Dr. Smith tries to view Dr. Kumar's patient
        response = self.client.get(reverse('doctor:patient_detail', kwargs={'patient_id': self.patient_kumar.id}))
        self.assertEqual(response.status_code, 404)

        # Dr. Smith views own patient
        response_own = self.client.get(reverse('doctor:patient_detail', kwargs={'patient_id': self.patient_smith.id}))
        self.assertEqual(response_own.status_code, 200)
        self.assertContains(response_own, 'Tommy Clark')

    def test_dashboard_renders_metrics(self):
        """Test dashboard loads with correct KPI counts for doctor."""
        self.client.login(username='dr.smith@test.com', password='password123')
        response = self.client.get(reverse('doctor:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tommy Clark')
        self.assertContains(response, 'Total Enrolled')

    def test_add_new_patient_and_joining_code_generation(self):
        """Test adding patient automatically generates individual joining code."""
        self.client.login(username='dr.smith@test.com', password='password123')
        response = self.client.post(reverse('doctor:patient_create'), {
            'first_name': 'Emma',
            'last_name': 'Watson',
            'age': 12,
            'gender': 'Female',
            'phone': '555-9999',
            'treatment_duration_months': 12
        })
        self.assertEqual(response.status_code, 302)

        new_pt = Patient.objects.filter(first_name='Emma', doctor=self.doc_smith).first()
        self.assertIsNotNone(new_pt)
        self.assertTrue(new_pt.patient_id.startswith('PA-PT-'))

        # Check joining code was generated automatically
        code = PatientJoiningCode.objects.filter(patient=new_pt).first()
        self.assertIsNotNone(code)
        self.assertTrue(code.code.startswith('PA-'))
        self.assertEqual(code.status, 'ACTIVE')

    def test_patient_joining_flow_and_approval(self):
        """Test full joining loop: patient claims code on portal -> doctor approves -> patient active."""
        # 1. Create a patient pending connection with active code
        patient_unclaimed = Patient.objects.create(
            doctor=self.doc_smith,
            patient_id='PA-PT-TEST-003',
            first_name='Lucas',
            last_name='Scott',
            age=11,
            gender='Male',
            phone='555-4321',
            treatment_status='PENDING_CONNECTION'
        )
        code_obj = PatientJoiningCode.objects.create(
            patient=patient_unclaimed,
            doctor=self.doc_smith,
            code='PA-LUCAS1',
            status='ACTIVE',
            expires_at=timezone.now() + datetime.timedelta(days=14)
        )

        # 2. Patient enters joining code on public join portal
        response = self.client.post(reverse('doctor:patient_join_portal'), {
            'joining_code': 'PA-LUCAS1',
            'patient_first_name': 'Lucas',
            'patient_last_name': 'Scott',
            'phone': '555-4321',
            'request_notes': 'Hi Dr. Smith, please connect my portal.'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Connection Request Submitted!')

        code_obj.refresh_from_db()
        self.assertEqual(code_obj.status, 'PENDING_APPROVAL')

        # 3. Doctor logs in and approves connection request
        self.client.login(username='dr.smith@test.com', password='password123')
        approve_resp = self.client.post(reverse('doctor:approve_patient_request', kwargs={'code_id': code_obj.id}))
        self.assertEqual(approve_resp.status_code, 302)

        code_obj.refresh_from_db()
        patient_unclaimed.refresh_from_db()
        self.assertEqual(code_obj.status, 'APPROVED')
        self.assertEqual(patient_unclaimed.treatment_status, 'ACTIVE')

    def test_advance_aligner_stage(self):
        """Test advancing aligner stage increments current_aligner."""
        self.client.login(username='dr.smith@test.com', password='password123')
        self.assertEqual(self.plan_smith.current_aligner, 4)

        response = self.client.post(reverse('doctor:advance_aligner', kwargs={'patient_id': self.patient_smith.id}))
        self.assertEqual(response.status_code, 302)

        self.plan_smith.refresh_from_db()
        self.assertEqual(self.plan_smith.current_aligner, 5)

    def test_export_patients_csv(self):
        """Test CSV export view generates proper headers and content."""
        self.client.login(username='dr.smith@test.com', password='password123')
        response = self.client.get(reverse('doctor:export_patients_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertContains(response, 'Patient ID')
        self.assertContains(response, 'Tommy')

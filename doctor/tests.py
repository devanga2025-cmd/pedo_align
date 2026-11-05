from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import (
    DoctorProfile, Patient, PatientJoiningCode,
    ClinicalRecord, TreatmentPlan, PhotoMonitoring,
    EmergencyAlert, Appointment, Notification,
    PreoperativePhoto, RadiographRecord, TreatmentOperationRecord,
    Prescription, TreatmentTurn, DoctorTreatmentMedia, MonthlyTreatmentNote
)
import datetime
import io
from PIL import Image
from patient.models import PatientProfile


def create_test_image_file(name='test_photo.jpg'):
    file = io.BytesIO()
    image = Image.new('RGB', (20, 20), color=(14, 165, 233))
    image.save(file, 'JPEG')
    file.seek(0)
    return SimpleUploadedFile(name, file.read(), content_type='image/jpeg')



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
        # Verify emergency button and reports & analytics are removed from dashboard view
        self.assertNotContains(response, 'Emergency Alerts (')
        self.assertNotContains(response, 'Reports & Analytics')

    def test_clinical_records_page_download_report_button(self):
        """Test clinical records page has the Download Report button."""
        self.client.login(username='dr.smith@test.com', password='password123')
        response = self.client.get(reverse('doctor:clinical_records'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Download Report')
        self.assertContains(response, reverse('doctor:export_patients_csv'))

    def test_patient_requests_removes_public_join_portal(self):
        """Test patient requests page does not contain public join portal."""
        self.client.login(username='dr.smith@test.com', password='password123')
        response = self.client.get(reverse('doctor:patient_requests'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Public Join Portal')

    def test_doctor_profile_enhancement_and_update(self):
        """Requirement 1: Doctor specialization taken directly as user input and printed in output."""
        self.client.login(username='dr.smith@test.com', password='password123')
        
        # Verify doctor profile fields
        self.assertEqual(self.doc_smith.email, 'dr.smith@test.com')
        
        # Update professional information with custom user-typed specialization
        custom_spec = 'Pediatric Dentist and Orthodontist Specialist'
        response = self.client.post(reverse('doctor:settings'), {
            'update_profile': '1',
            'full_name': 'Dr. Arthur J. Smith',
            'email': 'dr.arthur.smith@pedoalign.com',
            'phone_number': '+91 9876543210',
            'dental_qualification': 'MDS Orthodontics, Fellow Pedo-Align',
            'specialization': custom_spec,
            'ksdc_registration_number': 'KSDC-998877-A',
            'clinic_name': 'Smith Pediatric & Orthodontic Dental Center',
            'clinic_address': '400 Dental Plaza, Bangalore, KA',
            'bio': 'Specialist in pediatric clear aligner interceptive therapy.',
            'email_notifications': True,
            'sms_alerts': True,
            'emergency_push': True,
        })
        self.assertEqual(response.status_code, 302)
        
        self.doc_smith.refresh_from_db()
        self.assertEqual(self.doc_smith.full_name, 'Dr. Arthur J. Smith')
        self.assertEqual(self.doc_smith.specialization, custom_spec)
        self.assertEqual(self.doc_smith.ksdc_registration_number, 'KSDC-998877-A')
        self.assertEqual(self.doc_smith.clinic_name, 'Smith Pediatric & Orthodontic Dental Center')
        self.assertEqual(self.doc_smith.phone_number, '+91 9876543210')
        self.assertEqual(self.doc_smith.user.email, 'dr.arthur.smith@pedoalign.com')

        # Verify specialization is printed in output in base and settings
        settings_get = self.client.get(reverse('doctor:settings'))
        self.assertContains(settings_get, custom_spec)
        dash_get = self.client.get(reverse('doctor:dashboard'))
        self.assertContains(dash_get, custom_spec)
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

    def test_upper_and_lower_arch_monitoring(self):
        """Requirement 3: Upper & Lower Arch clinical monitoring with progress history."""
        self.client.login(username='dr.smith@test.com', password='password123')

        # Edit treatment plan with distinct Upper and Lower Arch statuses & notes
        edit_url = reverse('doctor:treatment_plan_edit', kwargs={'patient_id': self.patient_smith.id})
        response = self.client.post(edit_url, {
            'total_aligners': 24,
            'current_aligner': 5,
            'aligner_frequency_days': 7,
            'status': 'Active / In Progress',
            'upper_arch_status': 'Maxillary Expansion Active',
            'upper_arch_notes': 'Arch wire/aligner expanding transverse width by 1.5mm.',
            'lower_arch_status': 'Mandibular Leveling',
            'lower_arch_notes': 'Lower anterior crowding resolving smoothly.',
            'treatment_instructions': 'Wear aligners 22 hours daily. Change every 7 days strictly.',
        })
        self.assertEqual(response.status_code, 302)

        self.plan_smith.refresh_from_db()
        self.assertEqual(self.plan_smith.upper_arch_status, 'Maxillary Expansion Active')
        self.assertEqual(self.plan_smith.lower_arch_status, 'Mandibular Leveling')
        self.assertIn('transverse width', self.plan_smith.upper_arch_notes)
        self.assertIn('crowding resolving', self.plan_smith.lower_arch_notes)

        # Verify ArchProgressHistory entries were generated for both arches
        upper_hist = self.plan_smith.arch_histories.filter(arch='UPPER')
        lower_hist = self.plan_smith.arch_histories.filter(arch='LOWER')
        self.assertTrue(upper_hist.exists())
        self.assertTrue(lower_hist.exists())

    def test_dedicated_tray_management(self):
        """Requirement 8: Dedicated Tray Management configuration & schedule pause."""
        self.client.login(username='dr.smith@test.com', password='password123')
        
        edit_url = reverse('doctor:treatment_plan_edit', kwargs={'patient_id': self.patient_smith.id})
        next_change = timezone.localdate() + datetime.timedelta(days=7)
        response = self.client.post(edit_url, {
            'total_aligners': 20,
            'current_aligner': 5,
            'aligner_frequency_days': 7,
            'next_tray_change_date': next_change.strftime('%Y-%m-%d'),
            'is_paused': True,
            'pause_reason': 'Minor molar tracking lag; wear aligner #5 for additional 5 days.',
            'upper_arch_status': 'Holding',
            'lower_arch_status': 'Holding',
            'treatment_instructions': 'Hold current tray. Use chewies 15 minutes morning and night.',
            'status': 'Paused / Under Review',
        })
        self.assertEqual(response.status_code, 302)

        self.plan_smith.refresh_from_db()
        self.assertEqual(self.plan_smith.total_aligners, 20)
        self.assertEqual(self.plan_smith.current_aligner, 5)
        self.assertEqual(self.plan_smith.next_aligner, 6)
        self.assertTrue(self.plan_smith.is_paused)
        self.assertEqual(self.plan_smith.next_tray_change_date, next_change)
        self.assertIn('Minor molar tracking lag', self.plan_smith.pause_reason)

    def test_photo_monitoring_and_comparison_views(self):
        """Requirement 4 & 5: Review 5-angle photos & multi-stage comparison."""
        self.client.login(username='dr.smith@test.com', password='password123')

        p1 = PhotoMonitoring.objects.create(
            patient=self.patient_smith,
            week_number=1,
            aligner_stage=1,
            upload_date=timezone.localdate() - datetime.timedelta(days=14),
            is_before_sample=True,
            patient_notes='Week 1 baseline photos'
        )
        p2 = PhotoMonitoring.objects.create(
            patient=self.patient_smith,
            week_number=3,
            aligner_stage=3,
            upload_date=timezone.localdate(),
            is_after_sample=True,
            patient_notes='Week 3 progress photos'
        )

        # 1. 5-Angle Review view
        review_url = reverse('doctor:photo_review', kwargs={'photo_id': p1.id})
        resp_review = self.client.get(review_url)
        self.assertEqual(resp_review.status_code, 200)
        self.assertContains(resp_review, 'Front Bite')
        self.assertContains(resp_review, 'Upper Arch')
        self.assertContains(resp_review, 'Lower Arch')

        # 2. Multi-Stage Comparison view
        compare_url = reverse('doctor:photo_compare', kwargs={'patient_id': self.patient_smith.id})
        resp_compare = self.client.get(compare_url, {'left_id': p1.id, 'right_id': p2.id, 'angle': 'front'})
        self.assertEqual(resp_compare.status_code, 200)
        self.assertContains(resp_compare, 'Pre-Treatment Photos')
        self.assertContains(resp_compare, 'During-Treatment Photos')
        self.assertContains(resp_compare, 'Latest Treatment Photos')
        self.assertContains(resp_compare, 'Do not automatically diagnose or calculate clinical outcomes')

    def test_emergency_alert_doctor_workflow(self):
        """Requirement 7: Doctor receives emergency alert, responds with guidance, and resolves."""
        self.client.login(username='dr.smith@test.com', password='password123')

        alert = EmergencyAlert.objects.create(
            patient=self.patient_smith,
            issue_type='BROKEN_ALIGNER',
            severity='HIGH',
            description='Crack on upper left canine bracket area.',
            status='NEW'
        )

        # Doctor responds to emergency
        respond_url = reverse('doctor:emergency_respond', kwargs={'alert_id': alert.id})
        resp = self.client.post(respond_url, {
            'doctor_response': 'Switch to previous Tray #3 immediately and visit the clinic tomorrow for inspection.',
            'status': 'RESPONDED'
        })
        self.assertEqual(resp.status_code, 302)

        alert.refresh_from_db()
        self.assertEqual(alert.status, 'RESPONDED')
        self.assertIn('Switch to previous Tray #3', alert.doctor_response)

        # Quick resolve
        resolve_url = reverse('doctor:emergency_resolve_quick', kwargs={'alert_id': alert.id})
        resp_resolve = self.client.post(resolve_url)
        self.assertEqual(resp_resolve.status_code, 302)

        alert.refresh_from_db()
        self.assertEqual(alert.status, 'RESOLVED')
        self.assertIsNotNone(alert.resolved_at)


class PatientClinicalRecordAndJourneyTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_doc = User.objects.create_user(
            username='dr.clinical@test.com',
            email='dr.clinical@test.com',
            password='password123'
        )
        self.doctor = DoctorProfile.objects.create(
            user=self.user_doc,
            full_name='Aarav Mehta',
            phone_number='9876501234',
            dental_qualification='BDS, MDS Orthodontics',
            specialization='Orthodontist',
            ksdc_registration_number='KSDC-9876-A',
            clinic_name='Mehta Smiles Orthodontics',
            clinic_address='100 MG Road, Bangalore'
        )
        self.patient = Patient.objects.create(
            doctor=self.doctor,
            patient_id='PA-PT-CLIN-01',
            first_name='Rohan',
            last_name='Sharma',
            age=11,
            gender='Male',
            patient_category='CHILD',
            parent_guardian_name='Suresh Sharma',
            parent_guardian_phone='9888877777',
            parent_guardian_relationship='Father',
            treatment_start_date=timezone.localdate() - datetime.timedelta(days=60),
            treatment_duration_months=12,
            treatment_status='ACTIVE',
            email='rohan.sharma@test.com'
        )
        self.patient_user = User.objects.create_user(
            username='rohan.sharma@test.com',
            email='rohan.sharma@test.com',
            password='password123'
        )
        self.patient_profile = PatientProfile.objects.create(
            user=self.patient_user,
            full_name=self.patient.full_name,
            connected_patient_record=self.patient,
            connection_status='CONNECTED'
        )

    def test_preop_photos_upload_and_delete(self):
        self.client.login(username='dr.clinical@test.com', password='password123')
        upload_url = reverse('doctor:preop_photo_upload', kwargs={'patient_id': self.patient.id})
        test_img = create_test_image_file('preop_1.jpg')
        resp = self.client.post(upload_url, {
            'photo': test_img,
            'description': 'Initial baseline frontal occlusion view'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.patient.preoperative_photos.count(), 1)
        preop = self.patient.preoperative_photos.first()
        self.assertEqual(preop.description, 'Initial baseline frontal occlusion view')

        # Test delete
        del_url = reverse('doctor:preop_photo_delete', kwargs={'patient_id': self.patient.id, 'photo_id': preop.id})
        resp_del = self.client.post(del_url)
        self.assertEqual(resp_del.status_code, 302)
        self.assertEqual(self.patient.preoperative_photos.count(), 0)

    def test_radiograph_type1_and_type2_uploads(self):
        self.client.login(username='dr.clinical@test.com', password='password123')
        upload_url = reverse('doctor:radiograph_upload', kwargs={'patient_id': self.patient.id})
        
        # Upload Type 1
        img1 = create_test_image_file('opg_panoramic.jpg')
        resp1 = self.client.post(upload_url, {
            'radiograph_type': 'TYPE_1',
            'image': img1,
            'description': 'Baseline OPG Panoramic radiograph',
            'examination_date': timezone.localdate().strftime('%Y-%m-%d'),
        })
        self.assertEqual(resp1.status_code, 302)
        self.assertEqual(self.patient.radiographs.filter(radiograph_type='TYPE_1').count(), 1)

        # Upload Type 2
        img2 = create_test_image_file('lateral_ceph.jpg')
        resp2 = self.client.post(upload_url, {
            'radiograph_type': 'TYPE_2',
            'image': img2,
            'description': 'Baseline Lateral Cephalogram',
            'examination_date': timezone.localdate().strftime('%Y-%m-%d'),
        })
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(self.patient.radiographs.filter(radiograph_type='TYPE_2').count(), 1)

    def test_treatment_operation_record(self):
        self.client.login(username='dr.clinical@test.com', password='password123')
        op_url = reverse('doctor:operation_record_create', kwargs={'patient_id': self.patient.id})
        resp = self.client.post(op_url, {
            'record_date': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'current_condition': 'Upper arch crowding, deep bite 4mm',
            'examination_findings': 'Class II molar relationship, rotated upper incisors',
            'identified_problems': 'Crowding, overjet',
            'operation_performed': 'Composite button placement, IPR 0.2mm on lower anterior',
            'treatment_description': 'IPR completed between 31 and 41; attachments bonded.',
            'doctor_observations': 'Patient compliant; trays seated snugly with chewies.',
            'next_treatment_steps': 'Deliver aligner sets #5 through #8 at next 20-day follow-up.',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.patient.operation_records.count(), 1)
        record = self.patient.operation_records.first()
        self.assertIn('Composite button placement', record.operation_performed)

    def test_prescription_generation_and_print_view(self):
        self.client.login(username='dr.clinical@test.com', password='password123')
        presc_create_url = reverse('doctor:prescription_create', kwargs={'patient_id': self.patient.id})
        resp = self.client.post(presc_create_url, {
            'prescription_date': timezone.localdate().strftime('%Y-%m-%d'),
            'diagnosis': 'Class II malocclusion with localized gingival inflammation',
            'medicines_data': '1. Chlorhexidine 0.2% mouthwash - 10ml twice daily for 7 days.\n2. Paracetamol 500mg - SOS for discomfort.',
            'special_instructions': 'Rinse thoroughly after meals. Wear aligners 22h daily.',
            'next_followup_date': (timezone.localdate() + datetime.timedelta(days=20)).strftime('%Y-%m-%d'),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.patient.prescriptions.count(), 1)
        presc = self.patient.prescriptions.first()

        # View prescription detail
        detail_url = reverse('doctor:prescription_detail', kwargs={'patient_id': self.patient.id, 'presc_id': presc.id})
        resp_detail = self.client.get(detail_url)
        self.assertEqual(resp_detail.status_code, 200)
        self.assertContains(resp_detail, 'Chlorhexidine 0.2%')
        self.assertContains(resp_detail, 'Dr. Aarav Mehta')
        self.assertContains(resp_detail, 'KSDC-9876-A')

        # View printable / PDF sheet
        print_url = reverse('doctor:prescription_print', kwargs={'patient_id': self.patient.id, 'presc_id': presc.id})
        resp_print = self.client.get(print_url)
        self.assertEqual(resp_print.status_code, 200)
        self.assertContains(resp_print, 'Prescription')
        self.assertContains(resp_print, 'Mehta Smiles Orthodontics')

    def test_treatment_duration_and_current_month_calculation(self):
        self.client.login(username='dr.clinical@test.com', password='password123')
        update_url = reverse('doctor:treatment_duration_update', kwargs={'patient_id': self.patient.id})
        resp = self.client.post(update_url, {
            'treatment_duration_months': 6,
            'treatment_start_date': (timezone.localdate() - datetime.timedelta(days=90)).strftime('%Y-%m-%d'),
            'treatment_status': 'ACTIVE',
        })
        self.assertEqual(resp.status_code, 302)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.treatment_duration_months, 6)
        current_month = self.patient.calculate_current_treatment_month()
        self.assertGreaterEqual(current_month, 3)

    def test_turn_quest_sequence(self):
        self.client.login(username='dr.clinical@test.com', password='password123')
        turn_create_url = reverse('doctor:turn_quest_create', kwargs={'patient_id': self.patient.id})
        resp = self.client.post(turn_create_url, {
            'turn_number': 1,
            'start_date': timezone.localdate().strftime('%Y-%m-%d'),
            'completion_date': (timezone.localdate() + datetime.timedelta(days=14)).strftime('%Y-%m-%d'),
            'status': 'IN_PROGRESS',
            'instructions': 'Turn #1: Expansion and leveling stage. Wear 22h daily.',
            'next_turn_date': (timezone.localdate() + datetime.timedelta(days=14)).strftime('%Y-%m-%d'),
            'doctor_remarks': 'Initial aligner tracking well; good engagement.',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.patient.treatment_turns.count(), 1)
        turn = self.patient.treatment_turns.first()
        self.assertEqual(turn.turn_number, 1)

    def test_complete_12_stage_treatment_timeline(self):
        stages = self.patient.get_timeline_stages()
        self.assertEqual(len(stages), 12)
        self.assertEqual(stages[0]['name'], 'Patient Registration')
        self.assertTrue(stages[0]['is_completed'])
        stage_names = [s['name'] for s in stages]
        self.assertIn('Preoperative Photo Upload', stage_names)
        self.assertIn('Radiograph Upload', stage_names)
        self.assertIn('Appointment Scheduling', stage_names)
        self.assertIn('Treatment Started', stage_names)
        self.assertIn('Prescription Generated', stage_names)
        self.assertIn('Turn / Treatment Sequence Updates', stage_names)
        self.assertIn('Treatment Completed', stage_names)

    def test_patient_archive_and_deactivation(self):
        self.client.login(username='dr.clinical@test.com', password='password123')
        archive_url = reverse('doctor:archive_patient', kwargs={'patient_id': self.patient.id})
        
        # Option B: Deactivate patient (soft-delete)
        resp = self.client.post(archive_url, {
            'action_type': 'DEACTIVATE',
            'reason': 'Patient moved to another city; archived record.'
        })
        self.assertEqual(resp.status_code, 302)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_deactivated)
        self.assertTrue(self.patient.is_archived)

        # Verify patient is in archived patients list
        archived_list_url = reverse('doctor:archived_patients')
        resp_list = self.client.get(archived_list_url)
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, 'Rohan Sharma')
        self.assertContains(resp_list, 'Patient moved to another city')

        # Restore patient
        restore_url = reverse('doctor:restore_patient', kwargs={'patient_id': self.patient.id})
        resp_restore = self.client.post(restore_url)
        self.assertEqual(resp_restore.status_code, 302)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_deactivated)
        self.assertFalse(self.patient.is_archived)

    def test_delete_patient_account_and_access_block(self):
        """Test that doctor deleting a patient account deactivates credentials, prevents login, and retains doctor history."""
        # Use patient user and portal profile from setUp
        profile = self.patient_profile
        patient_user = self.patient_user
        joining_code = PatientJoiningCode.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            code='PA-DELTEST',
            status='APPROVED'
        )

        self.client.login(username='dr.clinical@test.com', password='password123')
        
        # 1. Active patient list shows "Delete A/C" button on cards
        resp_before = self.client.get(reverse('doctor:patient_list'))
        self.assertEqual(resp_before.status_code, 200)
        self.assertContains(resp_before, 'Delete A/C')
        self.assertContains(resp_before, 'Total Monitored in Career')

        delete_ac_url = reverse('doctor:delete_patient_account', kwargs={'patient_id': self.patient.id})

        # 2. Post to delete account
        resp = self.client.post(delete_ac_url, {
            'reason': 'Orthodontic therapy completed; final retainers delivered. Account closed.'
        })
        self.assertEqual(resp.status_code, 302)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_deactivated)
        self.assertTrue(self.patient.is_archived)
        self.assertEqual(self.patient.treatment_status, 'COMPLETED')
        profile.refresh_from_db()
        self.assertEqual(profile.connection_status, 'DISCONNECTED')
        patient_user.refresh_from_db()
        self.assertFalse(patient_user.is_active)

        # 3. Check doctor's patient list and history counters
        resp_list = self.client.get(reverse('doctor:patient_list'))
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, 'Total Monitored in Career')
        # Total career monitored count still includes self.patient
        self.assertEqual(resp_list.context['lifetime_count'], Patient.objects.filter(doctor=self.doctor).count())
        self.assertEqual(resp_list.context['archived_count'], 1)

        # 4. Patient portal login attempt must be strictly blocked
        self.client.logout()
        login_url = reverse('patient:login')
        resp_login_pwd = self.client.post(login_url, {
            'login_type': 'password',
            'login_identifier': self.patient.email,
            'password': 'password123',
        })
        self.assertContains(resp_login_pwd, 'deleted / closed following treatment completion')

        # Code login attempt must also be blocked
        resp_login_code = self.client.post(login_url, {
            'login_type': 'code',
            'joining_code': joining_code.code,
        })
        self.assertContains(resp_login_code, 'deleted / closed following treatment completion')

    def test_auto_calculate_age_from_dob(self):
        """Test DOB automatically calculates age in patient form clean."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        create_url = reverse('doctor:patient_create')
        ten_years_ago = (timezone.localdate() - datetime.timedelta(days=365 * 10 + 2)).strftime('%Y-%m-%d')
        resp = self.client.post(create_url, {
            'first_name': 'Dev',
            'last_name': 'Patel',
            'patient_category': 'CHILD',
            'gender': 'Male',
            'date_of_birth': ten_years_ago,
            # age omitted to test auto-calculation
            'phone': '9988776655',
            'appointment_frequency': 'MONTHLY',
            'treatment_duration_months': 12,
        })
        self.assertEqual(resp.status_code, 302)
        created_pt = Patient.objects.filter(phone='9988776655').first()
        self.assertIsNotNone(created_pt)
        self.assertEqual(created_pt.age, 10)

    def test_treatment_plans_card_has_open_button(self):
        """Test Treatment Plans page has an 'Open' button on each patient card."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        TreatmentPlan.objects.get_or_create(
            patient=self.patient,
            defaults={'total_aligners': 20, 'current_aligner': 1}
        )
        resp = self.client.get(reverse('doctor:treatment_plans'))
        self.assertEqual(resp.status_code, 200)
        open_url = reverse('doctor:patient_clinical_journey', kwargs={'patient_id': self.patient.id})
        self.assertContains(resp, open_url)
        self.assertContains(resp, 'Open')

    def test_treatment_plans_search_and_table_format(self):
        """Test Treatment Plans page has search bar, search button, and table view toggle."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        TreatmentPlan.objects.get_or_create(
            patient=self.patient,
            defaults={'total_aligners': 24, 'current_aligner': 5, 'status': 'Active / In Progress'}
        )
        url = reverse('doctor:treatment_plans')

        # 1. Verify Grid view has Search input, button, and view switches
        resp_grid = self.client.get(url)
        self.assertEqual(resp_grid.status_code, 200)
        self.assertContains(resp_grid, 'Search')
        self.assertContains(resp_grid, 'placeholder="Search by patient name, ID, phone..."')
        self.assertContains(resp_grid, 'Cards')
        self.assertContains(resp_grid, 'Table')
        self.assertContains(resp_grid, 'Rohan Sharma')

        # 2. Verify Table format view
        resp_table = self.client.get(f"{url}?view=table")
        self.assertEqual(resp_table.status_code, 200)
        self.assertContains(resp_table, '<table')
        self.assertContains(resp_table, 'Aligner Stage')
        self.assertContains(resp_table, 'Duration & Wear')
        self.assertContains(resp_table, 'Compliance')
        self.assertContains(resp_table, 'Tray #5 of 24')
        self.assertContains(resp_table, 'Open')

        # 3. Test Search filter
        resp_search_match = self.client.get(f"{url}?q=Rohan")
        self.assertEqual(len(resp_search_match.context['plans']), 1)
        resp_search_miss = self.client.get(f"{url}?q=NonExistentPatientXYZ")
        self.assertEqual(len(resp_search_miss.context['plans']), 0)
        self.assertContains(resp_search_miss, 'No Treatment Plans Found')

    def test_clinical_journey_preop_3_photos_compulsory(self):
        """Test that exactly 3 preoperative photos are strictly compulsory to save."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        journey_url = reverse('doctor:patient_clinical_journey', kwargs={'patient_id': self.patient.id})
        
        # 1. Attempt with only 1 photo
        img1 = create_test_image_file('photo_only_1.jpg')
        resp_invalid = self.client.post(journey_url, {
            'action': 'save_preop',
            'photo_1': img1,
            'description_1': 'Frontal view',
        })
        self.assertEqual(self.patient.preoperative_photos.count(), 0)
        self.assertContains(resp_invalid, '3 preoperative photos are compulsory')

        # 2. Attempt with all 3 photos
        img1 = create_test_image_file('photo_1.jpg')
        img2 = create_test_image_file('photo_2.jpg')
        img3 = create_test_image_file('photo_3.jpg')
        resp_valid = self.client.post(journey_url, {
            'action': 'save_preop',
            'photo_1': img1,
            'description_1': 'Frontal View in Centric Occlusion',
            'photo_2': img2,
            'description_2': 'Upper Arch Occlusal View',
            'photo_3': img3,
            'description_3': 'Lower Arch Occlusal View',
        })
        self.assertEqual(resp_valid.status_code, 302)
        self.assertRedirects(resp_valid, f"{journey_url}?step=2")
        self.assertEqual(self.patient.preoperative_photos.count(), 3)

    def test_clinical_journey_preop_add_more_photos_with_plus(self):
        """Test that doctor can add more photos beyond the 3 compulsory ones."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        journey_url = reverse('doctor:patient_clinical_journey', kwargs={'patient_id': self.patient.id})

        # 1. Verify GET renders Add More Photos (+) UI controls
        resp_get = self.client.get(journey_url)
        self.assertContains(resp_get, 'Add More Photos (+)')
        self.assertContains(resp_get, 'addExtraPhotoSlot()')

        # 2. Submit 3 compulsory photos + 2 extra photos dynamically added via "+"
        img1 = create_test_image_file('photo_1.jpg')
        img2 = create_test_image_file('photo_2.jpg')
        img3 = create_test_image_file('photo_3.jpg')
        extra_img4 = create_test_image_file('extra_4.jpg')
        extra_img5 = create_test_image_file('extra_5.jpg')

        resp_post = self.client.post(journey_url, {
            'action': 'save_preop',
            'photo_1': img1,
            'description_1': 'Frontal View',
            'photo_2': img2,
            'description_2': 'Upper Arch',
            'photo_3': img3,
            'description_3': 'Lower Arch',
            'extra_photos': [extra_img4, extra_img5],
            'extra_descriptions': ['Right Lateral Angle', 'Left Lateral Angle'],
        })
        self.assertEqual(resp_post.status_code, 302)
        # 3 compulsory + 2 additional = 5 photos saved
        self.assertEqual(self.patient.preoperative_photos.count(), 5)

        # 3. Add one more photo via add_extra_preop action
        extra_img6 = create_test_image_file('extra_6.jpg')
        resp_extra = self.client.post(journey_url, {
            'action': 'add_extra_preop',
            'title': 'Smile 45-degree angle',
            'photo': extra_img6,
            'description': 'Profile smile aesthetic evaluation',
        })
        self.assertEqual(resp_extra.status_code, 302)
        self.assertEqual(self.patient.preoperative_photos.count(), 6)
        new_photo = self.patient.preoperative_photos.order_by('-uploaded_at').first()
        self.assertEqual(new_photo.title, 'Smile 45-degree angle')

    def test_clinical_journey_radiographs_opg_and_lateral_ceph(self):
        """Test uploading OPG and LATERAL_CEPHALOGRAPH radiographs in step 2."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        journey_url = reverse('doctor:patient_clinical_journey', kwargs={'patient_id': self.patient.id})
        
        # Upload OPG
        opg_img = create_test_image_file('opg.jpg')
        resp_opg = self.client.post(journey_url, {
            'action': 'save_radiograph',
            'radiograph_type': 'OPG',
            'image': opg_img,
            'description': 'Panoramic full dentition view',
            'examination_date': timezone.localdate().strftime('%Y-%m-%d'),
        })
        self.assertEqual(resp_opg.status_code, 302)
        self.assertEqual(self.patient.radiographs.filter(radiograph_type='OPG').count(), 1)

        # Upload Lateral Cephalograph
        ceph_img = create_test_image_file('ceph.jpg')
        resp_ceph = self.client.post(journey_url, {
            'action': 'save_radiograph',
            'radiograph_type': 'LATERAL_CEPHALOGRAPH',
            'image': ceph_img,
            'description': 'Lateral cephalogram showing ANB angle',
            'examination_date': timezone.localdate().strftime('%Y-%m-%d'),
        })
        self.assertEqual(resp_ceph.status_code, 302)
        self.assertEqual(self.patient.radiographs.filter(radiograph_type='LATERAL_CEPHALOGRAPH').count(), 1)

    def test_clinical_journey_schedule_hospital_appointment(self):
        """Test scheduling next hospital appointment in step 3."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        journey_url = reverse('doctor:patient_clinical_journey', kwargs={'patient_id': self.patient.id})
        
        visit_date = (timezone.localdate() + datetime.timedelta(days=20)).strftime('%Y-%m-%d')
        resp_appt = self.client.post(journey_url, {
            'action': 'save_appointment',
            'scheduled_date': visit_date,
            'scheduled_time': '10:30',
            'appointment_type': 'ROUTINE_CHECKUP',
            'duration_minutes': '30',
            'instructions': 'Bring current aligner set #1 and previous X-ray films to the hospital.',
        })
        self.assertEqual(resp_appt.status_code, 302)
        appt = self.patient.appointments.filter(scheduled_date=visit_date).first()
        self.assertIsNotNone(appt)
        self.assertEqual(appt.scheduled_time.strftime('%H:%M'), '10:30')
        self.assertIn('Bring current aligner set #1', appt.instructions)

    def test_step4_patient_eligibility_and_photo_monitoring_selector(self):
        """Test that only patients who completed Steps 1, 2, and 3 are eligible for Step 4."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        
        # Initially, self.patient has 0 pre-op photos, 0 radiographs, 0 appointments
        self.assertFalse(self.patient.has_completed_step3)
        
        photo_mon_url = reverse('doctor:photo_monitoring')
        resp = self.client.get(photo_mon_url)
        self.assertEqual(resp.status_code, 200)
        # self.patient must NOT be in eligible_patients
        eligible_ids = [p.id for p in resp.context['eligible_patients']]
        self.assertNotIn(self.patient.id, eligible_ids)

        # Complete Step 1: 3 Pre-op photos
        PreoperativePhoto.objects.create(patient=self.patient, photo=create_test_image_file('p1.jpg'), title='Frontal')
        PreoperativePhoto.objects.create(patient=self.patient, photo=create_test_image_file('p2.jpg'), title='Upper')
        PreoperativePhoto.objects.create(patient=self.patient, photo=create_test_image_file('p3.jpg'), title='Lower')
        self.assertFalse(self.patient.has_completed_step3)

        # Complete Step 2: Radiograph
        RadiographRecord.objects.create(
            patient=self.patient,
            radiograph_type='OPG',
            image=create_test_image_file('opg.jpg'),
            title='Panoramic OPG'
        )
        self.assertFalse(self.patient.has_completed_step3)

        # Complete Step 3: Hospital appointment
        Appointment.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            scheduled_date=timezone.localdate() + datetime.timedelta(days=20),
            scheduled_time='11:00',
            status='UPCOMING'
        )

        # Now all 3 steps are complete!
        self.assertTrue(self.patient.has_completed_step3)

        # Check Photo Monitoring page: self.patient must now appear in eligible_patients
        resp2 = self.client.get(photo_mon_url)
        self.assertEqual(resp2.status_code, 200)
        eligible_ids2 = [p.id for p in resp2.context['eligible_patients']]
        self.assertIn(self.patient.id, eligible_ids2)
        self.assertContains(resp2, 'Completed Intake Patients')
        self.assertContains(resp2, self.patient.full_name)
        self.assertContains(resp2, 'Open')

    def test_step4_turn_quest_operation_prescription_with_photo_and_video(self):
        """Test prescribing Turn Quest operation with clinical problem diagnosis, weekly cadence, photo, and video."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        
        # Complete Steps 1-3 first
        for i in range(1, 4):
            PreoperativePhoto.objects.create(patient=self.patient, photo=create_test_image_file(f'preop_{i}.jpg'), title=f'View {i}')
        RadiographRecord.objects.create(patient=self.patient, radiograph_type='OPG', image=create_test_image_file('opg.jpg'))
        Appointment.objects.create(doctor=self.doctor, patient=self.patient, scheduled_date=timezone.localdate() + datetime.timedelta(days=20), scheduled_time='10:00')

        photo_mon_url = reverse('doctor:photo_monitoring')
        photo_file = create_test_image_file('turnquest_ref.jpg')
        video_file = SimpleUploadedFile("turnquest_demo.mp4", b"dummy video bytes", content_type="video/mp4")

        problem_text = "Severe anterior crowding with transverse maxillary discrepancy and deep bite."
        resp = self.client.post(photo_mon_url, {
            'action': 'save_step4_operation',
            'patient_id': self.patient.id,
            'patient_problem': problem_text,
            'operation_type': 'TURN_QUEST',
            'update_frequency': 'WEEKLY',
            'photo': photo_file,
            'photo_description': 'Turn Quest key slot orientation and initial seating',
            'video': video_file,
            'video_description': 'Turn Quest key turning demonstration for parents',
            'treatment_stage': 'Stage 1: Turn Quest Expansion Phase',
            'doctor_instructions': 'Turn the key one quarter turn clockwise every Sunday evening.',
        })
        self.assertEqual(resp.status_code, 302)

        # Verify DoctorTreatmentMedia was created properly
        media = DoctorTreatmentMedia.objects.filter(patient=self.patient, is_current=True).first()
        self.assertIsNotNone(media)
        self.assertEqual(media.operation_type, 'TURN_QUEST')
        self.assertEqual(media.operation_name, 'Turn Quest')
        self.assertEqual(media.update_frequency, 'WEEKLY')
        self.assertEqual(media.patient_problem, problem_text)
        self.assertTrue(bool(media.photo))
        self.assertTrue(bool(media.video))

        # Verify permanent TreatmentOperationRecord
        op_record = TreatmentOperationRecord.objects.filter(patient=self.patient).first()
        self.assertIsNotNone(op_record)
        self.assertEqual(op_record.operation_performed, 'Turn Quest')
        self.assertEqual(op_record.identified_problems, problem_text)

        # Verify Patient model fields updated
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.current_operation, 'Turn Quest')
        self.assertEqual(self.patient.monitoring_frequency, 'WEEKLY')
        self.assertEqual(self.patient.diagnosed_problem, problem_text)

    def test_step4_other_custom_operation_with_daily_cadence(self):
        """Test prescribing custom other operation with custom name and daily update cadence."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        
        # Complete Steps 1-3 first
        for i in range(1, 4):
            PreoperativePhoto.objects.create(patient=self.patient, photo=create_test_image_file(f'pre_{i}.jpg'), title=f'Angle {i}')
        RadiographRecord.objects.create(patient=self.patient, radiograph_type='LATERAL_CEPHALOGRAPH', image=create_test_image_file('ceph.jpg'))
        Appointment.objects.create(doctor=self.doctor, patient=self.patient, scheduled_date=timezone.localdate() + datetime.timedelta(days=15), scheduled_time='14:00')

        photo_mon_url = reverse('doctor:photo_monitoring')
        photo_file = create_test_image_file('rpe_appliance.jpg')
        custom_name = "Rapid Palatal Expander (RPE)"
        problem_text = "Bilateral posterior crossbite with high arched palate."

        resp = self.client.post(photo_mon_url, {
            'action': 'save_step4_operation',
            'patient_id': self.patient.id,
            'patient_problem': problem_text,
            'operation_type': 'OTHER',
            'custom_operation_name': custom_name,
            'update_frequency': 'DAILY',
            'photo': photo_file,
            'photo_description': 'RPE appliance activation screw view',
            'treatment_stage': 'Phase 1: Rapid Palatal Expansion',
            'doctor_instructions': 'Submit 1 daily occlusal photo after evening activation.',
        })
        self.assertEqual(resp.status_code, 302)

        media = DoctorTreatmentMedia.objects.filter(patient=self.patient, is_current=True).first()
        self.assertIsNotNone(media)
        self.assertEqual(media.operation_type, 'OTHER')
        self.assertEqual(media.operation_name, custom_name)
        self.assertEqual(media.update_frequency, 'DAILY')

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.current_operation, custom_name)
        self.assertEqual(self.patient.monitoring_frequency, 'DAILY')
        self.assertEqual(self.patient.diagnosed_problem, problem_text)

    def test_dedicated_step4_operation_page_get_and_post(self):
        """Test GET and POST on the dedicated Step 4 page (/photos/step4/<patient_id>/)."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        
        # Complete Steps 1-3 first
        for i in range(1, 4):
            PreoperativePhoto.objects.create(patient=self.patient, photo=create_test_image_file(f'preop_s4_{i}.jpg'), title=f'View {i}')
        RadiographRecord.objects.create(patient=self.patient, radiograph_type='OPG', image=create_test_image_file('opg_s4.jpg'))
        Appointment.objects.create(doctor=self.doctor, patient=self.patient, scheduled_date=timezone.localdate() + datetime.timedelta(days=20), scheduled_time='10:00')

        step4_url = reverse('doctor:step4_operation', kwargs={'patient_id': self.patient.id})
        
        # 1. GET page
        resp_get = self.client.get(step4_url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, 'Step 4: Patient Problem Diagnosis')
        self.assertContains(resp_get, self.patient.full_name)
        self.assertContains(resp_get, 'Turn Quest')

        # 2. POST prescription
        photo_file = create_test_image_file('tq_photo.jpg')
        video_file = SimpleUploadedFile("tq_video.mp4", b"dummy video bytes", content_type="video/mp4")
        prob_text = "Severe crowding with narrow arch and overjet."

        resp_post = self.client.post(step4_url, {
            'action': 'save_step4_operation',
            'patient_problem': prob_text,
            'operation_type': 'TURN_QUEST',
            'update_frequency': 'WEEKLY',
            'photo': photo_file,
            'photo_description': 'Turn Quest initial placement',
            'video': video_file,
            'video_description': 'Key turning technique video',
            'treatment_stage': 'Stage 1: Turn Quest Activation',
            'doctor_instructions': 'Turn once weekly every Sunday.',
        })
        self.assertEqual(resp_post.status_code, 302)

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.current_operation, 'Turn Quest')
        self.assertEqual(self.patient.monitoring_frequency, 'WEEKLY')
        self.assertEqual(self.patient.diagnosed_problem, prob_text)

        # 3. Verify in Photo Monitoring Table
        photo_mon_url = reverse('doctor:photo_monitoring')
        resp_table = self.client.get(photo_mon_url)
        self.assertEqual(resp_table.status_code, 200)
        self.assertContains(resp_table, 'Completed Intake Patients (Step 4 Operation Ready)')
        self.assertContains(resp_table, self.patient.full_name)
        self.assertContains(resp_table, 'Open')

    def test_doctor_upload_notifications_for_patient(self):
        """Test that doctor uploading photos, radiographs, and appointments triggers patient notifications."""
        self.client.login(username='dr.clinical@test.com', password='password123')
        journey_url = reverse('doctor:patient_clinical_journey', kwargs={'patient_id': self.patient.id})
        
        # 1. Doctor saves Step 1 preoperative photos
        p1 = create_test_image_file('p1.jpg')
        p2 = create_test_image_file('p2.jpg')
        p3 = create_test_image_file('p3.jpg')
        resp = self.client.post(journey_url, {
            'action': 'save_preop',
            'photo_1': p1,
            'description_1': 'Frontal View',
            'photo_2': p2,
            'description_2': 'Upper Arch',
            'photo_3': p3,
            'description_3': 'Lower Arch',
        })
        self.assertEqual(resp.status_code, 302)
        from patient.models import PatientNotification
        self.assertTrue(PatientNotification.objects.filter(
            patient=self.patient_profile,
            notification_type='DOCTOR_INSTRUCTION',
            title__icontains='Preoperative Photographs'
        ).exists())

        # 2. Doctor saves Step 2 Radiograph
        rad_img = create_test_image_file('opg_test.jpg')
        resp_rad = self.client.post(journey_url, {
            'action': 'save_radiograph',
            'radiograph_type': 'OPG',
            'image': rad_img,
            'description': 'Full panoramic radiograph',
            'examination_date': timezone.localdate().strftime('%Y-%m-%d'),
        })
        self.assertEqual(resp_rad.status_code, 302)
        self.assertTrue(PatientNotification.objects.filter(
            patient=self.patient_profile,
            notification_type='DOCTOR_INSTRUCTION',
            title__icontains='Radiograph'
        ).exists())

        # 3. Doctor saves Step 3 Appointment
        appt_date = (timezone.localdate() + datetime.timedelta(days=20)).strftime('%Y-%m-%d')
        resp_appt = self.client.post(journey_url, {
            'action': 'save_appointment',
            'scheduled_date': appt_date,
            'scheduled_time': '11:00',
            'appointment_type': 'ROUTINE_CHECKUP',
            'instructions': 'Bring current aligner trays',
            'duration_minutes': 30,
        })
        self.assertEqual(resp_appt.status_code, 302)
        self.assertTrue(PatientNotification.objects.filter(
            patient=self.patient_profile,
            notification_type='APPOINTMENT',
            title__icontains='Hospital Visit'
        ).exists())





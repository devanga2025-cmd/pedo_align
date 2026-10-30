from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from doctor.models import (
    DoctorProfile, Patient, PatientJoiningCode,
    ClinicalRecord, TreatmentPlan, PhotoMonitoring,
    EmergencyAlert, Appointment, Notification, PatientActivityLog
)
import datetime


class Command(BaseCommand):
    help = 'Seeds realistic doctor profiles, pediatric orthodontic patients, and monitoring records.'

    def handle(self, *args, **options):
        self.stdout.write("Seeding PEDO ALIGN doctor and patient data...")

        # 1. Doctor 1: Dr. Arthur Smith
        user1, _ = User.objects.get_or_create(
            username='dr.smith@pedoalign.com',
            defaults={
                'email': 'dr.smith@pedoalign.com',
                'first_name': 'Arthur',
                'last_name': 'Smith'
            }
        )
        user1.set_password('password123')
        user1.save()

        doc1, _ = DoctorProfile.objects.get_or_create(
            user=user1,
            defaults={
                'full_name': 'Arthur Smith',
                'phone_number': '+1 (555) 234-5678',
                'dental_qualification': 'MDS - Orthodontics & Pediatric Dentofacial Orthopedics',
                'clinic_name': 'SmileCraft Pediatric Ortho Center',
                'clinic_address': '450 Healthcare Boulevard, Suite 300, New York, NY 10016',
                'license_number': 'NY-DENT-89241',
                'bio': 'Specialist in interceptive pediatric aligner therapy and early phase adolescent orthopedics.',
                'email_notifications': True,
                'sms_alerts': True,
                'emergency_push': True
            }
        )

        # 2. Doctor 2: Dr. Rajesh Kumar (for testing doctor isolation)
        user2, _ = User.objects.get_or_create(
            username='dr.kumar@pedoalign.com',
            defaults={
                'email': 'dr.kumar@pedoalign.com',
                'first_name': 'Rajesh',
                'last_name': 'Kumar'
            }
        )
        user2.set_password('password123')
        user2.save()

        doc2, _ = DoctorProfile.objects.get_or_create(
            user=user2,
            defaults={
                'full_name': 'Rajesh Kumar',
                'phone_number': '+1 (555) 987-6543',
                'dental_qualification': 'BDS, MDS - Pediatric Dentistry & Orthodontics',
                'clinic_name': 'PedoCare Dental & Aligners Clinic',
                'clinic_address': '88 Health Plaza, Suite 102, Chicago, IL 60601',
                'license_number': 'IL-ORTO-55219',
                'bio': 'Focused on clear aligner treatment for children and young teens with arch development needs.',
            }
        )

        # ========================================================
        # PATIENTS FOR DR. ARTHUR SMITH
        # ========================================================

        # Patient 1: Leo Miller (Active, Week 8, Tray #8)
        p1, _ = Patient.objects.get_or_create(
            doctor=doc1,
            patient_id='PA-PT-2026-0001',
            defaults={
                'first_name': 'Leo',
                'last_name': 'Miller',
                'email': 'parent.miller@example.com',
                'phone': '+1 (555) 123-4567',
                'age': 11,
                'gender': 'Male',
                'date_of_birth': datetime.date(2015, 4, 15),
                'parent_guardian_name': 'David Miller (Father)',
                'parent_guardian_phone': '+1 (555) 123-4567',
                'treatment_status': 'ACTIVE',
                'treatment_start_date': timezone.localdate() - datetime.timedelta(days=60),
                'treatment_duration_months': 12,
                'notes': 'Moderate crowding with Class II Division 1 malocclusion. Responsive and motivated patient.'
            }
        )

        PatientJoiningCode.objects.get_or_create(
            patient=p1,
            defaults={
                'doctor': doc1,
                'code': 'PA-LEO888',
                'status': 'APPROVED',
                'expires_at': timezone.now() + datetime.timedelta(days=30),
                'claimed_at': timezone.now() - datetime.timedelta(days=60),
                'approved_at': timezone.now() - datetime.timedelta(days=59),
            }
        )

        ClinicalRecord.objects.get_or_create(
            patient=p1,
            defaults={
                'teeth_present': 'Mixed Dentition (Permanent First Molars & Incisors)',
                'overbite': 'Increased (>3mm)',
                'deep_bite': 'Moderate (50-75% overlap)',
                'molar_relationship': 'Class II Division 1',
                'canine_relationship': 'Class II',
                'crossbite': 'None',
                'molar_occlusion': 'Distal Step Molar Relation',
                'oral_habits': 'Thumb Sucking',
                'medical_history': 'Seasonal allergic rhinitis; no drug allergies.',
                'dental_history': 'No prior orthodontic therapy. Routine fluoride applications.',
                'skeletal_notes': 'Convex skeletal profile, retrognathic mandible with mild lip incompetence.',
                'doctor_clinical_notes': 'Interceptive aligner therapy initiated to expand maxillary arch and reduce excessive overjet.'
            }
        )

        TreatmentPlan.objects.get_or_create(
            patient=p1,
            defaults={
                'estimated_duration_months': 12,
                'total_aligners': 24,
                'current_aligner': 8,
                'aligner_frequency_days': 10,
                'start_date': timezone.localdate() - datetime.timedelta(days=60),
                'expected_completion_date': timezone.localdate() + datetime.timedelta(days=180),
                'status': 'Active / In Progress',
                'compliance_score': 94,
                'daily_wear_hours': 21.5,
                'next_review_date': timezone.localdate() + datetime.timedelta(days=12),
                'treatment_instructions': 'Wear aligners 20-22 hrs/day. Switch to Aligner #9 on scheduled date. Use chewies 5 mins daily.'
            }
        )

        # Photo monitoring records for Leo Miller
        PhotoMonitoring.objects.get_or_create(
            patient=p1,
            week_number=1,
            defaults={
                'aligner_stage': 1,
                'upload_date': timezone.localdate() - datetime.timedelta(days=55),
                'front_bite_photo': 'monitoring_photos/sample_baseline_front.jpg',
                'upper_arch_photo': 'monitoring_photos/sample_upper.jpg',
                'lower_arch_photo': 'monitoring_photos/sample_lower.jpg',
                'right_occlusion_photo': 'monitoring_photos/sample_right.jpg',
                'left_occlusion_photo': 'monitoring_photos/sample_left.jpg',
                'patient_notes': 'Baseline starter photos before beginning Tray 1.',
                'tracking_status': 'TRACKING_WELL',
                'doctor_feedback': 'Baseline recorded. Aligner 1 seated with full engagement.',
                'doctor_rating': 5,
                'is_before_sample': True,
                'reviewed_at': timezone.now() - datetime.timedelta(days=54)
            }
        )

        PhotoMonitoring.objects.get_or_create(
            patient=p1,
            week_number=4,
            defaults={
                'aligner_stage': 4,
                'upload_date': timezone.localdate() - datetime.timedelta(days=25),
                'front_bite_photo': 'monitoring_photos/sample_week4_front.jpg',
                'upper_arch_photo': 'monitoring_photos/sample_upper.jpg',
                'lower_arch_photo': 'monitoring_photos/sample_lower.jpg',
                'patient_notes': 'Tray 4 feels comfortable now, changed yesterday.',
                'tracking_status': 'TRACKING_WELL',
                'doctor_feedback': 'Transverse expansion progressing on track. Keep up the good wear time.',
                'doctor_rating': 5,
                'reviewed_at': timezone.now() - datetime.timedelta(days=24)
            }
        )

        PhotoMonitoring.objects.get_or_create(
            patient=p1,
            week_number=8,
            defaults={
                'aligner_stage': 8,
                'upload_date': timezone.localdate() - datetime.timedelta(days=2),
                'front_bite_photo': 'monitoring_photos/sample_week8_front.jpg',
                'upper_arch_photo': 'monitoring_photos/sample_upper.jpg',
                'lower_arch_photo': 'monitoring_photos/sample_lower.jpg',
                'patient_notes': 'Current tray fits snugly. No tooth sensitivity.',
                'tracking_status': 'TRACKING_WELL',
                'doctor_feedback': 'Excellent incisor uncrowding observed. Ready to progress to Tray 9 on Thursday.',
                'doctor_rating': 5,
                'is_after_sample': True,
                'reviewed_at': timezone.now() - datetime.timedelta(days=1)
            }
        )

        # Patient 2: Mia Thompson (Active, Anterior Crossbite case)
        p2, _ = Patient.objects.get_or_create(
            doctor=doc1,
            patient_id='PA-PT-2026-0002',
            defaults={
                'first_name': 'Mia',
                'last_name': 'Thompson',
                'email': 'thompson.family@example.com',
                'phone': '+1 (555) 345-6789',
                'age': 9,
                'gender': 'Female',
                'date_of_birth': datetime.date(2017, 8, 22),
                'parent_guardian_name': 'Rachel Thompson (Mother)',
                'treatment_status': 'ACTIVE',
                'treatment_start_date': timezone.localdate() - datetime.timedelta(days=35),
                'treatment_duration_months': 9,
                'notes': 'Anterior crossbite on teeth 11 and 21. Early intervention recommended.'
            }
        )

        PatientJoiningCode.objects.get_or_create(
            patient=p2,
            defaults={
                'doctor': doc1,
                'code': 'PA-MIA742',
                'status': 'APPROVED',
                'expires_at': timezone.now() + datetime.timedelta(days=30),
                'claimed_at': timezone.now() - datetime.timedelta(days=35),
                'approved_at': timezone.now() - datetime.timedelta(days=34),
            }
        )

        ClinicalRecord.objects.get_or_create(
            patient=p2,
            defaults={
                'teeth_present': 'Early Mixed Dentition',
                'overbite': 'Negative / Anterior Open Bite',
                'deep_bite': 'None',
                'molar_relationship': 'Class I',
                'canine_relationship': 'Class III',
                'crossbite': 'Anterior Crossbite',
                'oral_habits': 'Tongue Thrusting',
                'doctor_clinical_notes': 'Proclining upper central incisors to jump crossbite with aligner mechanics.'
            }
        )

        TreatmentPlan.objects.get_or_create(
            patient=p2,
            defaults={
                'estimated_duration_months': 9,
                'total_aligners': 18,
                'current_aligner': 5,
                'aligner_frequency_days': 10,
                'status': 'Active / In Progress',
                'compliance_score': 91,
                'daily_wear_hours': 21.0,
                'next_review_date': timezone.localdate() + datetime.timedelta(days=8),
                'treatment_instructions': 'Ensure aligners are seated completely over upper front attachments.'
            }
        )

        # Patient 3: Ethan Davis (Awaiting Approval - Joining code claimed)
        p3, _ = Patient.objects.get_or_create(
            doctor=doc1,
            patient_id='PA-PT-2026-0003',
            defaults={
                'first_name': 'Ethan',
                'last_name': 'Davis',
                'email': 'davis.parent@example.com',
                'phone': '+1 (555) 456-7890',
                'age': 13,
                'gender': 'Male',
                'treatment_status': 'PENDING_CONNECTION',
                'treatment_duration_months': 14,
                'parent_guardian_name': 'Mark Davis (Father)',
                'notes': 'Teen aligner candidate. Scanned in clinic, awaiting code activation.'
            }
        )

        PatientJoiningCode.objects.get_or_create(
            patient=p3,
            defaults={
                'doctor': doc1,
                'code': 'PA-ETH913',
                'status': 'PENDING_APPROVAL',
                'expires_at': timezone.now() + datetime.timedelta(days=12),
                'claimed_at': timezone.now() - datetime.timedelta(hours=4),
                'patient_request_notes': 'Hello Dr. Smith! Ethan received his starter aligner box and we would love to connect.'
            }
        )

        # Patient 4: Sophia Garcia (Active, Has Emergency Alert)
        p4, _ = Patient.objects.get_or_create(
            doctor=doc1,
            patient_id='PA-PT-2026-0004',
            defaults={
                'first_name': 'Sophia',
                'last_name': 'Garcia',
                'email': 'garcia.home@example.com',
                'phone': '+1 (555) 567-8901',
                'age': 10,
                'gender': 'Female',
                'parent_guardian_name': 'Elena Garcia (Mother)',
                'treatment_status': 'ACTIVE',
                'treatment_start_date': timezone.localdate() - datetime.timedelta(days=45),
                'treatment_duration_months': 10
            }
        )

        PatientJoiningCode.objects.get_or_create(
            patient=p4,
            defaults={
                'doctor': doc1,
                'code': 'PA-SOP512',
                'status': 'APPROVED',
                'expires_at': timezone.now() + datetime.timedelta(days=30),
                'approved_at': timezone.now() - datetime.timedelta(days=44)
            }
        )

        TreatmentPlan.objects.get_or_create(
            patient=p4,
            defaults={
                'estimated_duration_months': 10,
                'total_aligners': 20,
                'current_aligner': 6,
                'aligner_frequency_days': 10,
                'compliance_score': 82,
                'daily_wear_hours': 19.5,
                'status': 'Active / In Progress'
            }
        )

        # Emergency Alert for Sophia
        EmergencyAlert.objects.get_or_create(
            patient=p4,
            issue_type='LOOSE_ALIGNER',
            defaults={
                'severity': 'HIGH',
                'description': 'Lower aligner #6 feels loose on the right molar side and clicks when speaking. Sophia feels slight gum irritation.',
                'status': 'PENDING'
            }
        )

        # Patient 5: Noah Wilson (Completed Treatment)
        p5, _ = Patient.objects.get_or_create(
            doctor=doc1,
            patient_id='PA-PT-2026-0005',
            defaults={
                'first_name': 'Noah',
                'last_name': 'Wilson',
                'phone': '+1 (555) 678-9012',
                'age': 14,
                'gender': 'Male',
                'treatment_status': 'COMPLETED',
                'treatment_start_date': timezone.localdate() - datetime.timedelta(days=300),
                'treatment_duration_months': 10,
                'notes': 'Full aligner course successfully completed. Currently on nocturnal clear retainers.'
            }
        )

        TreatmentPlan.objects.get_or_create(
            patient=p5,
            defaults={
                'estimated_duration_months': 10,
                'total_aligners': 20,
                'current_aligner': 20,
                'status': 'Completed',
                'compliance_score': 98,
                'daily_wear_hours': 12.0
            }
        )

        # Appointments for Dr. Smith
        today = timezone.localdate()
        Appointment.objects.get_or_create(
            doctor=doc1,
            patient=p1,
            scheduled_date=today + datetime.timedelta(days=3),
            defaults={
                'scheduled_time': datetime.time(14, 30),
                'appointment_type': 'ROUTINE_CHECKUP',
                'duration_minutes': 30,
                'status': 'UPCOMING',
                'notes': 'Mid-treatment progress check and IPR evaluation.'
            }
        )

        Appointment.objects.get_or_create(
            doctor=doc1,
            patient=p2,
            scheduled_date=today + datetime.timedelta(days=7),
            defaults={
                'scheduled_time': datetime.time(10, 0),
                'appointment_type': 'ALIGNER_COLLECTION',
                'duration_minutes': 25,
                'status': 'UPCOMING',
                'notes': 'Deliver aligner sets #6 through #10.'
            }
        )

        Appointment.objects.get_or_create(
            doctor=doc1,
            patient=p4,
            scheduled_date=today + datetime.timedelta(days=1),
            defaults={
                'scheduled_time': datetime.time(16, 0),
                'appointment_type': 'EMERGENCY',
                'duration_minutes': 20,
                'status': 'UPCOMING',
                'notes': 'Emergency evaluation for loose lower aligner.'
            }
        )

        # Notifications for Dr. Smith
        Notification.objects.get_or_create(
            doctor=doc1,
            patient=p3,
            notification_type='PATIENT_REQUEST',
            title='New Connection Request: Ethan Davis',
            defaults={
                'message': 'Ethan Davis entered Joining Code PA-ETH913. Awaiting doctor approval.',
                'link_url': '/requests/',
                'is_read': False
            }
        )

        Notification.objects.get_or_create(
            doctor=doc1,
            patient=p4,
            notification_type='EMERGENCY',
            title='Emergency Alert: Sophia Garcia',
            defaults={
                'message': 'Patient reported loose aligner and molar discomfort. High priority.',
                'link_url': '/emergencies/',
                'is_read': False
            }
        )

        Notification.objects.get_or_create(
            doctor=doc1,
            patient=p1,
            notification_type='PHOTO_UPLOAD',
            title='Week 8 Photos: Leo Miller',
            defaults={
                'message': 'Leo submitted Week 8 aligner tracking photos. Tracking well.',
                'link_url': f'/patients/{p1.id}/?tab=photos',
                'is_read': True
            }
        )

        # Activity logs for Dr. Smith
        PatientActivityLog.objects.get_or_create(
            patient=p1,
            doctor=doc1,
            activity_type='Aligner Advanced',
            defaults={
                'description': 'Advanced patient Leo Miller to Aligner #8. Compliance score 94%.'
            }
        )

        # ========================================================
        # PATIENTS FOR DR. RAJESH KUMAR (ISOLATION TEST)
        # ========================================================
        p_kumar1, _ = Patient.objects.get_or_create(
            doctor=doc2,
            patient_id='PA-PT-2026-9001',
            defaults={
                'first_name': 'Aarav',
                'last_name': 'Patel',
                'phone': '+1 (555) 777-8888',
                'age': 12,
                'gender': 'Male',
                'treatment_status': 'ACTIVE',
                'treatment_duration_months': 12,
                'notes': 'Under Dr. Kumar care only. Demonstrates strict multi-tenant doctor isolation.'
            }
        )

        PatientJoiningCode.objects.get_or_create(
            patient=p_kumar1,
            defaults={
                'doctor': doc2,
                'code': 'PA-AAR202',
                'status': 'APPROVED',
                'expires_at': timezone.now() + datetime.timedelta(days=30),
            }
        )

        TreatmentPlan.objects.get_or_create(
            patient=p_kumar1,
            defaults={
                'estimated_duration_months': 12,
                'total_aligners': 24,
                'current_aligner': 3,
                'compliance_score': 88,
                'status': 'Active / In Progress'
            }
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded PEDO ALIGN database!"))
        self.stdout.write("-------------------------------------------------------------")
        self.stdout.write("DOCTOR 1 ACCOUNT:")
        self.stdout.write("  Email:    dr.smith@pedoalign.com")
        self.stdout.write("  Password: password123")
        self.stdout.write("  Clinic:   SmileCraft Pediatric Ortho Center (Dr. Arthur Smith)")
        self.stdout.write("  Patients: Leo Miller, Mia Thompson, Ethan Davis, Sophia Garcia, Noah Wilson")
        self.stdout.write("-------------------------------------------------------------")
        self.stdout.write("DOCTOR 2 ACCOUNT (Isolation Testing):")
        self.stdout.write("  Email:    dr.kumar@pedoalign.com")
        self.stdout.write("  Password: password123")
        self.stdout.write("  Clinic:   PedoCare Dental & Aligners Clinic (Dr. Rajesh Kumar)")
        self.stdout.write("  Patients: Aarav Patel (Doctor Kumar only sees his patients)")
        self.stdout.write("-------------------------------------------------------------")


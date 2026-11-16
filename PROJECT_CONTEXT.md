# PedoAlign — Complete Project Context & Architecture Documentation

**System Name**: PedoAlign (Pediatric Clear Aligner & Expansion Therapy Management Platform)  
**Version**: 2.0 (Clinical Enterprise Edition)  
**Repository**: [devanga2025-cmd/pedo_align](https://github.com/devanga2025-cmd/pedo_align)  
**Target Environment**: Web Application (Desktop & Mobile Responsive) + Android App (PWA / Webview APK)  
**Date Generated**: November 2026  

---

## 1. Executive Summary & Purpose

**PedoAlign** is a specialized, dual-portal pediatric dental and orthodontic care management platform. Designed specifically for pediatric dentists, orthodontists, and young patients (along with their parents/guardians), PedoAlign bridges the gap between in-clinic clinical visits and at-home tele-orthodontic monitoring.

### Core Problems Solved:
1. **Pediatric Compliance & Tracking**: Children undergoing clear aligner therapy or maxillary expansion (RPE, Turn Quest appliances) require frequent oversight. PedoAlign provides structured weekly photo uploads and step-by-step appliance turning schedules.
2. **Standardized Clinical Intake**: Guided multi-step documentation ensuring doctors never miss initial clinical records (3 compulsory pre-operative photos, dental radiographs like OPG and Lateral Cephalograms, and scheduled follow-up visits).
3. **Tele-Orthodontics & Feedback Loop**: Parents upload progress photos from home; doctors review, rate tracking accuracy, and approve tray advancements or request clinic visits if an appliance is ill-fitting.
4. **Emergency Escalation**: Immediate SOS reporting for loose brackets, broken aligners, or sharp appliance edges with direct photo evidence.

---

## 2. System Architecture & Technology Stack

```
+-------------------------------------------------------------------------+
|                              CLIENT TIER                                |
|   +---------------------------------+  +----------------------------+   |
|   | Doctor Web Portal (Responsive)  |  | Patient Web Portal / PWA   |   |
|   | Glassmorphism / Tailwind / CSS  |  | Android APK (PedoAlign.apk)|   |
|   +---------------------------------+  +----------------------------+   |
+------------------------------------+------------------------------------+
                                     |  HTTP / HTTPS (RESTful URLs & Forms)
+------------------------------------v------------------------------------+
|                           APPLICATION TIER                              |
|                          Django 5.x (Python 3.13)                       |
|   +---------------------------------+  +----------------------------+   |
|   |         doctor App              |  |        patient App         |   |
|   | Clinical Records, Care Path,    |  | Portal, Treatment Journey, |   |
|   | Photos, Appointments, Reports   |  | Uploads, Emergency SOS     |   |
|   +---------------------------------+  +----------------------------+   |
|   +-----------------------------------------------------------------+   |
|   |                  Shared Middleware & Context                    |   |
|   |      Role-based Access, Unread Notifications, PWA Services      |   |
|   +-----------------------------------------------------------------+   |
+------------------------------------+------------------------------------+
                                     |  Django ORM
+------------------------------------v------------------------------------+
|                              DATA TIER                                  |
|   +---------------------------------+  +----------------------------+   |
|   | SQLite3 Database (db.sqlite3)   |  | Media Storage (/media/)    |   |
|   | (Production-ready for Postgres) |  | Photos, X-Rays, Videos     |   |
|   +---------------------------------+  +----------------------------+   |
+-------------------------------------------------------------------------+
```

### Technology Breakdown:
* **Backend Framework**: Django 5.x (Python 3.13) using Model-View-Template (MVT) pattern.
* **Database**: SQLite3 (`db.sqlite3`) for local development, schema-ready for PostgreSQL in production.
* **Frontend**: HTML5, Vanilla JavaScript, CSS3 with modern CSS custom properties, Glassmorphism visual design, and Tailwind CSS utility classes.
* **PWA & Android Support**:
  * Progressive Web App manifest (`manifest.json`) and service worker (`sw.js`).
  * Android standalone APK packaged and distributed directly via the web portal (`/download/app/`).
  * Android digital asset links (`.well-known/assetlinks.json`).
* **Media Management**: Django FileField/ImageField with upload paths organized by clinical domain (`preoperative_photos/`, `radiographs/`, `monitoring_photos/`, `treatment_media/`, `patient_profiles/`, `doctor_avatars/`).

---

## 3. Core Modules & Clinical Workflows

### 3.1 Doctor Portal (`doctor` app)

The Doctor Portal serves as the clinical command center for pediatric orthodontists.

1. **Authentication & Profile Management**:
   - Multi-field doctor registration including Full Name, Dental Qualification, Specialization, KSDC (Karnataka State Dental Council) Registration Number, Clinic Name, Clinic Address, License Number, and Profile Avatar.
   - Configurable alert preferences (Email notifications, SMS alerts, Emergency push alerts).

2. **Doctor Dashboard**:
   - Key Clinical Metrics: Total Active Patients, Pending Connection Requests, Pending Photo Reviews, Today's & Upcoming Appointments, Active Emergencies.
   - Quick Access: One-click patient creation, appointment scheduling, and Android app download link.

3. **Guided Clinical Intake Workflow**:
   A 4-step structured protocol for every onboarded patient:
   - **Step 1: Pre-operative Photos**: Exactly 3 compulsory clinical baseline photographs (Frontal View in Centric Occlusion, Upper Maxillary Arch View, Lower Mandibular Arch View) with optional dynamic slots for additional angles (right/left lateral, smile line).
   - **Step 2: Radiographs**: Orthopantomogram (OPG) and Lateral Cephalometric radiograph uploads with date and description.
   - **Step 3: Schedule Next Hospital Visit**: Quick-preset appointment scheduling (+20 Days recommended follow-up, +15 Days, +30 Days) with time, duration, and patient instructions.
   - **Step 4: Operation / Visual Protocol & Turn Quest**: Appliance selection (RPE, Quad Helix, Clear Aligners, Twin Block), demonstration photos/videos, activation instructions, and turning frequency.

4. **Patient Management & Care Path**:
   - Filterable patient list (All, Pending Connection, Active Treatment, On Hold, Completed, Archived).
   - Card view and Table view toggle.
   - CSV export for clinic auditing.
   - **Patient Clinical Journey / Care Path**: Interactive timeline tracking current stage vs. total stages, aligner change countdown, wear compliance score (0–100%), daily wear hours, and arch progress history.
   - Prominent action controls: **Stage +1** (one-click advance), **Edit Plan**, and **Turn Quest / Visual Protocol**.

5. **Tele-Monitoring & Photo Review**:
   - Side-by-side comparative viewer (Before baseline vs. Current week monitoring photos).
   - Doctor rating (1 to 5 stars) and tracking status assessment (`On Track`, `Needs Attention`, `Critical - Visit Required`).
   - Direct feedback messages sent to the patient portal.

6. **Digital Prescription System**:
   - Structured prescription generator: Diagnosis, structured medication array (Drug Name, Dosage, Frequency, Duration, Special Instructions), next follow-up date.
   - Professional printable prescription format with clinic letterhead.

7. **Patient Pairing & Security**:
   - Automatic 6-digit alphanumeric Joining Code generation for newly added patients.
   - Doctor approves or rejects patient connection requests before medical data is accessible.

---

### 3.2 Patient & Guardian Portal (`patient` app)

Designed with a child-friendly, mobile-first interface optimized for parents and young aligner wearers.

1. **Patient Registration & Doctor Connection**:
   - Patients/guardians sign up with their details and child's date of birth.
   - Enter the 6-digit Doctor Joining Code to request linkage to their clinical record.
   - Status updates automatically via AJAX polling or notification when approved.

2. **Patient Dashboard**:
   - Real-time aligner counter (Current Stage / Total Stages).
   - Next tray change countdown timer.
   - Aligner wear tracker (hours worn today).
   - Next appointment reminder card.
   - Download Android App button.

3. **"My Treatment" / Journey Tab**:
   - Direct access to doctor's instructions, appliance turning protocols, and visual demonstration videos/photos.
   - Active prescriptions viewer with print and download capability.

4. **Weekly Photo Monitoring Submission**:
   - Intuitive upload interface for weekly progress photos: Front bite in occlusion, upper occlusal, lower occlusal, right/left lateral bite.
   - View past doctor reviews, star ratings, and clinical remarks.

5. **Emergency SOS System**:
   - Fast reporting form for orthodontic emergencies: Broken aligner, lost tray, poking wire, sharp appliance edge, severe pain, or gum swelling.
   - Photo attachment and immediate high-priority alert dispatch to the doctor's dashboard.

6. **Notification System**:
   - Unified notification bell in the top navigation bar.
   - Dynamic badge counter that increments strictly when new doctor messages, review feedback, or stage updates arrive.
   - One-click "Mark all as read" capability.

---

## 4. Database Schema & Data Models

PedoAlign contains **22 Django Models** providing comprehensive clinical coverage:

### 4.1 `doctor` App Models

| Model Name | Description & Key Fields | Relationships |
|:---|:---|:---|
| **`DoctorProfile`** | Doctor professional credentials, KSDC reg no, clinic name, clinic address, avatar, alert settings (`email_notifications`, `sms_alerts`, `emergency_push`). | `OneToOneField(User)` |
| **`Patient`** | Master clinical patient entity: ID (`patient_id`), demographics, parent/guardian info, appointment/monitoring frequencies, `treatment_status`, `is_archived`, `is_deactivated`. | `ForeignKey(DoctorProfile)` |
| **`PatientJoiningCode`** | 6-digit connection security code (`code`, `status`: PENDING, CLAIMED, APPROVED, REJECTED, EXPIRED). | `ForeignKey(Patient)`, `ForeignKey(DoctorProfile)` |
| **`ClinicalRecord`** | Detailed orthodontic examination: overbite, deep bite, crossbite, molar/canine relationships, oral habits, skeletal classification. | `OneToOneField(Patient)` |
| **`TreatmentPlan`** | Orthodontic aligner plan: `total_aligners`, `current_aligner`, `aligner_frequency_days`, `compliance_score`, `daily_wear_hours`, upper/lower arch status & photos. | `OneToOneField(Patient)` |
| **`ArchProgressHistory`** | Historical snapshots of maxillary or mandibular arch progress at distinct stages. | `ForeignKey(TreatmentPlan)` |
| **`TrayHistory`** | Historical record of each individual aligner tray (start date, completion date, notes). | `ForeignKey(TreatmentPlan)` |
| **`PhotoMonitoring`** | Weekly tele-monitoring photo submissions (5 angles), doctor tracking status (`ON_TRACK`, `NEEDS_ATTENTION`), doctor rating (1–5), feedback. | `ForeignKey(Patient)` |
| **`EmergencyAlert`** | Urgent orthodontic alerts: `issue_type`, `severity` (LOW, MEDIUM, HIGH, CRITICAL), photo, doctor response, resolution status. | `ForeignKey(Patient)` |
| **`Appointment`** | Clinical appointments: `appointment_type`, `scheduled_date`, `scheduled_time`, `duration_minutes`, status (`SCHEDULED`, `CONFIRMED`, `COMPLETED`, `CANCELLED`), reschedule fields. | `ForeignKey(DoctorProfile)`, `ForeignKey(Patient)` |
| **`Notification`** | In-app alerts for doctors (new patient request, photo uploaded, emergency SOS). | `ForeignKey(DoctorProfile)`, `ForeignKey(Patient)` |
| **`PatientActivityLog`** | Comprehensive audit trail logging every clinical action, stage advance, photo upload, and appointment change. | `ForeignKey(Patient)`, `ForeignKey(DoctorProfile)` |
| **`PreoperativePhoto`** | Compulsory initial baseline photographs and dynamic clinical angles. | `ForeignKey(Patient)` |
| **`RadiographRecord`** | Radiographic imaging records: `radiograph_type` (`OPG`, `LATERAL_CEPH`, `CBCT`, `IOPA`), examination date, version. | `ForeignKey(Patient)` |
| **`TreatmentOperationRecord`** | In-clinic procedural logs: condition findings, operation performed, treatment description, observations. | `ForeignKey(Patient)`, `ForeignKey(DoctorProfile)` |
| **`Prescription`** | Pediatric dental prescription: diagnosis, JSON structured medication data (`medicines_data`), special instructions, follow-up date. | `ForeignKey(Patient)`, `ForeignKey(DoctorProfile)` |
| **`TreatmentTurn`** | Expansion appliance turning records (RPE turn tracking, dates, turning instructions). | `ForeignKey(Patient)` |
| **`DoctorTreatmentMedia`** | Appliance demonstration videos, photos, and activation instructions for the patient portal ("Turn Quest / Visual Protocol"). | `ForeignKey(Patient)`, `ForeignKey(DoctorProfile)` |
| **`MonthlyTreatmentNote`** | Monthly clinical progress summaries recorded by the doctor. | `ForeignKey(Patient)` |

### 4.2 `patient` App Models

| Model Name | Description & Key Fields | Relationships |
|:---|:---|:---|
| **`PatientProfile`** | Patient user account profile: parent/guardian details, avatar, connection status (`UNCONNECTED`, `PENDING`, `CONNECTED`), pending code reference. | `OneToOneField(User)`, `ForeignKey(Patient, null=True)` |
| **`PatientNotification`** | Patient notifications: alerts received when doctor updates stage, reviews photos, or responds to an emergency. | `ForeignKey(PatientProfile)` |

---

## 5. Complete URL Routing & Endpoint Map

### Global & PWA Endpoints
* `/` -> `doctor:landing` (Public Landing Page)
* `/login/` -> `doctor:login` (Doctor Login)
* `/register/` -> `doctor:register` (Doctor Registration)
* `/dashboard/` -> `doctor:dashboard` (Main Doctor Dashboard)
* `/join/` -> `doctor:patient_join_portal` (Quick Patient Joining Page)
* `/download/app/` -> `download_app_apk` (Download Android APK)
* `/sw.js` -> Service Worker script
* `/manifest.json` -> PWA Web Manifest
* `/.well-known/assetlinks.json` -> Android App Verification Links

### Doctor Portal Endpoints (`doctor/urls.py`)
* **Patient Management**:
  * `/patients/` -> `patient_list`
  * `/patients/create/` -> `patient_create`
  * `/patients/<id>/` -> `patient_detail`
  * `/patients/<id>/edit/` -> `patient_edit`
  * `/patients/<id>/archive/` -> `archive_patient`
  * `/patients/<id>/restore/` -> `restore_patient`
  * `/patients/archived/` -> `archived_patients`
* **Clinical Intake & Care Path**:
  * `/patients/<id>/preop-photos/upload/` -> `preop_photo_upload`
  * `/patients/<id>/radiographs/upload/` -> `radiograph_upload`
  * `/patients/<id>/schedule-20day/` -> `schedule_20day_followup`
  * `/treatment-plans/<id>/journey/` -> `patient_clinical_journey`
  * `/patients/<id>/advance-aligner/` -> `advance_aligner`
  * `/patients/<id>/treatment-media/upload/` -> `treatment_media_upload`
  * `/patients/<id>/carepath/update/` -> `patient_carepath_update`
* **Tele-Monitoring**:
  * `/photos/` -> `photo_monitoring`
  * `/photos/<id>/review/` -> `photo_review`
  * `/patients/<id>/photos/compare/` -> `photo_compare`
* **Clinical Records, Operations & Prescriptions**:
  * `/patients/<id>/clinical/edit/` -> `clinical_record_edit`
  * `/patients/<id>/operations/create/` -> `operation_record_create`
  * `/patients/<id>/prescriptions/create/` -> `prescription_create`
  * `/patients/<id>/prescriptions/<presc_id>/print/` -> `prescription_print`
* **Appointments & Emergencies**:
  * `/appointments/` -> `appointments`
  * `/appointments/create/` -> `appointment_create`
  * `/appointments/<id>/status/` -> `appointment_status_update`
  * `/emergencies/` -> `emergency_alerts`
  * `/emergencies/<id>/respond/` -> `emergency_respond`
* **Notifications & Settings**:
  * `/notifications/` -> `notifications`
  * `/notifications/<id>/read/` -> `mark_notification_read`
  * `/notifications/read-all/` -> `mark_all_notifications_read`
  * `/settings/` -> `settings`
  * `/reports/export-csv/` -> `export_patients_csv`

### Patient Portal Endpoints (`patient/urls.py`)
* `/patient/` -> `patient:dashboard`
* `/patient/login/` -> `patient:login`
* `/patient/register/` -> `patient:register`
* `/patient/connect/` -> `patient:connect_doctor` (Submit 6-digit code)
* `/patient/api/connection-status/` -> `api_connection_status` (AJAX status check)
* `/patient/treatment/` -> `patient:my_treatment` (Journey, Appliance & Turn Quest)
* `/patient/photos/upload/` -> `patient:upload_photos` (Weekly photo monitoring)
* `/patient/appointments/` -> `patient:appointments`
* `/patient/appointments/request/` -> `patient:appointment_request`
* `/patient/emergency/` -> `patient:emergency` (SOS Report)
* `/patient/notifications/` -> `patient:notifications`
* `/patient/profile/` -> `patient:profile`

---

## 6. Recent Enhancements & Design Refinements

1. **Unified Navigation Bar Notifications**:
   - Removed redundant "Notifications" entries from both doctor and patient sidebars.
   - Unified notification access into the prominent top navigation bell icon with dynamic unread badge indicators.
   - Fixed patient notification counter logic so numbers increment strictly when verified clinical messages/updates arrive from the attending doctor.

2. **Care Path & Treatment Tab Consolidation**:
   - Embedded clinical intake, treatment protocols, and appliance guides ("Turn Quest / Visual Protocol") directly into the patient's profile treatment views.
   - Removed obsolete standalone next-visit sub-options that duplicated the Care Path.

3. **Streamlined UI & High-Impact Clinical Action Buttons**:
   - Replaced clunky top buttons with three modern, interactive action pills on the Care Path:
     - **`Stage +1`**: Gradient blue pill for instant aligner advancement.
     - **`Edit Plan`**: Light-bordered button for updating duration, frequency, and wear instructions.
     - **`Turn Quest / Visual Protocol`**: Pill button opening appliance guidance and demonstration video uploads.

4. **Repository & Media Optimization**:
   - Purged over 1,100 orphaned test upload files from `media/` accumulated during automated testing.
   - Cleaned untracked bytecode (`*.pyc`) and temporary scratch directories.
   - Verified 100% data integrity for all 25 active clinical files referenced in `db.sqlite3`.

---

## 7. Developer & Operational Setup Guide

### 7.1 Prerequisites
* Python 3.11+ (Tested on Python 3.13)
* Windows / Linux / macOS
* Git

### 7.2 Local Installation & Execution
```powershell
# 1. Clone repository
git clone https://github.com/devanga2025-cmd/pedo_align.git
cd pedo_align

# 2. Activate virtual environment
venv\Scripts\activate   # On Windows
# source venv/bin/activate  # On Linux/macOS

# 3. Apply database migrations
python manage.py migrate

# 4. Collect static assets
python manage.py collectstatic --noinput

# 5. Start the development server
python manage.py runserver 0.0.0.0:8000
```
Access the application at: `http://127.0.0.1:8000/`

### 7.3 Default Credentials (Seed / Test Environment)
* **Doctor Username**: `peddd`
* **Doctor Password**: `1234`
* **Admin / Superuser**: Accessible at `http://127.0.0.1:8000/admin/`

---

## 8. Directory Structure Overview

```
d:\Pedo_align\
├── config/                  # Django project settings, WSGI, root URL routing
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── doctor/                  # Doctor portal application
│   ├── models.py            # Clinical models (Patient, TreatmentPlan, Appointments, etc.)
│   ├── views.py             # Doctor workflows, intake, care path, photo reviews
│   ├── urls.py              # Doctor route declarations
│   ├── forms.py             # Intake, prescription, and treatment forms
│   ├── templates/doctor/    # Doctor dashboard, patient profiles, care path templates
│   └── static/doctor/       # Doctor portal styling, icons, and clinical CSS
├── patient/                 # Patient & parent portal application
│   ├── models.py            # PatientProfile, PatientNotification
│   ├── views.py             # Patient dashboard, photo upload, emergency SOS
│   ├── urls.py              # Patient route declarations
│   ├── forms.py             # Patient upload forms
│   └── templates/patient/   # Patient dashboard, treatment journey, photo submission
├── media/                   # User and clinical uploads (radiographs, photos, videos)
│   ├── preoperative_photos/
│   ├── radiographs/
│   ├── monitoring_photos/
│   ├── treatment_media/
│   └── patient_profiles/
├── staticfiles/             # Collected production static files
├── assent/app/              # Android APK package distribution (PedoAlign.apk)
├── manage.py                # Django CLI utility
├── db.sqlite3               # Active clinical SQLite database
└── PROJECT_CONTEXT.md       # Complete system architecture and context documentation
```

---

## 9. Future Roadmap Recommendations

1. **Automated WebPush / Firebase Cloud Messaging (FCM)**:
   - Implement push notifications for real-time alerts when a patient uploads monitoring photos or triggers an emergency SOS.
2. **AI-Assisted Tooth Alignment Verification**:
   - Incorporate computer vision models to automatically detect aligner seating and calculate marginal gap errors from monitoring photos.
3. **Cloud Object Storage (AWS S3 / GCS)**:
   - For high-volume clinical deployments, switch `DEFAULT_FILE_STORAGE` to Amazon S3 or Google Cloud Storage to offload high-resolution cephalometric and OPG X-ray files.

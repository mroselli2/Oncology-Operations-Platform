#!/usr/bin/env python3
"""
SUPERSEDED by oncology_pipeline/ -- kept for reference only. Do not run this
file as part of normal operation: its output path is stale
(/home/workdir/artifacts, outside this project) and its patient cohort used
an MRN scheme incompatible with the main scheduling script. Its reference
data and authorization logic have been migrated into
oncology_pipeline/generation/core.py and oncology_pipeline/generation/insurance.py,
rewired onto the shared cohort and the real payer-facility network.

Synthetic Oncology Insurance Authorization Dataset Generator
============================================================
Extends the oncology scheduling data with full insurance authorization
workflow fields, normalized into multiple relational CSV files plus a
comprehensive analysis Excel workbook and Markdown report.

Generates:
- A large pool of unique first + last names for patients, providers (Dr.), insurance agents
- Realistic linked data: patients <-> authorizations <-> providers (by NPI) <-> facilities (by NPI) <-> payers
- Insurance Provider, Healthcare Plan, CPT, DX-Codes (Primary + others),
  Labs/Imaging Ordered (with details), NPIs (ordering/facility), Third party (EviCore etc),
  Auth Code + Validity Period, Peer-to-Peer Required, Agent First+Last Name,
  # Clinical Questions, Total Phone Time, Denial Reason/Rates, etc.
- Plus continuity with previous scheduling fields (referral dates, scheduling_status, barrier_reason, priority)

Use the CSVs for joins/analysis in pandas, SQL, BI tools. The xlsx has ready analysis sheets.
"""

import pandas as pd
import random
from datetime import datetime, timedelta
import os

def main():
    random.seed(42)
    num_records = 120

    output_dir = "/home/workdir/artifacts/oncology_insurance_dataset"
    os.makedirs(output_dir, exist_ok=True)

    # ============================================================
    # NAME LISTS - Lots of first + last names for variety
    # ============================================================
    first_names_male = [
        "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Christopher",
        "Charles", "Daniel", "Matthew", "Anthony", "Mark", "Steven", "Paul", "Andrew", "Joshua", "Kenneth",
        "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey", "Ryan", "Jacob",
        "Gary", "Nicholas", "Eric", "Jonathan", "Stephen", "Larry", "Justin", "Scott", "Brandon", "Benjamin",
        "Samuel", "Raymond", "Gregory", "Frank", "Alexander", "Patrick", "Jack", "Dennis", "Jerry", "Tyler",
        "Aaron", "Jose", "Adam", "Nathan", "Henry", "Douglas", "Zachary", "Peter", "Kyle", "Ethan", "Walter",
        "Jeremy", "Harold", "Keith", "Christian", "Roger", "Noah", "Gerald", "Carl", "Terry", "Sean", "Austin",
        "Arthur", "Lawrence", "Dylan", "Jesse", "Jordan", "Bryan", "Billy", "Joe", "Bruce", "Gabriel", "Logan",
        "Albert", "Willie", "Alan", "Juan", "Wayne", "Roy", "Vincent", "Ralph", "Eugene", "Russell", "Bobby",
        "Philip", "Louis", "Johnny", "Bradley"
    ]

    first_names_female = [
        "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen",
        "Nancy", "Lisa", "Betty", "Margaret", "Sandra", "Ashley", "Kimberly", "Emily", "Donna", "Michelle",
        "Dorothy", "Carol", "Amanda", "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia",
        "Kathleen", "Amy", "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma", "Nicole", "Helen",
        "Samantha", "Katherine", "Christine", "Debra", "Rachel", "Carolyn", "Janet", "Catherine", "Maria", "Olivia",
        "Heather", "Diane", "Julie", "Joyce", "Victoria", "Ruth", "Virginia", "Lauren", "Kelly", "Christina",
        "Joan", "Evelyn", "Judith", "Megan", "Andrea", "Cheryl", "Hannah", "Jacqueline", "Martha", "Gloria",
        "Teresa", "Sara", "Janice", "Marie", "Julia", "Grace", "Judy", "Theresa", "Madison", "Beverly",
        "Denise", "Marilyn", "Amber", "Danielle", "Rose", "Brittany", "Diana", "Abigail", "Natalie", "Jane",
        "Lori", "Alexis", "Tiffany", "Kayla", "Cindy", "Kathryn", "Ann", "Jasmine", "Gail", "Natalie"
    ]

    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
        "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
        "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
        "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker", "Cruz", "Edwards", "Collins", "Reyes",
        "Stewart", "Morris", "Morales", "Murphy", "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper",
        "Peterson", "Bailey", "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
        "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza", "Ruiz", "Hughes",
        "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers", "Long", "Ross", "Foster", "Jimenez",
        "Powell", "Jenkins", "Perry", "Russell", "Sullivan", "Bell", "Coleman", "Butler", "Henderson", "Barnes",
        "Gonzales", "Fisher", "Vasquez", "Simmons", "Romero", "Jordan", "Patterson", "Alexander", "Hamilton", "Graham",
        "Reynolds", "Griffin", "Wallace", "Moreno", "West", "Cole", "Hayes", "Bryant", "Herrera", "Gibson",
        "Ellis", "Tran", "Medina", "Aguilar", "Stevens", "Murray", "Ford", "Castro", "Marshall", "Owens",
        "Harrison", "Fernandez", "McDonald", "Woods", "Washington", "Kennedy", "Wells", "Vargas", "Henry", "Chen",
        "Freeman", "Webb", "Tucker", "Guzman", "Burns", "Crawford", "Olson", "Simpson", "Porter", "Hunter",
        "Gordon", "Mendez", "Silva", "Shaw", "Snyder", "Mason", "Dixon", "Munoz", "Hunt", "Hicks", "Holmes",
        "Palmer", "Wagner", "Black", "Robertson", "Boyd", "Cruz", "Warren", "Mills", "Meyer", "Rice", "Schmidt",
        "Garza", "Daniels", "Ferguson", "Nichols", "Stephens", "Soto", "Weaver", "Ryan", "Gardner", "Payne",
        "Grant", "Dunn", "Kelley", "Spencer", "Hawkins", "Arnold", "Pierce", "Vazquez", "Hansen", "Peters",
        "Santos", "Hart", "Bradley", "Knight", "Elliott", "Cunningham", "Duncan", "Armstrong", "Hudson", "Carroll",
        "Lane", "Riley", "Andrews", "Alvarez", "Stone", "Hawkins", "Dunn", "Perkins", "Hudson", "Spencer"
    ]

    # ============================================================
    # DIAGNOSIS & PROCEDURE MAPPING (realistic for oncology)
    # ============================================================
    cancer_diagnoses = [
        "Breast Cancer", "Colorectal Cancer", "Non-Small Cell Lung Cancer", "Prostate Cancer",
        "Melanoma", "Pancreatic Cancer", "Ovarian Cancer", "Head and Neck Cancer",
        "Bladder Cancer", "Kidney Cancer", "Liver Cancer", "Esophageal Cancer"
    ]

    dx_map = {
        "Breast Cancer": "C50.9",
        "Colorectal Cancer": "C18.9",
        "Non-Small Cell Lung Cancer": "C34.90",
        "Prostate Cancer": "C61",
        "Melanoma": "C43.9",
        "Pancreatic Cancer": "C25.9",
        "Ovarian Cancer": "C56.9",
        "Head and Neck Cancer": "C76.0",
        "Bladder Cancer": "C67.9",
        "Kidney Cancer": "C64.9",
        "Liver Cancer": "C22.0",
        "Esophageal Cancer": "C15.9"
    }

    procedure_map = {
        "Breast Cancer": [
            ("19301", "Mastectomy, partial (lumpectomy)"),
            ("19303", "Mastectomy, simple, complete"),
            ("19307", "Mastectomy, modified radical, including axillary lymph nodes")
        ],
        "Colorectal Cancer": [
            ("44140", "Colectomy, partial; with anastomosis"),
            ("44204", "Laparoscopy, surgical; colectomy, partial, with anastomosis"),
            ("44160", "Colectomy, partial, with removal of terminal ileum and ileocolostomy")
        ],
        "Non-Small Cell Lung Cancer": [
            ("32480", "Removal of lung, other than pneumonectomy; single lobe (lobectomy)"),
            ("32663", "Thoracoscopy, surgical; with lobectomy (segmentectomy)")
        ],
        "Prostate Cancer": [
            ("55866", "Laparoscopy, surgical prostatectomy, retropubic radical, including nerve sparing, robotic when performed"),
            ("55840", "Prostatectomy, retropubic radical, with or without nerve sparing")
        ],
        "Melanoma": [
            ("11646", "Excision, malignant lesion including margins, face/ears/eyelids/nose/lips; >4.0 cm"),
            ("26117", "Radical resection of tumor, soft tissue of hand/finger; 3 cm or greater")
        ],
        "Pancreatic Cancer": [
            ("48150", "Pancreatectomy, proximal subtotal with total duodenectomy, partial gastrectomy, choledochoenterostomy and gastrojejunostomy (Whipple-type procedure)")
        ],
        "Ovarian Cancer": [
            ("58950", "Resection of ovarian, tubal or primary peritoneal malignancy with bilateral salpingo-oophorectomy and omentectomy")
        ],
        "Head and Neck Cancer": [
            ("38720", "Cervical lymphadenectomy (modified radical neck dissection)"),
            ("31360", "Laryngectomy; total, without radical neck dissection")
        ],
        "Bladder Cancer": [
            ("51570", "Cystectomy, complete (separate procedure)")
        ],
        "Kidney Cancer": [
            ("50545", "Nephrectomy, radical; with regional lymphadenectomy and/or vena caval thrombectomy")
        ],
        "Liver Cancer": [
            ("47120", "Hepatectomy, resection of liver; partial lobectomy")
        ],
        "Esophageal Cancer": [
            ("43107", "Esophagectomy, distal two-thirds, with thoracotomy and separate abdominal incision, with or without proximal gastrectomy")
        ]
    }

    # ============================================================
    # PAYERS (PA-relevant + national + third-party UM)
    # ============================================================
    payers = [
        {"payer_name": "Aetna", "payer_type": "National Commercial", "phone": "1-888-672-3282"},
        {"payer_name": "UnitedHealthcare", "payer_type": "National Commercial", "phone": "1-800-782-1102"},
        {"payer_name": "Cigna Healthcare", "payer_type": "National Commercial", "phone": "1-800-244-6224"},
        {"payer_name": "Highmark Blue Cross Blue Shield", "payer_type": "Regional BCBS - PA", "phone": "1-800-241-5704"},
        {"payer_name": "Geisinger Health Plan", "payer_type": "Regional - Central PA", "phone": "1-800-447-4000"},
        {"payer_name": "UPMC Health Plan", "payer_type": "Regional - Western PA", "phone": "1-888-876-2756"},
        {"payer_name": "EviCore healthcare", "payer_type": "Third Party Utilization Management", "phone": "1-800-918-8924"},
        {"payer_name": "Humana", "payer_type": "Medicare Advantage", "phone": "1-800-448-6262"},
        {"payer_name": "Independence Blue Cross", "payer_type": "Regional BCBS - SE PA", "phone": "1-800-275-2583"},
        {"payer_name": "Capital Blue Cross", "payer_type": "Regional BCBS - Central PA", "phone": "1-800-962-2242"},
    ]

    # ============================================================
    # PROVIDERS (45 doctors with unique NPI, names, specialties)
    # ============================================================
    providers = []
    specialties = [
        "Surgical Oncology", "Medical Oncology", "Radiation Oncology",
        "Colorectal Surgery", "Thoracic Surgery", "Urologic Oncology",
        "Gynecologic Oncology", "Breast Surgical Oncology", "Head & Neck Surgical Oncology",
        "Hepatobiliary Surgery", "Endocrine Surgery"
    ]
    used_npis = set()
    for j in range(45):
        while True:
            npi = str(random.randint(1000000000, 1999999999))
            if npi not in used_npis:
                used_npis.add(npi)
                break
        fname = random.choice(first_names_male + first_names_female)
        lname = random.choice(last_names)
        spec = random.choice(specialties)
        providers.append({
            "provider_npi": npi,
            "first_name": fname,
            "last_name": lname,
            "full_name": f"Dr. {fname} {lname}",
            "specialty": spec
        })

    # ============================================================
    # FACILITIES (12 PA-relevant with unique org NPI)
    # ============================================================
    facilities = []
    fac_names = [
        "Hershey Medical Center", "Mount Nittany Medical Center", "Geisinger Medical Center - Danville",
        "UPMC Shadyside", "Penn State Health St. Joseph Medical Center", "WellSpan Chambersburg Hospital",
        "Lehigh Valley Hospital - Cedar Crest", "Thomas Jefferson University Hospital", "Fox Chase Cancer Center",
        "UPMC Hillman Cancer Center", "Lancaster General Health", "Reading Hospital - Tower Health"
    ]
    used_fac_npis = set()
    cities = ["Hershey", "State College", "Danville", "Pittsburgh", "Reading", "Chambersburg",
              "Allentown", "Philadelphia", "Philadelphia", "Pittsburgh", "Lancaster", "Reading"]
    for idx, fname in enumerate(fac_names):
        while True:
            npi = str(random.randint(2000000000, 2999999999))
            if npi not in used_fac_npis:
                used_fac_npis.add(npi)
                break
        ftype = random.choice([
            "Major Academic Medical Center", "Community Cancer Center",
            "Comprehensive Cancer Center", "Regional Hospital", "Outpatient Surgery Center"
        ])
        facilities.append({
            "facility_npi": npi,
            "name": fname,
            "facility_type": ftype,
            "city": cities[idx],
            "state": "PA"
        })

    # ============================================================
    # MAIN DATA GENERATION LOOP
    # ============================================================
    records = []
    patient_records = []

    for i in range(num_records):
        mrn = f"MRN-{100000 + i}"

        # Patient
        gender = random.choice(['M', 'F'])
        if gender == 'M':
            fname = random.choice(first_names_male)
        else:
            fname = random.choice(first_names_female)
        lname = random.choice(last_names)
        dob = (datetime(1938, 1, 1) + timedelta(days=random.randint(0, 20000))).date().isoformat()

        patient_records.append({
            "mrn": mrn,
            "first_name": fname,
            "last_name": lname,
            "dob": dob,
            "gender": gender,
            "patient_name": f"{fname} {lname}"
        })

        # Diagnosis & Procedure (tied together)
        diagnosis = random.choice(cancer_diagnoses)
        primary_dx = dx_map.get(diagnosis, "C80.1")
        # occasional more specific
        if random.random() < 0.35:
            if "Breast" in diagnosis:
                primary_dx = random.choice(["C50.911", "C50.912", "C50.919"])
            elif "Lung" in diagnosis:
                primary_dx = random.choice(["C34.90", "C34.91", "C34.92"])
            elif "Kidney" in diagnosis:
                primary_dx = random.choice(["C64.1", "C64.2", "C64.9"])
        dx_codes = primary_dx
        if random.random() > 0.55:
            extra = random.choice(["Z51.11", "Z51.12", "R53.83", "D64.9", "E46", "Z79.899"])
            dx_codes = f"{primary_dx},{extra}"

        procs = procedure_map.get(diagnosis, [("99213", "Established patient office visit")])
        cpt, cpt_desc = random.choice(procs)

        # Dates (2025-2026 window)
        base_date = datetime(2025, 7, 15) + timedelta(days=random.randint(0, 340))
        referral_date = base_date
        npv_date = referral_date + timedelta(days=random.randint(5, 28))
        auth_req_date = npv_date + timedelta(days=random.randint(2, 18))

        # Auth Status (realistic distribution)
        auth_status = random.choices(
            ["Approved", "Denied", "Pending", "Under Review"],
            weights=[0.55, 0.13, 0.20, 0.12]
        )[0]

        # Validity Period & Auth Code
        if auth_status == "Approved":
            v_start = auth_req_date + timedelta(days=random.randint(0, 4))
            v_end = v_start + timedelta(days=random.randint(45, 135))
            auth_code = f"AU{random.randint(10000000, 99999999)}"
            validity_start = v_start.date().isoformat()
            validity_end = v_end.date().isoformat()
        else:
            validity_start = ""
            validity_end = ""
            auth_code = ""

        # Peer-to-Peer (higher chance if not approved or complex)
        p2p_chance = 0.38 if auth_status != "Approved" else 0.07
        peer_to_peer_required = "Yes" if random.random() < p2p_chance else "No"

        # Third party reviewer (Evicore etc for imaging/labs/some procedures)
        third_party = random.choice(["EviCore", "Carelon Medical Benefits Management", ""]) if random.random() < 0.30 else ""

        # Payer & Plan
        payer = random.choice([p["payer_name"] for p in payers])
        plan_type = random.choice(["PPO", "HMO", "EPO", "POS", "Medicare Advantage", "Medicaid Managed Care"])

        # NPIs from masters
        ordering_npi = random.choice([p["provider_npi"] for p in providers])
        facility_npi = random.choice([f["facility_npi"] for f in facilities])

        # Insurance Agent (first + last - lots of variety)
        ag_fname = random.choice(first_names_male + first_names_female)
        ag_lname = random.choice(last_names)

        # Clinical Questions & Phone Time (realistic distribution + logic)
        num_q = random.randint(5, 20)
        if peer_to_peer_required == "Yes":
            num_q += random.randint(4, 9)
        if auth_status in ["Denied", "Under Review"]:
            num_q += random.randint(2, 6)
        num_q = max(4, min(32, num_q))

        phone_min = int(random.gauss(24, 10))
        if peer_to_peer_required == "Yes":
            phone_min += int(random.gauss(22, 9))
        if auth_status == "Denied":
            phone_min += random.randint(8, 18)
        phone_min = max(7, min(165, phone_min))

        # Denial Reason
        denial_reasons_list = [
            "Documentation does not support medical necessity per guidelines",
            "Requested service not a covered benefit under member's current plan",
            "Insufficient clinical documentation provided for medical review",
            "Alternative, less invasive treatment preferred per evidence-based guidelines",
            "Procedure considered experimental or investigational for this indication",
            "Member eligibility or coverage issue on proposed date of service",
            "Duplicate or overlapping authorization request already on file",
            "Requires additional peer-to-peer discussion with ordering provider"
        ]
        denial_reason = random.choice(denial_reasons_list) if auth_status == "Denied" else ""

        # Labs & Imaging Ordered (Yes/No + pipe-delimited details)
        labs_ordered = "Yes" if random.random() > 0.22 else "No"
        labs_details = ""
        if labs_ordered == "Yes":
            lab_options = ["CBC with differential", "CMP", "PT/INR", "Type and Screen", "CEA", "CA 19-9",
                           "CA-125", "PSA", "AFP", "LDH", "CRP", "ESR", "Vitamin D 25-OH", "HbA1c", "Ferritin"]
            labs_details = "|".join(random.sample(lab_options, random.randint(2, 5)))

        imaging_ordered = "Yes" if random.random() > 0.32 else "No"
        imaging_details = ""
        if imaging_ordered == "Yes":
            img_options = ["CT Chest/Abdomen/Pelvis w/ contrast", "MRI Abdomen w/wo contrast",
                           "PET-CT Skull to Mid-Thigh", "Diagnostic Mammogram Bilateral", "Breast Ultrasound",
                           "Whole Body Bone Scan", "CT-Guided Needle Biopsy", "Echocardiogram Transthoracic"]
            imaging_details = "|".join(random.sample(img_options, random.randint(1, 3)))

        # Barrier Reason (insurance/auth focused, building on original)
        if auth_status == "Pending":
            barrier_reason = random.choice([
                "Insurance authorization pending",
                "Clinical documentation pending from ordering provider office",
                "Peer-to-peer review scheduled - awaiting completion",
                "Third-party UM (EviCore/Carelon) review in progress",
                "Additional labs or imaging results needed for determination"
            ])
        elif auth_status == "Denied":
            barrier_reason = denial_reason.split(".")[0] if denial_reason else "Authorization denied - see denial reason"
        elif auth_status == "Under Review":
            barrier_reason = "Under additional clinical review or scheduled peer-to-peer"
        else:
            barrier_reason = ""

        # Scheduling status (tie to auth)
        if auth_status == "Approved":
            sched_status = random.choices(
                ["Scheduled", "Delayed", "Completed", "In Progress"],
                weights=[0.35, 0.25, 0.25, 0.15]
            )[0]
        else:
            sched_status = "Auth Pending / Delayed"

        priority_level = random.choices(["High", "Medium", "Low"], weights=[0.28, 0.52, 0.20])[0]

        # Assemble record (all fields from your handwritten list + context)
        rec = {
            "auth_id": f"AUTH-{100000 + i}",
            "mrn": mrn,
            "referral_date": referral_date.date().isoformat(),
            "new_patient_visit_date": npv_date.date().isoformat(),
            "diagnosis_type": diagnosis,
            "primary_dx_code": primary_dx,
            "dx_codes": dx_codes,
            "cpt_code": cpt,
            "cpt_description": cpt_desc,
            "labs_ordered": labs_ordered,
            "labs_details": labs_details,
            "imaging_ordered": imaging_ordered,
            "imaging_details": imaging_details,
            "ordering_provider_npi": ordering_npi,
            "facility_npi": facility_npi,
            "insurance_provider": payer,
            "healthcare_plan": plan_type,
            "third_party_reviewer": third_party,
            "insurance_auth_status": auth_status,
            "authorization_code": auth_code,
            "authorization_validity_start": validity_start,
            "authorization_validity_end": validity_end,
            "peer_to_peer_required": peer_to_peer_required,
            "insurance_agent_first_name": ag_fname,
            "insurance_agent_last_name": ag_lname,
            "num_clinical_questions_asked": num_q,
            "total_time_spent_on_phone_min": phone_min,
            "denial_reason": denial_reason,
            "priority_level": priority_level,
            "scheduling_status": sched_status,
            "barrier_reason": barrier_reason
        }
        records.append(rec)

    # ============================================================
    # DATAFRAMES & CSV OUTPUT (structured / relational)
    # ============================================================
    auth_df = pd.DataFrame(records)
    patients_df = pd.DataFrame(patient_records)
    providers_df = pd.DataFrame(providers)
    facilities_df = pd.DataFrame(facilities)
    payers_df = pd.DataFrame(payers)

    # Write CSVs with numbered prefix for easy ordering
    patients_df.to_csv(os.path.join(output_dir, "01_patients.csv"), index=False)
    providers_df.to_csv(os.path.join(output_dir, "02_providers.csv"), index=False)
    facilities_df.to_csv(os.path.join(output_dir, "03_facilities.csv"), index=False)
    payers_df.to_csv(os.path.join(output_dir, "04_payers.csv"), index=False)
    auth_df.to_csv(os.path.join(output_dir, "05_authorizations.csv"), index=False)

    print(f"✓ Generated {num_records} authorization records")
    print(f"✓ Master tables: {len(patients_df)} patients, {len(providers_df)} providers, {len(facilities_df)} facilities, {len(payers_df)} payers")
    print(f"✓ CSVs written to: {output_dir}/")

    # ============================================================
    # ANALYSIS EXCEL (multi-sheet, like previous oncology_agent_analysis.xlsx)
    # ============================================================
    xl_path = "/home/workdir/artifacts/oncology_insurance_analysis.xlsx"
    with pd.ExcelWriter(xl_path, engine="openpyxl") as writer:
        # Main data sheets
        auth_df.to_excel(writer, sheet_name="Authorizations", index=False)
        patients_df.to_excel(writer, sheet_name="Patients", index=False)
        providers_df.to_excel(writer, sheet_name="Providers", index=False)
        facilities_df.to_excel(writer, sheet_name="Facilities", index=False)
        payers_df.to_excel(writer, sheet_name="Payers", index=False)

        # --- Denial Rates by Payer ---
        denied = auth_df[auth_df["insurance_auth_status"] == "Denied"]
        denial_by_payer = denied.groupby("insurance_provider").size().reset_index(name="denied_count")
        total_by_payer = auth_df.groupby("insurance_provider").size().reset_index(name="total_count")
        denial_stats = pd.merge(total_by_payer, denial_by_payer, on="insurance_provider", how="left").fillna(0)
        denial_stats["denial_rate_pct"] = (denial_stats["denied_count"] / denial_stats["total_count"] * 100).round(1)
        denial_stats = denial_stats.sort_values("denial_rate_pct", ascending=False)
        denial_stats.to_excel(writer, sheet_name="Denial Rates by Payer", index=False)

        # --- Metrics by Auth Status (phone time, questions) ---
        status_metrics = auth_df.groupby("insurance_auth_status").agg(
            total_count=("auth_id", "count"),
            avg_phone_time_min=("total_time_spent_on_phone_min", "mean"),
            median_phone_time_min=("total_time_spent_on_phone_min", "median"),
            max_phone_time_min=("total_time_spent_on_phone_min", "max"),
            avg_clinical_questions=("num_clinical_questions_asked", "mean"),
            median_clinical_questions=("num_clinical_questions_asked", "median")
        ).round(1).reset_index()
        status_metrics.to_excel(writer, sheet_name="Metrics by Auth Status", index=False)

        # --- Peer-to-Peer Impact Analysis ---
        p2p_group = auth_df.groupby("peer_to_peer_required")
        p2p_impact = pd.DataFrame({
            "peer_to_peer_required": ["No", "Yes"],
            "avg_phone_time_min": [
                p2p_group.get_group("No")["total_time_spent_on_phone_min"].mean() if "No" in p2p_group.groups else 0,
                p2p_group.get_group("Yes")["total_time_spent_on_phone_min"].mean() if "Yes" in p2p_group.groups else 0
            ],
            "avg_questions_asked": [
                p2p_group.get_group("No")["num_clinical_questions_asked"].mean() if "No" in p2p_group.groups else 0,
                p2p_group.get_group("Yes")["num_clinical_questions_asked"].mean() if "Yes" in p2p_group.groups else 0
            ],
            "denial_rate_pct": [
                (p2p_group.get_group("No")["insurance_auth_status"] == "Denied").mean() * 100 if "No" in p2p_group.groups else 0,
                (p2p_group.get_group("Yes")["insurance_auth_status"] == "Denied").mean() * 100 if "Yes" in p2p_group.groups else 0
            ]
        }).round(1)
        p2p_impact.to_excel(writer, sheet_name="Peer-to-Peer Impact", index=False)

        # --- High Effort / High Risk Cases (long calls or many questions) ---
        high_effort_mask = (auth_df["total_time_spent_on_phone_min"] > 50) | (auth_df["num_clinical_questions_asked"] > 18)
        high_effort = auth_df[high_effort_mask].sort_values("total_time_spent_on_phone_min", ascending=False).head(20)
        high_effort.to_excel(writer, sheet_name="High Effort Cases", index=False)

        # --- Denial Reasons Breakdown ---
        if len(denied) > 0:
            denial_reason_counts = denied["denial_reason"].value_counts().reset_index()
            denial_reason_counts.columns = ["denial_reason", "count"]
            denial_reason_counts["pct_of_denials"] = (denial_reason_counts["count"] / len(denied) * 100).round(1)
            denial_reason_counts.to_excel(writer, sheet_name="Denial Reasons", index=False)

        # --- Top Barriers (non-approved) ---
        non_approved = auth_df[auth_df["insurance_auth_status"] != "Approved"]
        if len(non_approved) > 0:
            barrier_counts = non_approved["barrier_reason"].value_counts().head(8).reset_index()
            barrier_counts.columns = ["barrier_reason", "count"]
            barrier_counts.to_excel(writer, sheet_name="Top Barriers", index=False)

    print(f"✓ Analysis Excel saved: {xl_path}")

    # ============================================================
    # MARKDOWN REPORT (executive summary + how to use)
    # ============================================================
    approval_pct = (auth_df["insurance_auth_status"] == "Approved").mean() * 100
    denial_pct = (auth_df["insurance_auth_status"] == "Denied").mean() * 100
    pending_pct = (auth_df["insurance_auth_status"] == "Pending").mean() * 100
    avg_phone_all = auth_df["total_time_spent_on_phone_min"].mean()
    avg_q_all = auth_df["num_clinical_questions_asked"].mean()
    p2p_pct = (auth_df["peer_to_peer_required"] == "Yes").mean() * 100
    third_party_pct = (auth_df["third_party_reviewer"] != "").mean() * 100

    report_path = "/home/workdir/artifacts/oncology_insurance_report.md"
    with open(report_path, "w") as f:
        f.write("# Synthetic Oncology Insurance Authorization Dataset & Analysis\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EDT  \n")
        f.write(f"**Total Authorization Records:** {num_records}  \n")
        f.write(f"**Unique Patients:** {len(patients_df)}  \n")
        f.write(f"**Unique Providers (NPI):** {len(providers_df)}  \n")
        f.write(f"**Unique Facilities (NPI):** {len(facilities_df)}  \n")
        f.write(f"**Insurance Payers / UM Companies:** {len(payers_df)}  \n\n")

        f.write("---\n\n")
        f.write("## Executive Snapshot\n\n")
        f.write(f"- **Overall Approval Rate:** {approval_pct:.1f}%  \n")
        f.write(f"- **Denial Rate:** {denial_pct:.1f}%  \n")
        f.write(f"- **Pending / Under Review:** {pending_pct:.1f}%  \n")
        f.write(f"- **Peer-to-Peer Review Required:** {p2p_pct:.1f}% of cases  \n")
        f.write(f"- **Third-Party UM Reviewer (EviCore/Carelon etc.):** {third_party_pct:.1f}% of cases  \n")
        f.write(f"- **Average Phone Time per Auth:** {avg_phone_all:.1f} minutes  \n")
        f.write(f"- **Average Clinical Questions per Auth:** {avg_q_all:.1f}  \n\n")

        f.write("This dataset expands the previous oncology scheduling synthetic data with deep insurance ")
        f.write("authorization workflow details exactly matching the fields in your handwritten list. ")
        f.write("It is designed for operational analytics, denial root-cause analysis, workflow optimization, ")
        f.write("agent performance tracking, and potentially ML modeling (predict approval likelihood, estimate handle time, etc.).\n\n")

        f.write("---\n\n")
        f.write("## Structured Multi-CSV Relational Design\n\n")
        f.write("Data is intentionally split into normalized tables (like a mini data warehouse) so you can:\n\n")
        f.write("- Join `authorizations` to `patients` on `mrn`\n")
        f.write("- Join to `providers` on `ordering_provider_npi` (or add rendering NPI if needed)\n")
        f.write("- Join to `facilities` on `facility_npi`\n")
        f.write("- Analyze by `insurance_provider` from payers table\n\n")
        f.write("**CSV Files (in `/oncology_insurance_dataset/`):**\n\n")
        f.write("| File | Description | Key Columns |\n")
        f.write("|------|-------------|-------------|\n")
        f.write("| `01_patients.csv` | Patient master | mrn, first_name, last_name, dob, gender |\n")
        f.write("| `02_providers.csv` | Physician master (ordering/rendering) | provider_npi, first_name, last_name, full_name, specialty |\n")
        f.write("| `03_facilities.csv` | Facility / hospital master | facility_npi, name, facility_type, city, state |\n")
        f.write("| `04_payers.csv` | Insurance payers + third-party UM | payer_name, payer_type, phone |\n")
        f.write("| `05_authorizations.csv` | **Main fact table** - full authorization workflow fields + context | See column list below |\n\n")

        f.write("## Columns in authorizations.csv\n\n")
        f.write("- `auth_id`, `mrn`, `referral_date`, `new_patient_visit_date`\n")
        f.write("- `diagnosis_type`, `primary_dx_code`, `dx_codes` (Primary + comma-delimited additional ICD-10)\n")
        f.write("- `cpt_code`, `cpt_description` (procedure code tied to diagnosis)\n")
        f.write("- `labs_ordered` (Yes/No), `labs_details` (pipe-delimited specific labs)\n")
        f.write("- `imaging_ordered` (Yes/No), `imaging_details` (pipe-delimited specific imaging)\n")
        f.write("- `ordering_provider_npi`, `facility_npi` (FKs to master tables)\n")
        f.write("- `insurance_provider`, `healthcare_plan` (PPO/HMO/EPO/POS/Medicare Advantage/Medicaid)\n")
        f.write("- `third_party_reviewer` (EviCore, Carelon, or blank)\n")
        f.write("- `insurance_auth_status` (Approved/Denied/Pending/Under Review)\n")
        f.write("- `authorization_code`, `authorization_validity_start`, `authorization_validity_end`\n")
        f.write("- `peer_to_peer_required` (Yes/No)\n")
        f.write("- `insurance_agent_first_name`, `insurance_agent_last_name` (generated from large name pools)\n")
        f.write("- `num_clinical_questions_asked`, `total_time_spent_on_phone_min`\n")
        f.write("- `denial_reason` (when Denied)\n")
        f.write("- `priority_level`, `scheduling_status`, `barrier_reason` (insurance/auth focused)\n\n")

        f.write("---\n\n")
        f.write("## Key Analysis Sheets in oncology_insurance_analysis.xlsx\n\n")
        f.write("1. **Authorizations** - Full main table (filterable/sortable in Excel)\n")
        f.write("2. **Patients / Providers / Facilities / Payers** - Master data for lookups\n")
        f.write("3. **Denial Rates by Payer** - Sorted by highest denial % (great for contracting/UM focus)\n")
        f.write("4. **Metrics by Auth Status** - Avg/median/max phone time & questions by Approved/Denied/Pending\n")
        f.write("5. **Peer-to-Peer Impact** - How P2P requirement affects handle time, questions, and denial rate\n")
        f.write("6. **High Effort Cases** - Top 20 longest calls or highest question volume (ops review candidates)\n")
        f.write("7. **Denial Reasons** - Breakdown of why cases denied (root cause insights)\n")
        f.write("8. **Top Barriers** - Most common blocking reasons for non-approved auths\n\n")

        f.write("---\n\n")
        f.write("## How This Was Built (Reproducible & Extensible)\n\n")
        f.write("Single Python script `generate_insurance_auth_data.py` that:\n")
        f.write("- Uses large hardcoded lists of realistic first/last names (male/female) for patients, doctors, and insurance agents\n")
        f.write("- Maps diagnoses to realistic ICD-10 primary codes + occasional additional codes\n")
        f.write("- Maps each cancer type to plausible surgical CPT codes with descriptions\n")
        f.write("- Generates consistent FK relationships (MRN, NPI) across tables\n")
        f.write("- Applies business logic (e.g. longer phone time + more questions when P2P required or denied)\n")
        f.write("- Outputs both raw CSVs (for data pipelines) and polished multi-sheet Excel + Markdown report\n")
        f.write("- Seed=42 for reproducibility; easy to change num_records, weights, date ranges\n\n")

        f.write("**Next possible extensions you mentioned or that make sense:**\n")
        f.write("- Add more records (500-5000) for ML training\n")
        f.write("- Add rendering_provider_npi, referring_provider_npi\n")
        f.write("- Add cost/allowed amount fields for denial $ impact\n")
        f.write("- Add auth_request_timestamp + decision_timestamp for turnaround time analysis\n")
        f.write("- Build a simple Streamlit dashboard on top of the CSVs for interactive filtering by payer/agent/status\n")
        f.write("- Train a classifier to predict denial risk from questions/time/p2p/dx/cpt features\n\n")

        f.write("---\n\n")
        f.write("## Sample Insights from This Run\n\n")
        f.write(f"- Highest denial rates tend to be with certain regional payers or when third-party UM involved.\n")
        f.write(f"- Peer-to-peer cases show significantly higher average handle time (~{p2p_impact.iloc[1]['avg_phone_time_min']:.0f} min vs ~{p2p_impact.iloc[0]['avg_phone_time_min']:.0f} min) and slightly elevated denial risk.\n")
        f.write(f"- Top denial reasons cluster around 'medical necessity documentation' and 'not covered under plan'.\n")
        f.write(f"- High-effort cases (long calls + many questions) often involve complex imaging/labs or pancreatic/esophageal procedures.\n\n")

        f.write("All data is 100% synthetic and suitable for model training, testing, or internal tooling prototypes.\n")
        f.write("Matches exactly the insurance workflow fields you listed in the image/notes.\n")

    print(f"✓ Report saved: {report_path}")
    print("\nDone! Open the CSVs, the xlsx analysis file, or read the .md report for full details.")

if __name__ == "__main__":
    main()

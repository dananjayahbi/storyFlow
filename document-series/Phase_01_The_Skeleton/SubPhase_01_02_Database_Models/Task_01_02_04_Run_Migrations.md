# Task 01.02.04 — Run Migrations

## Metadata

| Field                    | Value                                                                                                    |
| ------------------------ | -------------------------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                                                            |
| **Phase**                | Phase 01 — The Skeleton                                                                                  |
| **Document Type**        | Layer 3 — Task Document                                                                                  |
| **Estimated Complexity** | Low                                                                                                      |
| **Dependencies**         | [Task_01_02_01](Task_01_02_01_Create_Project_Model.md), [Task_01_02_02](Task_01_02_02_Create_Segment_Model.md), [Task_01_02_03](Task_01_02_03_Create_GlobalSettings_Model.md) |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.4)                                 |

---

## Objective

Generate and apply Django migrations for all three models (Project, Segment, GlobalSettings), creating the SQLite database schema.

---

## Instructions

### Step 1: Activate Virtual Environment

```bash
cd backend

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

---

### Step 2: Generate Migrations

```bash
python manage.py makemigrations api
```

**Expected output:**

```
Migrations for 'api':
  api/migrations/0001_initial.py
    - Create model Project
    - Create model GlobalSettings
    - Create model Segment
```

> If you see errors, they typically indicate model definition issues — missing imports, incorrect field arguments, or Pillow not installed.

---

### Step 3: Apply Migrations

```bash
python manage.py migrate
```

**Expected output (first run):**

```
Operations to perform:
  Apply all migrations: admin, api, auth, contenttypes, sessions
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  Applying admin.0001_initial... OK
  ...
  Applying api.0001_initial... OK
  Applying sessions.0001_initial... OK
```

---

### Step 4: Verify Database File

Confirm that `backend/db.sqlite3` exists:

```bash
# Windows (PowerShell)
Test-Path db.sqlite3

# macOS/Linux
ls -la db.sqlite3
```

---

### Step 5: Verify No Pending Migrations

```bash
python manage.py migrate
```

**Expected output:**

```
No migrations to apply.
```

---

## Expected Output

```
backend/
├── api/
│   └── migrations/
│       ├── __init__.py         ← Existing
│       └── 0001_initial.py     ← NEW (auto-generated)
├── db.sqlite3                  ← NEW (auto-generated)
└── ...
```

---

## Validation

- [ ] `python manage.py makemigrations api` completes with zero errors.
- [ ] `backend/api/migrations/0001_initial.py` exists.
- [ ] `python manage.py migrate` completes with zero errors, showing `OK` for all migrations.
- [ ] `backend/db.sqlite3` file exists.
- [ ] Running `python manage.py migrate` again shows "No migrations to apply."

---

## Notes

- `db.sqlite3` is git-ignored (configured in Task 01.01.10). Each developer will generate their own local database.
- The migration file `0001_initial.py` IS committed to Git — it records the schema definition.
- If `makemigrations` fails with a Pillow error, ensure Pillow is installed: `pip install Pillow>=10.0,<11.0`.
- Do NOT modify the auto-generated migration file manually.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_02_03_Create_GlobalSettings_Model.md](Task_01_02_03_Create_GlobalSettings_Model.md)
> **Next Task:** [Task_01_02_05_Register_Admin.md](Task_01_02_05_Register_Admin.md)

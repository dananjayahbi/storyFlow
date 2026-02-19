# Task 01.02.11 — Create Superuser

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                           |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Low                                                                     |
| **Dependencies**         | [Task_01_02_04](Task_01_02_04_Run_Migrations.md) — Migrations must be applied |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.11)|

---

## Objective

Create a Django superuser account for accessing the admin interface during development, and verify that all three models are accessible in the admin panel.

---

## Instructions

### Step 1: Create the Superuser

From the `backend/` directory with the virtual environment activated:

```bash
python manage.py createsuperuser
```

When prompted, enter:

| Field    | Value            |
| -------- | ---------------- |
| Username | `admin`          |
| Email    | `admin@localhost`|
| Password | `admin`          |

> Django will warn that the password is too common. Type `y` to confirm — this is a local-only development account.

---

### Step 2: Verify Admin Login

1. Start the dev server: `python manage.py runserver`
2. Navigate to `http://localhost:8000/admin/`
3. Log in with `admin` / `admin`.
4. Confirm you see the following sections in the admin:
   - **API** → Projects, Segments, Global Settings
   - **Authentication and Authorization** → Groups, Users

---

### Step 3: Smoke-Test the Models

1. **Create a test Project:** Click "Projects" → "Add Project" → enter a title (e.g., "Test Project") → Save.
2. **Verify GlobalSettings singleton:** Click "Global Settings" → you should see one entry (auto-created or able to add one). After creating it, the "Add" button should disappear.
3. **Verify Project list display:** Return to the Projects list. Confirm you see columns: Title, Status, Created At, Updated At.

---

## Expected Output

No files are created or modified. The superuser is stored in the SQLite database (`db.sqlite3`).

---

## Validation

- [ ] `python manage.py createsuperuser` completes without errors.
- [ ] Login at `http://localhost:8000/admin/` succeeds with the created credentials.
- [ ] Projects, Segments, and Global Settings all appear in the admin interface.
- [ ] A Project can be created through the admin.
- [ ] GlobalSettings admin prevents creating more than one instance.
- [ ] GlobalSettings admin prevents deleting the singleton.

---

## Notes

- The superuser credentials (`admin`/`admin`) are for **local development only**. There is no authentication in the application itself — the superuser is solely for Django Admin access.
- This is the **last task** in SubPhase 01.02. After this, all database models, migrations, serializers, admin configuration, DRF settings, and the superuser are in place.
- SubPhase 01.03 will build the API views, URL routing, and frontend components that consume the models and serializers created here.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Phase:** [Phase_01_Overview.md](../../Phase_01_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../../00_Project_Overview.md) (Layer 0)
> **Previous Task:** [Task_01_02_10_Create_ProjectDetail_Serializer.md](Task_01_02_10_Create_ProjectDetail_Serializer.md)
> **Next Task:** None — SubPhase 01.02 Complete ✓

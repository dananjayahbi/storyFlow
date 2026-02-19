# Task 01.01.01 — Initialize Django Project

## Metadata

| Field                    | Value                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                |
| **Phase**                | Phase 01 — The Skeleton                                                                |
| **Document Type**        | Layer 3 — Task Document                                                                |
| **Estimated Complexity** | Medium                                                                                 |
| **Dependencies**         | None — this is the first task in the first sub-phase                                   |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.1)               |

---

## Objective

Create the `/backend` directory, set up a Python virtual environment inside it, install the foundational Python packages (Django, DRF, django-cors-headers, Pillow), and scaffold the Django project using `django-admin startproject storyflow_backend .`. At the end of this task, the Django development server starts successfully on `http://localhost:8000`.

---

## Instructions

### Step 1: Create the Backend Directory

Create the `/backend` directory at the project root. This directory will house the entire Django project, virtual environment, and all backend code.

```bash
mkdir backend
cd backend
```

**Result:** An empty `backend/` directory exists at the project root.

---

### Step 2: Create the Python Virtual Environment

Inside `/backend`, create a Python virtual environment named `venv`.

```bash
python -m venv venv
```

Then activate it:

- **Windows (PowerShell):**
  ```powershell
  venv\Scripts\activate
  ```
- **Windows (cmd):**
  ```cmd
  venv\Scripts\activate.bat
  ```
- **macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```

After activation, the terminal prompt should show `(venv)` at the beginning.

**Verification:** Run `python --version` — it should show Python 3.11 or higher.

---

### Step 3: Install Core Python Packages

With the virtual environment activated, install the four foundational packages:

```bash
pip install "Django>=5.0,<6.0" "djangorestframework>=3.15,<4.0" "django-cors-headers>=4.3,<5.0" "Pillow>=10.0,<11.0"
```

**Verification:** Run `pip list` and confirm:

| Package                 | Expected Version Range |
| ----------------------- | ---------------------- |
| Django                  | 5.x                   |
| djangorestframework     | 3.15+                 |
| django-cors-headers     | 4.3+                  |
| Pillow                  | 10.x                  |

> **Important:** Do NOT install `onnxruntime`, `moviepy`, `numpy`, `soundfile`, or any processing libraries. Those are added in Phases 03–04.

---

### Step 4: Scaffold the Django Project

Run the `startproject` command with the trailing `.` to place `manage.py` directly inside `/backend`:

```bash
django-admin startproject storyflow_backend .
```

> **Critical:** The trailing `.` (dot) is essential. Without it, Django creates a nested `backend/storyflow_backend/storyflow_backend/` structure, which breaks the expected directory layout.

**Result:** The following files are auto-generated:

```
backend/
├── manage.py
└── storyflow_backend/
    ├── __init__.py
    ├── asgi.py
    ├── settings.py
    ├── urls.py
    └── wsgi.py
```

---

### Step 5: Verify the Django Development Server

Start the development server to confirm the scaffold is valid:

```bash
python manage.py runserver
```

**Expected output:**

```
Watching for file changes with StatReloader
...
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

Open `http://localhost:8000` in a browser — the default Django "The install worked successfully!" page should display.

> **Note:** You will see a warning about unapplied migrations — this is expected and will be resolved in SubPhase 01.02. Ignore it for now.

Press `Ctrl+C` to stop the server after verification.

---

## Expected Output

After completing this task, the project has the following structure:

```
/storyflow_root
└── /backend
    ├── manage.py                          ← Django management script
    ├── /venv                              ← Python virtual environment (git-ignored)
    │   ├── /Lib (or /lib)
    │   ├── /Scripts (or /bin)
    │   └── pyvenv.cfg
    └── /storyflow_backend
        ├── __init__.py                    ← Package init
        ├── asgi.py                        ← ASGI config (default)
        ├── settings.py                    ← Django settings (default — customized in Task 05)
        ├── urls.py                        ← Root URL config (default — modified in SubPhase 01.03)
        └── wsgi.py                        ← WSGI config (default)
```

The Django development server starts and serves the default welcome page. No models, no apps beyond the defaults, and no settings customization — those are handled by subsequent tasks.

---

## Validation

- [ ] `backend/` directory exists at the project root.
- [ ] `backend/venv/` directory exists and contains a valid Python virtual environment.
- [ ] Running `python --version` (with venv activated) shows Python 3.11+.
- [ ] `pip list` shows Django 5.x, djangorestframework 3.15+, django-cors-headers 4.3+, and Pillow 10.x.
- [ ] `backend/manage.py` exists at the top level of `/backend` (not nested deeper).
- [ ] `backend/storyflow_backend/settings.py` exists (one level of nesting, not two).
- [ ] `python manage.py runserver` starts without errors on `http://localhost:8000`.
- [ ] The default Django welcome page loads in a browser at `http://localhost:8000`.
- [ ] No processing libraries (onnxruntime, moviepy, numpy, soundfile) are installed.

---

## Notes

- The settings module is named `storyflow_backend`, NOT `storyflow`. This is intentional — it matches the project naming convention from `Phase_01_Overview.md`.
- The `venv/` directory is local to `/backend` and will be excluded by `.gitignore` (created in Task 01.01.10). Do not commit it.
- The unapplied migrations warning on `runserver` is normal at this stage — Django's built-in auth and admin migrations haven't been applied yet. This is handled in SubPhase 01.02 after model definitions.
- On Windows, if PowerShell blocks script execution, run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` before activating the virtual environment.

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Phase:** [Phase_01_Overview.md](../Phase_01_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Next Task:** [Task_01_01_02_Create_Api_App.md](Task_01_01_02_Create_Api_App.md)

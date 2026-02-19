# Task 01.01.05 — Configure Django Settings

## Metadata

| Field                    | Value                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                |
| **Phase**                | Phase 01 — The Skeleton                                                                |
| **Document Type**        | Layer 3 — Task Document                                                                |
| **Estimated Complexity** | Medium                                                                                 |
| **Dependencies**         | [Task_01_01_02](Task_01_01_02_Create_Api_App.md) — `api` app must exist to register it |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.5)               |

---

## Objective

Customize the auto-generated `backend/storyflow_backend/settings.py` to register the installed apps (`rest_framework`, `corsheaders`, `api`), configure the CORS middleware, set media file paths, and update `ALLOWED_HOSTS`. After this task, Django starts with all required middleware and app registrations in place.

---

## Instructions

### Step 1: Update `INSTALLED_APPS`

**File:** `backend/storyflow_backend/settings.py`

Replace the default `INSTALLED_APPS` list with:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    # Local
    'api',
]
```

**Grouping matters for readability:** Django built-ins first, then third-party packages, then local apps. Add comment separators as shown.

---

### Step 2: Update `MIDDLEWARE`

Replace the default `MIDDLEWARE` list with:

```python
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',          # ← MUST be FIRST
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

> **Critical:** `CorsMiddleware` MUST be the **first** entry in the middleware list — before `SecurityMiddleware` and before `CommonMiddleware`. Incorrect placement causes CORS preflight requests to fail.

---

### Step 3: Add CORS Configuration

Add the following below the `MIDDLEWARE` list (or at the bottom of the file):

```python
# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]
```

This allows the Next.js frontend (running on port 3000) to make API requests to the Django backend (port 8000).

---

### Step 4: Update `ALLOWED_HOSTS`

Change the default empty list:

```python
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
```

This is required for Django to accept requests on `localhost`.

---

### Step 5: Configure Media File Settings

Add the following below `STATIC_URL`:

```python
# Media files (user-uploaded content)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

This tells Django where to store and serve uploaded files (project images, audio, rendered videos). The `media/` directory was created in (or will be created in) [Task 01.01.12](Task_01_01_12_Create_Media_And_Model_Dirs.md).

---

### Step 6: Verify `DEFAULT_AUTO_FIELD`

Confirm this line already exists in the default `settings.py` (it should be auto-generated):

```python
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

If it exists, leave it as-is. If missing, add it.

---

### Step 7: Verify the Server Starts

With the virtual environment activated, run:

```bash
cd backend
python manage.py runserver
```

The server should start with **no errors**. You may see a warning about unapplied migrations — this is expected and resolved in SubPhase 01.02.

> **If you see errors:** Common issues include:
> - `ModuleNotFoundError: No module named 'corsheaders'` → virtual environment not activated or package not installed.
> - `ModuleNotFoundError: No module named 'rest_framework'` → same as above.
> - `No installed app with label 'api'` → `api` app directory doesn't exist (Task 01.01.02 not completed).

---

## Expected Output

The `settings.py` file now contains all required configuration. No new files are created — this task only modifies the existing auto-generated `settings.py`.

**Summary of changes to `settings.py`:**

| Setting                | Before (default)    | After (customized)                                      |
| ---------------------- | ------------------- | ------------------------------------------------------- |
| `INSTALLED_APPS`       | 6 Django built-ins  | + `rest_framework`, `corsheaders`, `api`                |
| `MIDDLEWARE`            | 7 default entries   | + `CorsMiddleware` as first entry                       |
| `ALLOWED_HOSTS`        | `[]`                | `['localhost', '127.0.0.1']`                            |
| `CORS_ALLOWED_ORIGINS` | *(not present)*     | `["http://localhost:3000"]`                             |
| `MEDIA_URL`            | *(not present)*     | `'/media/'`                                             |
| `MEDIA_ROOT`           | *(not present)*     | `BASE_DIR / 'media'`                                   |
| `DEFAULT_AUTO_FIELD`   | Already present     | Verified — no change                                    |

---

## Validation

- [ ] `INSTALLED_APPS` contains `'rest_framework'`, `'corsheaders'`, and `'api'`.
- [ ] `'corsheaders.middleware.CorsMiddleware'` is the **first** entry in `MIDDLEWARE`.
- [ ] `CORS_ALLOWED_ORIGINS` contains `"http://localhost:3000"`.
- [ ] `ALLOWED_HOSTS` contains `'localhost'` and `'127.0.0.1'`.
- [ ] `MEDIA_URL` is set to `'/media/'`.
- [ ] `MEDIA_ROOT` is set to `BASE_DIR / 'media'`.
- [ ] `DEFAULT_AUTO_FIELD` is `'django.db.models.BigAutoField'`.
- [ ] `python manage.py runserver` starts without errors.

---

## Notes

- The `CORS_ALLOWED_ORIGINS` list only includes `http://localhost:3000` — this is the Next.js development server. No production URLs are needed because StoryFlow is a local-only application.
- `MEDIA_ROOT` uses `BASE_DIR / 'media'` (pathlib syntax), which resolves to `backend/media/`. This is where Django stores uploaded files via `ImageField` and `FileField`.
- The `CorsMiddleware` placement as the first middleware entry is intentional. Some guides place it after `SecurityMiddleware`, but placing it first ensures all CORS headers are set before any other middleware can short-circuit the response.
- No `REST_FRAMEWORK` configuration block is added at this stage. DRF's default settings (e.g., pagination, permissions) will be configured in later sub-phases as needed.

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Phase:** [Phase_01_Overview.md](../Phase_01_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_01_01_04_Write_Requirements_File.md](Task_01_01_04_Write_Requirements_File.md)
> **Next Task:** [Task_01_01_06_Initialize_NextJS_Project.md](Task_01_01_06_Initialize_NextJS_Project.md)

# Task 01.01.09 — Configure CORS (Verification)

## Metadata

| Field                    | Value                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                 |
| **Phase**                | Phase 01 — The Skeleton                                                                 |
| **Document Type**        | Layer 3 — Task Document                                                                 |
| **Estimated Complexity** | Low                                                                                     |
| **Dependencies**         | [Task_01_01_05](Task_01_01_05_Configure_Django_Settings.md) — Django settings must be configured |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.9)                |

---

## Objective

Verify that CORS is correctly configured in Django settings so the Next.js frontend (`localhost:3000`) can make API requests to the Django backend (`localhost:8000`) without cross-origin errors.

> **Note:** The CORS configuration was already written in Task 01.01.05. This task is a dedicated verification pass to ensure everything works end-to-end.

---

## Instructions

### Step 1: Verify `django-cors-headers` in INSTALLED_APPS

Open `backend/storyflow/settings.py` and confirm `corsheaders` is present:

```python
INSTALLED_APPS = [
    # ... default Django apps ...
    'corsheaders',
    'rest_framework',
    'api',
]
```

---

### Step 2: Verify CorsMiddleware Placement

Confirm `CorsMiddleware` appears **before** `CommonMiddleware` in the `MIDDLEWARE` list:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',       # ← Must be BEFORE CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # ...
]
```

> **Why placement matters:** `CorsMiddleware` must process the request before `CommonMiddleware` to inject the correct CORS headers. Placing it lower will cause CORS preflight requests to fail silently.

---

### Step 3: Verify CORS_ALLOWED_ORIGINS

Confirm the allowed origins include the Next.js development server:

```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]
```

---

### Step 4: Live Cross-Origin Test

1. Start the Django backend:

   ```bash
   cd backend
   python manage.py runserver
   ```

2. In a separate terminal, start the Next.js frontend:

   ```bash
   cd frontend
   npm run dev
   ```

3. Open a browser, navigate to `http://localhost:3000`, open the Developer Tools console (F12 → Console), and run:

   ```javascript
   fetch("http://localhost:8000/api/")
     .then(res => console.log("Status:", res.status))
     .catch(err => console.error("CORS error:", err));
   ```

4. Expected outcome:
   - If CORS is correct: You should see `Status: 404` (because no API routes exist yet, but the request itself is allowed).
   - If CORS is broken: You will see a `TypeError: Failed to fetch` or a `CORS error` message in the console.

> A `404` response is a **pass** — it means the request reached Django and was processed. The route simply does not exist yet.

---

## Expected Output

No files are created or modified by this task. This is a verification-only task confirming the CORS configuration written in Task 01.01.05.

---

## Validation

- [ ] `corsheaders` is listed in `INSTALLED_APPS`.
- [ ] `corsheaders.middleware.CorsMiddleware` appears in `MIDDLEWARE` **before** `CommonMiddleware`.
- [ ] `CORS_ALLOWED_ORIGINS` includes `"http://localhost:3000"`.
- [ ] Live fetch from `localhost:3000` to `localhost:8000` does NOT produce a CORS error.

---

## Notes

- This task exists as a separate verification step because CORS misconfiguration is one of the most common issues when setting up a decoupled frontend/backend architecture. Catching it early prevents debugging headaches in later phases.
- If the test in Step 4 fails, double-check the middleware ordering — `CorsMiddleware` must be the **second** item in the list (after `SecurityMiddleware`).
- In production scenarios, `CORS_ALLOWED_ORIGINS` would be tightened. For local development, `localhost:3000` is sufficient.

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_01_08_Initialize_Shadcn_UI.md](Task_01_01_08_Initialize_Shadcn_UI.md)
> **Next Task:** [Task_01_01_10_Create_Gitignore.md](Task_01_01_10_Create_Gitignore.md)

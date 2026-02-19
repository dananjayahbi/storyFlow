# Task 01.01.11 — Create Dev Run Scripts

## Metadata

| Field                    | Value                                                                                                    |
| ------------------------ | -------------------------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.01 — Project Initialization & Tooling Setup                                                  |
| **Phase**                | Phase 01 — The Skeleton                                                                                  |
| **Document Type**        | Layer 3 — Task Document                                                                                  |
| **Estimated Complexity** | Low                                                                                                      |
| **Dependencies**         | [Task_01_01_05](Task_01_01_05_Configure_Django_Settings.md), [Task_01_01_06](Task_01_01_06_Initialize_NextJS_Project.md) |
| **Parent Document**      | [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2, §5.11)                                |

---

## Objective

Create developer convenience scripts that start both the Django backend and Next.js frontend servers with a single command. Scripts are Windows-first but include cross-platform variants.

---

## Instructions

### Step 1: Create the Backend Start Script (Windows)

Create `start-backend.bat` at the **project root**:

```bat
@echo off
echo Starting StoryFlow Backend...
cd /d %~dp0backend
call venv\Scripts\activate
python manage.py runserver
```

---

### Step 2: Create the Backend Start Script (macOS/Linux)

Create `start-backend.sh` at the **project root**:

```bash
#!/bin/bash
echo "Starting StoryFlow Backend..."
cd "$(dirname "$0")/backend"
source venv/bin/activate
python manage.py runserver
```

---

### Step 3: Create the Frontend Start Script (Windows)

Create `start-frontend.bat` at the **project root**:

```bat
@echo off
echo Starting StoryFlow Frontend...
cd /d %~dp0frontend
npm run dev
```

---

### Step 4: Create the Frontend Start Script (macOS/Linux)

Create `start-frontend.sh` at the **project root**:

```bash
#!/bin/bash
echo "Starting StoryFlow Frontend..."
cd "$(dirname "$0")/frontend"
npm run dev
```

---

### Step 5: Verify Scripts Execute Correctly

1. Open a terminal at the project root.
2. Run `start-backend.bat` (Windows) or `bash start-backend.sh` (macOS/Linux).
3. Confirm the Django server starts on `http://localhost:8000`.
4. Open a **second** terminal at the project root.
5. Run `start-frontend.bat` (Windows) or `bash start-frontend.sh` (macOS/Linux).
6. Confirm the Next.js server starts on `http://localhost:3000`.
7. Stop both servers with `Ctrl+C` in each terminal.

---

## Expected Output

```
StoryFlow/
├── start-backend.bat        ← NEW (Windows)
├── start-backend.sh         ← NEW (macOS/Linux)
├── start-frontend.bat       ← NEW (Windows)
├── start-frontend.sh        ← NEW (macOS/Linux)
├── backend/
├── frontend/
└── ...
```

---

## Validation

- [ ] `start-backend.bat` exists at the project root.
- [ ] `start-backend.sh` exists at the project root.
- [ ] `start-frontend.bat` exists at the project root.
- [ ] `start-frontend.sh` exists at the project root.
- [ ] Running the backend script activates the venv and starts Django on port 8000.
- [ ] Running the frontend script starts Next.js on port 3000.

---

## Notes

- These are separate scripts (one per server) rather than a single combined script. This keeps them simple and allows developers to restart one server without affecting the other.
- The `%~dp0` in `.bat` files and `$(dirname "$0")` in `.sh` files ensure the scripts work regardless of which directory the developer runs them from.
- On macOS/Linux, the `.sh` files may need to be made executable: `chmod +x start-backend.sh start-frontend.sh`.
- The scripts assume the virtual environment is located at `backend/venv/` as created in Task 01.01.01.
- A combined "start everything" script is intentionally omitted to keep things simple. Developers should run backend and frontend in separate terminal windows for easier log reading and independent restart.

---

> **Parent:** [SubPhase_01_01_Overview.md](SubPhase_01_01_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_01_10_Create_Gitignore.md](Task_01_01_10_Create_Gitignore.md)
> **Next Task:** [Task_01_01_12_Create_Media_And_Model_Dirs.md](Task_01_01_12_Create_Media_And_Model_Dirs.md)

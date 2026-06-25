# Feature 8.3 — Replace Hardcoded API Base URL with Environment Variable

| Field | Value |
|---|---|
| Feature ID | 8.3 |
| Title | Replace Hardcoded API Base URL with Environment Variable |
| Status | 🟡 Planned |
| Priority | Medium |
| Complexity | Low |
| Estimated Effort | 0.5–1 day |
| Dependencies | None |
| Output Files (NEW) | None (refactor only) |
| Files Modified | frontend/api/projectsApi.ts, frontend/api/settingsApi.ts, frontend/.env.local.example |

---

## 1. Document Overview

### 1.1 Problem Statement

Both `frontend/api/projectsApi.ts` and `frontend/api/settingsApi.ts` create their Axios
instances with the literal string `http://localhost:8000` written directly into the source
code as the value of the `baseURL` configuration property.
This is adequate for a single developer running the complete stack locally on the default port,
but it becomes a real operational obstacle the moment the application needs to run against any
other backend address — including a colleague's machine on the same LAN (`192.168.1.100:8000`),
a cloud-hosted staging server, or a Docker Compose network where the backend is reachable under
an internal hostname rather than `localhost`.
In every one of those cases, a developer must manually open each API source file, locate and
edit the hardcoded URL string, rebuild the frontend bundle, deploy, and then remember to revert
or re-edit the changes before committing — because a committed diff containing a colleague's
local IP address or a staging URL would immediately break every other developer's local workflow.

The second problem is that environment-specific configuration is now baked into the source code
itself, violating the Twelve-Factor App methodology's principle that configuration must be
stored in the environment and not in the code.
The practical effect of this violation is that the same compiled artifact cannot be used for
both local development and staging deployment — a new build is required for each target
environment, increasing build time, increasing the risk of environment-specific bugs that only
appear in production, and making rollback more complicated.
The third problem is the noise introduced into the git history: a deployment to a staging
environment produces a commit whose diff contains nothing of semantic value — just two URL
strings changed to a staging address and then changed back — making the blame history less
meaningful for the files that contain real logic alongside the configuration violation.

---

### 1.2 Proposed Solution

The correct fix is to replace the hardcoded URL in both API files with a reference to
`process.env.NEXT_PUBLIC_API_URL`, with a nullish coalescing fallback to `http://localhost:8000`
so that the application continues to work out of the box with no required configuration for
local development.
In addition, a `.env.local.example` file should be created at `frontend/` to document the
available environment variables so that developers setting up the project or configuring a new
deployment target know exactly what file to create and what values to provide.
A grep search across the entire `frontend/` directory should also be performed to verify that
no additional hardcoded occurrences of `localhost:8000` exist beyond the two known API files.

- In `frontend/api/projectsApi.ts`, locate the Axios instance creation statement and replace
  the hardcoded `baseURL` string value with the expression
  `process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'`, which reads the environment
  variable at Next.js build time and falls back to the local development default if the variable
  is not defined in the environment.

- In `frontend/api/settingsApi.ts`, apply the identical replacement to the Axios instance
  creation statement in that file, ensuring that both API clients use the exact same expression
  for resolving the base URL and behave consistently across all deployment environments.

- Run a recursive text search across all files in `frontend/` for the literal string
  `localhost:8000` to discover any additional hardcoded occurrences in component files, hook
  files, utility files, or any other location not addressed by the two known API files, and
  apply the same environment variable substitution to each additional occurrence found.

- Create the file `frontend/.env.local.example` with a clearly commented section for the
  `NEXT_PUBLIC_API_URL` variable, including the local development default, an example LAN
  address, an example staging URL, and a brief explanation of when each value is appropriate.

- Verify that `frontend/.env.local` is listed as an excluded pattern in `.gitignore` and
  confirm that `frontend/.env.local.example` is tracked by git so that it serves as permanent,
  discoverable documentation for all current and future contributors.

---

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Replacing hardcoded `localhost:8000` in `api/projectsApi.ts` and `api/settingsApi.ts` | Setting up actual staging or production deployment infrastructure |
| Creating `frontend/.env.local.example` with variable documentation | Modifying the Django backend server address or port number |
| Grepping for any additional hardcoded URL occurrences across `frontend/` | Adding other environment variables beyond the API base URL |
| Confirming `.env.local` is excluded from git tracking | Configuring HTTPS, TLS, or certificate handling for the API |
| Documenting Docker Compose usage patterns for the environment variable | Writing Terraform, Helm, or cloud configuration files |

---

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| frontend/api/projectsApi.ts | Axios client for all project CRUD API calls | Contains hardcoded `baseURL: 'http://localhost:8000'` |
| frontend/api/settingsApi.ts | Axios client for settings read and write API calls | Contains hardcoded `baseURL: 'http://localhost:8000'` |
| frontend/.env.local.example | Documentation template for local environment config | Does not yet exist; must be created as part of this task |
| frontend/.env.local | Actual local overrides for environment variables | Must be confirmed as excluded from git via .gitignore |
| frontend/next.config.ts | Next.js configuration file | Should be reviewed for any existing env variable handling |
| backend/storyflow_backend/settings.py | Django settings; defines ALLOWED_HOSTS and CORS config | Reference only; CORS must allow any new origins added by deployment |

---

## 2. Flow Diagram

The following ASCII diagram shows how the API base URL is resolved in both configurations.

    ─────────── BEFORE REFACTORING ──────────────────────────────────────────────
    projectsApi.ts ──── Axios({ baseURL: 'http://localhost:8000' })
                        URL is a compile-time constant baked into the bundle.
    settingsApi.ts ──── Axios({ baseURL: 'http://localhost:8000' })
                        Changing deployment target ──► edit source ──► rebuild.

    ─────────── AFTER REFACTORING ───────────────────────────────────────────────
    .env.local ──────────────────────────────────────────────────────────────────
    NEXT_PUBLIC_API_URL=http://192.168.1.100:8000   (optional; set per environment)

    .env.local.example ──────────────────────────────────────────────────────────
    # NEXT_PUBLIC_API_URL=http://localhost:8000       (local default)
    # NEXT_PUBLIC_API_URL=http://192.168.1.100:8000   (LAN example)
    # NEXT_PUBLIC_API_URL=https://api.staging.example.com  (staging example)

    projectsApi.ts ──── Axios({ baseURL: process.env.NEXT_PUBLIC_API_URL ??
                                          'http://localhost:8000' })
    settingsApi.ts ──── Axios({ baseURL: process.env.NEXT_PUBLIC_API_URL ??
                                          'http://localhost:8000' })
    Changing deployment target ──► set env var ──► no source edit ──► no rebuild.

---

## 3. Step-by-Step Instructions

### Step 3.1 — Replace the Hardcoded URL in the Projects API File

Open `frontend/api/projectsApi.ts` and locate the line where the Axios instance is created
with a configuration object that includes the `baseURL` property set to `'http://localhost:8000'`.
Replace the string literal value with the expression
`process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'`, which Next.js will evaluate at
build time by substituting the value of the environment variable if it is defined, or leaving
the fallback string in place if the variable is absent from the build environment.
After making the change, confirm that the TypeScript compiler in VS Code does not raise a
type error on the `baseURL` property — since Axios accepts `string | undefined` for `baseURL`
but the nullish coalescing operator guarantees this expression always evaluates to a `string`,
no type cast or assertion should be necessary.
Save the file and confirm the development server hot-reloads without errors.

---

### Step 3.2 — Apply the Same Replacement in the Settings API File

Open `frontend/api/settingsApi.ts` and perform the identical substitution — locate the
`baseURL` property in the Axios instance creation and replace the hardcoded string with
`process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'`.
Confirm that the two files now use exactly the same expression for resolving the base URL,
so that behavior is consistent between the projects API client and the settings API client
regardless of which environment variable value is present at build time.
Review the rest of the Axios configuration in `settingsApi.ts` to confirm that no other
configuration property (such as `timeout`, `headers`, or response interceptors) was
accidentally altered during the edit, since those properties must remain unchanged for
the settings API client to function correctly.
Save and verify that the development server continues to run without errors.

---

### Step 3.3 — Grep for Remaining Occurrences and Create the Example File

Run a recursive text search across all files in `frontend/` for the string `localhost:8000`
to identify any additional hardcoded URL occurrences that were not present in the two known
API files, such as a URL constructed inline inside a component or hook file.
For each additional occurrence found, evaluate whether it should also be replaced with the
`NEXT_PUBLIC_API_URL` environment variable expression, or whether it represents a different
kind of reference that should be handled differently (for example, a URL only used in
server-side code, where a non-public environment variable would be more appropriate).
After confirming no additional occurrences remain, create the file `frontend/.env.local.example`
with a commented header explaining its purpose, a line for `NEXT_PUBLIC_API_URL` with the
local development default as the example value, and additional commented lines showing LAN
and staging deployment examples.
Commit this file to the repository so that it is discoverable by future contributors.

---

### Step 3.4 — Verify Git Exclusion and Review CORS Configuration

Open the root `.gitignore` file and confirm that the pattern `frontend/.env.local` (or the
equivalent pattern `.env.local`) is listed as an excluded pattern so that developers' local
environment variable files can never be accidentally committed to the repository.
If the pattern is absent, add it before any further work is done, because a `.env.local` file
containing a developer's LAN address or staging credentials committed to the repository would
require a git history rewrite to fully remove.
Open `backend/storyflow_backend/settings.py` and review the `CORS_ALLOWED_ORIGINS` and
`ALLOWED_HOSTS` settings to understand what configuration changes would be needed on the Django
side when the `NEXT_PUBLIC_API_URL` is pointed to a new origin address during deployment,
and document those CORS requirements clearly in the `.env.local.example` file's comments so
that the deployment checklist is in one discoverable place.

---

## 4. Expected Outcome

1. Neither `frontend/api/projectsApi.ts` nor `frontend/api/settingsApi.ts` contains the
   literal string `localhost:8000` anywhere in the file after the refactoring, meaning that
   retargeting the application to a different backend address requires only setting an
   environment variable rather than editing and rebuilding from modified source code.

2. A developer who needs to deploy the frontend against a different backend — whether for
   LAN testing, staging, or production — can create a `frontend/.env.local` file, set
   `NEXT_PUBLIC_API_URL` to the appropriate address, start or rebuild the Next.js server,
   and immediately have a correctly configured application without touching any source file.

3. The `frontend/.env.local` file is confirmed to be excluded from git tracking, meaning
   environment-specific configuration choices remain private to each developer or deployment
   environment and will never appear in a commit diff, pull request, or code review.

4. A grep search for the string `localhost:8000` across all TypeScript and TSX files in
   `frontend/` returns exactly zero matches outside of the `.env.local.example` file, confirming
   that no hardcoded URL occurrences remain anywhere in the frontend source code.

5. The local development workflow is completely unchanged for developers who do not create
   a `.env.local` file — the nullish coalescing fallback ensures the application continues
   to target `http://localhost:8000` by default, requiring zero additional configuration
   steps for standard local development setups.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] A unit test for `projectsApi.ts` sets `process.env.NEXT_PUBLIC_API_URL` to a custom
      test value and confirms that the Axios instance's `baseURL` equals that custom value,
      verifying that the environment variable is correctly consumed by the Axios configuration.
- [ ] A unit test for `projectsApi.ts` with `NEXT_PUBLIC_API_URL` unset confirms that the
      Axios instance's `baseURL` falls back to `http://localhost:8000` as expected.
- [ ] A unit test for `settingsApi.ts` applies the same environment variable mock and confirms
      that its Axios instance also correctly resolves the base URL from the environment variable.
- [ ] A unit test confirms that an API request made through `projectsApi.ts` targets the URL
      derived from the environment variable, not any hardcoded string, verifying end-to-end
      variable propagation through the Axios configuration.

---

### 5.2 Integration / Manual Tests

- [ ] Start the frontend without a `.env.local` file and verify in the browser's Network panel
      that all API requests made by both `projectsApi.ts` and `settingsApi.ts` target
      `http://localhost:8000` as the fallback default.
- [ ] Create a `frontend/.env.local` file with `NEXT_PUBLIC_API_URL` set to a custom address
      such as `http://localhost:9000`, restart the Next.js development server, and verify in
      the browser's Network panel that API requests are now targeting the configured custom URL.
- [ ] Run `next build` with `NEXT_PUBLIC_API_URL` set as an environment variable and confirm
      the build completes successfully, verifying that the variable is correctly embedded into
      the client bundle during the production build process.
- [ ] Confirm that `frontend/.env.local.example` exists at the expected path, is readable and
      clearly documented, and accurately describes the `NEXT_PUBLIC_API_URL` variable with
      correct example values for at least three deployment scenarios.

---

### 5.3 Regression Tests

- [ ] Run the full Jest test suite and confirm that all previously passing API-layer tests
      continue to pass, verifying that mocking the Axios module still works correctly after
      the environment variable substitution is present in the implementation.
- [ ] Run `tsc --noEmit` across the entire frontend project and confirm the expression
      `process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'` does not introduce any
      new TypeScript errors at the Axios `baseURL` property.
- [ ] Run a grep search for `localhost:8000` across all TypeScript and TSX files in `frontend/`
      and confirm zero matches, establishing that no hardcoded URL occurrences remain in source.

---

## 6. Notes for AI Agent

- The `NEXT_PUBLIC_` prefix on the environment variable name is mandatory and not optional —
  Next.js performs a build-time substitution of environment variable references in client-side
  code, and it will only substitute variables whose names begin with `NEXT_PUBLIC_`; a variable
  named `API_URL` without the prefix will be `undefined` in the browser bundle even if it is
  correctly defined in `.env.local`, causing every API call to silently fall back to `localhost`.

- The `??` nullish coalescing operator is the correct choice for the fallback rather than `||`
  because `||` would also substitute the fallback for an empty string, masking a misconfigured
  environment where the developer has set `NEXT_PUBLIC_API_URL=` with an empty value intending
  to override the default but not providing an actual URL.

- Always also search for occurrences of just `localhost` without the port number during the
  grep audit step, because some files may construct the full URL by concatenating a hostname
  constant with a port constant defined separately, which would not be caught by searching only
  for the full `localhost:8000` string.

- In a Docker Compose based development setup, `NEXT_PUBLIC_API_URL` must be declared in the
  `environment` block of the Next.js frontend service within `docker-compose.yml`, and because
  Next.js bakes public environment variables into the bundle at build time rather than reading
  them at runtime, the Docker image must be built after setting the variable — meaning a single
  pre-built image cannot serve multiple environments without a server-side URL injection strategy.

---

## 6.1 Migration Safety Notes

- Before editing either API file, read through the complete Axios instance configuration in
  each one to ensure that the replacement edit targets only the `baseURL` property and leaves
  all other configuration options — such as `timeout`, request interceptors, response
  interceptors, and default headers — completely unchanged.

- After replacing the URL in both files, run the application in the development server without
  a `.env.local` file and navigate to a page that makes an API call, then open the browser
  Network panel and confirm that the request URL begins with `http://localhost:8000`; this
  directly validates that the fallback is working and the development workflow is unaffected.

- If any existing Jest test directly asserts that the Axios instance's `baseURL` equals the
  hardcoded string `http://localhost:8000`, that test must be updated after the migration to
  either mock `process.env.NEXT_PUBLIC_API_URL` or assert against the fallback value by first
  unsetting the environment variable in the test setup; leaving the old assertion in place
  will cause the test to fail even though the production code is correct.

- The `.env.local.example` file should be committed in the same pull request as the source
  code changes, not as a separate follow-up; separating them risks the documentation being
  missed entirely, leaving future contributors without any guidance on how to configure the
  application for non-localhost environments.

---

*Document created for StoryFlow project — Phase 8 Frontend Refactoring series.*
*Target directory: e:\My_GitHub_Repos\storyFlow\docs\features\document 3\*
*Stack: Next.js (app router) + TypeScript + Zustand*
*Last updated: 2026-03-10*

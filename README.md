# mei-ari-app-be

Mei Ari: inspection officers record findings, Gemini drafts a formal report, and the report moves
through Created → Completed → Verified → Signed. This repo contains the REST API and a web UI.

- Django project: `meiaribe/`
- API app: `meiaribe/meiari_v1/` (models, views, Gemini + report storage in `methods.py`)
- Web UI: `meiaribe/web/` (single-page app served at `/`, plain JS, no build step)
- SQLite DB: `meiaribe/db.sqlite3` (local development)

## Quick start

```bash
cp .env.example .env                                   # set GOOGLE_GEMINI_API_KEY
cd meiaribe && ../.venv/bin/python manage.py seed_demo && cd ..   # optional demo data (safe to re-run)
bash run_server.sh
```

Open http://localhost:8000 and sign in with a demo account (password `MeiAri@123`):

| Account | Role | Can move a report from |
| --- | --- | --- |
| `officer@demo.tn.gov.in` | Inspection officer | Created → Completed |
| `head@demo.tn.gov.in` | Inspection cell head | Completed → Verified |
| `admin@demo.tn.gov.in` | Inspection cell admin | any step, including Verified → Signed; also manages departments and offices |

Role rules are enforced in the UI only; the API does not check roles yet.

## Setup

```bash
bash run_server.sh            # creates .venv + installs requirements on first run, migrates, serves on 0.0.0.0:8000
bash run_server.sh 8001       # custom port
bash run_server.sh 8000 127.0.0.1   # localhost only
```

`settings.py` loads `.env` automatically, so `manage.py` commands work without sourcing it.

Manual setup:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd meiaribe && python manage.py migrate && python manage.py runserver 0.0.0.0:8000
```

Run the tests (Gemini is mocked):

```bash
cd meiaribe && python manage.py test meiari_v1
```

## Configuration (`.env`)

| Variable | Needed for | Default when unset |
| --- | --- | --- |
| `GOOGLE_GEMINI_API_KEY` | Report generation | Report endpoints return an error |
| `GEMINI_MODEL` | Report generation | `gemini-2.5-flash` |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | Sending OTP emails | OTP emails are printed to the server console |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_REGION_NAME`, `AWS_STORAGE_BUCKET_NAME` | Storing reports in S3 | Reports saved under `meiaribe/media/` |
| `SECRET_KEY`, `JWT_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Production | Development values |

## API flow (`/api/v1/`)

1. **Org setup**: `POST tngovtdept/` → `POST tngovtsubdept/` → `POST subdeptofficedetails/` (each also supports `GET`)
2. **Sign up**: `POST create-meiari-user/` (sends a 4-digit OTP) → `POST verify-otp/` `{user_id, otp}` (valid 10 min) → returns `access_id`. Use `POST resend-otp/` `{email}` or `{user_id}` to send a new OTP.
3. **Sign in**: `POST signin/` `{email, password}` → `token` (send as `Authorization: Bearer <token>`), user, and org details
4. **Work groups**: `POST create-workgroup-with-details/`, `GET workgroups/?sub_dept_office=<id>`, `POST workgroupmembers/`, `GET workgroup/<id>/members/`
5. **Tickets**: `POST workgroupticket/` (`ticket_code` is generated), `GET workgroupticket/<ticket_id>/`, `PATCH workgroupticket/<ticket_id>/` (e.g. `{ticket_status}`), `GET workgroupticket/<work_group_id>/` or `?work_group=<id>` (list), `GET workgroup/<id>/ticket-status-count/`
6. **Reports**: `POST generate-and-upload-report/` `{location: {city, latitude, longitude}, departmentName, subDepartmentName, accessId, subDeptOfficeName: <office id>, ...inspection data}` → `GET report-records/<office_id>/` → `GET update-status/<report_id>/?status=Verified` → `GET download-report/<report_id>/`

Lookups: `GET tngovtsubdept/?department=<id>`, `GET subdeptofficedetails/?sub_dept=<id>`, `GET users/?sub_dept_office=<id>`.

Health check: `GET check/`. Admin: `/admin/` (create a login with `python manage.py createsuperuser`).

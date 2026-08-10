# CampusQuest

A professional Flask-based college event discovery and participation platform.

## Stack

- Flask
- Flask-WTF / WTForms
- Jinja2 templates
- Flask-SQLAlchemy
- PostgreSQL
- Gunicorn

## Run locally

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## PostgreSQL

Set:

```text
DATABASE_URL=postgresql+psycopg://username:password@host:5432/database
SECRET_KEY=your-secret-key
```

The app creates its tables automatically on first start.

## Organizer account

The application starts with no demo accounts or demo events. To create an organizer account for development, temporarily change the role assigned in `register()` from `student` to `organizer`, create the account, then change it back.

For production, add a proper admin/organizer provisioning flow.

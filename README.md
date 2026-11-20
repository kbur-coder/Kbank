# Kbank

Django banking backend with a web interface and a REST API. Users register, open accounts and cards, transfer money between accounts, and review transactions.

## Features

- User registration, login, logout and profile editing (`accounts` app).
- Account opening, listing, detail view and closing (`banking` app).
- Transfers between accounts with a transaction history.
- Debit and credit cards linked to accounts.
- Django admin for users, accounts, transactions and cards.
- Swagger and ReDoc API documentation.

## Requirements

- Python 3.11+
- Django 5.2
- djangorestframework
- djangorestframework-simplejwt
- drf-yasg

There is no `requirements.txt` yet.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install django djangorestframework djangorestframework-simplejwt drf-yasg
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The project uses SQLite (`db.sqlite3`, ignored by git).

## Endpoints

Web pages:

| Path | Purpose |
|---|---|
| `/accounts/register/` | Register a new user |
| `/accounts/login/` | Log in |
| `/accounts/profile/` | View profile |
| `/accounts/profile/edit/` | Edit profile |
| `/accounts/logout/` | Log out |
| `/bank/accounts/` | List own accounts |
| `/bank/accounts/open/` | Open an account |
| `/bank/transfer/` | Transfer between accounts |
| `/bank/transactions/` | Transaction history |
| `/bank/cards/` | List cards |
| `/bank/cards/new/` | Create a card |

Other:

| Path | Purpose |
|---|---|
| `/admin/` | Django admin |
| `/api/token/refresh/` | Refresh a JWT token |
| `/swagger/` | Swagger UI |
| `/redoc/` | ReDoc |

## Known issues

- `bank_project/settings.py` contains `DEBUG = True` and a placeholder `SECRET_KEY`. Move both to environment variables before any deployment.
- `accounts/serializers.py` and `banking/serializers.py` refer to fields that the models do not have (for example `birth_date`, `passport`, `created_at`, `is_active`, `timestamp`). They are not used by the HTML views, so the API will not work until they are fixed.
- `Card.cvv` is stored in plain text.
- `accounts/tests.py` and `banking/tests.py` are empty.
- `accounts/__init__.py` and `banking/__init__.py` define `default_app_config`, which is deprecated in Django 3.2 and later.

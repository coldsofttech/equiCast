# equicast-backend

Django REST API that exposes the `equicast` core package over HTTP.

## Local development

```bash
uv sync --extra dev
uv run manage.py migrate
uv run manage.py runserver
```

The API is served at `http://localhost:8000/api/`.

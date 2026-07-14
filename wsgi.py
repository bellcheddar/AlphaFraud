"""Gunicorn entrypoint:  gunicorn wsgi:app  (see deploy/alphafraud-web.service)."""

from alphafraud.webapp import create_app

app = create_app()

"""Gunicorn config for the AlphaFraud web service. Referenced by alphafraud-web.service."""
import os

bind = os.environ.get("BIND_ADDR", "127.0.0.1:8000")
workers = int(os.environ.get("WEB_WORKERS", "3"))
worker_class = "sync"
timeout = 60
graceful_timeout = 30
keepalive = 5
# Log to stdout/stderr so journald captures everything (journalctl -u alphafraud-web).
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
proc_name = "alphafraud-web"

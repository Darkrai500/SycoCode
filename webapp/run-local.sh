#!/bin/sh
set -eu
cd "$(dirname "$0")"
export DJANGO_DEBUG=1
exec .venv/bin/python manage.py runserver 127.0.0.1:8765 --noreload

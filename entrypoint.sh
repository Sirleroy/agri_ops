#!/bin/sh
set -e
echo "Starting gunicorn on port 8000..."
exec gunicorn agri_ops_project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 120 \
    --log-level debug \
    --access-logfile - \
    --error-logfile -

#!/bin/bash
set -e
gunicorn --bind 127.0.0.1:5000 wsgi:app &
APP_PID=$!
sleep 15
echo "start client"
python3 client.py
APP_CODE=$?
sleep 3
echo "kill $APP_PID"
kill -TERM $APP_PID || true
echo "app code $APP_CODE"
exit $APP_CODE
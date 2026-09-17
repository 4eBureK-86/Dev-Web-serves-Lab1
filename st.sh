#!/bin/bash

# запускаем gunicorn, весь вывод пишем в файл, чтобы видеть ошибки
gunicorn --bind 127.0.0.1:5000 wsgi:app > gunicorn.log 2>&1 &
APP_PID=$!

# ждём старта
sleep 15

echo "=== gunicorn log ==="
cat gunicorn.log
echo "===================="

# проверяем, что процесс жив
if ! kill -0 $APP_PID 2>/dev/null; then
    echo "ERROR: gunicorn is not running!"
    exit 1
fi

echo "start client"
python3 client.py
APP_CODE=$?

sleep 3
echo "kill $APP_PID"
kill -TERM $APP_PID 2>/dev/null || true
echo "app code $APP_CODE"
exit $APP_CODE
"# carpooling-and-ride-sharing"
start server: daphne -b 0.0.0.0 -p 8000 carpooling.asgi:application
start a worker: celery -A carpooling worker --loglevel=info --pool=solo

pip install daphne

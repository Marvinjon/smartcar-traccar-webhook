"""
WSGI entry point for Gunicorn.

Usage: gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
"""

from webhook_handler import app

if __name__ == '__main__':
    app.run()

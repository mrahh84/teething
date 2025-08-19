"""
WSGI config for thething project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thething.settings')

application = get_wsgi_application()

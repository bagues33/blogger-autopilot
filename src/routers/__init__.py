"""
Domain Routers Package for Blogger Auto-Pilot SaaS
Organizes API endpoints by domain context with high cohesion and locality.
"""

from . import auth
from . import billing
from . import blogs
from . import articles
from . import keywords
from . import settings
from . import admin
from . import analytics
from . import audit_logs
from . import workspaces
from . import cron

__all__ = [
    'auth',
    'billing',
    'blogs',
    'articles',
    'keywords',
    'settings',
    'admin',
    'analytics',
    'audit_logs',
    'workspaces',
    'cron'
]

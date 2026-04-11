from .base import *  # noqa: F403

DEBUG = config('DEBUG', default=True, cast=bool)  # noqa: F405

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')  # noqa: F405

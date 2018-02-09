"""
tasks.py

module to connect a celery instance to this flask application
"""
from app import celery


@celery.task
def add(x, y):
    return x + y

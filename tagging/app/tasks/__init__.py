"""
tasks.py

module to connect a celery instance to this flask application
"""
from celery.contrib import rdb
from app import celery
from app.tasks import captions
from app.tasks import requests
from app.tasks import wikitext


@celery.task
def add(x, y):
    return x + y

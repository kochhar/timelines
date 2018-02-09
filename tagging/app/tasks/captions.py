"""
captions.py

module containing tasks for captions
"""
import urllib

from app import celery, db


@celery.task
def youtube_captions_from_video(video_id):
    """Given a youtube video id, fetches the captions for the video."""
    CAPTION_SERVICE_URL = 'http://video.google.com/timedtext'

    ?lang=en&v=JFpanWNgfQY

"""
captions.py

module containing tasks for captions
"""
import html
import logging
import os
from os import path
import requests
import subprocess
import tempfile
from xml.etree import ElementTree as ET

from app import app, celery, db

from bs4 import BeautifulSoup

CAPTION_SERVICE_URL = 'http://video.google.com/timedtext'
HEIDELTIME_WD = path.join(app.root_path, app.config['HEIDELTIME_LIB_DIR'])
HEIDELTIME_CMD_ARGS = \
    'java -jar de.unihd.dbs.heideltime.standalone.jar -t narratives'.split()
RESPONSE_SERIAL_FIELDS = [
#    'content',
#    'elapsed',
    'encoding',
    'headers',
    'links',
    'ok',
    'reason',
    'status_code',
    'text',
    'url'
]


@celery.task
def youtube_captions_from_video(video_id):
    """Given a youtube video id, fetches the captions for the video."""
    caption_params = {'lang': 'en', 'v': video_id}
    resp = requests.get(CAPTION_SERVICE_URL, params=caption_params)
    if resp.headers.get('Content-Type') == 'application/json':
        result = {'json': resp.json()}
    else:
        result = {}

    result.update(dict((f, getattr(resp, f)) for f in RESPONSE_SERIAL_FIELDS))
    # headers is an instance of CaseInsensitiveDict, convert to plain dic
    if 'headers' in result:
        result['headers'] = dict(result['headers'])
    return result


@celery.task
def events_from_captions(caption_result, video_id):
    """Given captions as string and a video_id, extracts events."""
    fd, filename = tempfile.mkstemp(suffix='.txt', prefix='cap-',
                                    dir=app.config['HEIDELTIME_TMPINPUT_DIR'])

    transcript_xml = caption_result['text']
    transcript_root = ET.fromstring(transcript_xml)

    f = os.fdopen(fd, 'w')
    for i, text_node in enumerate(transcript_root.findall('text')):
        unescaped = html.unescape(text_node.text)
        f.write(unescaped)
        f.write(' ')
    f.close()
    logging.debug('Wrote {} caption chunks for extraction'.format(i+1))

    cmd_args = HEIDELTIME_CMD_ARGS + [filename]
    logging.info('Invoking HeidelTime with {}'.format(' '.join(cmd_args)))
    res = subprocess.run(cmd_args, cwd=HEIDELTIME_WD, stdout=subprocess.PIPE)
    return res.stdout.decode('utf-8')

def events_from_date(date_pttn):
    wiki_url = wiki_url_from_date(date_pttn)
    html = requests.get(wiki_url).text

    logging.debug('hello there')
    # pass through beautiful soup
    soup = BeautifulSoup(html, 'html.parser')
    
    logging.debug('soup is here {}'.format(soup))

    temp = "somethinge else"
    for link in soup.find_all('a'):
        print(link.get('href'))

    return temp

def wiki_url_from_date(date_pttn):
    return "https://en.wikipedia.org/wiki/2011"
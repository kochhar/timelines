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

@celery.task
def events_from_date(date_pttn):
    date = date_from_pttn(date_pttn)

    events = []

    # get events from the year page
    wiki_url = "https://en.wikipedia.org/wiki/" + date.year
    html = requests.get(wiki_url).text
    year_soup = BeautifulSoup(html, 'html.parser')

    if date.month:
        months = []
        months.append(date.month)
    else if date.season:
        months = months_from_season(date.season)
    else:
        months = ['January', 'February', 'March']

    for month in months:
        events.push(events_from_year_soup(soup, month))

    # get events from the date page
    if date.day && date.month:
        wiki_url = "https://en.wikipedia.org/wiki/" + date.month + "_" + date.day
        html = requests.get(wiki_url).text
        date_soup = BeautifulSoup(html, 'html.parser')
        events.append( events_from_date_soup)
    
    # loop over events to see what matches
    # matchedEvents

    return matchedEvents

def date_from_pttn(date_pttn):
    # todo
    ret = {}
    ret.day = "15"
    ret.months = "3"
    ret.year = "2011"
    
    return ret

def events_from_year_soup(soup, month):
    t = soup.find(id=month)
    bullets = t.parent.next_sibling.next_sibling.children

    events = []
    for bullet in bullets:
        if bullet != "\n":
            events.append(events_from_bullet(bullet))
    
    return events

def events_from_bullet(bullet):
    # bullet is a soup object
    return bullet.get_text()

def events_from_date_soup(soup, year):
    t = soup.find(id="Events")
    bullets_soup = t.parent.next_sibling.next_sibling
    bullet = bullets_soup.select('a[href="/wiki/2011"]')[0].parent; 
    return events_from_bullet(bullet)



# testing 

def test1():
    year = "2011"
    wiki_url = "https://en.wikipedia.org/wiki/" + year
    html = requests.get(wiki_url).text
    soup = BeautifulSoup(html, 'html.parser')

    month = "June"

    return events_from_year_soup(soup, month)

def test2():
    wiki_url = "https://en.wikipedia.org/wiki/March_15"
    html = requests.get(wiki_url).text
    soup = BeautifulSoup(html, 'html.parser')

    year = "2011"

    return events_from_date_soup(soup, year)
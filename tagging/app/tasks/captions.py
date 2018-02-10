"""
captions.py

module containing tasks for captions
"""
from bs4 import BeautifulSoup
import html
import logging
import os
from os import path
import requests
import spacy
import subprocess
import tempfile
from xml.etree import ElementTree as ET

from app import app, celery, db


# load english language processing rules
nlp = spacy.load('en')


CAPTION_SERVICE_URL = 'http://video.google.com/timedtext'
HEIDELTIME_WD = path.join(app.root_path, app.config['HEIDELTIME_LIB_DIR'])
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
def fetch_url_result(url, params):
    """Given a url and params, fetches the result from the url.

    Returns:
        dict containg fields: encoding, headers, links, ok, reason,
                              status_code, text, url
        additionally, if the response is in JSON, result contains a json
        field.
    """
    resp = requests.get(url, params=params)
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
def youtube_captions_from_video(video_id):
    """Given a video_id returns the captions of the video."""
    return fetch_url_result(CAPTION_SERVICE_URL, {'lang': 'en', 'v': video_id})


@celery.task
def annotate_events_in_captions(caption_result, video_id, save_to_file=False):
    """Given captions as string and a video_id, extracts events."""
    transcript = ET.fromstring(caption_result['text'])
    text_blobs = [html.unescape(tn.text) for tn in transcript.findall('text')]
    # reconstitute into a unified blob
    blob = ' '.join(text_blobs).replace('\n', ' ')

    tmp_dir = app.config['HEIDELTIME_TMPINPUT_DIR']
    infd, infile = tempfile.mkstemp(suffix='.txt', prefix='cap-', dir=tmp_dir)
    fin = os.fdopen(infd, 'w')

    # parse the blob into sentences, and write it to the file
    doc = nlp(blob)
    for i, sent in enumerate(doc.sents):
        fin.write(sent.string.strip()+'\n')
    fin.close()
    logging.debug('Wrote {} caption sentences for extraction'.format(i+1))

    # Setup the command to execute
    HEIDELTIME_CMD_ARGS = \
        'java -jar de.unihd.dbs.heideltime.standalone.jar -t narratives'.split()
    cmd_args = HEIDELTIME_CMD_ARGS + [infile]

    # run the command and get the output
    logging.info('Invoking HeidelTime with {}'.format(' '.join(cmd_args)))
    if save_to_file:
        outfd, outfile = tempfile.mkstemp(suffix='.xml', prefix='evt-', dir=tmp_dir)
        res = subprocess.run(cmd_args, cwd=HEIDELTIME_WD, stdout=outfd)
        return outfile
    else:
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
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

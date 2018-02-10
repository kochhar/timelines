"""
captions.py

module containing tasks for captions
"""
from bs4 import BeautifulSoup
import html
import logging
import os
from os import path
import re
import requests
import spacy
import subprocess
import tempfile
from xml.etree import ElementTree as ET

from app import app, celery, db, lib

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
TML_REGEX = "<TimeML>(.*)</TimeML>"
TML_MATCHER = re.compile(TML_REGEX, re.DOTALL)
TIMX_REGEX = "<TIMEX3[^>]*>[^<]*</TIMEX3>"
TIMX_MATCH = re.compile(TIMX_REGEX)


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
    # container for the result
    annotated = {
        'captions': {'sents':[], 'ents': []},
        'heidel': {'sents':[]}
    }

    captions = ET.fromstring(caption_result['text'])
    text_blobs = [html.unescape(tn.text) for tn in captions.findall('text')]

    # parse the text blocks into entities and sentences
    entity_and_sent = lib.nlp_over_lines_as_blob(text_blobs, lib.entities_from_span, lib.str_from_span)
    entity_and_sent_pairs = list(entity_and_sent)
    # inside-out trick, converts a list of tuples into a tuple of lists, which get unpacked
    entities, sents = zip(*entity_and_sent_pairs)
    annotated['captions']['ents'] = entities
    annotated['captions']['sents'] = sents

    tmp_dir = app.config['HEIDELTIME_TMPINPUT_DIR']
    infd, infile = tempfile.mkstemp(suffix='.txt', prefix='cap-', dir=tmp_dir)
    fin = os.fdopen(infd, 'w')
    for sent_str in sents:
        fin.write(sent_str+'\n')
    fin.close()
    logging.debug('Wrote {} caption sentences for extraction'.format(len(sents)))

    # Setup the command to execute
    HEIDELTIME_CMD_ARGS = 'java -jar de.unihd.dbs.heideltime.standalone.jar -t narratives'.split()
    cmd_args = HEIDELTIME_CMD_ARGS + [infile]

    # run the command and get the output
    logging.info('Invoking HeidelTime with {}'.format(' '.join(cmd_args)))
    res = subprocess.run(cmd_args, cwd=HEIDELTIME_WD, stdout=subprocess.PIPE)
    output = res.stdout.decode('utf-8')
    match = TML_MATCHER.search(output)
    if not match:
        logging.info('Did not find any TimeML in the HeidelTime output')
        return annotated

    body = match.group(1)
    sents = [sent for sent in body.split('\n') if len(sent)]
    annotated['heidel']['sents'] = sents

    return annotated


@celery.task
def event_dates_from_timeml_annotated_captions(annotated, video_id):
    """Extracts events their dates and the entities associated with the
    event from captions which have been annotated with TimeML.

    Params:
        - annotated - {
            'captions': { 'sents': [ plain text sentences ] },
            'heidel': { 'sents': [ annotated sentences ] }
        }
        - video_id - string with the video_id
    """
    cap_sents = annotated['captions']['sents']
    cap_ents = annotated['captions']['ents']
    cap_timeann = annotated['heidel']['sents']
    logging.debug('Sentences: {}'.format(cap_sents))
    logging.debug('Entities: {}'.format(cap_ents))
    logging.debug('Annotated: {}'.format(cap_timeann))

    events = []
    ctx_entities = context_window(cap_ents, bef=1, aft=1)
    for ann, entities in zip(cap_timeann, ctx_entities):
        matches = TIMX_MATCH.finditer(ann)
        if not matches:
            events.append(())
            continue

        entities['before'] = [e for bl in entities['before'] for e in bl]
        entities['after'] = [e for al in entities['after'] for e in al ]
        ann_events = [_event_metadata(match) for match in matches]
        ann_events = [
            {'text': e[0], 'date': e[1], 'ents': entities}
            for e in ann_events if (e[0] and e[1])
        ]
        events.append(ann_events)

    annotated['events'] = events
    return annotated


def context_window(listy, bef=1, aft=1):
    """Given a list-list object (supporting random access) yields context
    windows before and after each item."""
    for i in range(len(listy)):
        idxb, idxaf = max(0, i-bef), min(i+aft+1, len(listy))
        before, after = listy[idxb:i], listy[i:idxaf]
        yield {'item': listy[i], 'before': before, 'after': after}


def _event_metadata(re_match_object):
    """Given a regex match object matching a TIMEX3 tag returns
    title and date metadata about the event.

    Params:
        re_match_object - re.MAtchObject

    Returns:
        A tuple (desc, date_pattern)
    """
    match = re_match_object
    start, end = (match.start(), match.end())
    tag_str = match.string[start:end]
    try:
        event = ET.fromstring(tag_str)
        if event.attrib.get('type') == 'DATE':
            desc = event.text
            date = event.attrib.get('value')
            return (desc, date)
        else:
            return (None, None)
    except ET.ParseError:
        import pdb; pdb.set_trace()


# testing

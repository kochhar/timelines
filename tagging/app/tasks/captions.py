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
    # reconstitute into a unified blob
    blob = ' '.join(text_blobs).replace('\n', ' ')

    tmp_dir = app.config['HEIDELTIME_TMPINPUT_DIR']
    infd, infile = tempfile.mkstemp(suffix='.txt', prefix='cap-', dir=tmp_dir)
    fin = os.fdopen(infd, 'w')

    # parse the blob into sentences, and write it to the file
    doc = nlp(blob)
    for i, sent in enumerate(doc.sents):
        entities = entities_from_span(sent)
        sent_str = sent.string.strip()
        annotated['captions']['ents'].append(entities)
        annotated['captions']['sents'].append(sent_str)
        fin.write(sent_str+'\n')
    fin.close()
    logging.debug('Wrote {} caption sentences for extraction'.format(i+1))

    # Setup the command to execute
    HEIDELTIME_CMD_ARGS = \
        'java -jar de.unihd.dbs.heideltime.standalone.jar -t narratives'.split()
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
def events_from_timeml_annotated_captions(annotated, video_id):
    """Extracts events from captions which have been annotated with TimeML.

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


def entities_from_span(spacy_span):
    """Given a spact span object, returns the entities in the span."""
    entities, temp_stack = list(), list()
    for token in spacy_span:
        if token.ent_iob_ == 'B':
            # Beginning a new entity. Complete the current stack and clear
            if temp_stack:
                entities.append(entity_text_type_from_tokens(temp_stack))
                temp_stack.clear()
            # Add the current one to start the new entity
            temp_stack.append(token)
        elif token.ent_iob_ == 'I':
            if not len(temp_stack):
                raise ValueError('Inside an entity but no stack is empty')
            temp_stack.append(token)
        elif token.ent_iob_ == 'O':
            # Ended entity. Complete the current stack and clear
            if temp_stack:
                entities.append(entity_text_type_from_tokens(temp_stack))
                temp_stack.clear()
    # end loop

    return entities


def entity_text_type_from_tokens(tokens):
    """Given an iterable of tokens representing an entity, returns a tuple
    with the entity text and type. Assumes that all tokens are of the same
    entity and there is only a single entity type."""
    entext = ' '.join([t.text for t in tokens])
    entype = tokens[0].ent_type_
    return entext, entype


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

"""
captions.py

module containing tasks for captions
"""
import html
import logging
import operator as op
import os
from os import path
import re
import subprocess
from xml.etree import ElementTree as ET

from app import app, celery, lib
from app.tasks import requests as treq


CAPTION_SERVICE_URL = 'http://video.google.com/timedtext'
HEIDELTIME_WD = path.join(app.root_path, app.config['HEIDELTIME_LIB_DIR'])
TML_REGEX = "<TimeML>(.*)</TimeML>"
TML_MATCHER = re.compile(TML_REGEX, re.DOTALL)
TIMX_REGEX = "<TIMEX3[^>]*>[^<]*</TIMEX3>"
TIMX_MATCH = re.compile(TIMX_REGEX)


@celery.task
def youtube_captions_from_video(video_id):
    """Given a video_id returns the captions of the video."""
    return treq.fetch_url_result(CAPTION_SERVICE_URL, {'lang': 'en', 'v': video_id})


@celery.task
def annotate_events_in_captions(caption_result, video_id, save_to_file=False):
    """Given captions as string and a video_id, extracts events."""
    # container for the result
    video_extract = {
        'video_id': video_id,
        'captions': {'sents':[], 'ents': []},
        'heidel': {'sents':[]}
    }
    if not caption_result['text']: return video_extract

    captions = ET.fromstring(caption_result['text'])
    text_blobs = [html.unescape(tn.text).replace('\n', ' ') for tn in captions.findall('text')]
    text_times = [tn.attrib.get('start') for tn in captions.findall('text')]

    # parse the text blocks into entities and sentences
    entity_and_sent = lib.nlp_over_lines_as_blob(text_blobs, lib.entities_from_span, lib.str_from_span)
    entity_and_sent_pairs = list(entity_and_sent)
    # inside-out trick, converts a list of tuples into a tuple of lists, which get unpacked
    entities, sents = zip(*entity_and_sent_pairs)
    timestamps, sents = zip(*assign_timestamp_to_sentences(text_blobs, text_times, sents))
    video_extract['captions']['ents'] = entities
    video_extract['captions']['sents'] = sents
    video_extract['captions']['timestamps'] = timestamps

    infile = lib.save_to_tempfile_as_lines(sents, prefix='cap-'+video_id,
                                           dir=app.config['HEIDELTIME_TMPINPUT_DIR'])
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
        return video_extract

    body = match.group(1)
    sents = [sent for sent in body.split('\n') if len(sent)]
    video_extract['heidel']['sents'] = sents

    return video_extract


def assign_timestamp_to_sentences(text_blobs, text_times, sentences):
    sentence_stamps = []
    idx_blob, idx_sent = 0, 0
    part_blob, part_sent = None, None

    while idx_blob < len(text_blobs):
        blob, ts = (part_blob, ts) if part_blob else (text_blobs[idx_blob], text_times[idx_blob])
        sentence = part_sent if part_sent else sentences[idx_sent]
        blob, sentence = blob.strip(), sentence.strip()
        # If blob and sentence are the same, record the timestamp and move to the next
        if blob == sentence:
            # if this match completes a previous sentence don't update sentence stamps
            if not part_sent:
                sentence_stamps.append((ts, sentences[idx_sent]))
            idx_blob += 1
            idx_sent += 1
            part_blob, part_sent = None, None
            continue

        # If not, two cases are possible:
        # - blob is longer than sentence
        # - sentence if longer than blob
        if blob.startswith(sentence):
            # if this match completes a previous sentence don't update sentence stamps
            if not part_sent:
                sentence_stamps.append((ts, sentences[idx_sent]))
            idx_sent += 1
            part_blob, part_sent = blob[len(sentence):], None
        elif sentence.startswith(blob):
            # if this match completes a previous sentence don't update sentence stamps
            if not part_sent:
                sentence_stamps.append((ts, sentences[idx_sent]))
            idx_blob += 1
            part_blob, part_sent = None, sentence[len(blob):]
        else:
            logging.warn('No initial overlap between %s and %s', blob, sentence)

    return sentence_stamps


@celery.task
def event_dates_from_timeml_annotated_captions(video_extract):
    """Extracts events their dates and the entities associated with the
    event from captions which have been annotated with TimeML.

    Params:
        - video_extract - {
            'video_id': '<video_id>',
            'captions': { 'sents': [ plain text sentences ] },
            'heidel': { 'sents': [ annotated sentences ] }
        }
        - video_id - string with the video_id
    """
    cap_ents = video_extract['captions']['ents']
    cap_timeann = video_extract['heidel']['sents']
    logging.debug('Entities: {}'.format(cap_ents))
    logging.debug('Annotated: {}'.format(cap_timeann))

    events = []
    ctx_ents = context_window(cap_ents, bef=1, aft=1)
    for ann, entities in zip(cap_timeann, ctx_ents):
        matches = TIMX_MATCH.finditer(ann)
        if not matches:
            events.append(())
            continue

        entities['before'] = [e for bl in entities['before'] for e in bl]
        entities['after'] = [e for al in entities['after'] for e in al ]

        event_text, event_date = op.itemgetter(0), op.itemgetter(1)
        ann_events = [_event_metadata(match) for match in matches]
        ann_events = [
            {'text': event_text(e), 'date': event_date(e), 'ents': entities}
            for e in ann_events if (event_text(e) and event_date(e))
        ]
        events.append(ann_events)

    video_extract['events'] = events
    return video_extract


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

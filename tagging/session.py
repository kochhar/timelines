import logging
logging.basicConfig(level=logging.DEBUG)

from app import lib
from app.tasks import captions
from app.tasks import wikitext
from importlib import reload
captions = reload(captions)
wikitext = reload(wikitext)

def run_annotations(video_id):
    """Runs the time annotations for a video id."""
    caps = captions.youtube_captions_from_video(video_id)
    annotations = captions.annotate_events_in_captions(caps, video_id)
    return annotations


def run_pipeline(video_id, save_as_json=True):
    """Runs the pipeline for a video id."""
    caps = captions.youtube_captions_from_video(video_id)
    annotations = captions.annotate_events_in_captions(caps, video_id)
    event_dates = captions.event_dates_from_timeml_annotated_captions(annotations)
    wikipedia_events = wikitext.wikipedia_events_from_dates(event_dates)

    # matching via entities
    wikipedia_entities = wikitext.event_entities_from_wikitext(wikipedia_events)
    matched_events = wikitext.match_event_via_entities(wikipedia_entities)
    # matching via vector similarity
    # vector_matches = wikitext.match_event_via_vector_sim(wikipedia_events)

    linked_topics = wikitext.resolve_match_link_topics(matched_events)

    if save_as_json:
        video_id = linked_topics['video_id']
        filename = lib.save_to_tempfile_as_json(linked_topics, prefix='match-{}-'.format(video_id))
        logging.info('Saved extracted events to %s', filename)

    return linked_topics


def preprocess_video_set():
    """Preprocesses the video set."""
    return [
        run_pipeline(video_id)
        for video_id in [
            'JFpanWNgfQY',
            '8EDW88CBo-8',
            'AQPlREDW-Ro',
            'iRYZjOuUnlU',
            'pzmO6RWy1v8',
            'wb6IiSUxpgw',
            'K5H5w3_QTG0',
            'veMFCFyOwFI',
        ]
    ]

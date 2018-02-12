import logging
logging.basicConfig(level=logging.DEBUG)

from app.tasks import captions
from app.tasks import wikitext
from importlib import reload
captions = reload(captions)
wikitext = reload(wikitext)


def run_pipeline(video_id):
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
    return matched_events


matched_events = run_pipeline('veMFCFyOwFI')

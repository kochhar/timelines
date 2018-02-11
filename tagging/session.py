import logging
logging.basicConfig(level=logging.DEBUG)

from app.tasks import captions
from app.tasks import wikitext
from importlib import reload
captions = reload(captions)
wikitext = reload(wikitext)

caps = captions.youtube_captions_from_video('veMFCFyOwFI')
annotations = captions.annotate_events_in_captions(caps, 'video')
event_dates = captions.event_dates_from_timeml_annotated_captions(annotations, 'video')
wikipedia_events = wikitext.wikipedia_events_from_dates(event_dates, 'video')
wikipedia_entities = wikitext.event_entities_from_wikitext(wikipedia_events, 'video')
matched_events = wikitext.match_event_via_entities(wikipedia_entities, 'video')


def save_as_json(obj, filename):
    f = open(filename, 'w')
    f.write(json.dumps(obj, indent=2))
    f.close()

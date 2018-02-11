"""
wikitext.py

module containing tasks for wikitext processing
"""
from bs4 import BeautifulSoup
import collections
import functools
import logging
import operator as op
import re
import requests

from app import app, celery, db, lib
DatePtn = collections.namedtuple('DatePtn', 'year month months day ssn')


CITE_REGEX = '\[\d+\]'
CITE_MATCH = re.compile(CITE_REGEX)
DEFAULT_DATEPTN = DatePtn(year=None, month=None, months=None, day=None, ssn=None)
ENTITY_TYPE_BLACKLIST = [
    'CARDINAL', 'DATE', 'LANGUAGE', 'MONEY',
    'ORDINAL', 'PERCENT', 'QUANTITY', 'TIME',
]
ITEM_MATCH_THRESHOLD = 0.25
WINDOW_MATCH_THRESHOLD = 0.18
MONTHS_BY_INDEX = {
    '01': 'January', '02': 'February', '03': 'March',
    '04': 'April', '05': 'May', '06': 'June',
    '07': 'July', '08': 'August',  '09': 'September',
    '10': 'October', '11': 'November', '12': 'December'
}
STOP_DATES = ['PRESENT_REF', 'XXXX-XX-XX']
# Time parsing regular expressions
YMD_REGEX = '(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})'
YM_REGEX  = '(?P<year>\d{4})-(?P<month>\d{2})'
YS_REGEX  = '(?P<year>\d{4})-(?P<season>\S+)'
YR_REGEX  = '(?P<year>\d{4})'
YMD_MATCH = re.compile(YMD_REGEX)
YM_MATCH = re.compile(YM_REGEX)
YS_MATCH = re.compile(YS_REGEX)
YR_MATCH = re.compile(YR_REGEX)


@celery.task
def wikipedia_events_from_dates(extracted_events, video_id):
    """Fetches wikipedia event descriptions given dates."""
    events = extracted_events['events']
    logging.debug('Events: {}'.format(events))

    for i, sent in enumerate(events):
        for j, event in enumerate(sent):
            date = date_from_pattern(event['date'])
            if not date or not date.year:
                event['wiki'] = []
                continue

            logging.info('Sent {}, candidate event {} on date {}'.format(i, j, date))
            event['wiki'] = wikitexts_from_date(date)

    return extracted_events


def wikitexts_from_date(date):
    """Given a DatePtn, returns a list of wikitext for the events on those days."""
    # get events from the year page
    wiki_url = "https://en.wikipedia.org/wiki/" + date.year
    html = requests.get(wiki_url).text
    year_soup = BeautifulSoup(html, 'html.parser')

    if date.month:
        months = [MONTHS_BY_INDEX[date.month]]
    elif date.ssn:
        months = [MONTHS_BY_INDEX[m] for m in date.months]
    else:
        months = MONTHS_BY_INDEX.values()

    wiki_texts = []
    for month in months:
        wiki_texts.extend(events_from_year_soup(year_soup, month))

    # get events from the date page
    if date.day and date.month:
        wiki_url = "https://en.wikipedia.org/wiki/" + MONTHS_BY_INDEX[date.month] + "_" + date.day
        html = requests.get(wiki_url).text
        date_soup = BeautifulSoup(html, 'html.parser')
        wiki_texts.extend(events_from_date_soup(date_soup, date.year))

    return wiki_texts


@celery.task
def event_entities_from_wikitext(extracted_events, video_id):
    """Runs named entity extraction over the wiki text for each extracted event.
    Extracted entities are saved in the wiki object for each event."""
    events = extracted_events['events']
    logging.debug('Events {}'.format(events))

    text_cleaner = functools.partial(CITE_MATCH.sub, '')
    entity_extractor = lib.entities_from_span
    nlp_over_lines = lib.nlp_over_lines

    for i, sent in enumerate(events):
        for j, event in enumerate(sent):
            if 'wiki' not in event: continue

            wiki_blobs = event['wiki']
            wiki_texts = [text_cleaner(b['text']) for b in wiki_blobs]
            extracts = nlp_over_lines(wiki_texts, entity_extractor)
            for blob, (entities,) in zip(wiki_blobs, extracts):
                blob['ents'] = entities

    return extracted_events


@celery.task
def match_event_via_entities(extracted_events, video_id):
    """Atempts to match an extracted event with the candidate wikipedia
    events for the date."""
    events = extracted_events['events']
    logging.debug('Events {}'.format(events))

    def entity_filter(entity_pairs):
        return [(e, etype) for (e, etype) in entity_pairs if etype not in ENTITY_TYPE_BLACKLIST]

    for candidate_list in events:
        if not candidate_list: continue
        for date in candidate_list:
            if date['date'] in STOP_DATES: continue

            try:
                match, scores = match_event_on_date(
                    text=date['text'],
                    date=date['date'],
                    ents=date['ents'],
                    candidate_events=date['wiki'],
                    entity_filter=entity_filter
                )
                date['match'] = match
                date['scores'] = scores
            except KeyError as ke:
                import pdb; pdb.set_trace()

    filename = lib.save_to_tempfile_as_json(extracted_events, prefix='match-{}-'.format(video_id))
    logging.info('Saved extracted events to %s', filename)
    return extracted_events


def match_event_on_date(text, date, ents, candidate_events, entity_filter):
    """Given an event date and entities relevant to the event, tries to match
    against candidate events fetched from wikipedia.

    Params:
        text - date text
        date - date as a pattern
        ents - Dict containing entity tuples for the event, and for windows
               before and after the event
        candidate_events - List of dicts containing: entities, text & links
               for the candidate events
        entity_filter - function which filters the relevant entities
    """
    date_item_ents = entity_filter(ents['item'])
    item_scores = [jacquard(date_item_ents, entity_filter(e['ents'])) for e in candidate_events]
    item_matches = [(i, score) for (i, score) in enumerate(item_scores) if score >= ITEM_MATCH_THRESHOLD]

    date_window_ents = entity_filter(ents['item'] + ents['before'] + ents['after'])
    # score the date ents against each candidate
    window_scores = [jacquard(date_window_ents, entity_filter(e['ents'])) for e in candidate_events]
    window_matches = [(i, score) for (i, score) in enumerate(window_scores) if score >= WINDOW_MATCH_THRESHOLD]

    event_scores = [(isc, wsc) for (isc, wsc) in zip(item_scores, window_scores)]
    matches = merge_item_window_matches(item_matches, window_matches)
    if not matches:
        return None, event_scores

    # get the best scoring event and return a copy of its dict
    best_idx, best_score = sorted(matches, key=op.itemgetter(1), reverse=True)[0]
    match_dict = dict(candidate_events[best_idx])
    match_dict.update({'idx': best_idx, 'score': best_score})
    return match_dict, event_scores


def jacquard(first, second):
    """Computes the jacquard similarity between two vectors described as lists.
    The items in the lists must be hashable.

    Jacquard similarity is the ratio of common items to the total items."""
    if not first or not second: return 0.0

    common = set(first).intersection(second)
    union = set(first).union(second)

    return float(len(common)) / float(len(union))


def merge_item_window_matches(item_matches, window_matches):
    unified_matches = []
    idx_item, idx_wdow = 0, 0

    while True:
        if idx_item == len(item_matches): break
        if idx_wdow == len(window_matches): break
        item_match, window_match = item_matches[idx_item], window_matches[idx_wdow]
        if item_match[0] < window_match[0]:
            unified_matches.append(item_match)
            idx_item += 1
        elif item_match[0] == window_match[0]:
            unified_matches.append(item_match)
            idx_item += 1
            idx_wdow += 1
        else: # item_match[0] > window_match[0]
            unified_matches.append(window_match)
            idx_wdow += 1

    if idx_item == len(item_matches) and idx_wdow < len(window_matches):
        unified_matches.extend(window_matches[idx_wdow:])
    elif idx_item < len(item_matches) and idx_wdow == len(window_matches):
        unified_matches.extend(item_matches[idx_item:])

    return unified_matches


def date_from_pattern(date_ptn):
    """Given a date pattern, attempts to parse it and return a DatePtn tuple.

    The following date patterns will be recognised and parsed.
    YYYY-MM-DD -> (year=YYYY, month=MM, day=DD)
    YYYY-MM    -> (year=YYYY, month=MM)
    YYYY-SN    -> (year=YYYY, season=SN, months=<list based on season>)
    YYYY       -> (year=YYYY)
    """
    match1 = YMD_MATCH.match(date_ptn)
    if match1:
        m = match1.groupdict()
        return DEFAULT_DATEPTN._replace(**m)

    match2 = YM_MATCH.match(date_ptn)
    if match2:
        m = match2.groupdict()
        return DEFAULT_DATEPTN._replace(**m)

    match3 = YS_MATCH.match(date_ptn)
    if match3:
        m = match3.groupdict()
        return DEFAULT_DATEPTN._replace(year=m['year'],
                                        ssn=m['season'],
                                        months=months_from_season(m['season']))

    match4 = YR_MATCH.match(date_ptn)
    if match4:
        m = match4.groupdict()
        return DEFAULT_DATEPTN._replace(**m)

    return None


def months_from_season(season):
    return {
        'SP': ['03', '04', '05'],
        'SU': ['06', '07', '08'],
        'AU': ['09', '10', '11'],
        'WI': ['12', '01', '02']
    }[season]


def events_from_year_soup(soup, month):
    events = []

    t = soup.find(id=month)
    found = t.parent
    while found.name != 'ul':
        try:
            found = found.next_sibling
        except AttributeError as e:
            logging.info('Could not find ul')
            logging.debug(soup, month)
            return events

    bullets = found.children
    for bullet in bullets:
        if bullet == "\n": continue
        ul = bullet.find('ul')
        if ul is None:
            events.append(events_from_bullet_soup(bullet))
        else:
            month_day = next(bullet.children) #eg. <a> for March 13
            for sub_bullet in ul.children:
                if sub_bullet == "\n": continue
                event = events_from_bullet_soup(sub_bullet)
                event['text'] = '{} - {}'.format(month_day.get_text(), event['text'])
                events.append(event)

    return events


def events_from_bullet_soup(bullet):
    ret = {}
    ret['text'] = bullet.get_text()

    links = []
    for tag in bullet.select('a'):
        links.append(tag.get('href'))
    ret['links'] = links
    return ret


def events_from_date_soup(soup, year):
    t = soup.find(id="Events")
    bullets_soup = t.parent.next_sibling.next_sibling
    # Find the section of the page with a link to the specific year
    bullet = bullets_soup.select('a[href="/wiki/{}"]'.format(year))[0].parent;
    return events_from_bullet_soup(bullet)



# testing
def test1():
    year = "2011"
    wiki_url = "https://en.wikipedia.org/wiki/" + year
    html = requests.get(wiki_url).text

    soup = BeautifulSoup(html, 'html.parser')
    month = "March"
    return events_from_year_soup(soup, month)


def test2():
    wiki_url = "https://en.wikipedia.org/wiki/March_15"
    html = requests.get(wiki_url).text

    soup = BeautifulSoup(html, 'html.parser')
    year = "2011"
    return events_from_date_soup(soup, year)


def test_date_from_pattern():
    patterns = ["2001-03-26", "1995-09", "2011-SU", "2001"]
    return [date_from_pattern(p) for p in patterns]


def test_wikitexts_from_date():
    date = date_from_pattern("2011-AU")
    return wikitexts_from_date(date)

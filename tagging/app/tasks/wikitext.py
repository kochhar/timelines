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

import en_core_web_sm

from app import app, celery, db, lib
from app.lib import wikipedia as wp


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
def wikipedia_events_from_dates(video_extract):
    """Fetches wikipedia event descriptions given dates."""
    events = video_extract['events']

    for i, sent in enumerate(events):
        for j, event in enumerate(sent):
            date = date_from_pattern(event['date'])
            if not date or not date.year:
                event['wiki'] = []
                continue

            logging.info('Sent {}, candidate event {} on date {}'.format(i, j, date))
            event['wiki'] = wikitexts_from_date(date)

    return video_extract


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
def event_entities_from_wikitext(video_extract):
    """Runs named entity extraction over the wiki text for each extracted event.
    Extracted entities are saved in the wiki object for each event."""
    events = video_extract['events']

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

    return video_extract


@celery.task
def match_event_via_entities(video_extract):
    """Atempts to match an extracted event with the candidate wikipedia
    events for the date."""
    events = video_extract['events']

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
                    entity_filter=entity_filter)
                date['match'] = match
                date['scores'] = scores
            except KeyError as ke:
                import pdb; pdb.set_trace()

    return video_extract


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


@celery.task
def resolve_match_link_topics(video_extract):
    """Given a video extract, processes all the matched events to augment
    their links with wikibase_ids."""
    events = video_extract['events']

    for candidate_list in events:
        if not candidate_list: continue
        for date in candidate_list:
            match = date.get('match')
            if not match: continue
            match['wptopics'] = resolve_links_to_topics(match['links'])

    return video_extract


def resolve_links_to_topics(links):
    # Preseve the hrefs which match the pattern '/wiki/Title'
    wp_links = filter(lambda l: l.startswith('/wiki'), links)
    wp_title_matcher = re.compile('/wiki/(.*)$')
    links_and_titles = list(map(lambda m: (m.group(0), m.group(1)),
                                filter(lambda m: m is not None,
                                       map(wp_title_matcher.match, wp_links))))

    title_wbid_map = dict(wp.wbid_from_titles(*[t for (l, t) in links_and_titles]))
    # Xform (l, title) -> (l, title, id) via (title -> id)
    return [{'href': l, 'title': t, 'wbid': title_wbid_map[t]} for (l, t) in links_and_titles]


@celery.task
def score_related_events(video_extract):
    """Scores the related events from a video's matched events for relevance.

    Examines video_extract['events'][i][j]['match']
    Match must have:
    - wptopics
    - wptopics_sel: { topic }
    - wptopics_rel: { 'part_of': [ [{ topic }], [{ topic }] ],
                      'category': [ { topic }, { topic } ]
                    }
    """
    transcript = video_extract['captions']['sents']
    events = video_extract['events']

    all_wprelated = []
    for candidate_list in events:
        if not candidate_list: continue
        for date in candidate_list:
            match = date.get('match')
            if not match: continue
            if not match.get('wptopics'): continue

            topic, related = match.get('wptopic_sel'), match.get('wptopic_rel')
            if not related:
                logging.info('No related events for %s', match.get('text'))
                continue
            if not topic:
                logging.info('No topic found for %s', match.get('text'))
                continue

            all_wprelated.append((topic, related))

    import pdb; pdb.set_trace()
    related_scores = score_events_in_relation(to=transcript, events=all_wprelated)
    video_extract['wptopics_rel'] = related_scores

    return video_extract


def score_events_in_relation(to, events):
    """Scores events in relation to a body of text.

    Params:
        to: iterable of sentences
        events: iterable of ((topic, wptopics_rel))
    """
    nlp = en_core_web_sm.load()

    scores = []
    to_nlp = nlp(''.join(to))

    for topic, wptopic_rel in events:
        related_by_partof = [t for partof in wptopic_rel['part_of'] for t in partof]
        for related in related_by_partof:
            if 'article' not in related:
                logging.info('No article present in related event %s', related)
                continue

            relevant_topic = related.copy()

            # Get article intro and replace citations
            intro = CITE_MATCH.sub('', wp.intro_from_article(wp.article_by_url(related['article'])))
            relevant_topic['score'] = to_nlp.similarity(intro)
            relevant_topic['via'] = topic
            scores.append(relevant_topic)

    return scores


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
    """Returns list of events: [{'text': '', 'links': ['']}] which occurred
    in a given month."""
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


def events_from_date_soup(soup, year):
    """Returns list of events: [{'text': '', 'links': ['']}] which occurred
    in a given year."""
    events = []
    t = soup.find(id="Events")
    bullets_soup = t.parent.next_sibling.next_sibling
    # Find the section of the page with a link to the specific year
    try:
        bullet = bullets_soup.select('a[href="/wiki/{}"]'.format(year))[0].parent;
        events.append(events_from_bullet_soup(bullet))
    except IndexError as e:
        logging.warn("Could not find bullet for year {}".format(year))

    return events


def events_from_bullet_soup(bullet):
    """Given a wikipedia event bullet soup, returns the event text and links."""
    ret = {}
    if not bullet: return ret

    ret['text'] = bullet.get_text()
    ret['links'] = [t.get('href') for t in bullet.select('a')]
    return ret


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

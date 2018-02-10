"""
wikitext.py

module containing tasks for wikitext processing
"""
from bs4 import BeautifulSoup
import collections
import logging
import re
import requests

from app import app, celery, db, lib
DatePtn = collections.namedtuple('DatePtn', 'year month months day ssn')


DEFAULT_DATEPTN = DatePtn(year=None, month=None, months=None, day=None, ssn=None)
MONTHS_BY_INDEX = {
    '01': 'January', '02': 'February', '03': 'March',
    '04': 'April', '05': 'May', '06': 'June',
    '07': 'July', '08': 'August',  '09': 'September',
    '10': 'October', '11': 'November', '12': 'December'
}
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
    events = extracted_events['events']
    logging.debug('Events: {}'.format(events))

    for i, sent in enumerate(events):
        for j, event in enumerate(sent):
            logging.info('Sent {}, candidate event {} on date {}'.format(i, j, event['date']))

            wiki_texts = wikitexts_from_date(date_from_pattern(event['date']))
            if wiki_texts is None: continue
            event['wiki'] = {'text': wiki_texts}

    return extracted_events


def wikitexts_from_date(date):
    """Given a DatePtn, returns a list of wikitext for the events on those days.
    If date_ptn is missing year, returns None"""
    if not date: return None
    if not date.year: return None

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
    events = extracted_events['events']
    logging.debug('Events {}'.format(events))

    for i, sent in enumerate(events):
        for j, event in enumerate(sent):
            if 'wiki' not in event: continue

            wiki_texts = event['wiki']['text']
            entity_and_sent = lib.nlp_over_lines_as_blob(wiki_texts, lib.entities_from_span, lib.str_from_span)
            entities, sents = zip(*list(entity_and_sent))
            event['wiki']['ents'] = entities
            event['wiki']['sents'] = sents

    return extracted_events


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
    t = soup.find(id=month)
    bullets = t.parent.next_sibling.next_sibling.children

    events = []
    for bullet in bullets:
        if bullet != "\n":
            ul = bullet.find('ul')
            if ul is None:
                events.append(events_from_bullet(bullet))
            else:
                month_day = next(bullet.children) #eg. <a> for March 13
                for sub_bullet in ul.children:
                    if sub_bullet != "\n":
                        sub_bullet.append(month_day)
                        events.append(events_from_bullet(sub_bullet))

    return events


def events_from_bullet(bullet):
    # bullet is a soup object
    return bullet.get_text()
    # ret = {}
    # ret['text'] = bullet.get_text()

    # links = []
    # for tag in bullet.select('a'):
    #     links.append(tag.get('href'))
    # ret['links'] = links
    # return ret


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

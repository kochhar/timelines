"""
utilities for interacting with wikipedia
"""
from bs4 import BeautifulSoup
import functools as ft
import json
import logging
import os.path
import requests
import urllib


EN_WIKIPEDIA_APIURL = 'https://en.wikipedia.org/w/api.php'


def wbid_from_titles(*titles):
    """Given one or more titles, fetches the wikibase id for each of  the titles.

    Returns a list of the form, [(title, wbid) ... ]
    """
    result = WPQuery().by_titles(titles, prop='pageprops', ppprop='wikibase_item')

    deredir = dict((redir['to'], redir['from']) for redir in result['query'].get('redirects', []))
    denorm = dict((norm['to'], norm['from']) for norm in result['query'].get('normalized', []))

    def orig_title(final_title):
        """Returns the original form of the title, given its denormalised form."""
        deredir_title = deredir.get(final_title, final_title)
        orig_title = denorm.get(deredir_title, deredir_title)
        return orig_title

    pages = result['query']['pages'].values()
    title_wbid_map = dict((orig_title(p['title']), # Backlink found title to the orig title
                           p.get('pageprops', {}).get('wikibase_item')) # Wikibase id if found
                          for p in pages)
    try:
        wbids = [(t, title_wbid_map[t]) for t in titles]
    except KeyError as e:
        logging.info(json.dumps(title_wbid_map, indent=2))
        logging.info(titles)
        import pdb; pdb.set_trace()

    return wbids


def article_by_title(title, fetch_strategy='url'):
    """Given a Wikipedia page title, returns the introductory text for the
    title from the English wikipedia."""
    return article_by_url(_eng_url_from_title(title), fetch_strategy)


def article_by_url(url, fetch_strategy='url'):
    """Given a Wikipedia page URL, return the introductory text for the title
    from the English wikipedia."""
    if fetch_strategy == 'url':
        fetcher = _fetch_html_from_url
    elif fetch_strategy == 'cache':
        fetcher = ft.partial(_fetch_html_from_cache,
                             cache_root='/Users/kochhar/workspace/projects/timelines/tagging/data')
    else:
        raise ValueError('Don\'t understand fetch strategy %s' % (fetch_strategy))

    return fetcher(urllib.parse.unquote(url))


def intro_from_article(html):
    """Given a wikipedia article HTML, will return the introduction of the article.

    If the article has a ToC all paragraphs before the ToC are considered the
    introduction. If the article does not have a ToC the main content is used.
    """
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.find('div', id='mw-content-text')

    # Try a few different approaches to getting the intro
    for extractor in [_intro_as_paras_before_toc, _intro_as_first_para]:
        intro = extractor(content)
        if intro: break

    return intro if intro else ''


class WikipediaAction(object):
    """A wikipedia API action."""
    def __init__(self, api_base_url=EN_WIKIPEDIA_APIURL):
        self.api_base_url = api_base_url


class WPQuery(WikipediaAction):
    """A query action on the wikipedia API."""

    def by_titles(self, titles, **kwargs):
        if isinstance(titles, str):
            titles=[titles]

        params = {
            'action': 'query',
            'format': 'json',
            'titles': '|'.join(titles),
            'redirects': 1
        }
        params.update(kwargs)

        resp = requests.post(self.api_base_url, params=params)
        return resp.json()
query = WPQuery()


def _fetch_html_from_url(url):
    """Given a wikipedia URL, fetches the HTML content for the URL."""
    return requests.get(url).text


def _fetch_html_from_cache(url, cache_root):
    """Given a wikipedia URL, fetches the HTML content from the cache."""
    if url.startswith('https://'):
        url = url[8:]
    elif url.startswith('http://'):
        url = url[7:]

    return ''.join(open(os.path.join(cache_root, url)).readlines())


def _eng_url_from_title(title):
    return "https://en.wikipedia.org/wiki/"+title


def _intro_as_paras_before_toc(content):
    """Given a content soup of a wikipedia page, returns the introduction of
    the page as all the paras before the ToC."""
    toc = content.find('div', id='toc')
    if not toc: return None

    intro_paras = reversed(toc.find_previous_siblings('p'))
    return ' '.join(p.text for p in intro_paras)


def _intro_as_first_para(content):
    """Given a content soup of a wikipedia page, returns the introduction of
    the page as the first para within the content."""
    return content.find('p').text

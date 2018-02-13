"""
utilities for interacting with wikipedia
"""
import json
import logging
import requests

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

"""
requests.py

tasks to make http requests
"""
import requests

from app import celery


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
    return serializable_requests_response(resp)


@celery.task
def send_url_payload(payload, url, headers=None):
    resp = requests.post(url, payload, headers=headers)
    return serializable_requests_response(resp)


def serializable_requests_response(resp):
    if resp.headers.get('Content-Type') == 'application/json':
        result = {'json': resp.json()}
    else:
        result = {}

    result.update(dict((f, getattr(resp, f)) for f in RESPONSE_SERIAL_FIELDS))
    # headers is an instance of CaseInsensitiveDict, convert to plain dic
    if 'headers' in result:
        result['headers'] = dict(result['headers'])
    return result

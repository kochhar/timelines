"""
module for processing API
"""
import logging
from urllib import parse

from celery import chain
from celery.result import AsyncResult
from flask import Response, jsonify
from flask_restful import abort, fields, marshal_with, Resource
from flask_restful.reqparse import RequestParser

from app import app, celery, tasks


class YoutubeInput(Resource):
    """Resource which represents an input queue for processing."""
    fields = {
        'url': fields.String,
        'video_id': fields.String,
        'task_id': fields.String,
    }

    @marshal_with(fields, envelope='in')
    def post(self):
        """Adds in a new youtube video for processing."""
        parser = RequestParser()
        parser.add_argument('url', required=True)
        args = parser.parse_args()

        logging.info('Enqueing {url:s}', args)
        # parse youtube url in the form of http://youtube.com/watch?v=<VIDEO_ID>
        # parse the extracted query to get the first available 'v' param
        parsed = parse.urlparse(args['url'])
        video_id = parse.parse_qs(parsed.query).get('v')[0]
        logging.debug('Found video_id {0}', video_id)
        if not video_id:
            msg = "Could not extract video_id (found '{0}') from {1}".format(
                video_id, args['url'])
            logging.warn(msg)
            return abort(400, message=msg)

        res = chain(
            tasks.captions.youtube_captions_from_video.s(video_id),
            tasks.captions.annotate_events_in_captions.s(video_id),
            tasks.captions.event_dates_from_timeml_annotated_captions.s(),
            tasks.wikitext.wikipedia_events_from_dates.s(),
            tasks.wikitext.event_entities_from_wikitext.s(),
            tasks.wikitext.match_event_via_entities.s(),
            tasks.wikitext.resolve_match_link_topics.s(),
            # tasks.requests.send_url_payload(app.config['WIKITEXT_PAYLOAD_DEST_URL']),
        ).apply_async()

        return {
            'url': args['url'],
            'video_id': video_id,
            'task_id': res.id
        }


class WikidataExtract(Resource):
    """Resource which represents wikidata extracts for processing."""
    fields = {
        'video_id': fields.String,
        'task_id': fields.String,
    }

    @marshal_with(fields, envelope='in')
    def post(self):
        """Adds in a new wikidata extract for relevance processing."""
        parser = RequestParser()
        parser.add_argument('extract', required=True)
        args = parser.parse_args()
        extract = args['extract']

        video_id = extract['video_id']
        logging.info('Enqueing relevance scoring for video %s', video_id)

        res = chain(
            tasks.wikitext.score_related_events.s(extract)
        ).apply_async()

        return {
            'video_id': video_id,
            'task_id': res.id
        }


class TaskResult(Resource):
    """Resource which represents the result of task enqueued."""

    def get(self, task_id):
        """Fetches the result of a task."""
        result = AsyncResult(id=task_id, app=celery)
        if result.status in ['SUCCESS', 'FAILURE']:
            try:
                response = jsonify(result.get())
            except Exception as e:
                logging.info(e)
                response = jsonify({'id': task_id, 'status': result.status, 'err': repr(e)})
        else:
            response = jsonify({'id': task_id, 'status': result.status})

        response.status_code = 200
        return response


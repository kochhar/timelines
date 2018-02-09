"""
module for processing API
"""
import logging
from urllib import parse

from celery import chain
from flask_restful import abort, fields, marshal_with, Resource
from flask_restful.reqparse import RequestParser
from app import tasks



class YoutubeInput(Resource):
    """Resource which represents an input queue for processing."""
    fields = {
        'url': fields.String,
        'video_id': fields.String,
        'task_id': fields.String,
    }

    def get(self):
        pass

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
            tasks.youtube_captions_from_video.s(video_id),
            tasks.annotate_events_in_captions.s(video_id),
            tasks.events_from_timeml_annotated_captions.s(video_id)
        ).apply_async()

        return {'url': args['url'],
                'video_id': video_id,
                'task_id': res.id}

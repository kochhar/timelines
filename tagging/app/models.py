from datetime import datetime
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.hybrid import hybrid_property
from flask_login import UserMixin

from app import db, bcrypt


class User(db.Model, UserMixin):

    ''' A user who has an account on the website. '''
    __tablename__ = 'user'

    first_name = db.Column(db.String)
    last_name = db.Column(db.String)
    phone = db.Column(db.String)
    email = db.Column(db.String, primary_key=True)
    confirmation = db.Column(db.Boolean)
    _password = db.Column(db.String)

    @property
    def full_name(self):
        return '{} {}'.format(self.first_name, self.last_name)

    @hybrid_property
    def password(self):
        return self._password

    @password.setter
    def _set_password(self, plaintext):
        self._password = bcrypt.generate_password_hash(plaintext)

    def check_password(self, plaintext):
        return bcrypt.check_password_hash(self.password, plaintext)

    def get_id(self):
        return self.email


class Video(db.Model):
    '''A video indexed for the timelines.'''
    __tablename__ = 'video'

    id = db.Column(db.Integer, primary_key=True)
    external_ids = db.Column(pg.JSONB)
    # metadata fields: views, likes, uploaded
    meta = db.Column(pg.JSONB)
    captions = db.Column(pg.JSONB)
    # events fields:
    events = db.Column(pg.JSONB)
    created_on = db.Column(db.DateTime, server_default=db.text("(now() at time zone 'utc')"))
    updated_on = db.Column(db.DateTime, onupdate=datetime.utcnow())

    __table_args__ = (
        db.Index('ix_video_external_id', db.text("external_ids")),
        db.Index('ix_video_metadata_views', db.text("meta->>views")),
        db.Index('ix_video_metadata_likes', db.text("meta->>likes")),
        db.Index('ix_video_metadata_uploaded', db.text("meta->>uploaded"))
    )

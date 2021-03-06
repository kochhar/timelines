import os
from celery import Celery
from flask import Flask
# from flask_bcrypt import Bcrypt
from flask_debugtoolbar import DebugToolbarExtension
# from flask_login import LoginManager
# from flask_mail import Mail
# from flask_migrate import Migrate
from flask_restful import Api
# from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Setup the app with the config.py file
app.config.from_object(os.environ['TIMELINES_CONFIG'])
# Setup the database
# db = SQLAlchemy(app)
# migrate = Migrate(app, db)

# Setup the password crypting
# bcrypt = Bcrypt(app)

# Setup the mail server
# mail = Mail(app)

# Setup the debug toolbar
app.config['DEBUG_TB_TEMPLATE_EDITOR_ENABLED'] = True
app.config['DEBUG_TB_PROFILER_ENABLED'] = True
toolbar = DebugToolbarExtension(app)

# App imports
# from app import admin
# from app.models import User
from app.logger_setup import logger
# from app.views import main, user, error

# app.register_blueprint(user.userbp)

# Setup the user login process
# login_manager = LoginManager()
# login_manager.init_app(app)
# login_manager.login_view = 'userbp.signin'


# @login_manager.user_loader
# def load_user(email):
#     return User.query.filter(User.email == email).first()


# Setup the celery task definitions
def make_celery(app):
    # create the celery instance and configure it
    celery = Celery(app.import_name,
                    backend=app.config['CELERY_RESULT_BACKEND'],
                    broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)

    # setup the base class for celery tasks
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        """Task class which creates an app_context before calling the task."""
        abstract = True
        def __call(self, *args, **kwargs):
            with app.app_context():
                return super(ContextTask, self).__call__(*args, **kwargs)
    celery.Task = ContextTask
    return celery


celery = make_celery(app)
from app import tasks


# Setup the API interface
from app.api import TaskResult, WikidataExtract, YoutubeInput
api = Api(app, prefix='/api/v1')
api.add_resource(YoutubeInput, '/in/yt', endpoint='yt_in')
api.add_resource(WikidataExtract, '/in/wd', endpoint='wd_in')
api.add_resource(TaskResult, '/tasks/<string:task_id>', endpoint='task_result')


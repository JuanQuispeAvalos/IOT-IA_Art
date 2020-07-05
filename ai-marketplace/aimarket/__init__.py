from pathlib import Path

from flask import Flask

import flask_uploads

# directory where the AI artist code is uploaded and stored
ARTISTS_DIR = "artists"
# directory where the AI artists place their art
ART_DIR = "art"

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=str(Path(app.instance_path) / 'aimarket.sqlite'),
        IOTA_NODE_ADDR="https://nodes.devnet.iota.org:443",
        UPLOADED_ARTISTS_DEST=str(Path(app.instance_path) / ARTISTS_DIR),
        ART_DIR=str(Path(app.instance_path) / ART_DIR),
        TIME_COST=100, # IOTAs per second
        DEFAULT_COST=1000, # IOTA cost if the running time is unknown
        WAIT_PAYMENT=10, # minutes to wait for payment before cancelling
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance and art folders exist
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config['ART_DIR']).mkdir(parents=True, exist_ok=True)

    # load the database functions
    from . import db
    db.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)

    # register the artist handling code and endpoints with flask
    from . import artist
    flask_uploads.configure_uploads(app, artist.artist_uploads)
    # set maximum file size, default is 16MB
    flask_uploads.patch_request_class(app)
    app.register_blueprint(artist.bp)
    app.add_url_rule('/', endpoint='index')

    return app

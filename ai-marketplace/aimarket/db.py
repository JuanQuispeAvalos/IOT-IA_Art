"""Handles the database functions."""

import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext

def init_app(app):
    """Initialize the app."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)


def init_db():
    """Initialize the database."""
    from . import iotautil

    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

    # create and store an iota seed when initializing the database
    iota_seed = iotautil.generate_seed()
    db.execute(
        'INSERT INTO iota (seed)'
        ' VALUES (?)',
        (iota_seed,)
    )
    db.commit()


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


def get_db():
    """Returns a valid database connection.

       Checks if a database connection already exists in the session.
       If there is an existing session, this session is returned.
       Otherwise a new connection is created and added to the session."""

    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(_=None):
    """Close the database connection."""
    db = g.pop('db', None)

    if db is not None:
        db.close()

"""
Handles functions for creating, updating, deleting AI artists.
"""

import threading
import datetime
import importlib
from pathlib import Path
import shutil
import time
import uuid
import zipfile

from flask import (
    Blueprint, flash, g, redirect, render_template,
    request, url_for, jsonify, current_app, send_from_directory
)
from werkzeug.exceptions import abort

import flask_uploads

from aimarket.auth import login_required
from aimarket.db import get_db
from aimarket.iotautil import IotaUtil

RETRIEVE_URL = 'retrieve-art'  # url used for retrieving commissioned artwork
BALANCE_CHECK_INTERVAL = 30  # seconds

artist_uploads = flask_uploads.UploadSet(
    'artists',
    extensions=('zip',),
)

bp = Blueprint('artist', __name__)


@bp.route('/')
@login_required
def index():
    """Handles index view and shows all registered AIs."""
    db = get_db()
    ais = db.execute(
        'SELECT ai.id, ai_name, genre_id, average_time,'
        ' surcharge, created, author_id, genre_name'
        ' FROM artist ai JOIN genre g ON ai.genre_id = g.id'
        ' WHERE ai.author_id = ?'
        ' ORDER BY created DESC',
        (g.user['id'],)
    ).fetchall()
    return render_template('artist/index.html', ais=ais)


@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    """Allows uploading a new AI."""
    db = get_db()
    if request.method == 'POST':
        ai_name = request.form['ai_name']
        genre = request.form['genre']
        surcharge = request.form['surcharge']
        artist = request.files['ai_code']
        error = None

        if not ai_name:
            error = 'Name is required.'
        
        if not artist:
            error = 'Artist code is required.'

        if not surcharge:
            surcharge = 0

        if error is not None:
            flash(error)
        else:
            # save the AI zip file
            filename = artist_uploads.save(artist)
            artists_dir = Path(current_app.config['UPLOADED_ARTISTS_DEST'])
            # make a unique directory for the new AI
            dir_name = str(uuid.uuid4())[:8]
            artist_dir = artists_dir / dir_name
            artist_dir.mkdir()
            # unzip the AI code into the new directory
            with zipfile.ZipFile(artists_dir / filename, 'r') as zip_ref:
                zip_ref.extractall(artist_dir)
            # find python script
            script = next(artist_dir.glob("*.py"))
            script = script.stem
            # delete unzipped folder
            (artists_dir / filename).unlink()
            # save the new AI's info
            filename = str(Path(dir_name) / script)
            db.execute(
                'INSERT INTO artist (ai_name, genre_id, author_id,'
                ' code, surcharge)'
                ' VALUES (?, ?, ?, ?, ?)',
                (ai_name, genre, g.user['id'], filename, surcharge)
            )
            db.commit()
            return redirect(url_for('artist.index'))

    genres = db.execute(
        'SELECT * FROM genre'
    ).fetchall()
    return render_template('artist/create.html', genres=genres)


def get_ai(aiid, check_author=True):
    """Returns the AI associated with aiid stored in the database.

    If check_author is true, a 403 error occurs if the author_id
    doesn't match the logged in user."""
    ai = get_db().execute(
        'SELECT ai.id, ai_name, code, surcharge, genre_id, average_time,'
        ' created, author_id, genre_name'
        ' FROM artist ai JOIN genre g ON ai.genre_id = g.id'
        ' WHERE ai.id = ?',
        (aiid,)
    ).fetchone()

    if ai is None:
        abort(404, "AI id {0} doesn't exist.".format(id))

    if check_author and ai['author_id'] != g.user['id']:
        abort(403)

    return ai


@bp.route('/<int:aiid>/update', methods=('GET', 'POST'))
@login_required
def update(aiid):
    """Allows updating a registered AI's information."""
    ai = get_ai(aiid)
    db = get_db()
    genres = db.execute(
        'SELECT * FROM genre'
    ).fetchall()

    if request.method == 'POST':
        ai_name = request.form['ai_name']
        genre = request.form['genre']
        surcharge = request.form['surcharge']
        error = None

        if not ai_name:
            error = 'AI name is required.'
        if not genre:
            error = 'Genre is required.'
        if not surcharge:
            surcharge = 0

        if error is not None:
            flash(error)
        else:
            db.execute(
                'UPDATE artist SET ai_name = ?, genre_id = ?, surcharge = ?'
                ' WHERE id = ?',
                (ai_name, genre, surcharge, aiid)
            )
            db.commit()
            return redirect(url_for('artist.index'))

    return render_template('artist/update.html', ai=ai, genres=genres)


@bp.route('/<int:aiid>/delete', methods=('POST',))
@login_required
def delete(aiid):
    """Allows deleting a registered AI."""
    ai = get_ai(aiid)
    # delete files first
    artist_path = current_app.config['UPLOADED_ARTISTS_DEST']
    code_path = Path(ai['code']).parent
    artist_path = Path(artist_path) / code_path
    if artist_path.exists():
        shutil.rmtree(artist_path)
    # delete entry in database
    db = get_db()
    db.execute('DELETE FROM artist WHERE id = ?', (aiid,))
    db.commit()
    return redirect(url_for('artist.index'))


@bp.route('/artist-list', methods=('GET',))
def artist_list():
    """Returns a list of all registered artists with associated genres
    and costs."""
    ais = get_db().execute(
        'SELECT ai.id, surcharge, average_time, genre_name'
        ' FROM artist ai JOIN genre g ON ai.genre_id = g.id'
    ).fetchall()
    response = []
    for row in ais:
        temp = dict(row)
        temp['cost'] = calc_cost(temp['average_time'], temp['surcharge'])
        # delete unnecessary information
        del temp['surcharge']
        del temp['average_time']
        response.append(temp)
    # return json response
    return jsonify(response)


def calc_cost(average_time, surcharge=0, config=None):
    """Calculates the cost of generating a piece of art."""
    if config is None:
        config = current_app.config
    if average_time is None:
        time_cost = config['DEFAULT_COST']
    else:
        time_cost = average_time * config['TIME_COST']
    cost = int(surcharge + time_cost)
    return cost


@bp.route('/<int:aiid>/request-art', methods=('GET', 'POST'))
def request_art(aiid):
    """Handle request to generate a new piece of art"""
    iota = IotaUtil()
    # generate new IOTA address specifically for this client
    addr, addr_index = iota.generate_address()
    # generate key
    key = uuid.uuid4().hex
    db = get_db()
    # insert entry into job table
    cursor = db.execute(
        'INSERT INTO job (access_key, addr_index, ai_id)'
        ' VALUES (?, ?, ?)',
        (key, addr_index, aiid)
    )
    job_id = cursor.lastrowid
    db.commit()
    # start background worker
    threading.Thread(
        target=art_generator, args=(job_id, iota, current_app.config)
    ).start()
    # compile response
    response = {
        'iota_addr': addr,
        'job_id': job_id,
        'key': key,
        'status_addr': f'/{job_id}/status',
        'retrieve_addr': f'/{job_id}/{RETRIEVE_URL}'
    }
    return jsonify(response), 202 # accepted status code


def get_job(jobid, key):
    """Returns the job associated with jobid or
       an error if the key is not valid."""
    job = get_db().execute(
        'SELECT access_key, completed, filename'
        ' FROM job WHERE id = ?',
        (jobid,)
    ).fetchone()
    if job is None:
        return abort(404) # job doesn't exist
    if key != job['access_key']:
        abort(403)
    return job


@bp.route(f'/<int:jobid>/status', methods=('GET', 'POST'))
def retrieve_status(jobid):
    """Allows retrieving the status of a job."""
    key = request.get_json()['key']
    job = get_job(jobid, key)
    response = {
        'status': "in_progress"
    }
    if job['completed'] is None:
        return jsonify(response), 409
    response['status'] = "completed"
    return jsonify(response)


@bp.route(f'/<int:jobid>/{RETRIEVE_URL}', methods=('GET', 'POST'))
def retrieve_art(jobid):
    """Allows retrieving the art from a completed job."""
    key = request.get_json()['key']
    job = get_job(jobid, key)
    if job['completed'] is None:
        return abort(409)
    # if the job is completed and the key is correct, serve the file
    return send_from_directory(
        directory=current_app.config['ART_DIR'], filename=job['filename']
    )


def art_generator(job_id, iota, config):
    """Background process which generates a piece of art
       based on job configuration.
       
       Background process begins by polling IOTA address for required balance.
       If not found within the number of minutes specified by the 
       config['WAIT_PAYMENT'], then cancel the request.
       Otherwise, if the payment is found at the address, generate the art
       and save it in the correct location."""

    import sqlite3
    # open a new connection for this thread
    db = sqlite3.connect(
        config['DATABASE'],
        detect_types=sqlite3.PARSE_DECLTYPES
    )
    db.row_factory = sqlite3.Row
    # get the job info
    info = db.execute(
        'SELECT addr_index, code, surcharge, average_time'
        ' FROM job j JOIN artist ai ON j.ai_id = ai.id'
        ' WHERE j.id = ?',
        (job_id,)
    ).fetchone()
    addr_index = info['addr_index']
    required_balance = calc_cost(
        info['average_time'], info['surcharge'], config
    )
    balance = 0
    wait_time = config['WAIT_PAYMENT']
    wait_time = datetime.timedelta(minutes=wait_time)
    start_time = datetime.datetime.now()

    # start polling to see if the required payment has been deposited
    while balance < required_balance \
            and datetime.datetime.now() < start_time + wait_time:
        time.sleep(BALANCE_CHECK_INTERVAL)
        # check balance
        balance = iota.get_balance(addr_index)
    if balance < required_balance:
        # job timed out - delete it
        db.execute('DELETE FROM job WHERE id = ?', (job_id,))
        db.commit()
    else:
        # load and import the AI's code
        code = '.'.join(Path(info['code']).parts)
        root_dir = Path(__file__).absolute().parent.parent
        code_dir = Path(config['UPLOADED_ARTISTS_DEST'])
        code_dir = code_dir.relative_to(root_dir)
        code_dir = '.'.join(code_dir.parts)
        module_name = code_dir + "." + code
        code_mod = importlib.import_module(module_name)
        store_path = Path(config['ART_DIR'])  # where to store the artwork
        # run the AI
        filename = code_mod.run(store_path)
        # save the job completion time and filename
        db.execute(
            'UPDATE job SET completed = ?, filename = ?'
            ' WHERE id = ?',
            (datetime.datetime.now(), filename, job_id)
        )
        db.commit()

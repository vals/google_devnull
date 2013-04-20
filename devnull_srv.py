#!/usr/bin/env python
"""\
Hello Redis Tasks
A quick example of how to use Redis as a task queue.
"""

import logging.config
import os
from functools import update_wrapper
from redis import Redis, ConnectionError
from flask import Flask, render_template, abort, request, session, abort, redirect, url_for, flash, jsonify, g
from tasks import *
import time
import json

import requests

SESSION = "69238bac-7636-45ee-8a6d-53ff31b50d08"

redis = Redis()

# Flask application
app = Flask(__name__)
app.config['DEBUG'] = __name__ == '__main__'
app.config.from_pyfile('config.py')
if 'LOGGING' in app.config:
    logging.config.dictConfig(app.config['LOGGING'])

base = "https://genericwitticism.com:8000/api3/"


## Ratelimiting code

class RateLimit(object):
    expiration_window = 10

    def __init__(self, key_prefix, limit, per, send_x_headers):
        self.reset = (int(time.time()) // per) * per + per
        self.key = key_prefix + str(self.reset)
        self.limit = limit
        self.per = per
        self.send_x_headers = send_x_headers
        p = redis.pipeline()
        p.incr(self.key)
        p.expireat(self.key, self.reset + self.expiration_window)
        self.current = min(p.execute()[0], limit)

    remaining = property(lambda x: x.limit - x.current)
    over_limit = property(lambda x: x.current >= x.limit)


def get_view_rate_limit():
    return getattr(g, '_view_rate_limit', None)


def on_over_limit(limit):
    return 'You hit the rate limit', 400


def ratelimit(limit, per=300, send_x_headers=True,
              over_limit=on_over_limit,
              scope_func=lambda: request.remote_addr,
              key_func=lambda: request.endpoint):
    def decorator(f):
        def rate_limited(*args, **kwargs):
            key = 'rate-limit/%s/%s/' % (key_func(), scope_func())
            rlimit = RateLimit(key, limit, per, send_x_headers)
            g._view_rate_limit = rlimit
            if over_limit is not None and rlimit.over_limit:
                return over_limit(rlimit)
            return f(*args, **kwargs)
        return update_wrapper(rate_limited, f)
    return decorator


def talk(param):
    url = base + "?" + "&".join(["=".join([k, v]) for k, v in param.iteritems()])
    return requests.get(url, verify=False, config={'encode_uri': False})


# Views
@app.route('/')
def index():
    if 'delete' in request.args:
        param = {'session': SESSION, 'command': 'deletecharacter', 'arg': request.args['delete']}
        talk(param)

    param = {"session": SESSION, "command": "getparty"}
    r = requests.get(base, params=param, verify=False)
    data = r.json
    print(data)

    character_ids = data["characters"]

    characters = []
    for char_id in character_ids:
        param["command"] = "getcharacter"
        param["arg"] = char_id
        r = requests.get(base, params=param, verify=False)
        characters.append(r.json)

    return render_template('index.html', characters=characters)


@app.route('/create', methods=['POST', 'GET'])
def create():
    if request.method == 'POST':
        df = {k: v[0] for k, v in dict(request.form).iteritems()}
        del df["my-form"]
        character = json.dumps(df).replace(' ', '')

        params = {"session": SESSION, "command": "createcharacter"}
        params["arg"] = character
        print(params)
        r = talk(params)
        print(r.url)
        print(r.content)

        return render_template('create.html')

    else:
        return render_template('create.html')


@app.route('/api')
@ratelimit(limit=10, per=1)
def devnull_api():
    """Grabs the args from the URL, starts the task, then redirects to show progress."""
    task = get.delay(base, params=request.args, verify=False)
    print get_view_rate_limit().remaining
    while(True):
        rv = task.return_value
        if rv:
            return rv


# Errors
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', message='Not Found', description='The requested URL was not found on the server.'), 404


@app.errorhandler(ConnectionError)
def page_not_found(e):
    debug_description = "<strong>redis-server</strong> is"
    production_description = "both <strong>redis-server</strong> and <strong>worker.py</strong> are"
    description = "Check to make sure that %s running." % (debug_description if app.debug else production_description)
    return render_template('error.html', message='Coult not connect to the task queue', description=description), 500

# Run dev server
if __name__ == '__main__':
    # Run both the task queue
    # TODO: When Flask version 0.8, refactor using the new app.before_first_request()
    debug = app.config.get('DEBUG', True)
    use_reloader = app.config.get('DEBUG', True)
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not use_reloader:
        from worker import TaskWorker
        worker = TaskWorker(app, debug=debug)
        worker.reset()
        worker.start()
    app.run(host=app.config.get('HOST', 'localhost'), port=app.config.get('PORT', 5000), debug=debug, use_reloader=use_reloader)

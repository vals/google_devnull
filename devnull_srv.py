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
import requests
import time

redis = Redis()

# Flask application
app = Flask(__name__)
app.config['DEBUG'] = __name__ == '__main__'
app.config.from_pyfile('config.py')
if 'LOGGING' in app.config:
    logging.config.dictConfig(app.config['LOGGING'])

base = "https://genericwitticism.com:8000/api3/"
params={"session": "229ec45e-ab2a-40df-b1ad-a2cb8e9f4dda"}

# http://localhost:8001/api?session=229ec45e-ab2a-40df-b1ad-a2cb8e9f4dda&command=getparty

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



# Views
@app.route('/')
def index():
    return render_template('index.html')


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

@app.route('/progress')
def add_progress():
    """Shows the progress of the current task or redirect home."""
    task_id = request.args.get('tid')
    return render_template('progress.html', task_id=task_id) if task_id else redirect('/')


@app.route('/poll')
def add_poll():
    """Called by the progress page using AJAX to check whether the task is complete."""
    task_id = request.args.get('tid')
    try:
        task = add.get_task(task_id)
    except ConnectionError:
        # Return the error message as an HTTP 500 error
        return 'Coult not connect to the task queue. Check to make sure that <strong>redis-server</strong> is running and try again.', 500
    ready = task.return_value is not None if task else None
    return jsonify(ready=ready)


@app.route('/results')
def add_results():
    """When poll_task indicates the task is done, the progress page redirects here using JavaScript."""
    task_id = request.args.get('tid')
    task = add.get_task(task_id)
    if not task:
        return redirect('/')
    result = task.return_value
    if not result:
        return redirect('/progress?tid=' + task_id)
    task.delete()
    # Redis can also be used to cache results
    return render_template('results.html', value=result)


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

#!/usr/bin/env python3

from gevent import monkey; monkey.patch_all()  # Enable asynchronous behavior
from gevent import event
from bottle import Bottle, request, response, route, run, static_file, template
import bottle
from collections import Counter
from datetime import datetime
from functools import wraps
import gevent
import json
import logging
import os
import random
import serial
import string
import sys
import time

my_open = open

logger = logging.getLogger("app:"+__name__)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

shutdown_updated = event.Event()
start_updated = event.Event()
next_answer_updated = event.Event()

# Sends the result of fn_content when update_event is set, or every "timeout" seconds.
# def stream_content(update_event, fn_content, timeout=None):
def stream_content(update_event, *content, timeout=None):
    response.content_type = 'text/event-stream'
    response.cache_control = 'no-cache'

    while True:
        flag_set = update_event.wait(timeout=timeout)
        if flag_set:
            update_event.clear()
        else:
            logger.info("TIMED OUT! retransmitting...")
        print(f"content: {str(content)}")
        content_json = json.dumps(content)
        logger.info(f"stream_content: {content_json}")
        yield f"data: {content_json}\n\n"

@route("/start")
def user_requested_start():
    start_updated.set()

@route("/push_start")
def push_start():
    print(f"pushing start...")
    yield from stream_content(start_updated)

shutdown_now = [False]
@route("/push_shutdown")
def push_shutdown():
    yield from stream_content(shutdown_updated, shutdown_now)

@route('/next_answer')
def next_answer():
    print('next answer requested')
    next_answer_updated.set()

@route("/push_next_answer")
def push_next_answer():
    yield from stream_content(next_answer_updated)

@route('/shutdown')
def shutdown():
    global shutdown_now
    shutdown_now[0] = True
    print("Shutting down...")
    shutdown_updated.set()

def init():
    global all_words
    with open("./allwords.txt", 'r') as f:
      lines = f.readlines()

if __name__ == '__main__':
    # logger.setLevel(logging.DEBUG)

    init()
    if len(sys.argv) > 1:
        random.seed(0)
    run(host='0.0.0.0', port=8080, server='gevent', debug=True, quiet=True)

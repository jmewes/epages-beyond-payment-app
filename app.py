# -*- coding: utf-8 -*-

"""
Author: Oliver Zscheyge
Description:
    Web app that generates beautiful order documents for ePages Beyond shops.
"""

import os
import logging
import random
from urllib.parse import urlparse, unquote

from flask import Flask, render_template, request, Response, abort, escape, jsonify
from app_installations import AppInstallations, PostgresAppInstallations

app = Flask(__name__)

APP_INSTALLATIONS = None
DEFAULT_HOSTNAME = ''
LOGGER = logging.getLogger("app")

@app.route('/')
def root():
    if DEFAULT_HOSTNAME != '':
        return render_template('index.html', installed=True, hostname=DEFAULT_HOSTNAME)
    return render_template('index.html', installed=False)


@app.route('/<hostname>')
def root_hostname(hostname):
    return render_template('index.html', installed=True, hostname=hostname)

@app.route('/callback')
def callback():
    args = request.args
    return_url = args.get("return_url")
    access_token_url = args.get("access_token_url")
    api_url = args.get("api_url")
    code = args.get("code")
    signature = unquote(args.get("signature"))

    APP_INSTALLATIONS.retrieve_token_from_auth_code(api_url, code, access_token_url, signature)

    return render_template('callback_result.html', return_url=return_url)

@app.route('/merchants/<shop_id>')
def merchant_account_status(shop_id):
    print("Serving always ready merchant account status")
    return jsonify({
        "ready" : True,
        "details" : {
            "primaryEmail" : "a@b.c"
        }
    })

@app.route('/payments', methods=['POST'])
def create_payment():
    print("Creating payment")
    return jsonify({
        "paymentNote" : "Please transfer the money using the reference %s to the account %s" % (generate_id(), generate_id()),
    })

@app.route('/payments/<payment_id>/capture', methods=['POST'])
def capture_payment(payment_id):
    print("Capturing payment %s" % payment_id)
    return jsonify({
        "paymentStatus" : "CAPTURED",
    })

def generate_id():
    return ''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))

@app.before_request
def limit_open_proxy_requests():
    """Security measure to prevent:
    http://serverfault.com/questions/530867/baidu-in-nginx-access-log
    http://security.stackexchange.com/questions/41078/url-from-another-domain-in-my-access-log
    http://serverfault.com/questions/115827/why-does-apache-log-requests-to-get-http-www-google-com-with-code-200
    http://stackoverflow.com/questions/22251038/how-to-limit-flask-dev-server-to-only-one-visiting-ip-address
    """
    if not is_allowed_request():
        print("Someone is messing with us:")
        print(request.url_root)
        print(request)
        abort(403)

def is_allowed_request():
    url = request.url_root
    return '.herokuapp.com' in url or \
           '.ngrok.io' in url or \
           'localhost:8080' in url or \
           '127.0.0' in url or \
           '0.0.0.0:80' in url

def get_installation(hostname):
    installation = APP_INSTALLATIONS.get_installation(hostname)
    if not installation:
        raise ShopNotKnown(hostname)
    return installation

@app.errorhandler(404)
def page_not_found(e):
    return '<h1>404 File Not Found! :(</h1>', 404

class ShopNotKnown(Exception):
    def __init__(self, hostname):
        super()
        self.hostname = hostname

@app.errorhandler(ShopNotKnown)
def shop_not_known(e):
    return render_template('index.html', installed=False, error_message="App not installed for the requested shop with hostname %s" % e.hostname)

@app.errorhandler(Exception)
def all_exception_handler(error):
    LOGGER.exception(error)
    return 'Error', 500

def init():
    global APP_INSTALLATIONS
    global DEFAULT_HOSTNAME

    CLIENT_ID = os.environ.get('CLIENT_ID', '')
    CLIENT_SECRET = os.environ.get('CLIENT_SECRET', '')
    API_URL = os.environ.get('API_URL', '')
    if API_URL != '': # private app mode - we are operating in a single shop and can store the token in memory
        print("Initialize in-memory AppInstallations")
        APP_INSTALLATIONS = AppInstallations(CLIENT_ID, CLIENT_SECRET)
        DEFAULT_HOSTNAME = urlparse(API_URL).hostname
        APP_INSTALLATIONS.retrieve_token_from_client_credentials(API_URL)
    else: # official app mode - we can handle multiple installations for multiple shops and store data about app installation in postgres
        print("Initialize PostgresAppInstallations")
        APP_INSTALLATIONS = PostgresAppInstallations(os.environ.get('DATABASE_URL'), CLIENT_ID, CLIENT_SECRET)
        APP_INSTALLATIONS.create_schema()

init()
if __name__ == '__main__':
    if os.environ.get('RUNNING_IN_DOCKER', '') != '':
        app.run(host='0.0.0.0', port=8080, threaded=True)
    else:
        app.run()

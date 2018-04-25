#!/usr/bin/env python3
import traceback
import requests
from urllib.parse import urljoin

from flask import Flask, request

TOKEN_HEADER = 'X-Centricient-Hook-Token'

class SampleBot(object):
    def __init__(self, site, username, appId, appSecret):
        print('Created bot for {}'.format(site))
        self.site = site
        self.username = username
        self.s = requests.Session()
        self.s.auth = (appId, appSecret)

    def pong(self, healthy=True):
        self.s.post(urljoin(self.site, 'api/v1/agent-hooks/pong'), json={'healthy':healthy})

    def acknowledge_conversation_update(self, update):
        cid  = update['state']['id']
        data = {'stateId': update['stateId']}
        self.s.post(urljoin(self.site, 'api/v1/messaging/conversations/{}/acknowledge'.format(cid)), json=data)

    def send_message(self, cid, msg):
        data = {'text': msg}
        self.s.post(urljoin(self.site, 'api/v1/messaging/conversations/{}/send-message'.format(cid)), json=data)

    def accept_invitation(self, cid):
        self.s.post(urljoin(self.site, 'api/v1/messaging/conversations/{}/accept'.format(cid)))

    def send_to_queue(self, cid, queue):
        data = {'targetQueue': queue}
        self.s.post(urljoin(self.site, 'api/v1/messaging/conversations/{}/send-to-queue'.format(cid)), json=data)

    def mark_closed(self, cid):
        self.s.post(urljoin(self.site, 'api/v1/messaging/conversations/{}/close'.format(cid)))

    def handle(self, event_type, data):
        if event_type == 'conversation-update':
            self.handle_conversation_update(data)

    def handle_conversation_update(self, update):
        conversation = update['state']

        hint = next((h['hint'] for h in update['hints']), None)
        if hint == 'invitation-timer-active':
            self.accept_invitation(conversation['id'])
        elif hint == 'response-timer-active':
            self.handle_responding_to_customer(conversation)

    def handle_responding_to_customer(self, conversation):
        cid = conversation['id']

        last_customer_message = next(msg for msg in reversed(conversation['messages']) if msg['fromCustomer'])['text']

        if last_customer_message.lower() == 'requeue':
            self.send_to_queue(cid, 'default')
        elif last_customer_message.lower() in ['goodbye', 'end', 'close', 'cya', 'bye']:
            self.mark_closed(cid)
        else:
            self.send_message(cid, last_customer_message.upper())

def create_app(config='config.py'):
    app = Flask(__name__)
    app.config.from_pyfile(config)
    bot = SampleBot(**app.config['BOT'])

    @app.route('/react', methods=['post'])
    def react():
        if app.config.get('HOOK_TOKEN') and app.config.get('HOOK_TOKEN') != request.headers.get(TOKEN_HEADER):
            return 'Invalid hook token', 403
        try:
            if request.json['ping']:
                bot.pong()

            for update in request.json['conversationUpdates']:
                bot.handle('conversation-update', update)
                bot.acknowledge_conversation_update(update)
        except Exception:
            traceback.print_exc()
        return '', 204

    @app.route('/ping')
    def ping():
        return 'pong'

    return app

if __name__=='__main__':
    app = create_app()
    app.run(port=9000, debug=True)
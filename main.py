#!/usr/bin/env python
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import xmpp
from google.appengine.api import mail
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from uuid import uuid4
from email.utils import *
from datetime import *
import re
import logging
import os

class Ping(db.Model):
    uuid = db.StringProperty()
    name = db.StringProperty()
    date_sent = db.DateTimeProperty()
    date_recv = db.DateTimeProperty()

def stats_for(service, count = 1000):
    q = Ping.all()
    q.filter("date_sent >", datetime.now() - timedelta(days=1))
    q.filter("name =", service)
    q.order("-date_sent")

    values = []
    for test in q.fetch(count):
        if test.date_recv != None:
            values.append((test.date_recv - test.date_sent).seconds)
        else:
            values.append((datetime.now() - test.date_sent).seconds)
    values.reverse()
    return values

def handle_response(body):
    uuid_search = re.search('\((.*)\)', body)
    if uuid_search == None: return
    uuid = uuid_search.group(1)
    ping = db.Query(Ping).filter('uuid = ', uuid).get()
    if ping == None: return
    ping.date_recv = datetime.now()
    ping.put()

class XMPPHandler(webapp.RequestHandler):
    def post(self):
        message = xmpp.Message(self.request.POST)
        sender = message.sender.split('/')[0]
        if sender == 'geochat@instedd.org':
            handle_response(message.body)

class MailHandler(InboundMailHandler):
    def receive(self, mail_message):
        sender = parseaddr(mail_message.sender)[1]
        if sender == 'geochat@instedd.org':
            handle_response(mail_message.body.decode())

class PingGeoChatXMPP(webapp.RequestHandler):
    def get(self):
        id = str(uuid4())
        xmpp.send_message('geochat@instedd.org', '.ping %s' % id)
        ping = Ping()
        ping.uuid = id
        ping.name = 'GeoChat (XMPP)'
        ping.date_sent = datetime.now()
        ping.put()

class PingGeoChatMail(webapp.RequestHandler):
    def get(self):
        id = str(uuid4())
        mail.send_mail(sender='test@insteddstatus.appspotmail.com',
                       to='geochat@instedd.org',
                       subject='Test Ping',
                       body='.ping %s' % id)
        ping = Ping()
        ping.uuid = id
        ping.name = 'GeoChat (Mail)'
        ping.date_sent = datetime.now()
        ping.put()

class Alert(webapp.RequestHandler):
    def get(self):
        # for stat in ['GeoChat (XMPP)', 'GeoChat (Mail)']:
        for stat in ['GeoChat (XMPP)']:
            stats = stats_for(stat, 2)
            if stats[0] > 60 and stats[1] > 60:
                mail.send_mail(sender='test@insteddstatus.appspotmail.com',
                               to='jwajnerman@manas.com.ar',
                               subject='Found huge delay in service: %s' % stat,
                               body='Found huge delay in service: %s' % stat)

class MainHandler(webapp.RequestHandler):
    def get(self):
        template_values = {
            'xmpp': ','.join([str(x) for x in stats_for('GeoChat (XMPP)')]),
            'mail': ','.join([str(x) for x in stats_for('GeoChat (Mail)')])
        }
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))



def main():
    application = webapp.WSGIApplication([('/', MainHandler),
                                          ('/tasks/ping_geochat_xmpp', PingGeoChatXMPP),
                                          ('/tasks/ping_geochat_mail', PingGeoChatMail),
                                          ('/tasks/alert', Alert),
                                          ('/_ah/xmpp/message/chat/', XMPPHandler),
                                          ('/_ah/mail/.+', MailHandler)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()

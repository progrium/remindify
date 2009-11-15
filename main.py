#!/usr/bin/env python

import wsgiref.handlers

from google.appengine.api.labs import taskqueue
from google.appengine.ext import webapp
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import urlfetch
from google.appengine.api import mail
from datetime import datetime
import urllib, hashlib
from dateutil import parser
import key

def notify(user, text, title, link=None):
    params = {'text':text,'title':title, 'icon': 'http://www.remindify.com/favicon.ico'}
    if link:
        params['link'] = link
    urlfetch.fetch('http://api.notify.io/v1/notify/%s?api_key=%s' % (hashlib.md5(user.email()).hexdigest(), key.api_key), method='POST', payload=urllib.urlencode(params))


def parse_time(tz, text):
    response = urlfetch.fetch('http://www.timeapi.org/%s/%s' % (tz.lower(), urllib.quote(text)))
    if response.status_code == 200:
        return response.content

class Reminder(db.Model):
    user = db.UserProperty(auto_current_user_add=True)
    raw = db.StringProperty(required=True)
    text = db.StringProperty()
    scheduled_raw = db.StringProperty()
    scheduled = db.DateTimeProperty()
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)
    
    def __init__(self, *args, **kwargs):
        if 'parse' in kwargs:
            kwargs['text'], kwargs['scheduled_raw'] = self.parse(kwargs['parse'], kwargs['timezone'])
            kwargs['scheduled'] = parser.parse(kwargs['scheduled_raw'])
            kwargs['raw'] = kwargs['parse']
        super(Reminder, self).__init__(*args, **kwargs)
    
    def scheduled_local(self):
        return parser.parse(self.scheduled_raw)
    
    def parse(self, raw, timezone):
        ats = raw.split(' at ')
        if len(ats) == 2:
            return (ats[0], parse_time(timezone, 'at %s' % ats[1]))
        ins = raw.split(' in ')
        if len(ins) == 2:
            return (ins[0], parse_time(timezone, 'in %s' % ins[1]))
        return raw, None
        

class MainHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url("/")
            reminders = Reminder.all().filter('user =', user).fetch(1000)
        else:
            login_url = users.create_login_url('/')
        self.response.out.write(template.render('main.html', locals()))
    
    def post(self):
        user = users.get_current_user()
        if self.request.get('id'):
            reminder = Reminder.get_by_id(int(self.request.get('id')))
            if reminder.user == user:
                reminder.delete()
        else:
            reminder = Reminder(parse=self.request.get('raw'), timezone=self.request.get('tz'))
            reminder.put()
            notify(user, str(reminder.scheduled_local()), "Reminder Scheduled")
        self.redirect('/')
        
class CheckHandler(webapp.RequestHandler):
    def get(self):
        reminders = Reminder.all().filter('scheduled <=', datetime.now())
        for reminder in reminders:
            notify(reminder.user, reminder.text, "Reminder")
            reminder.delete()
        self.response.out.write("ok")

def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler), 
        ('/check', CheckHandler),
        ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
    main()


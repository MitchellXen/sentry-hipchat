"""
sentry_hipchat.models
~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011 by Linovia, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from django import forms
from django.conf import settings
from django.utils.html import escape

from sentry.plugins.bases.notify import NotifyPlugin

import sentry_hipchat

import urllib
import urllib2
import json
import logging


COLORS = {
    'ALERT': 'red',
    'ERROR': 'red',
    'WARNING': 'yellow',
    'INFO': 'green',
    'DEBUG': 'purple',
}

API_ENDPOINT = 'https://api.hipchat.com/v2/room/%s/notification'

class HipchatOptionsForm(forms.Form):
    token = forms.CharField(help_text="Your hipchat API v2 token.")
    room = forms.CharField(help_text="Room name or ID.")
    notify = forms.BooleanField(help_text='Notify message in chat window.', required=False)
    include_project_name = forms.BooleanField(help_text='Include project name in message.', required=False)
    endpoint = forms.CharField(help_text="Custom API endpoint to send notifications to.", required=False,
                               widget=forms.TextInput(attrs={'placeholder': API_ENDPOINT}))


class HipchatMessage(NotifyPlugin):
    author = 'Xavier Ordoquy, Mitchell Klijnstra'
    author_url = 'https://github.com/linovia/sentry-hipchat'
    version = sentry_hipchat.VERSION
    description = "Event notification to Hipchat."
    resource_links = [
        ('Bug Tracker', 'https://github.com/linovia/sentry-hipchat/issues'),
        ('Source', 'https://github.com/linovia/sentry-hipchat'),
    ]
    slug = 'hipchat'
    title = 'Hipchat'
    conf_title = title
    conf_key = 'hipchat'
    project_conf_form = HipchatOptionsForm
    timeout = getattr(settings, 'SENTRY_HIPCHAT_TIMEOUT', 3)

    def is_configured(self, project):
        return all((self.get_option(k, project) for k in ('room', 'token')))

    def on_alert(self, alert, **kwargs):
        project = alert.project
        token = self.get_option('token', project)
        room = self.get_option('room', project)
        notify = self.get_option('notify', project) or False
        include_project_name = self.get_option('include_project_name', project) or False
        endpoint = self.get_option('endpoint', project) or API_ENDPOINT

        if token and room:
            self.send_payload(
                endpoint=endpoint,
                token=token,
                room=room,
                message='[ALERT]%(project_name)s %(message)s %(link)s' % {
                    'project_name': (' <strong>%s</strong>' % escape(project.name)) if include_project_name else '',
                    'message': escape(alert.message),
                    'link': alert.get_absolute_url(),
                },
                notify=notify,
                color=COLORS['ALERT'],
            )

    def notify_users(self, group, event, fail_silently=False):
        project = event.project
        token = self.get_option('token', project)
        room = self.get_option('room', project)
        notify = self.get_option('notify', project) or False
        include_project_name = self.get_option('include_project_name', project) or False
        level = group.get_level_display().upper()
        link = group.get_absolute_url()
        endpoint = self.get_option('endpoint', project) or API_ENDPOINT


        if token and room:
            self.send_payload(
                endpoint=endpoint,
                token=token,
                room=room,
                message='[%(level)s]%(project_name)s %(message)s [<a href="%(link)s">view</a>]' % {
                    'level': escape(level),
                    'project_name': (' <strong>%s</strong>' % escape(project.name)) if include_project_name else '',
                    'message': escape(event.error()),
                    'link': escape(link),
                },
                notify=notify,
                color=COLORS.get(level, 'purple'),
            )


    def send_payload(self, endpoint, token, room, message, notify, color='red'):
        get_values = {
            'auth_token': token
        }
        post_values = {
            'message': message.encode('u8'),
            'notify': bool(notify),
            'color': color,
            'message_format': 'html'
        }
        clean_endpoint = endpoint % (room.encode('u8')) + '?' + urllib.urlencode(get_values)
        request = urllib2.Request(clean_endpoint, json.dumps(post_values))
        request.add_header('Content-Type', 'application/json')
        response = urllib2.urlopen(request, timeout=self.timeout)
        http_code = response.getcode()

        if 401 == http_code:
            logger = logging.getLogger('sentry.plugins.hipchat')
            logger.error('Security token not accepted for supplied room ID')
        if 204 != http_code:
            logger = logging.getLogger('sentry.plugins.hipchat')
            logger.error('Event could not be sent to hipchat')

#
#
# Copyright 2019-2020 CSS
#
# This software is unpublished work which is proprietary to CSS.
# Any distribution is strictly forbidden
#
#

""" Log events and report them to pvrcloud """

import os
import sys
import logging
import threading
import Queue
import requests
import base64
import json
from datetime import datetime, timedelta
import pytz
from time import sleep
import random
import xbmc
import xbmcaddon

LIB_RESOURCES_PATH = xbmc.translatePath(os.path.join(xbmcaddon.Addon().getAddonInfo('path').decode('utf-8'), 'resources'.decode('utf-8'), 'lib'.decode('utf-8')))
sys.path.append(LIB_RESOURCES_PATH)

""" Local module imports - need to be after LIB_RESOURCES_PATH """
from watchsync.logging import KodiLog
from watchsync.notifications import KodiNotifications
from watchsync.auth import AuthSession, AuthBoto3Direct, AuthSessionServerError, AuthSessionClientError
from watchsync.utils import *
import sentry_sdk


__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name').decode('utf-8')
__addonversion__ = __addon__.getAddonInfo('version').decode('utf-8')
__addonid__ = __addon__.getAddonInfo('id').decode('utf-8')
__addonpath__ = __addon__.getAddonInfo('path').decode('utf-8')
__addonprofile__ = xbmc.translatePath(__addon__.getAddonInfo('profile').decode('utf-8'))

sentry_sdk.init(
    "https://9872e16f507545fa9edcdcbf47632fe7@o425593.ingest.sentry.io/5510343",
    environment="development",
    release="{}@{}".format(__addonid__, __addonversion__)
)

log = KodiLog(__file__, __name__)


""" Configuration Variables """
_event_api_url = u'https://keq4fgzes4.execute-api.eu-west-1.amazonaws.com/conceptv1/api/event_logger'
_request_timeout = 15.0
""" End of Configuration Variables """


# Helper class to convert a item to JSON.
class MultiTypeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.strftime('%Y-%m-%dT%H:%M:%S%z')
        elif isinstance(o, timedelta):
            return float(o.total_seconds())
        return super(MultiTypeEncoder, self).default(o)


def event_worker(msg_queue, auth_session, exit_event):
    """ Submits event messages to pvrcloud

        This runs in a continuous loop until exit_event is set
    """
    bo_factor = 0
    log.debug("Starting Events Sync Thread")
    s = requests.Session()
    custom_headers = {
        'User-Agent': xbmc.getUserAgent(),
        'Authorization': None,
        'Content-Type': 'application/json'
    }

    while not exit_event.is_set():
        try:
            next_msg = msg_queue.get(True, 3.0)

            log.debug("Received event from queue with pri: {}".format(next_msg[0]))

            # PriorityQueue - filter out weighting - not used elsewhere
            next_msg = next_msg[1]
            if next_msg is None:
                # Poison pill
                break

            # Update authorization header
            custom_headers['Authorization'] = auth_session.get_authorization_header()

            r = s.post(url=_event_api_url,
                       data=json.dumps(next_msg, cls=MultiTypeEncoder, ensure_ascii=False),
                       headers=custom_headers,
                       timeout=_request_timeout)
            r.raise_for_status()

            # Reset backoff factor
            bo_factor = 0

            # Reduce load on server by pausing between messages
            exit_event.wait(1.9)

        except Queue.Empty:
            continue

        except requests.RequestException as e:
            if e.response:
                log.warning("Comms Error: {} ({})".format(e.response.text, e))
            else:
                log.warning("Comms Error: {} ({})".format("(no data received)", e))

            # Re-add message to queue.. but at the front
            msg_queue.put((50, next_msg))

            # Exponential back-off - capped at 47 secs max
            bo_secs = (2 ** bo_factor) + (random.randint(0, 1000) / 1000.0)
            bo_factor = min(10, bo_factor + 1)
            exit_event.wait(min(47, bo_secs))

        except:
            raise

    log.debug("Exiting Events Sync Thread")

class EventLogger(object):

    """
        EventLogger Class

        To be used by other modules to register events

        Note: Uses threads / queues to synchronise events with pvrcloud
    """

    def __init__(self, auth_session=None):

        self.exit_event = threading.Event()
        self.event_msg_queue = Queue.PriorityQueue()

        self.auth = auth_session

        self.sync_thread = threading.Thread(target=event_worker,
                                            name='EventLogger worker',
                                            args=(self.event_msg_queue,
                                                  self.auth,
                                                  self.exit_event))

        self.sync_thread.start()

    def new(self, type, data=None):
        """ Add new event """
        payload = {
            # In Python 3 this would be: datetime.now(timezone.utc).isoformat(timespec='seconds')
            'origin_utc_datetime': datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S%z'),
            'event': type,
        }

        # Add data if exists
        if data:
            payload['data'] = data

        # Add to queue
        self.event_msg_queue.put((100, payload))

        return True

    def stop(self):
        """ Safely close down the worker thread """
        if self.sync_thread:
            # Use both poison pill and event to close down thread
            self.exit_event.set()
            # Send poison pill
            self.event_msg_queue.put((5, None))
            # Wait for thread to finish
            self.sync_thread.join()
            # Allow function to be called multiple times
            self.sync_thread = None

    def __del__(self):
        """ Trigger safe close when this instance is about to be destroyed """
        self.stop()

if __name__ == '__main__':
    sys.exit("This module is designed to be imported. It should not be called directly")
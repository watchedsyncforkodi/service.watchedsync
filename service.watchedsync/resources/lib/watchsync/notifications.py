#
#
# Copyright 2019-2020 CSS
#
# This software is unpublished work which is proprietary to CSS.
# Any distribution is strictly forbidden
#
#

import sys
import os
import Queue
import json
import xbmc
import xbmcaddon
from datetime import datetime

LIB_RESOURCES_PATH = xbmc.translatePath(os.path.join(xbmcaddon.Addon().getAddonInfo('path').decode('utf-8'), 'resources'.decode('utf-8'), 'lib'.decode('utf-8')))
sys.path.append(LIB_RESOURCES_PATH)

""" Local module imports - need to be after LIB_RESOURCES_PATH """
from watchsync.logging import KodiLog
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

class KodiNotifications(xbmc.Monitor):

    def __init__(self, notification_queue):
        super(KodiNotifications, self).__init__()
        self.log = KodiLog(__file__, __name__)
        self.process_queue = notification_queue
        self.last_video_scan_duration = -1.0
        self.last_video_clean_duration = -1.0
        self.is_video_scanning = False
        self.last_video_scan_start_dt = None


    def onNotification(self, sender, method, data):

        if sender == "xbmc" and method == "VideoLibrary.OnScanStarted":
            self.is_video_scanning = True
            self.last_video_scan_start_dt = datetime.utcnow()

        elif sender == "xbmc" and method == "VideoLibrary.OnScanFinished":
            self.is_video_scanning = False
            if self.last_video_scan_start_dt:
                self.last_video_scan_duration = (datetime.utcnow() - self.last_video_scan_start_dt).total_seconds()
                self.last_video_scan_start_dt = None

        if sender == "xbmc" and method in ["System.OnWake", "GUI.OnScreensaverDeactivated",
                                           "GUI.OnScreensaverActivated", "VideoLibrary.OnScanFinished"]:
            # Trigger wakeup of the remote end
            msg = {
                "sender": sender,
                "method": method,
                "data": None
            }
            # Put on higher priority
            self.process_queue.put((50, msg))

        elif sender == "xbmc" and method == "VideoLibrary.OnUpdate":
            # Parse data back into dict
            parsed_data = json.loads(data, encoding='utf-8')
            # Ignore transaction updates
            if 'transaction' in parsed_data and parsed_data['transaction']:
                pass
            # Ignore newly added items
            elif 'added' in parsed_data and parsed_data['added']:
                pass
            # Bug in kodi means duplicates can be issued. Look for item attribute
            elif 'item' in parsed_data:
                # Process notification
                msg = {
                    "sender": sender,
                    "method": method,
                    "data": data
                }
                self.process_queue.put((100, msg))


class ProcessNotificationsThread(BackgroundThread):

    def __init__(self, runtime_config, runtime_config_lock, wakeup_flag, notification_queue, event_logger):
        super(ProcessNotificationsThread, self).__init__(name="ProcessNotificationsThread")

        self.rt_config = runtime_config
        self.rt_lock = runtime_config_lock
        self.wakeup_flag = wakeup_flag
        self.log = KodiLog(__file__, __name__)
        self.process_queue = notification_queue
        self.el = event_logger

        with self.rt_lock:
            self.auth_session = runtime_config['session_auth']
            self.update_poll_interval = runtime_config['update_library_poll_interval']
            self.update_queue_url = runtime_config['update_library_queue_url']


    def stop(self):
        # call from parent to stop and exit thread
        # Send poison pill
        self.process_queue.put((5, None))
        self.exit_flag.set()

    def run(self):
        # Called by calling start()
        self.log.debug("Starting thread: {}".format(threading.currentThread().getName()))

        while not self.exit_flag.is_set():
            try:
                next_msg = self.process_queue.get(True, 3.0)

                self.log.debug("Received event from queue with pri {}: {}".format(next_msg[0], next_msg[1]))

                # PriorityQueue - filter out weighting - not used elsewhere
                next_msg = next_msg[1]
                if next_msg is None:
                    # Poison pill
                    break

                # Process message
                if next_msg['sender'] == 'xbmc' and next_msg['method'] == 'VideoLibrary.OnUpdate':
                    event_type = 'kodi.client.notification.{}'.format(next_msg['method'])
                    event_msg = {
                        'notification': next_msg
                    }
                    # Parse data back into dict
                    parsed_data = json.loads(next_msg['data'], encoding='utf-8')
                    event_msg['notification']['data'] = parsed_data
                    update_type = parsed_data['item']['type']

                    # Check it wasn't us that triggered the update
                    with self.rt_lock:
                        # runtime_config['ignore_updates_from'] = {
                        #     'movie': set(),
                        #     'episode': set()
                        # }
                        if parsed_data['item']['id'] in self.rt_config['ignore_updates_from'][update_type]:
                            # It was us
                            self.log.debug("Self generated - ignoring VideoLibrary.OnUpdate for {} id {}".format(update_type,
                                                                                                                 parsed_data['item']['id']))
                            self.rt_config['ignore_updates_from'][update_type].remove(parsed_data['item']['id'])
                            continue

                    if update_type == 'movie':
                        event_msg['moviedetails'] = get_movie_details(parsed_data['item']['id'])
                    elif update_type == 'episode':
                        event_msg['episodedetails'] = get_episode_details(parsed_data['item']['id'])
                        event_msg['tvshowdetails'] = get_tvshow_details(event_msg['episodedetails']['tvshowid'])
                    self.el.new(event_type, event_msg)

                if next_msg['sender'] == 'xbmc' and next_msg['method'] in ["System.OnWake", "GUI.OnScreensaverDeactivated",
                                                                           "VideoLibrary.OnScanFinished"]:
                    self.log.debug("Waking up VideoLibraryUpdateThread")
                    self.wakeup_flag.set()

                if next_msg['sender'] == 'xbmc' and next_msg['method'] in ["GUI.OnScreensaverActivated",
                                                                           "GUI.OnScreensaverDeactivated"]:
                    event_type = 'kodi.client.notification.{}'.format(next_msg['method'])
                    event_msg = {
                        'notification': next_msg
                    }
                    self.el.new(event_type, event_msg)

                # Simulate process message
                xbmc.sleep(750)

                # Finished processing msg

            except Queue.Empty:
                continue

            except:
                sentry_sdk.capture_exception()

        self.log.debug("Exiting thread: {}".format(threading.currentThread().getName()))


if __name__ == '__main__':
    pass

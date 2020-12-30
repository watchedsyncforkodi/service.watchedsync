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
import threading
import Queue
import requests
import json
import boto3
from botocore.exceptions import ClientError, ConnectionError, HTTPClientError
import hmac
import hashlib
import xbmc
import xbmcaddon

LIB_RESOURCES_PATH = xbmc.translatePath(os.path.join(xbmcaddon.Addon().getAddonInfo('path').decode('utf-8'), 'resources'.decode('utf-8'), 'lib'.decode('utf-8')))
sys.path.append(LIB_RESOURCES_PATH)

""" Local module imports - need to be after LIB_RESOURCES_PATH """
from watchsync.logging import KodiLog
from watchsync.notifications import KodiNotifications
from watchsync.auth import AuthSession, AuthBoto3Direct, AuthSessionError
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


""" Configuration Variables
"""
REGISTER_TIMEOUT = 20.0
REGISTER_MAX_BACKOFF = 433
HTTP_GET_TIMEOUT = 3.1
""" End of Configuration Variables
"""


class VideoLibraryUpdateThread(BackgroundThread):

    def __init__(self, runtime_config, runtime_config_lock, wakeup_flag):
        super(VideoLibraryUpdateThread, self).__init__(name="VideoLibraryUpdateThread")

        self.rt_config = runtime_config
        self.rt_lock = runtime_config_lock
        self.wakeup_flag = wakeup_flag
        self.log = KodiLog(__file__, __name__)

        with self.rt_lock:
            self.auth_session = runtime_config['session_auth']
            self.update_poll_interval = runtime_config['update_library_poll_interval']
            self.update_queue_url = runtime_config['update_library_queue_url']
            # Setup ignore update list
            runtime_config['ignore_updates_from'] = {
                'movie': set(),
                'episode': set()
            }
            # Setup scan list
            runtime_config['scan_history'] = set()

        self.boto3_auth_session = AuthBoto3Direct(self.auth_session,
                                                  assume_role_arn='arn:aws:iam::251217536828:role/watchsync_kodi_client_role',
                                                  role_session_name=getSettingAsString('auth_client_id')[:64],
                                                  session_duration=60*60*6)  # 6 hours

        # Get the boto3 service resource.
        self.boto3_session = boto3.session.Session(region_name='eu-west-1')

        self.this_device = getSettingAsString('auth_client_id')

    def is_kodi_busy(self):
        """
            Determines if the local kodi device is considered busy to do library operations
        :return True/False:
        """
        is_playing = xbmc.Player().isPlaying()
        is_scanning_library = xbmc.getCondVisibility('Library.IsScanning')

        if is_playing or is_scanning_library:
            return True

        return False

    def get_next_msg(self):
        """
            Get next message from the queue

        :return None/msg dict:
        """
        try:
            sqs = self.boto3_session.resource('sqs', **self.boto3_auth_session.get_resource_access_arguments())
            sqs_queue = sqs.Queue(self.update_queue_url)
            next_msg = sqs_queue.receive_messages(MaxNumberOfMessages=1,
                                                  MessageAttributeNames=['*'])

            if not getSettingAsBool('connected_online'):
                # Indicate to user we are connected
                # 32010 - Connected
                setSettingAsString("addon_status", getString(32010))
                setSettingAsBool("connected_online", True)

        except AuthSessionError as e:
            self.log.warning("Temporary authentication error: {}".format(e))
            if getSettingAsBool('connected_online'):
                # Indicate to user we are Offline
                # 32011 - Offline
                setSettingAsString("addon_status", getString(32011))
                setSettingAsBool("connected_online", False)
            next_msg = []

        except requests.RequestException as e:
            self.log.warning("Temporary communications error: {}".format(e))
            if getSettingAsBool('connected_online'):
                # Indicate to user we are Offline
                # 32011 - Offline
                setSettingAsString("addon_status", getString(32011))
                setSettingAsBool("connected_online", False)
            next_msg = []

        except (ClientError, ConnectionError, HTTPClientError) as e:
            self.log.warning("Temporary communications error: {}".format(e))
            if getSettingAsBool('connected_online'):
                # Indicate to user we are Offline
                # 32011 - Offline
                setSettingAsString("addon_status", getString(32011))
                setSettingAsBool("connected_online", False)
            next_msg = []

        except:
            if getSettingAsBool('connected_online'):
                # Indicate to user we are Offline
                # 32011 - Offline
                setSettingAsString("addon_status", getString(32011))
                setSettingAsBool("connected_online", False)
            next_msg = []
            sentry_sdk.capture_exception()

        return next_msg

    def mark_msg_complete(self, msg):
        """
            Mark msg has completed processing

        :param msg:
        :return:
        """
        # Can delete the message from the SQS queue once complete
        msg.delete()

    def scan_library_once_with_dirpath(self, scan_dirpath):
        """
            Scan library once with supplied directory path

        :param scan_path:
        :return True if scan initiated otherwise false:
        """
        with self.rt_lock:
            if scan_dirpath not in self.rt_config['scan_history']:
                self.log.debug("Initiate library scan with directory path: {}".format(scan_dirpath))
                # Haven't instructed to scan previously so scan now
                scan_video_library(scan_dirpath)
                # Update scan history
                self.rt_config['scan_history'].add(scan_dirpath)
                return True
            else:
                # Scanned previously - don't try again
                self.rt_config['scan_history'].remove(scan_dirpath)
                return False

    def update_content_watch_status_in_library(self, update_type, content_id, content_details):
        """
            Update content watch status

        :return:
        """
        with self.rt_lock:
            # runtime_config['ignore_updates_from'] = {
            #     'movie': set(),
            #     'episode': set()
            # }
            self.rt_config['ignore_updates_from'][update_type].add(content_id)
        return update_content_watch_status(update_type, content_id, content_details)

    def stop(self):
        # call from parent to stop and exit thread
        self.exit_flag.set()
        # Trigger wake up
        self.wakeup_flag.set()

    def run(self):
        # Called by calling start()
        self.log.debug("Starting thread: {}".format(threading.currentThread().getName()))

        # Set setting for connected online to false. Will set real status later in get_next_msg
        setSettingAsBool("connected_online", False)

        # Continuously loop until exit
        while not self.exit_flag.wait(1):

            # Wait poll interval time or received a wakeup command
            self.wakeup_flag.wait(self.update_poll_interval)
            # Reset wakeup flag
            self.wakeup_flag.clear()

            # Continue polling for new messages until no new messages
            msgs_to_process = True
            while msgs_to_process:
                # Reset
                msgs_to_process = []

                # Check we haven't been asked to exit
                if not self.exit_flag.is_set():
                    # Check kodi is not busy before continuing
                    if not self.is_kodi_busy():

                        # Try to get message from AWS. Returns empty if no messages found
                        msgs_to_process = self.get_next_msg()

                        # Will return list even if single message is returned
                        for msg_to_process in msgs_to_process:

                            # Check we haven't been asked to exit
                            if not self.exit_flag.is_set():
                                # Check kodi is not busy
                                if not self.is_kodi_busy():

                                    try:
                                        msg_body = json.loads(msg_to_process.body, encoding='utf-8')
                                    except:
                                        msg_body = msg_to_process.body

                                    # Build msg attrs into Python dict
                                    msg_attrs = {}
                                    if msg_to_process.message_attributes:
                                        for k in msg_to_process.message_attributes:
                                            # Build msg_attrs
                                            msg_attrs[k] = msg_to_process.message_attributes[k].get('StringValue', None)


                                    # Process message after short pause
                                    xbmc.sleep(850)

                                    # Ignore locally sourced messages
                                    if msg_attrs['origin'] == self.this_device:
                                        continue

                                    # Handle updating poll interval
                                    if msg_attrs['event'] == 'kodi.update_poll_interval.changed':
                                        if 'new_poll_interval' in msg_body:
                                            # Cap to minimum of 10 seconds
                                            new_interval = int(msg_body['new_poll_interval'])
                                            self.update_poll_interval = max(10, new_interval)
                                            self.log.debug("Updated poll interval to {}".format(self.update_poll_interval))

                                    # Handle VideoLibrary OnUpdate
                                    elif msg_attrs['event'].endswith("VideoLibrary.OnUpdate"):

                                        update_type = msg_body['notification']['data']['item']['type']
                                        operations = {
                                            "episode": {
                                                "id": "episodeid",
                                                "typedetails": "episodedetails"
                                            },
                                            "movie": {
                                                "id": "movieid",
                                                "typedetails": "moviedetails"
                                            }
                                        }
                                        this_op = operations[update_type]

                                        self.log.debug("Detected {} video update request".format(update_type))
                                        search_filename = msg_body[this_op['typedetails']]['filename']
                                        search_dirpath = msg_body[this_op['typedetails']]['dirpath']
                                        found_exact_match = False
                                        for c in find_content_with_filepath(update_type, search_filename, search_dirpath):
                                            log_s = "Standard method - found {} matching full path to update: {}"
                                            self.log.debug(log_s.format(update_type, c))
                                            found_exact_match = True
                                            self.update_content_watch_status_in_library(update_type,
                                                                                        c[this_op["id"]],
                                                                                        msg_body[this_op['typedetails']])
                                            self.log.info("Successfully sync watch status for {} - {}".format(update_type,
                                                                                                              c['label']))

                                        if update_type == 'episode':

                                            if not found_exact_match:
                                                # Find TV show on this device
                                                this_tvshowid = get_tvshowid_from_uniqueid(msg_body['tvshowdetails']['uniqueid'])
                                                found_different_path_match = False

                                                if this_tvshowid:

                                                    for c in find_content_with_filepath(update_type, search_filename):
                                                        if c['tvshowid'] == this_tvshowid:
                                                            # Found match tv show episode based on filename and tvshowid
                                                            log_s = "Fallback method - found {} matching filename and tvshowid {}"
                                                            self.log.debug(log_s.format(update_type, this_tvshowid))
                                                            found_different_path_match = True
                                                            self.update_content_watch_status_in_library(update_type,
                                                                                                        c[this_op["id"]],
                                                                                                        msg_body[this_op['typedetails']])
                                                            self.log.info(
                                                                "Successfully sync watch status for {} - {}".format(update_type,
                                                                                                                    c['label']))

                                                if not found_different_path_match:
                                                    # Can't find matching tv show or filename
                                                    # As last ditch attempt, try to scan the library
                                                    if self.scan_library_once_with_dirpath(search_dirpath):
                                                        # Skip more processing and wait until next message
                                                        continue
                                                    else:
                                                        # Tried scan and still got here - failed
                                                        content_title = "{} - {}".format(msg_body['tvshowdetails']['title'],
                                                                                         msg_body['episodedetails']['title'])
                                                        self.log.warning("Wasn't able to sync {} '{}'. Couldn't find a "
                                                                         "local match".format(update_type, content_title))

                                        elif update_type == 'movie':

                                            if not found_exact_match:
                                                # Find film on this device
                                                this_movieid = get_movieid_from_uniqueid(msg_body['moviedetails']['uniqueid'])
                                                found_different_path_match = False

                                                if this_movieid:

                                                    for c in find_content_with_filepath(update_type, search_filename):
                                                        if c['movieid'] == this_movieid:
                                                            # Found match film based on filename and movieid
                                                            log_s = "Fallback method - found {} matching filename and tvshowid {}"
                                                            self.log.debug(log_s.format(update_type, this_movieid))
                                                            found_different_path_match = True
                                                            self.update_content_watch_status_in_library(update_type,
                                                                                                        c[this_op["id"]],
                                                                                                        msg_body[this_op['typedetails']])
                                                            self.log.info(
                                                                "Successfully sync watch status for {} - {}".format(update_type,
                                                                                                                    c['label']))

                                                if not found_different_path_match:
                                                    # Can't find matching film.
                                                    # As last ditch attempt, try to scan the library
                                                    if self.scan_library_once_with_dirpath(search_dirpath):
                                                        # Skip more processing and wait until next message
                                                        continue
                                                    else:
                                                        # Tried scan and still got here - failed
                                                        content_title = "{}".format(msg_body['moviedetails']['title'])
                                                        self.log.warning("Wasn't able to sync {} '{}'. Couldn't find a "
                                                                         "local match".format(update_type, content_title))

                                    # Finished processing msg
                                    self.mark_msg_complete(msg_to_process)

        # Update settings to mark offline
        setSettingAsString("addon_status", getString(32011))
        setSettingAsBool("connected_online", False)
        self.log.debug("Exiting thread: {}".format(threading.currentThread().getName()))



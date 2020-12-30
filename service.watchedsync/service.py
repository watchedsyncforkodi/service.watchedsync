#
#
# Copyright 2016 CSS
#
# This software is unpublished work which is proprietary to CSS.
# Any distribution is strictly forbidden
#

import sys
import os
import threading
import Queue
import xbmc
import xbmcaddon

LIB_RESOURCES_PATH = xbmc.translatePath(os.path.join(xbmcaddon.Addon().getAddonInfo('path').decode('utf-8'), 'resources'.decode('utf-8'), 'lib'.decode('utf-8')))
sys.path.append(LIB_RESOURCES_PATH)

""" Local module imports - need to be after LIB_RESOURCES_PATH """
from watchsync.logging import KodiLog
from watchsync.notifications import KodiNotifications, ProcessNotificationsThread
from watchsync.setup import perform_setup_function
from watchsync.remote import VideoLibraryUpdateThread
from watchsync.event_logger import EventLogger
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

""" End of Configuration Variables
"""

log = KodiLog(__file__, __name__)

log.debug('RESOURCES_PATHs: {}'.format(LIB_RESOURCES_PATH))
log.debug('__file__: {}'.format(__file__))

def main():
    """Main function"""
    log.info('Starting')

    # Setup main runtime configuration variables (threadsafe)
    runtime_config = {
        'setup_complete': False
    }
    runtime_config_lock = threading.Lock()
    notification_queue = Queue.PriorityQueue()
    exit_flag = threading.Event()
    wakeup_flag = threading.Event()

    kn = KodiNotifications(notification_queue)
    el = None
    worker_threads = []

    try:
        # Perform setup operations
        setup_complete = perform_setup_function(runtime_config, runtime_config_lock)

        if setup_complete:

            # Setup event logger
            el = EventLogger(auth_session=runtime_config['session_auth'])
            startup_success_data = {
                'application':
                    {
                        'app_id': __addonid__,
                        'app_name': __addonname__,
                        'app_version': __addonversion__
                    },
                'system_info': runtime_config['system_info']
            }

            worker_threads.append(VideoLibraryUpdateThread(runtime_config,
                                                           runtime_config_lock,
                                                           wakeup_flag))
            worker_threads[-1].start()
            worker_threads.append(ProcessNotificationsThread(runtime_config,
                                                             runtime_config_lock,
                                                             wakeup_flag,
                                                             notification_queue,
                                                             el))
            worker_threads[-1].start()

            # Confirm startup successful
            log.info("Completed startup successfully")
            el.new('kodi.client.setup.complete', startup_success_data)

            try:
                while not kn.abortRequested():
                    # Sleep/wait for abort
                    if kn.waitForAbort(60):
                        # Abort was requested while waiting. We should exit
                        break
                    log.debug("service.watchedsync waited 60 secs for abort...")
            except KeyboardInterrupt:
                log.debug('Keyboard Interrupted')

        else:
            log.error("Failed to complete setup correctly. Terminating service")

    except:
        sentry_sdk.capture_exception()

    # Cleanly shutdown

    # Tell threads to exit
    exit_flag.set()

    for t in worker_threads:
        t.stop()

    # Update settings to mark offline
    setSettingAsString("addon_status", getString(32011))
    setSettingAsBool("connected_online", False)

    log.debug("Received abortRequested() - waiting for threads to exit")
    for t in worker_threads:
        t.join()

    # Stop the EventLogger
    if el:
        el.stop()

    # Close down sentry
    if sentry_sdk.Hub.current.client:
        sentry_sdk.Hub.current.client.close(timeout=1.0)

    log.info('All threads exited cleanly')


if __name__ == '__main__':
    main()


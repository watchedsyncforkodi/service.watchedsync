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
import boto3
import json
import uuid
import requests
import hmac
import hashlib
import xbmc
import xbmcaddon

LIB_RESOURCES_PATH = xbmc.translatePath(os.path.join(xbmcaddon.Addon().getAddonInfo('path').decode('utf-8'), 'resources'.decode('utf-8'), 'lib'.decode('utf-8')))
sys.path.append(LIB_RESOURCES_PATH)

""" Local module imports - need to be after LIB_RESOURCES_PATH """
from watchsync.logging import KodiLog
from watchsync.auth import AuthSession, AuthBoto3Direct, AuthSessionServerError, AuthSessionClientError
from watchsync.utils import *


__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name').decode('utf-8')
__addonversion__ = __addon__.getAddonInfo('version').decode('utf-8')
__addonid__ = __addon__.getAddonInfo('id').decode('utf-8')
__addonpath__ = __addon__.getAddonInfo('path').decode('utf-8')
__addonprofile__ = xbmc.translatePath(__addon__.getAddonInfo('profile').decode('utf-8'))


log = KodiLog(__file__, __name__)

""" Configuration Variables
"""
_request_timeout = 15
""" End of Configuration Variables
"""

def get_kodi_info_label(label):
    """
        Return kodi info label, handling temporary Busy errors

    :param label:
    :return string with info label:
    """
    res = "Busy"
    while res == "Busy":
        res = xbmc.getInfoLabel(label).decode('utf-8')
        xbmc.sleep(250)
    return res


def get_session_endpoints(runtime_config, runtime_config_lock):
    """
        Return the endpoints for these sessions

    :param runtime_config:
    :param runtime_config_lock:
    :return dict of endpoints:
    """
    # Simulate external call
    xbmc.sleep(750)
    #TODO: Replace stub endpoints
    stub_endpoints = {
        'register_endpoint': u'https://keq4fgzes4.execute-api.eu-west-1.amazonaws.com/conceptv1/api/register_device',
        'runtime_config_endpoint': u'https://keq4fgzes4.execute-api.eu-west-1.amazonaws.com/conceptv1/api/get_device_config'
    }
    with runtime_config_lock:
        runtime_config['endpoints'] = stub_endpoints

    return stub_endpoints


def get_registration_code(runtime_config, runtime_config_lock):
    """
        Return the registration code for this device

    :param runtime_config:
    :param runtime_config_lock:
    :return registration code string:
    """
    # See if already stored locally
    if getSettingAsString('registration_code'):
        registration_code = getSettingAsString('registration_code')
    else:
        # Generate new one
        registration_code = str(uuid.uuid4())
        setSettingAsString('registration_code', registration_code)

    # Make friendlier version of registration code to display to user
    friendly_registration_code = '-'.join((registration_code[0:4], registration_code[4:8])).upper()
    setSettingAsString('user_registration_code', friendly_registration_code)

    with runtime_config_lock:
        runtime_config['registration_code'] = registration_code
        runtime_config['friendly_registration_code'] = friendly_registration_code

    return registration_code


def retrieve_system_info(runtime_config, runtime_config_lock):
    """
        Retrieve kodi system information

    :param runtime_config:
    :param runtime_config_lock:
    :return dict with system info:
    """
    sk = '\xd5\xb3\x9c+\xf9=\xd0\n\xdb\xa4\x8b\xe3\xea\x88\xdf=\xbb\x96\xb4\xb8\xe5)4Wr\xf1@\xcc\xbfZ\xaf\xb3.?\x10!\x80lD\xc2\xb6UM\xd0\xb0\xc3\xb1@\xf6K\xc35\xf3+\x83MO\x89d\xe9\x1f0k\xbd\xe2o\xbc\xdci\x0c\xcaV\x1d\x81(.\x7f\x93\x1a8\x0b\x1f\xe5\xce\xc3GP\xeeU]\t\xb8\x1a\x12\xb7\xd9.\xde"\x99b\xc4;O+:\xf6\xb8\xba+\xf6pVel$\xbe\xd0j\x0e\xf8"\xae\x02q\x1b\xc4\xd8'
    mac_hash = hmac.new(sk, get_kodi_info_label("Network.MacAddress").lower(), digestmod=hashlib.sha256).hexdigest()
    system_info = {
        "System.OSVersionInfo": get_kodi_info_label("System.OSVersionInfo"),
        "System.BuildVersion": get_kodi_info_label("System.BuildVersion"),
        "System.Uptime": get_kodi_info_label("System.Uptime"),
        "Network.IPAddress": get_kodi_info_label("Network.IPAddress"),
        "Network.MacAddress.Hash": mac_hash,
        "UserAgent": xbmc.getUserAgent().decode('utf-8'),
    }

    # Determine system platform
    if xbmc.getCondVisibility("System.Platform.Linux"):
        system_info["System.Platform"] = u"Linux"
    elif xbmc.getCondVisibility("System.Platform.Windows"):
        system_info["System.Platform"] = u"Windows"
    elif xbmc.getCondVisibility("System.Platform.UWP"):
        system_info["System.Platform"] = u"UWP"
    elif xbmc.getCondVisibility("System.Platform.OSX"):
        system_info["System.Platform"] = u"OSX"
    elif xbmc.getCondVisibility("System.Platform.IOS"):
        system_info["System.Platform"] = u"IOS"
    elif xbmc.getCondVisibility("System.Platform.Darwin"):
        system_info["System.Platform"] = u"Darwin"
    elif xbmc.getCondVisibility("System.Platform.Android"):
        system_info["System.Platform"] = u"Android"

    with runtime_config_lock:
        runtime_config['system_info'] = system_info
        log.debug("Retrieved system information")

    return system_info


def register_device(runtime_config, runtime_config_lock):
    """
        Register this device

    :param runtime_config:
    :param runtime_config_lock:
    :return:
    """
    register_endpoint = None
    data_to_submit = {}
    with runtime_config_lock:
        register_endpoint = runtime_config['endpoints']['register_endpoint']
        data_to_submit['system_info'] = runtime_config['system_info']

    data_to_submit['application'] = {
        'app_id': __addonid__,
        'app_name': __addonname__,
        'app_version': __addonversion__
    }
    data_to_submit['registration_code'] = get_registration_code(runtime_config, runtime_config_lock)
    setSettingAsBool('in_registration_mode', True)

    # Attempt registration
    custom_headers = {
        'user-agent': xbmc.getUserAgent(),
        'Content-Type': 'application/json'
    }

    r = requests.post(url=register_endpoint,
                      data=json.dumps(data_to_submit),
                      headers=custom_headers,
                      timeout=_request_timeout)

    if 400 <= r.status_code < 500:
        # Failed during registration process - Inform user to register
        msg = "{} {}".format(getString(32014), getSettingAsString('user_registration_code'))
        displayOKDialog(msg)

    r.raise_for_status()
    reg_output = r.json()
    # output = {
    #     'auth_client_id': cd_xxxx,
    #     'auth_client_secret': xxxxxxx,
    #     'registration_status': 'successful'
    # }
    if reg_output['registration_status'] == 'successful':
        setSettingAsString('auth_client_id', reg_output['auth_client_id'])
        setSettingAsString('auth_client_secret', reg_output['auth_client_secret'])
        setSettingAsBool('in_registration_mode', False)
        setSettingAsString('registration_code', '')
        setSettingAsString('user_registration_code', '')
        log.info("Successfully registered device")


def authorise_device(runtime_config, runtime_config_lock):
    """
        Authorise device with service

    :param runtime_config:
    :param runtime_config_lock:
    :return:
    """
    # Call to AuthSession will raise exceptions if fails
    auth_session = AuthSession(scope='watchsync.client/event.write watchsync.client/task.read')

    with runtime_config_lock:
        runtime_config['session_auth'] = auth_session


def get_runtime_config(runtime_config, runtime_config_lock):
    """
        Get runtime config from service

    :param runtime_config:
    :param runtime_config_lock:
    :return:
    """
    config_endpoint = None
    auth_session = None
    with runtime_config_lock:
        # Use existing session auth
        auth_session = runtime_config['session_auth']
        config_endpoint = runtime_config['endpoints']['runtime_config_endpoint']

    custom_headers = {
        'User-Agent': xbmc.getUserAgent(),
        'Content-Type': 'application/json',
        'Authorization': auth_session.get_authorization_header()
    }

    r = requests.get(url=config_endpoint,
                     headers=custom_headers,
                     timeout=_request_timeout)
    r.raise_for_status()
    result = r.json()
    with runtime_config_lock:
        # Get runtime config from service. Set minimum of 10 seconds for poll interval
        runtime_config['update_library_poll_interval'] = max(10, result['queue_poll_interval'])
        runtime_config['update_library_queue_url'] = result['queue_endpoint']


def perform_setup_function(runtime_config, runtime_config_lock):
    """
        Perform all the setup functions

    :param runtime_config:
    :param runtime_config_lock:
    :return True/False - Whether setup functions have completed successfully:
    """
    kodi_system = xbmc.Monitor()
    setup_result = False
    setup_complete = False
    setup_attempts = 0

    # Indicate to user we are starting up
    # 32007 - Starting up...
    setSettingAsString("addon_status", getString(32007))

    while not kodi_system.abortRequested() and not setup_complete:
        try:
            setup_attempts += 1

            # Stub setup - loop 2 times before returning
            kodi_system.waitForAbort(10)
            if not kodi_system.abortRequested() and setup_attempts >= 2:
                retrieve_system_info(runtime_config, runtime_config_lock)

                get_session_endpoints(runtime_config, runtime_config_lock)

                if not getSettingAsString('auth_client_id') or not getSettingAsString('auth_client_secret'):
                    # Need to register device...
                    try:
                        # Indicate to user we are currently unregistered
                        # 32008 - Unregistered
                        setSettingAsString("addon_status", getString(32008))
                        register_device(runtime_config, runtime_config_lock)

                    except requests.exceptions.RequestException as err:
                        # Failure during registration - assume permanent
                        log.error("Failed while registering device: {}".format(err))
                        break

                    xbmc.sleep(1500)

                authorise_device(runtime_config, runtime_config_lock)

                try:
                    get_runtime_config(runtime_config, runtime_config_lock)

                except requests.exceptions.RequestException as err:
                    # Failure during retrieving config - assume permanent
                    log.error("Failed while getting runtime config: {}".format(err))
                    break

                # Mark setup successful
                setup_complete = True
                setup_result = True

                # Indicate to user we have completed setup
                # 32009 - Registered
                setSettingAsString("addon_status", getString(32009))

        except AuthSessionClientError as err:
            # If client based assume this is a permanent error that needs human input
            log.error("Failed client authentication during setup: {}".format(err))
            break

        except AuthSessionServerError as err:
            # If server based assume then assume this is a temporary error and try again later
            log.warning("Failed server authentication during setup: {}".format(err))
            # Go round the while loop again

    with runtime_config_lock:
        runtime_config['setup_complete'] = setup_complete
        log.debug("Performed setup function")

    return setup_result



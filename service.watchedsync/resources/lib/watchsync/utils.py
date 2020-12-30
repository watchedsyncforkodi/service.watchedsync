#
#
# Copyright 2019-2020 CSS
#
# This software is unpublished work which is proprietary to CSS.
# Any distribution is strictly forbidden
#
#

import os
import sys
import threading
import json
import urlparse
import uuid
from time import time
import xbmc
import xbmcaddon
import xbmcgui

LIB_RESOURCES_PATH = xbmc.translatePath(os.path.join(xbmcaddon.Addon().getAddonInfo('path').decode('utf-8'), 'resources'.decode('utf-8'), 'lib'.decode('utf-8')))
sys.path.append(LIB_RESOURCES_PATH)

""" Local module imports - need to be after LIB_RESOURCES_PATH """
import watchsync.logging

__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name').decode('utf-8')
__addonversion__ = __addon__.getAddonInfo('version').decode('utf-8')
__addonid__ = __addon__.getAddonInfo('id').decode('utf-8')
__addonpath__ = __addon__.getAddonInfo('path').decode('utf-8')
__addonprofile__ = xbmc.translatePath(__addon__.getAddonInfo('profile').decode('utf-8'))


class RepeatingTimerThread(threading.Thread):

    def __init__(self, interval, func, *args, **kwargs):
        super(RepeatingTimerThread, self).__init__(name="RepeatingTimerThread")
        self.run_func = func
        self.args = args
        self.kwargs = kwargs
        self.log = watchsync.logging.KodiLog(__file__, __name__)
        self.exit_flag = threading.Event()
        self.interval = interval

    def stop(self):
        # call from parent to stop and exit thread
        self.exit_flag.set()

    def run(self):
        # Called by calling start()
        self.log.debug("Starting thread: {}".format(threading.currentThread().getName()))
        self.run_func(*self.args, **self.kwargs)
        while not self.exit_flag.wait(self.interval):
            self.run_func(*self.args, **self.kwargs)
        self.log.debug("Exiting thread: {}".format(threading.currentThread().getName()))


class BackgroundThread(threading.Thread):

    def __init__(self, group=None, target=None, name=None, verbose=None):
        super(BackgroundThread, self).__init__(group=group, target=target, name=name, verbose=verbose)

        self.log = watchsync.logging.KodiLog(__file__, __name__)
        self.exit_flag = threading.Event()

    def stop(self):
        # call from parent to stop and exit thread
        self.exit_flag.set()

    def run(self):
        # Called by calling start()
        self.log.debug("Starting thread: {}".format(threading.currentThread().getName()))
        while not self.exit_flag.wait():
            pass
        self.log.debug("Exiting thread: {}".format(threading.currentThread().getName()))


def showSettings():
    __addon__.openSettings()

def getSettingAsString(setting):
    return __addon__.getSetting(setting).strip().decode('utf-8')

def setSettingAsString(setting, value):
    __addon__.setSetting(setting, str(value))

def setSettingAsBool(setting, value):
    __addon__.setSettingBool(setting, bool(value))

def getSettingAsBool(setting):
    return getSettingAsString(setting).lower() == u"true"

def getSettingAsFloat(setting):
    try:
        return float(getSettingAsString(setting))
    except ValueError:
        return 0

def getSettingAsInt(setting):
    try:
        return int(getSettingAsFloat(setting))
    except ValueError:
        return 0

def getString(string_id):
    return __addon__.getLocalizedString(string_id).encode('utf-8', 'ignore')

def displayOKDialog(msg):
    xbmcgui.Dialog().ok(__addonname__, msg)

def issue_kodi_jsonrpc_command(payload):
    """ Issue RPC command to kodi device and return results """
    log = watchsync.logging.KodiLog(__name__, "issue_kodi_jsonrpc_command")
    request_id = str(uuid.uuid4())
    payload["id"] = request_id
    payload["jsonrpc"] = "2.0"
    log.debug("Using following payload for JSON RPC command: {}".format(payload))
    try:
        start = time()
        res = None
        res = xbmc.executeJSONRPC(json.dumps(payload, encoding='utf-8', ensure_ascii=False))
        done = time()
        elapsed = done - start
        log.debug("JSON RPC returned OK (took {:.1f}ms)".format(elapsed*1000))
        return json.loads(res, encoding='utf-8')["result"]
    except:
        log.error("Error when executing JSON RPC command")
        log.error("  - command: {}".format(payload))
        log.error("  - response: {}".format(res))
        raise
        # return empty result
        return []


def get_results_from_kodi_jsonrpc(method, expected_results_name, properties, additional_params=None, filter_cmd=None):
    """
        Return iterator of results from the specified JSON RPC call

    :param method:
    :param expected_results_name:
    :param properties:
    :param additional_params: For passing additional parameters
    :param filter_cmd:
    :return:
    """
    log = watchsync.logging.KodiLog(__name__, "get_results_from_jsonrpc")
    payload_template = {
        "method": "",
        "params": {
            "limits": {
                "start": 0,
                "end": 0
            },
            "properties": "",
        }
    }

    # Loop and get all the information
    complete = False
    start = 0
    incr = 100
    while (not complete):
        payload = payload_template
        payload["method"] = method
        payload["params"]["limits"]["start"] = start
        payload["params"]["limits"]["end"] = start + incr
        payload["params"]["properties"] = properties
        if filter_cmd:
            payload["params"]["filter"] = filter_cmd
        if additional_params:
            payload["params"].update(additional_params)
        result = issue_kodi_jsonrpc_command(payload)
        if 'limits' in result:

            if expected_results_name in result:
                for entry in result[expected_results_name]:
                    yield entry

            start = result['limits']['end']
            if result['limits']['end'] >= result['limits']['total']:
                # finished with this call
                complete = True
        else:
            log.debug("No results returned")
            complete = True


def get_tvshow_details(tvshowid):
    """
        Get details of a TV show from Kodi

    :param tvshowid:
    :return dict with tvshowdetails:
    """
    payload = {
        "method": "VideoLibrary.GetTVShowDetails",
        "params": {
            "tvshowid": int(tvshowid),
            "properties": [
                "episode", "title", "uniqueid"
            ]
       }
    }
    result = issue_kodi_jsonrpc_command(payload)
    if result:
        return result['tvshowdetails']
    else:
        return None


def get_movie_details(movieid):
    """
        Get details of a film from Kodi

    :param movieid:
    :return dict with moviedetails:
    """
    payload = {
        "method": "VideoLibrary.GetMovieDetails",
        "params": {
            "movieid": int(movieid),
            "properties": [
                "title", "uniqueid", "lastplayed", "playcount", "resume", "file"
            ]
       }
    }
    result = issue_kodi_jsonrpc_command(payload)
    if result:
        # Add directory and file information
        if 'file' in result['moviedetails']:
            (dirpath, filename) = os.path.split(result['moviedetails']['file'])
            result['moviedetails']['dirpath'] = dirpath
            result['moviedetails']['filename'] = filename
        return result['moviedetails']
    else:
        return None


def get_episode_details(episodeid):
    """
        Get details of an episode from Kodi

    :param episodeid:
    :return dict with episodedetails:
    """
    payload = {
        "method": "VideoLibrary.GetEpisodeDetails",
        "params": {
            "episodeid": int(episodeid),
            "properties": [
                "title", "uniqueid", "lastplayed", "playcount", "resume", "file",
                "tvshowid", "dateadded", "episode", "season", "seasonid"
            ]
       }
    }
    result = issue_kodi_jsonrpc_command(payload)
    if result:
        # Add directory and file information
        if 'file' in result['episodedetails']:
            (dirpath, filename) = os.path.split(result['episodedetails']['file'])
            result['episodedetails']['dirpath'] = dirpath
            result['episodedetails']['filename'] = filename
        return result['episodedetails']
    else:
        return None


def update_content_watch_status(type, contentid, contentdetails):
    """
        Update the watch status of content in Kodi

    :param type:
    :param contentid:
    :param contentdetails:
    :return True/False:
    """
    # type logic
    operations = {
        "episode": {
            "method": "VideoLibrary.SetEpisodeDetails",
            "id": "episodeid",
        },
        "movie": {
            "method": "VideoLibrary.SetMovieDetails",
            "id": "movieid",
        }
    }
    this_op = operations[type]

    payload = {
        "method": this_op['method'],
        "params": {
            this_op['id']: contentid,
            "playcount": contentdetails["playcount"],
            "resume": contentdetails["resume"],
            "lastplayed": contentdetails["lastplayed"],
        },
    }
    result = issue_kodi_jsonrpc_command(payload)
    if result:
        return True
    else:
        return False


def find_content_with_filepath(type, search_filename, search_dirpath=None):
    """
        Find all content of specific type with path having dirpath and filename

    :param type: Either 'episode' or 'movie'
    :param search_filename:
    :param search_dirpath:
    :return dict of episodes:
    """
    # type logic
    operations = {
        "episode": {
            "method": "VideoLibrary.GetEpisodes",
            "result_name": "episodes",
            "properties": ["file", "episode", "season", "tvshowid", "dateadded", "uniqueid"],
        },
        "movie": {
            "method": "VideoLibrary.GetMovies",
            "result_name": "movies",
            "properties": ["file", "dateadded", "uniqueid"],
        }
    }
    this_op = operations[type]

    if search_dirpath:
        filter_path = {
            "and": [
                {
                    "field": "filename",
                    "value": search_filename,
                    "operator": "is",
                },
                {
                    "field": "path",
                    "value": search_dirpath,
                    "operator": "startswith",
                }
            ]
        }
    else:
        filter_path = {
            "field": "filename",
            "value": search_filename,
            "operator": "is",
        }

    return get_results_from_kodi_jsonrpc(this_op['method'],
                                         this_op['result_name'],
                                         this_op['properties'],
                                         filter_cmd=filter_path)


def find_episodes_with_filepath(search_filename, search_dirpath=None):
    """
        Find all episodes with path having dirpath and filename

    :param search_filename:
    :param search_dirpath:
    :return dict of episodes:
    """
    return find_content_with_filepath("episode", search_filename, search_dirpath)


def find_movies_with_filepath(search_filename, search_dirpath=None):
    """
        Find all movies with path having dirpath and filename

    :param search_filename:
    :param search_dirpath:
    :return dict of movies:
    """
    return find_content_with_filepath("movie", search_filename, search_dirpath)


def get_tvshowid_from_uniqueid(uniqueid_dict):
    """
        Return tvshowid from searching for matching at least one of the uniqueid keys in the supplied dict

    :param uniqueid_dict:
    :return int or none:
    """
    for t in get_results_from_kodi_jsonrpc("VideoLibrary.GetTVShows", "tvshows", ["uniqueid"]):
        # Have to scan as no ability to filter search uniqueid
        for k in uniqueid_dict:
            if uniqueid_dict[k] == t['uniqueid'].get(k, None):
                # Found match
                return t['tvshowid']

    # Haven't found a match
    return None


def get_movieid_from_uniqueid(uniqueid_dict):
    """
        Return movieid from searching for matching at least one of the uniqueid keys in the supplied dict

    :param uniqueid_dict:
    :return int or none:
    """
    for t in get_results_from_kodi_jsonrpc("VideoLibrary.GetMovies", "movies", ["uniqueid"]):
        # Have to scan as no ability to filter search uniqueid
        for k in uniqueid_dict:
            if uniqueid_dict[k] == t['uniqueid'].get(k, None):
                # Found match
                return t['movieid']

    # Haven't found a match
    return None


def scan_video_library(scan_path=None):
    """
        Trigger scan of kodi video library, using supplied path if provided

    :param scan_path:
    :return:
    """
    payload = {"method": "VideoLibrary.Scan", "params": {"showdialogs": True}}

    # Ensure path has '/' or '\' ending
    # Try to parse the path looking for URL
    try:
        exploded_path = urlparse.urlparse(scan_path)
        if exploded_path.scheme:
            # Detected URL
            if not scan_path.endswith('/'):
                scan_path = scan_path + '/'
        else:
            # Non-URL
            if scan_path.startswith('/') and not scan_path.endswith('/'):
                scan_path = scan_path + '/'
            elif scan_path.startswith('\\') and not scan_path.endswith('\\'):
                scan_path = scan_path + '\\'
    except:
        # Carry on as is
        pass

    if scan_path:
        payload["params"]["directory"] = scan_path

    issue_kodi_jsonrpc_command(payload)
    return True




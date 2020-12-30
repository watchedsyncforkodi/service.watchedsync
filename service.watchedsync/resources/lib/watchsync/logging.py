#
#
# Copyright 2019-2020 CSS
#
# This software is unpublished work which is proprietary to CSS.
# Any distribution is strictly forbidden
#
#

import xbmc
import xbmcaddon

__addon__ = xbmcaddon.Addon()
__addonversion__ = __addon__.getAddonInfo('version').decode('utf-8')
__addonid__ = __addon__.getAddonInfo('id').decode('utf-8')
__addonpath__ = __addon__.getAddonInfo('path').decode('utf-8')


class KodiLog(object):
    def __init__(self, module_name, class_name=None):
        self.module_name = module_name
        self.class_name = class_name

    def debug(self, msg):
        self._log(msg, xbmc.LOGDEBUG)

    def info(self, msg):
        # In v18 LOGINFO is not printed in kodi.log. Require LOGNOTICE level
        self._log(msg, xbmc.LOGNOTICE)

    def warning(self, msg):
        self._log(msg, xbmc.LOGWARNING)

    def error(self, msg):
        self._log(msg, xbmc.LOGERROR)

    def _log(self, msg, level):

        if isinstance(msg, unicode):
            msg = msg.encode('utf-8')

        if level == xbmc.LOGDEBUG:
            xbmc.log("[{}][{}][{}] {}".format(__addonid__, self.module_name, self.class_name, msg.__str__()), level)
        else:
            xbmc.log("[{}] {}".format(__addonid__, msg.__str__()), level)


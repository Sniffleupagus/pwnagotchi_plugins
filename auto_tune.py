import logging
import random

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.utils


class auto_tune(plugins.Plugin):
    __author__ = 'sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin that adjust AUTO mode parameters'

    def __init__(self):
        self._histogram = {'loops': 0 }
        self._unscanned_channels = []
        self._active_channels = []
        self._agent = None

    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    #def on_webhook(self, path, request):
    #    # display personality parameters for editing
    #    # show statistic per channel, etc
    #    pass

    # called when the plugin is loaded
    def on_loaded(self):
        pass

    def on_ready(self, agent):
        self._agent = agent
        if agent._config['ai']['enabled']:
            logging.info("Auto_Tune is inactive when AI is enabled.")
        else:
            logging.info("Auto_Tune is active! options = %s" % repr(self.options))

    # called before the plugin is unloaded
    #def on_unload(self, ui):
    #    pass

    # called when the agent refreshed its access points list
    def on_wifi_update(self, agent, access_points):
        # check aps and update active channels
        try:
            if agent._config['ai']['enabled']:
                return

            active_channels = []
            self._histogram["loops"] = self._histogram["loops"] + 1
            for ap in access_points:
                ch = ap['channel']
                logging.debug("%s %d" % (ap['hostname'], ch))
                if ch not in active_channels:
                    active_channels.append(ch)
                    if ch in self._unscanned_channels:
                        self._unscanned_channels.remove(ch)
                self._histogram[ch] = 1 if ch not in self._histogram else self._histogram[ch]+1

            self._active_channels = active_channels
            logging.info("Histo: %s" % repr(self._histogram))
        except Exception as e:
            logging.exception(e)

    # called when the agent refreshed an unfiltered access point list
    # this list contains all access points that were detected BEFORE filtering
    #def on_unfiltered_ap_list(self, agent, access_points):
    #    pass

    # called when an epoch is over (where an epoch is a single loop of the main algorithm)
    def on_epoch(self, agent, epoch, epoch_data):
        # pick set of channels for next time
        if agent._config['ai']['enabled']:
            return

        try:
            next_channels = self._active_channels.copy()
            n = 3 if "extra_channels" not in self.options else self.options["extra_channels"]
            if len(self._unscanned_channels) == 0:
                self._unscanned_channels = pwnagotchi.utils.iface_channels(agent._config['main']['iface'])

            for i in range(n):
                if len(self._unscanned_channels):
                    ch = random.choice(list(self._unscanned_channels))
                    self._unscanned_channels.remove(ch)
                    next_channels.append(ch)
            # update live config
            agent._config['personality']['channels'] = next_channels
            logging.info("Active: %s, Next scan: %s, yet unscanned: %d %s" % (self._active_channels, next_channels, len(self._unscanned_channels), self._unscanned_channels))
        except Exception as e:
            logging.exception(e)
            

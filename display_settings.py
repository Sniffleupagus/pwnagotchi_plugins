import logging

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue, Text
from pwnagotchi.ui.view import BLACK, WHITE
import pwnagotchi.ui.fonts as fonts


class DisplaySettings(plugins.Plugin):
    __author__ = 'Sniffleupagus'
    __version__ = '1.0.1'
    __license__ = 'GPL3'
    __description__ = 'Control backlight, and maybe other settings for displays.'

    def __init__(self):
        logging.debug("DisplaySettings plugin created")
        self._ui = None
        self._original_color = BLACK
        self.change_elements = ['face']

    def set_background(self, color):
        try:
            logging.debug("Set BG to %s" % (color))
            if not self._ui:
                return
            if hasattr(self._ui, "_white"):
                self._ui._white = color
            elif hasattr(self._ui, "set_backgroundcolor"):
                self._ui.set_backgroundcolor(color)
            for e in self.change_elements:
                if e in self._ui._state._state and hasattr(self._ui._state._state[e], 'setBackground'):
                    self._ui._state._state[e].setBackground(color)
        except Exception as e:
            logging.exception(e)

    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        # show sliders and control and shit :)
        pass

    # called when the plugin is loaded
    def on_loaded(self):
        logging.info("DisplaySettings options = %s" % self.options)
        self.change_elements = self.options.get("change_elements", ['face'])

    # called before the plugin is unloaded
    def on_unload(self, ui):
        try:
            self.set_background(self._original_color)
        except Exception as e:
            logging.exception(e)
        logging.info("goodbye")

    # called to setup the ui elements
    def on_ui_setup(self, ui):
      try:
        self._ui = ui
        if hasattr(ui, "_white"):
            self._original_color = ui._white

        self._display = ui._implementation
        if hasattr(self._display, "get_backlight"):
            logging.info("UI backlight ready")
        if hasattr(self._ui, "set_backgroundcolor"):
            logging.info("UI backgrounds ready")
        elif  hasattr(self._ui, "_white"):
            logging.info("UI backgrounds ok")
        # add custom UI elements
        self.set_background("#708090")
      except Exception as err:
          logging.warn("Display: %s, err: %s" % (repr(self._display), repr(err)))
    
    # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        pass
    
    # called when the hardware display setup is done, display is an hardware specific object
    def on_display_setup(self, display):
        self._display = display
        #if hasattr(display, "get_backlight"):
            
        pass

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        logging.info("unit is ready")
        # you can run custom bettercap commands if you want
        #   agent.run('ble.recon on')
        # or set a custom state
        #   agent.set_bored()

    # called when the AI finished loading
    def on_ai_ready(self, agent):
        pass

    # called when the AI finds a new set of parameters
    def on_ai_policy(self, agent, policy):
        pass

    # called when the AI starts training for a given number of epochs
    def on_ai_training_start(self, agent, epochs):
        pass

    # called after the AI completed a training epoch
    def on_ai_training_step(self, agent, _locals, _globals):
        pass

    # called when the AI has done training
    def on_ai_training_end(self, agent):
        pass

    # called when the AI got the best reward so far
    def on_ai_best_reward(self, agent, reward):
        self.set_background("#708090")

    # called when the AI got the worst reward so far
    def on_ai_worst_reward(self, agent, reward):
        self.set_background("#203040")

    # called when a non overlapping wifi channel is found to be free
    def on_free_channel(self, agent, channel):
        pass

    # called when the status is set to bored
    def on_bored(self, agent):
        self.set_background("#308080")

    # called when the status is set to sad
    def on_sad(self, agent):
        self.set_background("#302080")

    # called when the status is set to excited
    def on_excited(self, agent):
        try:
            if hasattr(self._display, "set_backlight"):
                self._display.set_backlight(0.8)
            self.set_background("#c08080")
        except Exception as err:
            logging.warn(repr(err))
        pass

    # called when the status is set to lonely
    def on_lonely(self, agent):
        try:
            if hasattr(self._display, "set_backlight"):
                self._display.set_backlight(0.4)
            self.set_background("#101090")
        except Exception as err:
            logging.warn(repr(err))
        pass

    # called when the agent is rebooting the board
    def on_rebooting(self, agent):
        self.set_background("#101010")

    # called when the agent is waiting for t seconds
    def on_wait(self, agent, t):
        try:
            if hasattr(self._display, "set_backlight"):
                self._display.set_backlight(0.2)
            self.set_background(self._original_color)
        except Exception as err:
            logging.warn(repr(err))
        pass

    # called when the agent is sleeping for t seconds
    def on_sleep(self, agent, t):
        try:
            if hasattr(self._display, "set_backlight"):
                self._display.set_backlight(0.1)
            self.set_background(self._original_color)
        except Exception as err:
            logging.warn(repr(err))
        pass

    # called when the agent refreshed its access points list
    def on_wifi_update(self, agent, access_points):
        try:
            if hasattr(self._display, "set_backlight"):
                self._display.set_backlight(0.6)
            self.set_background("#208030")
        except Exception as err:
            logging.warn(repr(err))
        pass

    # called when the agent refreshed an unfiltered access point list
    # this list contains all access points that were detected BEFORE filtering
    def on_unfiltered_ap_list(self, agent, access_points):
        pass

    # called when the agent is sending an association frame
    def on_association(self, agent, access_point):
        try:
            if hasattr(self._display, "set_backlight"):
                self._display.set_backlight(0.8)
            self.set_background("#308020")
        except Exception as err:
            logging.warn(repr(err))
        pass

    # called when the agent is deauthenticating a client station from an AP
    def on_deauthentication(self, agent, access_point, client_station):
        self.set_background("#400000")

    # callend when the agent is tuning on a specific channel
    def on_channel_hop(self, agent, channel):
        self.set_background("#00a000")

    # called when a new handshake is captured, access_point and client_station are json objects
    # if the agent could match the BSSIDs to the current list, otherwise they are just the strings of the BSSIDs
    def on_handshake(self, agent, filename, access_point, client_station):
        try:
            if hasattr(self._display, "set_backlight"):
                self._display.set_backlight(1.0)
            self.set_background("#00FF00")
        except Exception as err:
            logging.warn(repr(err))
        pass

    # revert to normal background color on_internet for MANU, on_epoch for AUTO
    def on_internet_available(self, agent):
        self.set_background(self._original_color)

    def on_epoch(self, agent, epoch, epoch_data):
        self.set_background(self._original_color)

    # called when a new peer is detected
    def on_peer_detected(self, agent, peer):
        try:
            if hasattr(self._display, "set_backlight"):
                self._display.set_backlight(1.0)
            self.set_background("#008080")
        except Exception as err:
            logging.warn(repr(err))
        pass

    # called when a known peer is lost
    def on_peer_lost(self, agent, peer):
        self.set_background("#800080")

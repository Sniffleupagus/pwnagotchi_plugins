import logging

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue, Text
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ai.epoch import Epoch


class pause_recon(plugins.Plugin):
    __author__ = 'Sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Override pwnagotchi.agent calls to pause recon without triggering blind reboots'
    
    def __init__(self):
      try:
        logging.info("%s created" % (type(self).__name__))
      except Exception as e:
          logging.exception(e)
      try:
        self._ui = None
        self._agent = None
        self.options = dict()
        self._ui_elements = {}
        self._orig_functions = {}
        self._start_epoch = 0
      except Exception as e:
          logging.exception(e)

    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        # will eventually have buttons to disable recon, config wifi, etc
        pass

    # called when the plugin is loaded
    def on_loaded(self):
        logging.warning("WARNING: Educational uses only! options = %s" % self.options)

    def add_ui_element(self, ui, name, element):
        try:
            ui.add_element(name, element)
            self._ui_elements[name] = element
        except Exception as e:
            logging.exception(e)

    def remove_ui_element(self, ui, name):
        try:
            ui.remove_element(name)
            self._ui_elements[name] = None
        except Exception as e:
            logging.exception(e)
        
    # called before the plugin is unloaded
    def on_unload(self, ui):
        try:
            with ui._lock:
                self.un_hijack(ui._agent)
                logging.info("\t\t\tUnhijacked")
        except Exception as e:
            logging.exception(e)

        try:
            for e in self._ui_elements.keys():
                try:
                    if self._ui_elements[e]:
                        with ui._lock:
                            self.remove_ui_element(ui, e)
                except Exception as err:
                    logging.exception("remove element %s: %s" % (e, err))
            logging.info("pause_recon unloaded")
        except Exception as err:
            logging.exception("Unloading: %s" % (err))

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._agent = agent
        logging.info("unit is ready")
        # you can run custom bettercap commands if you want
        #   agent.run('ble.recon on')
        # or set a custom state
        #   agent.set_bored()

    # called to set up the ui elements
    def on_ui_setup(self, ui):
        self._ui = ui
        # add custom UI elements
        with ui._lock:
            try:
                self.add_ui_element(ui, 'pause_stats', Text(color=BLACK, value='Recon Paused for 0 epochs',
                                                            position=(0, 60),
                                                            font=fonts.Small))
            except Exception as e:
                logging.exception(e)

        if not self._agent:
            self._agent = ui._agent

        if self._agent:
            self.hijack(self._agent)
            self._start_epoch = self._agent._epoch.epoch

    def hijack(self, agent):
        try:
            def hj_observe(self, aps, peers):
                """ Epoch.observe() sets the blind_for and inactive_for, which trigger
                    actions that should be avoided while recon is disabled
                    Override Epoch.observe() with hj_observe, which calls the original,
                    then sets those stats to be 0.  Also sets num_missed so is_stale()
                    will be true and attacks get skipped."""
                logging.debug("HJ observe: %s, %s, %s" % (self, len(aps), len(peers)))
                try:
                    if hasattr(self, 'hj_funcs'):
                        o_func = self.hj_funcs.get('observe', None)
                        if o_func:
                            o_func(aps, peers)    # call real observe function, pwnagotchi.ai.epoch.observe()
                        # override some of the stats
                        if self.blind_for > 0:
                            logging.warn("Resetting blind count from %d" % (self.blind_for))
                            self.blind_for = 0
                        if self.inactive_for > 0:
                            logging.warn("Resetting inactive count from %d" % (self.inactive_for))
                            self.inactive_for = 0
                        if self.sad_for > 0:
                            logging.warn("Resetting sad count from %d" % (self.sad_for))
                            self.sad_for = 0
                        if self.bored_for > 0:
                            logging.warn("Resetting bored count from %d" % (self.bored_for))
                            self.bored_for = 0
                        # set high enough to be stale, so attacks get skipped
                        self.num_missed = self.config['personality']['max_misses_for_recon'] + 1
                    else:
                        logging.error("ep has no orig_observe: %s" % (repr(self)))
                except Exception as e:
                    logging.exception(e)
                    
            ep = agent._epoch
            if ep:
                # set num_missed to avoid attacks
                ep.num_missed = ep.config['personality']['max_misses_for_recon'] + 1

                # dictionary to keep track of function(s) overridden
                if hasattr(ep, 'hj_funcs'):
                    logging.error("Already hijacked. wtf?")
                else:
                    ep.hj_funcs = {}

                # save the origional. Do not overwrite if one is already saved (since that's the OG original)
                if not 'observe' in ep.hj_funcs:
                    ep.hj_funcs['observe'] = ep.observe

                # override the Epoch.observe function with hj_observe
                ep.observe = hj_observe.__get__(ep, Epoch)
                logging.info("Hijacked recon functions %s" % (ep.hj_funcs))
                        
            try:
                r = agent.run('wifi.recon off')
                logging.info("Wifi recon off: %s" % (r))
            except Exception as e:
                logging.error("Disabling recon: %s" % (e))
        except Exception as e:
            logging.exception(e)

    def un_hijack(self, agent):
        try:
            if not agent:
                logging.info("No agent")
                return
            ep = agent._epoch
            ep.num_missed = 0
            logging.info("Unjacking %s" % (ep))
            if hasattr(ep, 'hj_funcs'):
                ep.observe = ep.hj_funcs['observe']
                if ep.observe == ep.hj_funcs['observe']:
                    logging.info("Restored Epoch.observe")
                    del ep.hj_funcs['observe']
                else:
                    logging.error("Failed to restore observe function")
                del ep.hj_funcs
            else:
                logging.error("\t\t\tNothing to unjack")

            try:
                logging.info("Unpausing recon")
                r = agent.run('wifi.recon on')
                logging.info("Wifi recon on: %s" % (r))
            except Exception as e:
                logging.error("Enabling recon: %s" % (e))
        except Exception as e:
            logging.exception(e)

    # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        if ui._agent:
            ui.set('pause_stats', "Recon paused for %s epochs" % (ui._agent._epoch.epoch - self._start_epoch))

    # called when an epoch is over (where an epoch is a single loop of the main algorithm)
    def on_epoch(self, agent, epoch, epoch_data):
        try:
            self._ui.set('pause_stats', "Epochs %s: %s" % (epoch, epoch_data))
        except Exception as e:
            logging.exception(e)
        pass


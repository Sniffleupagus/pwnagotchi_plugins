#
# Speech output for pwnagotchi
#
# extending the led.py plugin to run through TTS instead of blinking
#

from threading import Event
import _thread
import random
import logging
import time
import os
import subprocess
import json

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts

class SpeakToMe(plugins.Plugin):
    __author__ = 'sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Speech output plugin'

    def _speak(self, msg):
        if len(msg) > 0:
            self.logger.info("[SPEAK] '%s'" % (msg))

            voice = subprocess.run(['espeak-ng', '-vStorm+f5', '--stdin'], stdout=subprocess.PIPE, input=msg, encoding='ascii')
            
    # thread stuff copied from plugins/default/led.py
    # queue a message
    #   but if there is one already (busy) then don't
    def _queue_message(self, message):
        if not self._is_busy:
            self._message = message
            self._event.set()
            self.logger.debug("[Morse] message '%s' set", message)
        else:
            self.logger.debug("[Morse] skipping '%s' because the worker is busy", message)

    def _worker(self):
        while self._keep_going:
            self._event.wait()
            self._event.clear()

            if self._message == "QUITXXXQUIT":
                break

            self._is_busy = True
            self.logger.debug("Worker loop")

            try:
                self._speak(self._message)
                self.logger.debug("[Speak] spoke")
            except Exception as e:
                self.logger.warn("[Speak] error while speaking: %s" % repr(e))

            finally:
                self._is_busy = False

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.debug("[Speak] To Me plugin initializing")
        self._is_busy = False
        self._keep_going = True
        self._event = Event()
        self._message = None


    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        self.logger.info("[Morse] Web hook: %s" % repr(request))
        return "<html><body>Woohoo!</body></html>"

    # called when the plugin is loaded
    def on_loaded(self):
        try:
            self._is_busy = False

            self._keep_going = True
            _thread.start_new_thread(self._worker, ())
            greetings = ["Welcome back!", "Welcome aboard, Captain.", "Hey! When did you get here?", "Oh hi.", "Weird. How did I get here?", "Oh boy."]
            self._queue_message(random.choice(greetings))
            self.logger.info("[SpeakToMe] plugin loaded")
        except Exception as err:
            self.logger.warn("[SpeakToMe] loading error: %s" % repr(err))

    # called before the plugin is unloaded
    def on_unload(self, ui):
        self._keep_going = False
        self._queue_message('Pasta la vista, baby')

        pass

    # called when there's internet connectivity
    def on_internet_available(self, agent):
        pass

    # called when the hardware display setup is done, display is an hardware specific object
    def on_display_setup(self, display):
        pass

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._queue_message("READY! OK!")
        # you can run custom bettercap commands if you want
        #   agent.run('ble.recon on')
        # or set a custom state
        #   agent.set_bored()

    # called when the AI finished loading
    def on_ai_ready(self, agent):
        self._queue_message("My brain is fully functional")
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
        self._queue_message("Best day ever %s" % repr(reward))
        pass

    # called when the AI got the worst reward so far
    def on_ai_worst_reward(self, agent, reward):
        self._queue_message("This is terrible %s" % repr(reward))
        pass

    # called by bettercap events
    def on_bcap_ble_device_new(self, agent, event):
        self._queue_message("NEW BLE")
        pass
    
    # called when a non overlapping wifi channel is found to be free
    def on_free_channel(self, agent, channel):
        pass

    # called when the status is set to bored
    def on_bored(self, agent):
        pass

    # called when the status is set to sad
    def on_sad(self, agent):
        self._queue_message("Woe is me")
        pass

    # called when the status is set to excited
    def on_excited(self, agent):
        pass

    # called when the status is set to lonely
    def on_lonely(self, agent):
        pass

    # called when the agent is rebooting the board
    def on_rebooting(self, agent):
        self._queue_message("Hey Paul, what does this button do?")
        pass

    # called when the agent refreshed its access points list
    def on_wifi_update(self, agent, access_points):
        pass

    # called when the agent refreshed an unfiltered access point list
    # this list contains all access points that were detected BEFORE filtering
    def on_unfiltered_ap_list(self, agent, access_points):
        pass

    # called when the agent is sending an association frame
    def on_association(self, agent, access_point):
        #self._queue_message("Associate to %s on channel %d" % (access_point['hostname'], access_point['channel']))
        #self.logger.info("[Speak] access_point = '%s'" % repr(access_point))
        pass

    # called when the agent is deauthenticating a client station from an AP
    def on_deauthentication(self, agent, access_point, client_station):
        self._queue_message("I just booted someone")
        self.logger.info("[Speak] access_point = '%s', client= %s" % (repr(access_point), repr(client_station)))
        pass

    # callend when the agent is tuning on a specific channel
    def on_channel_hop(self, agent, channel):
        pass

    # called when a new handshake is captured, access_point and client_station are json objects
    # if the agent could match the BSSIDs to the current list, otherwise they are just the strings of the BSSIDs
    def on_handshake(self, agent, filename, access_point, client_station):
        self._queue_message("I poned one!")
        self.logger.info("[Speak] access_point = '%s', client= %s" % (repr(access_point), repr(client_station)))
        pass

    # called when an epoch is over (where an epoch is a single loop of the main algorithm)
    def on_epoch(self, agent, epoch, epoch_data):
        pass

    # called when a new peer is detected
    def on_peer_detected(self, agent, peer):
        try:
            self.logger.info("[Speak] peer found = '%s', %s" % (peer.full_name(), peer.adv))
            self._queue_message("Hello %s" % peer.name())
        except Exception as e:
            self.logger.exception(e)

    # called when a known peer is lost
    def on_peer_lost(self, agent, peer):
        self.logger.info("[Speak] peer lost = '%s'" % json.dumps(peer))
        pass

    def on_bcap_wifi_ap_new(self, agent, event):
        logging.info("[Speak] New AP: %s" % repr(event["data"]))

    def on_bcap_wifi_ap_lost(self, agent, event):
        logging.info("[Speak] lost AP: %s" % repr(event["data"]))

    def on_bcap_wifi_client_new(self, agent, event):
        logging.info("[Speak] %s New Client: %s" % (event["data"]["AP"]["hostname"], repr(event["data"]["Client"])))

    def on_bcap_wifi_client_lost(self, agent, event):
        logging.info("[Speak] %s lost Client: %s" % repr(event["data"]["Client"]))

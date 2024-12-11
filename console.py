import logging
import time
from datetime import datetime

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import Text, Line, LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts

from PIL import ImageFont

class Console(plugins.Plugin):
    __author__ = 'Sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A console scrolling status updates.'

    def __init__(self):
        self._console = [ "%s - Pwnagotchi Console %s" % (datetime.now().strftime('%c'), self.__version__) ]
        self._ui_elements = []       # keep track of UI elements created in on_ui_setup for easy removal in on_unload
        self._last_status = None

    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
#    def on_webhook(self, path, request):
#        pass


    def addConsole(self, msg):
        try:
            logging.debug("console: %s" % msg)
            now = datetime.now().strftime('%X')
            self._console.append('%s %s' % (now, msg))

            if len(self._console) > self.options['showLines']:
                m = self._console.pop(0)
                logging.debug("Removed %s" % m)
                
        except Exception as e:
            logging.exception(repr(e))



    # called when the plugin is loaded
    def on_loaded(self):
        logging.warning("Console options = " % self.options)

        self.options['showLines'] = self.options.get('showLines', 15)

    # called before the plugin is unloaded
    def on_unload(self, ui):
        try:
            # remove UI elements
            i = 0
            with ui._lock:
                for n in self._ui_elements:
                    ui.remove_element(n)
                    logging.info("Removed %s" % repr(n))
                    i += 1
            if i: logging.info("plugin unloaded %d elements" % i)
            
        except Exception as e:
            logging.warning("Unload: %s" % e)

    # called hen there's internet connectivity
    def on_internet_available(self, agent):
        pass

    # called to setup the ui elements
    def on_ui_setup(self, ui):
        # add custom UI elements
        pos = self.options.get('position', (20,100))
        self.options['position'] = pos
        color = self.options.get('color', 'Blue')
        font_height = self.options.get('font_size', int(ui._height/60))
        
        confont = ImageFont.truetype(fonts.FONT_NAME, size=font_height)
        ui.add_element('pwn-console', Text(color=color, value='--', position=(pos[0],pos[1]), font=fonts.Medium))
        self._ui_elements.append('pwn-console')

    # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        st = ui.get('status')
        if st != "" and st != '...' and st != self._last_status:
            self._last_status = st
            self.addConsole(st)

        ui.set('pwn-console', '\n'.join(self._console[:self.options['showLines']]))

    # called when the hardware display setup is done, display is an hardware specific object
    def on_display_setup(self, display):
        pass

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._agent = agent
        self.addConsole("Ready to pwn")

    # called when the AI finished loading
    def on_ai_ready(self, agent):
        #self.addConsole("Neural net ready.")
        pass

    # called when the AI finds a new set of parameters
    def on_ai_policy(self, agent, policy):
        pass

    # called when the AI starts training for a given number of epochs
    def on_ai_training_start(self, agent, epochs):
        self.addConsole("Begin training session")
        self._train_epoch = 0

    # called after the AI completed a training epoch
    def on_ai_training_step(self, agent, _locals, _globals):
        pass

    # called when the AI has done training
    def on_ai_training_end(self, agent):
        self.addConsole("End AI training session")


    # called when the AI got the best reward so far
    def on_ai_best_reward(self, agent, reward):
        self.addConsole("Best reward: %0.3f" % reward)

    # called when the AI got the worst reward so far
    def on_ai_worst_reward(self, agent, reward):
        self.addConsole("Worst reward: %0.3f" % reward)


    # called when a non overlapping wifi channel is found to be free
    def on_free_channel(self, agent, channel):
        pass

    # called when the status is set to bored
    def on_bored(self, agent):
        pass

    # called when the status is set to sad
    def on_sad(self, agent):
        pass

    # called when the status is set to excited
    def on_excited(self, agent):
        pass

    # called when the status is set to lonely
    def on_lonely(self, agent):
        pass

    # called when the agent is rebooting the board
    def on_rebooting(self, agent):
        self.addConsole("Rebooting.")

    # called when the agent is waiting for t seconds
    def on_wait(self, agent, t):
        pass

    # called when the agent is sleeping for t seconds
    def on_sleep(self, agent, t):
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
        #self.addConsole("A->%s" % (access_point['hostname']))
        pass

    # called when the agent is deauthenticating a client station from an AP
    def on_deauthentication(self, agent, access_point, client_station):
        #self.addConsole("D->%s %s" % (access_point['hostname'], client_station['hostname']))
        pass

    # callend when the agent is tuning on a specific channel
    def on_channel_hop(self, agent, channel):
        pass

    # called when a new handshake is captured, access_point and client_station are json objects
    # if the agent could match the BSSIDs to the current list, otherwise they are just the strings of the BSSIDs
    def on_handshake(self, agent, filename, access_point, client_station):
        self.addConsole("H->%s" % (access_point.get('hostname', "???")))


    # called when an epoch is over (where an epoch is a single loop of the main algorithm)
    def on_epoch(self, agent, epoch, epoch_data):
        pass

    # called when a new peer is detected
    def on_peer_detected(self, agent, peer):
        logging.info("Peer: %s" % repr(peer))
        self.addConsole("Peer: %s" % peer.adv.get('name', '???'))

    # called when a known peer is lost
    def on_peer_lost(self, agent, peer):
        logging.info("Peer: %s" % repr(peer))
        self.addConsole("Bye: %s" % peer.adv.get('name', '???'))
        
    def on_bcap_wifi_ap_new(self, agent, event):
        ap = event['data']
        self.addConsole("New AP: %s" % ap['hostname'])

    def on_bcap_wifi_ap_lost(self, agent, event):
        ap = event['data']
        self.addConsole("Bye AP: %s" % ap['hostname'])


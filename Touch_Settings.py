import logging
import signal
import sys
import threading
import time
import os
from subprocess import Popen, PIPE

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import *
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts

#
# Make an API for other plugins to use
#
# try:
#    import "Touch_Settings"
#    TS = Touch_Settings_API()
#    TS.addZone(...)
#
# except Exception as e:
#    logging.info("No touchscreen available")
#    TS = None
#


class Touch_Settings(plugins.Plugin):
    __author__ = 'Sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Use touchscreen input to toggle settings.'

    #
    # functions for other plugins to add touch function
    #

    #
    # if this fails, don't bother with the rest
    #
    def registerTouch(self, plugin):
        # add plugin to the list
        return True

    def unregisterTouch(self, plugin):
        # take plugin off the list and remove all associated touch zones
        return True
    
    # makeUIElementTouchable
    #
    # after creating a UI element in call this function to assign a touch handler to the element
    #
    #  try:
    #      touchscreen.makeUITouchable
    #
    #
    def makeUITouchable(self, ui, plugin, element_name, action, args=()):
        # find ui element

        # get bounding box

        # does it already exist?
        #   one per plugin per element. new ones replace old
        name = plugin.name + '-' + element_name
        add_touch_zone(self, ui, name, bbox, action, args):

    
    def __init__(self):
        self._ts_thread = None
        self.keepGoing = False
        self._view = None
        self._agent = None
        self.touchscreen = None
        self._ui_elements = []
        self.touch_zones = {}
        logging.basicConfig(format='%(asctime)-15s %(levelname)s [%(filename)s:%(lineno)d] %(funcName)s: %(message)s')

        logging.debug("plugin created")

    def touchScreenHandler(self, ts_device=None):
        try:
            if not ts_device:
                evtest = Popen(("/usr/bin/evtest"), stdout=PIPE, stderr=PIPE,
                               universal_newlines=True)
                while True:
                    output = str(evtest.stderr.readline())
                    if not output:
                        break
                    output.rstrip('\n')
                    logging.debug("Looking for screen: %s" % repr(output))
                    try:
                        if "Touchscreen" in output:
                            (ts_device, rest) = output.split(':', 2)
                            ts_device = str(ts_device)
                            logging.debug("Found device %s" % ts_device)
                            break
                    except Exception as e:
                        logging.error(repr(e))

                if not ts_device:
                    logging.error("Unable to find touch screen device")
                    return
                else:
                    logging.info("Touchscreen == %s" % ts_device)
    
                cmd = "/usr/bin/ts_print"
                os.environ["TSLIB_TSDEVICE"] = "%s" % ts_device
                #self.touchscreen = os.popen(cmd)
                self.touchscreen = Popen(['stdbuf', '-o0', cmd], env=os.environ, stdout=PIPE, universal_newlines=True, shell=False)
                if self.touchscreen:
                    self.keepGoing = True
                    for output in self.touchscreen.stdout:
                        if not output:
                            break
                        output = output.strip()
                        logging.debug("Touch '%s'" % output)
                        (tstamp, x, y, depth) = output.split()
                        x = int(x)
                        y = int(y)
                        depth = int(depth)
                        if tstamp:
                            logging.debug("Touch %s at %s, %s" % (depth, x, y))
                            self.process_touch([int(x),int(y)], depth)
                else:
                    logging.info("No touchscreen?")
            logging.info("ts_print exited")
            #err = self.touchscreen.stderr.read()
            #logging.info(err)
        except Exception as e:
            logging.info("Handler: %s" % repr(e))
    
    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        # define touch zones and actions
        pass

    # called when the plugin is loaded
    def on_loaded(self):
        logging.info("loaded with options = " % self.options)

    # called before the plugin is unloaded
    def on_unload(self, ui):
        try:
            # stop the thread
            self.keepGoing = False
            if self._ts_thread:
                logging.debug("Waiting for thread to exit")
                if self.touchscreen:
                    logging.debug("TERM to %s" % self.touchscreen.pid)
                    os.kill(self.touchscreen.pid, signal.SIGTERM)
                self._ts_thread.join()
                logging.debug("And its done.")
            
            # remove all ui elements
            if ui.has_element('UPS'):
                ui.remove_element('UPS')
            
            i = 0
            for n in self._ui_elements:
                ui.remove_element(n)
                logging.info("Removed %s" % repr(n))
                i += 1
            logging.info("plugin unloaded %d elements" % i)
        except Exception as e:
            logging.error("%s" % repr(e))

    # called hen there's internet connectivity
    def on_internet_available(self, agent):
        pass

    def add_touch_zone(self, ui, zname, zbox=[0,0,100,100], zaction=None, zargs=()):
        try:
            self.touch_zones[zname] = {'box':zbox, 'action': zaction, 'args':zargs}
            # draw a box around the zone for now
            ui.add_element('%s_box' % (zname), Rect(zbox, color=BLACK))
            self._ui_elements.append('%s_box' % zname)
            logging.info("have %d elements" % len(self._ui_elements))
            logging.info("Zone %s: %s" % repr(zname, self.touch_zones[zname]))
        except Exception as e:
            logging("%s" % repr(e))

    def pointInBox(self, point, box):
        logging.debug("is %s in %s" % (repr(point), repr(box)))
        return (point[0] >= box[0] and point[0] <= box[2] and point[1] >= box[1] and point[1] <= box[3])
        
    def process_touch(self, tpoint, depth):
        logging.debug("PT: %s" % repr(self.touch_zones))
        if int(depth) > 0:
            return
        for z in self.touch_zones:
            zone = self.touch_zones[z]
            if self.pointInBox(tpoint, zone['box']):
                logging.info("Zone %s: %s @ %s in %s: calls %s(%s)" % (depth,
                                                                       repr(z),
                                                                       repr(tpoint),
                                                                       repr(zone['box']),
                                                                       repr(zone['action']), repr(zone['args'])))
                break # stop at first matching action?
        
    # called to setup the ui elements
    def on_ui_setup(self, ui):
        # add custom UI elements
        self.add_touch_zone(ui, "test", [250, 50, 350, 150], "logging.info", ("TEST"))

    # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        some_voltage = 0.1
        some_capacity = 100.0
        ui.set('ups', "%4.2fV/%2i%%" % (some_voltage, some_capacity))

    # called when the hardware display setup is done, display is an hardware specific object
    def on_display_setup(self, display):
        pass

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        # start thread handler
        try:
            self._ts_thread = threading.Thread(target=self.touchScreenHandler, args=(), daemon=True)
            if not self._ts_thread:
                logging.info("Thread failed?")

            #self.touchScreenHandler()
            logging.info("starting ts_print thread")
            self._ts_thread.start()
            logging.info("started thread")

            logging.info("unit is ready")
        except Exception as e:
            logging.error(repr(e))

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
        pass

    # called when the AI got the worst reward so far
    def on_ai_worst_reward(self, agent, reward):
        pass

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
        pass

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
        pass

    # called when the agent is deauthenticating a client station from an AP
    def on_deauthentication(self, agent, access_point, client_station):
        pass

    # callend when the agent is tuning on a specific channel
    def on_channel_hop(self, agent, channel):
        pass

    # called when a new handshake is captured, access_point and client_station are json objects
    # if the agent could match the BSSIDs to the current list, otherwise they are just the strings of the BSSIDs
    def on_handshake(self, agent, filename, access_point, client_station):
        pass

    # called when an epoch is over (where an epoch is a single loop of the main algorithm)
    def on_epoch(self, agent, epoch, epoch_data):
        pass

    # called when a new peer is detected
    def on_peer_detected(self, agent, peer):
        pass

    # called when a known peer is lost
    def on_peer_lost(self, agent, peer):
        pass


if __name__ == "__main__":

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    #handler.setLevel(logging.DEBUG)
    #formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    #handler.setFormatter(formatter)
    #root.addHandler(handler)    
    
    ts = Touch_Settings()

    ts.touchScreenHandler()

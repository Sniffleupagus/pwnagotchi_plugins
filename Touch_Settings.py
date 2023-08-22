import logging
import signal
import sys
import threading
import time
import os
import RPi.GPIO as GPIO
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

    # plugins that want touchscreen can implement these callback functions:
    #
    # on_touch_ready(self, touchscreen)
    #
    # - called when the touchscreen has been started, during Your plugin can use it to know the touchscreen
    #   is available.
    #
    # on_touch_press(self, ts, ui, ui_element, touch_data)
    # on_touch_release(self, ts, ui, ui_element, touch_data)
    #
    # # simplified "button" interface. on_touchscreen_press is the initial touch,
    # # then supress all the wiggling, and on_touchscreen_release is the "0" when
    # # your finger comes off the screen. Much more efficient, if you are just pressing
    # # something to do an action
    #
    #
    # on_touch_move(self, ts, ui, ui_element, touch_data)
    #
    # # This will get every position update between the press and release (every finger wiggle).
    # # alsmost raw touchscreen access. This does not get called for the press or release, just
    # # all the in-betweens.
    #
    # # variables:
    #
    #   self = your plugin instance
    #
    #   ts, touchscreen = this touchscreen plugin instance
    #
    #   ui = pwnagotchi view/ui like in other plugin handlers
    #
    #   ui_element = name of display element where touch occurred. NOT IMPLEMENTED YET!!!!!
    #
    #   touch_data = { point: [x,y], pressure: p }
    #     x,y = point of touch
    #     p = 1-255 (i think) pressure or area or something like that
    #         0 when released
    #
    #
    # Future improvements:
    #
    # - make an array called Touch_Elements listing the UI elements of interest
    #
    # self.Touch_Elements = [ "face", "uptime", "assoc_count", "deauth_count" ]
    #
    # if a touch event occurs inside a ui_element in a plugin's Touch_Elements array,
    # on_touch* will get called (to all plugins implementing it, so check the element before blindly
    # processing a touch

    # - if user has buttons available, one can be assigned "next" to cycle through the touchable areas, highlighting
    # the current one with a box or something. If another button assigned to "ok"  is pressed, it is considered
    # a touch event on the selected item, and a touch release (0) event when the button is released. "prev" to cycle
    # backwares and "back" (just dismisses highlighting the selected element for now) are also implemented for UI
    # navigation.
    # - web_ui to add/remove UI elements from button cycling

    
    def __init__(self):
        self._ts_thread = None       # ts_print thread
        self.keepGoing = False       # let the ts_print thread know to stop going when we exit
        self._view = None            # pwnagotchi view/ui/display
        self._agent = None           # pwnagotchi agent
        self._beingTouched = False   # currently being touched or not
        self._ui_elements = []       # keep track of UI elements created in on_ui_setup for easy removal in on_unload

        self.touchscreen = None      # ts_print external process

        self.touch_elements = {}     # ui elements of interest for touch events

        # use buttons to cycle through user elements
        # web_ui to select which ones to include or not include
        self.buttonCurrentZone = None

        logging.basicConfig(format='%(asctime)-15s %(levelname)s [%(filename)s:%(lineno)d] %(funcName)s: %(message)s')

        logging.debug("plugin created")

    def touchScreenHandler(self, ts_device=None):
        try:
            if not ts_device:
                # try to find a touchscreen device
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

            if ts_device:
                cmd = "/usr/bin/ts_print"
                os.environ["TSLIB_TSDEVICE"] = "%s" % ts_device
                self.touchscreen = Popen(['stdbuf', '-o0', cmd], env=os.environ, stdout=PIPE, universal_newlines=True, shell=False)
                if self.touchscreen:
                    self.keepGoing = True
                    for output in self.touchscreen.stdout:
                        if not output or not self.keepGoing:
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
            logging.info("ts_print exitted")
            #err = self.touchscreen.stderr.read()
            #logging.info(err)
        except Exception as e:
            logging.info("Handler: %s" % repr(e))
    
    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        # define which elements are active or not
        pass

    # called when the plugin is loaded
    def on_loaded(self):
        logging.info("loaded with options = " % self.options)

        # to test pimoroni displayhatmini buttons, uncomment below, or define in your config.toml
        ##if 'gpios' not in self.options:
        ##    self.options['gpios'] = {'ok': 6, 'back' : 5, 'next': 24, 'prev': 16}   # Pimoroni display hat mini

    # called before the plugin is unloaded
    def on_unload(self, ui):
        try:
            # stop the thread
            self.keepGoing = False
            if self._ts_thread:
                if self.touchscreen:
                    logging.debug("TERM to %s" % self.touchscreen.pid)
                    os.kill(self.touchscreen.pid, signal.SIGTERM)
                logging.debug("Waiting for thread to exit")
                self._ts_thread.join()
                logging.debug("And its done.")

            # remove UI elements
            i = 0
            for n in self._ui_elements:
                ui.remove_element(n)
                logging.info("Removed %s" % repr(n))
                i += 1
            if i: logging.info("plugin unloaded %d elements" % i)

            if 'gpios' in self.options:
                for i in self.options['gpios'].values():
                    logging.info("Stop detecting GPIO %s" % repr(i))
                    GPIO.remove_event_detect(i)

        except Exception as e:
            logging.error("%s" % repr(e))

    # called when there's internet connectivity - probably dont need this
    def on_internet_available(self, agent):
        pass

    # is this point(x,y) in box (x1, y1, x2, y2), x2>x1, y2>y1
    def pointInBox(self, point, box):
        logging.debug("is %s in %s" % (repr(point), repr(box)))
        return (point[0] >= box[0] and point[0] <= box[2] and point[1] >= box[1] and point[1] <= box[3])

    def collect_touch_elements(self):
        # - go through plugins, and build touch_elements cache and complete array
        #   - cache is a mapping of plugin to touch_elements
        # - in process_touch, compare each plugin touch_elements to cached, and update if changed
        # - cache bounding boxes of elements, indexed on "name:xy:font:value", and update when
        #   different
        # Any display elements listed in the array will be checked for _press and _release,
        # and be available for button presses.
        pass

    def process_touch(self, tpoint, depth):
        logging.debug("PT: %s: %s" % (repr(self.tpoint), repr(depth)))

        touch_data = { 'point':tpoint, 'pressure': depth }

        # check UI element bounding boxes and call on_touch
        touch_element = None
        for te in self.touch_elements:
            bbox = [] # get bounding box of the element. NOT IMPLEMENTED YET
            if self.pointInBox(tpoint, bbox):
                logging.info("Zone %s: %s @ %s" % (depth,
                                                   repr(te),
                                                   repr(tpoint)))
                touch_element = te
                break # stop at first match

        if int(depth) > 0:
            if not self.beingTouched:
                plugins.on("touch_press", self, self._view, touch_element, touch_data)
                self.beingTouched = True
            else:
                plugins.on("touch_move", self, self._view, touch_element, touch_data)

        elif int(depth) == 0:
                plugins.on("touch_release", self, self._view, touch_element, touch_data)
                self.beingTouched = False

    # button handlers to cycle through touch areas and click
    # just detect clicks for now, NOT IMPLEMENTED YET
    def okButtonPress(self, button):
        logging.info("OK Button pressed: %s" % repr(button))
        if self.buttonCurrentZone:
            # find center, and highlight element
            pass

    def okButtonRelease(self, button):
        logging.info("OK Button released: %s" % repr(button))
        if self.buttonCurrentZone:
            # find center, and process click
            pass

    def backButtonPress(self, button):
        logging.info("Back Button pressed: %s" % repr(button))
        if self.buttonCurrentZone:
            # remove highlight and unselect
            self.buttonCurrentZone = None
            pass

    def backButtonRelease(self, button):
        logging.info("Back Button released: %s" % repr(button))
        if self.buttonCurrentZone:
            # remove highlight and unselect
            self.buttonCurrentZone = None
            pass

    def nextButtonPress(self, button):
        logging.info("Next Button pressed: %s" % repr(button))
        if self.buttonCurrentZone:
            # pick the next one
            pass
        else:
            # pick the first one, or last used one?
            pass

    def nextButtonRelease(self, button):
        logging.info("Next Button released: %s" % repr(button))
        if self.buttonCurrentZone:
            # pick the next one
            pass
        else:
            # pick the first one, or last used one?
            pass

    def prevButtonPress(self, button):
        logging.info("Prev Button pressed: %s" % repr(button))
        if self.buttonCurrentZone:
            # pick the previous one
            pass

    def prevButtonRelease(self, button):
        logging.info("Prev Button released: %s" % repr(button))
        if self.buttonCurrentZone:
            # pick the previous one
            pass

    # called when the hardware display setup is done, display is an hardware specific object
    def on_display_setup(self, display):
        # touchscreen setup/connection should go here, but doesn't have agent.. just display...
        pass

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._agent = agent    # save for posterity

        # set up GPIO - next, previous, ok, back
        if 'gpios' in self.options:
            GPIO.setmode(GPIO.BCM)
            if 'ok' in self.options['gpios']:
                try:
                    GPIO.setup(int(self.options['gpios']['ok']), GPIO.IN, GPIO.PUD_UP)
                    GPIO.add_event_detect(int(self.options['gpios']['ok']), GPIO.FALLING, callback=self.okButtonPress, bouncetime=600)
                    GPIO.add_event_detect(int(self.options['gpios']['ok']), GPIO.RISING, callback=self.okButtonRelease, bouncetime=600)
                except Exception as err:
                    logging.warning("OK button: %s" % repr(err))
            if 'next' in self.options['gpios']:
                try:
                    GPIO.setup(int(self.options['gpios']['next']), GPIO.IN, GPIO.PUD_UP)
                    GPIO.add_event_detect(int(self.options['gpios']['next']), GPIO.FALLING, callback=self.nextButtonPress, bouncetime=600)
                    GPIO.add_event_detect(int(self.options['gpios']['next']), GPIO.RISING, callback=self.nextButtonRelease, bouncetime=600)
                except Exception as err:
                    logging.warning("Next button: %s" % repr(err))
            if 'back' in self.options['gpios']:
                try:
                    GPIO.setup(int(self.options['gpios']['back']), GPIO.IN, GPIO.PUD_UP)
                    GPIO.add_event_detect(int(self.options['gpios']['back']), GPIO.FALLING, callback=self.backButtonPress, bouncetime=600)
                    GPIO.add_event_detect(int(self.options['gpios']['back']), GPIO.RISING, callback=self.backButtonRelease, bouncetime=600)
                except Exception as err:
                    logging.warning("Back button: %s" % repr(err))
            if 'prev' in self.options['gpios']:
                try:
                    GPIO.setup(int(self.options['gpios']['prev']), GPIO.IN, GPIO.PUD_UP)
                    GPIO.add_event_detect(int(self.options['gpios']['prev']), GPIO.FALLING, callback=self.prevButtonPress, bouncetime=600)
                    GPIO.add_event_detect(int(self.options['gpios']['prev']), GPIO.RISING, callback=self.prevButtonRelease, bouncetime=600)
                except Exception as err:
                    logging.warning("Prev button: %s" % repr(err))

        # start touchscreen handler thread
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

        plugins.on("touch_ready", self)

    # called to setup the ui elements
    def on_ui_setup(self, ui):
        self._view = ui
        # later, look through _view to get bounding boxes

    # called when the agent is rebooting the board
    def on_rebooting(self, agent):
        pass

    # called when the agent is waiting for t seconds
    def on_wait(self, agent, t):
        pass

    # called when the agent is sleeping for t seconds
    def on_sleep(self, agent, t):
        # update caches
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

    ts.okButtonPress(69)

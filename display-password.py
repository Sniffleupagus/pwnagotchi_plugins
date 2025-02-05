# display-password shows recently cracked passwords of nearby networks
# on the pwnagotchi display 
#
#
###############################################################
#
# Inspired by, and code shamelessly yoinked from
# the pwnagotchi memtemp.py plugin by https://github.com/xenDE
#
# Modified by Sniffleupagus
#
###############################################################
from pwnagotchi.ui.components import Text, Widget
from pwnagotchi.ui.view import BLACK
import RPi.GPIO as GPIO
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins
import pwnagotchi
import logging
import os
import operator
import random
import time
import qrcode

class WifiQR(Widget):
    def __init__(self, ssid, passwd, color = 0, version=6, box_size=3, border=3):
        super().__init__(color)
        self.ssid = ssid
        self.passwd = passwd
        self.color = color
        self.box_size = box_size
        self.border = border
        self.xy = (0,0,1,1)
        self.version = version
        self.img = None

    def draw(self, canvas, drawer):
        try:
            logging.debug("QR display")
            if not self.img:
                max_size = min([canvas.width, canvas.height])
                best_version = int((max_size/self.box_size - 17 - 2 * self.border) / 4)
                logging.info("Computed size: %d -> %d" % (max_size, best_version))
                self.version = best_version
                self.qr = qrcode.QRCode(version=self.version,
                                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                                        box_size=self.box_size, border=self.border
                                        )
                wifi_data = f"WIFI:T:WPA;S:{self.ssid};P:{self.passwd};;"
                self.qr.add_data(wifi_data)
                self.img = self.qr.make_image(fit=True, fill_color="black", back_color="white").convert(canvas.mode)
                logging.debug("QR Created: %s" % repr(self.img))

                self.xy = (int(canvas.width/2 - self.img.width/2),
                           int(canvas.height/2 - self.img.height/2),
                           int(canvas.width/2 - self.img.width/2 + self.img.width),
                           int(canvas.height/2 - self.img.height/2 + self.img.height)
                           )

            canvas.paste(self.img, self.xy)
        except Exception as e:
            logging.exception("Image failed: %s, %s" % (self.img.width, self.xy))

class DisplayPassword(plugins.Plugin):
    __author__ = '@nagy_craig, Sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin to display recently cracked passwords of nearby networks'


    def readPotfile(self, fname="/root/handshakes/wpa-sec.cracked.potfile"):
        if os.path.isfile(fname):
            st = os.stat(fname)
            mtime = st.st_mtime if st else 0

            if mtime == self.potfile_mtime:
                logging.debug("Potfile unchanged.")
            else:
                logging.info("Reading potfile.")
                self.potfile_mtime = mtime
                with open(fname) as f:
                    self.cracked = {}
                    for line in f:
                        (mac, othermac, ssid, info) = line.strip().split(':', 3)
                        self.cracked[mac.lower()] = line
                        self.cracked[ssid] = line

    def __init__(self):
        self._ui = None
        self.cracked = {}
        self.found = {}
        self._lastpass = None
        self._lastidx = 0
        self._next_change_time = 0
        self.potfile_mtime=0
        self.qr_code = None
        self.text_elem = None
        self.gpio = None
        self._lastgpio = 0
    
    def on_loaded(self):
        logging.info("display-password loaded: %s" % self.options)
        self.readPotfile()

        self.gpio = self.options.get("gpio", None)
        if self.gpio:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.gpio, GPIO.IN, GPIO.PUD_UP)
                GPIO.add_event_detect(self.gpio, GPIO.FALLING, callback=self.toggleQR,
                                      bouncetime=800)
            except Exception as e:
                logging.error("GPIO: %s" % e)
                self.gpio = None

    def toggleQR(self, channel):
      try:
        if not self._ui:
            return

        now = time.time()
        if now - self._lastgpio < 0.7:
            logging.info("Debounce %s %s" % (now, self._lastgpio))
            return
        self._lastgpio = now

        logging.info("TOGGLE!")
        if self.qr_code:
            logging.info("Close QR code")
            self._ui.remove_element('dp-qrcode')
            del self.qr_code
            self.qr_code = None
            self._ui.update(force=True)
        elif self._lastpass:
            try:
                ssid, passwd, rssi = self._lastpass
                border = self.options.get('border', 3)
                box_size = self.options.get('box_size', 3)
                self.qr_code = WifiQR(ssid, passwd, box_size=box_size, border=border)
                self._ui.add_element('dp-qrcode', self.qr_code)
                self._ui.update(force=True)
            except Exception as e:
                logging.exception(e)
      except Exception as e:
          logging.exception(e)

    def on_ready(self, agent):
        self._agent = agent

        # wipe out memory of APs to get notifications sooner
        if self.options.get("debug", False):
            agent.run('wifi.clear')

        self.check_aps(agent._access_points)

    def on_ui_setup(self, ui):
        self._ui = ui
        try:
            pos = (self.options.get('pos_x', 0), self.options.get('pos_y', 91))
            self.text_elem = Text(color=BLACK, value='',
                                  position=pos,
                                  font=fonts.Small)
            ui.add_element('display-password', self.text_elem)              
        except Exception as e:
            logging.exception(e)

    def on_unload(self, ui):
        try:
            with ui._lock:
                ui.remove_element('display-password')
                if self.qr_code:
                    ui.remove_element('dp-qrcode')

        except Exception as e:
            logging.info(e)
        if self.gpio:
            logging.info("Cleaning GPIO")
            GPIO.remove_event_detect(self.gpio)
            GPIO.cleanup(self.gpio)

    # update from list of visible APs, and pick from the file one that matchs
    def on_unfiltered_ap_list(self, agent, access_points):
        if self.options.get("show_whitelist", False):
            self.check_aps(access_points)

    #def on_wifi_update(self, agent, access_points):
    #    if not self.options.get("show_whitelist", False):
    #        self.check_aps(access_points)

    def check_aps(self, access_points):
      try:
        self.readPotfile()
        self.found = {}
        sorted_aps = sorted(access_points, key=operator.itemgetter( 'rssi'), reverse=True)

        for ap in sorted_aps:
            mac = ap['mac'].replace(":", "").lower()
            ssid = ap['hostname'].strip()
            rssi = ap.get('rssi', '')
            if mac in self.cracked:                
                logging.debug("APmac: %s, %s" % (self.cracked[mac].strip(), repr(ap)))
                (amac, smac, assid, apass) = self.cracked[mac].strip().split(':', 3)
                if ssid == assid:
                    logging.debug("Found: %s %s ? %s" % (mac, ssid, self.cracked[mac]))
                    self.found[mac] = [assid, apass, rssi]
            elif ssid in self.cracked:                
                logging.debug("APssid: %s, %s" % (self.cracked[ssid].strip(), repr(ap)))
                (amac, smac, assid, apass) = self.cracked[ssid].strip().split(':', 3)
                logging.debug("Found: %s %s ? %s" % (mac, ssid, self.cracked[ssid]))
                self.found[mac] = [assid, apass, rssi]
            else:
                logging.debug("AP: %s, %s not found" % (mac, ssid))
      except Exception as e:
          logging.exception(e)
    
    def on_bcap_wifi_ap_new(self, agent, event):
        try:
            if not self._ui:
                return
            ap = event['data']
            ssid = ap['hostname'].strip()
            mac = ap['mac'].replace(":", "").lower()
            rssi = ap.get('rssi', '')

            if mac in self.cracked:
                (amac, smac, assid, apass) = self.cracked[mac].strip().split(':', 3)
                logging.info("Popped up: %s %s ? %s" % (mac, ssid, self.cracked[mac]))
                self.found[amac] = [assid, apass, rssi]
                self._ui.set('display-password', "%s: %s (%s)" % (assid, apass, rssi))
                self._lastpass = self.found[amac]
            elif ssid in self.cracked:
                (amac, smac, assid, apass) = self.cracked[ssid].strip().split(':', 3)
                logging.info("Popped up: %s %s ? %s" % (mac, ssid, self.cracked[ssid]))
                self.found[amac] = [assid, apass, rssi]
                self._ui.set('display-password', "%s: %s (%s)" % (assid, apass, rssi))
                self._lastpass = self.found[amac]
        except Exception as e:
            logging.exception(repr(e))

    def on_ui_update(self, ui):
      try:
        now = time.time()
        if len(self.found):
            if now > self._next_change_time:
                mode = self.options.get("mode", "cycle")
                if mode == "rssi":
                    self._lastpass = self.found[list(self.found)[0]]
                elif mode == "random":
                    self._lastpass = self.found[random.choice(list(self.found))]
                else:
                    self._lastidx = (self._lastidx + 1) % len(self.found)
                    self._lastpass = self.found[list(self.found)[self._lastidx]]
                ui.set('display-password', "%s: %s (%s)" % (self._lastpass[0], self._lastpass[1], self._lastpass[2]))
                self._next_change_time = now + self.options.get("update_interval", 8)
        else:
            self._lastpass = None
            ui.set('display-password', "")
      except Exception as e:
          logging.exception(e)

    def on_touch_release(self, ts, ui, ui_element, touch_data):
        logging.debug("Touch release: %s" % repr(touch_data));
        try:
            if self.qr_code:
                # if qr_code is being displayed
                p = touch_data['point']
                tpos = self.qr_code.xy
                if (p[0] > tpos[0] and
                    p[0] < tpos[2] and
                    p[1] > tpos[1] and
                    p[1] < tpos[3]):
                    
                    logging.debug("Close QR code")
                    ui.remove_element('dp-qrcode')
                    del self.qr_code
                    self.qr_code = None
                    ui.update(force=True)
            else:
                # if touched the password location, pop up a QR code
                bbox = self.text_elem.font.getbbox(ui.get('display-password'))
                p = touch_data['point']
                tpos = self.text_elem.xy
                rbox = (tpos[0] + bbox[0], tpos[1] + bbox[1],
                        tpos[0] + bbox[2], tpos[1] + bbox[3])
                logging.debug("BBox is %s" % (repr(rbox)))
                logging.debug("Touch at %s" % (repr(p)))
                if (p[0] > tpos[0] + bbox[0] and
                    p[0] < tpos[0] + bbox[2] and
                    p[1] > tpos[1] + bbox[1] and
                    p[1] < tpos[1] + bbox[3]):
                    logging.info("Show QR code (%s)" % self._lastpass)
                    if self._lastpass:
                        ssid, passwd, rssi = self._lastpass
                        self.qr_code = WifiQR(ssid, passwd)
                        ui.add_element('dp-qrcode', self.qr_code)
                        ui.update(force=True)

        except Exception as err:
            logging.exception("%s" % repr(err))
        

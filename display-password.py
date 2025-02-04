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
    def __init__(self, ssid, passwd, xy=[100,1, 177, 87], color = 0):
        super().__init__(xy, color)
        self.ssid = ssid
        self.passwd = passwd
        self.xy = xy
        self.color = color
        
        self.qr = qrcode.QRCode(version=4,
                                error_correction=qrcode.constants.ERROR_CORRECT_L,
                                box_size=3,
                                )
        wifi_data = f"WIFI:T:WPA;S:{ssid};P:{passwd};;"
        self.qr.add_data(wifi_data)
        #self.img = qrcode.make(wifi_data)
        self.img = self.qr.make_image(fill_color="black", back_color="white")
        logging.info("QR Created: %s" % repr(self.img))
        self.img.save("/tmp/qrcode.png")
        self.img = self.img.convert('RGB')
        self.xy[2] = self.xy[0] + self.img.width
        self.xy[3] = self.xy[1] + self.img.height
    def draw(self, canvas, drawer):
        logging.info("QR display")
        canvas.paste(self.img, self.xy)


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
                logging.info("Potfile changed. Reloading")
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
    
    def on_loaded(self):
        logging.info("display-password loaded")
        self.readPotfile()

    def on_ready(self, agent):
        self._agent = agent

        logging.info("unit is ready")
        # wipe out memory of APs to get notifications sooner
        if self.options.get("debug", False):
            agent.run('wifi.clear')

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

    # update from list of visible APs, and pick from the file one that matchs
    def on_unfiltered_ap_list(self, agent, access_points):
        if self.options.get("show_whitelist", False):
            self.check_aps(access_points)

    def on_wifi_update(self, agent, access_points):
        if not self.options.get("show_whitelist", False):
            self.check_aps(access_points)

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
                    logging.info("Found: %s %s ? %s" % (mac, ssid, self.cracked[mac]))
                    self.found[mac] = [assid, apass, rssi]
            elif ssid in self.cracked:                
                logging.debug("APssid: %s, %s" % (self.cracked[ssid].strip(), repr(ap)))
                (amac, smac, assid, apass) = self.cracked[ssid].strip().split(':', 3)
                logging.info("Found: %s %s ? %s" % (mac, ssid, self.cracked[ssid]))
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
        logging.info("Touch release: %s" % repr(touch_data));
        try:
            if self.qr_code:
                # if qr_code is being displayed
                p = touch_data['point']
                tpos = self.qr_code.xy
                if (p[0] > tpos[0] and
                    p[0] < tpos[2] and
                    p[1] > tpos[1] and
                    p[1] < tpos[3]):
                    
                    logging.info("Close QR code")
                    ui.remove_element('dp-qrcode')
                    del self.qr_code
                    self.qr_code = None
                    ui.update(force=True)
            else:
                # if touched the password location, pop up a QR code
                logging.info("BBox is %s" % (repr(self.text_elem.xy)))
                p = touch_data['point']
                tpos = self.text_elem.xy
                if abs(p[0] - tpos[0]) < 20 and abs(p[1] - tpos[1]) < 20:
                    logging.info("Show QR code (%s)" % self._lastpass)
                    if self._lastpass:
                        ssid, passwd, rssi = self._lastpass
                        self.qr_code = WifiQR(ssid, passwd)
                        ui.add_element('dp-qrcode', self.qr_code)
                        ui.update(force=True)

        except Exception as err:
            logging.exception("%s" % repr(err))
        

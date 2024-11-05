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
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins
import pwnagotchi
import logging
import os
import operator
import random
import time

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
        if ui.is_waveshare_v2():
            h_pos = (0, 95)
            v_pos = (180, 61)
        elif ui.is_waveshare_v1():
            h_pos = (0, 95)
            v_pos = (170, 61)
        elif ui.is_waveshare144lcd():
            h_pos = (0, 92)
            v_pos = (78, 67)
        elif ui.is_inky():
            h_pos = (0, 83)
            v_pos = (165, 54)
        elif ui.is_waveshare27inch():
            h_pos = (0, 153)
            v_pos = (216, 122)
        else:
            h_pos = (0, 91)
            v_pos = (180, 61)

        if 'orientation' in self.options and self.options['orientation'] == "vertical":
            ui.add_element('display-password', LabeledValue(color=BLACK, label='', value='',
                                                   position=v_pos,
                                                   label_font=fonts.Bold, text_font=fonts.Small))
        else:
            # default to horizontal
            ui.add_element('display-password', LabeledValue(color=BLACK, label='', value='',
                                                   position=h_pos,
                                                   label_font=fonts.Bold, text_font=fonts.Small))

    def on_unload(self, ui):
        try:
            with ui._lock:
                ui.remove_element('display-password')
        except Exception as e:
            logging.info(e)

    # update from list of visible APs, and pick from the file one that matchs
    def on_wifi_update(self, agent, access_points):
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
                    self.found[mac] = "%s:%s (%s)" % (assid, apass, rssi)
            elif ssid in self.cracked:                
                logging.debug("APssid: %s, %s" % (self.cracked[ssid].strip(), repr(ap)))
                (amac, smac, assid, apass) = self.cracked[ssid].strip().split(':', 3)
                logging.info("Found: %s %s ? %s" % (mac, ssid, self.cracked[ssid]))
                self.found[mac] = "%s-%s (%s)" % (assid, apass, rssi)
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
                self.found[amac] = "%s:%s (%s)" % (assid, apass, rssi)
                self._ui.set('display-password', self.found[amac])
            elif ssid in self.cracked:
                (amac, smac, assid, apass) = self.cracked[ssid].strip().split(':', 3)
                logging.info("Popped up: %s %s ? %s" % (mac, ssid, self.cracked[ssid]))
                self.found[amac] = "%s-%s (%s)" % (assid, apass, rssi)
                self._ui.set('display-password', self.found[amac])

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
                ui.set('display-password', self._lastpass)
                self._next_change_time = now + self.options.get("update_interval", 5)
        else:
            self._lastpass = ""
            ui.set('display-password', self._lastpass)
      except Exception as e:
          logging.exception(e)

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
import random

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
                with open(fname) as f:
                    self.cracked = {}
                    for line in f:
                        (mac, othermac, ssid, info) = line.strip().split(':', 3)
                        self.cracked[mac.lower()] = line
                        self.cracked[ssid.lower()] = line

    def __init__(self):
        self.cracked = {}
        self.found = {}
        self.potfile_mtime=0
    
    def on_loaded(self):
        logging.info("display-password loaded")

    def on_ui_setup(self, ui):
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
        self.readPotfile()
        self.found = {}
        
        for ap in access_points:
            mac = ap['mac'].replace(":", "").lower()
            ssid = ap['hostname'].strip().lower()
            if mac in self.cracked:                
                logging.debug("APmac: %s, %s" % (self.cracked[mac].strip(), repr(ap)))
                (amac, smac, assid, apass) = self.cracked[mac].strip().split(':', 3)
                if ssid == assid.lower():
                    logging.debug("Found: %s %s ? %s" % (mac, ssid, self.cracked[mac]))
                    self.found[mac] = assid + ":" + apass                
            elif ssid in self.cracked:                
                logging.debug("APssid: %s, %s" % (self.cracked[ssid].strip(), repr(ap)))
                (amac, smac, assid, apass) = self.cracked[ssid].strip().split(':', 3)
                if ssid == assid.lower():
                    logging.debug("Found: %s %s ? %s" % (mac, ssid, self.cracked[ssid]))
                    self.found[mac] = assid + "-" + apass
            else:
                logging.debug("AP: %s, %s not found" % (mac, ssid))
    
    def on_ui_update(self, ui):
        if len(self.found):
            last_line = self.found[random.choice(list(self.found))]
        else:
            last_line = ""
        ui.set('display-password', last_line)

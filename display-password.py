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
from PIL import Image, ImageDraw, ImageFont
from pwnagotchi.ui.view import BLACK
import RPi.GPIO as GPIO
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins
import pwnagotchi
import logging
import os
import glob
import operator
import random
import time
import re
import socket
from datetime import datetime, date
from urllib.parse import urlparse, unquote
from dateutil.parser import isoparse

try:
    import dpkt
except Exception as e:
    logging.info("Install dpkt to extract timestamps from pcaps::")
    logging.info("\t$ sudo bash")
    logging.info("\t# source ~pi/.pwn/bin/activate")
    logging.info("\t# pip3 install dpkt")
    dpkt = None

try:
    import qrcode
except Exception as e:
    logging.info("Install python qrcode library to display QR codes: %s" % e)
    logging.info("To install in pwnagotchi venv:")
    logging.info("\t$ sudo bash")
    logging.info("\t# source ~pi/.pwn/bin/activate")
    logging.info("\t# pip3 install qrcode")
    qrcode = None

class WifiQR(Widget):
    def __init__(self, ssid, passwd, mac, rssi, color = 0, version=6, box_size=3, border=4, demo=False):
        super().__init__(color)
        self.color = color
        self.box_size = box_size
        self.border = border
        self.xy = (0,0,1,1)
        self.version = version
        self.img = None
        self.ts = None
        self.image = None
        self.value = None
        self.state = True
        self.event_handler = "display-password"

        if demo:
            self.wifi_data = "https://www.youtube.com/watch?v=xvFZjo5PgG0"
            self.ssid = "Wu-Tang LAN"
            self.passwd = "NutN2FWit"
            self.rssi = 69
            self.ts = 752847600
        else:
            self.ssid = ssid
            self.passwd = passwd
            self.mac = mac
            self.rssi = rssi
            self.wifi_data = f"WIFI:T:WPA;S:{ssid};P:{passwd};;"

            for hsdir in ("/root/handshakes", "/boot/handshakes", "/home/pi/handshakes"):
                fname = f"{hsdir}/{self.ssid}_{self.mac}.pcap"
                if os.path.isfile(fname):
                    self.ts = os.path.getctime(fname)
                    try:
                        if dpkt:
                            with open(fname, 'rb') as pc:
                                pcap = dpkt.pcap.Reader(pc)
                                for pts, buf in pcap:
                                    logging.debug(datetime.fromtimestamp(pts).strftime(" %x %X"))
                                    self.ts = pts
                                    break
                    except Exception as e:
                        logging.exception("could not process pcap %s: %s" % (fname, e))
                        self.ts = os.path.getctime(fname)
                    break
                else:
                    fname = None
                    self.ts = None

    def draw(self, canvas, drawer):
        try:
            logging.debug("QR display")
            if not self.img:
                w = canvas.width
                h = canvas.height
                img = Image.new(canvas.mode, (canvas.width, canvas.height), color=(0,0,0))
                d = ImageDraw.Draw(img)
                d.fontmode = "1"
                img_center = (int(canvas.width/2), int(canvas.height/2))

                max_size = min([canvas.width*0.8/2, canvas.height])
                if qrcode:
                    best_version = int((max_size/self.box_size - 17 - 2 * self.border) / self.box_size)
                    if best_version < 1:
                        best_version = 1
                    logging.debug("Computed size: %d -> %d" % (max_size, best_version))
                    self.version = best_version
                    self.qr = qrcode.QRCode(version=self.version,
                                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                                            box_size=self.box_size, border=self.border
                                            )

                    self.qr.add_data(self.wifi_data)
                    qimg = self.qr.make_image(fit=True, fill_color="black", back_color="white").convert(canvas.mode)
                    logging.debug("QR Created: %s" % repr(img))
                    b = qimg.getbbox()

                    f = ImageFont.truetype("DejaVuSans-Bold", int((b[3]-b[1])/7))
                    f2 = ImageFont.truetype("DejaVuSerif-Bold",int((b[3]-b[1])/11))
                    f3 = ImageFont.truetype("DejaVuSans", int((b[3]-b[1])/10))

                    x = b[2]+self.box_size
                    y = b[1]+self.border*self.box_size
                    d.text((x,y), "SSID", (192,192,192), font=f2)
                    b2 = img.getbbox()
                    d.text((b2[2],y), f" ({self.rssi} db)", (255,255,255), font=f2)
                    y = b2[3]
                    d.text((x,y), self.ssid, (255,255,255), font=f)
                    b2 = img.getbbox()
                    y = b2[3]+self.box_size
                    d.text((x, y), "PASSWORD", (192,192,193), font=f2)
                    b2 = img.getbbox()
                    y = b2[3]
                    d.text((x,y), self.passwd, (255,255,255), font=f)

                    if self.ts:
                        b2 = img.getbbox()
                        y = b2[3]+self.box_size
                        d.text((x, y), "DATE PWNED", (192,192,192), font=f2)
                        b2 = img.getbbox()
                        y = b2[3]

                        d.text((x,y), datetime.fromtimestamp(self.ts).strftime(" %x %X"), (255,255,255), font=f3)

                    b2 = img.getbbox()
                    img.paste(qimg, (0,0))
                    d.rectangle((0, 0, b2[2] + self.border*self.box_size, b[3]))
                    self.img = img.crop(img.getbbox()).convert(canvas.mode)

                    self.xy = (int(canvas.width/2 - self.img.width/2),
                               int(canvas.height/2 - self.img.height/2),
                               int(canvas.width/2 - self.img.width/2 + self.img.width),
                               int(canvas.height/2 - self.img.height/2 + self.img.height)
                               )
                else:
                    logging.debug("No QRCode")
                    x = self.border*2
                    y = self.border*2
                    f = ImageFont.truetype("DejaVuSans-Bold", int(h/8))
                    f2 = ImageFont.truetype("DejaVuSerif-Bold", int(h/12))
                    f3 = ImageFont.truetype("DejaVuSans", int(14))

                    for head, body in [["SSID", self.ssid], ["PASSWORD", self.passwd]]:
                        d.text((x,y), head, (192,192,192), font=f2)
                        b = img.getbbox()
                        y = b[3]#+self.box_size
                        logging.debug("%s at %s" % (head, b))
                        d.text((x,y), body, (255,255,255), font=f)
                        b = img.getbbox()
                        y = b[3]+self.box_size
                        logging.debug("%s at %s" % (body, b))

                    d.text((x,y+self.box_size), "Install qrcode lib to see QR codes:\n  $ sudo bash\n  # source ~pi/.pwn/bin/activate\n  # pip3 install qrcode", (255,255,255), font=f3)
                    b = img.getbbox()
                    d.rectangle((0, 0, b[2] + self.border*2, b[3] + self.border*2))
                    self.img = img.crop(img.getbbox())
                    self.xy = (int(canvas.width/2 - self.img.width/2),
                               int(canvas.height/2 - self.img.height/2),
                               int(canvas.width/2 + self.img.width/2),
                               int(canvas.height/2 + self.img.height/2))
            drawer.rectangle(self.xy, fill=None, outline='#808080')
            self.value = self.img
            self.image = self.img
            canvas.paste(self.img, self.xy)
        except Exception as e:
            logging.exception("Image failed: %s, %s" % (self.img, self.xy))

class DisplayPassword(plugins.Plugin):
    __author__ = '@nagy_craig, Sniffleupagus'
    __version__ = '1.2.2'
    __license__ = 'GPL3'
    __description__ = 'A plugin to display recently cracked passwords of nearby networks'

    def is_valid_mac(mac_address):
        mac_address_pattern = r"^([0-9A-Fa-f]{2}[:-]?){5}([0-9A-Fa-f]{2})$"
        return re.match(mac_address_pattern, mac_address) is not None

    def is_pmkid(text):
        pmkid_pattern = r"([0-9a-fA-F]{64})"
        match = re.search(pmkid_pattern, text)
        if match:
            return match.group(1)
        else:
            return None

    def readPotfile(self, fname="/root/handshakes/wpa-sec.cracked.potfile"):
        if os.path.isfile(fname):
            if fname not in self.potfiles:
                self.potfiles.append(fname)
            st = os.stat(fname)
            mtime = st.st_mtime if st else 0

            if mtime == self.potfile_mtimes.get(fname, -1):
                logging.debug("Potfile %s unchanged." % os.path.basename(fname))
            else:
                # recognize some files by name and configure field order
                # first is the character to split each line on
                # second is the number of fields to split into
                # remaining numbers represent the order of:
                #          AP mac, Client mac, SSID, and password
                # in the split string.
                if 'wpa-sec' in fname:
                    svc = "WPA-SEC"
                    layout = (':', 4, 0,1,2,3)
                elif 'cracked.pwncrack.potfile' in fname:
                    svc = "PWNCrack"
                    layout = (':', 5, 1,2,3,4)
                elif 'remote_cracking.potfile' in fname:
                    svc = "RemoteCracking"
                    layout = (':', 5, 1,2,3,4)
                else:
                    svc = os.path.basename(fname)
                    layout = None
                    logging.info("Unknown potfile format for %s. Going to guess" % fname)

                logging.info("Reading potfile %s" % fname)
                with open(fname) as f:
                    for line in f:
                        try:
                            line = line.strip()

                            if layout:
                                parts = line.split(layout[0], layout[1])

                                mac = parts[layout[2]]
                                ssid= parts[layout[4]]
                                crack_info={'mac': mac,
                                            'client': parts[layout[3]],
                                            'ssid': ssid,
                                            'passwd': parts[layout[5]],
                                            'service': svc}

                                self.cracked[mac] = crack_info
                                self.cracked[ssid] = crack_info
                            else:
                                # Guess layout
                                # if it looks like a mac, its probably a mac
                                # if it looks like a long hex string, it could be a pkmid, so ignore the first one
                                # otherwise assume SSID before password
                                try:
                                    parts = line.split(':')
                                    (pmkid, mac, cl_mac, ssid, pw) = (None, None, None, None, None)
                                    for p in range(parts):
                                        text = parts[p]
                                        if not mac and is_valid_mac(text):  # assume first mac as AP mac
                                            mac = text
                                        elif not cl_mac and is_valid_mac(text):  # assume second mac is client mac
                                            cl_mac = text
                                        elif not pmkid and is_pmkid(text):  # ignore first pkmid-looking thing
                                            pmkid = text
                                        elif not ssid:   # first string that gets here is assumes SSID
                                            ssid = text
                                        else:           # anything else is the password
                                            pw = text
                                    crack_info={'mac':mac,
                                                'client':mac,
                                                'ssid':ssid,
                                                'passwd':pw,
                                                'service':svc}
                                    if mac:
                                        self.cracked[mac] = crack_info
                                    if ssid:
                                        self.cracked[ssid] = crack_info
                                except Exception as ue:
                                    logging.exception("Unable to parse unknown potfile %s (text:%s): %s" % (fname, line, e))
                        except Exception as e:
                            logging.exception("Error processing potfile %s: %s" % (fname,e))
                            break
                self.potfile_mtimes[fname] = mtime

    def __init__(self):
        self._ui = None
        self.cracked = {}
        self.found = {}
        self._lastpass = None
        self._lastidx = 0
        self._next_change_time = 0
        self.potfile_mtimes={}
        self.qr_code = None
        self.text_elem = None
        self.gpio = None
        self._lastgpio = 0
        self.potfiles = [ ]
        self.shakedir = '/root/handshakes'
        # check new default locations
        for p in ['/home/pi/handshakes', '/boot/handshakes']:
            if os.path.exists(p):
                self.shakedir = p
                break
    
    def on_loaded(self):
        logging.debug("display-password loaded: %s" % self.options)

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
            logging.debug("Debounce %s %s" % (now, self._lastgpio))
            return
        self._lastgpio = now

        logging.debug("TOGGLE!")
        if self.qr_code:
            logging.debug("Close QR code")
            with self._ui._lock:
                self._ui.remove_element('dp-qrcode')
            del self.qr_code
            self.qr_code = None
            self._ui.update(force=True)
        elif self._lastpass:
            try:
                ssid, passwd, rssi, mac = self._lastpass['ssid'], self._lastpass['passwd'],self._lastpass['rssi'],self._lastpass['mac']
                border = self.options.get('border', 4)
                box_size = self.options.get('box_size', 3)
                self.qr_code = WifiQR(ssid, passwd, mac, rssi, box_size=box_size, border=border, demo=self.options.get('demo', False))
                with self._ui._lock:
                    self._ui.add_element('dp-qrcode', self.qr_code)
                self._ui.update(force=True)
            except Exception as e:
                logging.exception(e)
      except Exception as e:
          logging.exception(e)

    def on_config_changed(self, config):
        self.shakedir = config["bettercap"].get("handshakes", '/root/handshakes')
        for p in glob.glob(os.path.join(self.shakedir, '*potfile*')):
            self.readPotfile(p)

    def on_ready(self, agent):
        self._agent = agent
        config = agent._config

        try:
            logging.debug("Checking for %s AP passwords" % len(agent._access_points))
            self.check_aps(agent._access_points)
            # wipe out memory of APs to get notifications sooner
            if self.options.get("debug", False):
                logging.warning("*** Clearing bettercap AP list ***")
                agent.run('wifi.clear')
        except Exception as e:
            logging.exception(e)

    def on_ui_setup(self, ui):
        self._ui = ui
        try:
          with ui._lock:
            pos = (self.options.get('pos_x', 0), self.options.get('pos_y', 91))
            self.text_elem = Text(color=BLACK, value='',
                                  position=pos,
                                  font=fonts.Small)
            self.text_elem.state = True   # make touchable
            self.text_elem.event_handler = "display-password"
            ui.add_element('display-password', self.text_elem)
        except Exception as e:
            logging.exception(e)

    def on_unload(self, ui):
        try:
            with ui._lock:
                ui.remove_element('display-password')
                if self.qr_code:
                    ui.remove_element('dp-qrcode')
            ui.update(force=True)
        except Exception as e:
            logging.error(e)
        if self.gpio:
            logging.info("Cleaning GPIO")
            GPIO.remove_event_detect(self.gpio)
            GPIO.cleanup(self.gpio)

    # update from list of visible APs, and pick from the file one that matchs
    def on_unfiltered_ap_list(self, agent, access_points):
        if self.options.get("show_whitelist", False):
            self.check_aps(access_points)

    def on_wifi_update(self, agent, access_points):
        if not self.options.get("show_whitelist", False):
            self.check_aps(access_points)

    def check_aps(self, access_points):
      try:
        # update potfiles
        for p in glob.glob(os.path.join(self.shakedir, '*potfile*')):
            self.readPotfile(p)

        self.found = {}
        sorted_aps = sorted(access_points, key=lambda x:(int(isoparse(x['last_seen']).timestamp()),
                                                         x['rssi']), reverse=True)
        logging.debug("Sorted aps: %s" % (sorted_aps))

        for ap in sorted_aps:
            mac = ap['mac'].replace(":", "").lower()
            ssid = ap['hostname'].strip()
            rssi = ap.get('rssi', '')
            if mac in self.cracked:                
                logging.debug("APmac: %s, %s" % (self.cracked[mac], repr(ap)))
                self.found[mac] = self.cracked[mac]
                self.found[mac]['rssi'] = rssi
            elif ssid in self.cracked:                
                logging.debug("APssid: %s, %s" % (self.cracked[ssid], repr(ap)))
                self.found[mac] = self.cracked[ssid]
                self.found[mac]['rssi'] = rssi
            else:
                logging.debug("AP: %s, %s not found" % (mac, ssid))
      except Exception as e:
          logging.exception(e)

    def update_pass_display(self, ssid, pword, rssi, mac):
        if not self._ui:
            return
        if self.options.get('oneline', True):
            # one line layout - SSID: password (rssi)
            dp =  "%s: %s (%s)" % (ssid, pword, rssi)
            self._ui.set('display-password', dp)
            self.bbox = self.text_elem.font.getbbox(dp)
        else:  # two line layout - SSID (rssi)
            #                      password
            dp = "%s (%s)\n%s" % (ssid, rssi, pword)
            self._ui.set('display-password', dp)
            parts = dp.split('\n')
            bbox1 = self.text_elem.font.getbbox(parts[0])
            bbox2 = self.text_elem.font.getbbox(parts[1])
            self.bbox = (min(bbox1[0], bbox2[0]), min(bbox1[1], bbox2[1]),
                         max(bbox1[2], bbox2[2]), (bbox1[1] + (bbox2[3] - bbox2[1]) + (bbox1[3] - bbox1[1])))

    def on_bcap_wifi_ap_new(self, agent, event):
        try:
            if not self._ui:
                return
            ap = event['data']
            ssid = ap['hostname'].strip()
            mac = ap['mac'].replace(":", "").lower()
            rssi = ap.get('rssi', '')

            if mac in self.cracked:
                crk = self.cracked[mac]
                crk['rssi'] = rssi
                amac = crk['mac']
                logging.debug("Popped up: %s %s ? %s" % (mac, ssid, crk))
                self.found[amac] = crk
                self.update_pass_display(crk['ssid'], crk['passwd'], rssi, amac)
                self._lastpass = crk
            elif ssid in self.cracked:
                crk = self.cracked[ssid]
                crk['rssi'] = rssi
                amac = crk['mac']
                logging.debug("Popped up: %s %s ? %s" % (mac, ssid, crk))
                self.found[amac] = crk
                self.update_pass_display(crk['ssid'], crk['passwd'], rssi, amac)
                self._lastpass = self.found[amac]
        except Exception as e:
            logging.exception(repr(e))

    def on_ui_update(self, ui):
      try:
        now = time.time()
        if self.options.get('demo', False):
            self.update_pass_display("Wu-Tang LAN", "NutN2F*Wit", "69", "1:2:3:4:5:6")
            ui.set('shakes', "69 (420) [Shaolin Free Wifi]")
            self._lastpass = {'ssid': "Wu-Tang LAN",
                              'passwd': "NutN2F*Wit",
                              'rssi': "69",
                              'mac': "1:2:3:4:5:6",
                              'cl_mac': '7:8:9:1:2:3'}
        elif len(self.found):
            if now > self._next_change_time:
                mode = self.options.get("mode", "cycle")
                if mode == "rssi":
                    self._lastpass = self.found[list(self.found)[0]]
                elif mode == "random":
                    self._lastpass = self.found[random.choice(list(self.found))]
                else:
                    self._lastidx = (self._lastidx + 1) % len(self.found)
                    self._lastpass = self.found[list(self.found)[self._lastidx]]
                self.update_pass_display(self._lastpass['ssid'], self._lastpass['passwd'], self._lastpass['rssi'], self._lastpass['mac'])
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
                    with ui._lock:
                        ui.remove_element('dp-qrcode')
                    del self.qr_code
                    self.qr_code = None
                    ui.update(force=True)
            else:
                # if touched the password location, pop up a QR code
                bbox = self.bbox
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
                    logging.debug("Show QR code (%s)" % self._lastpass)
                    if self._lastpass:
                        ssid, passwd, rssi, mac = self._lastpass['ssid'], self._lastpass['passwd'],self._lastpass['rssi'],self._lastpass['mac']
                        self.qr_code = WifiQR(ssid, passwd, mac, rssi, demo=self.options.get('demo', False))
                        with ui._lock:
                            ui.add_element('dp-qrcode', self.qr_code)
                        ui.update(force=True)

        except Exception as err:
            logging.exception("%s" % repr(err))
        
    def on_webhook(self, path, request):
        try:
            method = request.method
            path = request.path
            if "/toggle" in path:
                self.toggleQR("web")
                return "OK", 204
            elif "/demo" in path:
                self.options['demo'] = not self.options.get('demo', False)
                return "OK - Demo %s" % self.options['demo']
            return "<html><body>Woohoo! %s:<p>Request <a href=\"/plugins/display-password/toggle\">/plugins/display-password/toggle</a> to view or dismiss the QR code on screen<p><a href=\"/plugins/display-password/demo\">Toggle Demo:</a> %s</body></html>" % (path, self.options.get('demo'))
        except Exception as e:
            logging.exception(e)
            return "<html><body>Error! %s</body></html>" % (e)

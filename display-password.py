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
import operator
import random
import time
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
                                    logging.info(datetime.fromtimestamp(pts).strftime(" %x %X"))
                                    self.ts = pts
                                    break
                    except Exception as e:
                        logging.info("could not process pcap: %s" % e)
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
                    logging.info("Computed size: %d -> %d" % (max_size, best_version))
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
                    logging.info("No QRCode")
                    x = self.border*2
                    y = self.border*2
                    f = ImageFont.truetype("DejaVuSans-Bold", int(h/8))
                    f2 = ImageFont.truetype("DejaVuSerif-Bold", int(h/12))
                    f3 = ImageFont.truetype("DejaVuSans", int(14))

                    for head, body in [["SSID", self.ssid], ["PASSWORD", self.passwd]]:
                        d.text((x,y), head, (192,192,192), font=f2)
                        b = img.getbbox()
                        y = b[3]#+self.box_size
                        logging.info("%s at %s" % (head, b))
                        d.text((x,y), body, (255,255,255), font=f)
                        b = img.getbbox()
                        y = b[3]+self.box_size
                        logging.info("%s at %s" % (body, b))

                    d.text((x,y+self.box_size), "Install qrcode lib to see QR codes:\n  $ sudo bash\n  # source ~pi/.pwn/bin/activate\n  # pip3 install qrcode", (255,255,255), font=f3)
                    b = img.getbbox()
                    d.rectangle((0, 0, b[2] + self.border*2, b[3] + self.border*2))
                    self.img = img.crop(img.getbbox())
                    self.xy = (int(canvas.width/2 - self.img.width/2),
                               int(canvas.height/2 - self.img.height/2),
                               int(canvas.width/2 + self.img.width/2),
                               int(canvas.height/2 + self.img.height/2))
            drawer.rectangle(self.xy, fill=None, outline='#808080')
            canvas.paste(self.img, self.xy)
        except Exception as e:
            logging.exception("Image failed: %s, %s" % (self.img, self.xy))

class DisplayPassword(plugins.Plugin):
    __author__ = '@nagy_craig, Sniffleupagus'
    __version__ = '1.1.8'
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
                ssid, passwd, rssi, mac = self._lastpass
                border = self.options.get('border', 4)
                box_size = self.options.get('box_size', 3)
                with self._ui._lock:
                    self.qr_code = WifiQR(ssid, passwd, mac, rssi, box_size=box_size, border=border, demo=self.options.get('demo', False))
                    self._ui.add_element('dp-qrcode', self.qr_code)
                self._ui.update(force=True)
            except Exception as e:
                logging.exception(e)
      except Exception as e:
          logging.exception(e)

    def on_ready(self, agent):
        self._agent = agent

        try:
            # wipe out memory of APs to get notifications sooner
            if self.options.get("debug", False):
                agent.run('wifi.clear')
            logging.info("Checking %s APs" % len(agent._access_points))
            self.check_aps(agent._access_points)
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
        #sorted_aps = sorted(access_points, key=operator.itemgetter("last_seen",  'rssi'), reverse=True)
        sorted_aps = sorted(access_points, key=lambda x:(int(isoparse(x['last_seen']).timestamp()),
                                                         x['rssi']), reverse=True)
        logging.info(sorted_aps)

        for ap in sorted_aps:
            mac = ap['mac'].replace(":", "").lower()
            ssid = ap['hostname'].strip()
            rssi = ap.get('rssi', '')
            if mac in self.cracked:                
                logging.debug("APmac: %s, %s" % (self.cracked[mac].strip(), repr(ap)))
                (amac, smac, assid, apass) = self.cracked[mac].strip().split(':', 3)
                if ssid == assid:
                    logging.debug("Found: %s %s ? %s" % (mac, ssid, self.cracked[mac]))
                    self.found[mac] = [assid, apass, rssi, amac]
            elif ssid in self.cracked:                
                logging.debug("APssid: %s, %s" % (self.cracked[ssid].strip(), repr(ap)))
                (amac, smac, assid, apass) = self.cracked[ssid].strip().split(':', 3)
                logging.debug("Found: %s %s ? %s" % (mac, ssid, self.cracked[ssid]))
                self.found[mac] = [assid, apass, rssi, amac]
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
            bbox2 = self.text_elem.font.getbbox(parts[0])
            self.bbox = (min(bbox1[0], bbox2[0]), min(bbox1[1], bbox2[1]),
                         max(bbox1[2], bbox2[2]), (bbox2[3] + (bbox2[3] - bbox2[1]) + (bbox1[3] - bbox1[1])))

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
                self.found[amac] = [assid, apass, rssi, amac]
                self.update_pass_display(assid, apass, rssi, amac)
                self._lastpass = self.found[amac]
            elif ssid in self.cracked:
                (amac, smac, assid, apass) = self.cracked[ssid].strip().split(':', 3)
                logging.info("Popped up: %s %s ? %s" % (mac, ssid, self.cracked[ssid]))
                self.found[amac] = [assid, apass, rssi, amac]
                self.update_pass_display(assid, apass, rssi, amac)
                self._lastpass = self.found[amac]
        except Exception as e:
            logging.exception(repr(e))

    def on_ui_update(self, ui):
      try:
        now = time.time()
        if self.options.get('demo', False):
            self.update_pass_display("Wu-Tang LAN", "NutN2F*Wit", "69", "1:2:3:4:5:6")
            ui.set('shakes', "69 (420) [Shaolin Free Wifi]")
            self._lastpass = ["Wu-Tang LAN", "NutN2F*Wit", "69", "1:2:3:4:5:6"]
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
                self.update_pass_display(self._lastpass[0], self._lastpass[1], self._lastpass[2], self._lastpass[3])
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
                logging.info("BBox is %s" % (repr(rbox)))
                logging.info("Touch at %s" % (repr(p)))
                if (p[0] > tpos[0] + bbox[0] and
                    p[0] < tpos[0] + bbox[2] and
                    p[1] > tpos[1] + bbox[1] and
                    p[1] < tpos[1] + bbox[3]):
                    logging.info("Show QR code (%s)" % self._lastpass)
                    if self._lastpass:
                        ssid, passwd, rssi, mac = self._lastpass
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
            query = unquote(request.query_string.decode('utf-8'))
            if "/toggle" in path:
                self.toggleQR("web")
                return "OK"
            elif "/demo" in path:
                self.options['demo'] = not self.options.get('demo', False)
                return "OK - Demo %s" % self.options['demo']
            return "<html><body>Woohoo! %s: %s<p>Request <a href=\"/plugins/display-password/toggle\">/plugins/display-password/toggle</a> to view or dismiss the QR code on screen<p><a href=\"/plugins/display-password/demo\">Toggle Demo:</a> %s</body></html>" % (path, query, self.options.get('demo'))
        except Exception as e:
            logging.exception(e)
            return "<html><body>Error! %s</body></html>" % (e)

import os
import logging
import re
import subprocess
import time
from io import TextIOWrapper
from pwnagotchi import plugins

import pwnagotchi.ui.faces as faces
from pwnagotchi.bettercap import Client

class Fix_BRCMF(plugins.Plugin):
    __author__ = 'xxx@xxx.xxx'
    __version__ = '0.1.0'
    __license__ = 'GPL3'
    __description__ = 'Reload brcmfmac module when blindbug is detected, instead of rebooting. Adapted from WATCHDOG'

    
    def __init__(self):
        self.options = dict()
        self.pattern = re.compile(r'brcmf_cfg80211_nexmon_set_channel.*?Set Channel failed')
        self.isReloadingMon0 = False
        self.connection = None
        self.LASTTRY = 0

    def on_loaded(self):
        """
        Gets called when the plugin gets loaded
        """
        logging.info("[FixBRCMF] plugin loaded.")



    # bettercap sys_log event
    # search syslog events for the brcmf channel fail, and reset when it shows up
    # apparently this only gets messages from bettercap going to syslog, not from syslog
    def on_bcap_sys_log(self, agent, event):
        try:
            if re.search('brcmf_cfg80211_nexmon_set_channel.*?Set Channel failed', event['data']['Message']):
                logging.info("[FixBRCMF]SYSLOG MATCH: %s" % event['data']['Message'])
                logging.info("[FixBRCMF]**** Should trigger a reload of the mon0 device")
                self._tryTurningItOffAndOnAgain(agent)                
        except Exception as err:
            logging.error("[FixBRCMF]SYSLOG FixBRCMF fail: %s" % err)            

    def on_epoch(self, agent, epoch, epoch_data):
        # get last 10 lines
        last_lines = ''.join(list(TextIOWrapper(subprocess.Popen(['journalctl','-n10','-k', '--since', '-3m'],
                                                stdout=subprocess.PIPE).stdout))[-10:])
        if len(self.pattern.findall(last_lines)) >= 5:
            logging.info("[FixBRCMF]**** Should trigger a reload of the mon0 device")
            display = agent.view()
            display.set('status', 'Blind-Bug detected. Restarting.')
            display.update(force=True)
            logging.info('[FixBRCMF] Blind-Bug detected. Restarting.')
            self._tryTurningItOffAndOnAgain(agent)


    def _tryTurningItOffAndOnAgain(self, connection):
        # avoid overlapping restarts, but allow it if its been a while
        # (in case the last attempt failed before resetting "isReloadingMon0")
        if self.isReloadingMon0 and (time.time() - self.LASTTRY) < 180:
            logging.info("[FixBRCMF] Duplicate attempt ignored")
        else:
            self.isReloadingMon0 = True
            self.LASTTRY = time.time()
            
            logging.info("[FixBRCMF] Let's do this")

            if hasattr(connection, 'view'):
                display = connection.view()
                if display: display.update(force=True, new_data={"status": "I'm blind! Try turning it off and on again",
                                                                 "face":faces.BORED})
            else:
                display = None

            logging.info('[FixBRCMF] Blind-Bug detected. Restarting.')

            # main divergence from WATCHDOG starts here
            #
            # instead of rebooting, and losing all that energy loading up the AI
            #    pause wifi.recon, close mon0, reload the brcmfmac kernel module
            #    then recreate mon0, ..., and restart wifi.recon

            # Turn it off
            #if connection is None:
            #    try:
            #        connection = Client('localhost', port=8081, username="pwnagotchi", password="pwnagotchi");
            #    except Exception as err:
            #        logging.error("[FixBRCMF connection] %s" % err)


            # attempt a sanity check. does mon0 exist?
            # is it up?
            try:
                cmd_output = subprocess.check_output("ip link show mon0", shell=True)
                logging.info("[FixBRCMF ip link show mon0]: %s" % repr(cmd_output))
                if ",UP," in str(cmd_output):
                    logging.info("mon0 is up. Skipping reset.");
                    self.isReloadingMon0 = False
                    return
            except Exception as err:
                logging.error("[FixBRCMF ip link show mon0]: %s" % repr(cmd_output))


            try:
                result = connection.run("wifi.recon off")
                if result["success"]:
                    logging.info("[FixBRCMF] wifi.recon off: success!")
                    if display: display.update(force=True, new_data={"status": "Wifi recon paused!",
                                                                     "face":faces.COOL})
                    else: print("Wifi recon paused")
                    time.sleep(2)
                else:
                    logging.warning("[FixBRCMF] wifi.recon off: FAILED: %s" % repr(result))
                    if display: display.update(force=True, new_data={"status": "Recon was busted (probably)",
                                                                     "face":random.choice((faces.BROKEN, faces.DEBUG))})
            except Exception as err:
                logging.error("[FixBRCMF wifi.recon off] %s" % repr(err))

                
            logging.info("[FixBRCMF] recon paused. Now trying mon0 shit")
                
            try:
                cmd_output = subprocess.check_output("sudo ifconfig mon0 down && sudo iw dev mon0 del", shell=True)
                logging.info("[FixBRCMF] mon0 down and deleted")
                if display: display.update(force=True, new_data={"status": "mon0 d-d-d-down!",
                                                                 "face":faces.BORED})
                else: print("mon0 down!")
            except Exception as nope:
                logging.error("[FixBRCMF delete mon0] %s" % nope)
                pass
                
            logging.info("[FixBRCMF] Now trying modprobe -r")


            # Try this sequence 3 times until it is reloaded
            #
            # Future: while "not fixed yet": blah blah blah. if "max_attemts", then reboot like the old days
            #
            tries = 0
            while tries < 3:
                tries = tries + 1
                try:
                    # unload the module
                    cmd_output = subprocess.check_output("sudo modprobe -r brcmfmac", shell=True)
                    logging.info("[FixBRCMF] unloaded brcmfmac")
                    if display: display.update(force=True, new_data={"status": "Turning it off...",
                                                                     "face":faces.SMART})
                    else: print("Turning it off #%d" % tries)
                    time.sleep(tries)
                    
                    # reload the module
                    try:
                        # reload the brcmfmac kernel module
                        cmd_output = subprocess.check_output("sudo modprobe brcmfmac", shell=True)
                        if not display: print("reloaded brcmfmac")
                        logging.info("[FixBRCMF] reloaded brcmfmac")
                        time.sleep(5 * tries) # give it some time for wlan device to stabilize, or whatever

                        # success! now make the mod0
                        try:
                            cmd_output = subprocess.check_output("sudo iw phy \"$(iw phy | head -1 | cut -d' ' -f2)\" interface add mon0 type monitor && sudo ifconfig mon0 up", shell=True)
                            if not display: print("mon0 recreated on attempt #%d" % tries)
                            tries = 5
                        except Exception as cerr: 
                            if not display: print("failed loading mon0 attempt #%d: %s", (tries, repr(cerr)))
                        
                    except Exception as err: # from modprobe
                        if not display: print("Failed unloading brcmfmac")
                        logging.error("[FixBRCMF] Failed unloading brcmfmac %s" % repr(err))

                    
                except Exception as nope: # from modprobe -r
                    # fails if already unloaded, so probably fine
                    logging.error("[FixBRCMF #%d modprobe -r] %s" % (tries, repr(nope)))
                    if not display: print("[FixBRCMF #%d modprobe -r] %s" % (tries, repr(nope)))
                    pass
            
                if tries < 3:
                    logging.info("[FixBRCMF] mon0 didn't make it. trying again")
                    if not display: print(" mon0 didn't make it. trying again")

            # exited the loop, so hopefully it loaded
            if tries is 5:
                logging.info("[FixBRCMF] WOOHOO!!!!! I think it really worked!")
                if display: display.update(force=True, new_data={"status": "And back on again...",
                                                                 "face":faces.INTENSE})
                else: print("And back on again...")
                logging.info("[FixBRCMF] mon0 back up")
                time.sleep(5) # give it a second before telling bettercap


                logging.info("[FixBRCMF] renable recon")

                try:
                    result = connection.run("set wifi.interface mon0; wifi.clear; wifi.recon on")
                    if result["success"]:
                        if display: display.update(force=True, new_data={"status": "I can see again! (probably)",
                                                                         "face":faces.HAPPY})
                        else: print("I can see again")
                        logging.info("[FixBRCMF] wifi.recon on")
                        self.LASTTRY = time.time() + 120 # 2 minute pause until next time.
                    else:
                        logging.error("[FixBRCMF] wifi.recon did not start up: %s" % repr(result))

                except Exception as err:
                    logging.error("[FixBRCMF wifi.recon on] %s" % repr(err))
            else:
                self.LASTTRY = time.time()
            self.isReloadingMon0 = False


if __name__ == "__main__":
    print("Performing brcmfmac reload and restart mon0...")
    fb =  Fix_BRCMF()

    data = {'Message': "kernel: brcmfmac: brcmf_cfg80211_nexmon_set_channel: Set Channel failed: chspec=1234"}
    event = {'data': data}


    agent = Client('localhost', port=8081, username="pwnagotchi", password="pwnagotchi");                    

    fb.on_bcap_sys_log(agent, event)
    

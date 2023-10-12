import os
import time
import logging
import subprocess

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts


class RSS_Voice(plugins.Plugin):
    __author__ = 'Sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Use RSS Feeds to replace canned voice messages on various events'

#     main.plugins.rss_voice.enabled = true
#     main.plugins.rss_voice.feed.wait.url = "https://www.reddit.com/r/worldnews.rss"
#     main.plugins.rss_voice.feed.bored.url = "https://www.reddit.com/r/showerthoughts.rss"
#     main.plugins.rss_voice.feed.sad.url = "https://www.reddit.com/r/pwnagotchi.rss"

    
    def __init__(self):
        logging.debug("example plugin created")
        self.voice = ""


    def _wget(self, url, rssfile, verbose = False):
        logging.info("RSS_Voice _wget %s: %s" % (rssfile, url))
        process = subprocess.run(["/usr/bin/wget", "-q", "-O", rssfile, url])
        logging.info("RSS_Voice: %s", repr(process))

    def _fetch_rss_message(self, key):
        rssfile = "/root/voice_rss/%s.rss" % key
        if os.path.isfile(rssfile):
            logging.info("RSS_Voice pulling from %s" % (rssfile))
            random_headline = "grep -Po \'<title>((?!<).)*</title>\' " + rssfile + " | sed \'s/<title>//g\' | sed \'s/<\/title>//g\' | shuf -n 1 | cut -c -64"
            headline = os.popen(random_headline).read().rstrip()

            logging.info("RSS_Voice %s: %s" % (key, headline))
            
            return headline
        
    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        # do something to edit RSS urls
        pass

    # called when the plugin is loaded
    def on_loaded(self):
        logging.warning("RSS_Voice options = %s" % self.options)

    # called before the plugin is unloaded
    def on_unload(self, ui):
        pass

    # called hen there's internet connectivity
    def on_internet_available(self, agent):
        # check rss feeds, unless too recent
        logging.debug("RSS_Voice internet available")
        if "feed" in self.options:
            now = time.time()
            feeds = self.options["feed"]
            logging.debug("RSS_Voice processing feeds: %s" % feeds)
            for k,v in feeds.items():   # a feed value can be a dictionary
                logging.debug("RSS_Voice feed: %s = %s" % (repr(k), repr(v)))
                timeout = 3600 if "timeout" not in v else v["timeout"]
                logging.debug("RSS_Voice %s timeout = %s" % (repr(k), timeout))
                try:
                    # update feed if past timeout since last check
                    rss_file = "/root/voice_rss/%s.rss" % k
                    if os.path.isfile(rss_file) and now < os.path.getmtime(rss_file) + timeout:
                        logging.debug("too soon by file age!")
                    else:
                        if "url" in v:
                            self._wget(v["url"], rss_file)
                        else:
                            logging.warn("No url in  %s" % repr(v))
                except Exception as e:
                    logging.error("RSS_Voice: %s" % repr(e))
        pass

    # called to setup the ui elements
    def on_ui_setup(self, ui):
        #
        # use built in elements, probably
        #
        # add custom UI elements
        #ui.add_element('ups', LabeledValue(color=BLACK, label='UPS', value='0%/0V', position=(ui.width() / 2 - 25, 0),
        #                                   label_font=fonts.Bold, text_font=fonts.Medium))
        pass

    # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        if self.voice != "":
            logging.info("RSS: Status to %s" % self.voice)
            ui.set('status', self.voice)
            self.voice = ""

    # called when the hardware display setup is done, display is an hardware specific object
    def on_display_setup(self, display):
        pass

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self.on_internet_available(agent)
        # you can run custom bettercap commands if you want
        #   agent.run('ble.recon on')
        # or set a custom state
        #   agent.set_bored()

    # set up RSS feed per emotion
    
    # called when the status is set to bored
    def on_bored(self, agent):
        self.voice = self._fetch_rss_message("bored")
        pass

    # called when the status is set to sad
    def on_sad(self, agent):
        self.voice = self._fetch_rss_message("sad")
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
        self.voice = "(%ss) %s" % (int(t), self._fetch_rss_message("wait"))
        logging.info("RSS_Voice on_wait: %s" % self.voice)


    # called when the agent is sleeping for t seconds
    def on_sleep(self, agent, t):
        self.voice = "(%ss zzz) %s" % (int(t), self._fetch_rss_message("sleep"))

    # called when an epoch is over (where an epoch is a single loop of the main algorithm)
    def on_epoch(self, agent, epoch, epoch_data):
        pass

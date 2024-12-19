import logging
import random
import os
import json

from os import listdir
from pathlib import Path

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.grid as grid


# Spam_Peers plugin
#
# Automatically send canned pwnmail messages to any new pwnagotchis you see. You can specify a list
# of known pwnagotchis that you will not send messages to. Any other pwnagotchi encountered will
# be sent an automated pwnmail message on the first encounter PER SESSION. The list is only stored in
# memory and will be reset when pwnagotchi restarts or reboots.  "known_peers" can be
# initialized from config.toml, so you can avoid having your own pwnagotchis spam each other.
#
# Customize the messages sent to peers in config.toml, like:
#
# main.plugins.spam_peers.enabled = true
# main.plugins.spam_peers.messages = [ "Hey buddy!", "Pwn here often?", "OMG! No way! A wild pwnagotchi!!!" ]
# main.plugins.spam_peers.known_peers = [ "put_fingerprints_of_your_other_pwnies_here",
#                                         "so_you_dont_spam_yourself_if_you_dont_want_to"]

class Spam_Peers(plugins.Plugin):
    __author__ = '@Sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Automatically send message to a new peers'

    def __init__(self):
        logging.debug("spam peers plugin created")
        # default message from @ABE's design specification :)
        self.messages = [ "THIS TOWN AINT BIG ENOUGH FOR THE 2 OF US" ]
        self.known_peers = []
        for f in os.listdir("/root/peers"):
            with open("/root/peers/" + f, 'r') as fp:
                p = json.load(fp)
            try:
                name=p['advertisement']['name']
                logging.info("Known peer %s %s" % (name, Path(f).stem))
                self.known_peers.append(Path(f).stem)
            except Exception as e:
                logging.info("Unknown peer %s %s" % (Path(f).stem, repr(p)))

        logging.info("I know %d peers" % len(self.known_peers))

    # called when the plugin is loaded
    def on_loaded(self):
        if "messages" in self.options:
            self.messages = self.options["messages"]
        if "known_peers" in self.options:
            self.known_peers = self.options["known_peers"]

        logging.info("spam_peers loaded.")
        logging.debug("Spamming peers with %d messages" % len(self.messages))

    # called when a new peer is detected
    def on_peer_detected(self, agent, peer):
        try:
            peer_print = peer.adv['identity']

            # only send when first seen, per session
            if peer_print not in self.known_peers:
                self.known_peers.append(peer_print)
                logging.info("Sending pwnmail to %s" % (repr(peer_print)))
                grid.send_message(peer_print, random.choice(self.messages))
            else:
                logging.info("Not spamming %s. On the list already" % (repr(peer_print)))
        except Exception as e:
            logging.info("spam_peers error: %s" % repr(e))

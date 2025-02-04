import logging
import os, sys

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts


try:
    sys.path.append(os.path.dirname(__file__))
    from Touch_UI import Touch_Button, Touch_Screen
    TOUCH_ENABLED = True
except Exception as e:
    TOUCH_ENABLED = False
    logging.debug(repr(e))

class enable_deauth(plugins.Plugin):
    __author__ = 'Sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Enable and disable DEAUTH on the fly. Enabled when plugin loads, disabled when plugin unloads.'

    def __init__(self):
        self._agent = None
        self._count = 0
        self.hasTouch = TOUCH_ENABLED
        self._touchscreen = None
        self._behave_list = []
        self._behave = False
        self._deauth_enable = True

        self._current_aps = []

    # make web_ui that lists hosts. click to add to behave_list, or deauth
    # button to toggle

    # called when the plugin is loaded
    def on_loaded(self):
        logging.info("[EnableDeauth] loaded %s" % repr(self.options))
        self._count = 0

        # set personality.deauth to this when ready
        self._deauth_enable = self.options.get('deauth_enable', True)

        # disable deauths when one of listed nets is visible
        self._behave_list = self.options.get('behave_list', [])

    # called before the plugin is unloaded
    def on_unload(self, ui):
        if self._agent:
            self._agent._config['personality']['deauth'] = False
        try:
            ui.remove_element('deauth_count')
        except Exception as e:
            logging.warn(repr(e))

        logging.info("[Enable_Deauth] unloading: disabled deauth")

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._agent = agent

        self.hasTouch = self._touchscreen and self._touchscreen.running

        if self.hasTouch and self._ui:
            self._ui._state._state['deauth_count'].state = self._agent._config['personality']['deauth']
        else:
            # turn on when plugin loads, and off on unload
            agent._config['personality']['deauth'] = self._deauth_enable

        logging.info("[Enable_Deauth] ready: enabled deauth")

    def on_touch_ready(self, touchscreen):
        self._touchscreen = touchscreen
        self.hasTouch = self._touchscreen and self._touchscreen.running
        logging.info("[DEAUTH] Touchscreen %s" % repr(touchscreen))

    # click on release
    def on_touch_release(self, ts, ui, ui_element, touch_data):
        logging.debug("[DEAUTH] Touch press: %s" % repr(touch_data));
        try:
            if ui_element == "deauth_count":
                logging.debug("Toggling %s" % repr(self._agent._config['personality']['deauth']))
                self._deauth_enable = self._ui._state._state['deauth_count'].state
                self._agent._config['personality']['deauth'] = self._deauth_enable
                self._behave = False

                logging.info("Toggled deauth to %s" % repr(self._ui._state._state['deauth_count'].state))

        except Exception as err:
            logging.info("%s" % repr(err))

    def on_deauthentication(self, agent, access_point, client_station):
        self._count += 1

    # called to setup the ui elements
    def on_ui_setup(self, ui):
        self._ui = ui
        # add custom UI elements
        try:
            if "position" in self.options:
                pos = self.options['position'].split(',')
                pos = [int(x.strip()) for x in pos]
            else:
                pos = (0,36,30,59)

            try:
                curstate = self._agent._config['personality']['deauth'] if self._agent else True
                ui.add_element('deauth_count', Touch_Button(position=pos,
                                                            color='#ddddff', alt_color='White', outline='DarkGray',
                                                            state=curstate,
                                                            text="deauth", value=0, text_color="Black",
                                                            alt_text=None, alt_text_color="Green",
                                                            font=fonts.Medium, alt_font=fonts.Medium,
                                                            shadow="Black", highlight="White",
                                                            event_handler="enable_deauth"
                                                            )
                               )
            except Exception:
                ui.add_element('deauth_count', LabeledValue(color=BLACK, label='D', value='', position=pos,
                                                           label_font=fonts.BoldSmall, text_font=fonts.Small))
        except Exception as err:
            logging.info("enable deauth ui error: %s" % repr(err))

    # called when refreshing AP list
    def on_unfiltered_ap_list(self, agent, access_points):
        oh_behave = False
        for ap in access_points:
            if ap.get('hostname', '[no hostname]') in self._behave_list:
                oh_behave = True
                if self._behave == False:
                    logging.info("%s visible: behaving" % ap.get('hostname', '[unknown]'))
            elif ap.get('mac', '[no hostname]').lower() in self._behave_list:
                oh_behave = True

        # temporary setting, so disable, but do not
        # change self._deauth_enable
        if oh_behave and not self._behave:
            self._behave = True
            agent._config['personality']['deauth'] = False
            logging.info("Home networks visible. Pausing")
            if self._ui:
                d_label = self._ui._state._state['deauth_count']
                try:
                    d_label.label = d_label.label.lower()
                except Exception as e:
                    d_label.text = d_label.text.lower()
        elif self._behave and not oh_behave:
            self._behave = False
            logging.info("Home networks gone. Enabled: %s", self._deauth_enable)
            agent._config['personality']['deauth'] = self._deauth_enable
            if self._ui:
                d_label = self._ui._state._state['deauth_count']
                try:
                    d_label.label = d_label.label.capitalize()
                except Exception as e:
                    d_label.text = d_label.text.capitalize()


    # Switch off deauths as soon as a home network shows up
    def on_bcap_wifi_ap_new(self, agent, event):
        try:
            if agent._config['personality']['deauth']:
                ap = event['data']
                apname = ap['hostname']
                apmac = ap['mac'].lower()

                if apname in self._behave_list or apmac in self._behave_list:
                    self._behave = True
                    logging.info("%s (%s) appeared: behaving" % (apname, apmac))
                    agent._config['personality']['deauth'] = False
                    if self._ui:
                        d_label = self._ui._state._state['deauth_count']
                        try:
                            d_label.label = d_label.label.lower()
                        except Exception as e:
                            d_label.text = d_label.text.lower()

        except Exception as e:
            logging.exception(repr(e))

    # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        try:
            ui.set('deauth_count', str(self._count))  # Update with current deauth count
        except Exception as err:
            logging.info("enable deauth ui error: %s" % repr(err))

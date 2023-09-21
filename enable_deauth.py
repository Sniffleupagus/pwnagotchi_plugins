import logging

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts


class Do_Deauth(plugins.Plugin):
    __author__ = 'Sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Enable and disable DEAUTH on the fly. Enabled when plugin loads, disabled when plugin unloads.'

    def __init__(self):
        self._agent = None
        self._count = 0
        pass
    
    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        pass

    # called when the plugin is loaded
    def on_loaded(self):
        self._count = 0
        pass

    # called before the plugin is unloaded
    def on_unload(self, ui):
        if self._agent: self._agent._config['personality']['deauth'] = False
        ui.remove_element('deauth_count')
        logging.info("[Enable_Deauth] unloading: disabled deauth")
        pass

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        agent._config['personality']['deauth'] = True
        self._agent = agent
        logging.info("[Enable_Deauth] ready: enabled deauth")

    def on_touch_ready(self, touchscreen):
        logging.info("[DEAUTH] Touchscreen %s" % repr(touchscreen))

    def on_touch_press(self, ts, ui, ui_element, touch_data):
        logging.info("[DEAUTH] Touch press: %s" % repr(touch_data));
        try:
            if 'point' in touch_data:
                point = touch_data['point']
                if point[0] > 50 and point[1] > 190:
                    logging.info("[DEAUTH] Toggling %s" % repr(self._agent._config['personality']['deauth']))
                    self._agent._config['personality']['deauth'] = not self._agent._config['personality']['deauth']
                    uiItems = ui._state._state
                    uiItems['deauth_count'].label = uiItems['deauth_count'].label.upper() if self._agent._config['personality']['deauth'] else uiItems['deauth_count'].label.lower()

        except Exception as err:
            logging.info("%s" % repr(err))

    def on_deauthentication(self, agent, access_point, client_station):
        self._count += 1
        pass

    # called to setup the ui elements
    def on_ui_setup(self, ui):
        # add custom UI elements
        try:
            if "position" in self.options:
                pos = self.options['position'].split(',')
                pos = [int(x.strip()) for x in pos]
            else:
                pos = (0,36)
            
            ui.add_element('deauth_count', LabeledValue(color=BLACK, label='D', value='0', position=pos,
                                                        label_font=fonts.BoldSmall, text_font=fonts.Small))
        except Exception as err:
            logging.info("enable deauth ui error: %s" % repr(err))

        # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        try:
            ui.set('deauth_count', "%d" % (self._count))
        except Exception as err:
            logging.info("enable deauth ui error: %s" % repr(err))

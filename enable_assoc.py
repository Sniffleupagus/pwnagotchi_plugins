import logging

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts


class Do_Assoc(plugins.Plugin):
    __author__ = 'evilsocket@gmail.com'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Enable and disable ASSOC  on the fly. Enabled when plugin loads, disabled when plugin unloads.'

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
        if self._agent: self._agent._config['personality']['associate'] = False
        ui.remove_element('assoc_count')
        logging.info("[Enable_Assoc] unloading: disabled association")
        pass

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        agent._config['personality']['associate'] = True
        self._agent = agent
        logging.info("[Enable_Assoc] ready: enabled association")

    def on_touch_ready(self, touchscreen):
        logging.info("[ASSOC] Touchscreen %s" % repr(touchscreen))

    def on_touch_press(self, ts, ui, ui_element, touch_data):
        logging.info("[ASSOC] Touch press: %s" % repr(touch_data));
        try:
            if 'point' in touch_data:
                point = touch_data['point']
                if point[0] > 50 and point[1] < 50:
                    logging.info("[ASSOC] Toggling %s" % repr(self._agent._config['personality']['associate']))
                    self._agent._config['personality']['associate'] = not self._agent._config['personality']['associate']
                    uiItems = ui._state._state
                    uiItems['assoc_count'].label = uiItems['assoc_count'].label.upper() if self._agent._config['personality']['associate'] else uiItems['assoc_count'].label.lower() 

        except Exception as err:
            logging.info("%s" % repr(err))

    def on_touch_release(self, ts, ui, ui_element, touch_data):
        logging.info("[ASSOC] Touch release: %s" % repr(touch_data));

    def on_association(self, agent, access_point):
        self._count += 1
        pass

    # called to setup the ui elements
    def on_ui_setup(self, ui):
        # add custom UI elements
        if "position" in self.options:
            pos = self.options['position'].split(',')
            pos = [int(x.strip()) for x in pos]
        else:
            pos = (0,29)
            
        ui.add_element('assoc_count', LabeledValue(color=BLACK, label='A', value='0', position=pos,
                                                   label_font=fonts.BoldSmall, text_font=fonts.Small))

        # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        ui.set('assoc_count', "%d" % (self._count))

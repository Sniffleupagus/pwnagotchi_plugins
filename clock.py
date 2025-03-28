from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins
import pwnagotchi
import logging
import datetime
import os
import toml
import yaml


class PwnClock(plugins.Plugin):
    __author__ = 'https://github.com/LoganMD'
    __version__ = '1.0.2'
    __license__ = 'GPL3'
    __description__ = 'Clock/Calendar for pwnagotchi'

    def on_loaded(self):
        if 'date_format' in self.options:
            self.date_format = self.options['date_format']
        else:
            self.date_format = "%m/%d/%y%n%I:%M %p"

        logging.info("Pwnagotchi Clock Plugin loaded.")

    def on_ui_setup(self, ui):
        pos = (130, 80)
        ui.add_element('clock', LabeledValue(color=BLACK, label='', value='-/-/-\n-:--',
                                             position=pos,
                                             label_font=fonts.Small, text_font=fonts.Small))

    def on_ui_update(self, ui):
        now = datetime.datetime.now()
        time_rn = now.strftime(self.date_format)
        ui.set('clock', time_rn)

    def on_unload(self, ui):
        ui.remove_element('clock')

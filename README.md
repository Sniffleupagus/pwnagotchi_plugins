# pwnagotchi_plugins

Plugins for <a href="https://github.com/evilsocket/pwnagotchi/releases/latest">pwnagotchi</a>

# fix_brcmfmac.py
Substitute for WATCHDOG that pauses wifi.recon, deletes the mon0 interface and the brcfmac kernel module,
then reloads the module, remakes mon0, then restarts wifi.recon. No more rebooting every time one little
annoying thing goes wrong. So far not configurable.

# blemon_plugin.py
Counts BLE devices and max # seen at a time in the upper left under the line. Not very configurable yet.
<b>REQUIRES</b> modified <a href="https://github.com/Sniffleupagus/pwnagotchi-snflpgs/blob/master/pwnagotchi/agent.py">agent.py</a>
from my fork of the evilsocket repository.<p>

Conflicts with bt-tether (because bettercap takes the bluetooth device). Enable and disable them as
needed in the plugins tab of the webUI, without having to restart pwnagotchi.

The modified agent.py calls plugins.on("bcap_{EVENT_NAME}", blah blah, blah), so all the plugins can
access anything that happens in bettercap. Some events may need to be unignored in the Events tab of
bettercap, or removed from the config so they don't keep coming back.<p>



# morse_code.py

Modified from the stock led.py plugin. It flashes morse code on the LED in response to events. It should
work with the stock agent.py, but it will have more to blink about if you use the modified version. Messages
are hard coded right now, configurable next time. Maybe.

<code>
main.plugins.morse_code.enabled = true
main.plugins.morse_code.led = 0
main.plugins.morse_code.delay = 200
</code>

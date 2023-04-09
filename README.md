# pwnagotchi_plugins

Plugins for <a href="https://github.com/evilsocket/pwnagotchi/releases/latest">pwnagotchi</a>

<img width="314" alt="netsucker-ble-uptime" src="https://user-images.githubusercontent.com/129890632/230241710-fd7047ce-89ac-4252-8812-4a51b3e6a2bc.png">

# fix_brcmfmac.py
<i>Did you try turning wlan0 off and on again?</i><p>

Substitute for WATCHDOG that tries to fix the problem instead of rebooting. It checks the logs
with journalctl, like watchdog. If it finds the "cant change channels" log messages it will:<p>

<ol>
<li>pauses wifi.recon in bettercap
<li>delete the mon0 interface
<li>modprobe -r brcfmac (unload kernel module for wlan0)
<li>modprobe brcfmac (reload it)
<li>remake mon0
<li> restarts wifi.recon in bettercap
</ol>

Each epoch, it will make up to 3 attempts to reload the module. If it succeeds, it will
wait at least 3 minutes for the lines in the logfile that already triggered it will have
moved on.<p>

Epoch detect/fix is not 100%. If you notice your pwnagotchi is blind, you can disable and
enable this plugin in the web ui, and it will check for mon0, and read the syslog and try
another reset if either of those looks wrong. [REQUIRES <a href="https://github.com/Sniffleupagus/pwnagotchi-snflpgs/commit/70bffe52001cc951814219a3f791008428ac707e">changes to agent.py and bettercap.py</a> to
give plugins more access to bettercap events]<p>

fix_brcmfmac.py can also be run on the command line if the plugin isn't getting it.<p>
<code>% python3 ./fix_brcmfmac.py
  Performing brcmfmac reload and restart mon0...
  Wifi recon paused
  mon0 down!
  Turning it off #1
  reloaded brcmfmac
  mon0 recreated on attempt #1
  And back on again...
  I can see again
  %</code><p>

<b>No more rebooting</b> every time one little annoying thing goes wrong (over and over and over). Long uptime! AI mode
just keeps going! So far not configurable. Pauses have been tweaked to <i>seem to work most of the time</i>
on a Rpi4, Rpi3, and Rpi0W.

# blemon_plugin.py
Counts BLE devices and max # seen at a time in the upper left under the line. Gets BLE info from bettercap events.
<b>REQUIRES</b> modified <a href="https://github.com/Sniffleupagus/pwnagotchi-snflpgs/blob/master/pwnagotchi/agent.py">agent.py</a>
from my fork of the evilsocket repository.<p>

The modified agent.py calls plugins.on("bcap_{event_name}", blah blah, blah), so all the plugins can
access anything that happens in bettercap. Some events may need to be unignored in the Events tab of
bettercap, or removed from the config so they don't keep coming back.<p>

Conflicts with bt-tether (because bettercap takes over the bluetooth device to scan). Enable and disable them as
needed in the plugins tab of the webUI, without having to restart pwnagotchi.

# enable_assoc.py and enable_deauth.py

When loaded or unloaded, these plugins turn on or off personality associate or deauth. Change behavior on the fly, without
restarting. Go to the plugins tab on webUI, and turn them on and off. No configuration. They change <code>agent._config['personality']['associate|deauth']</code> directly, so these plugins will affect "save and reboot" from web_cfg.<p>

# gps_more.py

Modified from stock gps.py. From loading, it will update GPS on epoch until it gets a fix, then just update for
handshakes. That way you can see that it is working before a handshake happens. Optionally saves all gps locations to a file (epoch and handshakes), like a breadcrumb trail.<p>

<code>main.plugins.gps_more.enabled = true
main.plugins.gps_more.device = "/dev/ttyACM0"
main.plugins.gps_more.speed = "9600"
main.plugins.gps_more.keepGPSOn = true               # don't send "gps off", so bettercap keeps lock
main.plugins.gps_more.save_file = "/root/gpstracks/%Y/gps_more_%Y%m%d.gps.json"</code><p>

<code>save_file</code> is processed by <code>strftime()</code>, so you can have a file per day, month, whatever. Also saves fixed with handshake
files like the original.


# morse_code.py

Modified from the stock led.py plugin. It flashes morse code on the LED in response to events. It should
work with the stock agent.py, but it will have more to blink about if you use the modified version. Messages
are generated in the code right now, but not configurable as config options yet. 

<code>main.plugins.morse_code.enabled = true
main.plugins.morse_code.led = 0                     # 0 is green light. 1 is the stupid bright red light on Pi3&4
main.plugins.morse_code.delay = 200</code>          # length of a dot in milliseconds. other timing is relative
main.plugins.morse_code.invert = True               # if 1 is off and 0 is on, like Rpi0w
main.plugins.morese_code.leaveOn = False            # leave light on (off if false) at end of message

# pwnagotchi_plugins

Plugins for <a href="https://github.com/evilsocket/pwnagotchi/releases/latest">pwnagotchi</a>

<img width="314" alt="netsucker-ble-uptime" src="https://user-images.githubusercontent.com/129890632/230241710-fd7047ce-89ac-4252-8812-4a51b3e6a2bc.png">

# fix_brcmfmac.py
<b>Might be too aggressive and restarting unnecessarily. Not currently using it.<p>
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

# meshpwnstic.py

Remote control and update pwnagotchi over Meshtastic LoRa network. This requires the meshtastic python library, install with: <code> pip3 install meshtastic</code>. By default, it connects to an instance of meshtastic running on the same raspberry pi as pwnagotchi. You can specify a different host, or a serial port in configuration, for example
<code>main.plugins.meshpwnstic.host = "127.0.0.1"
main.plugins.meshpwnstich.port = "/dev/ttyS0"
</code> 
But that has not been tested. 

The plugin does not configure the meshtastic node. You should set it up using a different client before having pwnagotchi connect to it. Messages are broadcast on the default channel, or sometimes as replies to direct messages. I strongly suggest changing your primary to a private channel if you are going to use this to not annoy people.

You can send commands to the pwnagotchi:

- "/echo blah blah" send back whatever you tell it to echo. 
- "/deauth [on/off]" will turn deauths on or off. With no option, it will return state and number of deauths in this session.
- "/assoc [on/off]" similar for association.
- "/bcap bettercap command" will run the command on bettercap and return the result in a message (maybe to the channel). Examples, "/bcap wifi.clear", "/bcap wifi.recon on", etc.
- "/status" will send uptime, and some stats.
- "/restart [manu]" will restart pwnagotchi in auto unless specified.

Meshpwnstic understands most messages that are sent over the radios. It will display a console showing the last few messages, configurable as option "showLines". Probably better suited to bigger screens. Unknown messages are not displayed, but will show in the log file. Meshpwnstic makes a lot of log messages if you have a lot of radio traffic.

# miyagi.py

Mr. Miyagi trained the Karate Kid. Miyagi.py trains pwnagotchis. When the plugin is loaded (manually or when pwnagotchi starts up), if laziness if high (> 0.9), it will drop it to 0.5 to increase likelihood of entering a training session. At the start of training, Miyagi moves brain.nn to brain.nn.bak, backing up the brain, in case of failure. During training, Miyagi updates the MODE display to let you know how many epochs of training have happened in the session. A standard session lasts 50 epochs. At the end of the 50 epochs, laziness will be increased slightly, to slowly reduce the amount of training over time.<p>

Future versions will have the ability to change the AI and personality parameters on the fly.<p>


# more_uptime.py
 
  Display cycles between system UPtime (since reboot), PRocess uptime (since pwnagotchi started this time), and plugIN uptime (since this plugin was (re)loaded... like a really bad stopwatch). By default the uptime is underneath the line
  below the existing uptime. Configuration options allow repositioning, or to override the stock UP display. Override seems to work on pi0w, but is unreliable on multiprocessors.
  
  <code>main.plugins.more_uptime.enables = true
    main.plugins.more_uptime.override = false
    main.plugins.more_uptime.position = "184,11"
  </code>

# morse_code.py

Modified from the stock led.py plugin. It flashes morse code on the LED in response to events. It should
work with the stock agent.py, but it will have more to blink about if you use the modified version. Messages
are generated in the code right now, but not configurable as config options yet. 

<code>main.plugins.morse_code.enabled = true
main.plugins.morse_code.led = 0                    
main.plugins.morse_code.delay = 200                 # length of a dot in milliseconds. other timing is relative
main.plugins.morse_code.invert = True               # if 1 is off and 0 is on, like Rpi0w
main.plugins.morese_code.leaveOn = False            # leave light on (off if false) at end of message </code>

 main.plugins.morse_code.led can be specified as an integer to pick an led from /sys/class/leds/led%d, or a full pathname like "/sys/class/leds/PWR/brightness" on pizero2w (might be ACT instead of PWR), or "GPIO6" for an LED on GPIO pin 6 (change the number for other pins...)

# rss_voice.py

An attempt to change canned voice messages to RSS feed. Idea from reddit post: https://www.reddit.com/r/pwnagotchi/comments/ioyg8w/modified_my_pwnagotchi_voicepy_to_return_a_random/

but attempting to use a plugin, instead of modifying the base code. Unfortunately "on_wait" only gets called
at the start of a long wait, while view and voice update many times during a long wait, without calling the
plugin handlers again. So either voice.py or view.py needs to be modified anyway. The plugin will work without
modified code, but the headline will get overwritten with a canned message after a few seconds.

# tweak_view.py
  
Edit the UI on the fly. It is a terrible user interface. You can break things. But move user interface elements
  around, change fonts (among the available sizes), change labels. From webui plugins page, click on "tweak_view" to
  bring up the <b>very rough</b> interface. Make changes carefully. Click "Update" at the bottom, and then go back and
  look at what you've done.
  
  THERE IS A BUG where it sometimes turns all the fonts to "SMALL". Check the form to make sure everything isn't Small before submitting, or delete all the undesired mods on the result page, if you didn't. Its really annoying. The face looks funny in Small font.
  
  All of the changes/tweaks/mods are saved in /etc/pwnagotchi/tweak_view.json, formatted for easy deleting. Changes to the
  file can be picked up by reloading the plugin (arguably a better interface, once you know the format, than changing
  things through the webui).
  
  This directly changes the position, font, label and other settings that are otherwise hard coded in the init code for each kind of hardware. The changes are done in the data structures in memory (agent._view._state._state[blah].bleah), not to any files (other than tweak_view.json, duh). It might have concurrency issues sometimes. The plugin tried to restore the
  original state when it is unloaded, but if it gets messed up, restarting pwnagotchi after disabling the plugin or
  editing/deleting the "tweak_view.json" file will restore things back to normal.
  
  Changes can take a few screen updates to take effect, depending on when the values updated. This plugin does not trigger any updates itself.
  

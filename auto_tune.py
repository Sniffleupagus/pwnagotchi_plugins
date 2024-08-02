import logging
import random
import time

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.utils
from pwnagotchi.utils import save_config, merge_config

from flask import abort
from flask import render_template_string

class auto_tune(plugins.Plugin):
    __author__ = 'sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin that adjust AUTO mode parameters'

    def __init__(self):
        self._histogram = {'loops': 0 }
        self._unscanned_channels = []
        self._active_channels = []
        self._agent = None

        self.descriptions = {
            "advertise": "enable/disable advertising to mesh peers",
            "deauth" : "enable/disable deauthentication attacks",
            "associate" : "enable/disable association attacks",
            "throttle_a" : "delay after an associate. Some delay seems to reduce nexmon crashes",
            "throttle_d" : "delay after a deauthenticate. Delay helps reduce nexmon crashes",
            "assoc_prob" : "probability of trying an associate attack. Set lower to spread out interaction instead of hitting all APs every time until max_interactions",
            "deauth_prob" : "probability of trying a deauth. will spread the 'max_interactions' over a longer time",
            "min_rssi" : "ignore APs with signal weaker than this value. lower values will attack more distant APs",
            "recon_time" : "duration of the bettercap channel hopping scan phase, to discover APs before sending attacks",
            "min_recon_time" : "time spent on each occupied channel per epoch, sending attacks and waiting for handshakes. and epoch is recon_time + #channels * min_recon_time seconds long",
            "ap_ttl" : "APs that have not been seen since this many seconds are ignored. Shorten this if you are moving, to not try to scan APs that are no longer in range.",
            "sta_ttl" : "Clients older than this will ignored",
        }


    def showEditForm(self, request):
        path = request.path if request.path.endswith("/update") else "%s/update" % request.path

        ret = '<form method=post action="%s">' % path
        ret += '<input id="csrf_token" name="csrf_token" type="hidden" value="{{ csrf_token() }}">'

        for secname, sec in [["Personality", self._agent._config['personality']],
                             ["AUTO Tune", self._agent._config['main']['plugins']['auto_tune']]]:
            ret += '<h2>%s Variables</h2>' % secname
            ret += '<table>\n'
            ret += '<tr align=left><th>Parameter</th><th>Value</th><th>Description</th></tr>\n'

            for p in sorted(sec):
                if type(sec[p]) in [int, str, float, bool]:
                    cls = type(sec[p]).__name__
                    ret += "<tr align=left>"
                    if cls == "bool":
                        ret += '<th>%s</th><td style="white-space:nowrap; vertical-align:top;">' % (p)
                        checked = " checked" if sec[p] else ""
                        ret += 'True:&nbsp;<input type=radio id="newval,%s,%s,%s" name="newval,%s,%s,%s" value="%s" %s>&nbsp;' % (sec[p], p, cls, sec[p], p, cls, "True", checked)
                        checked = " checked" if not sec[p] else ""
                        ret += 'False:&nbsp;<input type=radio id="newval,%s,%s,%s" name="newval,%s,%s,%s" value="%s" %s>' % (sec[p], p, cls, sec[p], p, cls, "False", checked)
                        ret += "</td>"
                    else:
                        ret += '<th>%s</th>' % (p)
                        ret += '<td><input type=text id="newval,%s,%s,%s" name="newval,%s,%s,%s" size="5" value="%s"></td>' % (sec[p], p, cls, sec[p], p, cls, sec[p])
                        #ret += '<tr><th>%s</th>' % ("" if p not in self.descriptions else self.descriptions[p])
                    if p in self.descriptions:
                        ret += "<td>%s</td>" % self.descriptions[p]
                    ret += '</tr>\n'
            ret += "</table>"
        ret += '<input type=submit name=submit value="update"></form><p>'
        return ret

    def showHistogram(self):
        ret = ""
        histo = self._histogram
        nloops = int(histo["loops"])
        if nloops > 0:
            ret += "<h2>APs per Channel over %s epochs</h2>" % (nloops)
            ret += "<table border=1 spacing=4 cellspacing=1>"
            chans = "<tr><th>Channel</th>"
            totals = "<tr><th>APs seen</th>"
            vals = "<tr><th>Avg APs/epoch</th>"

            for (ch, count) in sorted(histo.items(), key=lambda x:x[1], reverse = True):
                if ch == "loops":
                    pass
                else:
                    weight = float(count)/nloops
                    #ret +="<tr><th>%d</th><td>%0.2f</td>" % (ch, count)
                    chans += "<th>%s</th>" % ch
                    totals += "<td align=right>%d</td>" % count
                    vals += "<td align=right>%0.1f</td>" % weight
            chans += "</tr>"
            totals += "</tr>"
            vals += "</tr>"
            ret += chans + totals + vals
            ret += "</table>"
        else:
            ret += "<h2>No channel data collected yet</h2>"

        return ret

    def update_parameter(self, cfg, parameter, vtype, val, ret):
        changed = False
        if parameter in cfg:
            old_val = cfg[parameter]

            if val == old_val:
                pass
            elif vtype == "int":
                cfg[parameter] = int(val)
                changed = True
            elif vtype == "float":
                cfg[parameter] = float(val)
                ret += "Updated float %s: %s -> %s<br>\n" % (parameter, old_val, val)
                changed = True
            elif vtype == "bool":
                cfg[parameter] = bool(val == "True")
                ret += "Updated boolean %s: %s -> %s<br>\n" % (parameter, old_val, val)
                changed = True
            elif vtype == "str":
                cfg[parameter] = val
                ret += "Updated string %s: %s -> %s<br>\n" % (parameter, old_val, val)
                changed = True
            else:
                ret += "No update %s (%s): %s -> %s<br>\n" % (parameter, type, old_val, val)

        return changed

    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        # display personality parameters for editing
        # show statistic per channel, etc
        if not self._agent:
            ret = "<html><head><title>AUTO Tune not ready</title></head><body><h1>AUTO Tune not ready</h1></body></html>"
            return render_template_string(ret)

        try:
            if request.method == "GET":
                if path == "/" or not path:
                    logging.info("webook called")
                    ret = '<html><head><title>AUTO Tune</title><meta name="csrf_token" content="{{ csrf_token() }}"></head>'
                    ret += "<body><h1>AUTO Tune</h1><p>"
                    ret += self.showEditForm(request)

                    ret += self.showHistogram()
                    ret += "</body></html>"
                    return render_template_string(ret)
                # other paths here
            elif request.method == "POST":
                ret = '<html><head><title>AUTO Tune</title><meta name="csrf_token" content="{{ csrf_token() }}"></head>'
                if path == "update": # update settings that changed, save to json file
                    ret = '<html><head><title>AUTO Tune Update!</title><meta name="csrf_token" content="{{ csrf_token() }}"></head>'
                    ret += "<body><h1>AUTO Tune Update</h1>"
                    ret += "<h2>Processing changes</h2><ul>"
                    changed = False
                    for (key, val) in request.values.items():
                        if key != "":
                            #ret += "%s -> %s<br>\n" % (key,val)
                            try:
                                if key.startswith('newval,'):
                                    (tag, value, parameter, vtype) = key.split(",", 4)
                                    if value == val:
                                        logging.debug("Skip unchanged value")
                                        continue

                                    if parameter in self._agent._config['personality']:
                                        logging.debug("Personality update")
                                        chg = self.update_parameter(self._agent._config['personality'], parameter, vtype, val, ret)
                                    elif parameter in self.options:
                                        logging.debug("plugin settings update")
                                        chg = self.update_parameter(self.options, parameter, vtype, val, ret)
                                    else:
                                        ret += "<li><b>Skipping unknown %s</b> -> %s\n" % (key,val)
                                    if chg:
                                        ret += "<li>%s: %s -> %s\n" % (parameter, value, val)
                                    changed = changed or chg
                                else:
                                    pass # ret += "No update %s -> %s<br>\n" % (key, val)
                            except Exception as e:
                                ret += "</code><h2>Error</h2><pre>%s</pre><p><code>" % repr(e)
                                logging.exception(e)
                    ret += "</ul>"
                    if changed:
                        save_config(self._agent._config, "/etc/pwnagotchi/config.toml")
                    ret += self.showEditForm(request)
                    ret += self.showHistogram()
                    ret += "</body></html>"
                else:
                    ret += "<body><h1>Unknown request</h1>"
                    ret += '<img src="/ui?%s">' % int(time.time())
                    ret += "<h2>Path</h2><code>%s</code><p>" % repr(path)
                    ret += "<h2>Request</h2><code>%s</code><p>" % repr(request.values)
                    ret += "</body></html>"
                return render_template_string(ret)
        except Exception as e:
            ret = "<html><head><title>AUTO Tune error</title></head>"
            ret += "<body><h1>%s</h1></body></html>" % repr(e)
            logging.exception("AUTO Tune error: %s" % repr(e))
            return render_template_string(ret)

    # called when the plugin is loaded
    def on_loaded(self):
        pass

    def on_ready(self, agent):
        self._agent = agent

        if agent._config['ai']['enabled']:
            logging.info("Auto_Tune is inactive when AI is enabled.")
        else:
            logging.info("Auto_Tune is active! options = %s" % repr(self.options))

    # called before the plugin is unloaded
    #def on_unload(self, ui):
    #    pass

    # called when the agent refreshed its access points list
    def on_wifi_update(self, agent, access_points):
        # check aps and update active channels
        try:
            if agent._config['ai']['enabled']:
                return

            active_channels = []
            self._histogram["loops"] = self._histogram["loops"] + 1
            for ap in access_points:
                ch = ap['channel']
                logging.debug("%s %d" % (ap['hostname'], ch))
                if ch not in active_channels:
                    active_channels.append(ch)
                    if ch in self._unscanned_channels:
                        self._unscanned_channels.remove(ch)
                self._histogram[ch] = 1 if ch not in self._histogram else self._histogram[ch]+1

            self._active_channels = active_channels
            logging.info("Histo: %s" % repr(self._histogram))
        except Exception as e:
            logging.exception(e)

    # called when the agent refreshed an unfiltered access point list
    # this list contains all access points that were detected BEFORE filtering
    #def on_unfiltered_ap_list(self, agent, access_points):
    #    pass

    # called when an epoch is over (where an epoch is a single loop of the main algorithm)
    def on_epoch(self, agent, epoch, epoch_data):
        # pick set of channels for next time
        if agent._config['ai']['enabled']:
            return

        try:
            next_channels = self._active_channels.copy()
            n = 3 if "extra_channels" not in self.options else self.options["extra_channels"]
            if len(self._unscanned_channels) == 0:
                if "restrict_channels" in self.options:
                    logging.info("Repopulating from restricted list")
                    self._unscanned_channels = self.options["restrict_channels"].copy()
                elif hasattr(agent, "_allowed_channels"):
                    logging.info("Repopulating from allowed list: %s" % agent._allowed_channels)
                    self._unscanned_channels = agent._allowed_channels.copy()
                elif hasattr(agent, "_supported_channels"):
                    logging.info("Repopulating from supported list")
                    self._unscanned_channels = agent._supported_channels.copy()
                else:
                    logging.info("Repopulating unscanned list")
                    self._unscanned_channels = pwnagotchi.utils.iface_channels(agent._config['main']['iface'])

            for i in range(n):
                if len(self._unscanned_channels):
                    ch = random.choice(list(self._unscanned_channels))
                    self._unscanned_channels.remove(ch)
                    next_channels.append(ch)
            # update live config
            agent._config['personality']['channels'] = next_channels
            logging.info("Active: %s, Next scan: %s, yet unscanned: %d %s" % (self._active_channels, next_channels, len(self._unscanned_channels), self._unscanned_channels))
        except Exception as e:
            logging.exception(e)
            

import logging

import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
import time
from datetime import datetime
import traceback
from meshtastic.mesh_pb2 import _HARDWAREMODEL
from meshtastic.node import Node
from pubsub import pub
import argparse
import collections
import sys
import os
import math
from geopy import distance

import _thread
import threading
from pwnagotchi.ui.components import Text,LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts

import glob
import json

from pwnagotchi import restart
import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.utils as utils
class MeshPWNstic(plugins.Plugin):
    __author__ = 'Sniffleupagus'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Meshtastic interface for updates and control'

    def __init__(self):
        self.keepGoing = True       # let any background threads know to quit now
        self.TotalPackets = 0
        self.TotalNodes = 0
        self._ui_elements = []       # keep track of UI elements created in on_ui_setup for easy removal in on_unload
        self.status = ""
        self.connected = False
        
        self.myNode = None
        self.nodes = {}
        self.positions = {}
        self.channels = {}

        self.avgPing = None
        
        self.rangeTests = {}
        
        self.num_aps = 0
        self.num_aps_unfiltered = 0
        self.num_deauths = 0
        self.num_assocs = 0
        self.num_handshakes = 0

        self.interface = None
        self._ui = None
        self._agent = None
        self._display = None

        self.myLastPosition = None
        
        self.console = [ "--- %s ---" % datetime.now().strftime('%c') ]
        
        logging.debug("Meshy mesh mesh")

    # Meshtastic event handlers

    # when connected or reconnected
    def onConnectionEstablished(self, interface, topic=pub.AUTO_TOPIC):
        try:
            logging.info("Connected: %s, %s, %s" % (repr(self), repr(interface), repr(topic)))
            logging.info("MeshPWNstic Connected")
            self.connected = True
            self.status = "Connected to meshtastic"
            self.addConsole(self.status)
        except Exception as e:
            logging.exception("Connected: %s" % repr(e))

    # when connection is lost
    def onConnectionLost(self, interface, topic=pub.AUTO_TOPIC):
        try:
            logging.info("Conn Lost: %s, %s, %s" % (repr(self), repr(interface), repr(topic)))
            logging.info("MeshPWNstic Connection Lost")
            self.connected = False
            self.status = "Meshtastic connection lost"
            self.addConsole(self.status)
            time.sleep(3)
            if interface != None:
                interface.connect()
        except Exception as e:
            logging.exception("Conn Lost: %s" % repr(e))

    # on node info update
    def onNodeUpdated(self, node, interface):
        try:
            if self.interface == None:
                self.interface = interface
            logging.debug("Node update %s === %s" % (repr(node), repr(interface)))
            if 'num' in node and 'user' in node:
                if not node['num'] in self.nodes:
                    self.TotalNodes = self.TotalNodes + 1
                self.nodes[node['num']] = node['user']
                user = node['user']
                logging.info("Node update %s (%s) #%s: %s" % (user['longName'], user['shortName'], node['num'], user['hwModel']))
        except Exception as e:
            logging.exception("Node update: %s" % repr(e))


    def addConsole(self, msg):
        try:
            logging.debug("console: %s" % msg)
            now = datetime.now().strftime('%X')
            self.console.insert(0, '%s %s' % (now, msg))

            if len(self.console) > self.options['showLines']:
                m = self.console.pop()
                logging.debug("Removed %s" % m)
                
        except Exception as e:
            logging.exception(repr(e))

    # receive messages (text, data, position, telemetry)
    def onReceive(self, packet, interface):
        try:
            self.TotalPackets = self.TotalPackets + 1
            p_from = packet['from']
            p_to = packet['to']
            p_channel = packet['channel'] if 'channel' in packet else 0
                
            if p_from in self.nodes:
                sender = self.nodes[p_from]
                if not 'num' in sender:
                    sender['num'] = p_from
                sname = sender['longName'] if isinstance(sender, dict) and 'longName' in sender else sender
            elif p_from in self.channels:
                sender = self.channels[p_to]
                sname = sender['name']
            else:
                sender = p_from
                sname = "[unk]"

            if p_to in self.nodes:
                recip = self.nodes[p_to]
                if not 'num' in recip:
                    recip['num'] = p_from
                rname = recip['longName'] if isinstance(recip, dict) and 'longName' in recip else recip
            elif p_to in self.channels:
                recip = self.channels[p_to]
                rname = recip['name']
            else:
                recip = p_to
                rname = "[unk]"
                
            
            if 'decoded' in packet:
                p_data = packet['decoded']
                            
                portnum = p_data['portnum']
                if portnum == 'ADMIN_APP':
                    if 'admin' in p_data:
                        admin = p_data['admin']
                        if 'getChannelResponse' in admin:
                            chanResp = admin['getChannelResponse']
                            logging.debug("Channel resp: %s" % repr(chanResp))
                            ch_index = chanResp['index'] if 'index' in chanResp else 0
                            settings = chanResp['settings']
                            chanResp['id'] = p_from
                            self.channels[p_from] = chanResp

                            if len(settings):
                                logging.info('Channel %d id %s "%s" role %s', ch_index, p_from, settings['name'], repr(chanResp['role']))
                    else:
                        logging.info("ADMIN: %s, %s" % (repr(self), repr(packet)))

                elif portnum == 'TEXT_MESSAGE_APP':
                    logging.info("Received packet #%s: %s" % (self.TotalPackets, repr(packet)))
                    msg = p_data['text']
                    logging.info("%s -> %s: %s" % (repr(sender), repr(recip), msg))
                    self.pwnyCommand(sender, recip, msg)
                elif portnum == 'TELEMETRY_APP':
                    telemetry = p_data['telemetry']
                    t_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(telemetry['time']))
                    delta = time.time() - telemetry['time']

                    if self.avgPing == None:
                        self.avgPing = delta
                    else:
                        self.avgPing = (99.0 * self.avgPing + delta) / 100.0
                    
                    if 'deviceMetrics' in telemetry:
                        logging.info("TELE from %s, ping %0.2f (%0.2f avg) Device Metrics: %s" % (sname, float(delta), self.avgPing, repr(telemetry['deviceMetrics'])))
                        metrics = telemetry['deviceMetrics']
                        if 'batteryLevel' in metrics and metrics['batteryLevel'] < 20:
                            self.addConsole('%s battery low (%s)' % (sname, metrics['batteryLevel']))
                    elif 'powerMetrics' in telemetry:                        
                        logging.info("TELE from %s, ping %0.2f (%0.2f avg) Power: %s" % (sname, float(delta), self.avgPing, repr(telemetry['powerMetrics'])))
                    elif 'environmentMetrics' in telemetry:                        
                        logging.info("TELE from %s, ping %0.2f (%0.2f avg) Environment: %s" % (sname, float(delta), self.avgPing, repr(telemetry['environmentMetrics'])))
                    else:
                        logging.info("TELE from %s: %s" % (sname, repr(telemetry)))
                elif portnum == 'POSITION_APP':
                    position = p_data['position']
                    if 'latitude' in position:
                        p_lat = position['latitude']
                    elif 'latitudeI' in position:
                        p_lat = position['latitudeI']/10000000.0
                        position['latitude'] = p_lat
                    #elif self.myLastPosition and 'latitude' in self.myLastPosition:
                    #    p_lat = self.myLastPosition['latitude']
                    else:
                        return
                        
                    if 'longitude' in position:
                        p_lon = position['longitude']
                    elif 'longitudeI' in position:
                        p_lon = position['longitudeI']/10000000.0
                        position['longitude'] = p_lon
                    #elif self.myLastPosition and 'longitude' in self.myLastPosition:
                    #    p_lon = self.myLastPosition['longitude']
                    else:
                        return
                        
                    p_alt = position['altitude'] if 'altitude' in position else '--'
                    self.positions[p_from] = position
                    mypos = None
                    p_dist = 0
                    if self.myNode != None and self.myNode['num'] in self.positions and self.myNode['num'] == p_from:
                        logging.info("Updating MY position: %s" % repr(position))
                        if 'latitude' in position and 'longitude' in position:
                            self.myLastPosition = position
                            self.myNode['position'] = position
                            self._ui.set('meshpwnstic_lat', "%-4.4f" % position['latitude'])
                            self._ui.set('meshpwnstic_lon', "%-4.4f" % position['longitude'])
                            if 'altitude' in position:
                                self._ui.set('meshpwnstic_alt', "%s" % position['altitude'])

                        sname = '>me<'
                    elif self.myNode != None and 'num' in self.myNode and self.myNode['num'] in self.positions:
                        mypos = self.positions[self.myNode['num']]
                        p_dist = ', %0.2f mi' % distance.distance((mypos['latitude'], mypos['longitude']), (position['latitude'], position['longitude'])).miles
                    elif self.myLastPosition != None:
                        mypos = self.myLastPosition
                        if 'latitude' in mypos:
                            p_dist = ', %0.2f mi' % distance.distance((mypos['latitude'], mypos['longitude']), (position['latitude'], position['longitude'])).miles
                        elif 'latitudeI' in mypos:
                            mypos['latitude'] = mypos['latitudeI']/10000000.0
                            mypos['longitude'] = mypos['longitudeI']/10000000.0
                            p_dist = ', %0.2f mi' % distance.distance((mypos['latitude'], mypos['longitude']), (position['latitude'], position['longitude'])).miles
                        else:
                            mypos = "wtf"
                            p_dist = ''
                    else:
                        p_dist = ''
                    try: 
                        logging.info("POSITION of %s: %-4.4f, %-4.4f @ %s%s" % (sname, p_lat, p_lon, p_alt, p_dist))
                        self.status = "%s @ %-4.4f, %-4.4f - %s%s" % (sname, p_lat, p_lon, p_alt, p_dist)
                    except ValueError:
                        logging.info("POSITION of %s: %-4.4f, %-4,4f @ %s%s" % (sname, p_lat, p_lon, p_alt, p_dist))
                        self.status = "%s @ %s, %s - %s%s" % (sname, p_lat, p_lon, p_alt, p_dist)

                    self.addConsole(self.status)
                elif portnum == 'NODEINFO_APP':
                    if 'user' in packet:
                        num = packet['from']
                        user = packet['user']
                        if not num in self.nodes:
                            self.TotalNodes = self.TotalNodes +1
                            logging.info("New node!!! %d total" % self.TotalNodes)
                            interface.sendText("New node (%s) %s [%s] %s, %s" % (num, user['longName'], user['shortName'], user['id'], user['hwModel']))
                        self.nodes['num'] = user
                        logging.info("Rcv node update %s (%s) #%s: %s" % (user['longName'], user['shortName'], node['num'], user['hwModel']))
                        self.status = "%s [%s] #%s %s" % (user['longName'], user['shortName'], node['num'], user['hwModel'])
                        self.addConsole(self.status)
                elif portnum == 'RANGE_TEST_APP':
                    payload = "%s" % p_data['payload']
                    if payload.startswith('seq'):
                        seq = int(payload[4:])
                        if not p_from in self.rangeTests:
                            self.rangeTests[p_from] = { 'count' : 1, 'last' : seq }
                        elif seq < self.rangeTests[p_from]['last']:
                            self.rangeTests[p_from] = { 'count' : 1, 'last' : seq }
                        else:
                            self.rangeTests[p_from]['count'] += 1
                            self.rangeTests[p_from]['last'] = seq

                        logging.info("Range Test %s: %s" % (sname, repr(self.rangeTests[p_from])))
                    else:
                        logging.info("Range Test %s: %s" % (sname, repr(p_data)))
                else:
                    logging.info("Unknown: %s, %s, %s" % (repr(self), repr(packet), repr(interface)))
            elif 'encrypted' in packet:
                logging.info("Received from %s, encrypted message." % sender)
        except Exception as e:
            logging.exception("On Receive: %s" % repr(e))
            interface.sendText(repr(e))

    def pwnyCommand(self, sender, recip, msg):
        if msg.startswith('/'): # command
            parts = msg[1:].split(' ', 1)
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ''
            logging.info("Command: %s, args: %s" % (cmd, args))
            cmd = cmd.lower()

            sid = sender['id'] if isinstance(sender, dict) and 'id' in sender else sender

            if cmd == 'set':
                (key, val) = args.split('=', 1)
                key = key.strip()
                val = val.strip()
                logging.info("set %s to %s" % (key, val))                
            elif cmd == 'echo':
                self.interface.sendText(args, destinationId=sid)
            elif cmd == 'plugin':
                if args == '':
                    # help
                    self.interface.sendText("/plugin list|(enable|disable [plugin_name])", destinationId=sid)
                elif args.startswith('li'):
                    plugs = ",".join(plugins.loaded.keys())
                    logging.info("Loaded plugins: %s" % plugs)
                elif args.startswith('enable') or args.startswith('disable'):
                    (cmd, plug) = args.split(' ', 1)
                    logging.info("%sing %s" % (cmd[:-1], plug))
                    if plugins.toggle_plugin(plug, cmd == 'enable'):
                        self.interface.sendText("%s %sd" % (plug, cmd))
                    else:
                        self.interface.sendText("%s not %sd" % (plug, cmd))
                    logging.info("%s %sd" % (plug, cmd))
                elif args.startswith('toggle'):
                    (cmd, plug) = args.split(' ', 1)
                    logging.info("%sing %s" % (cmd[:-1], plug))
                    if plugins.toggle_plugin(plug, enable=False):
                        logging.info("%s disabled" % (plug))
                        time.sleep(1)
                        if plugins.toggle_plugin(plug, enable=True):
                            logging.info("%s re-enabled" % (plug))
                            self.interface.sendText("%s re-enabled" % (plug))
                        else:
                            logging.info("%s not re-enabled" % (plug))
                            self.interface.sendText("%s re-enabled" % (plug))
                    else:
                        logging.info("%s not %sd" % (plug, cmd))
                        self.interface.sendText("%s not %sd" % (plug, cmd))
                    logging.info("%s %sd" % (plug, cmd))
                    
                elif args.startswith('refresh'):
                    # refresh from custom directory to see if new plugins
                    new_plugs = ''
                    if 'custom_plugins' in self._agent._config['main']:
                        path = self._agent._config['main']['custom_plugins']
                        logging.info("loading plugins from %s" % (path))
                        for filename in glob.glob(os.path.join(path, "*.py")):
                            plugin_name = os.path.basename(filename.replace(".py", ""))
                            if not plugin_name in plugins.database:
                                logging.info("New plugin: %s" % (plugin_name))
                                plugins.database[plugin_name] = filename
                                new_plugs += ",%s" % plugin_name
                        if new_plugs != '':
                            self.interface.sendText("found new:%s" % (new_plugs), destinationId=sid)
                        else:
                            self.interface.sendText("ok", destinationId=sid)
                    else:
                        self.interface.sendText("no custom path", destinationId=sid)

            elif cmd == 'deauth' or cmd.startswith('assoc'):
                if cmd.startswith('assoc'):   # sanitize input
                    cmd = 'associate'

                if cmd == 'deauth':
                    count = self.num_deauths
                elif cmd == 'associate':
                    count = self.num_assocs

                lval = args.lower()
                if lval == '':
                    if self._agent != None:
                        state = (" enabled" if self._agent._config['personality'][cmd] else " disabled") if self._agent != None else ""
                        self.interface.sendText("%s %s. %d" % (cmd, state, count), destinationId=sid)                   
                elif lval == 'on':
                    if self._agent != None and 'personality' in self._agent._config:
                        self._agent._config['personality'][cmd] = True
                        self.interface.sendText("%s enabled. %d" % (cmd, count), destinationId=sid)
                    else:
                        self.interface.sendText("No personality", destinationId=sid)
                        return
                elif lval == 'off':
                    if self._agent != None and 'personality' in self._agent._config:
                        self._agent._config['personality'][cmd] = False
                        self.interface.sendText("%s disabled. %d" % (cmd, self._agent._epoch.num_deauths), destinationId=sid)
                    else:
                        self.interface.sendText("No personality", destinationId=sid)
                        return
            elif cmd == 'bcap':
                try:
                    logging.info("bcap command: %s" % args)
                    if self._agent != None:
                        result = self._agent.run(args)
                        self.interface.sendText("%s: %s" % (args, repr(result)), destinationId=sid)
                    else:
                        self.interface.sendText("No agent", destinationId=sid)
                except Exception as e:
                    logging(e)
            elif cmd == 'status':
                try:
                    HZ = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
                    status = ""
                    uptimes = open('/proc/uptime').read().split()
                    status += " up %s" % (utils.secs_to_hhmmss(float(uptimes[0])))
                    process_stats = open('/proc/self/stat').read().split()
                    status += ", p %s" % utils.secs_to_hhmmss(float(uptimes[0]) - (int(process_stats[21])/HZ))

                    status += ". %s(%s) APs." % (self.num_aps, self.num_aps_unfiltered)
                    status += ". %s/%s nodepos." % (len(self.positions), len(self.nodes))
                    self.interface.sendText(status, destinationId=sender['num'])
                    logging.info("send back to %s: %s" % (sender['num'], status))
                except Exception as e:
                    logging(e)
            elif cmd == 'restart':
                self.interface.sendText("Restarting.", destinationId=sid)
                if args.lower().startswith('manu'):
                    restart('MANU')
                else:
                    restart('AUTO')
            else:
                self.interface.sendText('I do not know how to "%s" with "%s". Maybe you can show me sometime.', cmd, args, destinationId=sid)
        else:
            sname = sender['longName'] if isinstance(sender, dict) and 'longName' in sender else sender
            self.status = "%s: %s" % (sname, msg)
            self.addConsole(self.status)
                    

    # pwnagotchi plugin handlers
        
    # called when http://<host>:<port>/plugins/<plugin>/ is called
    # must return a html page
    # IMPORTANT: If you use "POST"s, add a csrf-token (via csrf_token() and render_template_string)
    def on_webhook(self, path, request):
        # not sure what to show
        pass

    # called when the plugin is loaded
    def on_loaded(self):
        logging.info("MeshPWNstic options = %s" % self.options)
        try:
            if not 'host' in self.options and not 'serial' in self.options:
                logging.info("Defaulting to localhost")
                self.options['host'] = "127.0.0.1"

            if not 'showLines' in self.options:
                self.options['showLines'] = 3
        
        except Exception as e:
            logging.exception("Meshtastic onload: %s" % repr(e))

    # called before the plugin is unloaded
    def on_unload(self, ui):
        try:
            self.keepGoing = False

            # remove UI elements
            i = 0
            for n in self._ui_elements:
                ui.remove_element(n)
                logging.info("Removed %s" % repr(n))
                i += 1
            if i: logging.info("plugin unloaded %d elements" % i)

            if self.interface != None:
                self.interface.close()
                logging.info("meshtastic closed")

            pub.unsubAll()

            time.sleep(3)
            logging.info("meshpwnstic unloading")
        except Exception as e:
            logging.exception(repr(e))

    # called when there's internet connectivity
    def on_internet_available(self, agent):
        pass

    # called to setup the ui elements
    def on_ui_setup(self, ui):
      try:
        self._ui = ui
        self._display = ui._implementation
        # add custom UI elements
        pos = self.options['position'] if 'position' in self.options else (0,100)
        color = self.options['color'] if 'color' in self.options else 'Blue'
                
        ui.add_element('meshpwnstic_console', Text(color=color, value='--', position=pos, font=fonts.Medium))
        self._ui_elements.append('meshpwnstic_console')

        pos = (0,80)
        ui.add_element('meshpwnstic_lat', LabeledValue(color=color, label="LAT",value=' --.----', position=pos,
                                                       label_font=fonts.Medium, text_font=fonts.Medium))
        self._ui_elements.append('meshpwnstic_lat')

        pos = (80,80)
        ui.add_element('meshpwnstic_lon', LabeledValue(color=color, label="LON",value=' --.----', position=pos,
                                                       label_font=fonts.Medium, text_font=fonts.Medium))
        self._ui_elements.append('meshpwnstic_lon')
        
        pos = (0,90)
        ui.add_element('meshpwnstic_alt', LabeledValue(color=color, label="ALT",value='--', position=pos,
                                                       label_font=fonts.Medium, text_font=fonts.Medium))
        self._ui_elements.append('meshpwnstic_alt')
        
        logging.info("Added element")
      except Exception as err:
          logging.warn("ui_setup:err: %s" % ( repr(err)))
    
    # called when the ui is updated
    def on_ui_update(self, ui):
        # update those elements
        if self.status != "":
            #ui.set('status', self.status)
            self.status = ""
            
        if self.options['showLines'] > 0:
            ui.set('meshpwnstic_console', "\n".join(self.console))
    
    # called when the hardware display setup is done, display is an hardware specific object
    def on_display_setup(self, display):
        self._display = display
            
        pass

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._agent = agent

        try:
            pub.unsubAll()

            logging.info("Subscribing to connection info...")
            pub.subscribe(self.onConnectionEstablished, "meshtastic.connection.established")
            pub.subscribe(self.onConnectionLost, "meshtastic.connection.lost")
    
            logging.info("Subscribing to node updates...")
            pub.subscribe(self.onNodeUpdated, "meshtastic.node.updated")

            logging.info("Subscribing to messages...")
            pub.subscribe(self.onReceive, "meshtastic.receive")

            options = self.options
        
            if 'host' in options:
                logging.info("Connecting to device on host %s" % (options['host']))
                self.interface = meshtastic.tcp_interface.TCPInterface(options['host'])
            elif 'serial' in options:
                logging.info("Connecting to device at serial port %s" % (options['serial']))
                self.interface = meshtastic.serial_interface.SerialInterface(options['serial'])
            else:
                logging.info("Finding Meshtastic device",2)
                self.interface = meshtastic.serial_interface.SerialInterface()

            logging.info("Connected to meshtastic: %s" % repr(self.interface))

            self.myNode = self.interface.getMyNodeInfo()
            logging.info("My node: %s" % repr(self.myNode))

            if self.interface != None:
                if self.myNode != None and 'user' in self.myNode:
                    mynum = self.myNode['num']
                    user = self.myNode['user']
                    myid = user['id']
                    if 'position' in self.myNode:
                        # convert lat/long I to decimal
                        if not 'latitude' in self.myNode['position'] and 'latitudeI' in self.myNode['position']:
                            self.myNode['position']['latitude'] = self.myNode['position']['latitudeI']/10000000.0

                        if not 'longitude' in self.myNode['position'] and 'longitudeI' in self.myNode['position']:
                            self.myNode['position']['longitude'] = self.myNode['position']['longitudeI']/10000000.0
                            
                        if 'latitude' in self.myNode['position']:
                            if not mynum in self.positions:
                                self.positions[mynum] = self.myNode['position']
                            try:
                                self._ui.set('meshpwnstic_lat', "%-4.4f" % self.myNode['position']['latitude'])
                                self._ui.set('meshpwnstic_lon', "%-4.4f" % self.myNode['position']['longitude'])
                                if 'altitude' in self.myNode['position']:
                                    self._ui.set('meshpwnstic_alt',"%s" % self.myNode['position']['altitude'])
                            except Exception as e:
                                logging.exception(e)
                            self.myLastPosition = self.myNode['position']
                    self.interface.sendText("%s (%s) online: %s" % (user['longName'], mynum, myid))
                    logging.info("******** %s (%s) is ready ***********" % (user['longName'], mynum))
        except Exception as e:
            logging.exception(repr(e))
        
        # you can run custom bettercap commands if you want
        #   agent.run('ble.recon on')
        # or set a custom state
        #   agent.set_bored()

    # called when a non overlapping wifi channel is found to be free
    def on_free_channel(self, agent, channel):
        pass

    # called when the agent is rebooting the board
    def on_rebooting(self, agent):
        self.interface.sendText("Rebooting")
        pass

    # called when the agent refreshed its access points list
    def on_wifi_update(self, agent, access_points):
        try:
            self.num_aps = len(access_points)
        except Exception as err:
            logging.warn(repr(err))
        pass

    # called when the agent refreshed an unfiltered access point list
    # this list contains all access points that were detected BEFORE filtering
    def on_unfiltered_ap_list(self, agent, access_points):
        self.num_aps_unfiltered = len(access_points)


    # # called when the agent is sending an association frame
    # #    disabled because it happens too frequently
    def on_association(self, agent, access_point):
        self.num_assocs += 1
    
    # called when the agent is deauthenticating a client station from an AP
    def on_deauthentication(self, agent, access_point, client_station):
        self.num_deauths += 1

    # called when a new handshake is captured, access_point and client_station are json objects
    # if the agent could match the BSSIDs to the current list, otherwise they are just the strings of the BSSIDs
    def on_handshake(self, agent, filename, access_point, client_station):
        try:
            self.num_handshakes += 1

            if self.myLastPosition != None:
                gps_filename = filename.replace(".pcap", ".gps.json")
                with open(gps_filename, "w+t") as fp:
                          json.dump(self.myLastPosition, fp)

            if self.interface:
                hostname = access_point['hostname'] if 'hostname' in access_point else access_point['mac']
                clientname = client_station['hostname'] if 'hostname' in client_station else client_station['mac']
                msg = "PWND Handshake %s from %s" % (clientname, hostname)
                logging.debug(msg)
                self.interface.sendText(msg)
                self.addConsole(msg)
        except Exception as err:
            logging.warn(repr(err))
        pass

    # # called when an epoch is over (where an epoch is a single loop of the main algorithm)
    def on_epoch(self, agent, epoch, epoch_data):
        # if not connected, try reconnecting
        if self.connected == False:
            options = self.options
        
            if 'host' in options:
                logging.info("Connecting to device on host %s" % (options['host']))
                self.interface = meshtastic.tcp_interface.TCPInterface(options['host'])
            elif 'serial' in options:
                logging.info("Connecting to device at serial port %s" % (options['serial']))
                self.interface = meshtastic.serial_interface.SerialInterface(options['serial'])
            else:
                logging.info("Finding Meshtastic device",2)
                self.interface = meshtastic.serial_interface.SerialInterface()

            logging.info("Connected to meshtastic: %s" % repr(self.interface))

            self.myNode = self.interface.getMyNodeInfo()

        pass

    # # called when a new peer is detected
    # def on_peer_detected(self, agent, peer):
    #     try:
    #         pass
    #     except Exception as err:
    #         logging.warn(repr(err))
    #     pass

    # # called when a known peer is lost
    # def on_peer_lost(self, agent, peer):
    #     pass

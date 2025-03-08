import logging
import threading
import socket
import select
import os
import time
import glob

try:
    import prctl
except:
    pass

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import Text

socket_path = '/tmp/pwny_cmd_socket'

class Command_Server(plugins.Plugin):
    __author__ = 'Sniffleupagus (on github)'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A command control plugin for pwnagotchi.'

    def command_loop(self):
        logging.info("Worker started")

        try:
            prctl.set_name("cmd_server sock")
        except:
            pass

        t = threading.currentThread()

        try:
            os.unlink(socket_path)
        except OSError:
            if os.path.exists(socket_path):
                logging.exception(e)
                raise
        try:
            server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server_socket.bind(socket_path)
            server_socket.listen(5)
            logging.info("Listening on %s" % socket_path)
            read_list = [ server_socket ]
        except Exception as e:
            logging.exception(e)
            raise
        # listening loop
        while self._keep_going:
            try:
                readable, writable, errored = select.select(read_list, [], [], 0.5)
                for s in readable:
                    if s is server_socket:
                        client_socket, address = server_socket.accept()
                        read_list.append(client_socket)
                        client_socket.send(b'> ')
                    else:
                        data = s.recv(1024)
                        data = data.decode('utf-8').strip()
                        if data:
                            logging.debug("Data: %s" % repr(data))
                            # process command
                            parts = data.split(' ', 1)
                            cmd = parts[0].lower()
                            args = parts[1] if len(parts) > 1 else ''
                            logging.info("Command: %s, args: %s" % (cmd, args))

                            if cmd == "xyzzy":
                                s.send("Nothing happened.\n\r".encode())
                            elif cmd == 'refresh':  # load new custom plugins
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
                                        logging.info("Found new plugins: %s" % (new_plugs))
                                        s.send(("Found new plugins %s\n\r" % (new_plugs)).encode())
                                    else:
                                        logging.info("No new plugins found.")
                                        s.send(b'No new plugins found.\r\n')
                                else:
                                    logging.warn("no custom plugin path defined")
                            elif cmd == 'enable' or cmd == 'disable':
                                # enable plugin_name
                                # disable plugin_name
                                logging.info('%sinf %s plugin' % (cmd, args))
                                try:
                                    if plugins.toggle_plugin(args, cmd == 'enable'):
                                        s.send(("%s %sd\n\r" % (args, cmd)).encode())
                                    else:
                                        s.send(("%s not %sd\n\r" % (args, cmd)).encode())
                                except Exception as e:
                                    logging.exception(e)
                                    s.send(("Failed: %s\n\r" % repr(e)).encode())
                            elif cmd == 'backup':
                                logging.info("Backup command. Does nothing for now.")
                                s.send(("Backup not really done.\n\r").encode())

                            elif cmd == 'countdown':
                                try:
                                    self._ui.set("status", "Countdown!")
                                    self._ui.update()
                                    time.sleep(1)
                                    self._ui.set("status", "3")
                                    self._ui.update()
                                    time.sleep(1)
                                    self._ui.set("status", "2")
                                    self._ui.update()
                                    time.sleep(1)
                                    self._ui.set("status", "1")
                                    self._ui.update()
                                    time.sleep(1)
                                    self._ui.set("status", "Woohoo!")
                                    self._ui.update()
                                    logging.info("Countdown complete")
                                except Exception as e:
                                    logging.exception(e)
                            else:
                                logging.warning("Unknown command: %s, %s" % (cmd, args))
                                s.send(('Unknown command: %s\n\r' % cmd).encode())
                            client_socket.send(b'> ')

                        else:
                            # no data received from this client, so close connection
                            logging.info("Closing %s" % repr(s))
                            s.close()
                            read_list.remove(s)
            except Exception as e:
                logging.exception(e)

        logging.info("Thread: while loop exited")
        # exited while(keep_going)
        for s in read_list:
            try:
                s.close()
            except Exception as e:
                logging.exception(e)
        try:
            os.unlink(socket_path)
        except OSError:
            if os.path.exists(socket_path):
                raise
        logging.info("Command control socket closed. Thread exiting.")
    
    def __init__(self):
        self._agent = None
        self._ui = None
        self._keep_going = True
        self._worker = None
        self._keep_going = True

    def on_loaded(self):
        pass

    def on_ready(self, agent):
        try:
            self._agent = agent;
            logging.debug("Creating worker thread. options = %s" % self.options)
            self._worker = threading.Thread(target=self.command_loop)
            self._keep_going = True
            logging.debug("Worker = %s" % repr(self._worker))
            #self._worker.daemon = True
            self._worker.start()
        except Exception as e:
            logging.exception(e)

    # called before the plugin is unloaded
    def on_unload(self, ui):
        logging.debug("unloading")

        self._keep_going = False # signal the worker thread to end
        if self._worker:
            logging.debug("Waiting for worker")
            self._worker.join()
            logging.debug("worker finished")


    # called to setup the ui elements
    def on_ui_setup(self, ui):
        self._ui = ui


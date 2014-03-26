
import json
import logging
from pprint import pprint, pformat
import signal
import sys
import threading
import traceback
import time
import uuid
import weakref

import pika

from aurora.cls_logger import get_cls_logger
from aurora.ap_provision import writer as provision
from aurora.stop_thread import *
from aurora.exc import *

PIKA_LOGGER = logging.getLogger('pika')
PIKA_LOGGER.setLevel(logging.INFO)
LOGGER = logging.getLogger(__name__)


class Dispatcher(object):

    lock = None
    TIMEOUT = 30
    dispatch_count = 0
    status_closing = False
    def __init__(self, host, username, password, mysql_username, mysql_password, aurora_db):
        """Establishes the connection to RabbitMQ and sets up the queues"""
        self.LOGGER = get_cls_logger(self)
        self.LOGGER.info("Constructing Dispatcher...")
        # Run Pika logger so that error messages get printed
        
        self.host = host
        self.username = username
        self.password = password
        Dispatcher.lock = False
        self.restarting_connection = False
        self.aurora_db = aurora_db
        self.timeout_callback = None
        self.response_callback = None
        # Create list for requests sent out
        self.requests_sent = []

        #self.apm = ap_monitor.APMonitor(self, host, mysql_username, mysql_password)
        #self._start_connection()

        # Setup complete, now start listening and processing
        # This jumpstarts the connection, which in turn uses the callbacks
        # Note: connect() is called automatically in SelectConnection().__init__()
        #
        # self.connection.connect()

        # Start ioloop, this will quit by itself when Dispatcher().stop() is run

    def __del__(self):
        self.LOGGER.info("Deconstructing...")

    def set_timeout_callback(self, timeout_callback):
        self.timeout_callback = timeout_callback

    def set_response_callback(self, response_callback):
        self.response_callback = response_callback

    def start_connection(self):
        self._start_connection()

    def _start_connection(self):
        self.channel = None
        credentials = pika.PlainCredentials(self.username, self.password)
        self.connection = pika.SelectConnection(pika.ConnectionParameters(
                                                    host=self.host,
                                                    credentials=credentials
                                                ),
                                                self.on_connected)
        # Start ioloop, this will quit by itself when Dispatcher().stop() is run
        
        self.listener = threading.Thread(target=self.connection.ioloop.start)
        self.LOGGER.info("Starting pika listener %s", self.listener)
        self.listener.start()

    def _stop_connection(self):
        self._stop_all_request_sent_timers()
        try:
            con_open = True
            del self.channel 
            self.LOGGER.warn("Connection state: %s",
                             self.connection.connection_state)
            Dispatcher.status_closing = True
            self.connection.close()
            Dispatcher.lock = False
        except AttributeError as e:
            self.LOGGER.debug("Connection already closed...")
            

    def _restart_connection(self):
        self.LOGGER.info("Channel has died, restarting...")
        self._stop_connection()
        self.listener.join()

        # Dispatcher.lock = False
        printed_waiting = False

        while True:
            if not printed_waiting:
                self.LOGGER.info("Waiting for channel to close...")
                printed_waiting = True
            
            try:
                if self.connection.is_closed:
                    self.LOGGER.debug("Connection closed...")
                    break
            except AttributeError as e:
                self.LOGGER.debug("Connection closed (doesn't exist)...")
                break
            time.sleep(1)

        self.restarting_connection = True
        self.LOGGER.info("Starting new connection...")
        self._start_connection()
        printed_waiting = False
        while True:
            if not printed_waiting:
                self.LOGGER.info("Waiting for channel to open...")
                printed_waiting = True
            try:
                if self.connection.is_open and self.channel.is_open:
                    break
            except AttributeError as e:
                pass
            # Channel is not up again yet
            time.sleep(1)
        self.LOGGER.info("Channel back up, dispatching...")

    def _stop_all_request_sent_timers(self):
        while self.requests_sent:
            entry = self.requests_sent.pop()
            self.LOGGER.info("Cancelling timer %s", entry[1])
            entry[1].cancel()

    def on_connected(self, connection):
        self.connection.channel(self.channel_open)

    def channel_open(self, new_channel):
        self.channel = new_channel
        Dispatcher.status_closing = False
        response = self.channel.queue_declare(durable=True, 
                                              callback=self.on_queue_declared)

    def on_queue_declared(self, frame):
        self.callback_queue = frame.method.queue
        provision.update_reply_queue(self.callback_queue)
        self.channel.basic_consume(self.response_callback, queue=self.callback_queue)
        if self.restarting_connection:
            self.restarting_connection = False
        else:
            self._start_pika_channel_open_monitor()
            self._send_manager_up_status()

    def _send_manager_up_status(self):
        for ap in self.aurora_db.get_ap_list():
            self.dispatch({'command':'SYN'}, ap)

    def _start_pika_channel_open_monitor(self):
        self._pika_monitor_thread = StoppableThread(target=self._pika_monitor_loop)
        self.LOGGER.info("Starting pika monitor thread %s", self._pika_monitor_thread)
        self._pika_monitor_thread.start()

    def _stop_pika_channel_open_monitor(self):
        self.LOGGER.info("Stopping pika monitor thread %s", self._pika_monitor_thread)
        self._pika_monitor_thread.stop()
        self._pika_monitor_thread.join()

    def _pika_monitor_loop(self, stop_event=None):
        while not stop_event.is_set():
            try:
                if not (self.connection.is_open and self.channel.is_open):
                    self.LOGGER.warn("Pika connection down, restarting")
                    self._restart_connection()
                    self.LOGGER.warn("Continuing pika_monitor loop")
            except AttributeError:
                self.LOGGER.warn("Connection doesn't exist, restarting")
                self._restart_connection()
                self.LOGGER.warn("Continuing pika_monitor loop")

            time.sleep(0.5)


    def dispatch(self, config, ap, unique_id=None):
        """Send data to the specified queue.
        Note that the caller is expected to set database
        properties such as status."""

        # Create unique_id if none exists
        if unique_id is None:
            unique_id = "%s-%s" % (ap, str(uuid.uuid4()))
        else:
            unique_id = "%s-%s" % (ap, unique_id)

        # Convert JSON to string
        message = json.dumps(config)
        self.LOGGER.debug(message)

        # Send JSON
        # We attach a reply_to and correlation ID to tell the AP to send a message to the queue we create (randomly generated name) at init
        # with the correlation id specified.  This means that
        # we can see if our request executed successfully or not
        # See http://www.rabbitmq.com/tutorials/tutorial-six-python.html for more info
        if Dispatcher.lock:
            self.LOGGER.info("Locked, waiting...")
            while Dispatcher.lock:
                time.sleep(0.1)
                pass

        if Dispatcher.status_closing:
            raise MessageSendAttemptWhileClosing()

        self.LOGGER.debug("Locking...")
        Dispatcher.lock = True

        # Dispatch, catch if no channel exists
        while True:
            try:
                if self.connection.is_open and self.channel.is_open:
                    break
            except AttributeError:
                pass
            time.sleep(0.25)
        die_by_kb = False
        try:
            self.channel.basic_publish(exchange='', routing_key=ap, body=message, properties=pika.BasicProperties(reply_to = self.callback_queue, correlation_id = unique_id, content_type="application/json"))
        except IndexError as e:
            # Likely publishing the message didn't work
            self.LOGGER.warn(e.message)
            try:
                # Force the channel to close, the channel monitor should
                # notice, and restart the channel
                self.LOGGER.info("Forcing a channel close")
                self._stop_connection()
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except KeyboardInterrupt:
            die_by_kb = True
        except Exception as e:
            # A more serious error occured
            traceback.print_exc(file=sys.stdout)
            #self.LOGGER.error(e.message)
        else:
            self.LOGGER.info("Message for %s dispatched", ap)
            ap_slice_id = 'NONE'
            if config['command'] == 'SYN':
                ap_slice_id = 'SYN'
            else:
                ap_slice_id = config['slice']
            # Start a timeout countdown
            self.LOGGER.debug("ap_slice_id %s",ap_slice_id)
            timer = threading.Timer(self.TIMEOUT, self.timeout_callback, args=(ap_slice_id,ap,unique_id))
            self.LOGGER.debug("Adding timer %s", timer)
            self.requests_sent.append((unique_id, timer, ap_slice_id))
            timer.start()
            self.LOGGER.debug("requests_sent %s",self.requests_sent)
            if len(self.requests_sent) > 0:
                self.LOGGER.debug("Starting timer: %s",self.requests_sent[-1])
            else:
                self.LOGGER.error("Cannot start nonexistant timer")

        self.LOGGER.debug("Unlocking...")
        Dispatcher.lock = False
        if die_by_kb:
            raise KeyboardInterrupt()

    def get_open_channel(self):
        if self.channel.is_open:
            return self.channel
        return None

    def stop(self):
        # SelectConnection object close method cancels ioloop and cleanly
        # closes associated channels
        # Stop timers
        #self.apm.stop()
        self._stop_pika_channel_open_monitor()
        self._stop_connection()

        del self.connection
        del self.listener
        del self.timeout_callback
        del self.response_callback

    def _get_uuid_for_ap_syn(self, ap_syn):
        for request in self.requests_sent:
            if request[0].startswith(ap_syn + '-'):
                yield request[0]

    def have_request(self, correlation_id):
        for request in self.requests_sent:
            if request[0] == correlation_id:
                return (True, request)
        return (False, None)

    def remove_request(self, message_uuid=None, ap_syn=None):
        # If ap_syn isn't None, find all requests for this ap and cancel them
        # to create a clean slate.  User will have to manually restart failed slices.
        if ap_syn:
            for message_uuid in self._get_uuid_for_ap_syn(ap_syn):
                (have_request, request) = self.have_request(message_uuid)
                if have_request:
                    self.LOGGER.debug("Cancelling timer %s", request[1])
                    request[1].cancel()
                    self.LOGGER.debug("Removing request %s", str(request))
                    self.requests_sent.remove(request)
        else:
            (have_request, request) = self.have_request(message_uuid)
            if have_request:
                self.LOGGER.debug("Cancelling timer %s", request[1])
                request[1].cancel()
                self.LOGGER.debug("Removing request %s", str(request))
                self.requests_sent.remove(request)


# Menu loop; thanks Kevin
# Obviously this code will not be in a final version
if __name__ == '__main__':
    exitLoop = False

    ######
    # Connection Variables
    host = 'localhost'
    username = 'outside_world'
    password = 'wireless_access'
    mysql_username = 'root'
    mysql_password = 'supersecret'
    sender = Dispatcher(host, username, password, mysql_username, mysql_password)

    import ap_provision.http_srv as provision_srv
    provision_srv.run()

    while not exitLoop:
        print('Choose an option: ')
        print('0. Exit')
        print('1. Dispatch')
        choice = raw_input()
        if choice == '0':
            exitLoop = True
            # Stop listening for replies
            sender.stop()

        elif choice == '1':
            print('Enter json filename')
            try:
                file = open(raw_input())
                config = json.load(file)
                file.close()
            except:
                print('Bad file, returning to menu')
            else:

                print('Enter ap ID')
                ap = raw_input()
                print('Enter unique id')
                unique_id = raw_input()
                sender.dispatch( config, ap, unique_id)

    provision_srv.stop()

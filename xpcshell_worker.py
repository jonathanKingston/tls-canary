# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import logging
import os
from Queue import Queue, Empty
import subprocess
from threading import Thread

logger = logging.getLogger(__name__)
module_dir = os.path.split(__file__)[0]


def read_from_worker(worker, response_queue):
    global logger

    logger.debug('Reader thread started for worker %s' % worker)
    for line in iter(worker.stdout.readline, b''):
        line = line.strip()
        try:
            response_queue.put(Response(line))
            logger.debug("Received worker result: %s" % line)
        except ValueError:
            # FIXME: XPCshell is currently issuing many warnings, constant warning is too verbose
            # logger.warning("Unexpected script output: %s" % line.strip())
            if line.startswith("JavaScript error:"):
                logger.error("JS error from worker %s: %s" % (worker, line))
            elif line.startswith("JavaScript warning:"):
                logger.warning("JS warning from worker %s: %s" % (worker, line))
            else:
                logger.critical("Invalid output from worker %s: %s" % (worker, line))
    logger.debug('Reader thread finished for worker %s' % worker)
    worker.stdout.close()


class XPCShellWorker(object):
    """XPCShell worker implementing an asynchronous, JSON-based message system"""

    def __init__(self, app, script=None):
        global module_dir

        self.__app = app
        if script is None:
            self.__script = os.path.join(module_dir, "js", "scan_worker.js")
        else:
            self.__script = script
        self.__worker_thread = None
        self.__reader_thread = None
        self.__response_queue = Queue()

    def spawn(self):
        """Spawn the worker process and its dedicated reader thread"""
        global logger, module_dir

        cmd = [self.__app.exe, '-xpcshell', "-a", self.__app.browser, self.__script]
        logger.debug("Executing worker shell command `%s`" % ' '.join(cmd))
        self.__worker_thread = subprocess.Popen(
            cmd,
            cwd=self.__app.browser,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1)  # `1` means line-buffered

        # Spawn a reader thread, because stdio reads are blocking
        self.__reader_thread = Thread(target=read_from_worker, name="Reader",
                                      args=(self.__worker_thread, self.__response_queue))
        self.__reader_thread.daemon = True  # Thread dies with worker
        self.__reader_thread.start()

    def terminate(self):
        """Signal the worker process to quit"""
        # The reader tread dies when the Firefox process quits
        self.__worker_thread.terminate()

    def kill(self):
        """Kill the worker process"""
        self.__worker_thread.kill()

    def is_running(self):
        """Check whether the worker is still fully running"""
        if self.__worker_thread is None:
            return False
        return self.__worker_thread.poll() is None

    def send(self, cmd):
        """Send a command message to the worker"""
        global logger

        cmd_string = str(cmd)
        logger.debug("Sending worker message: `%s`" % cmd_string)
        try:
            self.__worker_thread.stdin.write(cmd_string + "\n")
            self.__worker_thread.stdin.flush()
        except IOError:
            logger.error("Can't write to worker. Message `%s` wasn't heard." % cmd_string)

    def receive(self):
        """Read queued messages from worker. Returns [] if there were none."""

        global logger

        # Read everything from the reader queue
        responses = []
        try:
            while True:
                responses.append(self.__response_queue.get_nowait())
        except Empty:
            pass

        return responses


class Command(object):

    def __init__(self, id, mode, **kwargs):
        if mode is None:
            raise Exception("Refusing to init mode-less command")
        self.__id = id
        self.__mode = mode
        self.__args = kwargs

    def __str__(self):
        return json.dumps({"id": self.__id, "mode": self.__mode, "args": self.__args})


class Response(object):

    def __init__(self, message_string):
        global logger

        self.id = None
        self.success = None
        self.result = None
        response = json.loads(message_string)  # May throw ValueError
        if "id" in response:
            self.id = response["id"]
        if "success" in response:
            self.success = response["success"]
        if "response" in response:
            self.result = response["response"]
        if len(response) > 3:
            logger.error("Worker response has unexpected format: %s" % message_string)

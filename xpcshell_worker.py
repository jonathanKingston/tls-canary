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
        try:
            response_queue.put(json.loads(line))
        except ValueError:
            # FIXME: XPCshell is currently issuing many warnings, constant warning is too verbose
            # logger.warning("Unexpected script output: %s" % line.strip())
            logger.debug("JS error in worker %s: %s" % (worker, line.strip()))
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
        global module_dir

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
        """Check whether the worker process is still running"""
        return self.__worker_thread is None or self.__worker_thread.poll() is None

    def send(self, msg):
        """Send a message to the worker"""
        self.__worker_thread.write(json.dumps(msg))

    def receive(self):
        """Read queued messages from worker. Returns [] if there were none."""

        global logger

        # Read everything from the reader queue
        results = []
        try:
            while True:
                results += self.results.get_nowait()
        except Empty:
            pass

        return results

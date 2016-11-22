# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import logging
import os
from Queue import Queue, Empty
import subprocess
from threading import Thread
import time

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
            logger.debug("Unexpected script output: %s" % line.strip())
    logger.debug('Reader thread finished for worker %s' % worker)
    worker.stdout.close()

def worker_manager(app, response_queue):
    global logger
    logger.debug('Manager thread started for app %s' % app)


class FirefoxWorker(object):
    def __init__(self, app, work_list):
        self.__app = app
        self.__work_list_total = len(work_list)
        self.__work_queue = Queue(maxsize=self.__work_list_total)
        for row in work_list:
            self.__work_queue.put(row)
        self.__urls_pending = 0
        self.__wakeup_pending = None
        self.__worker_thread = None
        self.__reader_thread = None
        self.__result_queue = Queue(maxsize=len(work_list))

    def spawn(self):
        """Spawn the worker process and its dedicated reader thread"""
        global module_dir

        self.__urls_pending = 0
        cmd = [self.__app.exe, '-xpcshell', "-a", self.__app.browser,
               os.path.join(module_dir, "js", "scan_worker.js")]
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
                                      args=(self.__worker_thread, self.__result_queue))
        self.__reader_thread.daemon = True  # Thread dies with worker
        self.__reader_thread.start()

    def send(self, msg):
        """Sends a JSON-formatted message to the worker"""
        self.__worker_thread.write(json.dumps(msg))

    def terminate(self):
        """Signals worker process to quit"""
        # The reader tread dies when the Firefox process quits
        self.send({"mode": "quit"})

    def wakeup(self):
        """Call this every few ms to keep the worker handling events (long story)"""
        if not self.__is_wakeup_pending():
            self.send({"mode": "wakeup"})

    def __scan_url(self, rank, url):
        msg = {"mode": "scan", "url": url, "rank": rank}
        self.send(msg)
        self.__urls_pending += 1

    def maintain_queue(self, parallel=100):
        while self.__urls_pending < parallel and not self.__work_queue.empty():
            self.__send_url(self.__work_queue.get)
        results = []

    def is_done(self):
        return self.__work_queue.empty()

    def get_result(self):
        """Read from result queue. Returns None if empty."""
        try:
            return self.results.get_nowait()
        except Empty:
            return None

    def __wait_for_remaining_workers(self, delay):
        kill_time = time.time() + delay
        while time.time() < kill_time:
            for worker in self.workers:
                ret = worker.poll()
                if ret is not None:
                    logger.debug('Worker terminated with return code %d' % ret)
                    self.workers.remove(worker)
            if len(self.workers) == 0:
                break
            time.sleep(0.05)

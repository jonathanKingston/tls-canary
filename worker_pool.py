# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import time
from worq.pool.thread import WorkerPool
from worq import get_broker, get_queue, TaskSpace

import xpcshell_worker as xw

logger = logging.getLogger(__name__)
ts = TaskSpace(__name__)


def init(worq_url):
    global logger, ts
    broker = get_broker(worq_url)
    broker.expose(ts)
    return broker


def start_pool(worq_url, num_workers=1, **kw):
    broker = init(worq_url)
    pool = WorkerPool(broker, workers=num_workers)
    pool.start(**kw)
    return pool


@ts.task
def scan_urls(app, urls, final_timeout=10):
    global logger

    logger.debug("scan_urls task called with %s" % repr(urls))

    xpcw = xw.XPCShellWorker(app)
    xpcw.spawn()

    wakeup_cmd = xw.Command(0, "wakeup")
    for url in urls:
        scan_cmd = xw.Command(url, "scan", url=url)
        xpcw.send(scan_cmd)
        xpcw.send(wakeup_cmd)

    xpcw.send(xw.Command(0, "quit"))

    # Fetch results from queue, wait for potential stragglers
    results = {}
    timeout_time = time.time() + final_timeout
    while time.time() < timeout_time:
        for response in xpcw.receive():
            results[response.id] = True if response.result == "OK" else False
        if len(results) >= len(urls):
            break
        xpcw.send(wakeup_cmd)
        time.sleep(0.1)

    xpcw.terminate()

    return results


def run_scans(app, urls, num_workers=1, worq_url = "memory://"):
    p = start_pool(worq_url, timeout=1, num_workers=num_workers)
    try:
        queue = get_queue(worq_url, target=__name__)

        # Enqueue tasks to be executed in parallel
        scan_results = [queue.scan_urls(app, url) for url in urls]

    finally:
        p.stop()

    return scan_results
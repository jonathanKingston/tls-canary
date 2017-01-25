# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from worq.pool.process import WorkerPool
from worq import get_broker, TaskSpace

from xpcshell_worker import XPCShellWorker

logger = logging.getLogger(__name__)
ts = TaskSpace("TLS Canary Worker Pool")

def init(worq_url):
    global logger, ts
    broker = get_broker(worq_url)
    broker.expose(ts)
    return broker


def start_pool(worq_url, num_workers=1, **kw):
    broker = init(worq_url)
    pool = WorkerPool(broker, init, workers=num_workers)
    pool.start(**kw)
    return pool


@ts.task
def scan_urls(urls):
    xpcshell_worker = XPCShellWorker()
    xpcshell_worker.spawn()

    results = []
    wakeup_cmd = {"mode": "wakeup"}
    for url in urls:
        scan_cmd = {"mode": "scan", "url": url}
        xpcshell_worker.send(scan_cmd)
        xpcshell_worker.send(wakeup_cmd)

    quit_cmd = {"mode": "quit"}
    xpcshell_worker.send(quit_cmd)
    
    for result in xpcshell_worker.receive():
        results.append(result)

    return results

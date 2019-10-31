import os
import random
import signal
import subprocess

import pytest


class ServerFixture(object):
    def __init__(self, proc, port):
        self.proc = proc
        self.port = port


@pytest.fixture(scope='module')
def server_process():
    port = random.randint(100000, 135000)
    proc = subprocess.Popen(['python', 'server.py', '--port', str(port)])
    yield ServerFixture(proc, port)
    os.kill(proc.pid, signal.SIGINT)
    proc.wait()

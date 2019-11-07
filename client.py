import logging
import msgpack
import socket
import struct
import time


log = logging.getLogger()

SSH_PORT = 22


class ClientException(Exception):
    '''
    Raised by ManagerClient when errors are encountered
    '''


class ProcIO(object):

    def __init__(self, conn, proc_id, name):
        self.conn = conn
        self.proc_id = proc_id
        self.name = name

    def read(self, size=None):
        if self.name not in ('stdout', 'stderr'):
            raise Exception("Stream not readable")
        return self.conn.read_stream(self.proc_id, self.name, size)

    def write(self, byts):
        if self.name != 'stdin':
            raise Exception("Stream not writable")
        self.conn.write_stream(self.proc_id, self.name, byts)


class ManagerClient(object):

    def __init__(self, conn_id=None, sock=None):
        self.conn_id = conn_id
        self.sock = sock

    def connect(self, host, port, timeout=30):
        self.sock = socket.socket()
        start = time.time()
        connected = False
        while not connected and time.time() - start < timeout:
            try:
                self.sock.connect((host, port))
            except ConnectionRefusedError:
                time.sleep(.3)
            else:
                connected = True
        if not connected:
            raise ClientException('Unable to connect to manager')

    def close(self):
        req = self.create_msg({'kind': 'close'})
        self.sock.send(req)
        rep = self.recv_msg(self.sock)
        self.sock.close()
        self.sock = None

    @property
    def is_connected(self):
        return self.sock

    def ssh_connect(self, host):
        if not self.sock:
            raise ClientException('No manager connection')
        req = self.create_msg({'kind': 'connect', 'host': host})
        self.sock.send(req)
        rep = self.recv_msg(self.sock)
        # TODO: error checking
        self.conn_id = rep['conn_id']

    def ssh_run(self, cmd):
        if not self.sock:
            raise ClientException('No manager connection')
        if not self.conn_id:
            raise ClientException('No ssh connection')
        req = self.create_msg({'kind': 'run', 'conn_id': self.conn_id, 'command': cmd})
        self.sock.send(req)
        rep = self.recv_msg(self.sock)
        # TODO: error checking
        return cmd, rep['stdout'], rep['stderr']

    def ssh_exec(self, cmd):
        if not self.sock:
            raise ClientException('No manager connection')
        if not self.conn_id:
            raise ClientException('No ssh connection')
        req = self.create_msg({'kind': 'exec', 'conn_id': self.conn_id, 'command': cmd})
        self.sock.send(req)
        rep = self.recv_msg(self.sock)
        stdin = ProcIO(self, rep['proc_id'], 'stdin')
        stdout = ProcIO(self, rep['proc_id'], 'stdout')
        stderr = ProcIO(self, rep['proc_id'], 'stderr')
        return stdin, stdout, stderr

    def write_stream(self, proc_id, name, byts):
        if not self.sock:
            raise ClientException('No manager connection')
        if not self.conn_id:
            raise ClientException('No ssh connection')
        req = self.create_msg(
            {
                'kind': 'write_stream',
                'conn_id': self.conn_id,
                'proc_id': proc_id,
                'name': name,
                'byts': byts,
            }
        )
        self.sock.send(req)
        self.recv_msg(self.sock)

    def read_stream(self, proc_id, name, size=None):
        if not self.sock:
            raise ClientException('No manager connection')
        if not self.conn_id:
            raise ClientException('No ssh connection')
        req = self.create_msg(
            {
                'kind': 'read_stream',
                'conn_id': self.conn_id,
                'proc_id': proc_id,
                'name': name,
                'size': size,
            }
        )
        self.sock.send(req)
        rep = self.recv_msg(self.sock)
        return rep['byts']

    def ssh_disconnect(self):
        if not self.sock:
            raise ClientException('No manager connection')
        if not self.conn_id:
            raise ClientException('No ssh connection')
        req = self.create_msg({'kind': 'disconnect', 'conn_id': self.conn_id})
        self.sock.send(req)
        rep = self.recv_msg(self.sock)
        if 'status' not in rep or rep['status'] != 'closed':
            raise Exception('Could not disconnect')
        self.conn_id = None

    @staticmethod
    def create_msg(msg):
        packed = msgpack.packb(msg, use_bin_type=True)
        return struct.pack('>I', len(packed)) + packed

    @staticmethod
    def recvall(sock, n):
        # Helper function to recv n bytes or return None if EOF is hit
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    @classmethod
    def recv_msg(cls, sock):
        # Read message length and unpack it into an integer
        raw_msglen = cls.recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return msgpack.unpackb(cls.recvall(sock, msglen), raw=False)


class ClientFactory(object):

    def __init__(self, manager_host='127.0.0.1', manager_port='12345', manager=None):
        self.manager_host = manager_host
        self.manager_port = manager_port
        if manager is not None:
            self.manager = manager
        else:
            self.manager = ManagerClient()

    def __call__(self):
        return SSHClient(self.manager_host, self.manager_port, self.manager)


class SSHClient(object):

    def __init__(self, manager_host='127.0.0.1', manager_port='12345', manager=None):
        self.manager_host = manager_host
        self.manager_port = manager_port
        if manager is not None:
            self.manager = manager
        else:
            self.manager = ManagerClient()

    def has_manager_conn(self):
        return self.manager.sock is not None

    def connect_manager(self, timeout=30):
        self.manager.connect(self.manager_host, self.manager_port, timeout=timeout)

    def connect(
        self,
        hostname,
        port=SSH_PORT,
        username=None,
        password=None,
        pkey=None,
        key_filename=None,
        timeout=None,
        allow_agent=True,
        look_for_keys=True,
        compress=False,
        sock=None,
        gss_auth=False,
        gss_kex=False,
        gss_deleg_creds=True,
        gss_host=None,
        banner_timeout=None,
        auth_timeout=None,
        gss_trust_dns=True,
        passphrase=None,
        disabled_algorithms=None,
    ):
        if not self.has_manager_conn():
            self.connect_manager()
        print("Connecting to %s" % (hostname,))
        self.manager.ssh_connect(hostname)

    def close(self):
        self.manager.ssh_disconnect()

    def exec_command(
        self,
        command,
        bufsize=-1,
        timeout=None,
        get_pty=False,
        environment=None,
    ):
        return self.manager.ssh_exec(command)

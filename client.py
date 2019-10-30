import socket
import struct
import msgpack


class ManagerClient(object):

    def __init__(self, conn_id=None, sock=None):
        self.conn_id = conn_id
        self.sock = sock

    def connect(self, host, port):
        self.sock = socket.socket()
        self.sock.connect((host, port))

    def close(self):
        req = self.create_msg({'kind': 'close'})
        self.sock.send(req)
        self.sock.close()
        self.sock = None

    @property
    def is_connected(self):
        return self.sock

    def ssh_connect(self, host):
        if not self.sock:
            raise Exception('No manager connection')
        req = self.create_msg({'kind': 'connect', 'host': host})
        self.sock.send(req)
        rep = self.recv_msg(self.sock)
        # TODO: error checking
        self.conn_id = rep['conn_id']

    def ssh_exec(self, cmd):
        if not self.sock:
            raise Exception('No manager connection')
        if not self.conn_id:
            raise Exception('No ssh connection')
        req = self.create_msg({'kind': 'run', 'conn_id': self.conn_id, 'command': cmd})
        self.sock.send(req)
        rep = self.recv_msg(self.sock)
        # TODO: error checking
        return rep['stdout'], rep['stderr']

    def ssh_disconnect(self):
        if not self.sock:
            raise Exception('No manager connection')
        if not self.conn_id:
            raise Exception('No ssh connection')
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

    @staticmethod
    def recv_msg(sock):
        # Read message length and unpack it into an integer
        raw_msglen = recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return msgpack.unpackb(recvall(sock, msglen), raw=False)


class SSHClient(object):

    def __init__(self, manager_host='127.0.0.1', manager_port='12345', manager=None):
        self.manager_host = manager_host
        self.manager_port = manager_port
        if manager is not None:
            self.manager = manager
        else:
            self.manager = Manager()

    def has_manager_conn(self):
        return self.sock is not None

    def connect_manager(self):
        self.manager.connect(self.manager_host, self.manager_port)

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
        self.manager.ssh_connect(hostname)


import socket
import struct
import msgpack

def create_msg(msg):
    # Prefix each message with a 4-byte length (network byte order)
    packed = msgpack.packb(msg, use_bin_type=True)
    return struct.pack('>I', len(packed)) + packed

def recvall(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data


def recv_msg(sock):
    # Read message length and unpack it into an integer
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    return msgpack.unpackb(recvall(sock, msglen), raw=False)

s = socket.socket()
s.connect(('127.0.0.1', 8888))
print('client connect')

msg = create_msg({'kind': 'connect', 'host': '10.27.3.51'})
s.send(msg)
msg = recv_msg(s)
print('client got : %s' % (msg))
conn_id = msg['conn_id']
msg = create_msg({'kind': 'run', 'conn_id': conn_id, 'command': 'echo Start!'})
print('send run')
s.send(msg)
msg = recv_msg(s)
print('client got : %s' % (msg))
msg = create_msg({'kind': 'disconnect', 'conn_id': conn_id})
s.send(msg)
msg = recv_msg(s)
print('client got : %s' % (msg))
msg = create_msg({'kind': 'close'})
s.send(msg)
#msg = recv_msg(s)

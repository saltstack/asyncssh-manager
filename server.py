import asyncio
import asyncssh
import struct
import msgpack
import uuid

class Client(object):

    def __init__(self, addr, reader, writer, task=None):
        self.addr = addr
        self.writer = writer
        self.reader = reader
        self.task = task


class Manager(object):
    handlers = {
        'connect': 'handle_connect',
        'disconnect': 'handle_disconnect',
        'close': 'handle_close',
        'run': 'handle_run',
    }

    def __init__(self, clients=None, connections=None):
        self.clients = {}
        if clients is not None:
            self.clients = clients
        self.connections = {}
        if connections is not None:
            self.connections = connections

    async def handle_client(self, client):
        keep_going = True
        while keep_going:
            message = await self.recv_msg(client.reader)
            if message is None:
                await asyncio.sleep(.3)
                continue
            print("Received %r from %r" % (message, client.addr))
            handler_name = self.handlers[message['kind']]
            handler = getattr(self, handler_name)
            keep_going = await handler(client, message)

#        print("Send: %r" % message)
#        await self.send_msg(client.writer, message)

#        await client.writer.drain()

#        print("Close the client socket")
#        client.writer.close()

    async def handle_run(self, client, msg):
        conn_id = msg['conn_id']
        conn = self.connections[conn_id]
        result = await conn.run(msg['command'], check=True)
        await self.send_msg(client.writer, {'conn_id': conn_id, 'stdout': result.stdout})
        return True

    async def handle_close(self, client, msg):
        await client.writer.drain()
        client.writer.close()
        client.reader.close()
        return False

    async def handle_disconnect(self, client, msg):
        conn_id = msg['conn_id']
        conn = self.connections[conn_id]
        conn.close()
        await conn.wait_closed()
        await self.send_msg(client.writer, {'conn_id': conn_id, 'status': 'closed'})
        return True

    async def handle_connect(self, client, msg):
        conn_id = str(uuid.uuid4())
        connection = await asyncssh.connect(msg['host'])
        print(dir(connection))
        self.connections[conn_id] = connection
        await self.send_msg(client.writer, {'conn_id': conn_id, 'status': 'connected'})
        return True

    async def handle_client_connection(self, reader, writer):
        addr = writer.get_extra_info('peername')
        client =  Client(addr, reader, writer)
        self.clients[addr] = client
        client.task = asyncio.ensure_future(self.handle_client(client))

    async def send_msg(self, writer, msg):
        # Prefix each message with a 4-byte length (network byte order)
        packed = msgpack.packb(msg, use_bin_type=True)
        msg = struct.pack('>I', len(packed)) + packed
        writer.write(msg)
        await writer.drain()

    async def _recv_all(self, reader, length):
        # Helper function to recv n bytes or return None if EOF is hit
        data = b''
        while len(data) < length:
            try:
                packet = await reader.readexactly(length - len(data))
            except asyncio.IncompleteReadError:
                packet = None
            if not packet:
                return None
            data += packet
        return data

    async def recv_msg(self, reader):
        # Read message length and unpack it into an integer
        raw_msglen = await self._recv_all(reader, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return msgpack.unpackb(await self._recv_all(reader, msglen), raw=False)

    async def serve(self):
        while True:
            for addr in list(self.clients):
                client = self.clients[addr]
                if client.task.done():
                    self.clients.pop(addr)
                await client.task
            await asyncio.sleep(1)


async def start(manager, loop):
    coro = asyncio.start_server(manager.handle_client_connection, '127.0.0.1', 8888, loop=loop)
    server = await asyncio.ensure_future(coro)
    print('Serving on {}'.format(server.sockets[0].getsockname()))
    await asyncio.ensure_future(manager.serve())


def main():
    # Serve requests until Ctrl+C is pressed
    loop = asyncio.get_event_loop()
    manager = Manager()
    asyncio.ensure_future(start(manager, loop))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.stop()
    finally:
        loop.close()

if __name__ == '__main__':
    main()

import argparse
import asyncio
import asyncssh
import logging
import msgpack
import struct
import uuid


log = logging.getLogger()

parser = argparse.ArgumentParser()
parser.add_argument(
    '--address',
    default='127.0.0.1',
    type=str,
    help='Address to bind to [default: 127.0.0.1]',
)
parser.add_argument(
    '--port',
    type=int,
    default=10888,
    help='Port to bind to [default: 10888]',
)


class Client(object):

    def __init__(self, addr, reader, writer, task=None):
        self.addr = addr
        self.writer = writer
        self.reader = reader
        self.task = task


class Manager(object):

    # Map message kinds to handle methods
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
        self.keep_running = True

    async def client_task(self, client, keep_going=True):
        while keep_going: #and self.keep_going:
            message = await self.recv_msg(client.reader)
            if message is None:
                await asyncio.sleep(.3)
                continue
            log.info('Received massage %s from %s', message['kind'], client.addr)
            handler_name = self.handlers[message['kind']]
            handler = getattr(self, handler_name)
            keep_going = await handler(client, message)

    async def handle_run(self, client, msg):
        conn_id = msg['conn_id']
        conn = self.connections[conn_id]
        result = await conn.run(msg['command'], check=True)
        await self.send_msg(client.writer, {'conn_id': conn_id, 'stdout': result.stdout})
        return True

    async def handle_close(self, client, msg):
        await client.writer.drain()
        client.writer.close()
        #client.reader.close()
        return False

    async def handle_disconnect(self, client, msg):
        conn_id = msg['conn_id']
        conn = self.connections[conn_id]
        conn.close()
        await conn.wait_closed()
        await self.send_msg(client.writer, {'conn_id': conn_id, 'status': 'closed'})
        return True

    async def handle_connect(self, client, msg):
        '''
        '''
        conn_id = str(uuid.uuid4())
        connection = await asyncssh.connect(msg['host'])
        self.connections[conn_id] = connection
        await self.send_msg(client.writer, {'conn_id': conn_id, 'status': 'connected'})
        return True

    async def new_client(self, reader, writer):
        '''
        Handle new client connections by spawning a `handle_client` task.
        '''
        log.info("New client")
        addr = writer.get_extra_info('peername')
        client =  Client(addr, reader, writer)
        self.clients[addr] = client
        client.task = asyncio.ensure_future(self.client_task(client))

    async def send_msg(self, writer, msg):
        '''
        Send a messsage a client via the writer
        '''
        # Prefix each message with a 4-byte length (network byte order)
        packed = msgpack.packb(msg, use_bin_type=True)
        msg = struct.pack('>I', len(packed)) + packed
        writer.write(msg)
        await writer.drain()

    async def _recv_all(self, reader, length):
        '''
        Helper function to recv n bytes or return None if EOF is hit
        '''
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
        '''
        Read message length and unpack it into an integer, then read the rest
        of they bytes specified by the leng off the wire
        '''
        raw_msglen = await self._recv_all(reader, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return msgpack.unpackb(await self._recv_all(reader, msglen), raw=False)

    async def serve(self):
        '''
        Clean up client tasks as they end
        '''
 #       try:
        while True: # self.keep_running:
            for addr in list(self.clients):
                client = self.clients[addr]
                if client.task.done():
                    self.clients.pop(addr)
                    await client.task
            await asyncio.sleep(.3)
#        except KeyboardInterrupt:
#            pass

    async def start(self, address, port, loop):
        coro = asyncio.start_server(self.new_client, address, port, loop=loop)
        server = await asyncio.ensure_future(coro)
        log.info('Serving on {}'.format(server.sockets[0].getsockname()))
        await asyncio.ensure_future(self.serve())


def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    ns = parser.parse_args()
    # Serve requests until Ctrl+C is pressed
    loop = asyncio.get_event_loop()
    manager = Manager()
    #task = asyncio.ensure_future(manager.start(ns.address, ns.port, loop))
    asyncio.ensure_future(manager.start(ns.address, ns.port, loop))
    try:
        #loop.run_until_complete(manager.start(ns.address, ns.port, loop))
        loop.run_forever()
    except KeyboardInterrupt:
        print("MEH 1")
        manager.keep_running = False
        print("MEH 2")
        loop.stop()
        print("MEH 3")
    finally:
        loop.close()

if __name__ == '__main__':
    main()

```
import subprocess
import paramiko
import client

host = '127.0.0.1'
port = 12345

manager = subprocess.Popen(['python', 'server.py', '--host', host, '--port', str(port)])


factory = client.ClientFactory(host, port)

# Monkey patch paramiko
paramiko.SSHClient = factory

```


from client import SSHClient, ClientException

from .fixtures import server_process, sshd
import pytest



def test_client_server_connect(server_process):
    client = SSHClient(manager_port=server_process.port)
    client.connect_manager()
    assert client.has_manager_conn()


def test_client_server_no_connect(server_process):
    client = SSHClient(manager_port=server_process.port + 10)
    with pytest.raises(ClientException, match='^Unable to connect to manager$'):
        client.connect_manager(timeout=1)


def test_client_server_ssh_connect(server_process, sshd):
    client = SSHClient(manager_port=server_process.port)
    client.connect_manager()
    assert client.has_manager_conn()
    assert client.manager.conn_id is None
    client.connect('10.27.3.51', sshd.port)
    assert client.manager.conn_id is not None

def test_client_server_ssh_echo(server_process, sshd):
    client = SSHClient(manager_port=server_process.port)
    client.connect_manager()
    assert client.has_manager_conn()
    assert client.manager.conn_id is None
    client.connect('10.27.3.51', sshd.port)
    assert client.manager.conn_id is not None
    stdin, stdout, stderr = client.exec_command('echo Test!')
    print(stdout.name)
    assert stdout.read(1024) == 'Test!\n'
    client.close()
    assert client.manager.conn_id is None

def test_client_server_ssh_stdin(server_process, sshd):
    client = SSHClient(manager_port=server_process.port)
    client.connect_manager()
    assert client.has_manager_conn()
    assert client.manager.conn_id is None
    client.connect('10.27.3.51', sshd.port)
    assert client.manager.conn_id is not None
    stdin, stdout, stderr = client.exec_command('bc')
    stdin.write('10 + 10\n')
    assert stdout.read(1024) == '20\n'
    client.close()
    assert client.manager.conn_id is None

def test_client_server_ssh_close(server_process, sshd):
    client = SSHClient(manager_port=server_process.port)
    client.connect_manager()
    assert client.has_manager_conn()
    assert client.manager.conn_id is None
    client.connect('10.27.3.51', sshd.port)
    assert client.manager.conn_id is not None
    client.close()
    assert client.manager.conn_id is None


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
    print("MEH")
    client.connect('10.27.3.51', sshd.port)


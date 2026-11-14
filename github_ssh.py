import os, sys, json, base64, threading, select
from urllib.request import urlopen
import paramiko
hostkeys=json.load(urlopen('https://api.github.com/meta',timeout=20))['ssh_keys']
client=paramiko.SSHClient()
for key in hostkeys:
    kind,encoded=key.split()[:2]
    cls={'ssh-ed25519':paramiko.Ed25519Key,'ssh-rsa':paramiko.RSAKey,'ecdsa-sha2-nistp256':paramiko.ECDSAKey}.get(kind)
    if cls:client.get_host_keys().add('[ssh.github.com]:443',kind,cls(data=base64.b64decode(encoded)))
client.connect('ssh.github.com',443,username='git',key_filename=os.environ['COURT_GIT_KEY_FILE'],look_for_keys=False,allow_agent=False,timeout=25)
channel=client.get_transport().open_session()
channel.exec_command(sys.argv[-1])
def send():
    try:
        while True:
            data=os.read(0,65536)
            if not data:break
            channel.sendall(data)
        channel.shutdown_write()
    except (OSError,EOFError):pass
threading.Thread(target=send,daemon=True).start()
while True:
    if channel.recv_ready():os.write(1,channel.recv(65536))
    if channel.recv_stderr_ready():os.write(2,channel.recv_stderr(65536))
    if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():break
    select.select([channel],[],[],.1)
status=channel.recv_exit_status();client.close();sys.exit(status)

import os
import time

import pytest
from scapy.all import rdpcap, ICMP

from services_debugger.dumpers import PCAPDump


@pytest.mark.usefixtures('test_ssh_server')
def test_pcap_dumper():
    dumper = PCAPDump(name='pcap_dump', address='127.0.0.1', port=10022,
                      username='test_user', password='test_password', output_file='test_dump.pcap')
    dumper.start()
    time.sleep(5)
    dumper.stop()

    assert os.path.isfile('test_dump.pcap')
    assert os.path.getsize('test_dump.pcap') > 0

    pcap = rdpcap('test_dump.pcap')
    assert len(pcap) > 0
    ping_requests = [pkt for pkt in pcap if ICMP in pkt and pkt.payload['ICMP'].type == 8]
    assert len(ping_requests) >= 4

    os.remove('test_dump.pcap')

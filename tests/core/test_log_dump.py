import os
import re
import time

import pytest

from app.core.dumpers import LogDump
from app.models.host import Host


@pytest.mark.usefixtures('test_ssh_server')
def test_log_dumper() -> None:
    """Проверка работы удаленного сниффера логов."""

    dumper = LogDump(
        name='log_dump',
        host=Host(
            ssh_address='127.0.0.1',
            ssh_port=10022,
            username='test_user',
            password='test_password',
        ),
        output_file='ping.log',
        dumped_file='/tmp/ping.log',
    )
    dumper.start()
    time.sleep(5)
    dumper.stop()

    assert os.path.isfile('ping.log')
    assert os.path.getsize('ping.log') > 0

    count_ping = 0
    with open('ping.log', encoding='utf8') as log_file:
        for line in log_file:
            if re.match(r'64 bytes from 127\.0\.0\.1: seq=\d+ ttl=64 time=\d+\.\d{3} ms', line):
                count_ping += 1
            else:
                raise AssertionError(f'Unmatched line: {line}')
    assert count_ping >= 4
    os.remove('ping.log')

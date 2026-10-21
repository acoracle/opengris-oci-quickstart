#!/usr/bin/env python3
"""Submit eight tasks to the running OCI Raw workers and print versions/hosts."""
import argparse
from scaler import Client


def inspect_worker(number):
    import socket
    import time
    from importlib.metadata import version
    time.sleep(2)
    return {'task': number, 'host': socket.gethostname(),
            'scaler': version('opengris-scaler'), 'numpy': version('numpy')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scheduler', default='tcp://127.0.0.1:8516')
    args = parser.parse_args()
    with Client(address=args.scheduler) as client:
        futures = [client.submit(inspect_worker, number) for number in range(8)]
        for future in futures:
            print(future.result(), flush=True)

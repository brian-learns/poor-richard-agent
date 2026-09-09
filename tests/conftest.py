"""Shared fixtures: every test runs with the network blocked.

Adapted from the Poor Richard almanack's ``tests/conftest.py``. A PASS therefore
means the code path is both correct *and* offline. The socket patch catches
TCP/DNS attempts made after interpreter start; a component that touches the
network at runtime fails loudly, which is the desired behaviour.
"""

import socket

import pytest


@pytest.fixture(autouse=True)
def no_network():
    def blocked(*args, **kwargs):
        raise RuntimeError("network access attempted (blocked by tests/conftest.py)")

    old = (
        socket.socket.connect,
        socket.socket.connect_ex,
        socket.getaddrinfo,
    )
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.getaddrinfo = blocked
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = old

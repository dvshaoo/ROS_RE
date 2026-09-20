"""Minimal GDB Remote Serial Protocol client -- enough to talk to lldb-server's
gdbserver mode without needing a full gdb/lldb client installed on the host.

Protocol: packets are $<payload>#<2-hex-digit-checksum>. We ack with '+'.
"""
import socket


class RSP:
    def __init__(self, host='127.0.0.1', port=15040):
        self.sock = socket.create_connection((host, port), timeout=10)
        self.buf = b''

    def _checksum(self, data: bytes) -> int:
        return sum(data) & 0xff

    def send(self, payload: str):
        data = payload.encode()
        pkt = b'$' + data + b'#' + f'{self._checksum(data):02x}'.encode()
        self.sock.sendall(pkt)

    def _read_byte(self):
        if not self.buf:
            self.buf = self.sock.recv(65536)
            if not self.buf:
                raise ConnectionError('socket closed')
        b, self.buf = self.buf[:1], self.buf[1:]
        return b

    def recv_raw(self, timeout=10, debug=False):
        self.sock.settimeout(timeout)
        out = b''
        # skip leading acks/notifications
        while True:
            b = self._read_byte()
            if debug:
                print('  RAW byte:', b)
            if b == b'+' or b == b'-':
                continue
            if b == b'$':
                break
            out += b  # unexpected leading junk, keep for debugging
        payload = b''
        while True:
            b = self._read_byte()
            if b == b'#':
                break
            payload += b
        _cksum = self._read_byte() + self._read_byte()
        self.sock.sendall(b'+')  # ack
        return payload.decode(errors='replace')

    def cmd(self, payload: str, timeout=10) -> str:
        self.send(payload)
        return self.recv_raw(timeout=timeout)

    def close(self):
        self.sock.close()


def hex_encode(s: str) -> str:
    return s.encode().hex()


if __name__ == '__main__':
    r = RSP()
    print('qSupported ->', r.cmd('qSupported:multiprocess+;swbreak+;hwbreak+;qRelocInsn+'))
    print('?          ->', r.cmd('?'))
    print('qC         ->', r.cmd('qC'))
    print('qHostInfo  ->', r.cmd('qHostInfo'))
    r.close()

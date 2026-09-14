#!/usr/bin/env python3
"""
Local DNS server for ROS-RE.
Resolves ALL .easebar.com domains to 127.0.0.1.
Listens on UDP 53, forwards non-easebar queries to the real DNS (router).
"""
import socket, struct, sys, threading

DNS_SERVER = "192.168.100.1"  # router
LISTEN_PORT = 53
LISTEN_ADDR = "0.0.0.0"

# Domains we fake-resolve to localhost
FAKE_DOMAINS = set()
FAKE_IP = "127.0.0.1"

def parse_domain(data, offset):
    """Parse a domain name from DNS packet, return (domain_string, new_offset)."""
    parts = []
    jumped = False
    original_offset = offset
    max_offset = offset
    while True:
        if offset >= len(data):
            break
        length = data[offset]
        if length == 0:
            offset += 1
            if not jumped:
                max_offset = offset
            break
        if (length & 0xC0) == 0xC0:
            # Pointer
            if not jumped:
                max_offset = offset + 2
            pointer = struct.unpack("!H", data[offset:offset+2])[0] & 0x3FFF
            offset = pointer
            jumped = True
            continue
        offset += 1
        parts.append(data[offset:offset+length].decode("ascii", errors="replace"))
        offset += length
    return ".".join(parts), max_offset if not jumped else max_offset

def handle_request(data, addr, sock):
    try:
        # Parse header
        tx_id = data[0:2]
        flags = data[2:4]
        qdcount = struct.unpack("!H", data[4:6])[0]
        ancount = struct.unpack("!H", data[6:8])[0]

        # Parse question
        offset = 12
        domain, offset = parse_domain(data, offset)
        qtype = struct.unpack("!H", data[offset:offset+2])[0]
        offset += 2
        qclass = struct.unpack("!H", data[offset:offset+2])[0]
        offset += 2

        domain_lower = domain.lower()
        is_easebar = "easebar.com" in domain_lower

        if is_easebar:
            print(f"[DNS] FAKE {domain} -> {FAKE_IP}", flush=True)
            # Build response: copy header, set QR bit (response), 1 answer
            resp_flags = b"\x81\x80"  # standard response, no error
            resp = tx_id + resp_flags
            resp += struct.pack("!HHHH", qdcount, 1, 0, 0)  # 1 answer
            resp += data[12:offset]  # copy question section
            # Answer section: domain pointer at offset 12, type A, class IN, TTL 300, 4 bytes
            resp += b"\xc0\x0c"  # pointer to domain at offset 12
            resp += struct.pack("!HH", 1, 1)  # type A, class IN
            resp += struct.pack("!I", 300)  # TTL 300s
            resp += struct.pack("!H", 4)  # rdlength
            resp += socket.inet_aton(FAKE_IP)
            sock.sendto(resp, addr)
        else:
            # Forward to real DNS
            print(f"[DNS] FORWARD {domain}", flush=True)
            forward_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            forward_sock.settimeout(5)
            try:
                forward_sock.sendto(data, (DNS_SERVER, 53))
                real_resp, _ = forward_sock.recvfrom(512)
                sock.sendto(real_resp, addr)
            except socket.timeout:
                print(f"[DNS] TIMEOUT forwarding {domain}", flush=True)
            finally:
                forward_sock.close()
    except Exception as e:
        print(f"[DNS] ERROR: {e}", flush=True)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LISTEN_ADDR, LISTEN_PORT))
    print(f"[DNS] Listening on {LISTEN_ADDR}:{LISTEN_PORT}", flush=True)
    print(f"[DNS] Fake resolve: *.easebar.com -> {FAKE_IP}", flush=True)
    print(f"[DNS] Forward: everything else -> {DNS_SERVER}", flush=True)
    while True:
        data, addr = sock.recvfrom(512)
        threading.Thread(target=handle_request, args=(data, addr, sock), daemon=True).start()

if __name__ == "__main__":
    main()

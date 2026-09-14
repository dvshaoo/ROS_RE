import struct

data = open('wire_capture.pcap', 'rb').read()
off = 24
pkts = []
while off < len(data):
    ts_sec, ts_usec, caplen, origlen = struct.unpack_from('<IIII', data, off)
    off += 16
    pkt = data[off:off+caplen]
    off += caplen
    pkts.append((ts_sec, ts_usec, caplen, origlen, pkt))

t_first = pkts[0][0] + pkts[0][1] / 1e6

def parse_eth_ip_udp(pkt):
    eth_type = struct.unpack_from('>H', pkt, 12)[0]
    if eth_type != 0x0800:
        return None
    ip_off = 14
    ver_ihl = pkt[ip_off]
    ihl = (ver_ihl & 0xF) * 4
    proto = pkt[ip_off + 9]
    src_ip = '.'.join(str(b) for b in pkt[ip_off+12:ip_off+16])
    dst_ip = '.'.join(str(b) for b in pkt[ip_off+16:ip_off+20])
    if proto != 17:  # UDP
        return {'proto': proto, 'src_ip': src_ip, 'dst_ip': dst_ip}
    udp_off = ip_off + ihl
    src_port, dst_port, udp_len, udp_csum = struct.unpack_from('>HHHH', pkt, udp_off)
    payload = pkt[udp_off+8:udp_off+udp_len]
    return {
        'proto': 'UDP', 'src_ip': src_ip, 'dst_ip': dst_ip,
        'src_port': src_port, 'dst_port': dst_port,
        'payload_len': len(payload), 'payload': payload,
    }

print(f"{'#':<3} {'t(s)':<8} {'src':<22} {'dst':<22} {'len':<5} {'hex_prefix'}")
for i, (s, u, cl, ol, pkt) in enumerate(pkts):
    t = s + u / 1e6 - t_first
    info = parse_eth_ip_udp(pkt)
    if info is None or info.get('proto') != 'UDP':
        print(i, f"{t:.3f}", 'non-UDP or unparsed', info)
        continue
    src = f"{info['src_ip']}:{info['src_port']}"
    dst = f"{info['dst_ip']}:{info['dst_port']}"
    print(f"{i:<3} {t:<8.3f} {src:<22} {dst:<22} {info['payload_len']:<5} {info['payload'][:20].hex()}")

print()
print("=== Full payload hex for packet 0 (first client request) ===")
print(parse_eth_ip_udp(pkts[0][4])['payload'].hex())
print()
print("=== Full payload hex for packet 1 (first reply) ===")
print(parse_eth_ip_udp(pkts[1][4])['payload'].hex())

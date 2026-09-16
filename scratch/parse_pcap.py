import struct
import sys

path = sys.argv[1] if len(sys.argv) > 1 else 'baseapp_capture.pcap'

with open(path, 'rb') as f:
    data = f.read()

magic, ver_major, ver_minor, tz, sigfigs, snaplen, network = struct.unpack_from('<IHHiIII', data, 0)
print('magic=0x%x network=%d' % (magic, network))
offset = 24
pkt_num = 0
while offset < len(data):
    ts_sec, ts_usec, incl_len, orig_len = struct.unpack_from('<IIII', data, offset)
    offset += 16
    pkt = data[offset:offset+incl_len]
    offset += incl_len
    pkt_num += 1

    # Linux cooked capture (SLL) header is 16 bytes if network==113, else assume raw IP (network==101) or Ethernet (1)
    idx = 0
    if network == 113:  # LINKTYPE_LINUX_SLL
        idx = 16
    elif network == 1:  # Ethernet
        idx = 14
    # else raw IP, idx=0

    ip = pkt[idx:]
    if len(ip) < 20:
        continue
    ver_ihl = ip[0]
    ihl = (ver_ihl & 0x0F) * 4
    proto = ip[9]
    src = '.'.join(str(b) for b in ip[12:16])
    dst = '.'.join(str(b) for b in ip[16:20])
    if proto != 17:  # UDP
        print('pkt %d: non-UDP proto=%d src=%s dst=%s' % (pkt_num, proto, src, dst))
        continue
    udp = ip[ihl:]
    if len(udp) < 8:
        continue
    sport, dport, ulen, csum = struct.unpack_from('>HHHH', udp, 0)
    payload = udp[8:]
    print('pkt %d: %s:%d -> %s:%d len=%d payload_len=%d hex=%s' % (
        pkt_num, src, sport, dst, dport, ulen, len(payload), payload[:40].hex()))

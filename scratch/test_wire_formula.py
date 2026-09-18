import struct

def encode_method_call(entity_id, method_index, num_methods, args=b''):
    div = (num_methods + 192) // 255
    threshold = 62 - div

    if method_index < threshold:
        w1 = method_index
        extra_byte = b''
    else:
        diff = method_index - threshold
        w1 = threshold + (diff // 256)
        extra_byte = bytes([diff % 256])

    msgid = 128 + w1
    width = 2 if w1 < 64 else 1
    payload = struct.pack('<I', entity_id) + extra_byte + args
    return msgid, width, payload

def decode_method_call(msgid, payload, num_methods):
    w1 = msgid - 128
    div = (num_methods + 192) // 255
    threshold = 62 - div

    eid = struct.unpack('<I', payload[:4])[0]
    stream = payload[4:]

    if w1 < threshold:
        method_index = w1
        args = stream
    else:
        extra_byte = stream[0]
        args = stream[1:]
        diff_high = w1 - threshold
        method_index = threshold + (diff_high << 8) + extra_byte

    return eid, method_index, args

def test():
    for idx in range(25):
        msgid, width, payload = encode_method_call(1, idx, 25, b'test')
        eid, dec_idx, args = decode_method_call(msgid, payload, 25)
        assert eid == 1 and dec_idx == idx and args == b'test', f'Account failed for {idx}'

    for idx in [0, 56, 57, 58, 100, 500, 1083, 1130]:
        msgid, width, payload = encode_method_call(2, idx, 1131, b'data')
        eid, dec_idx, args = decode_method_call(msgid, payload, 1131)
        assert eid == 2 and dec_idx == idx and args == b'data', f'Athlete failed for {idx}'

    msgid, width, payload = encode_method_call(1, 1083, 1131, b'\x00')
    print(f'showSelectCharacter(1083) wire encoding:')
    print(f'  msgid: {msgid} (hex: 0x{msgid:02x})')
    print(f'  width: {width} bytes')
    print(f'  payload len: {len(payload)} bytes')
    print(f'  payload hex: {payload.hex()}')
    assert msgid == 189
    assert width == 2
    assert payload == struct.pack('<I', 1) + b'\x02\x00'
    print('ALL TESTS PASSED!')

if __name__ == '__main__':
    test()

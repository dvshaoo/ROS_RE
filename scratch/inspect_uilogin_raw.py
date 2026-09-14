with open(r'c:\Users\Raysoo\Downloads\ROS_RE\scratch\uilogin.raw', 'rb') as f:
    data = f.read()

print(f"uilogin.raw size: {len(data)} bytes")
print("First 300 bytes:")
print(data[:300])

# Check if it contains python bytecode or text
if b'\x03\xf3\r\n' in data[:4] or b'c\x00\x00\x00' in data[:20]:
    print("Detected Python compiled code / marshal data!")
    import marshal, dis
    # Try unmarshalling
    try:
        # Check header
        code = marshal.loads(data[8:])
        print(f"Code object unmarshalled successfully! co_name: {code.co_name}")
        print("Constants:", code.co_consts)
        print("Names:", code.co_names)
    except Exception as e:
        print(f"Marshal error: {e}")
        try:
            code = marshal.loads(data)
            print(f"Code object unmarshalled from 0: {code.co_name}")
        except Exception as e2:
            print(f"Marshal error 2: {e2}")

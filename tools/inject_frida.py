import frida
import sys
import time

# Connect to Gadget - with Gadget, the device IS the app process
device = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
print('Connected to device')

# With Gadget listen mode, we need to enumerate and find the game process
# Gadget runs inside the game process, so we attach to PID 1 (it will map to the Gadget host)
try:
    # List all processes to find chiji
    procs = device.enumerate_processes()
    for p in procs:
        print(f'  Process: {p.name} (PID: {p.pid})')
        if 'chiji' in p.name.lower() or p.pid > 10000:
            pass  # continue listing
except Exception as e:
    print(f'enumerate_processes failed: {e}')

# Try to attach using the session ID directly
print('\nTrying to get Gadget session...')
try:
    # Gadget's session is the host process itself
    # Use attach with PID -1 to get the Gadget host
    session = device.attach(device.enumerate_processes()[0].pid)
    print(f'Attached to PID {device.enumerate_processes()[0].pid}')
    
    with open(r'C:\Users\Raysoo\Downloads\ROS_RE\mitm\frida-dns-hook.js', 'r') as f:
        script_code = f.read()
    
    script = session.create_script(script_code)
    script.load()
    print('Script loaded successfully!')
    print('DNS hook is now active. Game should resolve easebar.com domains.')
    
    # Keep alive for 5 minutes
    print('Keeping session alive for 5 minutes...')
    time.sleep(300)
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()

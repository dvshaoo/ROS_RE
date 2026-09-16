import hashlib
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.backends import default_backend

cert_bytes = Path(r"c:\Users\Raysoo\Downloads\ROS_RE\mitm\ca_v3.crt").read_bytes()
cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())

# In OpenSSL, subject_hash is the first 4 bytes of SHA1 of the DER-encoded subject, in little endian
# subject_hash_old is the first 4 bytes of MD5 of the canonical DER-encoded subject, in little endian
# But OpenSSL canonicalizes the name (lowercase, no leading/trailing spaces, UTF-8 strings).
print("Subject:", cert.subject)

import subprocess
# Let's run git openssl or similar if available, or check python
import shutil
openssl_path = shutil.which("openssl")
if openssl_path:
    print("Found openssl:", openssl_path)
    res1 = subprocess.run([openssl_path, "x509", "-in", r"c:\Users\Raysoo\Downloads\ROS_RE\mitm\ca_v3.crt", "-noout", "-subject_hash"], capture_output=True, text=True)
    res2 = subprocess.run([openssl_path, "x509", "-in", r"c:\Users\Raysoo\Downloads\ROS_RE\mitm\ca_v3.crt", "-noout", "-subject_hash_old"], capture_output=True, text=True)
    print("subject_hash:", res1.stdout.strip())
    print("subject_hash_old:", res2.stdout.strip())

from pathlib import Path
from cryptography import x509
from cryptography.hazmat.backends import default_backend

content = Path(r"c:\Users\Raysoo\Downloads\ROS_RE\mitm\srv.crt").read_bytes()
# Count how many certificates are in srv.crt
certs = x509.load_pem_x509_certificates(content)
print(f"Number of certs in srv.crt: {len(certs)}")
for i, c in enumerate(certs):
    print(f"Cert {i}: Subject={c.subject}, Issuer={c.issuer}")

for ca_name in ["ca.crt", "ca_v2.crt", "ca_v3.crt"]:
    ca_bytes = Path(r"c:\Users\Raysoo\Downloads\ROS_RE\mitm", ca_name).read_bytes()
    ca = x509.load_pem_x509_certificate(ca_bytes, default_backend())
    print(f"CA {ca_name}: Subject={ca.subject}, Issuer={ca.issuer}")

import ssl
from pathlib import Path

mitm_dir = Path(r"c:\Users\Raysoo\Downloads\ROS_RE\mitm")
for ca_name in ["ca.crt", "ca_v2.crt", "ca_v3.crt"]:
    ca_path = mitm_dir / ca_name
    srv_path = mitm_dir / "srv.crt"
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        srv = x509.load_pem_x509_certificate(srv_path.read_bytes(), default_backend())
        ca = x509.load_pem_x509_certificate(ca_path.read_bytes(), default_backend())
        print(f"{ca_name}: {srv.issuer == ca.subject}")
    except Exception as e:
        print("Error:", e)
        break

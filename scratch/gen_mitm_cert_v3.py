import os, datetime, hashlib, ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

HERE = r'c:\Users\Raysoo\Downloads\ROS_RE\mitm'

# 1. Generate CA private key and cert
ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

ca_subject = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, u'ROS-RE MITM CA V3'),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'ROS-RE'),
])

ca_cert = (
    x509.CertificateBuilder()
    .subject_name(ca_subject)
    .issuer_name(ca_subject)
    .public_key(ca_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
    .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    .sign(ca_key, hashes.SHA256(), default_backend())
)

# 2. Generate Server private key and cert
srv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

srv_subject = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, u'*.easebar.com'),
])

san_names = [
    'sdk-os.mpsdk.easebar.com',
    'qr.mpsdk.easebar.com',
    '*.mpsdk.easebar.com',
    '*.easebar.com',
    '*.netease.com',
    '*.matrix.easebar.com',
    '*.matrix.netease.com',
    '*.nie.netease.com',
    '*.nie.easebar.com',
    '*.proxima.nie.netease.com',
    '*.proxima.nie.easebar.com',
    'drpf-h45na.proxima.nie.netease.com',
    'drpf-h45na.proxima.nie.easebar.com',
    'data-detect.nie.netease.com',
    'data-detect.nie.easebar.com',
    'applogsg.matrix.netease.com',
    'applog.matrix.netease.com',
    'applog.matrix.easebar.com',
    'mgbsdknaeast.matrix.netease.com',
    'h45na.update.easebar.com',
    'g61.update.easebar.com',
    'mbdl.update.easebar.com',
    'mbdl.update.netease.com',
    'unisdk.update.easebar.com',
    'unisdk.update.netease.com',
    'update.unisdk.easebar.com',
    'sigma-keypoint-h41na.proxima.nie.easebar.com',
    'sigma-keypoint-h45na.proxima.nie.easebar.com',
    'play.googleapis.com',
    'localhost',
    '127.0.0.1'
]

srv_cert = (
    x509.CertificateBuilder()
    .subject_name(srv_subject)
    .issuer_name(ca_subject)
    .public_key(srv_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
    .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
    .add_extension(
        x509.SubjectAlternativeName([x509.DNSName(n) if not n.replace('.', '').isdigit() else x509.IPAddress(ipaddress.IPv4Address(n)) for n in san_names]),
        critical=False
    )
    .sign(ca_key, hashes.SHA256(), default_backend())
)

# Save files
ca_crt_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
srv_crt_pem = srv_cert.public_bytes(serialization.Encoding.PEM)
srv_key_pem = srv_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption()
)

with open(os.path.join(HERE, 'ca_v3.crt'), 'wb') as f:
    f.write(ca_crt_pem)
with open(os.path.join(HERE, 'srv.crt'), 'wb') as f:
    f.write(srv_crt_pem)
with open(os.path.join(HERE, 'srv.key'), 'wb') as f:
    f.write(srv_key_pem)

# Calculate old subject hash for Android cacerts
der_subject = ca_cert.subject.public_bytes(default_backend())
h = hashlib.md5(der_subject).digest()
val = int.from_bytes(h[:4], 'little')
hash_name = f'{val:08x}.0'
hash_path = os.path.join(HERE, hash_name)
with open(hash_path, 'wb') as f:
    f.write(ca_crt_pem)

print('Generated:', hash_name, 'at', hash_path)

#!/usr/bin/env python3
import os
from ipaddress import ip_address
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta

def generate_ca():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'RU'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'ServerMonitor'),
        x509.NameAttribute(NameOID.COMMON_NAME, 'ServerMonitor CA'),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None),
        critical=True
    ).sign(key, hashes.SHA256())
    
    return key, cert

def generate_cert(ca_key, ca_cert, name, is_server=True):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'RU'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'ServerMonitor'),
        x509.NameAttribute(NameOID.COMMON_NAME, name),
    ])
    
    builder = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        ca_cert.subject
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)
    )
    
    san = x509.SubjectAlternativeName([
        x509.DNSName('localhost'),
        x509.DNSName('central'),
        x509.IPAddress(ip_address('127.0.0.1')),
    ])
    builder = builder.add_extension(san, critical=False)
    
    builder = builder.add_extension(
        x509.BasicConstraints(ca=False, path_length=None),
        critical=True
    )
    
    if is_server:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False
        )
    else:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False
        )
    
    cert = builder.sign(ca_key, hashes.SHA256())
    return key, cert

def save_cert(key, cert, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(f'{path}.key', 'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    with open(f'{path}.crt', 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

def main():
    print('Generating CA certificate...')
    ca_key, ca_cert = generate_ca()
    
    os.makedirs('central/certs', exist_ok=True)
    os.makedirs('node/certs', exist_ok=True)
    
    with open('central/certs/ca.crt', 'wb') as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    with open('node/certs/ca.crt', 'wb') as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    
    print('Generating central server certificate...')
    server_key, server_cert = generate_cert(ca_key, ca_cert, 'central', is_server=True)
    save_cert(server_key, server_cert, 'central/certs/server')
    
    print('Generating node certificate...')
    node_key, node_cert = generate_cert(ca_key, ca_cert, 'node-agent', is_server=False)
    save_cert(node_key, node_cert, 'node/certs/client')
    
    print('Certificates generated successfully!')

if __name__ == '__main__':
    main()

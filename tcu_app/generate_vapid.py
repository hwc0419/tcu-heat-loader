#!/usr/bin/env python3
# =============================================================================
# generate_vapid.py — Generate VAPID keys for Web Push notifications
# =============================================================================
# Run once before starting web_server.py:
#   python3 generate_vapid.py
#
# Generates vapid_keys.json in tcu_app/ directory.
# Keep vapid_keys.json secure — add to .gitignore.
# =============================================================================

import json
import os
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
import base64

def generate_vapid_keys():
    # Generate EC key pair
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key  = private_key.public_key()

    # Encode private key
    private_bytes = private_key.private_numbers().private_value.to_bytes(32, 'big')
    private_b64   = base64.urlsafe_b64encode(private_bytes).rstrip(b'=').decode()

    # Encode public key (uncompressed point format)
    pub_numbers = public_key.public_numbers()
    x = pub_numbers.x.to_bytes(32, 'big')
    y = pub_numbers.y.to_bytes(32, 'big')
    public_bytes = b'\x04' + x + y
    public_b64   = base64.urlsafe_b64encode(public_bytes).rstrip(b'=').decode()

    keys = {
        'public_key':  public_b64,
        'private_key': private_b64,
    }

    out_path = os.path.join(os.path.dirname(__file__), 'vapid_keys.json')
    with open(out_path, 'w') as f:
        json.dump(keys, f, indent=2)

    print('VAPID keys generated successfully.')
    print(f'Saved to: {out_path}')
    print()
    print(f'Public key:  {public_b64}')
    print()
    print('Keep vapid_keys.json secure — do not commit to git.')

if __name__ == '__main__':
    generate_vapid_keys()

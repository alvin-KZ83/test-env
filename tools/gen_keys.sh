#!/usr/bin/env bash
# Generate a fresh RSA keypair for quiz-result encryption.
#
#   bash tools/gen_keys.sh
#
# Writes:
#   tools/keys/private_key.pem   <- keep OFF the repo (already in .gitignore)
#   tools/keys/public_key.pem
# and prints the one-line base64 to paste into PUBLIC_KEY_SPKI_B64
# in test_runner.html.
set -euo pipefail
cd "$(dirname "$0")/keys"

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out private_key.pem
openssl pkey -in private_key.pem -pubout -out public_key.pem
chmod 600 private_key.pem

echo
echo "PUBLIC_KEY_SPKI_B64 (paste this into test_runner.html):"
echo
openssl pkey -pubin -in public_key.pem -outform DER | base64 | tr -d '\n'
echo

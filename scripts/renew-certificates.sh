#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

compose=(docker compose --profile certificates)
cert_path=/etc/letsencrypt/live/tokenpilot-ip/fullchain.pem
before="$(${compose[@]} run --rm --entrypoint sh certbot -c "sha256sum ${cert_path} 2>/dev/null || true")"

${compose[@]} run --rm --entrypoint certbot certbot certonly \
  --non-interactive \
  --webroot -w /var/www/certbot \
  --cert-name tokenpilot-ip \
  --ip-address "${PUBLIC_IP:-65.0.146.12}" \
  --preferred-profile shortlived \
  --email "${LETSENCRYPT_EMAIL:?Set LETSENCRYPT_EMAIL in .env}" \
  --agree-tos --no-eff-email \
  --keep-until-expiring

after="$(${compose[@]} run --rm --entrypoint sh certbot -c "sha256sum ${cert_path} 2>/dev/null || true")"
if [[ "${before}" != "${after}" ]]; then
  ${compose[@]} exec -T frontend nginx -t
  ${compose[@]} exec -T frontend nginx -s reload
  echo "Certificate changed; frontend Nginx reloaded."
else
  echo "Certificate unchanged; frontend Nginx was not reloaded."
fi

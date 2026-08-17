# TokenPilot Docker deployment

The stack runs React/Nginx, FastAPI/Uvicorn, and PostgreSQL. Only the frontend port is published. Nginx preserves the existing backend paths: most routes are `/auth`, `/dashboard`, `/workspace`, etc.; the API-key router intentionally uses `/api`. React routes fall back to `index.html`.

## Run locally or on a VPS

Copy `.env.example` to `.env`, set all `REQUIRED` values, and keep `API_KEY_ENCRYPTION_KEY` unchanged across restarts and deployments.

```sh
docker compose build
docker compose up -d
docker compose run --rm backend alembic upgrade head
docker compose ps
```

Check `/`, `/health`, and refresh a nested route such as `/dashboard/company/teams`. The health check performs `SELECT 1`, and Compose waits for PostgreSQL and the backend before starting the frontend.

PostgreSQL, uploaded avatars/screenshots, and the response cache use named volumes. Do not use `docker compose down -v` in a deployment.

## AWS Lightsail / EC2 HTTPS deployment

Install Docker Engine and the Compose plugin, clone/copy the project, create the production `.env`, and set `PUBLIC_IP=65.0.146.12` plus a real `LETSENCRYPT_EMAIL`. Open TCP 80 and 443 in the AWS security group/firewall; do not expose 5432. No host Nginx is required.

The certificate is stored in the persistent Docker volume `tokenpilot_letsencrypt_data`; the ACME challenge webroot is in `tokenpilot_acme_webroot`. Neither contains files tracked by Git.

On a new host, obtain the first publicly trusted IP certificate while the frontend is stopped. Certbot 5.4 or newer is required for IP certificates:

```sh
docker compose --profile certificates up -d postgres backend
export LETSENCRYPT_EMAIL='you@example.com'
docker compose --profile certificates run --rm --service-ports certbot certonly \
  --standalone \
  --cert-name tokenpilot-ip \
  --ip-address 65.0.146.12 \
  --preferred-profile shortlived \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos --no-eff-email
```

The normal deployment then starts the frontend on both HTTP and HTTPS:

```sh
docker compose build
docker compose up -d
docker compose run --rm backend alembic upgrade head
docker compose ps
```

After the first certificate, install the renewal timer. It runs the webroot ACME renewal daily, compares the certificate hash, and reloads only frontend Nginx when a new certificate is installed:

```sh
sudo install -m 0755 scripts/renew-certificates.sh /usr/local/sbin/tokenpilot-renew-certificates
sudo tee /etc/systemd/system/tokenpilot-renew-certificates.service >/dev/null <<'EOF'
[Unit]
Description=Renew TokenPilot Let's Encrypt IP certificate

[Service]
Type=oneshot
WorkingDirectory=/path/to/TokenPilot
ExecStart=/usr/local/sbin/tokenpilot-renew-certificates
EOF
sudo tee /etc/systemd/system/tokenpilot-renew-certificates.timer >/dev/null <<'EOF'
[Unit]
Description=Daily TokenPilot certificate renewal

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=1h

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now tokenpilot-renew-certificates.timer
sudo systemctl start tokenpilot-renew-certificates.service
sudo systemctl status tokenpilot-renew-certificates.timer
```

Replace `/path/to/TokenPilot` with the absolute checkout path. The script reads `PUBLIC_IP` and `LETSENCRYPT_EMAIL` from that checkout's `.env` via Compose. Test renewal without issuing a certificate using `docker compose --profile certificates run --rm certbot renew --dry-run` only after Certbot has a renewal configuration; the installed daily wrapper is the production renewal mechanism.

Verify HTTPS and the redirect:

```sh
curl -I http://65.0.146.12/
curl -I https://65.0.146.12/
curl -kI https://65.0.146.12/dashboard/company/teams
docker compose exec frontend nginx -t
```

The `-k` is only useful while diagnosing certificate trust; a correctly issued public certificate should work without it. To roll back to HTTP, stop the HTTPS stack, restore the previous HTTP-only `Frontend/nginx.conf` and Compose port/volume changes from the prior Git revision, then run `docker compose up -d --build`. Keep the certificate volume; do not delete PostgreSQL or application volumes.

```sh
docker compose logs -f backend
docker compose logs -f frontend
docker compose exec postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

## Updates and rollback

Back up PostgreSQL, pull the update, then run `docker compose build`, `docker compose up -d`, and the migration command. For rollback, redeploy the previous Git revision and rebuild/start it. Preserve `.env`, the Fernet key, and all named volumes; restore a DB backup only if a migration requires it.

Docker health checks do not prove SMTP delivery or external AI-provider credentials. Exercise registration/OTP, password reset, invitations, role workflows, uploads, and provider calls with real integration credentials after deployment.

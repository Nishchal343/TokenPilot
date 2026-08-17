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

## AWS Lightsail / EC2

Install Docker Engine and the Compose plugin, clone/copy the project, create the production `.env`, then use the commands above. Open only TCP 80 (and 443 if TLS is handled by a separate proxy). Do not expose 5432.

```sh
docker compose logs -f backend
docker compose logs -f frontend
docker compose exec postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

## Updates and rollback

Back up PostgreSQL, pull the update, then run `docker compose build`, `docker compose up -d`, and the migration command. For rollback, redeploy the previous Git revision and rebuild/start it. Preserve `.env`, the Fernet key, and all named volumes; restore a DB backup only if a migration requires it.

Docker health checks do not prove SMTP delivery or external AI-provider credentials. Exercise registration/OTP, password reset, invitations, role workflows, uploads, and provider calls with real integration credentials after deployment.

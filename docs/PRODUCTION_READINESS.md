# Production Readiness Notes

This project is still a local teaching MVP. The following checklist captures the first online-platform baseline before opening it to external users.

## Security

- Set `ASM_API_TOKEN` in the backend environment before exposing the FastAPI service outside localhost.
- When `ASM_API_TOKEN` is set, all API routes except `GET /api/health` require either:
  - `Authorization: Bearer <token>`
  - `X-API-Key: <token>`
- Keep CORS permissive only for local development. Restrict `allow_origins` to the production frontend origin before public deployment.

## Database

- SQLite is acceptable for local demos and teaching.
- Use PostgreSQL for a shared online service.
- Add Alembic before production schema changes. The current automatic table creation is useful for MVP iteration, but not enough for controlled upgrades.

## Runtime

- Serve the frontend as static files behind HTTPS.
- Run FastAPI behind a process manager and reverse proxy.
- Move long simulations, realtime polling, mock generation, and calibration runs into a worker process before multi-user deployment.
- Keep frontend runtime resources synced as a complete static bundle. The local `scripts/sync-service.sh` now syncs the complete `frontend/` tree, including `asm-platform/` and `3d-process/`, into the service frontend directory.

## Local Engineering Baseline

Before treating the current local build as healthy, run:

```bash
./scripts/verify-p7.sh
```

This verifies frontend module syntax, backend unit tests, required service frontend files, backend health, and frontend static resource availability. Passing this script is the local P7 engineering gate; it is not a substitute for a public production launch review.

## Project And User Isolation

- `projects.owner_id` is currently a placeholder.
- Add real user accounts and `project_members` before sharing projects between users.
- Required roles: `owner`, `editor`, `viewer`.

## External Data

- Real plant data should enter through a dedicated adapter, not direct browser writes.
- Store raw values, cleaned accepted values, quality issues, and source metadata together.
- Keep mock data visibly marked as `source=mock`.

## Minimum Launch Gate

- API token enabled.
- PostgreSQL migration path documented.
- Worker strategy selected.
- Backup/restore tested.
- Project-level access control implemented.
- Calibration and model credibility pages clearly marked as teaching/decision-support, not certified engineering output.
- P7 local engineering verification passing after every deployment sync.

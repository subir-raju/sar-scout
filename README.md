# SAR Scout

SAR Scout is a prototype for prioritizing disaster events for synthetic-aperture
radar (SAR) satellite imaging. Its goal is to make autonomy boundaries visible:
routine, pre-approved decisions can be automated, while higher-risk decisions
should be sent to a human for approval.

## Status

This repository currently contains the installable Python package foundation
and tested event/task models. It does **not** connect to a satellite provider
or submit real tasking requests. A mock tasking service, policy engine, event
ingestion, and replay evaluation are planned next.

## Setup

From the repository root, activate your virtual environment and install the
project with its development and evaluation tools:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev,eval]"
```

Run the tests and linter:

```bash
pytest
ruff check .
```

## Current model

The package defines validated `Event`, `Task`, and `Decision` models. Task
status changes go through an explicit transition function, which rejects
transitions that are not part of the task lifecycle.

## Safety and limitations

All tasking behavior is simulated. There is no live API client, orbital pass
prediction, or SAR image processing in this starter. Do not use it to submit
real tasking requests. Any future integration should use a mock service first,
keep credentials out of source control, and require human approval outside
explicitly configured limits.

## Website

`web/` is a React + TypeScript site (built with Vite) that lets you play with the rules in a browser:
change the limits, score a made-up event, replay a made-up morning of nine events, and try to
tamper with the audit log. The scoring, the policy and the audit chain are written a second time in
TypeScript, and the tests check that they give exactly the same numbers and hashes as the Python code
(`python scripts/export_parity.py` writes the reference values).

    cd web
    npm install
    npm run dev          # http://localhost:5173
    npm test

Optionally the site can call the Python code running on a server (`src/sar_scout/api.py`). Each
visitor gets a private, temporary sandbox with its own database and audit log, and the satellite
service behind it is a mock. To try it locally:

    SCOUT_ALLOWED_ORIGINS=http://localhost:5173 uvicorn sar_scout.api:app_from_env --factory --port 8000
    cd web && cp .env.example .env.local && npm run dev

The site is deployed on Vercel (folder `web`, variable `VITE_API_URL`) and the API on Railway (the
`Dockerfile`, variable `SCOUT_ALLOWED_ORIGINS`).

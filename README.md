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

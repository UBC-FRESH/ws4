==========================
Run an allowlisted command
==========================

The web console is a small, opt-in power-user surface. It composes one of five allowlisted
WS4 commands from typed fields and launches it as an argv array. It is **not** a shell, a
terminal, or a Python evaluator.

Enable it only on a trusted or loopback service:

.. code-block:: bash

   export WS4_CONSOLE_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
   ws4 serve --dataset build/compiled --runs runs --targets targets.yaml \
       --allow-console --console-root /path/to/instance --allow-runs

The token is required on every console endpoint as ``Authorization: Bearer <token>``.
The browser stores it in ``sessionStorage`` for the current tab; it is never placed in a
URL or written to an audit record. Without ``--allow-console`` the console API does not
exist and the browser does not show the **Console** workspace. ``--console-token`` may
also be supplied directly; the environment variable is preferred so the secret stays out
of the process argument list.

What is allowed
---------------

The console can launch these command families:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Command
     - Typed inputs
   * - ``simulate``
     - schedule CSV, years.
   * - ``optimize``
     - targets, initial schedule, years, iterations, time limit, seed, engine, islands,
       and LNS weights.
   * - ``state-watch``
     - targets, candidate index **or** candidate cache, initial schedule, seed state,
       years, iterations, period width, watched accounts, and LNS weights.
   * - ``gpu-run``
     - targets, seed schedule, effect table, cache directory, seeds, years, population,
       generations, and device.
   * - ``report``
     - an existing run directory and optional targets.

Every command writes into a fresh ``runs/console-<timestamp>-<id>/`` directory. The
console supplies ``--out``, ``--out-dir``, ``--json-out``, ``--schedule-out``, and
``--summary-out``; a caller cannot choose the output path. Artifacts are listed and
downloadable from the **Console** panel.

The console does not run ``ws4 serve``, package installation, arbitrary Python, raw
``bash``, pipes, redirection, command substitution, or network clients. Those remain
outside this tier; the Python sandbox is a separate, later boundary.

Security boundary
-----------------

* Requests are typed and unknown fields are rejected before launch.
* Inputs are resolved with ``strict=True`` and must stay inside the configured read-only
  roots. Path traversal, missing inputs, and unknown flags are rejected.
* Output paths are server-owned scratch paths.
* The child process is launched with ``shell=False``, a cleaned environment, and its own
  process group. There is no shell interpretation of any field.
* One job runs at a time by default; the sliding-window limit is six starts per minute.
* Each job has a 180-second wall clock limit and a one-megabyte captured-output limit.
  Exceeding either terminates the process group and marks the job failed.
* Each completed job appends one line to ``runs/console-audit.jsonl`` with the workspace,
  command, argv, dataset fingerprint, start/end time, exit status, and artifact paths.

The token is an access gate, not a multi-user account system. Run the service behind the
host's normal authentication and network controls. The allowlisted CLI tier does not
provide a kernel sandbox or network namespace; do not enable it on an untrusted public
host. That stronger boundary belongs to the Python job-runner tier.

Trying it in the browser
------------------------

**1. Open Console.** The workspace is visible only when the service exposes the feature.

**2. Enter the token** and select **Connect**. The command picker and typed fields load.

**3. Pick ``report``**, leave the newest run directory in the field, and select **Run job**.
The output appears in the Console panel, and the report CSV/JSON files appear under
**Artifacts**. A rejected field, such as a path outside the configured roots, returns a
validation message before any process starts.

From Python, the same contract is a JSON request:

.. code-block:: python

   import requests

   headers = {"Authorization": f"Bearer {token}"}
   response = requests.post(
       "http://127.0.0.1:8000/api/console/jobs",
       headers=headers,
       json={"command": "report", "run": "/srv/runs/run1"},
       timeout=10,
   )
   job = response.json()

Poll ``/api/console/jobs/{id}`` for status, ``/api/console/jobs/{id}/output?offset=N`` for
captured output, and ``/api/console/jobs/{id}/artifacts`` for the scratch files.

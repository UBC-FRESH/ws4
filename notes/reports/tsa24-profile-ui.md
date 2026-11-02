# TSA24 scenario-profile UI

Date: 2026-11-02
Status: complete

## Surface

The web service can now expose the P98 profile library:

```bash
ws4 serve \
  --dataset build/compiled \
  --runs runs \
  --targets targets.yaml \
  --scenario-profiles config/ws4/profiles/ltsy.yaml
```

The Targets tab gains a **Profile** selector and **Load profile** button. Applying a
profile validates its target file with the optimizer loader and replaces the configured
targets YAML, preserving the same backup and refusal behavior as the existing target
editor.

## API

- `GET /api/scenario-profiles`
- `GET /api/scenario-profiles/{name}`
- `POST /api/scenario-profiles/{name}/apply`

The list endpoint is machine-readable and is the contract for any future UI. Invalid
libraries or profiles return a named 404/422; applying without an editable targets path
returns 409.

## Safety

- The service still starts read-only unless targets and profile paths are explicitly
  configured.
- Apply only writes through the existing validated targets path.
- The UI disables the apply control under read-only skins.
- Unknown profile names do not write a target file.

## Tests

- Profile API list/detail/apply test.
- 404 for an unknown profile.
- Static shell test for the selector controls.
- Profile-library and CLI tests from P98.

## Limits

- The selector changes the target file; it does not start a GPU watcher.
- Profile edits are not part of the UI.
- The profile library remains an instance-owned YAML file.

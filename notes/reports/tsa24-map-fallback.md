# P113 map capability fallback

Date: 2026-11-03
Status: complete

## Change

`GET /api/summary` now reports `capabilities.geometry`. The browser uses that flag
to show an explicit **Map unavailable** panel when the service was started
without `--geometry`, and does not issue block-map requests in that state.

Direct map and geometry API calls keep their existing naming `404`; the server
contract is unchanged for API callers.

## TSA 24

The TSA 24 compiled dataset has no geometry layer. The portal now shows:

> Map unavailable — This dataset has no geometry layer. Configure `--geometry`
> to enable the block map.

No synthetic geometry is generated.

## Verification

- Focused web tests: `77 passed`
- `GET /api/summary` reports `capabilities.geometry: false` without geometry
- Map-unavailable panel is present in the browser shell

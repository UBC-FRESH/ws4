# P102 Ask overlay

Date: 2026-11-02
Status: complete

## Change

The WS4 web app no longer reserves a chat panel inside the sidebar. The assistant is now
opened from a compact **✦ Ask** pill in the header and rendered as a floating overlay.

- available from every workspace;
- closed by default;
- opens over the current workspace without changing it;
- closes with the overlay × button or Escape;
- focuses the input when opened;
- remains hidden when the agent is disabled or unavailable.

The existing `/api/chat`, session state, Markdown rendering, retry behavior, and action
chips are unchanged.

## Files

- `ws4/web/static/index.html`
- `ws4/web/static/app.js`
- `ws4/web/static/style.css`
- `tests/test_web.py`

## Validation

- static shell test asserts the Ask button, close control, and overlay position after
  `</main>`;
- stylesheet test asserts the pill and fixed-position overlay;
- existing web/chat tests remain green;
- dashboard is green.

## Limits

The remote `ws4.01101.dev` origin is managed outside this checkout and was not redeployed.
This change is in the repository and takes effect on the next service deployment.

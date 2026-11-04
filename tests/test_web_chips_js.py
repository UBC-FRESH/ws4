"""Behaviour tests for the browser chip handler without a browser build."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

APP = Path(__file__).resolve().parents[1] / "ws4" / "web" / "static" / "app.js"


def _run_handler(calls: str) -> list[list[object]]:
    """Run the extracted handler with deterministic UI mocks."""
    source = APP.read_text(encoding="utf-8")
    start = source.index("function applyChatChip(chip)")
    end = source.index("\nasync function sendChat", start)
    handler = source[start:end]
    script = f"""
const calls = [];
const inputs = {{}};
const state = {{ features: [{{ properties: {{ block_id: 'B-1' }} }}], selectedBlock: null }};
const $ = (id) => inputs[id] ??= {{ value: '', focus() {{ calls.push(['focus', id]); }} }};
function setWorkspace(value) {{ calls.push(['workspace', value]); }}
function setSubView(workspace, subview) {{ calls.push(['subview', workspace, subview]); }}
function setPeriod(value) {{ calls.push(['period', value]); }}
function showDetail(block) {{ calls.push(['block', block]); }}
function showToast(message, error) {{ calls.push(['toast', message, error]); }}
{handler}
{calls}
console.log(JSON.stringify(calls));
"""
    completed = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    # The Node harness emits a JSON array of call tuples.
    return cast("list[list[object]]", json.loads(completed.stdout))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_chip_handler_applies_only_safe_view_changes() -> None:
    """Workspace, subview, period, block, and prompt chips call the safe UI hooks."""
    calls = _run_handler(
        """
applyChatChip({ action: 'open_workspace', target: 'results' });
applyChatChip({ action: 'open_subview', target: 'data:carbon' });
applyChatChip({ action: 'set_period', target: '4' });
applyChatChip({ action: 'select_block', target: 'B-1' });
applyChatChip({ action: 'select_block', target: 'missing' });
applyChatChip({ action: 'ask', target: 'Explain the penalty.' });
calls.push(['ask-value', inputs['chat-input']?.value || '']);
"""
    )
    assert calls[:4] == [
        ["workspace", "results"],
        ["workspace", "data"],
        ["subview", "data", "carbon"],
        ["period", 4],
    ]
    assert ["workspace", "map"] in calls
    assert ["block", "B-1"] in calls
    assert any(call[0] == "toast" and call[2] is True for call in calls)
    assert ["focus", "chat-input"] in calls
    assert ["ask-value", "Explain the penalty."] in calls

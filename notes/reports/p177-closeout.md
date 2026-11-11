# P177 close-out: containment contract and validation protocol

Date: 2026-11-11
Phase: P177 (#1046)
Branch: `feature/p177-containment-protocol`
Pull request: #1050

## Outcome

Added a containment-mask input and defined the free-burn versus suppressed validation protocol.

## Decision

- Containment is a management scenario input, not a fitted parameter.
- Small CFSDS cases are suppression-dominated and are not ROS-skill evidence.
- Large/free-burn cases remain the ROS validation set.
- P176 basin evidence is the basis for this split.

## Limits

- No public containment time/line data were added.
- Containment masks must come from a scenario or external spatial layer.
- The default model remains free-burn.

## Verification

- Dashboard: GREEN.
- Containment contract tests green.
- No merge without maintainer approval.

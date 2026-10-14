# ADR 0008: Python first, with C++ kernels behind a stable API

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

The first prototypes of the core functions will be Python. Some hot loops (the annual simulation, and
neighbour scoring under a large search) may not meet the performance target in pure Python. Rewriting
the whole system in C++ up front would slow development and add a build and ABI surface before the
design is settled.

## Decision

Build the reference implementation in Python. Profile it, and move only the measured bottleneck kernels
to C++ behind a stable Python API (pybind11 or nanobind), with a NumPy buffer interface. Keep the
operator and metaheuristic interfaces free of Python-only types so a C++ kernel is a drop-in
replacement.

## Consequences

- Development stays fast while the design is fluid.
- Performance work is evidence-driven: a kernel moves to C++ only when profiling justifies it.
- A C++ kernel introduces a build toolchain, wheels, and an ABI surface that must be maintained.
- The interfaces must be disciplined enough that Python and C++ kernels are interchangeable.

## Alternatives considered

- **C++ from the start.** Rejected: premature, and it slows the design and test loop.
- **Python only, with no extension path.** Rejected: it risks a hard performance ceiling.
- **A separate GPU/C++ codebase.** Rejected: two implementations of the model would drift.

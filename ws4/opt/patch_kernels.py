"""Native kernels for the incremental patch state.

numba is an optional dependency (the ``opt`` extra). When it is installed the two component
relabels — the whole state at reset, and the components touched by a bulk move — run as ``njit``
kernels over CSR adjacency; otherwise the same loops run in Python. Both paths compute the same
thing, and the state is held to exact parity with the from-scratch computation by the
``test_patch_state`` suite.

Component ids are written into ``comp`` as ``base + c``, so the caller can allocate them from its
own counter without a second pass, and the per-component area, perimeter and member count come back
in the output arrays.
"""

from __future__ import annotations

import numpy as np

try:  # pragma: no cover - which branch runs depends on the environment
    from numba import njit

    HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    HAVE_NUMBA = False

    def njit(*args: object, **kwargs: object) -> object:  # type: ignore[no-redef]
        """Stand in for :func:`numba.njit` when numba is absent."""

        def wrap(func: object) -> object:
            return func

        if args and callable(args[0]):
            return args[0]
        return wrap


@njit(cache=True, fastmath=True)
def label_all(
    ptr: np.ndarray,
    indices: np.ndarray,
    lengths: np.ndarray,
    areas: np.ndarray,
    member: np.ndarray,
    value: np.ndarray,
    comp: np.ndarray,
    base: int,
    stack: np.ndarray,
    area_out: np.ndarray,
    perim_out: np.ndarray,
    count_out: np.ndarray,
) -> int:
    """Label every member component, writing ``base + c`` into ``comp``.

    Parameters
    ----------
    ptr, indices, lengths : numpy.ndarray
        The CSR adjacency: offsets, neighbour indices, and shared boundary lengths.
    areas : numpy.ndarray
        The block area per node.
    member : numpy.ndarray
        Non-zero for a member block.
    value : numpy.ndarray
        The criterion value per node.
    comp : numpy.ndarray
        The component id per node, written here.
    base : int
        The first component id to allocate.
    stack : numpy.ndarray
        Scratch, at least as long as the node count.
    area_out, perim_out, count_out : numpy.ndarray
        Scratch, at least as long as the node count, written per component.

    Returns
    -------
    int
        The number of components.
    """
    n = member.size
    for i in range(n):
        comp[i] = -1
    count = 0
    for start in range(n):
        if member[start] == 0 or comp[start] != -1:
            continue
        cid = base + count
        area = 0.0
        perim = 0.0
        members = 0
        sp = 0
        stack[sp] = start
        sp += 1
        comp[start] = cid
        while sp > 0:
            sp -= 1
            node = stack[sp]
            members += 1
            area += value[node] * areas[node]
            for e in range(ptr[node], ptr[node + 1]):
                other = indices[e]
                if member[other] == 1:
                    if comp[other] == -1:
                        comp[other] = cid
                        stack[sp] = other
                        sp += 1
                else:
                    perim += lengths[e]
        area_out[count] = area
        perim_out[count] = perim
        count_out[count] = members
        count += 1
    return count


@njit(cache=True, fastmath=True)
def label_from_seeds(
    ptr: np.ndarray,
    indices: np.ndarray,
    lengths: np.ndarray,
    areas: np.ndarray,
    member: np.ndarray,
    value: np.ndarray,
    comp: np.ndarray,
    changed: np.ndarray,
    base: int,
    stack: np.ndarray,
    walk: np.ndarray,
    visited: np.ndarray,
    gen: int,
    area_out: np.ndarray,
    perim_out: np.ndarray,
    count_out: np.ndarray,
) -> int:
    """Relabel the components holding a changed block or one of its member neighbours.

    The seeds are the changed blocks that are members plus their member neighbours, so every
    component the change can touch is walked. ``visited`` is a generation stamp: nodes queued as
    seeds carry ``gen`` and nodes already walked carry ``gen + 1``, so the caller only has to
    advance ``gen`` by two between calls.

    Parameters
    ----------
    ptr, indices, lengths : numpy.ndarray
        The CSR adjacency.
    areas : numpy.ndarray
        The block area per node.
    member : numpy.ndarray
        Non-zero for a member block, after the change has been applied.
    value : numpy.ndarray
        The criterion value per node, after the change has been applied.
    comp : numpy.ndarray
        The component id per node, written here.
    changed : numpy.ndarray
        The dense indices of the changed blocks.
    base : int
        The first component id to allocate.
    stack, walk, visited : numpy.ndarray
        Scratch, at least as long as the node count.
    gen : int
        The generation stamp; must exceed any value left in ``visited``.
    area_out, perim_out, count_out : numpy.ndarray
        Scratch, at least as long as the node count, written per rebuilt component.

    Returns
    -------
    int
        The number of rebuilt components.
    """
    seeds = 0
    for k in range(changed.size):
        block = changed[k]
        if member[block] == 1 and visited[block] != gen:
            visited[block] = gen
            stack[seeds] = block
            seeds += 1
        for e in range(ptr[block], ptr[block + 1]):
            other = indices[e]
            if member[other] == 1 and visited[other] != gen:
                visited[other] = gen
                stack[seeds] = other
                seeds += 1
    count = 0
    for s in range(seeds):
        start = stack[s]
        if visited[start] == gen + 1:
            continue
        cid = base + count
        area = 0.0
        perim = 0.0
        members = 0
        sp = 0
        walk[sp] = start
        sp += 1
        visited[start] = gen + 1
        while sp > 0:
            sp -= 1
            node = walk[sp]
            comp[node] = cid
            members += 1
            area += value[node] * areas[node]
            for e in range(ptr[node], ptr[node + 1]):
                other = indices[e]
                if member[other] == 1:
                    if visited[other] != gen + 1:
                        visited[other] = gen + 1
                        walk[sp] = other
                        sp += 1
                else:
                    perim += lengths[e]
        area_out[count] = area
        perim_out[count] = perim
        count_out[count] = members
        count += 1
    return count

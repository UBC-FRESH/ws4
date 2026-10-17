#!/usr/bin/env python3
"""Audit public API docstrings against the signatures they document.

``AGENTS.md`` requires every public function, method, property, and class to carry a numpy-style
docstring whose parameters and return value match the annotations. The Sphinx build catches a broken
reference, but it does not notice a missing ``Parameters`` section or a sentence the code has
outgrown, so the drift is invisible until someone reads the page. This audit closes that gap and
runs as its own gate in ``scripts/dashboard.py``. It covers the ``ws4`` package and the modules in
``scripts/``.

The rules are the repository's conventions::

    the docstring exists;
    every parameter is documented, and nothing else is;
    a callable that returns a value has a Returns section;
    a section header is preceded by a blank line.

``numpydoc`` enforces these rules on the scripts through ``tests/test_api_docstrings.py``. This
audit covers the package, where a library cannot know two of the repository's conventions: a
dataclass, a pydantic model, or a plain class documents its constructor arguments under
``Attributes`` rather than ``Parameters``, and a ``Protocol``'s constructor signature is not its
own. A parameter whose name starts with an underscore is a private detail and is not required, and
``*args`` or ``**kwargs`` may be left undocumented. The command-line module is skipped: a Typer
command's docstring is its help text, and its parameters come from the option decorators.

Command-line usage::

    python scripts/doc_audit.py [--package PACKAGE] [--scripts-dir DIR]

The exit status is 0 when every public docstring is complete.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import pkgutil
import re
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

PACKAGE: Final[str] = "ws4"
SCRIPTS_DIR: Final[Path] = Path(__file__).resolve().parent
SKIPPED_MODULES: Final[frozenset[str]] = frozenset({"ws4.cli"})
PARAMETER_SECTIONS: Final[tuple[str, ...]] = ("Parameters", "Other Parameters", "Attributes")
CALL_SECTIONS: Final[tuple[str, ...]] = ("Parameters", "Other Parameters")
RETURN_SECTIONS: Final[tuple[str, ...]] = ("Returns", "Yields")
SECTION_HEADERS: Final[frozenset[str]] = frozenset(
    {
        "Parameters",
        "Other Parameters",
        "Attributes",
        "Returns",
        "Yields",
        "Raises",
        "Warns",
        "Notes",
        "Examples",
        "See Also",
        "References",
    }
)
IGNORED_PARAMETERS: Final[frozenset[str]] = frozenset({"self", "cls"})
ENTRY: Final[re.Pattern[str]] = re.compile(
    r"^(\s*)([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*:\s*(.*)$"
)


@dataclass(frozen=True)
class Finding:
    """One incomplete docstring.

    Attributes
    ----------
    code : str
        The stable code: ``IMPORT``, ``MISSING``, ``PARAMS``, ``STALE``, ``RETURNS``, or
        ``SECTION``.
    name : str
        The qualified name of the object, or the module that could not be imported.
    detail : str
        What is wrong, as a sentence.
    """

    code: str
    name: str
    detail: str

    def render(self) -> str:
        """Return the finding as one line.

        Returns
        -------
        str
            The finding, formatted ``CODE name: detail``.
        """
        return f"{self.code} {self.name}: {self.detail}"


def section_lines(doc: str) -> list[str]:
    """Return a docstring's lines, with tabs expanded.

    Parameters
    ----------
    doc : str
        The docstring.

    Returns
    -------
    list of str
        The lines.
    """
    return doc.expandtabs(4).splitlines()


def header_indexes(lines: Sequence[str]) -> list[int]:
    """Return the indexes of the numpy section headers in a docstring.

    Parameters
    ----------
    lines : sequence of str
        The docstring's lines.

    Returns
    -------
    list of int
        The indexes of the headers, in order.
    """
    return [
        index
        for index, line in enumerate(lines)
        if line.strip() in SECTION_HEADERS
        and index + 1 < len(lines)
        and set(lines[index + 1].strip()) == {"-"}
    ]


def has_section(doc: str, *names: str) -> bool:
    """Return whether a docstring has one of the named numpy sections.

    Parameters
    ----------
    doc : str
        The docstring.
    *names : str
        The section names to look for, such as ``"Returns"``.

    Returns
    -------
    bool
        True when a name is a header, underlined on the next line.
    """
    lines = section_lines(doc)
    return any(lines[index].strip() in names for index in header_indexes(lines))


def section_entries(doc: str, name: str) -> tuple[str, ...]:
    """Return the entry names under one numpy docstring section.

    An entry is a line at the section's entry indent of the form ``name : type``. A wrapped
    description is indented further and is not an entry.

    Parameters
    ----------
    doc : str
        The docstring.
    name : str
        The section name, such as ``"Parameters"``.

    Returns
    -------
    tuple of str
        The documented names, in order, with comma-separated names split.
    """
    lines = section_lines(doc)
    headers = header_indexes(lines)
    starts = [index for index in headers if lines[index].strip() == name]
    entries: list[str] = []
    for start in starts:
        stop = next((index for index in headers if index > start), len(lines))
        entry_indent: int | None = None
        for line in lines[start + 2 : stop]:
            stripped = line.strip()
            if not stripped or set(stripped) == {"-"}:
                continue
            indent = len(line) - len(line.lstrip())
            match = ENTRY.match(line)
            if entry_indent is None:
                if match is None:
                    break
                entry_indent = indent
            elif indent < entry_indent:
                break
            if indent == entry_indent and match is not None:
                entries.extend(part.strip() for part in match.group(2).split(","))
    return tuple(entries)


def documented_names(doc: str) -> tuple[str, ...]:
    """Return every name documented under a parameter-like section.

    Parameters
    ----------
    doc : str
        The docstring.

    Returns
    -------
    tuple of str
        The union of the ``Parameters``, ``Other Parameters``, and ``Attributes`` entries.
    """
    names: list[str] = []
    for section in PARAMETER_SECTIONS:
        names.extend(section_entries(doc, section))
    return tuple(names)


def parameter_entries(doc: str) -> tuple[str, ...]:
    """Return the names a docstring offers as call parameters.

    ``Attributes`` is excluded: a class documents its attributes there, and an instance attribute
    that is not a constructor argument is not a stale parameter.

    Parameters
    ----------
    doc : str
        The docstring.

    Returns
    -------
    tuple of str
        The ``Parameters`` and ``Other Parameters`` entries.
    """
    names: list[str] = []
    for section in CALL_SECTIONS:
        names.extend(section_entries(doc, section))
    return tuple(names)


def section_findings(name: str, doc: str) -> list[Finding]:
    """Check that every section header is preceded by a blank line.

    A header that follows a description line is read as part of it, so the section is lost.

    Parameters
    ----------
    name : str
        The qualified name, used in the findings.
    doc : str
        The docstring.

    Returns
    -------
    list of Finding
        One finding per misplaced header.
    """
    lines = section_lines(doc)
    return [
        Finding("SECTION", name, f"the {lines[index].strip()} section needs a blank line before it")
        for index in header_indexes(lines)
        if index > 0 and lines[index - 1].strip()
    ]


def signature_of(obj: object) -> inspect.Signature | None:
    """Return an object's signature, or None when it cannot be inspected.

    ``inspect.signature`` is typed for callables, but the audit also inspects classes and instances
    whose type decides whether a signature exists at all, so the argument is cast.

    Parameters
    ----------
    obj : object
        The function, method, class, or instance.

    Returns
    -------
    inspect.Signature or None
        The signature, or None for an object the ``inspect`` module cannot describe.
    """
    try:
        return inspect.signature(cast("Callable[..., object]", obj))
    except (TypeError, ValueError):
        return None


def signature_parameters(obj: object) -> list[inspect.Parameter] | None:
    """Return a callable's parameters, or None when it has no inspectable signature.

    Parameters
    ----------
    obj : object
        The function, method, or class.

    Returns
    -------
    list of inspect.Parameter or None
        The parameters, or None for an object the ``inspect`` module cannot describe.
    """
    signature = signature_of(obj)
    return None if signature is None else list(signature.parameters.values())


def returns_value(obj: object) -> bool:
    """Return whether an annotated callable returns a value worth documenting.

    Parameters
    ----------
    obj : object
        The function, method, or property accessor.

    Returns
    -------
    bool
        True when the return annotation is present and is not None.
    """
    signature = signature_of(obj)
    if signature is None:
        return False
    annotation = signature.return_annotation
    if annotation is inspect.Signature.empty:
        return getattr(obj, "__name__", "") not in {"__init__", "__post_init__"}
    return str(annotation) not in {"None", "NoneType"}


def parameter_findings(
    name: str,
    parameters: Sequence[inspect.Parameter],
    documented: Sequence[str],
    entries: Sequence[str],
) -> list[Finding]:
    """Compare a signature's parameters with the ones a docstring documents.

    Parameters
    ----------
    name : str
        The qualified name, used in the findings.
    parameters : sequence of inspect.Parameter
        The parameters of the signature.
    documented : sequence of str
        Every name the docstring documents, including attributes.
    entries : sequence of str
        The names documented as call parameters.

    Returns
    -------
    list of Finding
        One finding per direction when the two disagree.
    """
    required: list[str] = []
    allowed: set[str] = set()
    for parameter in parameters:
        if parameter.name in IGNORED_PARAMETERS or parameter.name.startswith("_"):
            continue
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            allowed.update({parameter.name, f"*{parameter.name}"})
        elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
            allowed.update({parameter.name, f"**{parameter.name}"})
        else:
            required.append(parameter.name)
            allowed.add(parameter.name)
    findings: list[Finding] = []
    missing = [parameter for parameter in required if parameter not in documented]
    if missing:
        findings.append(Finding("PARAMS", name, f"parameters not documented: {', '.join(missing)}"))
    stale = [entry for entry in entries if entry not in allowed]
    if stale:
        findings.append(
            Finding(
                "STALE", name, f"documented parameters not in the signature: {', '.join(stale)}"
            )
        )
    return findings


def check_object(name: str, obj: object) -> list[Finding]:
    """Check one public object's docstring against its signature.

    Parameters
    ----------
    name : str
        The qualified name, used in the findings.
    obj : object
        The function, method, property, or class.

    Returns
    -------
    list of Finding
        The findings; empty when the docstring is complete.
    """
    doc = inspect.getdoc(obj) or ""
    if not doc:
        return [Finding("MISSING", name, "has no docstring")]
    findings = section_findings(name, doc)
    if not getattr(obj, "_is_protocol", False):
        parameters = signature_parameters(obj)
        if parameters is not None:
            findings.extend(
                parameter_findings(name, parameters, documented_names(doc), parameter_entries(doc))
            )
    if not inspect.isclass(obj) and returns_value(obj) and not has_section(doc, *RETURN_SECTIONS):
        findings.append(Finding("RETURNS", name, "returns a value but has no Returns section"))
    return findings


def member_findings(owner: str, view: type) -> list[Finding]:
    """Check the public methods and properties of a class.

    Parameters
    ----------
    owner : str
        The qualified class name.
    view : type
        The class whose members are checked.

    Returns
    -------
    list of Finding
        The findings for its members.
    """
    findings: list[Finding] = []
    for attribute, member in vars(view).items():
        if attribute.startswith("_"):
            continue
        target: Any = None
        if inspect.isfunction(member):
            target = member
        elif isinstance(member, (staticmethod, classmethod)):
            target = member.__func__
        elif isinstance(member, property):
            target = member.fget
        if target is not None:
            findings.extend(check_object(f"{owner}.{attribute}", target))
    return findings


def module_qualnames(package: str, scripts_dir: Path | None) -> Iterator[str]:
    """Yield the importable name of every module in an audit's scope.

    Parameters
    ----------
    package : str
        The importable package name.
    scripts_dir : Path or None
        A directory of standalone modules, such as ``scripts/``.

    Yields
    ------
    str
        Each module name, the package and its submodules first, then the standalone modules.
    """
    root = importlib.import_module(package)
    yield package
    found = pkgutil.walk_packages(root.__path__, f"{package}.")
    yield from (info.name for info in sorted(found, key=lambda info: info.name))
    if scripts_dir is not None:
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        yield from (
            path.stem for path in sorted(scripts_dir.glob("*.py")) if path.stem != "__init__"
        )


def module_findings(name: str) -> list[Finding]:
    """Audit one module's public objects.

    Parameters
    ----------
    name : str
        The importable module name.

    Returns
    -------
    list of Finding
        The findings, ordered by definition.
    """
    try:
        module = importlib.import_module(name)
    except Exception as exc:  # report the failure, do not stop the audit
        return [Finding("IMPORT", name, f"cannot be imported: {exc}")]
    findings: list[Finding] = []
    if not (inspect.getdoc(module) or "").strip():
        findings.append(Finding("MISSING", name, "the module has no docstring"))
    for attribute, obj in vars(module).items():
        if attribute.startswith("_") or getattr(obj, "__module__", None) != name:
            continue
        qualified = f"{name}.{attribute}"
        if inspect.isfunction(obj) or inspect.isclass(obj):
            findings.extend(check_object(qualified, obj))
        if inspect.isclass(obj):
            findings.extend(member_findings(qualified, obj))
    return findings


def audit(package: str = PACKAGE, scripts_dir: Path | None = SCRIPTS_DIR) -> list[Finding]:
    """Audit every public object in a package and a directory of standalone modules.

    Parameters
    ----------
    package : str, optional
        The importable package name. Defaults to ``"ws4"``.
    scripts_dir : Path or None, optional
        A directory of standalone modules, or None to skip them. Defaults to ``scripts/``.

    Returns
    -------
    list of Finding
        The findings, ordered by module and then by definition order.
    """
    findings: list[Finding] = []
    for name in module_qualnames(package, scripts_dir):
        if name in SKIPPED_MODULES:
            continue
        findings.extend(module_findings(name))
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    """Run the audit and report the findings.

    Parameters
    ----------
    argv : sequence of str or None, optional
        The command-line arguments. None reads ``sys.argv``.

    Returns
    -------
    int
        The exit status: 0 when every public docstring is complete, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        description="Audit public docstrings against their signatures."
    )
    parser.add_argument("--package", default=PACKAGE, help="the importable package to audit")
    parser.add_argument(
        "--scripts-dir",
        type=Path,
        default=SCRIPTS_DIR,
        help="a directory of standalone modules to audit, such as scripts/",
    )
    arguments = parser.parse_args(argv)
    findings = audit(arguments.package, arguments.scripts_dir)
    for finding in findings:
        print(finding.render())
    if findings:
        print(f"{len(findings)} incomplete docstring(s)")
        return 1
    print(f"{arguments.package} and {arguments.scripts_dir}: every public docstring is complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())

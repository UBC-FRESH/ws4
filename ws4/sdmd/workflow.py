"""FreshForge provider for the SDMD atlas digitisation workflow.

The provider exposes four node types:

``ws4.sdmd.render``
    Render the source PDF page with figrecover.
``ws4.sdmd.extract``
    Extract vector isopleths from the PDF with :mod:`ws4.sdmd.digitise`.
``ws4.sdmd.overlay``
    Draw the stored curves over the rendered page with figrecover QA.
``ws4.sdmd.review``
    Write a figrecover review manifest.

FreshForge is an optional dependency. Import this module only when the
``digitise`` extra is installed.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from .digitise import calibrate_axes, load_spec, read_labelled_curves, write_diagram
from .review import overlay_diagram, render_pdf_page, write_review_manifest

__all__ = ["SdmdProvider", "sdmd_provider"]


class SdmdProvider:
    """FreshForge provider for the four SDMD digitisation nodes."""

    def metadata(self) -> object:
        """Return the provider and node-type metadata.

        Returns
        -------
        object
            A FreshForge ``ProviderMetadata`` record.
        """
        from freshforge.providers import NodeTypeMetadata, ProviderMetadata

        return ProviderMetadata(
            id="ws4.sdmd",
            version="1.0",
            name="WS4 SDMD digitisation",
            description="Render, extract, overlay, and review SDMD diagrams.",
            node_types=(
                NodeTypeMetadata(
                    id="render",
                    name="Render PDF page",
                    inputs=(),
                    outputs=("image",),
                    parameters=("pdf", "out", "dpi"),
                ),
                NodeTypeMetadata(
                    id="extract",
                    name="Extract vector isopleths",
                    inputs=(),
                    outputs=("diagram",),
                    parameters=("spec", "out"),
                ),
                NodeTypeMetadata(
                    id="overlay",
                    name="Overlay recovered curves",
                    inputs=(),
                    outputs=("overlay",),
                    parameters=("spec", "diagram", "image", "out", "dpi"),
                ),
                NodeTypeMetadata(
                    id="review",
                    name="Write review manifest",
                    inputs=(),
                    outputs=("review",),
                    parameters=("diagram", "overlay", "out", "status"),
                ),
                NodeTypeMetadata(
                    id="import-lines",
                    name="Import a labelled curve family",
                    inputs=(),
                    outputs=("family",),
                    parameters=(
                        "pdf",
                        "dash",
                        "width",
                        "unit",
                        "kind",
                        "x_ticks",
                        "y_ticks",
                        "out",
                    ),
                ),
            ),
        )

    def validate_node(
        self,
        node: object,
        node_type: object,
        *,
        location: str,
    ) -> Sequence[object]:
        """Check the required parameters for one node.

        Parameters
        ----------
        node : object
            The FreshForge workflow node.
        node_type : object
            The provider node-type metadata.
        location : str
            Diagnostic location label.

        Returns
        -------
        sequence of object
            FreshForge diagnostics; empty when the node is valid.
        """
        from freshforge.records import Diagnostic, DiagnosticSeverity

        required = {
            "render": ("pdf", "out"),
            "extract": ("spec", "out"),
            "overlay": ("spec", "diagram", "image", "out"),
            "review": ("diagram", "overlay", "out"),
            "import-lines": (
                "pdf",
                "dash",
                "width",
                "unit",
                "kind",
                "x_ticks",
                "y_ticks",
                "out",
            ),
        }
        node_id = str(getattr(node_type, "id", ""))
        parameters = getattr(node, "parameters", {})
        if not isinstance(parameters, dict):
            parameters = {}
        missing = [key for key in required.get(node_id, ()) if key not in parameters]
        if not missing:
            return ()
        return (
            Diagnostic(
                severity=DiagnosticSeverity.ERROR,
                code="ws4.sdmd.parameter.missing",
                message="missing parameters: " + ", ".join(missing),
                location=location,
            ),
        )

    def run_node(self, node: object, node_type: object, *, context: object) -> object:
        """Execute one SDMD node.

        Parameters
        ----------
        node : object
            The FreshForge workflow node.
        node_type : object
            The provider node-type metadata.
        context : object
            The FreshForge run context.

        Returns
        -------
        object
            A FreshForge ``ProviderRunResult``.
        """
        from freshforge.records import ProviderRunResult, RunStatus

        params = _parameters(node)
        resolve = getattr(context, "resolve_path", None)
        if not callable(resolve):
            raise ValueError("the FreshForge context has no resolve_path method")
        node_id = str(getattr(node_type, "id", ""))
        if node_id == "render":
            image = render_pdf_page(
                resolve(str(params["pdf"])),
                resolve(str(params["out"])),
                dpi=int(str(params.get("dpi", 300))),
            )
            return ProviderRunResult(
                status=RunStatus.SUCCESS,
                outputs={"image": str(image)},
                artifacts={"image": str(image)},
            )
        if node_id == "extract":
            diagram = resolve(str(params["out"]))
            write_diagram(load_spec(resolve(str(params["spec"]))), diagram)
            return ProviderRunResult(
                status=RunStatus.SUCCESS,
                outputs={"diagram": str(diagram)},
                artifacts={"diagram": str(diagram)},
            )
        if node_id == "overlay":
            overlay = overlay_diagram(
                resolve(str(params["diagram"])),
                resolve(str(params["spec"])),
                resolve(str(params["image"])),
                resolve(str(params["out"])),
                dpi=int(str(params.get("dpi", 300))),
            )
            return ProviderRunResult(
                status=RunStatus.SUCCESS,
                outputs={"overlay": str(overlay)},
                artifacts={"overlay": str(overlay)},
            )
        if node_id == "review":
            review = write_review_manifest(
                resolve(str(params["diagram"])),
                resolve(str(params["overlay"])),
                resolve(str(params["out"])),
                status=str(params.get("status", "needs_review")),
            )
            return ProviderRunResult(
                status=RunStatus.SUCCESS,
                outputs={"review": str(review)},
                artifacts={"review": str(review)},
            )
        if node_id == "import-lines":
            output = resolve(str(params["out"]))
            output.parent.mkdir(parents=True, exist_ok=True)
            calibration = calibrate_axes(
                _tick_pairs(params["x_ticks"], "x_ticks"),
                _tick_pairs(params["y_ticks"], "y_ticks"),
            )
            curves = read_labelled_curves(
                resolve(str(params["pdf"])),
                dash=str(params["dash"]),
                width=float(str(params["width"])),
                unit=str(params["unit"]),
                calibration=calibration,
            )
            payload = {
                "schema_version": "ws4.sdmd.line-import.v1",
                "source_pdf": str(resolve(str(params["pdf"]))),
                "kind": str(params["kind"]),
                "dash": str(params["dash"]),
                "width": float(str(params["width"])),
                "unit": str(params["unit"]),
                "curves": [
                    {
                        "value": curve.value,
                        "path_index": curve.path_index,
                        "label_distance": curve.label_distance,
                        "points": [list(point) for point in curve.points],
                    }
                    for curve in curves
                ],
            }
            output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return ProviderRunResult(
                status=RunStatus.SUCCESS,
                outputs={"family": str(output)},
                artifacts={"family": str(output)},
            )
        raise ValueError(f"unknown WS4 SDMD node type {node_id!r}")


def sdmd_provider() -> SdmdProvider:
    """Return the FreshForge provider factory.

    Returns
    -------
    SdmdProvider
        A new provider instance.
    """
    return SdmdProvider()


def _tick_pairs(value: object, name: str) -> tuple[tuple[float, float], ...]:
    """Parse a workflow calibration tick list.

    Parameters
    ----------
    value : object
        A list of ``[value, position]`` pairs.
    name : str
        The parameter name, used in a diagnostic.

    Returns
    -------
    tuple of tuple of float
        The parsed pairs.

    Raises
    ------
    ValueError
        If the value is not a list of two-number pairs.
    """
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list of [value, position] pairs")
    pairs: list[tuple[float, float]] = []
    for item in value:
        if not isinstance(item, list | tuple) or len(item) != 2:
            raise ValueError(f"{name} must be a list of [value, position] pairs")
        pairs.append((float(item[0]), float(item[1])))
    return tuple(pairs)


def _parameters(node: object) -> dict[str, object]:
    """Return a workflow node's parameter mapping.

    Parameters
    ----------
    node : object
        A FreshForge workflow node.

    Returns
    -------
    dict of str to object
        The node parameters.

    Raises
    ------
    ValueError
        If the node has no parameter mapping.
    """
    parameters = getattr(node, "parameters", None)
    if not isinstance(parameters, dict):
        raise ValueError("the FreshForge node has no parameter mapping")
    return {str(key): value for key, value in parameters.items()}

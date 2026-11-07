# SDMD digitisation workflow

`sdmd-digitise.yaml` is a FreshForge workflow for one public SDMD PDF:

1. `render` renders the page with `figrecover`.
2. `extract` reads the vector isopleths with `ws4.sdmd.digitise`.
3. `overlay` draws the curves over the rendered page with `figrecover.qa`.
4. `review` writes a `figrecover` review manifest.

`sdmd-line-import.yaml` is the locked line-type workflow for the fdcp
top-height family. It renders the source with `figrecover`, then
`ws4.sdmd.import-lines` matches printed labels to the `[ 3 2 ]` paths and writes
a `ws4.sdmd.line-import.v1` artifact with the value, path index, label distance,
and ordered points for every curve. Ambiguous, distant, duplicate, or unordered
matches fail the node instead of being guessed.

Install the optional tools:

```bash
python -m pip install -e '.[digitise]'
```

Copy a public PDF and a diagram spec into `workflows/data/`, then plan and run:

```bash
freshforge plan workflows/sdmd-digitise.yaml
freshforge run workflows/sdmd-digitise.yaml --json
```

The spec is the review decision: it names the PDF axis ticks, the drawing path
indices, and the printed isopleth values. The workflow does not guess them.

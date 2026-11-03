# SDMD digitisation workflow

`sdmd-digitise.yaml` is a FreshForge workflow for one public SDMD PDF:

1. `render` renders the page with `figrecover`.
2. `extract` reads the vector isopleths with `ws4.sdmd.digitise`.
3. `overlay` draws the curves over the rendered page with `figrecover.qa`.
4. `review` writes a `figrecover` review manifest.

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

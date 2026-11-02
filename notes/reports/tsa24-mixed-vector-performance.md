# P97 mixed-target vector performance

Date: 2026-11-02
Status: complete; PR #695

## Result

The P89 mixed feature/product target has 11 factorized cells. Under the P95 vector path it
is no longer dominated by the padded-layout recomputation.

| Measurement | P89 padded path | P97 vector path |
|---|---:|---:|
| Target-switch evaluation | 4.53 s | **0.397 s** |
| Two-generation run | 14.86 s | **0.315 s** |
| Evaluations per second | 12.9 | **609** |

- exact objective error: **9.8e-13**
- sparse table cells unchanged: **200 → 200**
- factorized cells: 11
- GPU peak: **20.15 GB**
- wall including startup: **130.7 s**
- population construction/startup: 37.0 s

The vector path caches one `[options]` value vector per target cell and gathers it through
the candidate rows. That removes the repeated `[genomes, blocks, fragments, segments]`
intermediate for each generation.

The higher GPU peak is expected: eleven cached vectors (ten product cells and the feature
stock cell) take about 2.2 GB on top of the table and padded layout.

## Conclusion

The P95 one-cell speedup generalizes to a multi-account target. The multi-account target
switch is also much cheaper, which is the path the live watcher needs.

## Archive

```text
/srv/shared-data/gep/ws4/archive/tsa24-ltsy-mixed-vector/
```

Contains the measured record, runner, target, implementation snapshot, and checksums.

## Pull request

PR #695 contains the runner change, benchmark report, and planning updates. The archive is outside git.

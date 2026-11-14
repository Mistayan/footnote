# Benchmark environment snapshots

Captured locally on 2026-11-13, while the sequential benchmark was running. Each text file lists installed distribution names and versions from that environment's Python metadata:

- `lab.txt`: model gates, sweeps and model timing.
- `mem0.txt`: mem0 competitor adapter.
- `cognee.txt`: Cognee competitor adapter.
- `dbbake.txt`: storage controls and the matched LanceDB experiment.

These are version snapshots, not wheel-hash locks or cross-platform install guarantees. They do not capture the bytes of downloaded model weights. The lab weights have their own `../models.lock.json`; the competitor receipts currently name their embedders and library versions but do not include equivalent per-file model hashes. Preserve that limitation when reporting reproducibility.

# Resident query encoding

Encoding only, no retrieval or query cache. Same fixed dev queries per corpus for every model.

| Dataset | Model | Queries | Dimensions | p50 ms | p95 ms | Model files MiB |
|---|---|---:|---:|---:|---:|---:|
| scifact | bekko-a8m | 100 | 384 | 1.03 | 1.339 | 156.84 |
| nfcorpus | bekko-a8m | 100 | 384 | 0.509 | 0.697 | 156.84 |
| alloprof | bekko-a8m | 100 | 384 | 1.297 | 2.968 | 156.84 |
| mix-fr-en | bekko-a8m | 100 | 384 | 1.263 | 3.074 | 156.84 |
| scifact | gte-small | 100 | 384 | 2.01 | 2.664 | 33.12 |
| nfcorpus | gte-small | 100 | 384 | 1.032 | 1.335 | 33.12 |
| alloprof | gte-small | 100 | 384 | 2.913 | 5.657 | 33.12 |
| mix-fr-en | gte-small | 100 | 384 | 2.872 | 5.369 | 33.12 |
| scifact | embeddinggemma-300m | 100 | 768 | 11.926 | 13.96 | 1197.17 |
| nfcorpus | embeddinggemma-300m | 100 | 768 | 9.279 | 10.518 | 1197.17 |
| alloprof | embeddinggemma-300m | 100 | 768 | 14.212 | 30.849 | 1197.17 |
| mix-fr-en | embeddinggemma-300m | 100 | 768 | 14.332 | 30.755 | 1197.17 |
| scifact | harrier-270m | 100 | 640 | 12.039 | 13.905 | 1074.27 |
| nfcorpus | harrier-270m | 100 | 640 | 9.426 | 10.638 | 1074.27 |
| alloprof | harrier-270m | 100 | 640 | 14.48 | 30.89 | 1074.27 |
| mix-fr-en | harrier-270m | 100 | 640 | 14.276 | 29.665 | 1074.27 |
| scifact | granite-small-en-r2 | 100 | 384 | 3.718 | 4.795 | 188.02 |
| nfcorpus | granite-small-en-r2 | 100 | 384 | 2.279 | 2.937 | 188.02 |
| alloprof | granite-small-en-r2 | 100 | 384 | 4.707 | 11.641 | 188.02 |
| mix-fr-en | granite-small-en-r2 | 100 | 384 | 4.727 | 10.923 | 188.02 |
| scifact | arctic-m-v2 | 100 | 768 | 11.359 | 14.034 | 1185.59 |
| nfcorpus | arctic-m-v2 | 100 | 768 | 7.721 | 11.57 | 1185.59 |
| alloprof | arctic-m-v2 | 100 | 768 | 12.791 | 26.721 | 1185.59 |
| mix-fr-en | arctic-m-v2 | 100 | 768 | 12.918 | 27.7 | 1185.59 |

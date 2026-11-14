# Model candidate dev results

Tuning results only. These are not end-to-end latency measurements or heldout confirmation.


### scifact (dev)  (809 queries)

| Config | nDCG@10 | Recall@10 | MRR@10 | vs best | Chunks | Embed s |
|---|---|---|---|---|---|---|
| research:models · M1 embeddinggemma-300m dense only | 0.9012 | 0.9810 | 0.8775 | +0.0000 | 5183 | 449 |
| research:models · M4 embeddinggemma-300m 256 dims alone in the hybrid | 0.8541 | 0.9692 | 0.8184 | -0.0471 | 5183 | 0 |
| research:models · M2 embeddinggemma-300m alone in the hybrid | 0.8514 | 0.9630 | 0.8190 | -0.0498 | 5183 | 0 |
| research:models · M3 bekko-a8m + embeddinggemma-300m | 0.8049 | 0.9217 | 0.7726 | -0.0963 | 5183 | 0 |
| research:models · M2 granite-small-en-r2 alone in the hybrid | 0.7783 | 0.8950 | 0.7468 | -0.1228 | 5183 | 0 |
| research:models · M2 harrier-270m alone in the hybrid | 0.7765 | 0.8869 | 0.7477 | -0.1247 | 5183 | 0 |
| research:models · M3 bekko-a8m + granite-small-en-r2 | 0.7716 | 0.8900 | 0.7401 | -0.1296 | 5183 | 0 |
| research:models · M3 bekko-a8m + harrier-270m | 0.7702 | 0.8811 | 0.7416 | -0.1310 | 5183 | 0 |
| research:models · M1 harrier-270m dense only | 0.7627 | 0.8827 | 0.7301 | -0.1385 | 5183 | 402 |
| research:models · M0 shipped pair: bekko-a8m + gte-small | 0.7624 | 0.8731 | 0.7329 | -0.1387 | 5183 | 1 |
| research:models · M3 bekko-a8m + arctic-m-v2 | 0.7622 | 0.8688 | 0.7343 | -0.1390 | 5183 | 0 |
| research:models · M1 granite-small-en-r2 dense only | 0.7609 | 0.8875 | 0.7276 | -0.1403 | 5183 | 0 |
| research:models · M2 arctic-m-v2 alone in the hybrid | 0.7601 | 0.8682 | 0.7304 | -0.1411 | 5183 | 0 |
| research:models · M1 arctic-m-v2 dense only | 0.7323 | 0.8504 | 0.7012 | -0.1689 | 5183 | 532 |

### nfcorpus (dev)  (324 queries)

| Config | nDCG@10 | Recall@10 | MRR@10 | vs best | Chunks | Embed s |
|---|---|---|---|---|---|---|
| research:models · M2 embeddinggemma-300m alone in the hybrid | 0.3681 | 0.1743 | 0.5821 | +0.0000 | 3633 | 0 |
| research:models · M1 embeddinggemma-300m dense only | 0.3634 | 0.1714 | 0.5759 | -0.0047 | 3633 | 1 |
| research:models · M3 bekko-a8m + embeddinggemma-300m | 0.3602 | 0.1726 | 0.5508 | -0.0079 | 3633 | 0 |
| research:models · M4 embeddinggemma-300m 256 dims alone in the hybrid | 0.3576 | 0.1690 | 0.5607 | -0.0105 | 3633 | 0 |
| research:models · M3 bekko-a8m + granite-small-en-r2 | 0.3539 | 0.1683 | 0.5440 | -0.0142 | 3633 | 0 |
| research:models · M0 shipped pair: bekko-a8m + gte-small | 0.3539 | 0.1652 | 0.5408 | -0.0142 | 3633 | 1 |
| research:models · M3 bekko-a8m + arctic-m-v2 | 0.3538 | 0.1652 | 0.5490 | -0.0143 | 3633 | 0 |
| research:models · M2 harrier-270m alone in the hybrid | 0.3536 | 0.1669 | 0.5468 | -0.0146 | 3633 | 0 |
| research:models · M3 bekko-a8m + harrier-270m | 0.3528 | 0.1676 | 0.5419 | -0.0153 | 3633 | 0 |
| research:models · M2 arctic-m-v2 alone in the hybrid | 0.3486 | 0.1618 | 0.5592 | -0.0195 | 3633 | 0 |
| research:models · M1 arctic-m-v2 dense only | 0.3469 | 0.1587 | 0.5680 | -0.0212 | 3633 | 2 |
| research:models · M1 harrier-270m dense only | 0.3457 | 0.1620 | 0.5463 | -0.0224 | 3633 | 367 |
| research:models · M2 granite-small-en-r2 alone in the hybrid | 0.3441 | 0.1610 | 0.5301 | -0.0241 | 3633 | 0 |
| research:models · M1 granite-small-en-r2 dense only | 0.3365 | 0.1606 | 0.5257 | -0.0316 | 3633 | 120 |

### alloprof (dev)  (692 queries)

| Config | nDCG@10 | Recall@10 | MRR@10 | vs best | Chunks | Embed s |
|---|---|---|---|---|---|---|
| research:models · M1 embeddinggemma-300m dense only | 0.5669 | 0.7659 | 0.5040 | +0.0000 | 2556 | 273 |
| research:models · M2 embeddinggemma-300m alone in the hybrid | 0.5615 | 0.7688 | 0.4959 | -0.0054 | 2556 | 0 |
| research:models · M2 arctic-m-v2 alone in the hybrid | 0.5500 | 0.7356 | 0.4913 | -0.0170 | 2556 | 0 |
| research:models · M3 bekko-a8m + embeddinggemma-300m | 0.5462 | 0.7514 | 0.4813 | -0.0208 | 2556 | 0 |
| research:models · M3 bekko-a8m + arctic-m-v2 | 0.5433 | 0.7370 | 0.4823 | -0.0237 | 2556 | 0 |
| research:models · M4 embeddinggemma-300m 256 dims alone in the hybrid | 0.5394 | 0.7442 | 0.4745 | -0.0275 | 2556 | 0 |
| research:models · M3 bekko-a8m + harrier-270m | 0.5250 | 0.7110 | 0.4665 | -0.0419 | 2556 | 0 |
| research:models · M1 arctic-m-v2 dense only | 0.5235 | 0.7139 | 0.4632 | -0.0435 | 2556 | 291 |
| research:models · M2 harrier-270m alone in the hybrid | 0.5208 | 0.6922 | 0.4664 | -0.0461 | 2556 | 0 |
| research:models · M3 bekko-a8m + granite-small-en-r2 | 0.5110 | 0.7153 | 0.4473 | -0.0559 | 2556 | 0 |
| research:models · M0 shipped pair: bekko-a8m + gte-small | 0.5036 | 0.6879 | 0.4455 | -0.0634 | 2556 | 1 |
| research:models · M1 harrier-270m dense only | 0.4707 | 0.6561 | 0.4129 | -0.0962 | 2556 | 243 |
| research:models · M2 granite-small-en-r2 alone in the hybrid | 0.4657 | 0.6517 | 0.4069 | -0.1013 | 2556 | 0 |
| research:models · M1 granite-small-en-r2 dense only | 0.3925 | 0.5737 | 0.3355 | -0.1745 | 2556 | 102 |

### mix-fr-en (dev)  (1852 queries)

| Config | nDCG@10 | Recall@10 | MRR@10 | vs best | Chunks | Embed s |
|---|---|---|---|---|---|---|
| research:models · M1 embeddinggemma-300m dense only | 0.6691 | 0.7503 | 0.6699 | +0.0000 | 11462 | 1137 |
| research:models · M2 embeddinggemma-300m alone in the hybrid | 0.6458 | 0.7444 | 0.6405 | -0.0233 | 11462 | 0 |
| research:models · M4 embeddinggemma-300m 256 dims alone in the hybrid | 0.6367 | 0.7379 | 0.6296 | -0.0324 | 11462 | 0 |
| research:models · M3 bekko-a8m + embeddinggemma-300m | 0.6156 | 0.7183 | 0.6089 | -0.0535 | 11462 | 0 |
| research:models · M3 bekko-a8m + arctic-m-v2 | 0.5950 | 0.6887 | 0.5929 | -0.0741 | 11462 | 0 |
| research:models · M2 harrier-270m alone in the hybrid | 0.5938 | 0.6839 | 0.5918 | -0.0753 | 11462 | 0 |
| research:models · M2 arctic-m-v2 alone in the hybrid | 0.5936 | 0.6877 | 0.5932 | -0.0755 | 11462 | 0 |
| research:models · M3 bekko-a8m + harrier-270m | 0.5867 | 0.6735 | 0.5856 | -0.0824 | 11462 | 0 |
| research:models · M3 bekko-a8m + granite-small-en-r2 | 0.5856 | 0.6804 | 0.5810 | -0.0835 | 11462 | 0 |
| research:models · M0 shipped pair: bekko-a8m + gte-small | 0.5796 | 0.6716 | 0.5752 | -0.0894 | 11462 | 1 |
| research:models · M1 arctic-m-v2 dense only | 0.5728 | 0.6714 | 0.5723 | -0.0963 | 11462 | 1225 |
| research:models · M1 harrier-270m dense only | 0.5682 | 0.6654 | 0.5646 | -0.1009 | 11462 | 990 |
| research:models · M2 granite-small-en-r2 alone in the hybrid | 0.5668 | 0.6615 | 0.5604 | -0.1023 | 11462 | 0 |
| research:models · M1 granite-small-en-r2 dense only | 0.5312 | 0.6306 | 0.5245 | -0.1379 | 11462 | 423 |

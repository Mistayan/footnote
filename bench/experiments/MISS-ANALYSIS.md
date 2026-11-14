# Miss analysis, dev split

Shipped-like lab stack (bekko-a8m + gte-small, z-score convex fusion, alpha 0.55, whole documents). Counts are relevant documents. Dev data only: this chooses experiments, it proves nothing.

## scifact: 809 queries, 919 relevant documents

nDCG@10 fused 0.7624, lexical only 0.7025, dense only 0.7536; per-query best-arm oracle 0.8065 (upper bound, not achievable).

| Slice | fused 11-20 | fused 21-100 | fused not in top 100 | fused top 10 | missed: dense top 10 only | missed: lexical top 10 only | missed: neither arm top 10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| all | 41 | 55 | 26 | 797 | 18 | 5 | 99 |
| lang=en | 39 | 45 | 23 | 745 | 17 | 5 | 85 |
| lang=other | 2 | 10 | 3 | 52 | 1 | 0 | 14 |
| length=1-4 words | 1 | 2 | 0 | 6 | 1 | 0 | 2 |
| length=13+ words | 18 | 13 | 7 | 353 | 9 | 2 | 27 |
| length=5-12 words | 22 | 40 | 19 | 438 | 8 | 3 | 70 |

## nfcorpus: 324 queries, 11385 relevant documents

nDCG@10 fused 0.3539, lexical only 0.2921, dense only 0.3535; per-query best-arm oracle 0.3882 (upper bound, not achievable).

| Slice | fused 11-20 | fused 21-100 | fused not in top 100 | fused top 10 | missed: both arms top 10 | missed: dense top 10 only | missed: lexical top 10 only | missed: neither arm top 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 411 | 1314 | 8741 | 919 | 1 | 101 | 107 | 10257 |
| lang=en | 136 | 390 | 2098 | 331 | 1 | 37 | 26 | 2560 |
| lang=other | 275 | 924 | 6643 | 588 | 0 | 64 | 81 | 7697 |
| length=1-4 words | 290 | 955 | 6767 | 618 | 0 | 66 | 83 | 7863 |
| length=13+ words | 1 | 6 | 24 | 0 | 0 | 0 | 0 | 31 |
| length=5-12 words | 120 | 353 | 1950 | 301 | 1 | 35 | 24 | 2363 |

## alloprof: 692 queries, 692 relevant documents

nDCG@10 fused 0.5036, lexical only 0.3317, dense only 0.4709; per-query best-arm oracle 0.5821 (upper bound, not achievable).

| Slice | fused 11-20 | fused 21-100 | fused not in top 100 | fused top 10 | missed: dense top 10 only | missed: lexical top 10 only | missed: neither arm top 10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| all | 59 | 71 | 86 | 476 | 29 | 11 | 176 |
| lang=fr | 59 | 71 | 85 | 472 | 29 | 11 | 175 |
| lang=other | 0 | 0 | 1 | 4 | 0 | 0 | 1 |
| length=1-4 words | 0 | 1 | 0 | 6 | 0 | 0 | 1 |
| length=13+ words | 45 | 62 | 71 | 357 | 27 | 6 | 145 |
| length=5-12 words | 14 | 8 | 15 | 113 | 2 | 5 | 30 |

## mix-fr-en: 1852 queries, 13023 relevant documents

nDCG@10 fused 0.5796, lexical only 0.4694, dense only 0.5584; per-query best-arm oracle 0.6329 (upper bound, not achievable).

| Slice | fused 11-20 | fused 21-100 | fused not in top 100 | fused top 10 | missed: both arms top 10 | missed: dense top 10 only | missed: lexical top 10 only | missed: neither arm top 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 461 | 1244 | 9245 | 2073 | 1 | 125 | 97 | 10727 |
| lang=en | 170 | 375 | 2220 | 1042 | 0 | 51 | 29 | 2685 |
| lang=fr | 50 | 76 | 94 | 494 | 0 | 20 | 9 | 191 |
| lang=other | 241 | 793 | 6931 | 537 | 1 | 54 | 59 | 7851 |
| length=1-4 words | 253 | 817 | 7053 | 523 | 1 | 53 | 66 | 8003 |
| length=13+ words | 52 | 87 | 111 | 720 | 0 | 24 | 6 | 220 |
| length=5-12 words | 156 | 340 | 2081 | 830 | 0 | 48 | 25 | 2504 |


#!/bin/sh
PY=bench/.labenv/Scripts/python.exe
EN='{"dense":{"model":"bge-small-en"},"lexical":{"k1":1.5,"tokenizer":{"stem":"en"}},"fusion":{"kind":"cc","norm":"zscore","alpha":0.55},"chunker":{"kind":"whole"}}'
ML='{"dense":{"model":"bekko-a8m"},"lexical":{"k1":1.5,"tokenizer":{"stem":"en"}},"fusion":{"kind":"cc","norm":"zscore","alpha":0.55},"chunker":{"kind":"whole"}}'
export PYTHONDONTWRITEBYTECODE=1
$PY -I bench/sweep.py rerank --datasets scifact --split dev --tag en:bge-small-en --max-queries 200 --only "mxbai" --base-json "$EN"
$PY -I bench/sweep.py rerank --datasets scifact --split dev --tag en:bge-small-en --max-queries 200 --only "no rerank" --base-json "$EN"
$PY -I bench/sweep.py rerank --datasets alloprof --split dev --tag ml:bekko-a8m --max-queries 200 --only "mmarco" --base-json "$ML"
$PY -I bench/sweep.py rerank --datasets alloprof --split dev --tag ml:bekko-a8m --max-queries 200 --only "no rerank" --base-json "$ML"
$PY -I bench/sweep.py rerank --datasets alloprof --split dev --tag ml:bekko-a8m --max-queries 200 --only "bge-reranker" --base-json "$ML"
echo DONE

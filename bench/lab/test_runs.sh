#!/bin/sh
# Reportable runs of the frozen winners on the official test split, then LongMemEval heldout (user-turn indexing).
PY=bench/.labenv/Scripts/python.exe
export PYTHONDONTWRITEBYTECODE=1
for ds in scifact nfcorpus; do for e in en-gte-small ml-bekko-a8m; do echo "== $ds $e"; $PY -I bench/run.py $ds lab:$e 2>&1 | tail -3; done; done
for ds in alloprof syntec mix-fr-en; do echo "== $ds ml-bekko-a8m"; $PY -I bench/run.py $ds lab:ml-bekko-a8m 2>&1 | tail -3; done
B='"lexical":{"k1":1.5,"tokenizer":{"stem":"en"}},"fusion":{"kind":"cc","norm":"zscore","alpha":0.55},"chunker":{"kind":"whole","roles":"user"}'
for m in gte-small bekko-a8m; do echo "== longmemeval heldout $m"; $PY -I bench/run_lme.py lab:lme-user-$m --split heldout --lab-json "{\"dense\":{\"model\":\"$m\"},$B}" 2>&1 | tail -4; done
echo DONE

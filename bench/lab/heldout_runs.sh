#!/bin/sh
# Heldout validation of the frozen candidates (protocol: tune on dev, report on heldout). Receipts are immutable.
PY=bench/.labenv/Scripts/python.exe
export PYTHONDONTWRITEBYTECODE=1
for ds in scifact nfcorpus; do for e in en-bge-small en-gte-small ml-bekko-a8m; do $PY -I bench/run.py $ds lab:$e --split heldout 2>&1 | tail -2; done; done
for ds in alloprof syntec mix-fr-en; do for e in ml-bekko-a8m ml-bekko-a25m; do $PY -I bench/run.py $ds lab:$e --split heldout 2>&1 | tail -2; done; done
echo DONE

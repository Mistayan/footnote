#!/bin/sh
# Model candidates on dev, after the head-to-head (it needs a quiet machine for its latency). Quality only here; latency per model is measured apart.
PY=bench/.labenv/Scripts/python.exe
export PYTHONDONTWRITEBYTECODE=1
until grep -q "^DONE" bench/work/headtohead.log; do sleep 30; done
BASE='{"dense":{"model":"bekko-a8m","extra":{"model":"gte-small","weight":0.5}},"lexical":{"k1":1.2,"tokenizer":{"stem":"en"}},"fusion":{"kind":"cc","norm":"zscore","alpha":0.55},"chunker":{"kind":"whole"}}'
for ds in scifact nfcorpus alloprof mix-fr-en; do
  $PY -I bench/sweep.py models2 --datasets $ds --split dev --tag research:models --base-json "$BASE"
done
echo DONE

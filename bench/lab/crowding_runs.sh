#!/bin/sh
PY=bench/.labenv/Scripts/python.exe
export PYTHONDONTWRITEBYTECODE=1
for m in bekko-a8m e5-small-multi; do
  $PY -I bench/sweep.py crowding --datasets mix-fr-en --split dev --tag mix:$m --base-json "{\"dense\":{\"model\":\"$m\"},\"lexical\":{\"k1\":1.5,\"tokenizer\":{\"stem\":\"en\"}},\"fusion\":{\"kind\":\"cc\",\"norm\":\"zscore\",\"alpha\":0.55},\"chunker\":{\"kind\":\"whole\"}}"
done
echo DONE

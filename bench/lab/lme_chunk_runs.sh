#!/bin/sh
# LongMemEval-S dev, first 40 scoreable questions: how to cut chat sessions. Base = EN profile (bge-small-en, BM25 stem=en k1=1.5, CC zscore 0.55)
PY=bench/.labenv/Scripts/python.exe
B='"dense":{"model":"bge-small-en"},"lexical":{"k1":1.5,"tokenizer":{"stem":"en"}},"fusion":{"kind":"cc","norm":"zscore","alpha":0.55}'
run() { echo "== $1"; PYTHONDONTWRITEBYTECODE=1 $PY -I bench/run_lme.py lab:lme-$1 --split dev --questions 40 --lab-json "{$B,\"chunker\":$2}" 2>&1 | tail -4; }
run whole       '{"kind":"whole"}'
run user        '{"kind":"whole","roles":"user"}'
run rounds2000  '{"kind":"rounds","size":2000}'
run rounds1000  '{"kind":"rounds","size":1000}'
run sent1000    '{"kind":"sent","size":1000}'
run user-rounds '{"kind":"rounds","size":1000,"roles":"user"}'

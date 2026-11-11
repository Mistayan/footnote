"""Run with python -m tools.knowledge_runtime (bounded serial JSONL, not MCP)."""
import argparse
import json
import sqlite3
import sys
import time

from . import KnowledgeRuntime, Runtime, ResidentReranker


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('db', 'model', 'qdrant-url', 'collection', 'allow-root'):
        parser.add_argument('--' + field, required=True)
    parser.add_argument('--allow-file', action='append', required=True)
    parser.add_argument('--reranker-model', help='explicit existing pinned mMARCO directory; no download')
    parser.add_argument('--source-manifest', help='explicit bounded source metadata JSON; no inference')
    for field in ('write', 'create', 'recover-index'):
        parser.add_argument('--' + field, action='store_true')
    args = parser.parse_args()
    runtime = None
    authority = None
    try:
        started = time.perf_counter()
        reranker = ResidentReranker(args.reranker_model) if args.reranker_model is not None else None
        reranker_load_ms = (time.perf_counter()-started)*1000 if reranker else 0.0
        authority = Runtime(db=args.db, model=args.model, qdrant_url=args.qdrant_url,
                            collection=args.collection, allow_root=args.allow_root,
                            allow_files=args.allow_file, write=args.write, create=args.create,
                            recover_index=args.recover_index)
        runtime = KnowledgeRuntime(authority, source_manifest=args.source_manifest)
        runtime.reranker = reranker
        print(json.dumps({'ready': True, 'transport': 'jsonl', 'model': authority.encoder.identity,
                          'encoder_loads': 1, 'generation': authority.generation,
                          'model_load_ms': authority.model_load_ms, 'reranker_load_ms': reranker_load_ms,
                          **runtime.session_stats()}), flush=True)
        while True:
            line = sys.stdin.buffer.readline(16385)
            if not line:
                return 0
            if len(line) > 16384:
                print(json.dumps({'ok': False, 'error': 'request exceeds 16 KiB; closing'}), flush=True)
                return 2
            request = None
            started = time.perf_counter()
            try:
                request = json.loads(line)
                request_id = request.get('request_id', '') if isinstance(request, dict) else ''
                if not isinstance(request_id, str) or len(request_id) > 64:
                    raise ValueError('request_id must be a string of at most 64 characters')
                response = {'ok': True, 'result': runtime.handle(request)}
            except (ValueError, TypeError, KeyError, OSError, RuntimeError, sqlite3.Error) as error:
                response = {'ok': False, 'error': str(error)[:512]}
            response['elapsed_ms'] = (time.perf_counter() - started) * 1000
            if isinstance(request, dict) and isinstance(request.get('request_id'), str) and len(request['request_id']) <= 64:
                response['request_id'] = request['request_id']
            serialized = json.dumps(response, ensure_ascii=True, allow_nan=False)
            if len(serialized.encode()) > 65535:
                serialized = json.dumps({'ok': False, 'error': 'response exceeds 64 KiB'})
            print(serialized, flush=True)
    except Exception as error:
        print(json.dumps({'ready': False, 'error': str(error)[:512]}), flush=True)
        return 1
    finally:
        if runtime is not None:
            runtime.close()
        elif authority is not None:
            authority.close()


if __name__ == '__main__':
    sys.exit(main())

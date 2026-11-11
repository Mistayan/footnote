# Pooled relevance review — pivot run run-20261019-a1

**Independent MODEL review, NOT independent human validation. Supplementary diagnostic only; historical labels unchanged.**

## Outcome

Exact-source review supports **8/10 first results (80%)**, versus the historical selected-ID **7/10 (70%)**, for each of baseline, pivot and fusion. The additional useful first result is go-holdout-07: RWMutex documentation explicitly says “As with Mutexes”, so its answer applies to Mutex too. This is not mere same-topic substitution. The selected-positive set therefore understates useful rank-one answers by one question, but two real strict-evidence misses remain: writer-progress rationale (01) and Broadcast-versus-Signal (08).

80% here is a post-observation model-adjudicated point estimate on ten reused questions, NOT passing the user’s first ≥80% milestone, NOT fresh validation, and NOT evidence of ≥90% generalization. No model or ranking was rerun. No generated-answer accuracy is measured. A descriptive Wilson 95% interval for 8/10 is approximately (0.49, 0.943); question dependence and model-judgment uncertainty make even this nominal interval optimistic.

## Scope, protocol and limitations

- First shell command was `rtk --version` (0.48.0). No installs, inference, runtime edits, staging or commits. Only this NEW report and the uniquely owned relevance-review directory were written. Public benchmark snapshots only; no vault or private source searched.
- A deterministic shuffled pool (seed 8942317) was saved before review: 95 unique question/passage pairs, 210 ranked occurrences, 14 questions, 3 variants. Ten new-at-original-run Go answerable questions plus exactly four no-answer examples (Go 10/11 and reused holdout EN/FR). They are already observed tests now.
- Pool hides variant, rank, score, translations, selected-positive annotations and model identifiers; preserves full question and source/version identity necessary for applicability. Mapping was saved separately and read only after 95 decisions were written. Blinding is partial: schema discovery accidentally displayed baseline go-holdout-00 including old labels/ranking before pool preparation. That question is not fully blinded. Same model family and shared artifact authorship cannot be excluded; this is a separate review pass, not institutional or human independence.
- Entire six frozen Go source files were read as data. Code comments directing developers to change files, and tutorials showing destructive commands, were treated as untrusted source text and not executed. All 35 Go corpus slices and all 95 pooled source slices/hash chains verified exactly. Commit/tag identity is recorded by original receipt, not independently re-resolved against upstream. No live-source refresh was used.
- ENTAILS means the passage itself supplies the answer in applicable scope (code accepted where unambiguous); PARTIAL means useful context or missing qualifier, not a correct complete answer. INCOMPATIBLE means wrong applicability/version. INSUFFICIENT means no answer evidence; SOURCE UNKNOWN reserved for unverifiable provenance (none observed). Related primitive alone does not establish contradiction.
- This review exhausts the union of the three returned top-five lists for these questions, not all candidate pools, ranks beyond five or all possible query/corpus pairs. The supplementary evidence map includes necessary direct source proofs and one unpooled alternate; it is NOT an exhaustive replacement qrels file. Unreviewed candidates remain unjudged, not negative.

## Counts (answerable queries only unless marked)

| Variant | Old selected-ID P@1 | Reviewed strict P@1 | ≥1 entails in top5 | Entailing passages / 50 | Four no-answer candidate accepts |
|---|---:|---:|---:|---:|---:|
| baseline | 7/10 | 8/10 | 9/10 | 13/50 | 4/4 |
| pivot | 7/10 | 8/10 | 10/10 | 14/50 | 4/4 |
| fusion | 7/10 | 8/10 | 9/10 | 13/50 | 4/4 |

Unique-pair raw counts: {"insufficient": 55, "partial topical": 19, "entails answer with correct scope": 14, "incompatible": 7}. Ranked-occurrence raw counts (duplicate cross-variant passages count repeatedly): {"entails answer with correct scope": 40, "partial topical": 51, "insufficient": 104, "incompatible": 15}.

No no-answer example has any entailing top-five passage. Existing `accepted=1` for all four examples in each variant means candidate false acceptance **4/4 per variant**, not 12 independent queries or generated harmful answers. Precision without abstention/coverage gates cannot qualify.

## Disagreements and sensitivity

- First-result disagreement: 07 / go-rwmutex-005 is useful in all three variants, despite not belonging to the old selected-ID set. Exact comparative wording is the basis, not expected-ID membership.
- Additional top-five evidence not selected originally: 05 / go-waitgroup-002 (negative counter panic in code), 06 / go-waitgroup-003 (reuse-before-return panic), 07 / go-rwmutex-005. These are omissions in selected-positive coverage, not proof historical UNKNOWN entries were asserted false. No selected positive occurring in the reviewed top5 was downgraded.
- Borderline 01: go-rwmutex-002 and truncated go-rwmutex-001 state that blocked writers exclude new readers and show mechanism; neither explains the eventual-writer-progress purpose asked by “Pourquoi”. Strict complete-answer judgment is PARTIAL. A looser mechanism-only usefulness contract could credit 01 and raise this reused diagnostic point estimate; that is a reporting-unit change, NOT a manufactured 90% acceptance result. Freeze that distinction before the next evaluation.
- 08 rank one only states Signal wakes one and mentions Broadcast; it does not say Broadcast wakes all. The answer exists at rank four in all variants. 01 has its explicit rationale at rank four only in pivot, absent baseline/fusion top5. All necessary proof passages occur in each variant’s 20-candidate pool (see per-query candidate fields below): ranking/presentation, not absent source corpus.
- 06 code-only secondary proof is moderate confidence and not needed to judge rank one. 05 code proof depends on source scope identifying v as signed counter. 07 comparative wording is strong but human review could reasonably request direct Mutex prose as the preferred citation.

## Per-question first-result and top-five evidence

### fresh-holdout-noanswer-en

What is the current production latency of my private application?

**Required evidence absent:** Authorized private telemetry/configuration for the named deployment, not public language documentation. No private retrieval was performed.

**baseline first result:** `git-reset-002` — **INSUFFICIENT**. Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought.[11]

> ip of the current branch. If `<mode>` is omitted,
> 	defaults to `--mixed`. The `<mode>` must be one of the following:
> +
> --
> --soft::
> 	Does not touch the index file or the working tree at all (but
> 	resets the head to `<comm

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `git-reset-002` / B036 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 2 | `git-reset-014` / B089 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 3 | `rust-rc-006` / B090 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 4 | `git-reset-000` / B049 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 5 | `rust-rc-007` / B015 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |

**pivot first result:** `git-reset-002` — **INSUFFICIENT**. Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought.[11]

> ip of the current branch. If `<mode>` is omitted,
> 	defaults to `--mixed`. The `<mode>` must be one of the following:
> +
> --
> --soft::
> 	Does not touch the index file or the working tree at all (but
> 	resets the head to `<comm

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `git-reset-002` / B036 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 2 | `git-reset-014` / B089 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 3 | `rust-rc-006` / B090 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 4 | `git-reset-000` / B049 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 5 | `rust-rc-007` / B015 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |

**fusion first result:** `git-reset-002` — **INSUFFICIENT**. Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought.[11]

> ip of the current branch. If `<mode>` is omitted,
> 	defaults to `--mixed`. The `<mode>` must be one of the following:
> +
> --
> --soft::
> 	Does not touch the index file or the working tree at all (but
> 	resets the head to `<comm

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `git-reset-002` / B036 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 2 | `git-reset-014` / B089 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 3 | `gitignore-001` / B040 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 4 | `rust-rc-006` / B090 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 5 | `rust-mutex-009` / B025 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |

### fresh-holdout-noanswer-fr

Quel mot de passe est configuré sur mon serveur privé ?

**Required evidence absent:** Authorized private telemetry/configuration for the named deployment, not public language documentation. No private retrieval was performed.

**baseline first result:** `rust-rc-004` — **INSUFFICIENT**. Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought.[4]

> >`, as shown in Listing 15-18. Each `Cons` variant will now hold a value
> and an `Rc<T>` pointing to a `List`. When we create `b`, instead of taking
> ownership of `a`, we’ll clone the `Rc<List>` that `a` is holding, thereb

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `rust-rc-004` / B005 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 2 | `git-clean-001` / B019 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 3 | `git-reset-002` / B065 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 4 | `rust-mutex-006` / B075 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 5 | `rust-mutex-007` / B063 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |

**pivot first result:** `gitignore-001` — **INSUFFICIENT**. Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought.[3]

> tignore` file.  A project normally
>    includes such `.gitignore` files in its repository, containing patterns for
>    files generated as part of the project build.
> 
>  * Patterns read from `$GIT_DIR/info/exclude`.
> 
>  * Patte

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `gitignore-001` / B004 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 2 | `rust-mutex-006` / B075 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 3 | `rust-mutex-005` / B001 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 4 | `rust-borrow-009` / B069 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 5 | `git-clean-001` / B019 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |

**fusion first result:** `gitignore-001` — **INSUFFICIENT**. Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought.[3]

> tignore` file.  A project normally
>    includes such `.gitignore` files in its repository, containing patterns for
>    files generated as part of the project build.
> 
>  * Patterns read from `$GIT_DIR/info/exclude`.
> 
>  * Patte

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `gitignore-001` / B004 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 2 | `git-clean-001` / B019 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 3 | `rust-mutex-006` / B075 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 4 | `gitignore-008` / B008 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |
| 5 | `rust-borrow-003` / B056 | INSUFFICIENT | Public Git/Rust tutorial has neither private server password nor private application production telemetry; no answer can be inferred. No private data sought. |

### go-holdout-00

Dans Go 1.23.2, un échec de `TryLock` établit-il une relation de synchronisation ?

**Necessary direct answer evidence** [8] (frozen `mutex.txt`; acceptable alternatives: `go-mutex-000`):

```go
// A successful call to [Mutex.TryLock] is equivalent to a call to Lock.
// A failed call to TryLock does not establish any “synchronizes before”
// relation at all.
//
```

**baseline first result:** `go-mutex-000` — **ENTAILS**. Explicit failed TryLock creates no synchronizes-before relation.[8]

> // A successful call to [Mutex.TryLock] is equivalent to a call to Lock.
> // A failed call to TryLock does not establish any “synchronizes before”
> // relation at all.
> //
> // [the Go memory model]: https://go.dev/ref/mem
> type Mutex struct {
> 	state int32
> 	sema  uint32
> }
> 
> // A Locker represents an object that can be locked and unlocked.
> type Locker inte

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-mutex-000` / B031 | ENTAILS | Explicit failed TryLock creates no synchronizes-before relation. |
| 2 | `go-rwmutex-001` / B028 | PARTIAL | RWMutex synchronization is related, not failed Mutex.TryLock guarantee. |
| 3 | `go-rwmutex-004` / B072 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-mutex-001` / B046 | PARTIAL | Opening is a severed sentence; fairness prose does not establish failed TryLock memory-model rule. |
| 5 | `go-mutex-003` / B013 | PARTIAL | TryLock failure branches skip race.Acquire, but instrumentation alone is not the memory-model contract. |

**Direct-proof presence:** top5 ['go-mutex-000']; candidates ['go-mutex-000']. Missing from top5: [].

**pivot first result:** `go-mutex-000` — **ENTAILS**. Explicit failed TryLock creates no synchronizes-before relation.[8]

> // A successful call to [Mutex.TryLock] is equivalent to a call to Lock.
> // A failed call to TryLock does not establish any “synchronizes before”
> // relation at all.
> //
> // [the Go memory model]: https://go.dev/ref/mem
> type Mutex struct {
> 	state int32
> 	sema  uint32
> }
> 
> // A Locker represents an object that can be locked and unlocked.
> type Locker inte

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-mutex-000` / B031 | ENTAILS | Explicit failed TryLock creates no synchronizes-before relation. |
| 2 | `go-rwmutex-001` / B028 | PARTIAL | RWMutex synchronization is related, not failed Mutex.TryLock guarantee. |
| 3 | `go-rwmutex-002` / B060 | PARTIAL | TryRLock is a different operation from Mutex.TryLock. |
| 4 | `go-rwmutex-004` / B072 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-mutex-001` / B046 | PARTIAL | Opening is a severed sentence; fairness prose does not establish failed TryLock memory-model rule. |

**Direct-proof presence:** top5 ['go-mutex-000']; candidates ['go-mutex-000']. Missing from top5: [].

**fusion first result:** `go-mutex-000` — **ENTAILS**. Explicit failed TryLock creates no synchronizes-before relation.[8]

> // A successful call to [Mutex.TryLock] is equivalent to a call to Lock.
> // A failed call to TryLock does not establish any “synchronizes before”
> // relation at all.
> //
> // [the Go memory model]: https://go.dev/ref/mem
> type Mutex struct {
> 	state int32
> 	sema  uint32
> }
> 
> // A Locker represents an object that can be locked and unlocked.
> type Locker inte

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-mutex-000` / B031 | ENTAILS | Explicit failed TryLock creates no synchronizes-before relation. |
| 2 | `go-rwmutex-002` / B060 | PARTIAL | TryRLock is a different operation from Mutex.TryLock. |
| 3 | `go-rwmutex-001` / B028 | PARTIAL | RWMutex synchronization is related, not failed Mutex.TryLock guarantee. |
| 4 | `go-rwmutex-004` / B072 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-mutex-001` / B046 | PARTIAL | Opening is a severed sentence; fairness prose does not establish failed TryLock memory-model rule. |

**Direct-proof presence:** top5 ['go-mutex-000']; candidates ['go-mutex-000']. Missing from top5: [].

### go-holdout-01

Pourquoi de nouveaux lecteurs ne peuvent-ils plus acquérir le verrou lorsqu’un écrivain attend ?

**Necessary direct answer evidence** [5] (frozen `rwmutex.txt`; acceptable alternatives: `go-rwmutex-000`):

```go
// If any goroutine calls [RWMutex.Lock] while the lock is already held by
// one or more readers, concurrent calls to [RWMutex.RLock] will block until
// the writer has acquired (and released) the lock, to ensure that
// the lock eventually becomes available to the writer.
// Note that this prohibits recursive read-locking.
//
```

**baseline first result:** `go-rwmutex-002` — **PARTIAL**. States blocked writer excludes new readers and shows mechanism, but omits eventual writer-progress rationale.[5]

> semantics, which would incorrectly synchronize racing
> // readers, thus potentially missing races.
> 
> // RLock locks rw for reading.
> //
> // It should not be used for recursive read locking; a blocked Lock
> // call excludes ne

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-rwmutex-002` / B081 | PARTIAL | States blocked writer excludes new readers and shows mechanism, but omits eventual writer-progress rationale. |
| 2 | `go-rwmutex-005` / B021 | PARTIAL | Unblocks readers on writer Unlock, but does not state why pending writer excludes new readers. |
| 3 | `go-rwmutex-004` / B006 | PARTIAL | Pending-writer announcement and active-reader wait show mechanism, but not why readers must yield for eventual writer progress. |
| 4 | `go-mutex-001` / B052 | PARTIAL | Mutex fairness is related but not RWMutex writer-versus-reader policy. |
| 5 | `go-mutex-003` / B030 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 []; candidates ['go-rwmutex-000']. Missing from top5: ['go-rwmutex-000'].

**pivot first result:** `go-rwmutex-002` — **PARTIAL**. States blocked writer excludes new readers and shows mechanism, but omits eventual writer-progress rationale.[5]

> semantics, which would incorrectly synchronize racing
> // readers, thus potentially missing races.
> 
> // RLock locks rw for reading.
> //
> // It should not be used for recursive read locking; a blocked Lock
> // call excludes ne

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-rwmutex-002` / B081 | PARTIAL | States blocked writer excludes new readers and shows mechanism, but omits eventual writer-progress rationale. |
| 2 | `go-rwmutex-005` / B021 | PARTIAL | Unblocks readers on writer Unlock, but does not state why pending writer excludes new readers. |
| 3 | `go-rwmutex-004` / B006 | PARTIAL | Pending-writer announcement and active-reader wait show mechanism, but not why readers must yield for eventual writer progress. |
| 4 | `go-rwmutex-000` / B017 | ENTAILS | Explicit reader blocking is to ensure eventual writer availability; answers why. |
| 5 | `go-rwmutex-001` / B091 | PARTIAL | Reader blocking fact appears, but why (eventual writer progress) is truncated. |

**Direct-proof presence:** top5 ['go-rwmutex-000']; candidates ['go-rwmutex-000']. Missing from top5: [].

**fusion first result:** `go-rwmutex-002` — **PARTIAL**. States blocked writer excludes new readers and shows mechanism, but omits eventual writer-progress rationale.[5]

> semantics, which would incorrectly synchronize racing
> // readers, thus potentially missing races.
> 
> // RLock locks rw for reading.
> //
> // It should not be used for recursive read locking; a blocked Lock
> // call excludes ne

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-rwmutex-002` / B081 | PARTIAL | States blocked writer excludes new readers and shows mechanism, but omits eventual writer-progress rationale. |
| 2 | `go-rwmutex-005` / B021 | PARTIAL | Unblocks readers on writer Unlock, but does not state why pending writer excludes new readers. |
| 3 | `go-mutex-007` / B059 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-rwmutex-004` / B006 | PARTIAL | Pending-writer announcement and active-reader wait show mechanism, but not why readers must yield for eventual writer progress. |
| 5 | `go-mutex-001` / B052 | PARTIAL | Mutex fairness is related but not RWMutex writer-versus-reader policy. |

**Direct-proof presence:** top5 []; candidates ['go-rwmutex-000']. Missing from top5: ['go-rwmutex-000'].

### go-holdout-02

Avec `Once.Do`, une fonction qui panique sera-t-elle exécutée à nouveau au prochain appel ?

**Necessary direct answer evidence** [7] (frozen `once.txt`; acceptable alternatives: `go-once-001`):

```go
// If f panics, Do considers it to have returned; future calls of Do return
// without calling f.
```

**baseline first result:** `go-once-001` — **ENTAILS**. Explicit panic counts as returned; future Do does not call f.[7]

> // If f panics, Do considers it to have returned; future calls of Do return
> // without calling f.
> func (o *Once) Do(f func()) {
> 	// Note: Here is an incorrect implementation of Do:
> 	//
> 	//	if o.done.CompareAndSwap(0, 1) {
> 	//		f()
> 	//	}
> 	//
> 	// Do guarantees that when it returns, f has finished.
> 	// This implementation would not implement that guar

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-once-001` / B010 | ENTAILS | Explicit panic counts as returned; future Do does not call f. |
| 2 | `go-once-000` / B053 | PARTIAL | Once first-invocation contract omits panic behavior; exception must not be inferred. |
| 3 | `go-pool-005` / B079 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-cond-001` / B092 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-pool-002` / B057 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-once-001']; candidates ['go-once-001']. Missing from top5: [].

**pivot first result:** `go-once-001` — **ENTAILS**. Explicit panic counts as returned; future Do does not call f.[7]

> // If f panics, Do considers it to have returned; future calls of Do return
> // without calling f.
> func (o *Once) Do(f func()) {
> 	// Note: Here is an incorrect implementation of Do:
> 	//
> 	//	if o.done.CompareAndSwap(0, 1) {
> 	//		f()
> 	//	}
> 	//
> 	// Do guarantees that when it returns, f has finished.
> 	// This implementation would not implement that guar

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-once-001` / B010 | ENTAILS | Explicit panic counts as returned; future Do does not call f. |
| 2 | `go-once-000` / B053 | PARTIAL | Once first-invocation contract omits panic behavior; exception must not be inferred. |
| 3 | `go-pool-005` / B079 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-waitgroup-001` / B070 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-pool-002` / B057 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-once-001']; candidates ['go-once-001']. Missing from top5: [].

**fusion first result:** `go-once-001` — **ENTAILS**. Explicit panic counts as returned; future Do does not call f.[7]

> // If f panics, Do considers it to have returned; future calls of Do return
> // without calling f.
> func (o *Once) Do(f func()) {
> 	// Note: Here is an incorrect implementation of Do:
> 	//
> 	//	if o.done.CompareAndSwap(0, 1) {
> 	//		f()
> 	//	}
> 	//
> 	// Do guarantees that when it returns, f has finished.
> 	// This implementation would not implement that guar

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-once-001` / B010 | ENTAILS | Explicit panic counts as returned; future Do does not call f. |
| 2 | `go-once-000` / B053 | PARTIAL | Once first-invocation contract omits panic behavior; exception must not be inferred. |
| 3 | `go-waitgroup-001` / B070 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-cond-001` / B092 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-waitgroup-002` / B039 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-once-001']; candidates ['go-once-001']. Missing from top5: [].

### go-holdout-03

Les objets placés dans `Pool` peuvent-ils disparaître sans notification ?

**Necessary direct answer evidence** [9] (frozen `pool.txt`; acceptable alternatives: `go-pool-000`):

```go
// Any item stored in the Pool may be removed automatically at any time without
// notification. If the Pool holds the only reference when this happens, the
// item might be deallocated.
//
```

**baseline first result:** `go-pool-000` — **ENTAILS**. Explicit removal at any time without notification.[9]

> // Any item stored in the Pool may be removed automatically at any time without
> // notification. If the Pool holds the only reference when this happens, the
> // item might be deallocated.
> //
> // A Pool is safe for use by multiple goroutines simultaneously.
> //
> // Pool's purpose is to cache allocated but unused items for later reuse,
> // relieving press

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-pool-000` / B014 | ENTAILS | Explicit removal at any time without notification. |
| 2 | `go-pool-001` / B086 | PARTIAL | Pool cache shrinks and structure context, no arbitrary silent-removal guarantee. |
| 3 | `go-pool-003` / B037 | PARTIAL | Get may ignore pool; race-enabled Put drops items, but narrower than general removal at any time without notification. |
| 4 | `go-pool-004` / B026 | PARTIAL | Pool victim-cache aging and removal are related, but no general no-notification contract in this slice. |
| 5 | `go-cond-002` / B078 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-pool-000']; candidates ['go-pool-000']. Missing from top5: [].

**pivot first result:** `go-pool-000` — **ENTAILS**. Explicit removal at any time without notification.[9]

> // Any item stored in the Pool may be removed automatically at any time without
> // notification. If the Pool holds the only reference when this happens, the
> // item might be deallocated.
> //
> // A Pool is safe for use by multiple goroutines simultaneously.
> //
> // Pool's purpose is to cache allocated but unused items for later reuse,
> // relieving press

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-pool-000` / B014 | ENTAILS | Explicit removal at any time without notification. |
| 2 | `go-pool-003` / B037 | PARTIAL | Get may ignore pool; race-enabled Put drops items, but narrower than general removal at any time without notification. |
| 3 | `go-pool-001` / B086 | PARTIAL | Pool cache shrinks and structure context, no arbitrary silent-removal guarantee. |
| 4 | `go-pool-004` / B026 | PARTIAL | Pool victim-cache aging and removal are related, but no general no-notification contract in this slice. |
| 5 | `go-cond-002` / B078 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-pool-000']; candidates ['go-pool-000']. Missing from top5: [].

**fusion first result:** `go-pool-000` — **ENTAILS**. Explicit removal at any time without notification.[9]

> // Any item stored in the Pool may be removed automatically at any time without
> // notification. If the Pool holds the only reference when this happens, the
> // item might be deallocated.
> //
> // A Pool is safe for use by multiple goroutines simultaneously.
> //
> // Pool's purpose is to cache allocated but unused items for later reuse,
> // relieving press

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-pool-000` / B014 | ENTAILS | Explicit removal at any time without notification. |
| 2 | `go-pool-003` / B037 | PARTIAL | Get may ignore pool; race-enabled Put drops items, but narrower than general removal at any time without notification. |
| 3 | `go-pool-001` / B086 | PARTIAL | Pool cache shrinks and structure context, no arbitrary silent-removal guarantee. |
| 4 | `go-pool-004` / B026 | PARTIAL | Pool victim-cache aging and removal are related, but no general no-notification contract in this slice. |
| 5 | `go-cond-002` / B078 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-pool-000']; candidates ['go-pool-000']. Missing from top5: [].

### go-holdout-04

Pourquoi faut-il attendre une condition dans une boucle plutôt que supposer qu’elle est vraie après le réveil ?

**Necessary direct answer evidence** [2] (frozen `cond.txt`; acceptable alternatives: `go-cond-001`):

```go
// Because c.L is not locked while Wait is waiting, the caller
// typically cannot assume that the condition is true when
// Wait returns. Instead, the caller should Wait in a loop:
//
//	c.L.Lock()
//	for !condition() {
//	    c.Wait()
//	}
//	... make use of condition ...
//	c.L.Unlock()
```

**baseline first result:** `go-cond-001` — **ENTAILS**. Explicit unlocked wait interval and prescribed condition loop; no spurious-wakeup claim needed.[2]

> // Because c.L is not locked while Wait is waiting, the caller
> // typically cannot assume that the condition is true when
> // Wait returns. Instead, the caller should Wait in a loop:
> //
> //	c.L.Lock()
> //	for !condition() {
> //	    c.Wait()
> //	}
> //	... make use of condition ...
> //	c.L.Unlock()
> func (c *Cond) Wait() {
> 	c.checker.check()
> 	t := runtime_no

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-cond-001` / B067 | ENTAILS | Explicit unlocked wait interval and prescribed condition loop; no spurious-wakeup claim needed. |
| 2 | `go-mutex-004` / B066 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 3 | `go-mutex-002` / B058 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-pool-001` / B027 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-waitgroup-001` / B083 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-cond-001']; candidates ['go-cond-001']. Missing from top5: [].

**pivot first result:** `go-cond-001` — **ENTAILS**. Explicit unlocked wait interval and prescribed condition loop; no spurious-wakeup claim needed.[2]

> // Because c.L is not locked while Wait is waiting, the caller
> // typically cannot assume that the condition is true when
> // Wait returns. Instead, the caller should Wait in a loop:
> //
> //	c.L.Lock()
> //	for !condition() {
> //	    c.Wait()
> //	}
> //	... make use of condition ...
> //	c.L.Unlock()
> func (c *Cond) Wait() {
> 	c.checker.check()
> 	t := runtime_no

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-cond-001` / B067 | ENTAILS | Explicit unlocked wait interval and prescribed condition loop; no spurious-wakeup claim needed. |
| 2 | `go-mutex-004` / B066 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 3 | `go-waitgroup-001` / B083 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-rwmutex-004` / B064 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-pool-005` / B035 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-cond-001']; candidates ['go-cond-001']. Missing from top5: [].

**fusion first result:** `go-cond-001` — **ENTAILS**. Explicit unlocked wait interval and prescribed condition loop; no spurious-wakeup claim needed.[2]

> // Because c.L is not locked while Wait is waiting, the caller
> // typically cannot assume that the condition is true when
> // Wait returns. Instead, the caller should Wait in a loop:
> //
> //	c.L.Lock()
> //	for !condition() {
> //	    c.Wait()
> //	}
> //	... make use of condition ...
> //	c.L.Unlock()
> func (c *Cond) Wait() {
> 	c.checker.check()
> 	t := runtime_no

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-cond-001` / B067 | ENTAILS | Explicit unlocked wait interval and prescribed condition loop; no spurious-wakeup claim needed. |
| 2 | `go-mutex-004` / B066 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 3 | `go-mutex-002` / B058 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-pool-001` / B027 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-mutex-003` / B085 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-cond-001']; candidates ['go-cond-001']. Missing from top5: [].

### go-holdout-05

What happens when the `WaitGroup` counter becomes negative?

**Necessary direct answer evidence** [6] (frozen `waitgroup.txt`; acceptable alternatives: `go-waitgroup-000`, `go-waitgroup-001`, `go-waitgroup-002`):

```go
// Add adds delta, which may be negative, to the [WaitGroup] counter.
// If the counter becomes zero, all goroutines blocked on [WaitGroup.Wait] are released.
// If the counter goes negative, Add panics.
//
```

**baseline first result:** `go-waitgroup-001` — **ENTAILS**. Explicit negative counter causes Add panic.[6]

> // If the counter goes negative, Add panics.
> //
> // Note that calls with a positive delta that occur when the counter is zero
> // must happen before a Wait. Calls with a negative delta, or calls with a
> // positive delta that start when the counter is greater than zero, may happen
> // at any time.
> // Typically this means the calls to Add should execute

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-waitgroup-001` / B074 | ENTAILS | Explicit negative counter causes Add panic. |
| 2 | `go-waitgroup-002` / B043 | ENTAILS | Negative v branch panics with negative WaitGroup counter; source confirms v is signed counter. |
| 3 | `go-waitgroup-000` / B007 | ENTAILS | Explicit negative counter causes Add panic. |
| 4 | `go-waitgroup-003` / B073 | PARTIAL | WaitGroup reuse panic, not negative-counter panic. |
| 5 | `go-cond-001` / B054 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-waitgroup-000', 'go-waitgroup-001', 'go-waitgroup-002']; candidates ['go-waitgroup-000', 'go-waitgroup-001', 'go-waitgroup-002']. Missing from top5: [].

**pivot first result:** `go-waitgroup-001` — **ENTAILS**. Explicit negative counter causes Add panic.[6]

> // If the counter goes negative, Add panics.
> //
> // Note that calls with a positive delta that occur when the counter is zero
> // must happen before a Wait. Calls with a negative delta, or calls with a
> // positive delta that start when the counter is greater than zero, may happen
> // at any time.
> // Typically this means the calls to Add should execute

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-waitgroup-001` / B074 | ENTAILS | Explicit negative counter causes Add panic. |
| 2 | `go-waitgroup-002` / B043 | ENTAILS | Negative v branch panics with negative WaitGroup counter; source confirms v is signed counter. |
| 3 | `go-waitgroup-000` / B007 | ENTAILS | Explicit negative counter causes Add panic. |
| 4 | `go-waitgroup-003` / B073 | PARTIAL | WaitGroup reuse panic, not negative-counter panic. |
| 5 | `go-cond-001` / B054 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-waitgroup-000', 'go-waitgroup-001', 'go-waitgroup-002']; candidates ['go-waitgroup-000', 'go-waitgroup-001', 'go-waitgroup-002']. Missing from top5: [].

**fusion first result:** `go-waitgroup-001` — **ENTAILS**. Explicit negative counter causes Add panic.[6]

> // If the counter goes negative, Add panics.
> //
> // Note that calls with a positive delta that occur when the counter is zero
> // must happen before a Wait. Calls with a negative delta, or calls with a
> // positive delta that start when the counter is greater than zero, may happen
> // at any time.
> // Typically this means the calls to Add should execute

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-waitgroup-001` / B074 | ENTAILS | Explicit negative counter causes Add panic. |
| 2 | `go-waitgroup-002` / B043 | ENTAILS | Negative v branch panics with negative WaitGroup counter; source confirms v is signed counter. |
| 3 | `go-waitgroup-000` / B007 | ENTAILS | Explicit negative counter causes Add panic. |
| 4 | `go-waitgroup-003` / B073 | PARTIAL | WaitGroup reuse panic, not negative-counter panic. |
| 5 | `go-rwmutex-004` / B048 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-waitgroup-000', 'go-waitgroup-001', 'go-waitgroup-002']; candidates ['go-waitgroup-000', 'go-waitgroup-001', 'go-waitgroup-002']. Missing from top5: [].

### go-holdout-06

When reusing a `WaitGroup`, may new additions start before all previous waits have returned?

**Necessary direct answer evidence** [6] (frozen `waitgroup.txt`; acceptable alternatives: `go-waitgroup-001`, `go-waitgroup-003`):

```go
// If a WaitGroup is reused to wait for several independent sets of events,
// new Add calls must happen after all previous Wait calls have returned.
```

**baseline first result:** `go-waitgroup-001` — **ENTAILS**. Explicit new Add after ALL previous Wait returns.[6]

> // If a WaitGroup is reused to wait for several independent sets of events,
> // new Add calls must happen after all previous Wait calls have returned.
> // See the WaitGroup example.
> func (wg *WaitGroup) Add(delta int) {
> 	if race.Enabled {
> 		if delta < 0 {
> 			// Synchronize decrements with Wait.
> 			race.ReleaseMerge(unsafe.Pointer(wg))
> 		}
> 		race.Disa

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-waitgroup-001` / B076 | ENTAILS | Explicit new Add after ALL previous Wait returns. |
| 2 | `go-waitgroup-003` / B047 | ENTAILS | Wait code panics on reuse before previous Wait returns; operational support for forbidden overlap (moderate confidence). |
| 3 | `go-waitgroup-000` / B077 | PARTIAL | WaitGroup counter and Add timing context omits reuse rule. |
| 4 | `go-waitgroup-002` / B084 | PARTIAL | Add-concurrent-with-Wait guard is related but lacks full next-cycle/all-previous-waits rule. |
| 5 | `go-cond-001` / B003 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-waitgroup-001', 'go-waitgroup-003']; candidates ['go-waitgroup-001', 'go-waitgroup-003']. Missing from top5: [].

**pivot first result:** `go-waitgroup-001` — **ENTAILS**. Explicit new Add after ALL previous Wait returns.[6]

> // If a WaitGroup is reused to wait for several independent sets of events,
> // new Add calls must happen after all previous Wait calls have returned.
> // See the WaitGroup example.
> func (wg *WaitGroup) Add(delta int) {
> 	if race.Enabled {
> 		if delta < 0 {
> 			// Synchronize decrements with Wait.
> 			race.ReleaseMerge(unsafe.Pointer(wg))
> 		}
> 		race.Disa

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-waitgroup-001` / B076 | ENTAILS | Explicit new Add after ALL previous Wait returns. |
| 2 | `go-waitgroup-003` / B047 | ENTAILS | Wait code panics on reuse before previous Wait returns; operational support for forbidden overlap (moderate confidence). |
| 3 | `go-waitgroup-000` / B077 | PARTIAL | WaitGroup counter and Add timing context omits reuse rule. |
| 4 | `go-waitgroup-002` / B084 | PARTIAL | Add-concurrent-with-Wait guard is related but lacks full next-cycle/all-previous-waits rule. |
| 5 | `go-cond-001` / B003 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-waitgroup-001', 'go-waitgroup-003']; candidates ['go-waitgroup-001', 'go-waitgroup-003']. Missing from top5: [].

**fusion first result:** `go-waitgroup-001` — **ENTAILS**. Explicit new Add after ALL previous Wait returns.[6]

> // If a WaitGroup is reused to wait for several independent sets of events,
> // new Add calls must happen after all previous Wait calls have returned.
> // See the WaitGroup example.
> func (wg *WaitGroup) Add(delta int) {
> 	if race.Enabled {
> 		if delta < 0 {
> 			// Synchronize decrements with Wait.
> 			race.ReleaseMerge(unsafe.Pointer(wg))
> 		}
> 		race.Disa

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-waitgroup-001` / B076 | ENTAILS | Explicit new Add after ALL previous Wait returns. |
| 2 | `go-waitgroup-000` / B077 | PARTIAL | WaitGroup counter and Add timing context omits reuse rule. |
| 3 | `go-waitgroup-003` / B047 | ENTAILS | Wait code panics on reuse before previous Wait returns; operational support for forbidden overlap (moderate confidence). |
| 4 | `go-waitgroup-002` / B084 | PARTIAL | Add-concurrent-with-Wait guard is related but lacks full next-cycle/all-previous-waits rule. |
| 5 | `go-cond-001` / B003 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-waitgroup-001', 'go-waitgroup-003']; candidates ['go-waitgroup-001', 'go-waitgroup-003']. Missing from top5: [].

### go-holdout-07

Must the same goroutine lock and unlock a `Mutex`?

**Necessary direct answer evidence** [8] (frozen `mutex.txt`; acceptable alternatives: `go-mutex-005`, `go-mutex-006`, `go-rwmutex-005`):

```go
// A locked [Mutex] is not associated with a particular goroutine.
// It is allowed for one goroutine to lock a Mutex and then
// arrange for another goroutine to unlock it.
```

**baseline first result:** `go-rwmutex-005` — **ENTAILS**. As with Mutexes explicitly extends non-goroutine-association to Mutex, despite RWMutex context.[5]

> // As with Mutexes, a locked [RWMutex] is not associated with a particular
> // goroutine. One goroutine may [RWMutex.RLock] ([RWMutex.Lock]) a RWMutex and then
> // arrange for another goroutine to [RWMutex.RUnlock] ([RWMutex.Unlock]) it.
> func (rw *RWMutex) Unlock() {
> 	if race.Enabled {
> 		_ = rw.w.state
> 		race.Release(unsafe.Pointer(&rw.readerSem))
> 		

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-rwmutex-005` / B032 | ENTAILS | As with Mutexes explicitly extends non-goroutine-association to Mutex, despite RWMutex context. |
| 2 | `go-mutex-006` / B041 | ENTAILS | Explicit one goroutine may lock and another unlock. |
| 3 | `go-mutex-004` / B033 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-rwmutex-000` / B094 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-mutex-002` / B011 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-mutex-006', 'go-rwmutex-005']; candidates ['go-mutex-005', 'go-mutex-006', 'go-rwmutex-005']. Missing from top5: ['go-mutex-005'].

**pivot first result:** `go-rwmutex-005` — **ENTAILS**. As with Mutexes explicitly extends non-goroutine-association to Mutex, despite RWMutex context.[5]

> // As with Mutexes, a locked [RWMutex] is not associated with a particular
> // goroutine. One goroutine may [RWMutex.RLock] ([RWMutex.Lock]) a RWMutex and then
> // arrange for another goroutine to [RWMutex.RUnlock] ([RWMutex.Unlock]) it.
> func (rw *RWMutex) Unlock() {
> 	if race.Enabled {
> 		_ = rw.w.state
> 		race.Release(unsafe.Pointer(&rw.readerSem))
> 		

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-rwmutex-005` / B032 | ENTAILS | As with Mutexes explicitly extends non-goroutine-association to Mutex, despite RWMutex context. |
| 2 | `go-mutex-006` / B041 | ENTAILS | Explicit one goroutine may lock and another unlock. |
| 3 | `go-mutex-004` / B033 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-rwmutex-000` / B094 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-mutex-002` / B011 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-mutex-006', 'go-rwmutex-005']; candidates ['go-mutex-005', 'go-mutex-006', 'go-rwmutex-005']. Missing from top5: ['go-mutex-005'].

**fusion first result:** `go-rwmutex-005` — **ENTAILS**. As with Mutexes explicitly extends non-goroutine-association to Mutex, despite RWMutex context.[5]

> // As with Mutexes, a locked [RWMutex] is not associated with a particular
> // goroutine. One goroutine may [RWMutex.RLock] ([RWMutex.Lock]) a RWMutex and then
> // arrange for another goroutine to [RWMutex.RUnlock] ([RWMutex.Unlock]) it.
> func (rw *RWMutex) Unlock() {
> 	if race.Enabled {
> 		_ = rw.w.state
> 		race.Release(unsafe.Pointer(&rw.readerSem))
> 		

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-rwmutex-005` / B032 | ENTAILS | As with Mutexes explicitly extends non-goroutine-association to Mutex, despite RWMutex context. |
| 2 | `go-mutex-006` / B041 | ENTAILS | Explicit one goroutine may lock and another unlock. |
| 3 | `go-mutex-004` / B033 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-rwmutex-000` / B094 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-mutex-002` / B011 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-mutex-006', 'go-rwmutex-005']; candidates ['go-mutex-005', 'go-mutex-006', 'go-rwmutex-005']. Missing from top5: ['go-mutex-005'].

### go-holdout-08

Which condition-variable method wakes every waiter rather than a single waiter?

**Necessary direct answer evidence** [2] (frozen `cond.txt`; acceptable alternatives: `go-cond-002`):

```go
// Broadcast wakes all goroutines waiting on c.
//
// It is allowed but not required for the caller to hold c.L
// during the call.
```

**baseline first result:** `go-cond-001` — **PARTIAL**. Signal one is stated; Broadcast merely mentioned, no all-waiter semantics.[2]

> //
> // [the Go memory model]: https://go.dev/ref/mem
> // [Roberto Clapis's series on advanced concurrency patterns]: https://blogtitle.github.io/categories/concurrency/
> // [Bryan Mills's talk on concurrency patterns]: http

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-cond-001` / B087 | PARTIAL | Signal one is stated; Broadcast merely mentioned, no all-waiter semantics. |
| 2 | `go-cond-000` / B055 | PARTIAL | Broadcast closing-channel analogy is useful but all-versus-one answer requires outside channel semantics. |
| 3 | `go-rwmutex-003` / B082 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-cond-002` / B034 | ENTAILS | Explicit Broadcast all versus Signal one. |
| 5 | `go-mutex-007` / B095 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-cond-002']; candidates ['go-cond-002']. Missing from top5: [].

**pivot first result:** `go-cond-001` — **PARTIAL**. Signal one is stated; Broadcast merely mentioned, no all-waiter semantics.[2]

> //
> // [the Go memory model]: https://go.dev/ref/mem
> // [Roberto Clapis's series on advanced concurrency patterns]: https://blogtitle.github.io/categories/concurrency/
> // [Bryan Mills's talk on concurrency patterns]: http

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-cond-001` / B087 | PARTIAL | Signal one is stated; Broadcast merely mentioned, no all-waiter semantics. |
| 2 | `go-cond-000` / B055 | PARTIAL | Broadcast closing-channel analogy is useful but all-versus-one answer requires outside channel semantics. |
| 3 | `go-rwmutex-003` / B082 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-cond-002` / B034 | ENTAILS | Explicit Broadcast all versus Signal one. |
| 5 | `go-mutex-007` / B095 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-cond-002']; candidates ['go-cond-002']. Missing from top5: [].

**fusion first result:** `go-cond-001` — **PARTIAL**. Signal one is stated; Broadcast merely mentioned, no all-waiter semantics.[2]

> //
> // [the Go memory model]: https://go.dev/ref/mem
> // [Roberto Clapis's series on advanced concurrency patterns]: https://blogtitle.github.io/categories/concurrency/
> // [Bryan Mills's talk on concurrency patterns]: http

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-cond-001` / B087 | PARTIAL | Signal one is stated; Broadcast merely mentioned, no all-waiter semantics. |
| 2 | `go-cond-000` / B055 | PARTIAL | Broadcast closing-channel analogy is useful but all-versus-one answer requires outside channel semantics. |
| 3 | `go-waitgroup-002` / B068 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-cond-002` / B034 | ENTAILS | Explicit Broadcast all versus Signal one. |
| 5 | `go-rwmutex-004` / B044 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-cond-002']; candidates ['go-cond-002']. Missing from top5: [].

### go-holdout-09

What happens if the initialization function recursively invokes `Do` on the same `Once`?

**Necessary direct answer evidence** [7] (frozen `once.txt`; acceptable alternatives: `go-once-001`):

```go
// Because no call to Do returns until the one call to f returns, if f causes
// Do to be called, it will deadlock.
//
```

**baseline first result:** `go-once-001` — **ENTAILS**. Explicit same-Once recursive Do deadlocks; complete answer.[7]

> // Because no call to Do returns until the one call to f returns, if f causes
> // Do to be called, it will deadlock.
> //
> // If f panics, Do considers it to have returned; future calls of Do return
> // without calling f.
> func (o *Once) Do(f func()) {
> 	// Note: Here is an incorrect implementation of Do:
> 	//
> 	//	if o.done.CompareAndSwap(0, 1) {
> 	//		f()
> 

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-once-001` / B009 | ENTAILS | Explicit same-Once recursive Do deadlocks; complete answer. |
| 2 | `go-once-000` / B029 | PARTIAL | Once first-call contract does not explicitly resolve recursive initialization deadlock. |
| 3 | `go-rwmutex-004` / B016 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-rwmutex-002` / B020 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-cond-003` / B050 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-once-001']; candidates ['go-once-001']. Missing from top5: [].

**pivot first result:** `go-once-001` — **ENTAILS**. Explicit same-Once recursive Do deadlocks; complete answer.[7]

> // Because no call to Do returns until the one call to f returns, if f causes
> // Do to be called, it will deadlock.
> //
> // If f panics, Do considers it to have returned; future calls of Do return
> // without calling f.
> func (o *Once) Do(f func()) {
> 	// Note: Here is an incorrect implementation of Do:
> 	//
> 	//	if o.done.CompareAndSwap(0, 1) {
> 	//		f()
> 

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-once-001` / B009 | ENTAILS | Explicit same-Once recursive Do deadlocks; complete answer. |
| 2 | `go-once-000` / B029 | PARTIAL | Once first-call contract does not explicitly resolve recursive initialization deadlock. |
| 3 | `go-rwmutex-004` / B016 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-rwmutex-002` / B020 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-cond-003` / B050 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-once-001']; candidates ['go-once-001']. Missing from top5: [].

**fusion first result:** `go-once-001` — **ENTAILS**. Explicit same-Once recursive Do deadlocks; complete answer.[7]

> // Because no call to Do returns until the one call to f returns, if f causes
> // Do to be called, it will deadlock.
> //
> // If f panics, Do considers it to have returned; future calls of Do return
> // without calling f.
> func (o *Once) Do(f func()) {
> 	// Note: Here is an incorrect implementation of Do:
> 	//
> 	//	if o.done.CompareAndSwap(0, 1) {
> 	//		f()
> 

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-once-001` / B009 | ENTAILS | Explicit same-Once recursive Do deadlocks; complete answer. |
| 2 | `go-once-000` / B029 | PARTIAL | Once first-call contract does not explicitly resolve recursive initialization deadlock. |
| 3 | `go-cond-001` / B002 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 4 | `go-pool-003` / B022 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |
| 5 | `go-cond-003` / B050 | INSUFFICIENT | Different synchronization primitive or unrelated public documentation; does not establish the requested operation/condition. Shared concurrency vocabulary is not an answer. |

**Direct-proof presence:** top5 ['go-once-001']; candidates ['go-once-001']. Missing from top5: [].

### go-holdout-10

Quelle est la latence médiane en nanosecondes de nos verrous privés en production ?

**Required evidence absent:** Authorized private telemetry/configuration for the named deployment, not public language documentation. No private retrieval was performed.

**baseline first result:** `go-mutex-002` — **INSUFFICIENT**. Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency.[8]

> s don't try to acquire the mutex even if it appears
> 	// to be unlocked, and don't try to spin. Instead they queue themselves at
> 	// the tail of the wait queue.
> 	//
> 	// If a waiter receives ownership of the mutex and sees

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-mutex-002` / B062 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 2 | `go-mutex-005` / B088 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 3 | `go-pool-004` / B024 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 4 | `go-rwmutex-001` / B071 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 5 | `go-mutex-004` / B045 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |

**pivot first result:** `go-rwmutex-003` — **INSUFFICIENT**. Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency.[5]

>  race.Enabled {
> 				race.Enable()
> 				race.Acquire(unsafe.Pointer(&rw.readerSem))
> 			}
> 			return true
> 		}
> 	}
> }
> 
> // RUnlock undoes a single [RWMutex.RLock] call;
> // it does not affect other simultaneous readers.
> // It is 

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-rwmutex-003` / B093 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 2 | `go-mutex-002` / B062 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 3 | `go-pool-003` / B023 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 4 | `go-pool-004` / B024 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 5 | `go-rwmutex-001` / B071 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |

**fusion first result:** `go-mutex-002` — **INSUFFICIENT**. Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency.[8]

> s don't try to acquire the mutex even if it appears
> 	// to be unlocked, and don't try to spin. Instead they queue themselves at
> 	// the tail of the wait queue.
> 	//
> 	// If a waiter receives ownership of the mutex and sees

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-mutex-002` / B062 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 2 | `go-rwmutex-001` / B071 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 3 | `go-pool-004` / B024 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 4 | `go-mutex-005` / B088 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |
| 5 | `go-pool-003` / B023 | INSUFFICIENT | Public Go implementation contains no measurement of these private production locks. Time constants or runtime_nanotime are not measured median latency. |

### go-holdout-11

For Go 9.99, what are the new guarantees of `WaitGroup.Go`?

**Required evidence absent:** A matching Go 9.99 source/version and WaitGroup.Go contract; this corpus only supports the frozen Go 1.23.2 snapshot. Do not reinterpret another version as a forecast.

**baseline first result:** `go-waitgroup-000` — **INCOMPATIBLE**. Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases.[6]

> // Copyright 2011 The Go Authors. All rights reserved.
> // Use of this source code is governed by a BSD-style
> // license that can be found in the LICENSE file.
> 
> package sync
> 
> import (
> 	"internal/race"
> 	"sync/atomic"
> 	"uns

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-waitgroup-000` / B051 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 2 | `go-waitgroup-001` / B018 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 3 | `go-once-001` / B042 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 4 | `go-cond-001` / B038 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 5 | `go-pool-003` / B080 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |

**pivot first result:** `go-waitgroup-000` — **INCOMPATIBLE**. Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases.[6]

> // Copyright 2011 The Go Authors. All rights reserved.
> // Use of this source code is governed by a BSD-style
> // license that can be found in the LICENSE file.
> 
> package sync
> 
> import (
> 	"internal/race"
> 	"sync/atomic"
> 	"uns

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-waitgroup-000` / B051 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 2 | `go-waitgroup-001` / B018 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 3 | `go-once-001` / B042 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 4 | `go-cond-001` / B038 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 5 | `go-pool-003` / B080 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |

**fusion first result:** `go-waitgroup-000` — **INCOMPATIBLE**. Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases.[6]

> // Copyright 2011 The Go Authors. All rights reserved.
> // Use of this source code is governed by a BSD-style
> // license that can be found in the LICENSE file.
> 
> package sync
> 
> import (
> 	"internal/race"
> 	"sync/atomic"
> 	"uns

| Rank | Passage / blind ID | Decision | Reason |
|---:|---|---|---|
| 1 | `go-waitgroup-000` / B051 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 2 | `go-waitgroup-002` / B012 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 3 | `go-mutex-000` / B061 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 4 | `go-waitgroup-001` / B018 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |
| 5 | `go-once-001` / B042 | INCOMPATIBLE | Frozen Go 1.23.2 source cannot establish requested Go 9.99 WaitGroup.Go guarantees; version/method applicability mismatch, not a claim about live future Go releases. |

## Provenance and reproducibility

Evidence directory: `artifacts/relevance-review/9aa54f35-87f9-40dc-ac59-9daa1b771a61`.

- `blinded-pool.json`: original shuffled full passages/questions (no old labels/variant scores). SHA-256 `ca1bed74ed3fc939a1a4874fa34fac70d6344e40c2c7296e26a5e0402c7f74cf`.
- `adjudications-blinded.json`: 95 full raw decisions with verbatim quotes, reasons, confidence and source URLs/offsets/hashes; written before unblinding. SHA-256 `98d727cd328dc2c0c88a4388aaf707f04ea204e4d5e4904756f23251fcabc5ce`.
- `unblind-mapping.json`, `adjudications-unblinded.json`: 210 rank/variant mappings and selected-positive comparisons; `summary.json`: exact machine-counted totals.
- `supplementary-evidence-map.json`: source-anchored answer evidence alternatives, separate from unchanged historical judgments; `source-checks.json`, `pooled-source-checks.json`: exact source/slice/hash verification; `input-hashes.json` and `reviewed-source-hashes.json`: reproducibility hashes.
- Original raw results: `artifacts/pivot-language/run-20261019-a1/raw-results.json`; original frozen Go source receipts and text: same run’s `fresh_go/source-receipts.json` and `fresh_go/sources/*.raw` / `*.txt`. All original links preserved in pooled/raw artifacts. Reused no-answer source provenance checked against same run’s `reused/sources`.

### Original frozen Go source SHA-256

| Source | Raw SHA-256 |
|---|---|
| mutex | `507443584e79a36244c0c1800fe480632822be195f9f59f99fc3d2aef9c9b4a6` |
| rwmutex | `1252488d2494c163a57f148fa21c39f80a43ca4aa20e1a9426d5ea15d3c453a3` |
| once | `5cb3dc3e4b4fec79fe581e10425ed669de9bb775f89051aa9e151f3ae57a48d7` |
| waitgroup | `8c93cdfd66c456745dba90fa4a0deccbbf76f2deb3a321c891ef642b8254937c` |
| pool | `d613639cb20b77b0db9104bc0de2590f781f4ea3a01494619e521aa727114f99` |
| cond | `324314fd3a484897ce540a242f9de85d00407040c8cd2ee7db5d5761f5d14d4f` |

## Recommendation for the next frozen evaluation

Retain this run as diagnostic history. Before new inference, build a NEW question set with different Go examples plus bilingual/operator/negation, applicability and answerability controls. Freeze full questions, version scopes, complete evidence spans and graded pooled labels independent of expected-ID selection. Specifically define whether a “why” answer requires rationale rather than restating behavior, whether source code is standalone sufficient, and whether explicit “As with X” comparisons count (recommended: yes). Have a separate model review and optional human adjudicator resolve those edge cases and label additional candidate alternatives before score reporting. Human review is optional, but do not call any model-only exercise independent human validation.

Freeze candidate budget/ranker, reporting unit and ≥80% first / ≥90% higher target together with an answerable-coverage minimum and no-answer false-acceptance cap. Report accepted-correct/accepted-total, answerable accepted/rejected and no-answer false accepts, not selected-ID hit rate alone. Keep an untouched holdout unseen by translation/ranking tuning; freeze a new test after using this review to diagnose ranking. Prefer moving explicit rationale/Broadcast proof ahead of related passages, then verify on that fresh frozen set. No runtime activation is recommended from this review.

## Sources

[2] https://raw.githubusercontent.com/golang/go/ed07b321aef7632f956ce991dd10fdd7e1abd827/src/sync/cond.go — cond
[3] https://raw.githubusercontent.com/git/git/v2.47.0/Documentation/gitignore.txt — gitignore
[4] https://raw.githubusercontent.com/rust-lang/book/1500248d8f230566e4ec9f27fcbb8fe9e2898ab1/src/ch15-04-rc.md — rust-rc
[5] https://raw.githubusercontent.com/golang/go/ed07b321aef7632f956ce991dd10fdd7e1abd827/src/sync/rwmutex.go — rwmutex
[6] https://raw.githubusercontent.com/golang/go/ed07b321aef7632f956ce991dd10fdd7e1abd827/src/sync/waitgroup.go — waitgroup
[7] https://raw.githubusercontent.com/golang/go/ed07b321aef7632f956ce991dd10fdd7e1abd827/src/sync/once.go — once
[8] https://raw.githubusercontent.com/golang/go/ed07b321aef7632f956ce991dd10fdd7e1abd827/src/sync/mutex.go — mutex
[9] https://raw.githubusercontent.com/golang/go/ed07b321aef7632f956ce991dd10fdd7e1abd827/src/sync/pool.go — pool
[11] https://raw.githubusercontent.com/git/git/v2.47.0/Documentation/git-reset.txt — git-reset

# Official History Cache Reuse Design

## Goal

Ensure every formal strategy data preparation run scans the existing AlphaPilot OKX public OHLCV warehouse first, reuses every compatible completed partition across strategies and timeframes, and downloads only missing history or a newly closed tail. Preserve partially downloaded pages so a pause or restart does not restart the same partition from the newest candle.

## Boundaries

- Applies uniformly to `5m`, `15m`, `1h`, `4h`, and `1d` formal data contracts.
- Does not alter strategy logic, backtest gates, target R, universe ranking, Demo execution, or Live boundaries.
- A formal partition remains reusable only when its official manifest, canonical path, source endpoint, schema, and SHA-256 digest validate.
- Local or third-party research files remain valid for the research precheck but are never relabeled as OKX official evidence.
- The currently running external batch worker is not restarted or interrupted.

## Existing Behavior

Completed cross-contract partitions are already reusable, but each partition independently scans the manifest directory. A reused partition still checks for a newly closed tail, which is correct but can look like another download in the UI. In-progress checkpoints store only page counters; they do not store the fetched page rows, so a paused partial partition starts over.

## Design

### Manifest Index

At collection startup, load official manifest metadata once into a key-indexed catalog using `(instrumentId, timeframe, sourceEndpoint)`. Validation remains lazy: only candidates requested by the current contract are checked against the canonical root, file existence, and SHA-256 digest. The newest valid partition by `endTime` becomes the shared base.

The collector will use this catalog for every requested timeframe. A full base with no new confirmed candles is returned as reused. A base with a short new tail is merged with that tail and written as a new immutable canonical partition. A missing key performs an initial download.

### Durable Partial Chunks

While downloading a partition backwards from OKX, every bounded page batch is written to a contract/key-specific resumable chunk directory under `_alphapilot/tmp/official-resume/`. Checkpoint metadata records the chunk paths, accumulated row count, request count, and oldest cursor.

On resume, validated chunks are loaded and the request starts after the oldest persisted cursor. New pages are appended as additional immutable chunks. On successful completion, chunks are merged once with the shared base, deduplicated, validated, written to canonical Parquet, and removed. If the user pauses, the current buffered pages are flushed before returning `paused`.

Malformed or missing chunks fail closed: they are ignored or quarantined and the partition resumes from the last valid cursor. Completed canonical evidence is never replaced by an incomplete chunk.

### Progress Semantics

Checkpoint progress distinguishes:

- `contract_checkpoint_reuse`: exact completed contract partition.
- `shared_incremental_refresh`: verified completed cross-contract base plus only a tail check.
- `resuming_partial_download`: persisted partial chunks plus continued older-page download.
- `initial_download`: no compatible completed or partial data exists.

This allows the console to state what is being reused without changing the workflow API.

## Testing

- Verify the manifest directory is indexed once per collector run.
- Verify all requested timeframes use the same cross-contract catalog.
- Verify compatible completed partitions request only the missing tail.
- Verify interrupted initial downloads persist chunks and resume from the oldest saved cursor.
- Verify interrupted incremental refreshes merge shared base, saved chunks, and the final tail without duplicates.
- Verify corrupt chunks are not promoted to formal evidence.
- Run the focused data-foundation tests, then the complete test suite and compile check.

## Acceptance

After this change, repeated strategy runs do not redownload complete compatible history. They perform at most a tail refresh for an already covered partition. Paused incomplete downloads continue from durable rows instead of restarting. Formal provenance remains unchanged.

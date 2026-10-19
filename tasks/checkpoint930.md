# Implementation checkpoint930

Historical checkpoint, superseded by `submission930.md`: all six native builds now
completed, general suite265PASS and native photo checks30PASS. No Rust process is
left running. The old active-build/PID instructions below are historical only.

Isolated branch `fisiones-daguerre930`; owner codex-fisiones-producto, supervision926
also open. Public photo base c769427; incorporated vector ff98eb2 at b3cc3074.
Committed implementation checkpoints b21c6ef7, 8bc33c2f, 39a0a576 and35f16e3;
this checkpoint adds honest global-model messages/catalogue descriptions, owner
branding, common-photo pagination and the corresponding focused checks.

No CAS930 has been submitted and no self-review performed. No integration, push,
real-data migration, original app restart, GUI activation or model operation occurred.
Current root reviewer/coordinator is codex-rendimiento. The source API/MCP transfer
is implemented and checked; installed packaging and CUA are still unverified.

## Verified

- Cold owner/catalogue95; both modules initially OFF; static25 vector tools,
  659 commands, 57 vector MCP aliases, 31 photo operations, seven owner operations.
- Full general suite258 pass,13 skip, one model deselection115.33s. Initial250 pass,
  five failures, ten skips and one deselection120.24s remains recorded. Four failures
  concerned preserved backend contract/effective global selection and one the enlarged
  MCP catalogue. Corrected contract follow-up31 pass18.27s. No performance threshold
  was relaxed; concurrent two-job Rust builds were active during both full suites.
- Vector CLI/GUI release built entirely in this checkout. CLI SHA256
  517b739f89a446eca19a147962b27e7b5d47b04df9b39417beb28ecfe46862d2;
  GUI9f80f3df5a5dadb3d829cac27b23c4af8df62889b7bc341c5c085865578fe2db.
  Production native/bin headless checks6 pass3.74s: complete schema parity,
  historical original preserved, edit/undo/redo/reopen, three export formats and
  real photo/vector/photo transfer with persisted IDs/revisions/original SHA.
- Actual owner HTTP + stdio MCP complete flow1 pass7.75s, including modules OFF,
  explicit activation/demo/index, native error flag, stable ID reopen, real transfer,
  photo result ID and retained PNG Range206 download after Photos OFF.
- Causal repeated cancellation, timed-out native save reconciliation, owned editor
  save/exit barrier and failed editor-control startup ownership6 pass0.46s. No window.
- Final owner/global/caption/URL checks18 pass2.09s include actual native vector
  transfer and pagination over the real native photo store. Source titles, paths,
  prompts and opaque documents are not rewritten; only known URL fields change.
- Cinzel/SourceSans are self-hosted, native Vector uses owner identity/theme, and
  all native UI functions remain present. Final photo client build passes2.51s.
- Layers CLI completed while GUI linked; original document/photo assertions2 pass
  0.40s using this checkout target/release only. That is explicitly build-target QA,
  not the final production native/bin receipt.
- Vendored SDK unchanged. Exact global938 job pins/auth/no fallback/truncation are
  tested in inert transport. No live inference or global deployment is certified.

## Active compilation and next steps

Unified builder session8717: `.venv/Scripts/python.exe -u scripts/build_engines.py
--engine all`, CARGO_BUILD_JOBS=2. Started19Oct05:08 local. Layers CLI/GUI now exist
in native/bin; Develop began05:21. Log `tasks/native-photo-build930.txt` is still being
written and remains untracked. Do not interrupt the current build or start another
Rust build. The last observed cargo73596 belongs to this builder; PID observations
are historical and must be checked before operating on any process.

When it exits successfully, record SHA256 of all four binaries and run original
headless optional checks with DAGUERRE_NATIVE_TESTS=1 (inspect selectors to exclude
any GUI test). `tests/test_craft_engines.py` three real cases and compositor native
cases preserve existing Layers/Develop behaviour. Compare production static tools18
and243 against explicit metadata-only native discovery. No old checkout binary may
be copied into this worktree. No GUI test/model/real profile is authorised here.

After any failure, repair the actual cause and rerun the affected checks. Once those
receipts complete, update manual limits/inventory, commit log/report and submit930
with exact commits/tree for independent review. Root owns CUA, installed packaging,
integration and eventual task934 migration/registration. Do not claim any of them
complete from source/native CLI tests alone. `docs/MIGRATION930.json` is an inventory,
not evidence that actual data has been moved. App:daguerre-qa930 and port64846 were
released after the last stdio run; reacquire separately before any new listener.

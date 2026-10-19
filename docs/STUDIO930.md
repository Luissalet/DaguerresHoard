# Visual studio

Source candidate930 is under development and has not been independently reviewed,
integrated, installed or checked in a browser. No real user store has been opened.
The inherited photo functionality, including reference matching, Layers and Develop,
remains in the Photos module. The incorporated vector editor retains its own complete
client, native document format, 25 native tools, 659 commands and 57 public MCP aliases.
The owner's cold catalogue exposes 31 photo tools, 57 vector aliases and seven common
operations. Static catalogues are source build outputs, not runtime engine discovery.

## Build and launch from source

Use a private virtual environment with `requirements-lock.txt`. Build the client and
self-hosted fonts with `python scripts/build_studio_assets.py`. Build Layers/Develop
with `python scripts/build_engines.py`; build the vector CLI and editor with
`python daguerre_hoard/studio_native/durer/scripts/build_engine.py`. Cargo1.95.0 and
the locked workspaces are required. Builders default to two concurrent cargo jobs.
All code and binaries belong to this repository; neither retired repository nor its
running server is required. No dependencies or data are linked to another checkout.
This is a source build workflow; a complete installed wheel has not been certified.

Start through `python -m daguerre_hoard --help` or the existing launcher. Opening the
root page starts neither native library. Use Activate for Photos or Vector, then Open
to enter the complete native interface. `--demo` permits an explicit Prepare synthetic
demo operation after activating Photos; startup itself does not generate or index it.
Stopping closes admission, drains current operations, joins jobs/session threads and
closes owned native editor windows normally. An unsaved native editor may show its
save/discard dialogue: the module stays stopping until the window actually exits.
No process timeout is treated as successful OFF. Actual Windows dialogue behaviour
still requires the coordinator's CUA check; no native GUI was opened for these tests.
If cleanup fails, the app remains owned/stopping; Retry stop invokes its native
cleanup again. Reactivation waits for successful cleanup. The Windows close-window
transport is implemented; other platforms currently require closing an owned editor
manually before retrying OFF. No unsupported platform is silently reported stopped.

Previous database jobs left as running are shown as held without rewriting their
historical rows. Automatic maintenance is an explicit per-activation option, OFF by
default; it is not a promise to resume incomplete jobs. Existing editor PIDs are not
restored by default. Other modules remain available while one drains.

## Shared projects and files

Create a project on the owner page, activate both modules and select an indexed photo.
Photo to edit creates an actual vector project with a derived preview of the original,
saves its editable native document and records stable photo/vector identifiers and
content hashes. Original registered image bytes are never overwritten. Vector result
to Photos exports a real PNG, explicitly scans only the owned result folder and stores
the resulting native photo identifier. Each transfer keeps its snapshot, immutable
revision hash and receipt. Native object links open the actual photo lightbox or vector
project. Retained result downloads and project history remain available with modules OFF.

Existing photos stay in the owner's root data directory. Vector data is under `vector/`;
`studio-projects.sqlite3` holds common projects and `studio-artifacts/` derived sources
and results. No existing separate vector store has been automatically migrated. No scan
or copy of Luis's data is part of this implementation or its verification.

The common HTTP surface is `/api/studio/modules`, `/projects`, `/objects`, project
`/{id}/photo` and `/{id}/export`, plus `/artifacts/{project}/{sha256}`. MCP operations
are `visual_modules`, `visual_module_set`, `visual_projects`, `visual_project_create`,
`visual_project_photo`, `visual_project_export` and `visual_demo_prepare`. Discovering
the catalogue never enables a module; native calls while OFF return an explicit error.
The master family token authenticates owner MCP dispatch. Per-agent profile migration
across the two former products has not been certified.

## Models and checks

Text/vision calls compose the unmodified SDK with the owned global938 consumer. A job
pins endpoint, model and connection revision from the authenticated global descriptor;
completion requests carry all three expected fields. No local fallback, provider key,
model load or QA conversation is used. Unavailable, stale and truncated responses are
errors. Effective service deployment and live inference remain external acceptance
requirements; inert transport tests are not a live-model certification.

Current evidence is recorded under `tasks/`: cold discovery, lifecycle, exact global
pins, reference matching and causal cancellation/drain checks. Initial full photo suite:
250 pass, five contract failures, ten skips, one model deselection in120.24s while native
Rust builds ran. Follow-up contract verification passed31 tests; the final general suite
passed258 with13 skips and one model deselection in115.33s. Both results are preserved.
The vector CLI and editor were built from this checkout; six actual headless checks pass
against its production `native/bin`, including full schema/command parity, historical
copy/edit/undo/redo/reopen, SVG/PNG/PDF exports and real photo/vector/photo transfer.
Real owner stdio MCP also passes that complete transfer, reopen, OFF and retained PNG
Range206 download. No native editor window was opened. Layers/Develop release builds
and all30 original optional photo/compositor checks now pass, including actual Develop
exposure/export and original-byte preservation. Explicit metadata discovery of owned
production binaries matches all18 Layers and243 Develop schemas. The final general
suite passes265 with15 skips and one model deselection in92.10s; real-factory regressions
verify failed close retry and retained resources. Browser behaviour, GUI save dialogues
and real data continuity are not established by these CPU tests. The migration
inventory is `MIGRATION930.json`; it records expectations rather than a migration receipt.

## Installed Windows package

Build the existing owned assets and six native release binaries first, then run
`python -m build --wheel --no-isolation` with setuptools/wheel/build installed in
the development environment. Wheel assembly does not run Cargo, Node or a model.
The wheel is Windows x64 specific and contains the photo frontend, vector static
client, common UI/fonts/licences, frozen catalogues, bundled SDK data and all six
executables. It contains no profile, model weights or former checkout dependency.

`scripts/install_studio.py --wheel <wheel> --target <new-directory> --python
<external-python> --profile <profile-directory>` installs the locked dependencies
and owned payload to a new target outside the checkout. Installation does not
open or migrate the profile. Start `daguerre-run.cmd --no-browser` explicitly;
`daguerre-mcp.cmd` is the stdio entrypoint and only discovers tools until called.
The wheel also declares `daguerre-hoard` and `daguerre-mcp` console entrypoints.
The generated launchers use an external Python with isolation, not the source venv.

Installed resources are read-only product payload under `daguerre_hoard/resources`;
mutable data defaults to `%LOCALAPPDATA%/DaguerresHoard/data`, outside the target.
An explicit CLI data directory or `DAGUERRE_DATA_DIR` selects a profile, including
demo QA. `launch.json` may provide its default; caller environment wins. The selected
profile's `.env` fills missing environment variables without overwriting caller values.
Existing development flags, valid master token and backend configuration are retained.
No scan, job recovery, module activation or live inference is performed by installation.

The owned global sync close propagates an inner HTTP close failure and retains its
same client/loop/thread for another OFF. A retiring backend is removed from its owner
registry only after success. Real installed photo factories are probed with two close
failures and a successful third OFF; ON cannot replace the retained owner.
The owner inventories its parent and synchronous twin clients separately. Transport
failures retain their close operation even after HTTPX marks its client CLOSED;
successful resources are checkpointed and remaining resources retry before OFF.
The HTTPX0.28.1/httpcore1.0.9 composition is owned code, outside the vendored SDK.

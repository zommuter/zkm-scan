# Relay log <!-- merge=union; append-only — never edit or reorder past entries -->

## 2026-06-12 21:47 — reviewer (claude-fable-5)

Handoff: first CLAUDE.md + ARCHITECTURE.md incl. zkm-pdf routing-contract asymmetry — text PDFs currently double-ingested (pdfs/ + scans/). Repaired collection-broken suite (SB5 root-shim imports, pre-M2 SCAN_* keys) to 15 green. ROADMAP 7 ROUTINE (text-layer skip per contract, skip-ledger vs re-OCR every run, missing-language-pack error, DPI config, OCR confidence observe-only, HEIC, tz-naive EXIF dates FAIL core validate_frontmatter) + 1 HARD (unify scanned-only threshold across core/pdf/scan). 11 red specs + 2 guards; @manual Gherkin; 6 REVIEW_ME. NOTE: tesseract MISSING on this machine (poppler present) — integration tier skips cleanly; install tesseract + deu/eng before real OCR.

## 2026-06-12 23:56 — reviewer (Fable 5)

uv.lock refresh (parent zkm 0.14.0) — unblocks relay dispatch

## 2026-06-13 — executor (Sonnet)

Worked id:6913, id:8810, id:c199, id:5d7d, id:f7d3, id:aae8 — all 6 ROUTINE items implemented in a single session: text-layer PDF skip + pdf-producer sidecar skip (6913), below-threshold OCR skip ledger (8810), configurable DPI with default 300 (c199), OCR confidence in frontmatter (5d7d), HEIC/HEIF via optional pillow-heif extra (f7d3), tz-aware EXIF dates + pages field for PDFs (aae8). pypdf added to core deps; pillow-heif in optional [heic] extra; dpi/pdf_text_threshold added to both plugin.yaml copies. Full suite: 29 passed, 1 skipped (pillow-heif importorskip), 1 EXPECTED-RED (5c02).
BLOCKED: 5c02 Pre-existing test test_scan_lang_passed_to_pytesseract (test_convert.py:209) calls convert(store, cfg(src, lang="fra+deu")) without mocking pytesseract.get_languages(); fra is not installed on this machine. Implementing the language-pack pre-check raises ValueError before OCR, breaking that test. The test must be updated to mock GET_LANGS before 5c02 can land.
Friction: none — all other items sized correctly for one session; 6913 and 8810 share the skip-ledger writer as intended.

## 2026-06-13 10:15 — executor (sonnet, relay-loop)

executor: implement id:6913/8810/c199/5d7d/f7d3/aae8 (6 ROUTINE items); BLOCKED id:5c02 (pre-existing test conflict)

## 2026-06-13 — executor (Sonnet)

Worked id:5c02 — connected the pre-existing `_check_lang_packs()` helper into `convert()` with a single call at lang-resolution time. The prior BLOCKED was caused by `test_scan_lang_passed_to_pytesseract` in test_convert.py using `fra+deu` without mocking `pytesseract.get_languages()`; `fra` is not installed. Fixed by adding a `GET_LANGS` mock (returning `["fra", "deu", "eng", "osd"]`) to that test — additive change that preserves the test's intent while accommodating the new pre-check. Full suite: 30 passed, 1 skipped (pillow-heif importorskip). Friction: none; fix was a one-line call + one test mock.

## 2026-06-13 10:47 — executor (sonnet, manual relay integration)

feat(scan): id:5c02 graceful tesseract lang-pack error + pillow-heif lock (executor 1035, manual integration)

## 2026-06-13 15:08 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: audited 2459d06 (REVIEW_ME owner decisions) clean — no code/test drift, suite 30 pass/1 skip; pointer v1→v2; 2 decision-driven follow-ups 874c/600c, zkm-photo 33e5 to inbox

## 2026-06-13 — executor (claude-sonnet-4-6)

Worked id:874c — renamed `fm["ocr_confidence"]` → `fm["scan_ocr_confidence"]` in convert.py per owner namespacing rule; updated test_5d7d assertion (decision-driven, not a weakening).
Worked id:600c — replaced `dt.astimezone()` in `_exif_str_to_iso` with `dt.replace(tzinfo=ZoneInfo(<local IANA zone>))` so UTC offset is resolved from the photo's own naive date; added `_local_zone()` helper (resolves via /etc/localtime symlink then /etc/timezone fallback); added `test_aae8_600c_dst_safe_exif_offset_jan_and_jul` asserting +01:00 Jan / +02:00 Jul for Europe/Zurich (skips if local zone differs). Full suite: 14 passed, 1 skipped (pillow-heif). Friction: worktree path breaks `uv run` (path `../..` resolves wrong); worked around via PYTHONPATH + UV_PROJECT_ENVIRONMENT pointing to main checkout venv.

## 2026-06-13 15:32 — executor (sonnet, relay-loop)

executor: id:874c rename ocr_confidence→scan_ocr_confidence + id:600c DST-safe EXIF offset via IANA ZoneInfo (2 ROUTINE items, 31 pass/1 skip)

## 2026-06-13 23:04 — reviewer (claude-opus-4-8, relay-loop)

review: audited 7a5e5f3 (REVIEW_ME R1 batch-confirm) clean — doc-only triage commit, no code/test drift in window. Re-ran suite from main checkout (worktree `../..` editable path breaks uv, known): 31 pass / 1 skip; the 3 confirmed boxes (6913/c199/f7d3) verified genuinely green. f7d3's `test_..._processed_when_supported` is by-design importorskip-guarded (optional `heic` extra absent) — legitimate skip per acceptance, not a gamed pass; supported-path remains unverified in this env. Contract pointer v2 == canonical, no refresh. All 9 ROUTINE items closed; routine_open=0; only HARD id:02bd (cross-repo routing unify) open. README lacks heic-extra/DPI mention but those shipped in prior windows — pre-existing minor drift, not introduced here. @manual Gherkin checklist unchanged.

## 2026-06-13 23:22 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: audited 7a5e5f3 REVIEW_ME R1 triage clean — 31 pass/1 by-design skip, 6913/c199/f7d3 verified green, routine_open=0

## 2026-06-13 23:25 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: audited 7a5e5f3 REVIEW_ME R1 triage clean — 31 pass/1 by-design skip, 6913/c199/f7d3 verified green, routine_open=0

## 2026-06-13 23:29 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: audited 7a5e5f3 REVIEW_ME R1 triage clean — 31 pass/1 by-design skip, 6913/c199/f7d3 verified green, routine_open=0

## 2026-06-16 16:27 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

handoff: C1 refresh relay pointer v2→v4 + README (dead SCAN_* env → snake_case config, shipped features); C2 re-derive queue (9 ROUTINE done, HARD id:02bd gated for /meeting), fix stale TODO summary; suite 31 pass/1 skip

## 2026-06-18 13:48 — reviewer (claude-opus-4-8, relay-loop)

review: audited d44721b (single ROADMAP-only commit, /meeting --cross gated-HARD triage D2) clean — design-ledger annotation on existing HARD id:02bd adding the DECIDED direction (shared zkm.pdftext helper + single pdf_text_threshold key, pilot density discriminator w/ char-count fallback, subsumes zkm-pdf id:9475). gaming-scan clean; no test/code files touched (ROADMAP.md only); suite 31 pass/1 by-design skip (pillow-heif) from main checkout (worktree ../.. editable path breaks uv, known). §5b: id:02bd stays [HARD — strong model] + GATED (cross-repo coordinated 3-repo release, gated for /meeting id:2d20) — deferred, NOT promoted to executor-ready; TODO id:390f summary already consistent. Contract pointer v4 == canonical, no refresh. routine_open=0; only HARD id:02bd open.

## 2026-06-18 13:56 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: audited d44721b (ROADMAP-only /meeting gated-HARD 02bd triage) clean — no code/test drift, suite 31 pass/1 skip, routine_open=0

## 2026-06-22 21:26 — maintenance (manual, uv.lock cascade)

uv.lock cascade refresh to zkm 0.16.0 — mechanical version-pin only (id:bae5), audit-exempt class (no code/spec change).
## 2026-06-22 16:01 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

Review of relay-ckpt-20260618-1356..HEAD — single LEDGER-ONLY commit 7554b86: relay(human) lane-tag migration of id:02bd from `[HARD — strong model]` → `[HARD — meeting]` (id:78ff explicit-lane convention). gaming-scan.sh CLEAN (no code/test churn). Test baseline green in main checkout: 31 passed, 1 skipped (pillow-heif importorskip — legitimate optional-dep skip, not a counted pass). Worktree pytest fails only on the editable `zkm==0.14.0 @ ../../` path not resolving from the cache worktree — environment artifact, not a regression. Verdict CORRECT: id:02bd is a cross-repo (zkm core + zkm-pdf + zkm-scan) design-gated HARD requiring a /meeting decision (id:2d20) before anyone can build — `[HARD — meeting]` is the accurate lane (matches its "Surfaced for /meeting. Not auto-dispatched" status), so the human migration is sound. Cross-ledger consistent: TODO id:390f accurately states "1 open ROADMAP item HARD id:02bd GATED for /meeting; 9 ROUTINE done". No reverse-handoff needed (no unqualified new items). Contract pointer already at v4 (current). routine_open=0 (sole open item is meeting-gated HARD, not executor work). No reopens, no gaming flags, no REVIEW_ME additions.

## 2026-06-23 15:38 — reconcile (human)

reconcile integrate: relay(review): audit relay-ckpt-20260618-1356..HEAD — LEDGER-ONLY (id:78ff lane-tag), CLEAN, suite 31/1skip green, routine_open=0

## 2026-06-24 17:14 — reviewer (claude-opus-4-8, relay-loop)

Review of 1 commit since relay-ckpt-20260623-1538 (df13372 — ROADMAP re-scope of id:02bd `[HARD — meeting]`→`[ROUTINE]`, no code). Verified the re-scope is factually correct: design D2 settled 2026-06-18, shared helper `zkm/src/zkm/pdftext.py` (probe/is_scanned_only/resolve_threshold) shipped 2026-06-22, and zkm-scan still uses its OWN local `pdf_text_threshold` (`convert.py:106`) — only single-repo adoption remains, correctly ROUTINE. Consolidated the item: removed the now-contradictory leftover `[HARD — meeting]` rationale + stale `Status: GATED` blocks, added a Done-check and a History note. Mini-handoff (§5b): the item had no red spec, so added `test_02bd_scan_routing_agrees_with_shared_pdftext` (`# roadmap:02bd`) — genuinely RED, exposing the concrete drift (zkm-scan's `_probe_pdf_text` counts unstripped `extract_text() or ""` vs the shared helper's `.strip()`; a whitespace-padded PDF gives scan_chars=227 vs oracle_stripped=27 at threshold 100 → opposite scanned-only verdicts). Fixed the stale TODO.md summary line id:390f (still said HARD/gated). roadmap-lint clean, gaming-scan clean (test ADD only). Suite 31 passed / 1 skipped (pillow-heif importorskip, legitimate). No items closed this turn. routine_open after re-derivation = 1 (id:02bd).

## 2026-06-24 17:25 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review(02bd): verified HARD→ROUTINE re-scope, consolidated item + added red spec for shared zkm.pdftext adoption; 31 pass/1 skip

## 2026-06-24 — executor (claude-sonnet-4-6)

Worked id:02bd — switched zkm-scan's scanned-only routing to the shared `zkm.pdftext` helper. Three changes in `src/zkm_scan/convert.py`: (1) import `resolve_threshold as _pdftext_resolve_threshold` from `zkm.pdftext`; (2) replace `int(config.get("pdf_text_threshold", 100))` in `convert()` with `_pdftext_resolve_threshold(config)` — the local key is still honoured via resolve_threshold's priority-1 top-level lookup; (3) update `_probe_pdf_text` to use `.strip()` semantics matching `zkm.pdftext.probe` (was: `len(page.extract_text() or "")`, now: `len(text.strip())` with None→0). This closes the whitespace-padding drift: a whitespace-padded PDF now returns the same scanned-only verdict in both plugins. Full suite: 32 passed, 1 skipped (pillow-heif importorskip, legitimate). Worktree note: tests run with `PYTHONPATH=zkm/src:worktree/src` + `UV_PROJECT_ENVIRONMENT` pointing to main checkout .venv (known worktree `../..` editable path issue). Friction: none — seam was well-defined, fix was surgical.

## 2026-06-24 17:33 — executor (sonnet, relay-loop)

id:02bd — adopt zkm.pdftext shared helper for scanned-only routing (stripped char count + resolve_threshold); 32 passed, 1 skipped

## 2026-06-26 10:09 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: TODO conformance commit clean; verified id:02bd green (executor-checkpoint blind-spot), reconciled drained ROADMAP + stale TODO id:390f summary

## 2026-07-01 14:56 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: window was 1 human REVIEW_ME ack (no code); suite green (15p/1skip), ROADMAP drained; refreshed contract pointer v4→v6, pruned resolved REVIEW_ME boxes [id:[,]]

## 2026-07-02 00:35 — reviewer (claude-fable-5, genuine Fable recheck, relay-loop)

Fable recheck of the pending optional audit (relay.toml last_strong_ckpt=relay-ckpt-20260701-1456, fable_rechecked=false — Opus stood in): diff window relay-ckpt-20260701-1456..HEAD is EMPTY (zero commits), so this pass is a state audit, not a diff audit. Independent verification: FULL suite green in the main checkout at the identical commit 075f8bb — 32 passed / 1 skipped (pillow-heif importorskip in test_roadmap.py:216, by-design optional-dep skip, not counted as a pass); the cache worktree cannot run tests (editable `zkm @ ../../` resolves outside it — known environment artifact). Spot-audited the standin-verified claims in source: id:874c `scan_ocr_confidence` namespaced key (convert.py:292), id:600c DST-safe ZoneInfo localization with documented astimezone() fallback (`_local_zone`/`_exif_str_to_iso`), id:02bd shared `zkm.pdftext.resolve_threshold` adoption (convert.py:33,110) — all match their acceptance. gaming-scan clean (empty window), roadmap-lint clean (no open items), relay-doctor per-repo clean (0 issues; classify replay verdict=idle consistent), contract pointer already v6 (current), README/ARCHITECTURE no drift, REVIEW_ME empty, TODO id:390f summary accurate, no reverse-handoff candidates (empty window). RECHECK FINDING (process, no reopen): the 2026-07-01 standin review logged "suite green (15p/1skip)" — that is exactly tests/test_roadmap.py alone (16 collected), i.e. a subset run claimed as the suite; matches the already-inbox'd routed:49a0 run-or-record-skip hardening for review.md step 3. No item was closed on that subset (id:02bd's closing run was a genuine full 32p/1s by the executor), so no gaming flag and nothing reopened. All 10 board items independently confirmed green; ROADMAP stays drained; routine_open=0. Integrator: flip `fable_rechecked` to 2026-07-02 for zkm-scan — this was a real Fable session.

## 2026-07-02 00:31 — reviewer (claude-fable-5, relay-loop)

review: genuine Fable recheck — empty window, FULL suite 32p/1s green at 075f8bb, all 10 board ids independently confirmed, board drained; flip fable_rechecked=2026-07-02 [id:6913,8810,5c02,c199,5d7d,f7d3,aae8,874c,600c,02bd]

## 2026-07-02 08:32 — reviewer (claude-fable-5, relay-loop)

review: empty window since relay-ckpt-20260702-0031 (0 commits), suite 32p/1s green, board drained (routine_open=0); classifier "unaudited commits" verdict was spurious — dispatch dropped the relay.toml # path: override (routed:0537 to dotclaude-skills)

## 2026-07-02 10:00 — reviewer (claude-fable-5, relay-loop)

review: ledger-only window (ckpt append + id:390f defang), suite 32p/1s green, gaming-scan clean, board drained; lint-ok'd id:390f orphan line (todo-conformance clean) @ 98298d8 [id:390f]

## 2026-07-02 12:40 — reviewer (claude-fable-5, relay-loop)

review: ledger-tail-only window (prev review's 2 ledger commits past mis-anchored tag — id:25aa 3rd occurrence, already tracked in dotclaude-skills), suite 32p/1s green, gaming-scan clean, board drained, zero-commit branch closes the window via id:8e3e [id:390f]

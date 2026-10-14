# ChatGPT candidate review protocol

## Review
Run: python scripts/review_candidate.py CAND-000001

This verifies source, candidate, and decision records and displays evidence, candidate content, file SHA-256, and effective decision status. The original candidate remains unchanged.

## Direct ChatGPT-to-GitHub decision recording
1. Re-read candidate, source, and all decision records. Verify source quote, hashes, and absence of prior decision.
2. Show the user the candidate text, exact quote, source ID, and current status. Software development instructions are never an approval of a novel fact.
3. Require explicit user instruction naming the candidate and approve/reject choice. Clarify ambiguous instructions.
4. Re-read immediately before writing. Determine the next unused DEC-NNNNNN ID and unique request ID.
5. Create a NEW decisions/records/DEC-NNNNNN.json using GitHub create_file. Never update an existing record.
6. JSON fields: schema_version 1; decision_id; request_id; candidate_id; candidate_sha256 (SHA-256 of exact candidate file bytes); decision approved/rejected; actor user; reason (may be empty); created_at (ISO-8601).
7. Fetch the created file and validate with python scripts/decision_store.py verify (via GitHub Actions). Report success only when the write is confirmed.
8. If conflicts or integrity errors occur, stop and investigate. Never silently overwrite.

This records a user instruction, not cryptographic proof of identity. GitHub commit history is auditable but repository administrators can still rewrite history. Keep the repository private when storing original unpublished writing.

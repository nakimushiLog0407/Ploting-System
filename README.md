# Novel Source Archive — Stage 1

GitHub repository files are the storage system. No database, external API server, or third-party Python packages are required. Use a **private** GitHub repository.

## Recommended browser-only setup

1. Upload all contents of this folder into the root of a **private** GitHub repository.
2. Open the repository's **Code → Codespaces → Create codespace** (if available on your account). Alternatively, clone the repository on a Linux/macOS computer with Python 3.10+.
3. In the terminal, create `input.txt` using a text editor. Paste the original passage without changing it. Do not use `echo` if exact newlines matter. Confirm its content before saving.
4. Run:

   ```bash
   python scripts/source_store.py save --file input.txt --request-id idea-20261014-001
   python scripts/source_store.py verify
   python scripts/source_store.py read SRC-000001 --output restored.txt
   cmp input.txt restored.txt
   ```

5. Save the archive files to GitHub **together in one commit**:

   ```bash
   git add sources/records sources/payloads
   git commit -m "Archive source SRC-000001"
   git push
   ```

6. Check **Actions → Verify source archive**. This workflow verifies the committed records and runs automated tests.

**Do not commit `input.txt` or `restored.txt`** unless you deliberately want extra copies of your original text. Delete them after confirming the round trip. If using a shared computer, consider the privacy implications of local files.

## Commands

- `python scripts/source_store.py save --file input.txt --request-id unique-001`
- `python scripts/source_store.py read SRC-000001 --output restored.txt`
- `python scripts/source_store.py verify SRC-000001`
- `python scripts/source_store.py verify` (all sources)
- `python -m unittest discover -s tests -v`

The same request ID with identical UTF-8 bytes returns `already_saved` and the original source ID. Reusing an ID with different bytes fails. Identical text with a **different** request ID is allowed (a distinct intentional submission).

The script saves the **exact UTF-8 bytes of the input file**, including BOM, spaces and newline styles. It never normalizes text or line endings. `read` without `--output` writes raw bytes to stdout. `read --output` refuses to overwrite an existing file. Git itself may alter line endings if `.gitattributes` is not configured; the included `.gitattributes` marks payloads as binary to prevent Git text conversions.

## Important limitations

- This version archives a **file supplied by the user**, not an automatically captured ChatGPT message. It cannot prove ChatGPT copied a chat message exactly. Compare the original before registration.
- A record and its payload are created as two local files. If the process is interrupted between writes, verification **fails closed**; repair the incomplete operation before saving again. A single Git commit includes both files atomically at the repository level.
- Local locking uses Linux/macOS `fcntl` and protects only writers sharing the same filesystem. **Do not register simultaneously from multiple independent Codespaces/clones.** Pull the latest branch first and use one writer; resolve push conflicts without overwriting previously committed records.
- GitHub permissions must be set so ordinary users/AI cannot bypass review and directly change the protected branch. The workflow detects changes but does not itself enforce branch protection. In a private repository, configure branch rules if available on your plan.
- SHA-256 detects accidental changes and corruption; it does not prevent an authorized editor from rewriting both payload and metadata. Git history, branch protection, and independent backups are required for stronger tamper resistance.
- The repository itself is not an independent backup. Keep an additional offline or separate-location copy.
- The first-stage code has no ChatGPT connector or automatic action trigger. These must be tested separately.

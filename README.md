# Sustainability Document Hub

Front end for the Okanagan College sustainability evidence base.
Maintained by the SustainOC team. Internal reference.

## What is in this repo

| File | Purpose |
|---|---|
| `index.html` | The catalogue interface. Self-contained: all CSS, JS and logos inline. Reads `catalogue.json` at load. |
| `catalogue.json` | Every record with its metadata and links. The machine-readable version of this site. |
| `catalogue.csv` | Same content, for Excel. |
| `manifest_all.csv` | Source data for the peer library (392 rows), produced by the library build. |
| `oc_seed.csv` | Source data for the Okanagan College collection. |
| `tools/build_catalogue.py` | Regenerates `catalogue.json` and `catalogue.csv`. |
| `Run-FilesPresent.cmd` | Double-click launcher for the inventory. Self-contained, always pauses. Use this. |
| `INVENTORY-manual.txt` | Paste-one-line fallback if the launcher is blocked. |
| `tools/Get-FilesPresent.ps1` | Lists what is actually in the library clones, for reconciliation. |
| `.nojekyll` | Stops GitHub Pages running Jekyll, which would hide any `_`-prefixed folder. |
| `robots.txt` | Keeps this out of search indexes. |

The PDFs themselves are not here. They live in the library repositories and are
addressed by `catalogue.json`.

## Adding or updating documents

1. Add the files to the library repository and push.
2. Add the matching rows to `manifest_all.csv` (peers) or `oc_seed.csv` (OC).
3. Take an inventory of what is actually in the clones. **Double-click
   `Run-FilesPresent.cmd`.** It finds the clone folders itself, writes
   `files_present.csv`, prints the size breakdown, and keeps the window open.
   Either repo-relative or full paths are accepted in that CSV.
   If it cannot find the clones it asks for the path, so you can also drag the
   folder that holds them onto the launcher.

   The launcher is self-contained. It does not run the `.ps1`, it passes the
   inventory to PowerShell as a command, which a locked-down execution policy
   cannot block. It always pauses at the end, pass or fail.

   If the window still will not stay open, use `INVENTORY-manual.txt`. That
   route needs no script file at all: open PowerShell in the folder holding the
   clones and paste one line.

   Do not use right-click "Run with PowerShell" on `tools\Get-FilesPresent.ps1`.
   That starts in the wrong folder, and on a managed device Group Policy
   overrides the execution policy so the script never runs.

4. Rebuild the catalogue:

   ```
   python tools/build_catalogue.py manifest_all.csv files_present.csv
   ```

   This writes `catalogue.json`, `catalogue.csv`, and `unmatched_files.csv`
   (anything sitting in a clone with no matching manifest row). It also prints
   how many catalogued documents have no library copy. Those records fall back
   to the publisher link rather than showing a dead link.

5. Commit `catalogue.json` and `catalogue.csv`. Pages redeploys in under a minute.

Nothing in `index.html` needs editing when documents change. If a library
repository is ever added, renamed or merged, edit the `SOURCES` block at the top
of `build_catalogue.py` and rebuild.

## Previewing locally

Browsers block local file reads, so opening `index.html` from disk shows a load
error. Serve the folder instead:

```
python -m http.server
```

Then open `http://localhost:8000`.

## Contact

Corrections and missing documents go to the SustainOC team at
`sustainoc@okanagan.bc.ca`.

## Classification

Records carry an `access` value. `Restricted` records deliberately carry no
link: the CPTED and accessibility assessments identify physical security
weaknesses and must not be published to an open URL. Request those from the
SustainOC team. Nothing in the Okanagan
College collection is mirrored to a public repository.

Run the MEDIA HEALTH CHECK operation. This is a **read-only** audit of the Sonarr/Radarr libraries that writes a report to the vault. Do NOT delete, rename, or move files — only inspect and report. The user reviews the report and decides what to act on.

## Configuration

- **TV Shows root**: `/mnt/media/Plex/TV Shows/` (Sonarr)
- **Movies root**: query Radarr API for `rootfolder[0].path`
- **Sonarr API**: `http://localhost:8989/api/v3/`
  - API key: `$SONARR_API_KEY` env, or `sudo grep ApiKey /var/lib/sonarr/config.xml`
- **Radarr API**: `http://localhost:7878/api/v3/`
  - API key: `$RADARR_API_KEY` env, or `sudo grep ApiKey /var/lib/radarr/config.xml`
- **Report destination**: `_llm/status/media-health.md` in the vault (read `vault-config.md` for vault path)
- **Previous report**: same path — read it first to compute deltas (new/fixed issues)

If an API key is missing, write a stub report flagging the missing env var and exit — don't guess.

## Checks

Each check below should populate one section of the report. Findings are categorized:
- **ERROR** — broken state Sonarr/Radarr will refuse to handle (missing folders, API/disk mismatch, duplicates)
- **WARN** — cosmetic/inefficient (release-style names, nested junk folders, empty dirs)
- **INFO** — stats and trends

### 1. TV folder naming compliance
- List any top-level TV folder not matching `Show Name (YYYY)$` — flag as WARN with proposed canonical name (use Sonarr `/api/v3/series/lookup?term=` to suggest correct title+year).
- List any folder with release tags (`S01.COMPLETE`, `1080p`, `WEB-DL`, `BluRay`, `[TGx]`, `[rartv]`, `x265`, `H264`, `HEVC` in the folder name) — flag as WARN.
- Skip `.stfolder` and any folder Syncthing-marker-named.

### 2. TV season structure
- For each show folder, verify it contains `Season NN/` subdirectories (zero-padded, two digits).
- Flag single-digit `Season N/` as WARN (`Season 1` should be `Season 01`).
- Flag media files (`.mkv`, `.mp4`, `.m4v`, `.avi`) at the top level of a show folder (not inside a `Season NN/`) as ERROR.
- Flag non-`Season NN` subdirectories inside show folders (e.g., release-style subfolders, leftover `s01/`, `Subs/`, `Sample/`) as WARN with file-type breakdown (videos / subs / images / junk).

### 3. Sonarr ↔ disk consistency
- `GET /api/v3/series` — for each `series.path`, check the folder exists. Missing → ERROR.
- `GET /api/v3/rootfolder` — read `unmappedFolders[]`. Each unmapped folder (except `.stfolder`) → WARN ("not imported to Sonarr yet").
- For each Sonarr series, run `GET /api/v3/episode?seriesId=N` and count files Sonarr knows about vs. files on disk. Mismatch → INFO.

### 4. TV duplicates
- Group Sonarr series by `tvdbId`. Any duplicates → ERROR.
- For each TV folder pair where one folder's name is a substring of another (case-insensitive, ignoring year and release tags), flag as WARN ("possible duplicate, manual review needed").

### 5. Movie folder naming + Radarr consistency
- Same approach for Radarr root folder. Movies should be `Movie Name (YYYY)/Movie Name (YYYY).ext` (Radarr's canonical layout).
- Flag any movie folder containing a `Season NN/` subdirectory → WARN (likely a misplaced TV show).
- Flag any nested release subfolder inside a movie folder → WARN.
- `GET /api/v3/movie` (Radarr) — confirm each `movie.path` exists. Missing → ERROR.

### 6. Junk files
- Count `.nfo`, `.txt` (matching `RARBG.txt`, `[TGx]Downloaded*`, `NEW upcoming releases*`), `.parts`, `.url` files across both roots. Report total count + estimated total size as INFO.
- Note: do NOT delete them. Just report.

### 7. Disk health
- `df -BG` for each root's filesystem. Report free space, % used.
- If < 10% free → ERROR; < 20% free → WARN.
- Compare with previous report's "% used" to show trend ("disk grew 3% since last check").

### 8. Sonarr/Radarr lookup confidence
- For each top-level folder, hit Sonarr/Radarr lookup. If the top result's title+year doesn't match the folder name → WARN ("Sonarr's auto-suggest would pick: X — manual import required").

## Report format

Write to `_llm/status/media-health.md`:

```markdown
---
type: llm-generated
generated: YYYY-MM-DD HH:MM
---
# Media Library Health — YYYY-MM-DD

## Summary
- TV shows: N folders, M issues (X errors, Y warnings)
- Movies: N folders, M issues (...)
- Disk usage: X% used (Δ vs last check)
- New issues since last check: N
- Resolved since last check: M

## ERRORS
(one bullet per issue — what + which file + proposed fix command)

## WARNINGS
(grouped by category — naming, structure, dupes, junk)

## INFO
(stats, trends, lookup confidence breakdown)

## Suggested cleanup commands
(bash snippets the user can review and run manually — never auto-executed)
```

Append a line to `_llm/log.md` with the run summary.

Finally: open the report in Obsidian via `obsidian open vault="VAULT_NAME" path="_llm/status/media-health.md"` if running interactively. Skip the open step in headless mode.

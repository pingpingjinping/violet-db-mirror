# violet-db-mirror

GitHub Actions mirror for Violet metadata and mobile database snapshots.

The scheduled workflow:

1. builds the existing `fast-hsync` collector from `pingpingjinping/violet`;
2. restores the previous full state DB;
3. synchronizes Hitomi and ExHentai;
4. builds an incremental delta;
5. exports the Korean mobile DB snapshot;
6. publishes the updated files to the `db-state` release.

## Secret

Create an Actions repository secret named `EH_COOKIE` containing the full cookie string used for ExHentai:

```
ipb_member_id=...; ipb_pass_hash=...; igneous=...
```

The workflow never prints the cookie value.

## Adding another language database later

The app-side selector already understands these database types:

| App type | `Language` value in DB | Release asset |
| --- | --- | --- |
| `ko` | `korean` | `rawdata-korean.db` |
| `en` | `english` | `rawdata-english.db` |
| `ja` | `japanese` | `rawdata-japanese.db` |
| `global` | no language filter | `rawdata.db` |

So adding English, Japanese, or global support does **not** require another app change as long as these names are kept.

### 1. Export the snapshot

The current exporter is `scripts/export-korean.py`. Either generalize it to accept a language argument or add equivalent exporters for the new snapshots.

For a language-specific DB, copy rows from `HitomiColumnModel` with the normalized language value:

```sql
WHERE lower(trim(Language)) = 'english'
```

Use `japanese` for Japanese. The global DB should not apply a language filter.

Keep the same validation used by the Korean exporter:

- copy the `HitomiColumnModel` schema;
- copy the table indexes;
- run `PRAGMA quick_check`;
- reject an empty export;
- write to a temporary file and replace the final file only after validation succeeds.

### 2. Keep the release filenames exact

The iOS app derives the asset name from the selected DB type, so the filenames are part of the client/server contract:

```text
rawdata.db
rawdata-korean.db
rawdata-english.db
rawdata-japanese.db
```

Do not rename these unless the app's `SyncManager.createRawdbPostfixiOS()` mapping is changed too.

### 3. Make `syncversion.txt` point to the base URL

For multi-language snapshots the `db` entry must point to the common **base** URL, not directly to the Korean file.

Example:

```text
db 1789900000 https://github.com/pingpingjinping/violet-db-mirror/releases/download/db-state/rawdata
```

The app appends the selected suffix itself:

```text
ko     -> -korean.db
en     -> -english.db
ja     -> -japanese.db
global -> .db
```

Therefore a manifest URL ending in `rawdata-korean.db` is not suitable once multiple language DBs are enabled.

### 4. Update `.github/workflows/sync-db.yml`

When a new snapshot is enabled, update the workflow in all relevant places:

- download the previous release asset when preserving old snapshots is useful;
- run the exporter after `fast-hsync`;
- validate the exported row count and language;
- include the new file in `gh release upload db-state ... --clobber`;
- optionally add its size/hash to `sync-status.json` and the release notes.

The Korean export currently shows the intended location for these steps.

### 5. App changes are only needed for a brand-new language

Korean, English, Japanese, and global are already mapped by the app. If a different language is added later, update the app-side mappings in `violet-release` as well:

- the DB selector UI;
- `SyncManager.createRawdbPostfixiOS()`;
- `SyncManager.translateToLanguage()`;
- any default/fallback DB selection logic.

For example, adding Chinese would require the app to expose `zh` again and the mirror to publish `rawdata-chinese.db`.

## Notes

- The full/global DB can be much larger than a language-specific snapshot, so consider storage and download cost before publishing `rawdata.db`.
- The mirror's state database (`violet-state.db.zst`) is the collector state and is separate from the mobile snapshots.
- Pi/mobile-server snapshot generation is a separate deployment path. Changes here do not automatically create the corresponding files on the Pi.

# violet-db-mirror

Experimental GitHub Actions collector for Violet metadata.

The first stage only verifies that a GitHub-hosted runner can:

1. build the existing `fast-hsync` collector from `pingpingjinping/violet`;
2. fetch a small Hitomi ID range and create a SQLite DB;
3. optionally reach ExHentai with an authenticated cookie stored as the `EH_COOKIE` Actions secret.

No production DB is published yet. After the connectivity test passes, this repository can be extended into a 6-hour incremental DB pipeline.

## Secret

Create an Actions repository secret named `EH_COOKIE` containing the full cookie string when testing ExHentai:

```
ipb_member_id=...; ipb_pass_hash=...; igneous=...
```

The workflow never prints the cookie value.

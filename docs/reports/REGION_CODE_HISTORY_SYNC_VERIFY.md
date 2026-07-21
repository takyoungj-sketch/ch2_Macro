# region_code_history sync verify

## Design

- **Interim SSOT:** `land_stats.region_code_history` (replicate, do not fork).
- **Targets:** `built_stats`, `collective_stats` local copies for JOIN/API.
- **Long-term:** CH2 Macro shared region master (`region_codes` + `history`), not Land-owned.
- **Excluded:** unresolved / `split` (no auto rows).
- **Ledger:** never UPDATE `beopjungri_code`.

- dry_run=False
- land allowed-type rows: **191**

## Sync stats

```json
{
  "built_stats": {
    "history": {
      "before": 0,
      "after": 191,
      "upserted": 191,
      "dry_run": false
    },
    "region_codes": {
      "land_rows": 382,
      "written": 382,
      "dry_run": false
    }
  },
  "collective_stats": {
    "history": {
      "before": 0,
      "after": 191,
      "upserted": 191,
      "dry_run": false
    },
    "region_codes": {
      "land_rows": 382,
      "written": 382,
      "dry_run": false
    }
  }
}
```

## Integrity

```json
{
  "land_n": 191,
  "targets": {
    "built_stats": {
      "history_n": 191,
      "missing_vs_land": 0,
      "extra_vs_land": 0,
      "sample_sute_canon": "4377025626",
      "sample_hwaseong_canon": "4159325021",
      "ok": true
    },
    "collective_stats": {
      "history_n": 191,
      "missing_vs_land": 0,
      "extra_vs_land": 0,
      "sample_sute_canon": "4377025626",
      "sample_hwaseong_canon": "4159325021",
      "ok": true
    }
  }
}
```

- integrity_ok: **True**

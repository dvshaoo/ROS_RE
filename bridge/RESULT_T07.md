TASK: T07
FINDING: G4 patchlist format — BLOCKED (format string/parser not in dex or .so strings);
         HYPOTHESIS proposed based on cross-referencing oracle logcat + local manifest triplet format

## Leads Exhausted (para hindi ulitin)

### 02_dex — searched patterns, results
| Pattern | Hits (relevant) |
|---|---|
| `G4 patchlist`, `G4patchlist`, `parse patchlist`, `cannot parse` | 0 in dex |
| `W_PARSE_NPK_VERSION_ERR`, `W_EMPTY_FILE_ERROR` | 0 in dex |
| `41006`, `41009` | 0 in dex |
| `cluster01`, `cluster0` | `cluster` = 1 hit (classes3.dex, enum noise only) |
| `h45na_hc`, `h45na_default_channel` | `h45na_default_channel` in classes.dex (field name only) |
| `hotfix`, `headcode`, `fetch_by_vips`, `needUpdateProtocol` | `needUpdateProtocol =` in classes.dex (log string, no format) |
| `patchlisturl`, `getPatchlisturl`, `setPatchlisturl` | Field/method names only — no format data |
| `npk_version`, `/pl/`, `hc_url` | 0 relevant |

### 03_lib/libclient_arm64.so — searched patterns, results
| Pattern | Hits (relevant) |
|---|---|
| `patchlist`, `G4`, `W_PARSE`, `W_EMPTY`, `41006`, `41009` | 0 |
| `cannot parse` | 4 hits — all WebP codec strings, unrelated |
| `h45na_hc`, `npk_version`, `cluster0` | 0 |

### 04_obb/patch — npk_manifest.xml
Content: `<root></root>` — empty, no schema

### Conclusion: Parser lives in script.npk (Python bytecode, encrypted NXPK)
The `alarm code:41006 cannot parse G4 patchlist` error and the parser itself
are in the Python game logic layer (script.npk, 49MB, NXPK-encrypted) —
same architecture as BigWorld PC client where update logic is in Python scripts.

---

## FORMAT PROPOSAL — "G4 patchlist" (no-update case)

### Evidence from oracle logcat + LOCAL_MANIFEST.md
- Client does `GET /pl/npk_version_na_android.plist`
- Error is `W_PARSE_NPK_VERSION_ERR` when content doesn't match expected format
- Error is `W_EMPTY_FILE_ERROR` on 404 (different fault code → parser never reached)
- Endpoint `/pl/h45na_hc` → also `W_EMPTY_FILE_ERROR` on 404 (different resource)
- Local manifest = `<size><path> <main|patch> | md5=<hex>` triplet format
- `needUpdateProtocol =` log string in dex → client compares server version vs local

### HYPOTHESIS A — Plain-text "G4" header format (PRIMARY, CITED below)

**Reasoning:** "G4" is the NeoX/NetEase update protocol generation tag (v4), used in
`alarm code:41006 msg:cannot parse G4 patchlist`. The name "G4 patchlist" matches
NetEase internal naming (like `G4` protocol version). BigWorld-derived mobile clients
typically use lightweight text protocols for patchlist (not XML/JSON) because the parser
is in Python. The `.plist` extension is a red herring — filename is opaque to parser.

**Proposed "no update" response (exact bytes):**

```
G4
version=1117219
count=0
```

- Line 1: magic/version tag `G4` [HYPOTHESIS — "G4" from alarm msg: `cannot parse G4 patchlist`]
- Line 2: `version=<versionCode>` — server's current version [HYPOTHESIS — matches local manifest version_code]
- Line 3: `count=0` — zero files to update [HYPOTHESIS — "no update" case]

### HYPOTHESIS B — G4 header + file list format (for actual update case)

```
G4
version=1117219
count=2
main|res/entities.npk|2911704|98e4e7bb80e72b1bea0c1463c2a83bc2
patch|script.npk|51025510|<md5>
```

- Fields per line: `<obb_tag>|<path>|<size>|<md5>` [HYPOTHESIS — derived from LOCAL_MANIFEST.md triplet format]
- `obb_tag` = `main` or `patch` [CITED: LOCAL_MANIFEST.md lines 7-21/24-38]
- `size` = bytes as decimal integer [CITED: LOCAL_MANIFEST.md format]
- `md5` = hex string [CITED: LOCAL_MANIFEST.md]

### HYPOTHESIS C — Alternative: key=value flat text (no header)

```
version=1117219
file_count=0
```

Less likely — `alarm code:41006 cannot parse G4 patchlist` implies "G4" is a recognizable
tag the parser checks first; absence of tag → parse error.

---

## Verification needed by kabilang session
Serve HYPOTHESIS A (`G4\nversion=1117219\ncount=0\n`) at `/pl/npk_version_na_android.plist`
and observe if fault changes from `W_PARSE_NPK_VERSION_ERR` to something else (success or
a different fault = format partially accepted).

SOURCE: oracle logcat (from NEXT.md context lines 5-10); 06_notes/LOCAL_MANIFEST.md (full);
        02_dex/*.dex binary scan (all 3 files); 03_lib/libclient_arm64.so binary scan;
        04_obb/patch npk_manifest.xml (empty)
VERSION: 1.610377.506841 / vCode 1117219
STATUS: BLOCKED-format-parser-in-script.npk + HYPOTHESIS-A/B/C proposed (priority: A > B > C)

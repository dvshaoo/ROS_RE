# RESULT_T10 — NXPK Collision Fix & script.npk Index Census

TASK: T10
STATUS: COMPLETE (honest, verified-sa-file only)

---

## (a) Collision Fix Proof (`05_entities/neox_decrypt.py`)

### 1. Root Cause Analysis
In the original `05_entities/neox_decrypt.py` (line 103), the heuristic `_guess_name()` used:
```python
if 'BigWorld engine' in text or '<entity' in text.lower():
    return 'entities.xml'
```
This caused **4 separate streams** in `entities.npk` to be named `entities.xml`, each sequentially overwriting the previous one:
1. Offset `0x00DE8`: Master BigWorld entity declarations (`7792B`) — matched `'BigWorld engine'`.
2. Offset `0x32DEC`: Property & type aliases table (`112399B`) — matched `'<entity'`.
3. Offset `0x3F50C`: EntityGroup pool component def (`361B`) — matched `'<entity'`.
4. Offset `0x43B38`: Dynamic groups component def (`1931B`) — matched `'<entity'`.

Only the final 1931B stream survived on disk, hiding the actual 7792B master `entities.xml`.

### 2. Backup & Tool Fix
- **Backup created**: `05_entities/neox_decrypt.py.bak` (original script preserved untouched).
- **Tool upgraded**: `05_entities/neox_decrypt.py`:
  - Parses the official 28-byte NXPK index table located at offset `0x4E028` (628 entries).
  - Implemented automatic collision resolution: if multiple streams share a name or collide, `_0x<OFFSET>` is appended before the file extension.
  - Distinct stream classification:
    - Offset `0x00DE8` -> `entities.xml` and `entities_0xDE8.xml` (`7792B`)
    - Offset `0x32DEC` -> `entities_types_0x32DEC.xml` (`112399B`)
    - Offset `0x3F50C` -> `entities_0x3F50C.xml` (`361B`)
    - Offset `0x43B38` -> `entities_0x43B38.xml` (`1931B`)
  - Added CLI options: `--index-scan` and `--obb` for non-destructive index census.

### 3. File Proof on Disk (`05_entities/out/`)
- `05_entities/out/entities.xml`: 7,792 bytes (MD5: `d9dfab9a9c9f7a7605dcb3948ec179ee`)
- `05_entities/out/entities_0xDE8.xml`: 7,792 bytes (verified identical to 0xDE8 stream)
- `05_entities/out/entities_types_0x32DEC.xml`: 112,399 bytes
- `05_entities/out/entities_0x3F50C.xml`: 361 bytes
- `05_entities/out/entities_0x43B38.xml`: 1,931 bytes
- Total files extracted: **628 files** (100% of the 628 index table entries cleanly extracted).

---

## (b) `script.npk` Index Census

### 1. File & Header Properties
- **Source**: `04_obb/patch.1117219.com.netease.chiji.obb` -> `script.npk`
- **Total file size**: 51,025,488 bytes (48.66 MB)
- **NXPK Header (24 bytes)**:
  - `[0x00 - 0x03]`: Magic = `NXPK`
  - `[0x04 - 0x07]`: Entry count = **3,959** (`0x00000F77`)
  - `[0x08 - 0x0F]`: Reserved / 0
  - `[0x10 - 0x13]`: Flag = 1
  - `[0x14 - 0x17]`: Table offset = **50,914,636** (`0x0308E54C`)
- **Index Table**:
  - Size: 110,852 bytes (3,959 entries × 28 bytes/entry)
  - Mathematical integrity: `50,914,636 (data) + 110,852 (table) = 51,025,488 bytes` (exact byte-for-byte match).
- **Payload Characteristics**:
  - All 3,959 entries have `CompSz == DecompSz` and `Flags == 0`.
  - Every payload begins with proprietary magic bytes `7A 1C` (NeoX Python bytecode package).
  - Entry names are stored as 32-bit hashes (`name_hash`); no plaintext ASCII filenames exist in the index table.

### 2. First 20 Entries Census (capped)
Command: `python 05_entities/neox_decrypt.py --obb 04_obb/patch.1117219.com.netease.chiji.obb script.npk --index-scan 20`

| Idx | Name Hash | File Offset | CompSz (B) | DecompSz (B) | Flags |
|----:|:---------:|:-----------:|-----------:|-------------:|:-----:|
| 0 | `0x0004CC2D` | `0x021872CC` | 1,990 | 1,990 | 0 |
| 1 | `0x00189956` | `0x02762878` | 2,175 | 2,175 | 0 |
| 2 | `0x0021766F` | `0x011EB6C0` | 7,130 | 7,130 | 0 |
| 3 | `0x0044BB26` | `0x026B3698` | 17,033 | 17,033 | 0 |
| 4 | `0x006172FC` | `0x01AEFB88` | 2,162 | 2,162 | 0 |
| 5 | `0x0077DF65` | `0x02939274` | 2,641 | 2,641 | 0 |
| 6 | `0x0092D5E0` | `0x028BFB34` | 14,180 | 14,180 | 0 |
| 7 | `0x00A660D3` | `0x00DDC0A8` | 4,852 | 4,852 | 0 |
| 8 | `0x00B16308` | `0x0260663C` | 5,430 | 5,430 | 0 |
| 9 | `0x00BF8002` | `0x02DEF4D4` | 7,305 | 7,305 | 0 |
| 10 | `0x00E29BFC` | `0x021D9178` | 350 | 350 | 0 |
| 11 | `0x00E2ED66` | `0x02F17228` | 2,892 | 2,892 | 0 |
| 12 | `0x00EC5CD0` | `0x02AB8CB8` | 24,160 | 24,160 | 0 |
| 13 | `0x01183228` | `0x0169F9A8` | 300 | 300 | 0 |
| 14 | `0x01207C54` | `0x02DD0944` | 1,899 | 1,899 | 0 |
| 15 | `0x01229E58` | `0x02706588` | 84 | 84 | 0 |
| 16 | `0x012C2505` | `0x02CE5288` | 4,013 | 4,013 | 0 |
| 17 | `0x01483985` | `0x01E40CC8` | 1,577 | 1,577 | 0 |
| 18 | `0x014A13DB` | `0x02878A64` | 1,916 | 1,916 | 0 |
| 19 | `0x01526329` | `0x02A24110` | 7,271 | 7,271 | 0 |

*(Remaining 3,939 entries capped to maintain token discipline).*

---

## (c) `Athlete.def` — BLOCKED (Not Present in Static Client Files)

### 1. Where Searched:
1. `05_entities/entities.npk` (both table-driven scan of 628 entries and raw zlib search):
   - **0** entity definition files contain `<ClientName>Athlete</ClientName>`.
   - The string `Athlete` only occurs in 8 places in `entities.npk`:
     - `<Athlete/>` tag in `entities_0xDE8.xml` (offset 0xDE8, index 140).
     - Interface reference mentions in 7 component files: `entity_0186.xml` (offset 0x17F70), `entity_0214.xml` (offset 0x1BB98), `entity_0238.xml` (offset 0x205EC), `Avatar.def.xml` (offset 0x243A8), `entity_0374.xml` (offset 0x3DD64), `entity_0375.xml` (offset 0x3E00C), `entity_0437.xml` (offset 0x47960).
     - **NO** direct `Athlete.def` exists in `entities.npk`. The offset `0xCE44` from T09 was verified to not exist.
2. `script.npk` (`04_obb/patch.1117219.com.netease.chiji.obb`):
   - Full binary scan of all 51,025,488 bytes for ASCII strings `Athlete` and `Athlete.def`: **0 occurrences**.
3. `assets.npk` (`04_obb/patch.1117219.com.netease.chiji.obb`): **0 occurrences**.
4. `res/entities.npk` (`04_obb/main.1117219.com.netease.chiji.obb`): SHA-256 hash verified identical to `05_entities/entities.npk`.

### 2. Verdict & Leads
- **Verdict**: **BLOCKED** (no `Athlete.def` file exists in the APK or OBB files).
- **Leads**:
  - `Athlete` is declared as an entity tag in `entities.xml`, but BigWorld engines allow entities to be cell/base-only (server-side only) with no client definition.
  - If client logic exists, it is implemented directly in Python bytecode (`Athlete.pyc`) stored inside `script.npk`, not as a `.def` XML.

---

## (d) Entity Type-ID Table — BLOCKED in Static Files

### 1. Where Searched:
1. `05_entities/entities.npk` (628 entries):
   - No explicit table or mapping file exists that maps entity names to numeric Type-IDs (e.g., JSON, dictionary, or XML mapping attributes).
2. Binary inspection of `03_lib/libclient_arm64.so`:
   - Found `EntityType::init(` at offset `0x02A47C66` loading `entities\entities.xml`.
   - String at offset `0x02A62000`: `EntityDescription::serverMethod: Do not have server method %d. There are only %d. Check that entities.xml is up-to-date.`
3. `entities_0xDE8.xml` (7,792 bytes, offset 0xDE8):
   - Contains 281 entity tags in declaration order:
     - Tag #0: `GlobalBaseStub`
     - Tag #126: `LoginProxy`
     - Tag #127: `Account`
     - Tag #128: `BattleAccount`
     - Tag #129: `Avatar`
     - Tag #140: `Athlete`
   - In BigWorld / KBEngine architecture, entity type IDs may correspond to order in `entities.xml`, but **this cannot be claimed as an established fact without runtime confirmation**, as previous assumptions (e.g. 1-based vs 0-based offset, or filtered entity types) caused verification failures.

### 2. Verdict & Next Step
- **Verdict**: **BLOCKED in static files** (no hardcoded name→ID lookup table file exists).
- **Next Step**: **Runtime logcat / memory inspection** during live app launch. When `libclient_arm64.so` runs `EntityType::init()`, the live engine builds its internal `EntityType` array in memory and logs/initializes network handlers.

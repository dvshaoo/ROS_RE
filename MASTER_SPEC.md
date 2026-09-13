# MASTER_SPEC.md — Verified Ground-Truth Facts (Rules of Survival v1117219)

Each entry below has a `source:line` citation from decompiled bytecode or other verified source. Unknowns go to BLOCKED.md.

## Protocol & Message IDs
- `W_PARSE_NPK_VERSION_ERR` = errcode 41006, msg "cannot parse G4 patchlist"
  - Source: `patch/tags.py:61-63`, `patch/antihijack.py:264-269`
- `_parse_npk_version_string()` parses hybrid format: `head` (CSV lines) + `##########` separator + `tail` (JSON)
  - Source: `patch/ResourcePatcher.py:403-420` (bytecode `lnotab` mapping)
- `_verify_npk_version()` triggers 41006 if `_parse_npk_version_string()` throws ANY exception
  - Source: `patch/antihijack.py:264-269`
- Version compare: `min_client_version`, `min_engine_version`, `min_patch_client_version`, `min_patch_engine_version`
  - Source: `patch/patch_mgr.py:348-470`

## G4 Patchlist Schema (T13 Verified)
- **Required format**: `##########` (10 hash chars) + valid JSON tail
- **Minimal no-update payload**: `##########\n{}` (13 bytes)
  - Hex: `23 23 23 23 23 23 23 23 23 23 0A 7B 7D`
- **Parser execution**: `head` = `""` → 0 iterations; `tail` = `"{}"` → `json.loads("{}")` returns `{}`
- **41006 eliminated**: Previous errors caused by missing `##########` separator and invalid tail JSON
- **Source**: `patch/ResourcePatcher.py:403-420`

## KeyError: 'type' Root Cause (T14 Verified)
- **Crash site**: `ResourcePatcher.py:1279`, `npk_file_type = version_info['type']`
- **Root cause**: JSON tail absent `"type"` key → Python `dict.__getitem__` raises `KeyError`
- **What object accessed**: `version_info` = `PatchCache.VERSION_INFO`, populated by `_parse_npk_version_string()` from G4 patchlist response
- **Also crashed later**: `ZeroDivisionError` at line 1285/1299 in `patch_size_calc` (downstream data format)
- **Fix requirements**:
  1. `"type": "package"` in JSON tail → triggers package mode (`useFirstPack=True`, `needPatch=False`)
  2. `"version": "1117219"` must be STRING, not int → `version_info['version'] + '/'` works in Python 2.7
  3. `"file_list": []` → makes `filesToPatch` empty, bypasses per-file iteration
  4. `"use_dlc_clothes": false` → disables DLC clothes downloading
  5. `/1117219/total_list` served as zlib-compressed cPickle `{}`
- **Source**: `patch/ResourcePatcher.py:1271-1285` (bytecode disassembly), `patch/patch_mgr.py:463`

## Decrypted Module Hashes (from OBB → script.npk)
| Hash (Hex) | Module Name | Offset in script.npk | Encrypted | Decrypted |
|:---:|---|---:|---:|:---:|
| `0x4CC04A3F` | `patch/ResourcePatcher.py` | `0x0276C580` (`41338240`) | 33,752 B | 48,715 B |
| `0x9942CA75` | `patch/antihijack.py` | `0x0268A00C` (`40411148`) | 9,061 B | 13,277 B |
| `0xE4578D82` | `patch/tags.py` | `0x026A46F0` (`40519408`) | 2,087 B | 3,222 B |
| `0x467B3ADF` | `patch/config.py` | `0x026882E8` (`40403688`) | 714 B | 1,031 B |
| `0x43DB3088` | `patch/patch_mgr.py` | `0x0269CA00` (`40487424`) | 28,531 B | 42,815 B |
| `0x7DB4633E` | `patch/patch_utils.py` | `0x0268CBD4` (`40422356`) | 8,124 B | 12,173 B |

## AES Key (from libclient_arm64.so)
- Key: `w5q6^C04SW!@e}ad` → bytes `77 35 71 36 5e 43 30 34 53 57 21 40 65 7d 61 64`
- Located at: `0x02B504E0` in `libclient_arm64.so`
- Used for: AES-128-ECB decryption of `script.npk` entries

## Successfully Extracted Data
- **458+ entity definitions** from `entities.npk` (NXPK format, zlib-compressed)
- **3,959 entries** in `script.npk` census (28-byte table at `0x308E54C`, all csz==dsz)
- **7 `ANDROID_URL` endpoints** from `assets.npk` module (dlc download table)
- **Entity type IDs**: LoginProxy=126, Account=127, Avatar=129, Athlete=140

## MITM Server Endpoints Served
- `GET /pl/npk_version_na_android.plist` → corrected plist with `type`, `version` string, `file_list`, `use_dlc_clothes`
- `GET /1117219/total_list` → zlib-compressed pickle (protocol 2)
- Other endpoints return 404 (mitm-serve-a)

---
*Verified facts only. Unknowns go to BLOCKED.md. Each claim cites source file and line (or bytecode offset).*
*Last updated: 2026-09-13*
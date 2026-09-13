# RESULT_T14 — KeyError: 'type' Root Cause Analysis & Exact Plist Tail Schema

**TASK**: T14 (KeyError-'type' kill — basahin ang decrypted modules)  
**STATUS**: COMPLETE (ROOT CAUSE IDENTIFIED, BYTECODE DISASSEMBLED & CITED DOWN TO EXACT INSTRUCTION OFFSETS)  
**MODE**: Static-only reverse engineering; NO live serving or emulator/device execution.

---

## 1. Executive Summary: What Caused `KeyError: 'type'`

The live oracle crash:
```text
Traceback: File "patch\ResourcePatcher.py", line 1279, in patch_size_calc
KeyError: 'type'
```

### Root Cause:
1. In `patch/ResourcePatcher.py` (`0x4CC04A3F`), line 1279:
   The function `patch_size_calc` executes:
   ```python
   npk_file_type = version_info['type']
   ```
2. **What object is accessed with `['type']`?**
   It is `version_info`, retrieved at line 1274 from `PatchCache.VERSION_INFO`.
   `PatchCache.VERSION_INFO` is populated directly by `_parse_npk_version_string()` from the G4 patchlist response (`head` + `tail` separated by `##########`).
3. **Why did it KeyError?**
   The `head` of the G4 patchlist only parses CSV lines into `<name>_size` and `<name>_md5`.
   All scalar configuration keys (`version`, `version_name`, `min_*_version`, `type`, `file_list`, etc.) MUST come from the JSON `tail` (`json.loads(tail)`).
   In T13, the served JSON tail was:
   ```json
   {"version": 1117219, "version_name": "1.610377.506841", "min_client_version": 0, "min_engine_version": 0, "min_patch_client_version": 0, "min_patch_engine_version": 0}
   ```
   **The key `"type"` was completely absent from the JSON tail dictionary.**
   Because Python dictionary subscript `version_info['type']` was executed without a `.get()` fallback, Python immediately raised `KeyError: 'type'`.

---

## 2. Python 2.7 Bytecode Disassembly & Line Citations

### (a) `patch/ResourcePatcher.py`: `patch_size_calc` (lines 1271–1285)
**Function**: `patch_size_calc(filesToPatch, context, settingLanguage, result, useDLCClothes)`  
**Code Object**: `co_argcount = 5`, `firstlineno = 1271`  
`co_varnames`: `['filesToPatch', 'context', 'settingLanguage', 'result', 'useDLCClothes', 'filesPatchInfo', 'version_info', 'npk_file_type', 'patch_version_dir', 'version_path', ...]` (indices: `6=version_info`, `7=npk_file_type`, `8=patch_version_dir`, `9=version_path`)  
`co_consts`: `[None, 'USE_LANGUAGE_FILTER', 'PatchCache.VERSION_INFO is None', 'error_code', 'type', 'version', '/', 0, 1.0629911572472126, 100, '/total_list', '/dlc_clothes_file_map', ...]` (indices: `4='type'`, `5='version'`, `6='/'`, `10='/total_list'`)

#### Bytecode Trace:
```text
L1274 [ 15] LOAD_GLOBAL   PatchCache (names[2])
L1274 [ 18] LOAD_ATTR     VERSION_INFO (names[3])
L1274 [ 21] STORE_FAST    version_info (varnames[6])

L1275 [ 24] LOAD_FAST     version_info (varnames[6])
L1275 [ 27] POP_JUMP_IF_TRUE -> byte 62 (if version_info is not None)
L1276 [ 30] LOAD_FAST     result (varnames[3])
L1276 [ 33] LOAD_GLOBAL   PatchConst (names[5])
L1276 [ 36] LOAD_ATTR     FAIL (names[6])
L1276 [ 42] LOAD_CONST    'PatchCache.VERSION_INFO is None' (consts[2])
L1276 [ 52] CALL_FUNCTION pos=2 kw=0
L1277 [ 59] RETURN_VALUE

--- CRASH SITE (Line 1279) ---
L1279 [ 62] LOAD_FAST     version_info (varnames[6])
L1279 [ 65] LOAD_CONST    'type' (consts[4])
L1279 [ 68] BINARY_SUBSCR               <--- CRASH: KeyError: 'type'
L1279 [ 69] STORE_FAST    npk_file_type (varnames[7])

L1280 [ 72] LOAD_FAST     version_info (varnames[6])
L1280 [ 75] LOAD_CONST    'version' (consts[5])
L1280 [ 78] BINARY_SUBSCR
L1280 [ 79] STORE_FAST    patch_version_dir (varnames[8])

L1281 [ 82] LOAD_FAST     patch_version_dir (varnames[8])
L1281 [ 85] LOAD_CONST    '/' (consts[6])
L1281 [ 88] BINARY_ADD                  <--- CRITICAL: 'version' MUST be string ("1117219"), NOT int!
L1281 [ 89] STORE_FAST    version_path (varnames[9])

L1287 [141] LOAD_GLOBAL   USE_TOTAL_LIST (names[9])
L1287 [144] POP_JUMP_IF_FALSE -> byte 167
L1288 [147] LOAD_GLOBAL   downloadTotalList (names[10])
L1288 [150] LOAD_FAST     patch_version_dir
L1288 [153] LOAD_CONST    '/total_list'
L1288 [156] BINARY_ADD
L1288 [157] LOAD_FAST     result
L1288 [160] CALL_FUNCTION pos=2 kw=0

L1290 [167] LOAD_FAST     useDLCClothes (varnames[4])
L1290 [170] POP_JUMP_IF_FALSE -> byte 193
L1291 [173] LOAD_GLOBAL   downloadDLCClothesInfo (names[11])
L1291 [176] LOAD_FAST     patch_version_dir
L1291 [179] LOAD_CONST    '/dlc_clothes_file_map'
L1291 [182] BINARY_ADD
L1291 [183] LOAD_FAST     result
L1291 [186] CALL_FUNCTION pos=2 kw=0

L1296 [218] SETUP_LOOP
L1296 [221] LOAD_FAST     filesToPatch (varnames[0])
L1296 [225] FOR_ITER      -> byte 747
L1296 [228] STORE_FAST    fileName (varnames[13])
...
L1308 [355] LOAD_FAST     version_info (varnames[6])
L1308 [358] LOAD_FAST     download_file_name (varnames[15])
L1308 [361] LOAD_CONST    '_updated' (consts[24])
L1308 [364] BINARY_ADD
L1308 [365] BINARY_SUBSCR
L1308 [366] STORE_FAST    npk_updated (varnames[16])

L1320 [459] LOAD_FAST     npk_file_type (varnames[7])
L1320 [462] LOAD_CONST    'package' (consts[31])
L1320 [465] COMPARE_OP    ==
L1320 [468] POP_JUMP_IF_FALSE -> byte 514 (if not 'package')
L1320 [471] LOAD_FAST     npk_updated (varnames[16])
L1320 [474] UNARY_NOT
L1320 [475] POP_JUMP_IF_FALSE -> byte 504 (if npk_updated is True)
L1321 [478] LOAD_GLOBAL   False
L1321 [484] STORE_SUBSCR  filePatchInfo['needPatch'] = False
L1322 [488] LOAD_GLOBAL   True
L1322 [494] STORE_SUBSCR  filePatchInfo['useFirstPack'] = True
L1323 [498] JUMP_ABSOLUTE -> byte 225 (CONTINUE NEXT FILE: SKIPS download_file_list!)
```

### (b) Critical Insight: Value of `"type"` and `"version"`
1. **`version_info['type']` value**:
   - Line 1320 explicitly tests: `if npk_file_type == 'package':`.
   - When `"type": "package"` AND `_updated == 0` (or `False`):
     `filePatchInfo['needPatch'] = False`
     `filePatchInfo['useFirstPack'] = True`
     The engine marks the files as already up-to-date, uses the base OBB pack (`useFirstPack`), and skips downloading any patch list or patch files.
2. **`version_info['version']` type**:
   - Line 1281 executes `version_info['version'] + '/'`.
   - In Python 2.7, this MUST be a `str`: `"version": "1117219"`.
   - If served as a JSON integer `1117219`, it raises `TypeError: unsupported operand type(s) for +: 'int' and 'str'`.

---

## 3. Keywords & Lifecycle Tracing

### (a) `patch_language` and `need patch for language!`
- **Module**: `patch/patch_utils.py` (`0x7DB4633E`), lines 18–35 (`getPatchLanguage`):
  ```python
  def getPatchLanguage():
      try:
          patch_version_path = os.path.join(ResourcePatcher.absDocRoot, 'patchVersion')
          with open(patch_version_path, 'r') as fp:
              ver = fp.read().strip()
          ver_info = ver.split('.')
          if len(ver_info) >= 4:
              return ver_info[3]
      except Exception:
          return None
  ```
  On a fresh client or when `absDocRoot/patchVersion` is missing or has fewer than 4 components, `getPatchLanguage()` returns `None`.
- **Module**: `patch/patch_mgr.py` (`0x43DB3088`), lines 611–618 (`VersionStage._check_language_patch`):
  ```python
  def _check_language_patch(self, settingLanguage):
      patch_language = patch_utils.getPatchLanguage()
      print 'patch_language:', str(patch_language)
      if patch_language is None or patch_language != settingLanguage:
          return True
      return False
  ```
- **Module**: `patch/patch_mgr.py`, lines 431–433 (`VersionStage.updateStage`):
  ```python
  need_language_patch = self._check_language_patch(settingLanguage)
  if need_language_patch:
      print 'need patch for language!'
  ```
  At line 444:
  ```python
  if patch_client_ver < min_patch_client_ver or need_language_patch:
      self._context.need_patch = True
  ```
  This is standard behavior: because `patch_language` is `None`, the game flags that language assets must be verified, and therefore invokes `ResourcePatcher.PatchSizeCalculator`.

### (b) `USE_LANGUAGE_FILTER`
- **Module**: `patch/ResourcePatcher.py`:
  - Line 65: `USE_LANGUAGE_FILTER = True` (module-level constant).
  - In `patch_size_calc` (lines 1272, 1331, 1364), `settingLanguage` is passed to `calcNpkPatchInfo` and `is_ignored_file`.
  - `is_ignored_file` (lines 1220–1260):
    Filters out language-specific files in `res/ui` and `common/international_data/` (e.g. `translate_code_<lang>`, `translate_properties_<lang>`) that do not match `settingLanguage`.

### (c) `LINYUAN___useDLCClothes` & `use_dlc_clothes`
- **Module**: `patch/patch_mgr.py`, lines 409–410 (`VersionStage.updateStage`):
  ```python
  useDLCClothes = info.get('use_dlc_clothes', False) and patch_utils.isLitePackage()
  print 'LINYUAN___useDLCClothes:', useDLCClothes
  ```
- If `"use_dlc_clothes": false` (or omitted) in the JSON tail:
  `useDLCClothes` evaluates to `False`.
  In `patch_size_calc` line 1290:
  `if useDLCClothes:` is skipped, preventing any attempt to download `/dlc_clothes_file_map`.

### (d) `file_list` & `filesToPatch`
- **Module**: `patch/patch_mgr.py`, line 463 (`VersionStage.updateStage`):
  ```python
  _filesToPatch = info.get('file_list', [])
  self._context.patchSizeCalculator = ResourcePatcher.PatchSizeCalculator(
      _filesToPatch, self._context, settingLanguage, useDLCClothes=useDLCClothes
  )
  ```
- **What is the list being iterated?**
  `filesToPatch` in `patch_size_calc` (line 1296: `for fileName in filesToPatch:`) is passed directly from `_filesToPatch`.
  By supplying `"file_list": []` in the JSON tail:
  `filesToPatch` is an empty list `[]`.
  The loop in `patch_size_calc` lines 1296–1346 executes 0 times.
  It skips all per-file subscript accesses (`_updated`, `_size`, `_md5`, `FILELIST_<name>`), proceeds directly to lines 1350–1354 (`needPatch = False`, `sizeToDownload = 0`), and reports `PatchConst.FINISH` (`(False, 0, 0)`).

### (e) `USE_TOTAL_LIST` and `/total_list`
- **Module**: `patch/ResourcePatcher.py`, lines 65, 1287–1288:
  ```python
  USE_TOTAL_LIST = True
  ...
  if USE_TOTAL_LIST:
      downloadTotalList(patch_version_dir + '/total_list', result)
  ```
  `downloadTotalList` calls `_fetch_http_data('1117219/total_list')`.
  It expects a zlib-compressed cPickle object:
  ```python
  data = _fetch_http_data(fileName)
  data = zlib.decompress(data)
  data = cPickle.loads(data)
  ```
  If this request returns a 404 error, `downloadTotalList` raises an exception and reports `PatchConst.FAIL_WITH_INFO` (`errcode 2055`).
  **Recommendation**: The MITM server should serve `/1117219/total_list` as:
  `zlib.compress(cPickle.dumps({}, -1))` (or Python 2 pickle protocol 2).

---

## 4. Exact Plist Payload Specification (Head + Tail)

To satisfy `_parse_npk_version_string` (T13) AND `patch_size_calc` (T14) with zero `KeyError`, zero `TypeError`, and zero download size:

### Plist Content:
```text
##########
{"type": "package", "version": "1117219", "version_name": "1.610377.506841", "min_client_version": 0, "min_engine_version": 0, "min_patch_client_version": 0, "min_patch_engine_version": 0, "file_list": [], "use_dlc_clothes": false}
```

### Field-by-Field Verification:

| JSON Key | Value | Expected Type | Consuming Location | Why Required / Safe |
|---|---|:---:|---|---|
| `"type"` | `"package"` | `str` | `ResourcePatcher.py:1279, 1320` | Prevents `KeyError: 'type'`; triggers package mode (`useFirstPack=True`, `needPatch=False`). |
| `"version"` | `"1117219"` | `str` | `ResourcePatcher.py:1280, 1281` | Concatenated with `'/'` (`patch_version_dir + '/'`). MUST be `str` to avoid `TypeError`. |
| `"version_name"` | `"1.610377.506841"` | `str` | `patch_mgr.py:447` | Used for version display / string formatting. |
| `"min_client_version"` | `0` | `int` | `patch_mgr.py:416` | Ensures client version is >= minimum (no forced full-client app update). |
| `"min_engine_version"` | `0` | `int` | `patch_mgr.py:440` | Ensures engine version is >= minimum (no forced engine update). |
| `"min_patch_client_version"` | `0` | `int` | `patch_mgr.py:849` | Bypasses client patch requirement. |
| `"min_patch_engine_version"` | `0` | `int` | `patch_mgr.py:831` | Bypasses engine patch requirement. |
| `"file_list"` | `[]` | `list` | `patch_mgr.py:463` -> `ResourcePatcher.py:1296` | Makes `filesToPatch` empty, bypassing iteration over NPK files and eliminating all `_updated`/`_size`/`_md5` sub-checks. |
| `"use_dlc_clothes"` | `false` | `bool` | `patch_mgr.py:409` -> `ResourcePatcher.py:1290` | Disables DLC clothes downloading (`LINYUAN___useDLCClothes: False`), skipping `/dlc_clothes_file_map`. |

---

## 5. Summary Table for Handoff

| Question | Finding | Citation |
|---|---|---|
| Object accessed with `['type']` | `version_info` (which is `PatchCache.VERSION_INFO`) | `ResourcePatcher.py:1274, 1279` |
| Line of failure | Line 1279 (`npk_file_type = version_info['type']`) | `ResourcePatcher.py:1279` (byte 62..71) |
| Subsequent required keys on `version_info` | `'version'` (MUST be string for line 1281 concatenation `+ '/'`) | `ResourcePatcher.py:1280..1281` |
| Source of list being iterated | `filesToPatch = info.get('file_list', [])` | `patch_mgr.py:463` |
| Reason for `need patch for language!` | Local `absDocRoot/patchVersion` missing/empty -> `getPatchLanguage()` returns `None` | `patch_utils.py:18`, `patch_mgr.py:431, 611` |
| Reason for `USE_LANGUAGE_FILTER True` | Constant module initialization | `ResourcePatcher.py:65` |
| Reason for `LINYUAN___useDLCClothes: False` | `info.get('use_dlc_clothes', False)` defaults to `False` | `patch_mgr.py:409..410` |
| Recommended Plist Tail | `{"type": "package", "version": "1117219", "version_name": "1.610377.506841", "min_client_version": 0, "min_engine_version": 0, "min_patch_client_version": 0, "min_patch_engine_version": 0, "file_list": [], "use_dlc_clothes": false}` | Static proof complete |

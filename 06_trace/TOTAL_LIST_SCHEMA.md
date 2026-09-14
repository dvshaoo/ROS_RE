# ROS v1117219 — `total_list` / Patch-List Schema (Resolved)

**Result up front**: the patch-list gate (`Retrieving patch lists 0.00%`) is **CLEARED**.
The client now boots all the way through engine init and reaches the title/login screen
(User Agreement dialog, already logged in as Guest). This was verified against the live
client on the existing LDPlayer setup, not assumed.

## 0. Method Note — Why This Is Empirical, Not Decompiled

The task asked to decompile `patch/ResourcePatcher.py` out of `script.npk` to read the
schema directly from source. That was attempted first and is documented in §1 as a
genuine, bounded attempt — it did not succeed in this session, for a concrete, reportable
reason (custom encryption, not a skipped step). Given that, the schema below was
determined by **controlled differential testing against the live client**: each fix was
driven by an exact, specific Python traceback (file + line number + exception type) printed
to `logcat` by the client's own embedded interpreter when a wrong schema was served. This is
still evidence-based — every field decision below is traceable to a specific, quoted runtime
error, not a guess — but it is dynamic evidence rather than static source, and is labeled as
such throughout.

## 1. Attempted Static Extraction (Bounded Attempt, Not Completed)

- `script.npk` is a NeoX `NXPK`-format package (magic bytes `NXPK`, confirmed):
  - Header: `magic(4)="NXPK"`, `file_count(4)=3959`, `reserved(8)`, `format(4)=1`,
    `index_offset(4)=0x0308e54c`, plus two more 4-byte fields (checksum-shaped).
  - Index: `file_count` entries of 28 bytes each, immediately confirmed by
    `(filesize - index_offset) / 28 == file_count` exactly (3959.0, no remainder).
  - Each entry: `{name_hash(4), data_offset(4), size_compressed(4), size_original(4),
    val1(4), val2(4), flags(4)}`. `size_compressed == size_original` for every sampled
    entry (no zlib/deflate compression is used at the container level).
- **Blocker**: every entry's payload begins with a **constant 2-byte marker `7a 1c`**
  followed by data indistinguishable from random bytes — not a recognized zlib/gzip header,
  and `zlib.decompress()` (with and without the zlib wrapper) fails on every sampled entry.
  This is a custom encryption/obfuscation layer, not plain compression.
- Searched `libclient_arm64.so` for the plaintext filenames and error strings that would
  appear in a decompiled `ResourcePatcher.py` (`ResourcePatcher`, `total_list`,
  `patch_size_calc`, `patch_mgr`) — **none found**. Only the string `file_list` was found (2
  occurrences), confirming the scripts themselves are not frozen into the native binary.
- Found the RTTI-confirmed native class `neox::package::NeoXPackage` (string
  `N4neox7package11NeoXPackageE`) and a companion `neox::t2script::Module` type
  (`N4neox8t2script6ModuleE`, seen earlier in this project's login-flow work) — these are
  almost certainly where the actual per-file decryption happens, in native code, before the
  bytes are handed to the embedded Python interpreter's `marshal`/import mechanism.
  Locating and reversing that decrypt routine is a **separate, self-contained task** of
  comparable size to the native login-flow work already done in this project, and was
  correctly out of scope for "fix the local patch server" — flagged here as the clean
  follow-up if source-level verification of the schema is ever wanted.
- Confirmed CRC32 of plausible filenames does **not** match any of the 3959 index hashes,
  so the hash algorithm is also non-standard (not investigated further, given the above).

**Everything past this point is CONFIRMED BY DYNAMIC CAPTURE, not by decompiled source.**

## 2. The Actual Schema (Confirmed By Client Runtime Behavior)

The client's own error messages, quoted verbatim from `logcat`, pinned down the exact shape
required — three iterations, each fixing exactly what the previous traceback named:

### Iteration 1 — baseline: empty `file_list`

```
"file_list": []
```
Result:
```
Traceback (most recent call last):
  File "lib\threading.py", line 810, in __bootstrap_inner
  File "lib\threading.py", line 763, in run
  File "patch\ResourcePatcher.py", line 1285, in patch_size_calc
ZeroDivisionError: float division by zero
```
**Conclusion**: `patch_size_calc` unconditionally divides by some quantity derived from the
number of files in `file_list` (or their total size) with no zero-guard. An empty list is
not a valid "nothing to patch" signal in this build — CONFIRMED BY DYNAMIC CAPTURE.

### Iteration 2 — `file_list` entries as dicts

```python
"file_list": [{"name": "dummy.npk", "size": 1, "md5": "0"*32, "updated": 0}]
```
Result:
```
File "patch\ResourcePatcher.py", line 1299, in patch_size_calc
TypeError: unhashable type: 'dict'
```
**Conclusion**: `file_list` entries are used directly as **hash keys** (e.g. in a `set(...)`
or as a `dict` key) somewhere in `patch_size_calc` — they must be a hashable type (a plain
string), not a dict. This also disproves the natural-looking hypothesis that `file_list`
entries carry their own metadata inline — CONFIRMED BY DYNAMIC CAPTURE.

### Iteration 3 — `file_list` as plain strings, metadata in a separate `total_list` dict

```python
"file_list": ["dummy.npk"]
# total_list served separately:
{"dummy.npk": {"size": 1, "md5": "0"*32, "updated": 0}}
```
Result:
```
File "patch\ResourcePatcher.py", line 1308, in patch_size_calc
KeyError: u'dummy.npk_updated'
```
**Conclusion (the key finding)**: `patch_size_calc` does not do `some_dict[name]['updated']`
— it does a **flat, string-concatenated lookup**: `some_dict[name + '_updated']`. This is
the exact same convention already visible, in plain sight, in the plist's own top-level OBB
keys (`"patch.1117219.com.netease.chiji.obb_updated"`,
`"patch.1117219.com.netease.chiji.obb_size"`,
`"patch.1117219.com.netease.chiji.obb_md5"`) — this project's earlier sessions had already
served as unwitting evidence for this convention without recognizing it as generalizable to
`file_list` entries too. CONFIRMED BY DYNAMIC CAPTURE.

### Iteration 4 (final, working) — per-file flat keys on the **plist itself**

```python
"file_list": ["dummy.npk"],
"dummy.npk_updated": 0,
"dummy.npk_size": 1,
"dummy.npk_md5": "00000000000000000000000000000000",
```
placed as **top-level keys in the plist dict** (the same dict `file_list` and the OBB keys
already live in) — **not** inside the separately-fetched `total_list` response. Result: no
exception. The client proceeds past `patch_size_calc` entirely; `total_list` continues to
be requested and served (a small pickled dict, now unused-but-harmless) with no further
errors referencing it.

**This means `total_list`'s actual schema/purpose was not exercised by this test** — the
per-file `_updated`/`_size`/`_md5` triplet needs to exist somewhere `patch_size_calc` can
find it via `name + '_suffix'` string lookup, and placing it directly on the plist dict
(which is definitely in scope, since it's the same object the OBB keys and `file_list`
already live on) was sufficient. Whether `total_list` needs the *same* triplet for a
**non-trivial** file list (i.e., once `file_list` contains more than a placeholder that
requires no real download) was not tested — flagged as UNKNOWN / a good next check before
relying on this for real content patches.

## 3. Full Schema Table

| Field | Location | Type | Consumer | Confidence |
|---|---|---|---|---|
| `file_list` | plist top level | `list[str]` (plain filenames, hashable) | `patch\ResourcePatcher.py:patch_size_calc` — iterated and used as/with hash keys | CONFIRMED BY DYNAMIC CAPTURE |
| `<filename>_updated` | plist top level, one key per `file_list` entry | `int` (0/1 observed) | same function, `name + '_updated'` lookup | CONFIRMED BY DYNAMIC CAPTURE |
| `<filename>_size` | plist top level | `int` | same function (presumed: summed for progress/total-bytes calc, given the function name and the original `ZeroDivisionError`) | STRONG EVIDENCE (present in the working config; not individually isolated from `_updated`/`_md5`) |
| `<filename>_md5` | plist top level | `str` (32 hex chars) | same function (presumed: change detection) | STRONG EVIDENCE (same caveat) |
| `total_list` response body | separate HTTP endpoint `/1117219/total_list` | `zlib.compress(pickle.dumps(X, 2))`, `X` = a dict | fetched successfully, no longer implicated in any traceback once §2 Iteration 4 was applied | UNKNOWN schema for non-trivial use — CONFIRMED only that an empty-ish placeholder dict does not itself block progress once the plist carries the per-file keys |
| absolute-URI request line for `/1117219/total_list` | HTTP layer, not patch schema | n/a | `mitm_serve.H._handle` — path must be matched with `in`, not `startswith('/')`, because the client issues a full-URI GET line | CONFIRMED BY DYNAMIC CAPTURE (fixed in the prior session's commit `5479ec7`, still correct) |

## 4. Why The Old `{}` Response Failed

The old code shipped two separate defects, fixed one at a time in the iterations above:
1. `PLIST`'s `"file_list": []` (empty) — the client's own `patch_size_calc` divides by a
   quantity that is zero whenever there are no files to check, with no guard for the "empty
   is fine, nothing to do" case. This is a bug in the **client's** patch engine (or at least
   in this particular server-config-dependent code path of it), not something the server
   can route around by choosing a different "empty" representation — a placeholder entry is
   required.
2. `TOTAL_LIST_PAYLOAD = zlib.compress(pickle.dumps({}, 2))` was a red herring — the actual
   consumer never got far enough to care what `total_list` contained, because the crash
   happened earlier, inside `patch_size_calc`'s handling of `file_list` itself (first the
   ZeroDivisionError, then after adding an entry, the TypeError/KeyError chain in §2). The
   original assumption that "the schema problem is in `total_list`" was reasonable given the
   task's framing, but the evidence showed the real fix needed to be applied to the **plist**,
   with `total_list` turning out not to be on the critical path for this minimal case.

## 5. The Corrected Local-Server Response

Applied directly to the existing `mitm/mitm_serve.py` (no duplicate server created):

```python
PLIST = (
    b'##########\n'
    b'{\n'
    b'  "type": "package",\n'
    b'  "version": "1117219",\n'
    b'  "version_name": "1.610377.506841",\n'
    b'  "min_client_version": 0,\n'
    b'  "min_engine_version": 0,\n'
    b'  "min_patch_client_version": 0,\n'
    b'  "min_patch_engine_version": 0,\n'
    b'  "use_dlc_clothes": false,\n'
    b'  "file_list": ["dummy.npk"],\n'
    b'  "dummy.npk_updated": 0,\n'
    b'  "dummy.npk_size": 1,\n'
    b'  "dummy.npk_md5": "00000000000000000000000000000000",\n'
    b'  "patch.1117219.com.netease.chiji.obb_updated": 0,\n'
    b'  "patch.1117219.com.netease.chiji.obb_size": 1,\n'
    b'  "patch.1117219.com.netease.chiji.obb_md5": "00000000000000000000000000000000"\n'
    b'}\n'
)

TOTAL_LIST_PAYLOAD = zlib.compress(pickle.dumps({
    'dummy.npk_updated': 0,
    'dummy.npk_size': 1,
    'dummy.npk_md5': '00000000000000000000000000000000',
}, 2))
```

(`total_list`'s payload is kept in the same flat-key shape as a defensive/consistent choice
even though §2 showed it wasn't the thing gating progress in this test — cheap to keep
correct-shaped in case a later, non-trivial `file_list` does consult it.)

## 6. Test Result (Verified From Live Client Logs, Not Assumed)

Full run captured via `adb logcat`, `mitm/captures/SERVE_B.txt`, and screenshots
(`scratch/relaunch11.png`, `scratch/relaunch12.png` — not committed, referenced for the
record). After applying §5:

```
[trouger] properties.init()... assets/data/properties
Type <class 'libclaudia.internals.ResourceController.ResourceController'> should be initialized immediately after creation.
Type <class 'libclaudia.Settings.TagsAndLayers.TagLayerManager'> should be initialized immediately after creation.
Type <class 'libclaudia.Settings.CanvasManager.CanvasManager'> should be initialized immediately after creation.
Type <class 'ui.chat.voiceUtils.VoiceUtils'> should be initialized immediately after creation.
Type <class 'scenario.helper.scenario_gameobj.ScenarioGameObject'> should be initialized immediately after creation.
...
http_get url=https://h45na.update.easebar.com/server_list_ad.txt
http_get url=https://h45na.update.easebar.com/notice_pc_hw.txt
```
No further tracebacks referencing `ResourcePatcher.py`, `patch_size_calc`, `file_list`, or
`total_list` appear anywhere after this point in the captured log. **Zero exceptions** were
logged for the remainder of the captured session.

Screen state (`scratch/relaunch11.png` → `relaunch12.png`, screenshots taken directly from
the live LDPlayer instance): the client renders the full title screen UI (Events / Notice /
Contact / Language / PC-Login side rail), shows **"Guest"** already logged in top-right, hit
one transient "Slow connection" dialog (a *different*, later gate — not a `ResourcePatcher`
error), and after dismissing it, presented NetEase's User Agreement dialog (page 1 of 91,
Accept/Reject). This is unambiguously **past** the patch-list gate this task targeted.

## 7. Answers To The Task's Specific Questions

1. **Exact `total_list` schema discovered**: not the actual blocker (see §4) — its own
   schema remains only partially exercised (§2 Iteration 4 note). The real fix was on the
   plist itself.
2. **Why the old `{}` response failed**: two stacked bugs — an empty `file_list` crashes
   `patch_size_calc` with `ZeroDivisionError`, and even after populating `file_list`, the
   per-file metadata must be flat `name + '_suffix'` keys on the plist, not a nested dict
   anywhere.
3. **Exact local-server fix**: §5, applied to `mitm/mitm_serve.py` directly (no duplicate
   server file created, per the task's instruction).
4. **Client passed `Retrieving patch lists 0.00%`?** **YES**, verified via logcat (zero
   tracebacks past this point) and screenshots (title screen rendered).
5. **Client reached PLAY?** Reached the **title/login screen** (Guest already signed in,
   User Agreement dialog showing) — one to two taps short of the PLAY button itself. Per
   this task's explicit instruction to stop once the patch gate is cleared and not chase
   further UI/gates, the session stopped here without clicking through the 91-page
   agreement.
6. **Did LoginApp `:25000` receive traffic?** **No** — confirmed via
   `mitm/captures/BASEAPP_LOGIN_CAPTURE.txt` (only listener-startup log lines present, no
   `LOGINAPP UDP RECV` entries). Expected, since PLAY was not reached.
7. **Did BaseApp `:25010` receive anything?** **No**, same evidence, same reason.
8. **Next concrete blocker** (for whichever future session continues past this task's
   scope): a **"Slow connection. Please check your connection and try again."** dialog
   appeared once during this run, tied to a different endpoint than the patch/plist system
   (likely the UniSDK/MPay or notice-fetch path, not `ResourcePatcher`) — not investigated
   further per this task's explicit stop condition. The very next UI step after that is the
   User Agreement (Accept/Reject), then presumably the PLAY button itself.

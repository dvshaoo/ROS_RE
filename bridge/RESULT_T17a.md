# RESULT_T17a: patchVersion Path and Write-Site Analysis (Static RE)

## 1. Executive Summary
- **Target File**: `patchVersion`
- **Computed Absolute Path**:
  - Android runtime: `/data/data/com.netease.chiji/files/patchVersion`
  - Formula: `ResourcePatcher.absDocRoot + '/patchVersion'` (or `os.path.join(ResourcePatcher.absDocRoot, 'patchVersion')`)
- **Write-Site**:
  - **Writer**: `BaseStage.beforePatchFinish` (`patch/patch_mgr.py:160-162`)
  - **Written Format**: `self._context.patchVersion` = `'1.%d.%d.%s' % (min_patch_engine_ver, min_patch_client_ver, settingLanguage)` (`patch/patch_mgr.py:447`)
- **Cancel Path Behavior (L664-668)**:
  - **CONFIRMED WRITE**: Sa CANCEL path (`patch/patch_mgr.py:664-668`), **nasusulat ang file** dahil tinatawag ang `self.beforePatchFinish()` sa Line 667 bago mag-`goto_stage(CANCEL_STAGE)` sa Line 668.

---

## 2. Definition & Computation of `ResourcePatcher.absDocRoot`

### Source Excerpt: `patch/ResourcePatcher.py:28-36`
```python
28: try:
29:     import game3d
30:     platform = game3d.get_platform()
31:     docRoot = game3d.get_doc_dir()
32: except AttributeError:
33:     if platform == game3d.PLATFORM_IOS:
            if os.path.basename(os.path.realpath(os.curdir)) == 'app':
                docRoot = '../Documents/'
            else:
                docRoot = './Documents/'
34: absDocRoot = os.path.realpath(docRoot)
35: if platform == game3d.PLATFORM_WIN32:
36:     absDocRoot = absDocRoot.replace('\\', '/')
```
- **Android Target**: Sa engine (`game3d.get_doc_dir()`), nagre-resolve ito sa app data directory: `/data/data/com.netease.chiji/files`.
- **Absolute Target File Path**: `/data/data/com.netease.chiji/files/patchVersion`.

---

## 3. ALL Write and Delete Sites of `patchVersion`

Across the entire `script.npk`, **isa lang ang sumusulat** sa `patchVersion` file:

### 3.1 The Sole Writer: `BaseStage.beforePatchFinish` (`patch/patch_mgr.py:160-162`)
```python
154: def beforePatchFinish(self):
155:     reload(Version)
156:     f = open(ResourcePatcher.absDocRoot + '/firstPackVersion', 'w')
157:     f.write(patch_utils.getFirstPackVersion())
158:     f.close()
160:     f = open(ResourcePatcher.absDocRoot + '/patchVersion', 'w')
161:     f.write(self._context.patchVersion)
162:     f.close()
164:     patch_utils._removeIfExists(ResourcePatcher.absDocRoot + '/repair')
166:     self._writeMD5FileList()
```

### 3.2 Content Format Written
Set in `patch/patch_mgr.py:447` (`VersionStage.updateStage`):
```python
self._context.patchVersion = '1.%d.%d.%s' % (min_patch_engine_ver, min_patch_client_ver, settingLanguage)
```
Halimbawa: `'1.0.0.en'` kung `min_patch_engine_version=0`, `min_patch_client_version=0`, at `settingLanguage='en'`.

### 3.3 Deletion Site: `BirthStage.cleanPatch` (`patch/patch_mgr.py:292+`)
```python
patch_utils._removeIfExists(ResourcePatcher.absDocRoot + '/patchVersion')
```
Tinatawag ito sa `BirthStage` tuwing kailangan mag-clean patch o may repair trigger.

---

## 4. Callers of `beforePatchFinish` and the CANCEL Path

Tinatawag ang `beforePatchFinish` sa mga sumusunod na sites:
1. `PrePatchStage.updateStage` (`patch/patch_mgr.py:660`) - Normal clean finish (0 download size, not forced).
2. `PrePatchStage.updateStage` (`patch/patch_mgr.py:667`) - **CANCEL PATH**.
3. `PrePatchStage.updateStage` (`patch/patch_mgr.py:735, 737`) - PrePatch completion paths.
4. `PatchStage.updateStage` (`patch/patch_mgr.py:990, 1087`) - Download/patch finish paths.

### Detailed CANCEL Path Excerpt: `patch/patch_mgr.py:664-669`
```python
664: if self._context.forcePatch:
665:     print 'fubingnan totalSizeToDownload == 0 but force Patch!, patch resource got problem?'
666:     # event report
667:     self.beforePatchFinish()
668:     self.goto_stage(CANCEL_STAGE)
669:     return
```

### Konklusyon sa Cancel Path:
- **Nasusulat ba sa cancel path?** **OO**. Sa Line 667, tinatawag ang `beforePatchFinish()`, na nagbubukas ng `open(absDocRoot + '/patchVersion', 'w')` at isinusulat ang `self._context.patchVersion`.
- **Bakit nag-trigger ang cancel path una pa lang?** Dahil sa initial check sa `VersionStage` (`patch/patch_mgr.py:431, 611`), wala pa ang `patchVersion` file sa disk (o na-remove ng `cleanPatch`), kaya `getPatchLanguage()` -> `None` -> `need_language_patch = True` -> `forcePatch = True`. Pagdating sa `PrePatchStage`, 0 ang download size pero `forcePatch=True`, kaya nag-print at nag-cancel stage, pero isinulat na nito ang `patchVersion` para sa susunod na retry.

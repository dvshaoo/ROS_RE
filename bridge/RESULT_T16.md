# RESULT_T16: force-Patch Driver Trace (Static RE)

## 1. Executive Summary
- **Target String**: `'fubingnan totalSizeToDownload == 0 but force Patch!, patch resource got problem?'`
- **Module & Function**: `patch/patch_mgr.py:665` in `PrePatchStage.updateStage`
- **Driver Chain**:
  1. `patch/patch_utils.py:18` (`getPatchLanguage()`): Reads `<absDocRoot>/patchVersion`. If absent or split length < 4, returns `None`.
  2. `patch/patch_mgr.py:611` (`VersionStage._check_language_patch(settingLanguage)`): Checks `if patch_language is None or patch_language != settingLanguage: return True`.
  3. `patch/patch_mgr.py:431, 444-446` (`VersionStage.updateStage`):
     `need_language_patch = self._check_language_patch(settingLanguage)`
     `if patch_client_ver < min_patch_client_ver or need_language_patch:`
         `self._context.forcePatch = True`
  4. `patch/patch_size_calc.py`: Discovers 0 diff files to download (`totalSizeToDownload == 0`).
  5. `patch/patch_mgr.py:658, 664-668` (`PrePatchStage.updateStage`):
     `if self._context.totalSizeToDownload == 0:`
         `if self._context.forcePatch:`
             `print 'fubingnan totalSizeToDownload == 0 but force Patch!, patch resource got problem?'`
             `self.beforePatchFinish()`
             `self.goto_stage(CANCEL_STAGE)` -> triggers patch failure popup.

---

## 2. Print Site & Immediate Condition

### Excerpt: `patch/patch_mgr.py:655-670` (`PrePatchStage.updateStage`)
```python
655:    (needPatch, self._context.prePatchedSize, self._context.totalSizeToDownload) = self.sizeCalculator.getPatchSize()
656:    # ...
658:    if self._context.totalSizeToDownload == 0:
659:        if not (self._context.forcePatchForValidation or needPatch):
660:            self.beforePatchFinish()
661:            self.patch_finish()
662:            return
663:        # ...
664:        if self._context.forcePatch:
665:            print 'fubingnan totalSizeToDownload == 0 but force Patch!, patch resource got problem?'
666:            # report event ...
667:            self.beforePatchFinish()
668:            self.goto_stage(CANCEL_STAGE)
669:            return
```

---

## 3. Flag Setter: `self._context.forcePatch`

### Excerpt: `patch/patch_mgr.py:431-447` (`VersionStage.updateStage`)
```python
431:    need_language_patch = self._check_language_patch(settingLanguage)
432:    # ...
444:    if patch_client_ver < min_patch_client_ver or need_language_patch:
445:        # ...
446:        self._context.forcePatch = True
447:    self._context.patchVersion = '1.%d.%d.%s' % (min_patch_engine_ver, min_patch_client_ver, settingLanguage)
```

---

## 4. Root Driver: `_check_language_patch` and `patchVersion`

### Excerpt: `patch/patch_mgr.py:608-615` (`VersionStage._check_language_patch`)
```python
608:    def _check_language_patch(self, settingLanguage):
609:        # ...
610:        patch_language = patch_utils.getPatchLanguage()
611:        if patch_language is None or patch_language != settingLanguage:
612:            return True
613:        return False
```

### Excerpt: `patch/patch_utils.py:18-28` (`getPatchLanguage`)
```python
18: def getPatchLanguage():
19:     path = os.path.join(ResourcePatcher.absDocRoot, 'patchVersion')
20:     if not os.path.exists(path):
21:         return None
22:     try:
23:         with open(path, 'r') as fp:
24:             content = fp.read().strip()
25:             parts = content.split('.')
26:             if len(parts) >= 4:
27:                 return parts[3]
28:     except Exception:
29:         pass
30:     return None
```

---

## 5. Clearing Mechanism (Exact Inputs)

To prevent `forcePatch = True` from triggering `CANCEL_STAGE` when `totalSizeToDownload == 0`:

1. **Local File Input (`<absDocRoot>/patchVersion`)**:
   - Location: `/data/data/com.netease.chiji/files/patchVersion` (or `absDocRoot + '/patchVersion'`).
   - Format: `1.<engine_ver>.<client_ver>.<settingLanguage>` (e.g. `1.0.0.en`).
   - Effect: `patch_utils.getPatchLanguage()` returns `'en'`. `_check_language_patch('en')` returns `False`.
2. **Server Plist Input (`reslist.plist` / `version_info`)**:
   - `min_patch_client_version`: `0`
   - `min_patch_engine_version`: `0`
   - Effect: `patch_client_ver < min_patch_client_ver` evaluates to `False`.
3. **Outcome**:
   With `need_language_patch == False` and `patch_client_ver >= min_patch_client_ver`:
   `self._context.forcePatch` remains `False`.
   At line 659: `if not (self._context.forcePatchForValidation or needPatch):` is taken.
   `PrePatchStage` calls `self.patch_finish()` cleanly without entering `CANCEL_STAGE`.

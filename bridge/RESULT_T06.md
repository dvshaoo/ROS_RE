TASK: T06
FINDING: 2 wrapper candidates written (CANDIDATE_PLIST_XML.txt, CANDIDATE_JSON.txt); version key = 1117219; file-array placeholder = __FILELIST__

## Wrapper 1 — CANDIDATE_PLIST_XML.txt
Format: Apple Binary/XML plist, `<dict>` root, keys `version` (integer) + `files` (array).
HYPOTHESIS: Likely parser — NeoX engine na Android commonly uses NSPropertyListSerialization
  o native plist reader (BigWorld mobile inherits iOS-origin code). Ang `.plist` extension +
  `GET /pl/` path strongly suggests Apple plist format; `version` integer key = versionCode
  1117219 ang diffed ng client laban sa local manifest. Each file entry sa array malamang
  `<dict>` na may `path`, `size`, `md5` keys (matching local manifest triplet format).

## Wrapper 2 — CANDIDATE_JSON.txt
Format: JSON object, keys `version` (integer) + `files` (array of objects).
HYPOTHESIS: Fallback candidate — kung ang plist reader ay custom-parsed at nagtanggap ng
  JSON (hal. sa Android port, plist replaced ng JSON para mabilis). Mas unlikely kaysa plist
  dahil ang endpoint path ay `.plist` literally, pero posible na legacy alias.

## Context from LOCAL_MANIFEST.md
- Client ground truth: size+path+obb_tag triplets + md5 per line
- 16 main entries + 17 patch entries (~33 files total)
- Server plist = diff source: client compares server list vs local to decide what to download
- `__FILELIST__` placeholder = ilalagay ng kabilang session mula sa actual OBB file list

SOURCE: 06_notes/LOCAL_MANIFEST.md (full, 39 lines); bridge/CANDIDATE_PLIST_XML.txt; bridge/CANDIDATE_JSON.txt
VERSION: 1.610377.506841 / vCode 1117219
STATUS: PASS (wrappers written; values = HYPOTHESIS — kabilang session mag-ve-verify via MITM)

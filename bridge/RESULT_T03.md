TASK: T03
FINDING: drpf POST field list confirmed (7 keys); update-check URLs confirmed; drpf POST path = BLOCKED (no literal path in dex strings)

## (a) Header/Query Field List (sections with hits)

| Field key         | Source constant / log string              | dex file           |
|-------------------|-------------------------------------------|--------------------|
| jf_gameid         | JF_GAMEID, jf_gameid=                     | classes.dex        |
| unisdk_deviceid   | unisdk_deviceid                           | classes.dex        |
| transid           | transid, transid=, KEY_TRANSID            | classes.dex/3.dex  |
| app_channel       | app_channel, app_channel=, APP_CHANNEL    | classes.dex/3.dex  |
| is_root           | is_root, is_root=, DEVICE_INFO_IS_ROOT    | classes.dex        |
| is_emulator       | is_emulator, is_emulator=                 | classes.dex        |
| sdk_ver           | sdk_ver, sdk_ver=, SDK_VER                | classes.dex        |

Also seen in query string template (line 52/109):
  egameid=%s&login_channel=%s&app_channel=%s&platform=%s&username=%s&udid=%s&sessionid=%s&sdk_version=%s
  → additional fields: egameid, login_channel, platform, username, udid, sessionid, sdk_version

## (b) Update-check URLs (latest_v*.json)

| URL                                                              | dex file    |
|------------------------------------------------------------------|-------------|
| http://update.unisdk.easebar.com/html/latest_v6.json            | classes.dex |
| http://update.unisdk.easebar.com/html/latest_v21.json           | classes.dex |
| http://update.unisdk.easebar.com/html/latest_v21.tw.json        | classes.dex |
| http://update.unisdk.easebar.com/html/latest_v36.tw.json        | classes.dex |
| http://update.unisdk.easebar.com/html/latest_v39.tw.json        | classes.dex |
| http://unisdk.update.easebar.com/html/latest_v36.tw.json        | classes.dex |
| http://unisdk.update.easebar.com/html/latest_v39.tw.json        | classes.dex |
| https://unisdk.update.easebar.com/html/latest_v36.tw.json       | classes.dex |
| https://unisdk.update.easebar.com/html/latest_v39.tw.json       | classes.dex |
| https://update.unisdk.easebar.com/html/latest_v36.tw.json       | classes.dex |
| https://update.unisdk.easebar.com/html/latest_v39.tw.json       | classes.dex |
| https://unisdk.update.easebar.com/feature/                      | classes.dex |

## (c) drpf POST path

BLOCKED — walang literal POST path sa dex strings (e.g. `/drpf/` o `/report`).
Host confirmed: `https://drpf-h45na.proxima.nie.easebar.com`
Path likely inside AdvDrpf class body o runtime-constructed — kailangang i-decompile ang AdvDrpf para makita.

SOURCE: 06_notes/DRPF_FIELDS.md §jf_gameid, §unisdk_deviceid, §transid, §app_channel, §is_root, §is_emulator, §easebar URLs with path
        dex: 02_dex\classes.dex (primary), classes3.dex (secondary)
VERSION: 1.610377.506841 / vCode 1117219
STATUS: PASS (a+b confirmed; c = BLOCKED-no-POST-path-in-strings)

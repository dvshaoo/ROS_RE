TASK: T05
FINDING: Static-hunt verdict — server host/port = 0 hits across dex+.so+OBB; entities.npk (329KB) + script.npk (49MB) found in OBB; entities.npk is NXPK-encrypted → T06 entity defs = BLOCKED-pending-NeoX-decrypt

## (a) Server host/port static verdict

| Layer | Keys searched | Hits | Note |
|---|---|---|---|
| 02_dex (classes.dex/2/3) | ServerListURL, 25000, channel_login, loginapp literal | 0 server addr | Keys found, values runtime-set |
| 03_lib (libclient_arm64.so) | serverlist, 25000, channel_login | 0 | confirmed T04 |
| 04_obb (main+patch, 3.3 GB) | serverlist, server_list, loginapp, 25000, channel_login, listsvr, login_url, serverurl, server_addr, gameserver | 0 real hits | Only hit: `SF250000` = font name, NOT port 25000 |

**Verdict: No static server address anywhere in dex/so/OBB.**
Next hunt must be **LIVE MITM capture** (traffic intercept at runtime), not static scan.

## (b) NPK files found in OBB

### main.1117219.com.netease.chiji.obb (361 entries)
| File | Size |
|---|---|
| res/entities.npk | 329.2 KB |
| res/animators.npk | 151.4 KB |
| res/common.npk | 2278.1 KB |
| res/effect.npk | 564583.5 KB |
| res/character.npk | 713417.1 KB |
| res/character2.npk | 459610.9 KB |
| *(+ others)* | |

### patch.1117219.com.netease.chiji.obb (24 entries)
| File | Size |
|---|---|
| script.npk | **49829.6 KB (~49 MB)** |
| assets.npk | 10649.5 KB |
| res/scene.npk | 215071 KB |
| res/ui.npk | 457254.8 KB |
| res/vehicle.npk | 312360 KB |
| *(+ others)* | |

## (c) entities.npk — NXPK encrypted → T06 BLOCKED

- File: `res/entities.npk` (329 KB) in main OBB
- Magic: `NXPK` (NeoX proprietary format)
- Content: **encrypted** — all targeted string searches returned 0 hits:
  LoginProxy=0, Account=0, Athlete=0, Avatar=0, Properties=0, Methods=0,
  onLogin=0, onChannelLogin=0, showSelectCharacter=0, entities.xml=0, .def=0,
  onCreateCharacter=0, enterHall=0
- Same pattern as PC track: entity defs live in script.npk Python bytecode
- **T06 (Entity defs) = BLOCKED-pending-NeoX-decrypt** — kabilang session ang gagawa ng decrypt tool

SOURCE: 06_notes/OBB_SERVERLIST.md (all sections), 06_notes/OBB_FILEHUNT.md (full), 06_notes/ENTITIES_NPK.md (all sections)
VERSION: 1.610377.506841 / vCode 1117219
STATUS: PASS (all verdicts confirmed from note files; no guessing)

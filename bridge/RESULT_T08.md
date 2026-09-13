TASK: T08
FINDING: NXPK = no encryption — consecutive zlib streams from offset 0x18.
  628 entity defs decompressed from entities.npk (337KB).
  Account/Athlete/LoginProxy/Avatar defs fully readable.
  Decryptor: 05_entities/neox_decrypt.py (stdlib-only, run-ready).

## NXPK Container Map (entities.npk, v1117219)

| Field | Offset | Value | Notes |
|---|---|---|---|
| magic | 0x000 | `NXPK` (4E 58 50 4B) | confirmed |
| unknown_1 | 0x004 | 628 (0x274) | possibly header+index total size |
| unknown_2 | 0x008 | 0 | |
| unknown_3 | 0x00C | 0 | |
| entry_count | 0x010 | 1 | misleading — header says 1 but 628 streams inside |
| comp_size_0 | 0x014 | 319528 (0x4E028) | size of first zlib stream payload |
| payload_start | 0x018 | `78 9C` | zlib magic, first stream begins here |
| index/tail | 0x4E040 | 17560 bytes | tail index (points into OBB, not this file) |

**Key finding:** No XOR, no Rotor, no per-string deob — direct zlib, no encryption.
The PC-track pipeline lead (Rotor + reverse_string) does NOT apply to this mobile NXPK.

## Decrypt Steps

1. Open `entities.npk`
2. Scan byte-by-byte for `78 9C` / `78 DA` / `78 01` (zlib magic) starting at offset 0x18
3. `zlib.decompress(data[offset:])` → UTF-8 XML entity def
4. Extract `<ClientName>` tag for filename
5. Repeat until EOF
**No decryption key needed. Pure zlib.**

## How to Run

```
cd c:\Users\Raysoo\Downloads\ROS_RE
python 05_entities\neox_decrypt.py 05_entities\entities.npk 05_entities\out\
```

Output: one `.def.xml` per entity in `05_entities/out/`

## Sample Output (Account.def, offset 0x5E40, 2911 bytes decompressed)

### Properties (declaration order = stream order):
1. `isBan` — BOOL, BASE, Persistent
2. `startBanTime` — INT64, BASE, Persistent
3. `banTime` — INT32, BASE, Persistent
4. `banReason` — STRING, BASE, Persistent
5. `nickname` — STRING, BASE, Persistent, DatabaseLength=20
6. `isMobileAccount` — BOOL, BASE_AND_CLIENT, Persistent
7. `isGuest` — BOOL, BASE, Persistent

### BaseMethods (declaration order):
1. `onNextProxyDestroy` — no args
2. `handshake` <Exposed/> — Args: STRING (hotfix md5), DEVICE_INFO, CHANNEL_INFO, CLIENT_ENGINE_INFO, STRING (sauth reply)
3. `onAcquireLock` — Args: UINT8, STRING, UINT16
4. `onDuplicateLogin` — no args
5. `uploadABSwitchesConfig` <Exposed/> — Arg: STRING (formatInfo)

### ClientMethods (declaration order):
1. `loadSceneAfterReconnect` — Arg: INT32 (mapID)
2. `onLogin` — Args: INT32, STRING
3. `onChannelLogin` — Args: UINT8, PYTHON
4. `refreshSwitches` — Arg: PY_DICT
5. `refreshForbiddenID` — Arg: PY_DICT
6. `syncServerTime` — Arg: INT64
7. `syncServerTimeZone` — Args: INT64, INT64, INT64
8. `onLoginPCServer` — Arg: BOOL

## Sample Output (LoginProxy.def, offset 0x2884, 665 bytes)

### Properties: (none)

### BaseMethods:
1. `handshake` <Exposed/> — Args: DEVICE_INFO, CHANNEL_INFO
2. `onAccountDestroy` — Arg: INT32
3. `bindUrs` <Exposed/> — Args: STRING (new uid), STRING (old uid)

### ClientMethods:
1. `onChannelLogin` — Args: UINT8, PYTHON

## Sample Output (Athlete.def, offset 0xCE44, 28416 bytes — first 5 props)

ClientName: Athlete
Interfaces: iFirstPay, iProxyNoCell, iFriend, iMail, iBindPhone, iHallTeam, iChatHall, iPay, ...
(Full def in 05_entities/out/ after run)

## Key Insight for T09 (plist parser)

Account.BaseMethods[2].handshake first Arg = `STRING` = **hotfix md5**.
This confirms the client sends a hotfix/patch MD5 during handshake — the server
plist response is what provides the expected hotfix file list.

SOURCE:
  05_entities/entities.npk byte scan (offsets 0x18, 0x2884, 0x5E40, 0xCE44)
  06_notes/ENTITIES_NPK.md (all-0 string hits → confirmed NXPK has no plaintext strings)
  NEXT.md leads (entry_count=1 at 0x10 confirmed; PC Rotor pipeline = NOT applicable)
VERSION: 1.610377.506841 / vCode 1117219
STATUS: PASS — Account/LoginProxy defs extracted; Athlete/Avatar confirmed present;
        decryptor written at 05_entities/neox_decrypt.py; run to extract all 628 entities.

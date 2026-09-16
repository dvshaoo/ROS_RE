# ClientInterface message table (CONFIRMED, direct from binary static initializer)

## Source

Ghidra decompilation of `_INIT_44` (static offset `0x90c5a0`), the global
constructor that builds the `ClientInterface`/`BaseAppExtInterface`/
`LoginInterface` method-description tables via repeated calls to
`FUN_00a8b30c(interfaceDescriptor, "methodName", isVariableLength,
lengthOrSize, priority)`. Found via a Ghidra string search for the literal
"authenticate" (which appears as a registered method name), then
decompiling its containing function in full. See
`scratch/ghidra_scripts/FindAuthenticate.java` and
`scratch/ghidra_authenticate.txt` for the raw decompile.

**Confidence: CONFIRMED.** This is not inferred from call-site counting or
disassembly heuristics — it is the literal, in-order sequence of
registration calls in the binary's own static initializer, which is
exactly how BigWorld assigns sequential message IDs (0-indexed, in
registration order) to each named method on an interface.

## Cross-validation

`versionPointIdentity` lands at **index 94** by direct count in this table
— independently confirming the project's prior E2E-022 finding (`msgID =
94`, derived via a totally different method: programmatically walking all
122 interface-method registration call sites in program order). Two
independent methods agree exactly. `setGameTime` = index 3 and
`createBasePlayer` = index 5 also match this project's existing, already
live-tested assumptions.

## ClientInterface (BaseApp → Client direction), by message ID

Format: `id: name (FIXED n bytes | VARIABLE)`. VARIABLE entries show the
raw `(isVariableLength, lengthFieldWidth)` args as registered.

```
0:  authenticate                                        FIXED 4
1:  bandwidthNotification                                FIXED 4
2:  updateFrequencyNotification                          FIXED 1
3:  setGameTime                                          FIXED 4
4:  resetEntities                                        FIXED 1
5:  createBasePlayer                                     VARIABLE (1,2)
6:  createCellPlayer                                     VARIABLE (1,2)
7:  spaceData                                            VARIABLE (1,2)
8:  spaceViewportInfo                                    FIXED 13 (0xd)
9:  createEntity                                         VARIABLE (1,2)
10: updateEntity                                         VARIABLE (1,2)
11: enterAoI                                             FIXED 5
12: enterAoIThruViewport                                 FIXED 6
13: enterAoIOnVehicle                                    FIXED 9
14: partialUpdate                                        FIXED 5
15: leaveAoI                                             VARIABLE (1,2)
16: tickSync                                             FIXED 1
17: relativePositionReference                            FIXED 1
18: setSpaceViewport                                     FIXED 1
19: setVehicle                                           FIXED 4
20: stayPut                                              FIXED 4
21: stayPutAlias                                         FIXED 1
22: historyEventBegin                                    FIXED 4
23: historyEventEnd                                      FIXED 1
24: avatarUpdateNoAliasFullPosYawPitchRollTimeStamp      FIXED 14 (0xe)
25: avatarUpdateNoAliasFullPosYawPitchRollNoTimeStamp    FIXED 12 (0xc)
26: avatarUpdateNoAliasFullPosYawPitchTimeStamp          FIXED 13 (0xd)
27: avatarUpdateNoAliasFullPosYawPitchNoTimeStamp        FIXED 11 (0xb)
28: avatarUpdateNoAliasFullPosYawTimeStamp               FIXED 12 (0xc)
29: avatarUpdateNoAliasFullPosYawNoTimeStamp             FIXED 10
30: avatarUpdateNoAliasFullPosNoDirTimeStamp             FIXED 11 (0xb)
31: avatarUpdateNoAliasFullPosNoDirNoTimeStamp           FIXED 9
32: avatarUpdateNoAliasUnpackPosYawPitchRollTimeStamp    FIXED 15 (0xf)
33: avatarUpdateNoAliasUnpackPosYawPitchRollNoTimeStamp  FIXED 13 (0xd)
34: avatarUpdateNoAliasUnpackPosYawPitchTimeStamp        FIXED 14 (0xe)
35: avatarUpdateNoAliasUnpackPosYawPitchNoTimeStamp      FIXED 12 (0xc)
36: avatarUpdateNoAliasUnpackPosYawTimeStamp             FIXED 13 (0xd)
37: avatarUpdateNoAliasUnpackPosYawNoTimeStamp           FIXED 11 (0xb)
38: avatarUpdateNoAliasUnpackPosNoDirTimeStamp           FIXED 12 (0xc)
39: avatarUpdateNoAliasUnpackPosNoDirNoTimeStamp         FIXED 10
40: avatarUpdateNoAliasOnGroundYawPitchRollTimeStamp     FIXED 12 (0xc)
41: avatarUpdateNoAliasOnGroundYawPitchRollNoTimeStamp   FIXED 10
42: avatarUpdateNoAliasOnGroundYawPitchTimeStamp         FIXED 11 (0xb)
43: avatarUpdateNoAliasOnGroundYawPitchNoTimeStamp       FIXED 9
44: avatarUpdateNoAliasOnGroundYawTimeStamp              FIXED 10
45: avatarUpdateNoAliasOnGroundYawNoTimeStamp            FIXED 8
46: avatarUpdateNoAliasOnGroundNoDirTimeStamp            FIXED 9
47: avatarUpdateNoAliasOnGroundNoDirNoTimeStamp          FIXED 7
48: avatarUpdateNoAliasNoPosYawPitchRollTimeStamp        FIXED 9
49: avatarUpdateNoAliasNoPosYawPitchRollNoTimeStamp      FIXED 7
50: avatarUpdateNoAliasNoPosYawPitchTimeStamp            FIXED 8
51: avatarUpdateNoAliasNoPosYawPitchNoTimeStamp          FIXED 6
52: avatarUpdateNoAliasNoPosYawTimeStamp                 FIXED 7
53: avatarUpdateNoAliasNoPosYawNoTimeStamp               FIXED 5
54: avatarUpdateNoAliasNoPosNoDirTimeStamp               FIXED 6
55: avatarUpdateNoAliasNoPosNoDirNoTimeStamp             FIXED 4
56: avatarUpdateAliasFullPosYawPitchRollTimeStamp        FIXED 11 (0xb)
57: avatarUpdateAliasFullPosYawPitchRollNoTimeStamp      FIXED 9
58: avatarUpdateAliasFullPosYawPitchTimeStamp            FIXED 10
59: avatarUpdateAliasFullPosYawPitchNoTimeStamp          FIXED 8
60: avatarUpdateAliasFullPosYawTimeStamp                 FIXED 9
61: avatarUpdateAliasFullPosYawNoTimeStamp               FIXED 7
62: avatarUpdateAliasFullPosNoDirTimeStamp               FIXED 8
63: avatarUpdateAliasFullPosNoDirNoTimeStamp             FIXED 6
64: avatarUpdateAliasUnpackPosYawPitchRollTimeStamp      FIXED 12 (0xc)
65: avatarUpdateAliasUnpackPosYawPitchRollNoTimeStamp    FIXED 10
66: avatarUpdateAliasUnpackPosYawPitchTimeStamp          FIXED 11 (0xb)
67: avatarUpdateAliasUnpackPosYawPitchNoTimeStamp        FIXED 9
68: avatarUpdateAliasUnpackPosYawTimeStamp               FIXED 10
69: avatarUpdateAliasUnpackPosYawNoTimeStamp             FIXED 8
70: avatarUpdateAliasUnpackPosNoDirTimeStamp             FIXED 9
71: avatarUpdateAliasUnpackPosNoDirNoTimeStamp           FIXED 7
72: avatarUpdateAliasOnGroundYawPitchRollTimeStamp       FIXED 9
73: avatarUpdateAliasOnGroundYawPitchRollNoTimeStamp     FIXED 7
74: avatarUpdateAliasOnGroundYawPitchTimeStamp           FIXED 8
75: avatarUpdateAliasOnGroundYawPitchNoTimeStamp         FIXED 6
76: avatarUpdateAliasOnGroundYawTimeStamp                FIXED 7
77: avatarUpdateAliasOnGroundYawNoTimeStamp              FIXED 5
78: avatarUpdateAliasOnGroundNoDirTimeStamp              FIXED 6
79: avatarUpdateAliasOnGroundNoDirNoTimeStamp            FIXED 4
80: avatarUpdateAliasNoPosYawPitchRollTimeStamp          FIXED 6
81: avatarUpdateAliasNoPosYawPitchRollNoTimeStamp        FIXED 4
82: avatarUpdateAliasNoPosYawPitchTimeStamp              FIXED 5
83: avatarUpdateAliasNoPosYawPitchNoTimeStamp            FIXED 3
84: avatarUpdateAliasNoPosYawTimeStamp                   FIXED 4
85: avatarUpdateAliasNoPosYawNoTimeStamp                 FIXED 2
86: avatarUpdateAliasNoPosNoDirTimeStamp                 FIXED 3
87: avatarUpdateAliasNoPosNoDirNoTimeStamp               FIXED 1
88: detailedPosition                                     FIXED 30 (0x1e)
89: forcedPosition                                       FIXED 36 (0x24)
90: controlEntity                                        FIXED 5
91: voiceData                                            VARIABLE (1,2)
92: restoreClient                                        VARIABLE (1,2)
93: restoreBaseApp                                       VARIABLE (1,2)
94: versionPointIdentity                                 FIXED 8   <- CROSS-VALIDATED, see above
95: versionPointSummary                                  FIXED 34 (0x22)
96: resourceFragment                                     VARIABLE (1,2)
97: resourceVersionStatus                                FIXED 8
98: resourceVersionTag                                   FIXED 1
99: loggedOff                                            FIXED 1
100: shortEntityMessage                                  VARIABLE, 1-byte length (1,1,0)
101: longEntityMessage                                   VARIABLE, 2-byte length (1,2,0)
```

## BaseAppExtInterface (Client → BaseApp direction)

Registered separately, own 0-indexed numbering (NOT shared with
ClientInterface above):

```
0: baseAppLogin              VARIABLE (1,2)
1: authenticate               FIXED 4
2: avatarUpdateImplicit       FIXED 24 (0x18)
3: avatarUpdateExplicit       FIXED 32 (0x20)
4: avatarUpdateWardImplicit   FIXED 24 (0x18)
5: avatarUpdateWardExplicit   FIXED 32 (0x20)
6: switchInterface            FIXED 0
7: requestEntityUpdate        VARIABLE (1,2)
8: enableEntities             FIXED 8
9: setSpaceViewportAck        FIXED 8
10: setVehicleAck             FIXED 8
11: restoreClientAck          FIXED 4
12: identifyVersionPoint      VARIABLE (1,2)   <- matches project's existing E2E-021 finding of msgID=12
13: summariseVersionPoint     VARIABLE (1,2)
14: commenceResourceDownload  VARIABLE (1,2)
15: disconnectClient          FIXED 1
16: resourceVersionTag        FIXED 1
17: entityMessage             VARIABLE (1,2)
```

Note: `authenticate` (FIXED 4 bytes) exists on **both** interfaces —
`BaseAppExtInterface` index 1 (client sends this to BaseApp) and
`ClientInterface` index 0 (BaseApp sends this to client). These are
separate message-ID spaces; the same name being reused for a
request/response pair on each side is a normal BigWorld convention.

## Relevance to the live "authenticate" corruption bug (2026-09-17)

`ClientInterface` id **0** = `authenticate`, FIXED 4-byte body. The live
corruption (`Bundle::iterator::unpack( authenticate ): Not enough data on
stream ... needed 4`, `Nub::processOrderedPacket(...): Discarding bundle
due to corrupted header for message id 0`) is the client's Bundle parser
genuinely trying to read a `ClientInterface::authenticate` call — id 0 is
not some out-of-range/garbage value, it's the very first and lowest valid
ClientInterface message ID, which is why a handful of stray trailing zero
byte(s) in whatever we send is enough to trigger it convincingly. This
project's own server never deliberately sends this message.

**Ruled out this session:** removing the 2-byte `b'\x00\x00'` trailing
"bundle footer" from `createBasePlayer`'s construction (offset-11
coincidence with where that footer sits) was tested live and made things
*worse* — the client then fails to parse `createBasePlayer` itself
("Not enough data on stream at 2 for payload (4 left, needed 6)", the
exact 2-byte shortfall). That footer is required there; the phantom
`authenticate` misparse comes from somewhere else in the sequence, not yet
isolated as of this note (see
`06_notes/GHIDRA_ONCHANNELLOGIN_TRACE.md` Finding 6/7 for the fuller
bisection history — `versionPointIdentity` and `CHANNEL_ACK` replies were
also each tested disabled without eliminating the corruption).

**Next actionable step:** now that the full FIXED/VARIABLE length table
above is confirmed, audit every packet this project's server sends
against its *exact* registered length (not assumed values) — in
particular, verify the wastage-padding/stripping arithmetic in
`bf_encrypt`/the receive-side wastage-stripping logic byte-for-byte
against a real client-sent packet of a *known* FIXED-length message, since
an off-by-a-few-bytes error there would explain corruption appearing
after multiple different message types without any one specific message's
own body format being at fault.

TASK: T09
FINDING: Athlete (51 props, 51 ClientMethods), LoginProxy (0 props, 3 ClientMethods) — fully extracted.
  Type-ID table found: LoginProxy=128, Account=129, Avatar=131, Athlete=142.

---

## LoginProxy.def (offset 0x2884, 665B decompressed)

### Properties: (none)

### BaseMethods (declaration order):
| # | Name | Args | Exposed? |
|---|---|---|---|
| 1 | `handshake` | DEVICE_INFO, CHANNEL_INFO | Yes |
| 2 | `onAccountDestroy` | INT32 | No |
| 3 | `bindUrs` | STRING (new uid), STRING (old uid) | Yes |

### ClientMethods (declaration order):
| # | Name | Args |
|---|---|---|
| 1 | `onChannelLogin` ★ | UINT8, PYTHON |

★ = target method confirmed

---

## Athlete.def (offset 0xCE44, 28416B decompressed)

ClientName: Athlete
Interfaces (declaration order): iFirstPay, iProxyNoCell, iFriend, iMail, iBindPhone,
  iHallTeam, iChatHall, iPay, iGMCommand, iGMAdmin, iRank, iCurrency, iChips,
  iMiscVar, iMiscIntVar, iMiscMapVar, iAccountServiceMgr, ... (+100 more interfaces)

### Properties (declaration order, 51 direct props):
| # | Name | Type | Flags |
|---|---|---|---|
| 1 | proficiencyState | INT32 | BASE_AND_CLIENT |
| 2 | realNameAuthed | BOOL | BASE_AND_CLIENT |
| 3 | msToken | STRING | BASE_AND_CLIENT |
| 4 | msTicket | STRING | BASE_AND_CLIENT |
| 5 | hostID | INT32 | BASE_AND_CLIENT |
| 6 | msHttpAP | PYTHON | BASE_AND_CLIENT |
| 7 | freshManState | BOOL | BASE_AND_CLIENT |
| 8 | finishedDtsTraining | BOOL | BASE_AND_CLIENT |
| 9 | baseCharacterType | UINT32 | BASE_AND_CLIENT |
| 10 | baseLevel | INT32 | BASE_AND_CLIENT |
| 11 | disconnectTimerID | TIMER_ID | BASE |
| 12 | reconnecting | BOOL | BASE |
| 13 | lastLogInTime | FLOAT | BASE_AND_CLIENT |
| 14 | lastLogOutTime | FLOAT | BASE_AND_CLIENT |
| 15 | createTime | FLOAT | BASE_AND_CLIENT |
| 16 | ursAccount | STRING | BASE |
| 17 | lastOperation | STRING | BASE |
| 18 | firstLogOnUdidForRealName | STRING | BASE |
| 19 | isCheater | BOOL | BASE |
| 20 | isBan | BOOL | BASE |
| 21 | startBanTime | INT64 | BASE |
| 22 | banTime | INT32 | BASE |
| 23 | banReason | STRING | BASE |
| 24 | realPlayerName | KEY_NAME | BASE |
| 25 | lastChangeNameTime | FLOAT | BASE |
| 26 | lastGMRedhintMsg | STRING | BASE |
| 27 | pushGMRedHintMsgTimerID | TIMER_ID | BASE |
| 28 | readGMRedhintMsg | BOOL | BASE_AND_CLIENT |
| 29 | filePickerToken | STRING | BASE_AND_CLIENT |
| 30 | filePickerDelToken | STRING | BASE_AND_CLIENT |
| 31 | filePickerVoiceToken | STRING | BASE_AND_CLIENT |
| 32 | filePickerVoiceDelToken | STRING | BASE_AND_CLIENT |
| 33 | requestObserveTimerID | INT32 | BASE |
| 34 | mongoTestData | MONGO_TEST_DATA | BASE |
| 35 | weaponKillCount | PYTHON | BASE_AND_CLIENT |
| 36 | needDrawCardConfirm | BOOL | BASE |
| 37 | valentineSuitsCollected | INT32 | BASE |
| 38 | transformSuitsCollected | PYTHON | BASE |
| 39 | propsFromRandomItemGiftbag | PYTHON | BASE |
| 40 | useOwnAppearOverHeroAppear | INT32 | BASE_AND_CLIENT |
| 41 | hasInformedHeroOwnCloth | BOOL | BASE_AND_CLIENT |
| 42 | hasShowSpecialTipsPanel | BOOL | BASE_AND_CLIENT |
| 43 | hasShowSpecialTipsPanelRestTime | PYTHON | BASE |
| 44 | cclive_last_start_time | PYTHON | BASE |
| 45 | newFunctionGuideRecord | PYTHON | BASE_AND_CLIENT |
| 46 | enterGameCountRecord | INT32 | BASE_AND_CLIENT |
| 47 | hasAccountInOtherPlatform | BOOL | BASE_AND_CLIENT |
| 48 | hasAccountInOtherServer | BOOL | BASE_AND_CLIENT |
| 49 | hasShowNoGPSPermissionTips | PYTHON | BASE_AND_CLIENT |
| 50 | freeHeroRefreshTimes | PYTHON | BASE_AND_CLIENT |
| 51 | freeHeroRefreshWeekIdx | INT8 | BASE_AND_CLIENT |

### ClientMethods (declaration order, 51 total — targets marked ★):
| # | Name | Args |
|---|---|---|
| 1 | showSelectFreshmanState | () |
| 2 | onRefreshMSToken | STRING, STRING |
| 3 | onKickOff | () |
| **4** | **showSelectCharacter ★** | **ARRAY** |
| **5** | **onCreateCharacter ★** | **BOOL, STRING** |
| 6 | onRoleCreateSuc | INT32 |
| 7 | onChangeNickname | BOOL, STRING |
| 8 | updateBaseCharacter | INT32 |
| 9 | updateBaseNickname | STRING |
| 10 | preloadMap | INT32 |
| 11 | cancelPreloadMap | () |
| **12** | **enterHall ★** | **BOOL** |
| 13 | onGetGMToken | STRING |
| 14 | transferToBattleServer | STRING, INT32, KEY_NAME, BLOB, UINT32 |
| 15 | systemMsg | STRING, STRING |
| 16 | systemJumpTip | STRING |
| 17 | systemJumpPanel | STRING |
| 18 | gmKickLowVersion | STRING |
| 19 | gmsyncForbidLiveChannel | ARRAY |
| 20 | gmsyncRedPoints | ARRAY |
| 21 | onGetPlayerTip | FRIEND_ABSTRACT, STRING, VECTOR2, STRING |
| 22 | requestClientProcList | () |
| 23 | requestClientSpeedUp | () |
| **24** | **onLogin ★** | **INT32, STRING** |
| 25 | onUpdateRedBadgeInfo | PYTHON |
| 26 | onQueryQuiz201701Sign | INT32, STRING |
| 27 | onQueryGirlActivitySign | INT32, STRING |
| 28 | pushGMRedHintMsg | STRING |
| 29 | onRequestFilePickerToken | STRING, INT32 |
| 30 | onRequestFilePickerDelToken | STRING |
| 31 | onRequestFilePickerVoiceToken | STRING |
| 32 | onRequestFilePickerVoiceDelToken | STRING |
| 33 | updateReadGMRedhintMsg | BOOL |
| 34 | updateExtraCommonInfo | PYTHON |
| 35 | updateTantanSex | INT32 |
| 36 | updateTantanPicCount | INT32 |
| 37 | onSetPortrait | STRING |
| 38 | onSyncSwitches | STRING, BOOL |
| 39 | onZhongqiuSkinKillNumberUpdate | INT32 |
| 40 | announceValentineTShirtReward | () |
| 41 | onGetGMSupportToken | STRING |
| 42 | onBaseLevelUpdate | INT32 |
| 43 | onGetDtsAppearance | INT32, INT32 |
| 44 | onSyncGotAwards | PYTHON |
| 45 | updateShouldCreatePetInBattle | BOOL |
| 46 | onBuyBraveBookExperience | () |
| 47 | syncUseOwnAppearOverHeroAppear | INT32 |
| 48 | onGmClearNewFunctionGuide | () |
| 49 | resetHasShowSpecialPanel | () |
| 50 | syncAccountInOtherServer | BOOL |
| 51 | syncFreeHeroRefreshWeekIdx | INT8 |

NOTE: onChannelLogin NOT in Athlete direct def — inherited from iProxyNoCell interface.

---

## Type-ID Table (entities.xml, offset 0xDE8, 7792B, declaration order = typeID)

Key entries:
| TypeID | Entity |
|---|---|
| 128 | **LoginProxy** |
| 129 | **Account** |
| 130 | BattleAccount |
| 131 | **Avatar** |
| 132 | AvatarHeroSecretTreasure |
| 133 | AutoRoyaleAvatar |
| 134 | AvatarImba |
| 142 | **Athlete** |
| 143 | Npc |
| 144 | Robot |

Full table: 282 entities total (1=Seat ... 282=WeaponIllustrationStub).
VERDICT: Type-ID table FOUND (not BLOCKED) — entities.xml encodes declaration order = typeID (1-based).

SOURCE: 05_entities/entities.npk — zlib offsets 0xCE44 (Athlete), 0x2884 (LoginProxy), 0xDE8 (entities.xml)
        05_entities/out/LoginProxy.def.xml (verified match)
VERSION: 1.610377.506841 / vCode 1117219
STATUS: PASS (Athlete 51 props + 51 ClientMethods; LoginProxy 0 props + 1 ClientMethod;
        type-ID table found; all 4 targets confirmed with positions)

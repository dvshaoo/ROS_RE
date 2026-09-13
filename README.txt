ROS_RE — reverse-engineering workspace (sariling RE, walang ibang project)
=====================================================================

FLOW:
1. Ilagay ang downloaded .xapk sa 00_INBOX\ (HUWAG palitan ang filename — may version info yan)
2. Extract: XAPK = zip (base APK + OBB). Base APK -> 01_apk\ ; OBB -> 04_obb\
3. Mula sa base APK: classes.dex -> 02_dex\ ; lib/*/libclient.so -> 03_lib\
4. Mula sa OBB/assets: entity defs, tables, npk -> 05_entities\
5. Bawat finding sa 06_notes\ — LAGING may version + versionCode sa taas ng note

RECORD FIRST (bago mag-RE):
- filename, version (hal. 1.610377.506841), versionCode (hal. 1117219)
- arch ng lib na ginagamit (armeabi-v7a / arm64-v8a)

UNANG TARGETS (para sa auth + lobby gates):
- dex: UniSDK auth endpoints, drpf POST fields, guest-login flow
- dex/so: BigWorld logOn, loginapp address/port parsing, server-list URL
- entities: LoginProxy/Account/Avatar/Athlete defs (property order = stream order),
  client method declaration order (hindi = UID; i-verify sa runtime)
- OBB tables: LoginRetCode / ChannelLoginRetEnum numerics

RULE: values are PER-VERSION. Walang kokopyahin mula sa ibang version o ibang project.

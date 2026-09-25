# HANDOFF TO MUSE SPARK: Rules of Survival (ROS) LAN Emulation & Findings

> **Target Client**: Rules of Survival Mobile (Android `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a)  
> **Environment**: LDPlayer 9 (`emulator-5554`, Android guest `172.16.1.15`, Gateway/Host `172.16.1.2`)  
> **Primary Server Script**: `mitm/local_baseapp_capture.py`  
> **Author / Prepared By**: Antigravity Assistant (Gemini)  
> **Date**: 2026-09-22

---

## 1. Executive Status & Quick Start

The client connects to a local integrated server running on the Windows host (`mitm/local_baseapp_capture.py`), providing HTTP (:80), HTTPS (:443/:8443), LoginApp UDP (:25000), and BaseApp UDP (:25010).

### Starting the Server & Environment Checklist
1. **Emulator Networking**: LDPlayer wipes iptables rules on restart. Ensure the 5 DNAT rules are active:
   ```bash
   & "C:\LDPlayer\LDPlayer9\adb.exe" -s emulator-5554 shell "su -c 'iptables -t nat -F OUTPUT && iptables -t nat -A OUTPUT -p tcp --dport 80 -j DNAT --to-destination 172.16.1.2:80 && iptables -t nat -A OUTPUT -p tcp --dport 443 -j DNAT --to-destination 172.16.1.2:443 && iptables -t nat -A OUTPUT -p tcp --dport 8443 -j DNAT --to-destination 172.16.1.2:8443 && iptables -t nat -A OUTPUT -p udp --dport 25000 -j DNAT --to-destination 172.16.1.2:25000 && iptables -t nat -A OUTPUT -p udp --dport 20013 -j DNAT --to-destination 172.16.1.2:20013'"
   ```
2. **Server Execution**:
   ```bash
   python mitm/local_baseapp_capture.py
   ```
3. **Current Client State**: Lobby loads cleanly with avatar, dressed in saved Depot cosmetics, top bar balances (999,999 gold/diamonds), and functional navigation.

---

## 2. Issue 1: Depot -> "Lobby Theme" Delay & Black Screen on Exit

### A. The Symptoms
1. When entering **Depot > Lobby Theme**, theme items initially appear empty or take a while before populating.
2. When pressing the back button or leaving the Lobby Theme page, the 3D scene (garage, motorcycle, sky, lighting) disappears completely, leaving only the avatar floating in pitch black void.

### B. Root Cause Analysis (Bytecode Disassembly)
1. **Why items took long/delayed**:
   - `UIHallThemeMall` queries mall goods with standard `queryAvailableMallGoods` (exposed method `312`).
   - A recent patch sniffs `if b'UIHallThemeMall' in payload:` in `handle_upstream_calls()` to return `_hall_theme_runtime_goods()`.
   - Because `UIHallThemeMall` emits enter telemetry, sniffing raw bytes introduced timing mismatches.
2. **Why it turns BLACK on leave/back**:
   - Disassembly of `ui/UIHallThemeMall.py:on_leave()`:
     ```python
     self.display_reset(True)
     self.displayListView.removeAllItems()
     Globals.uiMgr.UIMain.SendMessage('onShowOriTheme')
     ```
   - Disassembly of `ui/main/HallTheme.py:onShowOriTheme()`:
     ```python
     if self.showingTeammateTheme:
         self.onShowTheme(self.teammateThemeData['themeID'], self.teammateThemeData['items'])
     else:
         self.onShowTheme(self.player.dtsHallThemeID, set(self.player.dtsHallVehicleAppearanceList))
     ```
   - Disassembly of `ui/main/HallTheme.py:onThemeChange()`:
     ```python
     self._clearOldTheme()   # DESTROYS all background models, sfx, and decorations via DestroyImmediate!
     self.currentThemeID = themeID
     self._createNewTheme(self.currentThemeID)
     ```
   - **THE ROOT CAUSE**: In the client, `self.player.dtsHallThemeID` defaults to `0`!
   - In table `0x5f10aa7e` (`data_hall_theme`), valid theme IDs are:
     - `270000`: Default Classic Theme (Motorcycle, garage, industrial lights, etc.)
     - `270001` - `270004`, `279001` - `279011`: Other unlockable themes
     - **Theme `0` does not exist!**
   - When `_createNewTheme(0)` executes, looking up `0` in `data_hall_theme` returns `None`. Nothing is instantiated. All existing models were destroyed by `_clearOldTheme()`, leaving a **completely pitch black background with no lights**!

### C. Recommended Fix
1. Ensure the player's `dtsHallThemeID` is set to `270000` (instead of `0`) in `data/player_state.json` and in `athlete_mobile_stream.bin` / property updates.
2. In `local_baseapp_capture.py`, if the client requests theme updates or enters/leaves theme, sync `onUpdateDtsHallThemeID(270000)`.

---

## 3. Issue 2: "Supreme Supply" (Monthly Supply, KIND 7) Blank/Black Tab

### A. The Symptoms
In the **SUPPLY** UI:
- **STAR SUPPLY**, **LOOKS SUPPLY**, **VEHICLE SUPPLY**, and **FIREARMS SUPPLY** render 3D scenes, prize lists, and draw buttons.
- **SUPREME SUPPLY** renders completely blank / black.

### B. Root Cause Analysis (Bytecode Disassembly)
1. Looked into `ui/UIMonthlySupplyPackage.py`:
   ```python
   def on_enter(self):
       ...
       curMonthSupplementID = self.getLocalMonthlySupplementID()
       ...
       if curMonthSupplementID:
           self.StartCoroutine('startMonthSupplyAnimCoro_FewUI', curMonthSupplementID)
       # If curMonthSupplementID is None, it falls through and does nothing!
   ```
2. Looked into `common/supplement_utils.py:getCurrentMonthSupplementID()`:
   ```python
   curTime = time.time()
   for k, v in legacyProperties.iterMonthSupplementParamData():
       startTime = time.mktime(time.strptime(v.START_TIME, '%Y.%m.%d %H:%M:%S'))
       endTime = time.mktime(time.strptime(v.END_TIME, '%Y.%m.%d %H:%M:%S'))
       if startTime <= curTime < endTime:
           return v.SUPPLEMENT_ID
   return None
   ```
3. Inspected table `0x5c64e12a` (`data_month_supplement_param`):
   - Record #62: `SUPPLEMENT_ID: 9765`, `START_TIME: '2018.11.14 0:1:0'`, `END_TIME: '2021.12.30 0:0:0'`
   - **All 62 records expired on or before December 30, 2021!**
   - In year 2026, `curTime` > `endTime` for every single entry, so `getCurrentMonthSupplementID()` returns `None`.
   - Without a valid `SUPPLEMENT_ID`, the client aborts loading the Supreme Supply UI components.

### C. Recommended Fix
Choose either of the two approaches:
1. **Client Asset Table Patch (Preferred)**:
   In `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/assets.npk` (or APK assets.npk), modify entry 62 in member `0x5c64e12a` so that `END_TIME` is `'2030.12.30 0:0:0'`.
   Once patched, `getCurrentMonthSupplementID()` will return `9765`, immediately unlocking Supreme Supply.
2. **Alternative (Time Spoofing)**:
   Set device system time to 2021 (caution: verify if TLS cert validity period covers it).

---

## 4. Issue 3: "Looks Draw" & Supply Draw Mechanics

### A. The Draw Protocol
1. **Client Request**:
   - Single Draw: exposed method `0xda` (`openSupplyBox`, base index 467)
     - Arguments: `INT32 supplementID, INT32 currencyID, ARRAY<INT32>, BOOL`
   - 10x Draw: exposed method `0xdc` (`openMultipleSupplyBox`, base index 469)
2. **Server Reply**:
   - Client expects `onOpenSupplyBox(INT32 id, PYTHON appearanceIDs, BOOL isWatchAd)` (method index 387) or `onMultiOpenSupplyBox(INT32 id, PYTHON appearanceIDs)` (method index 389).
3. **Prizes & Inventory**:
   - Pool: `SUPPLEMENT_LIST` + `GUARANTEE_LIST` from `data_supplement` (`0x9e1c8652`), expanded via hall prop table `0x5081e268`.
   - To make won items appear in Depot, call `grant_appearance_prizes()` which sends `onAddDtsAppearanceItem` (idx 335) and saves to `data/player_inventory.json`.
4. **Currency Deductions**:
   - Star Supply uses Diamonds (Currency ID 2, `onYBUpdated` idx 203).
   - Looks Supply uses Color Diamonds (Currency ID 9, `onCurrencyUpdated` idx 204).
   - `local_baseapp_capture.py` has `_charge_store_currency(sock, addr, key, cur, price)`. Verify that Currency 9 is populated in player profile so the client does not block the draw locally for insufficient funds.

---

## 5. Summary of Files & Key Tools

| File / Path | Purpose |
|:---|:---|
| `mitm/local_baseapp_capture.py` | Main server implementation (traffic routing, UDP RPCs, mall/draw handlers). |
| `data/player_state.json` | Persistent equipped appearance, gender, and theme settings. |
| `data/player_inventory.json` | Persistent player cosmetic inventory. |
| `tools/load_table.py` | Reads and parses tables from `assets.npk` by member signature. |
| `tools/script_disas.py` | Disassembles Python bytecode from client `script.npk`. |
| `tools/script_query.py` | Finds scripts containing specific symbol/function names. |
| `scratch/inspect_month_supply.py` | Inspects month supplement table `0x5c64e12a`. |
| `scratch/uihalltheme_disas.txt` | Bytecode dump of `UIHallThemeMall.py`. |

---

## 6. Suggested Action Plan for Muse Spark

1. **Fix Lobby Theme Blackout**:
   - In `data/player_state.json` and `local_baseapp_capture.py`, set default `dtsHallThemeID` to `270000`.
   - Send `onUpdateDtsHallThemeID(270000)` on hall entry so `_createNewTheme` never receives `0`.
2. **Fix Supreme Supply**:
   - Patch `0x5c64e12a` in `assets.npk` to extend record #62 `END_TIME` to `2030.12.30 0:0:0`.
   - Push updated `assets.npk` to `/sdcard/Android/data/com.netease.chiji/files/netease/h45na/assets.npk`.
3. **Verify Looks Draw**:
   - Verify initial balance for currency 9 (`COLOUR_DIAMOND`) sent via `onCurrencyUpdated(9, 999999, 0)`.
   - Tap "Draw 1x" or "Draw 10x" on Looks tab and confirm reward animation renders.

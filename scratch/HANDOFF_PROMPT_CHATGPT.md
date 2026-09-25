# HANDOFF TO CHATGPT: Rules of Survival (ROS) Store / Mall UI Blank Tabs Fix

> **Date**: 2026-09-21  
> **Client Version**: Rules of Survival Mobile (Android `com.netease.chiji`, v1.610377.506841, vCode 1117219, arm64-v8a)  
> **Environment**: Windows Host + LDPlayer 9 (`emulator-5554`, Guest IP `172.16.1.15`, Gateway `172.16.1.2`)  
> **Repository Root**: `C:\Users\Raysoo\Downloads\ROS_RE`  
> **Active Server Script**: `mitm/local_baseapp_capture.py` (UDP :25000 LoginApp, UDP :25010 BaseApp, HTTP :80/:443/:8443)

---

## 1. Executive Summary & Context

We are emulating a NetEase Rules of Survival (BigWorld Mercury engine) private server.
Gates 0 to 4 are fully operational:
- **Gate 0-1**: CDN/Patch & UniSDK HTTP Auth bypass.
- **Gate 2-3**: Mercury UDP handshake on :25000 & :25010, Blowfish `pc_variant` session key encryption, `Account` (type 38, eid 1) login.
- **Gate 4**: `Athlete` (type 51, eid 1) character load, scene preload (`showSelectCharacter`), 3D Hall Lobby entry (`Dev | Raysoo` with custom avatar, black wings, sun halo, motorbike, 999k diamonds/gold).
- **Gate 6**: Supply Gacha box draws, cosmetic persistence (`player_inventory.json`).

### Current Problem Being Solved: Gate 5 — Store / Mall UI
When entering the in-game **Store (Mall)**, tabs (Suggested, Packs, Looks, Firearms, Others, Suit Mall) were showing **blank/empty** grids.
We have already **successfully cracked and visually verified** the Suggested tab (it rendered banners, 3D Mossback model, and 2x3 items grid), but **switching tabs or opening Store freshly still renders blank tabs**.

---

## 2. What Has Been Fixed & Verified (Current Wins)

1. **Store Data Tables Identified & Extracted from `assets.npk`**:
   - `0x832995b1` (`data_mall.2`): Suggested / Packs / Sundry (Others)
   - `0x878e57c9` (`data_mall.1`): Looks / Cloth
   - `0x55977219` (`data_mall_goods_gun`): Firearms
   - `0x9fb2d5d5` (`data_mall_suit`): Suit Mall Bundles
   - Function in `mitm/local_baseapp_capture.py`: `_mall_tables()` merges all 4 tables (807 total records, 670 visible).

2. **Client RPC Vector on Athlete (1,131 methods total)**:
   - `[ 448] onQueryAvailableMallGoods(PYTHON goodsDict)`: Generic mall goods reply.
   - `[ 449] onQueryAvailableMallGoodsByType(UINT32 type, PYTHON goodsDict)`: Location-specific mall goods reply.
   - `[ 450] onQueryAvailableMallGoodsForAppearanceMall(PYTHON goodsDict)`: **Authoritative callback for the default "Suggested" tab (`UIDtsAppearanceMall`)!**
   - `[ 441] onBuyMallGood(ARRAY<INT32> props)`: Mall purchase success callback.
   - `[ 203] updateDevDiamond(INT64 free, INT64 pay, INT32)`: Currency update (Diamonds).
   - `[ 204] updateDevCurrency(INT32 id, INT64 amount, INT32)`: Currency update (Gold, Tokens).

3. **Live Visual Proof of Working Suggested Mall (`scratch/live_screen_resumed.png`)**:
   - Using `scratch/push_live_mall.py`, we sent client method `450` (`onQueryAvailableMallGoodsForAppearanceMall`) and `448`/`449`.
   - Result: The Suggested tab immediately rendered:
     - Header banner: *"I'M DARKER THAN ANY GRIM TALE"*
     - 3D Preview: "Mossback" model with accessories
     - 2x3 Grid: "New Arrivals" (S16-Mossback crate, Skull Merc & Enhanced, Stormbringer - Gold) and "Hot" (Dual blades, Chainsaw), with 9,999 diamonds prices.

---

## 3. What is NOT Yet Fixed (The Blocker)

### A. The Client's `is_enter` Guard
In decrypted `entities/iMall.py`:
```python
def onQueryAvailableMallGoods(self, availableMallGoodsDict):
    self.availableMallGoodsDict = availableMallGoodsDict
    if Globals.uiMgr.UIMall and Globals.uiMgr.UIMall.is_enter:
        Globals.uiMgr.UIMall.onQueryAvailableMallGoods(dict(filter(mallFilter, availableMallGoodsDict.items())))
    elif Globals.uiMgr.UIMallCloth and Globals.uiMgr.UIMallCloth.is_enter:
        Globals.uiMgr.UIMallCloth.onQueryAvailableMallGoods(dict(filter(clothMallFilter, availableMallGoodsDict.items())))
    elif Globals.uiMgr.UIMallSundry and Globals.uiMgr.UIMallSundry.is_enter:
        ...
```
And in `onQueryAvailableMallGoodsForAppearanceMall`:
```python
def onQueryAvailableMallGoodsForAppearanceMall(self, availableAppearanceMallGoodsDict):
    if Globals.uiMgr.UIDtsAppearanceMall and Globals.uiMgr.UIDtsAppearanceMall.is_enter:
        Globals.uiMgr.UIDtsAppearanceMall.onQueryAvailableMallGoods(dict(filter(appearanceMallFilter, ...)))
```
**The root cause**:
If the server only pushes goods at login/hall entry, `Globals.uiMgr.<UI>.is_enter` is `False`. The goods dictionary is never passed into the specific UI instance!
When the user subsequently clicks a tab (e.g. `Packs`), `UIMall.on_enter()` checks `if self.availMallGoods:`—which is `None`!

### B. Upstream Query Handling & Timing in `mitm/local_baseapp_capture.py`
When a tab opens, client code runs `doQueryMallGoodsFromServer()`:
```python
# In UIMall.py (Packs), UIMallCloth.py (Looks), UIWeaponMall.py (Firearms):
if switches.SysEnableOptMall:
    BigWorld.player().queryAvailableMallGoodsByType(self.MallLocationType)
else:
    BigWorld.player().base.queryAvailableMallGoods()

# In UIDtsAppearanceMall.py (Suggested):
super(UIDtsAppearanceMall, self).doQueryMallGoodsFromServer()
BigWorld.player().base.queryAvailableMallGoodsForAppearanceMall()
```
Client upstream calls arrive with exposed method indices:
- `exposed_idx = 310`: `queryAvailableMallGoodsByType(UINT32 type)` (5 bytes)
- `exposed_idx = 311`: `queryAvailableMallGoodsForAppearanceMall()` (1 byte)
- `exposed_idx = 312`: `queryAvailableMallGoods()` (1 byte)

**Why fresh opens still fail**:
1. When the client sends `310` (query by type) with `type = 0` (`GoodsLocationType.ALL`), the server currently only replies with `449 (type=0)`.
2. But in `entities/iMall.py`:
   - `onQueryAvailableMallGoodsByType` with `type=0` calls `self.onQueryAvailableMallGoods(goodsDict)`.
   - `self.onQueryAvailableMallGoods` uses an `if / elif` chain that **only updates the currently open sub-tab**! It does **not** update `UIDtsAppearanceMall` (Suggested), which strictly requires client method `450`!
3. Conversely, when `UIDtsAppearanceMall` opens, it calls `311` (`queryAvailableMallGoodsForAppearanceMall`). The server needs to return `450` **and** `448`/`449` so all tabs are populated.

### C. The `fillGoods2` Filter in `UIMall.py` (Packs Tab)
In `ui/UIMall.py`:
`Awake()` sets:
```python
if self.SHOULD_SHOW_SECONDARY_TITLE:
    self.fillGoods = self.fillGoods2
```
And `fillGoods2()` does:
```python
newProductGoods = filter(lambda x: mall_utils.getMallGoodSecondaryDisplayType(x[0]) == NEW_PRODUCT, allAvailableGoods)
hotProductGoods = filter(lambda x: mall_utils.getMallGoodSecondaryDisplayType(x[0]) == HOT_PRODUCT, allAvailableGoods)
```
Where `getMallGoodSecondaryDisplayType` reads `properties.getMallData(goodID).SECONDARY_DISPLAY_TYPE_ENUM` (1 = `NEW_PRODUCT`, 2 = `HOT_PRODUCT`).
In `0x832995b1`, out of 213 items with `IS_DISPLAY_IN_MALL`, some have `sec_type: 1` or `2`, but others have `None`. Items with `None` are discarded by `fillGoods2`.
Ensure that the items dictionary served contains items with valid `IS_DISPLAY_IN_MALL` and secondary display types.

---

## 4. Key Files and Code Locations

| File | Purpose / Role |
|:---|:---|
| `mitm/local_baseapp_capture.py` | Integrated server script. Handles upstream packets in `handle_upstream_calls()` and mall replies in `_send_mall_query_reply()`. |
| `scratch/push_live_mall.py` | Standalone script that demonstrated the working fix by pushing RPCs 448, 450, and 449 into UDP 25010. |
| `tools/load_table.py` | NPK table reader for APK assets (`0x832995b1`, `0x878e57c9`, `0x55977219`, `0x9fb2d5d5`). |
| `tools/script_disas.py` | Python bytecode disassembler for mobile `script.npk`. |
| `scratch/live_screen_resumed.png` | Screenshot of working Suggested Mall with 3D model & items. |
| `scratch/live_screen_packs_test.png` | Screenshot showing Packs tab open but empty grid. |

---

## 5. Exact Implementation Plan to Fix the Remaining Tabs

In `mitm/local_baseapp_capture.py`:

### Step 1: Update `_send_mall_query_reply()`
Whenever ANY mall query arrives (`310`, `311`, or `312`), or whenever Store is queried:
The server should send a **complete multi-RPC response burst**:
1. **Client Method `450`** (`onQueryAvailableMallGoodsForAppearanceMall`):
   Payload: Pickled dict of all visible goods (`_mall_runtime_goods()`).
   *This guarantees `UIDtsAppearanceMall` (Suggested) renders whenever it is active.*
2. **Client Method `448`** (`onQueryAvailableMallGoods`):
   Payload: Pickled dict of all visible goods.
   *This guarantees whichever sub-tab is currently entered (`UIMall`, `UIMallCloth`, `UIWeaponMall`, `UIMallSuit`, `UIMallSundry`) receives the data.*
3. **Client Method `449`** (`onQueryAvailableMallGoodsByType`):
   Send for `type = 0` (`ALL`), `type = 8` (`MALL` / Packs), `type = 128` (`CLOTH_MALL` / Looks), `type = 512` (`WEAPON_MALL` / Firearms), `type = 1024` (`SUIT_MALL`), and `type = 32` (`SUNDRY_MALL` / Others).
   *This guarantees sub-UIs that listen via `onUIGetGoods` also receive the data directly regardless of `is_enter` timing.*

### Step 2: Ensure Server Upstream Router Catches All Tab Switches
In `handle_upstream_calls()` in `local_baseapp_capture.py`:
```python
if name in ('queryAvailableMallGoods', 'queryAvailableMallGoodsByType', 'queryAvailableMallGoodsForAppearanceMall'):
    _send_all_mall_replies(sock, addr, key)
    continue
```
Remove any `_seen_exposed` suppression for mall queries so repeated tab clicks always receive fresh data.

### Step 3: Verify Live with ADB Tap Commands
Screen resolution is 1920x1080:
- Open Store from Lobby: `adb shell input tap 40 240`
- Verify Suggested Tab: Check banner, 3D model, items grid.
- Tap PACKS: `adb shell input tap 90 250` -> Capture screenshot, verify pack cards.
- Tap LOOKS: `adb shell input tap 90 340` -> Capture screenshot, verify clothing cards.
- Tap FIREARMS: `adb shell input tap 90 430` -> Capture screenshot, verify weapon skins.
- Tap OTHERS: `adb shell input tap 90 620` -> Capture screenshot, verify sundry items.

---

## 6. Verification Status Checklist

- [x] Blowfish session key decryption working
- [x] Client method indices 448, 449, 450 identified
- [x] Suggested Tab (Appearance Mall) visually rendered (`live_screen_resumed.png`)
- [ ] Packs Tab (`UIMall`) rendering cards
- [ ] Looks Tab (`UIMallCloth`) rendering cards
- [ ] Firearms Tab (`UIWeaponMall`) rendering cards
- [ ] Others Tab (`UIMallSundry`) rendering cards
- [ ] Automatic multi-RPC reply integrated into `local_baseapp_capture.py`

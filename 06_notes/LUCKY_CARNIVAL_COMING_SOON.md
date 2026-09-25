# Lucky Carnival: “COMING SOON” investigation

## Live status — 2026-09-22

Screenshot: `scratch/carnival_current.png`

The visible page is **Lucky Carnival**, reached from the hall’s Carnival route. It is not a Supply tab. The wheel is present, but its center says **COMING SOON**, and the right-side text overlaps. The weekly progress panel still renders (`0/30`).

## Verified cause

The hall bootstrap in `mitm/local_baseapp_capture.py` sends Athlete client method **745**, `onUpdateLuckyCarnivalData(PYTHON)`, after the preserved Stage-4 login sequence.

That RPC was added for a separate verified reason: without it the client aborts fresh hall initialization on missing `iLuckyCarnivalIsSuper`. The current payload is deliberately a safe empty/default object:

```python
{
  'operation': 0,
  'luckySeasonDraws': 0,
  'luckyRoundCloseTime': 0,
  'luckySeasonNo': 0,
  'luckyRoundBuff': 0,
  'luckyRoundState': 0,
  'luckySeasonEndTime': 0,
  'luckySeasonGiftGotState': [],
  'luckyRoundGotIndex': [],
  'luckyRoundGift': [],
  'luckyRoundDraws': 0,
  'luckyRoundNo': 0,
  'luckySeasonCharge': 0,
  'luckyRoundGiftValue': [],
  'luckyRoundRefreshTime': 0,
  'luckyRoundIsSuper': False,
  'luckyRoundByRecommend': False,
}
```

This avoids the missing-attribute crash, but is not a valid active Carnival season/round. The screenshot is expected from that state. Do not remove RPC 745 just to hide the panel; doing so reintroduces the hall-init failure.

## Known client/server vocabulary

- Client UI module: `ui/UILuckyCarnival.py`.
- Client common data module: `common/lucky_carnival_common.py`.
- Athlete exposed calls: `onDoLuckyLottery` 897, `onOpenLuckyCarnival` 898, `onGetLuckySeasonGift` 899, `tryGetCurrentLuckyCarnivalDiamond` 900, `tryGetLuckyCarnivalDiamondPrizeRecord` 901, `tryGetLuckyCarnivalRoundTempGift` 902.
- Related client callbacks in the verified method table: `onUpdateLuckyCarnivalData` 745, `onShowOldCarnivalBg` 750, `onShowNewCarnivalBg` 751, plus 744/746–748 nearby.
- Existing code comment around `mitm/local_baseapp_capture.py` line 1674 verifies only the index/name mapping; it does **not** prove the active-state record shape.

## Required evidence before changing behavior

1. Disassemble `ui/UILuckyCarnival.py` methods that decide `COMING SOON`, initialize the wheel, update the countdown, and handle DRAW/USE. Use `tools/script_disas.py` and record exact branch fields/constants.
2. Disassemble `common/lucky_carnival_common.py` functions that parse season/round/turntable data. Locate the static table(s) in `assets.npk` by member signature and document their schemas.
3. Capture the outbound exposed call(s) caused by opening Lucky Carnival and pressing its actionable controls. Map their method index and argument shape before implementing replies.
4. Build the smallest active, future-dated record that satisfies the client’s exact branch conditions. Do not invent fields, dates, or IDs.
5. Send the validated state via RPC 745 after `enterHall`, then send any separately required background/state callbacks only if the client code proves they are required.
6. Live-test from a fresh login. Verify: active wheel replaces COMING SOON; countdown is coherent; a draw produces one upstream call per tap; response updates the wheel/reward UI; no `SCRIPT ERROR`; hall remains clean after Back.

## Constraints

- Local/LAN only; never call production NetEase services.
- Do not use `iProxy.sendHotfix`, `tps.run_hotfix`, or any server-to-client code execution route.
- Do not change the verified Stage-4 order: `showSelectCharacter([]) -> onCreateCharacter -> onRoleCreateSuc -> updateBaseCharacter -> updateBaseNickname -> enterHall`.
- Keep RPC 745; replace only its all-zero placeholder after the shape is proven.
- A method message must remain <= 65,535 bytes; fragment Mercury packets as the existing sender already does.
- Every code change requires a live test, note update, and atomic commit. Do not commit `mitm/mitm_serve.py` or `mitm/captures/SERVE_B.txt`.

## 2026-09-25 Update — wheel is active, but the Draw button is dead (client-side)

This whole file predates the current state. As of `checkpoint: sync verified working lobby build`
(commit `0c2390b6`, made by another agent in a session not visible here), RPC 745 now sends a real
active-round record (`_carnival_payload()` in `mitm/local_baseapp_capture.py`, `luckyRoundState=1`),
`onDoLuckyLottery`/`onOpenLuckyCarnival`/etc. are wired in `_CARNIVAL_EXPOSED` and
`handle_upstream_calls`, and reward granting (`_grant_carnival_prize`) works. Live-tested: opening
**Carnival** from the hall now shows the real 16-slot wheel (not "COMING SOON"), with a live
countdown, "This week's Progress: 0/30", and a lit "💎10 Draw" button — matching
`refreshLuckyCarnivaPanel`'s gate on `iLuckyCarnivalRoundState == ROUND_STATE_OPEN(1)`.

**New, still-open bug: the Draw button itself does nothing.** Verified with both `adb input tap`
and the user's real finger, twice, with a clean `adb logcat -c` before each attempt:
- Zero `<SCRIPT>`-tagged output of any kind (not even a non-error print) around the tap.
- Zero upstream Mercury call reaches the server (`onDoLuckyLottery` never logged by
  `handle_upstream_calls`'s `_seen_exposed` tracker, which logs every distinct `(method,len)` pair
  including unmapped ones).
- No visible reaction (no toast, no button dim/bright change, no popup).
- `uiautomator dump` confirms the touch surface is a single opaque `1920x1080` view and taps land
  at the exact pixel expected (ruled out any coordinate/DPI mapping bug).
- BACK and other hall buttons respond fine in the same session, so input dispatch to the app works
  in general.

Disassembly of `ui/UILuckyCarnival.py` / `UILuckyCarnivalAdvance.py` / `UILuckyCarnivalSuper.py`
`onLotteryBtnClicked` + `genNeedYB` (via `tools/script_disas.py`) shows the gating logic (switches
flag, `checkLastLotteryIsMark`, `checkWelfareValid`, currency check) all resolve favorably for a
fresh dev account's first draw (`iLuckyCarnivalRoundDraws==0` skips the currency check entirely per
the client's own "first draw free" logic) and none of it should require a script error. Since no
Python code runs at all (not even the touch-phase-Ended guard at the top of the function), the touch
is most likely being consumed before it reaches this widget's binding — at the native Cocos
touch-dispatch / hit-test level, possibly by another overlay node (the wheel screen also renders a
"Congratulations! ... Claim `<N>` Diamond" winner-broadcast ticker that may have an oversized
invisible touch-catcher). This has **not** been proven; it needs a native Frida hook on the touch
dispatcher (not just the Python VM) to confirm which node actually claims the touch. Frida
infrastructure already exists (`mitm/frida_run.py`, `/data/local/tmp/frida-server` on the emulator,
confirmed startable via `su -c 'nohup /data/local/tmp/frida-server -D ...'`), but no touch-dispatch
hook script exists yet — this is the next concrete step if/when this bug is picked back up.

## 2026-09-25 Daily-rotating wheel pool (implemented)

User ask: make the wheel's displayed items rotate periodically (not the same 16 every time) so it
doesn't get stale, changing roughly every 24 hours. Investigated whether an official "Fits of Fury"
item set exists in this build's extracted assets to seed the pool with — it does not, verifiably:
- `scratch/find_fits_of_fury.py` over every `assets.npk` member found only two unrelated Chinese-text
  hits (a weapon 2/4-piece combo-bonus set named 狂怒 "Fury" in table `0x20d8ba8b`, SUIT_ID 7 — a
  gunplay stat bonus, not a wearable set) and zombie AI behavior-tree file paths containing the word
  "fury" (table `0x389a85b1`) — neither is a cosmetic costume.
- All `NAME` fields on hall-prop tables (e.g. `0xc656e064`) are `_g89na_trans('<md5>')` placeholders;
  `tools/load_table.py` deliberately does not resolve them (no English string table has been
  extracted into this repo yet), so item display names are only knowable live, from the running
  client's own resources, not from static table dumps. Do not assert an item's marketing name from
  its hash — verify with a screenshot instead.

Since the specific named set couldn't be verified, the rotation was built from the wheel's own real
candidate pool instead of invented ids: `LuckyCarnivalRoundReward` (table `0x237dd2bb`, 1977 rows).
Each row already carries `HALL_PROP_ID`, `ITEM_VALUE` (1=common/2=uncommon/3=rare rarity tag) and
`TURNTABLE_TYPE` (`(0,)`=988 rows for the normal wheel we use, `(1,)`=318 and `(2,)`=669 for the
Advance/Super wheel variants we don't currently serve).

`mitm/local_baseapp_capture.py`: `_carnival_daily_pool(day_ordinal)` filters to `TURNTABLE_TYPE==(0,)`
+ `ITEM_ENABLE`, buckets by `ITEM_VALUE`, and deterministically shuffles each bucket with
`random.Random(day_ordinal)` (so the pick is stable all day and reproducible, not from decompiled
ground truth — a private-server QoL choice) before taking 3 rare + 8 uncommon + 5 common = 16 ids,
mirroring the mostly-common/uncommon-with-a-couple-of-rares shape of the live wheel. New helper
`_carnival_gift_and_values()` caches this per `datetime.date.today()` and, when the day rolls over,
also resets `got_index`/`draws` (old slot claims don't carry meaning against a new pool) and bumps
`round_no`. `_carnival_payload()` and `_handle_do_lucky_lottery()` now read the pool through this
helper instead of the old fixed `_CARNIVAL_GIFT = range(1,17)` constant.

Live-tested 2026-09-25: relogged in, server log shows `CARNIVAL: rotated daily pool day=... gift=...`
on first Carnival-panel-triggering activity after restart, wheel renders 16 icons from the new pool.
The Draw-button bug above is unaffected either way (pool content isn't the blocker).

## 2026-09-25 "Fists of Fury" identified — the 拳王 (Boxing King) 6-piece set

User's actual ask was "Fists of Fury" (not "Fits of Fury" as first misheard). Re-searched assets.npk
for the corrected name and its likely Chinese equivalents; still no literal EN string anywhere (see
above — item names are untranslated `_g89na_trans(md5)` placeholders in every table), but "拳王"
("Boxing King") and "拳霸" ("Boxing Tyrant") hit repeatedly, and their icon paths confirm a themed
boxer/fist costume set — the most plausible source for whatever localized EN name the user saw:

| Piece | Hall-prop id | Table | PROP_TYPE | Icon |
|---|---|---|---|---|
| Head | 101111 | `0xa2f095a2` | BobyAppearanceType (PART 1111) | `head/male_head_quanwang.png` |
| Hair | 102119 | `0xa2f095a2` | BobyAppearanceType (PART 2119, CATEGORY 2) | `hair/img_quanwang_hair.png` |
| Goggles | 105037 | `0xa2f095a2` | DecorationAppearanceType (PART 8102, CATEGORY 12) | `deco/img_quanwang_yanzhao.png` |
| Headband | 110007 | `0xa2f095a2` | WearableApperanceType | `helmet/img_quanwang_fadai.png` |
| Top | 111020 | `0xa2f095a2` | WearableApperanceType (CATEGORY 2) | `body/img_quanwang_yi.png` |
| Pants | 112020 | `0xa2f095a2` | WearableApperanceType (CATEGORY 3) | `leg/img_quanwang_ku.png` |

All 6 are QUALITY 4-5 and already resolve cleanly through the existing `_prop_tables()` /
`_get_appearance_slot()` machinery (table `0xa2f095a2` was already in the scanned list) — no prop-
resolution code change was needed, only wiring them into a reward path. Found via
`0x207bb152` (raw `PartModel` geometry table, parts 1111/2119/3019/3119/4045/4145/5034/5134/8002)
cross-referenced against every table containing a `'PART': <id>` back-reference (see session
transcript for the exact regex sweep) to find the sellable `Prop`-wrapped ids.

**Caveat:** all 6 pieces carry `EXCHANGE_SERIE: 500013`, meaning in the live game they belong to a
token/coupon **Exchange Shop** (client RPCs `[524] onQueryAvailableExchangeItem` /
`[525] onExchangeItem`, `entities/iItemExchange.py`, `ui/UIItemExchange.py` — listed as unimplemented
in `06_notes/HALL_DEEP_DIVE_2026-09-24.md` §6), not the Lucky Carnival wheel's native reward table
(0x237dd2bb has no row for any of these 6 ids).

**REVERTED same day — breaks the wheel live.** The first attempt injected these ids directly into
the wheel's `luckyRoundGift` list as `-hall_prop_id` (a "grant this hall-prop id directly, skip the
reward-table lookup" convention). Live-tested by the user (both via `adb input tap` and their own
finger, in the real Carnival panel, not the unrelated Store "LUCKY CLUB" top-up page which looks
similar and was briefly confused for it): the panel froze on the CSB default "Claimed" placeholder,
the countdown stopped ticking, and even **BACK stopped responding** — a hard hang, not a cosmetic
glitch. This is exactly the failure this same file already warned about further up: the client's
`initPanelLotteryItem` calls `getLuckyCarnivalRoundRewardData(id).HALL_PROP_ID` against the
**client's own bundled copy** of table `0x237dd2bb` — an id with no row there returns `None` and
aborts `on_enter` entirely, taking the countdown/Back/cleanup wiring down with it. The server cannot
invent new rows in a table the client already has baked into its APK; every id sent to the wheel
must already exist as a row there. Removed the negative-id branch from `_carnival_daily_pool()`; the
wheel is back to 16 real reward-table ids only (verified fix, server restarted, see commit history).

**Where "Fists of Fury" actually went instead:** since it can never legitimately appear on this
wheel, it's granted straight to the account at hall bootstrap (`run_baseapp_stage_machine()`, right
after `hall_state_rpcs`), one time only (guarded by checking `data/player_inventory.json` for the 6
ids first), via `grant_appearance_prizes()` — the same already-verified RPC 335
(`onAddDtsAppearanceItem`) path Supply/Store prizes use. It lands in inventory; equip it from
**Depot**. `_CARNIVAL_PREMIUM_HALL_PROPS` is kept as the single source of the 6 ids for this grant.

## 2026-09-25 Select-controls relogin loop — untested mitigation, and proof it predates today

While re-testing the Carnival fix, the "network timeout -> back to Select Controls -> Loading ->
Lobby (no Daily Claim)" loop from earlier in the day (see LOGIN_FLOW_TRACE.md 2026-09-25) recurred
repeatedly, along with a top-bar currency stuck at the `283283` CSB placeholder (even after 3
`onGPUpdated`/`onSPUpdated`/`onYBUpdated(999999)` retries to a confirmed-alive session over 150s+)
and a stray "SUPPORT DROID / HUMAN" selector floating above the character in the hall.

**Isolation proof these are pre-existing, not caused by today's Carnival/grant work:** at the user's
request, removed the Fists-of-Fury grant/equip code entirely and reset `data/player_state.json`,
then separately ran the **untouched** `ros_offline_server_backup` copy (synced this morning, before
any of today's changes) unmodified. Both reproduced the identical currency/UI symptoms; the backup
run additionally surfaced what looked like real (non-local) account/team data (a Chinese nickname,
a live team roster with "Haven't Paid" tags) — stopped immediately out of caution per the
Local/LAN-only rule, most likely stale cached client state rather than a live leak, but not verified
either way. Conclusion: none of this is a regression from today's session.

**Mitigation attempted (unverified, one clean run only):** `Athlete.onQueryAvailableSupplement`
(idx 392) is a ~39KB payload needing ~27-29 fragmented UDP datagrams. It used to fire inline in
`hall_state_rpcs`, i.e. immediately after `showSelectCharacter`/`enterHall`, landing right on top of
the client's Select-Controls scene transition. Deferred it by `ROS_SUPPLEMENT_DELAY` seconds
(default 4) via a one-shot `threading.Timer` instead of sending it inline
(`mitm/local_baseapp_capture.py`, `send_character_creation_response_chain`). One fresh relaunch after
this change completed in a single STAGE1-5 cycle with no relogin — better than the two back-to-back
loops seen immediately before it — but one clean run does not prove the fix; the loop was already
intermittent before today. Needs several more repeated cold-launch trials to know if this actually
helps or if it was a lucky run.

**Still unresolved, confirmed pre-existing, needs its own session:**
- Top-bar currency (3 slots, all showing `283283`) never updates despite repeated correct-value RPCs to a stable session — the RPC/id mapping for these specific slots in this hall top-bar layout is not what `onGPUpdated`/`onSPUpdated`/`onYBUpdated` feed (per `06_notes/HALL_DEEP_DIVE_2026-09-24.md`, likely needs the generic `onCurrencyUpdated(id, val, src)` idx 204 with the correct currency ids for these particular slots, not yet identified).
- Stray "SUPPORT DROID / HUMAN" selector above the character, overlapping "Share" buttons, garbled "Finish"/"check the..." text — matches the already-documented "hall UI non-deterministic" family of issues.
- Daily Claim popup not appearing on a fresh login.

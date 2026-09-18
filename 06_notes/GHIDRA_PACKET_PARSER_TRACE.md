# Ghidra packet-parser trace: root cause and complete resolution of the phantom "authenticate" (id 0) corruption

## Objective

Trace the client's receive path byte-for-byte, from raw UDP payload to
`Bundle::iterator::unpack`'s message-ID extraction, to determine exactly
which byte/offset/state causes every packet this project's server sends
(`local_baseapp_capture.py`) to be misread as containing a trailing,
truncated `ClientInterface::authenticate` (message id 0) call — the bug
that currently prevents progress past `ServerConnection::logOn:
status==LOGGED_ON` toward Account/Avatar/Character Creation.

---

## Current Confirmed State

```
Login -> LoginApp -> BaseApp -> createBasePlayer -> LOGGED_ON
      -> Reliable Channel Establishment (packet #0 ACKed)
      -> Client receives BaseApp traffic (versionPointIdentity, setGameTime, entity RPCs)
      -> Nub::processFilteredPacket
      -> Nub::processPacket
      -> Bundle::iterator::unpack
      -> corrupted/phantom "authenticate" (message ID 0)
      -> Account / Character Creation NOT reached
```

- **LoginApp authentication**: PASS (UDP 25000, 4-byte LE ReplyID @ offset 5, Blowfish `pc_variant` IV=0).
- **BaseApp login**: PASS (`baseAppLogin` request/reply correlated, status=1).
- **Reliable ACK handling**: PASS (`FLAG_ON_CHANNEL | FLAG_HAS_ACKS = 0x000c`, seq 0 ACKed, inactivity timer stops).
- **createBasePlayer**: PASS (`id: 1, type: 127 Account`, `status==LOGGED_ON`).
- **The Blocker**: Client repeatedly logs:
  ```
  Bundle::iterator::unpack( authenticate ): Not enough data on stream at 11 for payload (1 left, needed 4)
  Nub::processOrderedPacket( 172.16.1.2:25010 ): Discarding bundle due to corrupted header for message id 0
  ```
  This trace investigates and fully solves this blocker.

---

## processFilteredPacket (`FUN_00a8fa30`, static `0x98fa30`)

- **Signature**: `int FUN_00a8fa30(long param_1, undefined8 param_2, long *param_3, undefined1 *param_4)`
- **Caller**: `FUN_00a96f2c` (immediately after `in_place_decrypt` / `FUN_00a8924c`) and `FUN_00a8d380` (unfiltered/raw ingress).
- **Parameters**:
  - `param_1`: `Nub*`
  - `param_2`: `Endpoint*` (remote socket address)
  - `param_3`: `Packet*` (the packet object)
  - `param_4`: output status flags

### Header & Flags Consumption Sequence

1. **Wire Flags Extraction**:
   - `puVar33 = (uint *)(param_3 + 0xc);` (byte offset `0x60` from `param_3` as `long*`).
   - `uVar6 = (ushort)*puVar33;` reads the 16-bit little-endian wire flags at offset `0..1` of the packet data buffer.
   - Guard check: `if (uVar6 < 0x400)` (flags must be strictly less than 10 bits; rejected otherwise).

2. **Bit Meanings in `processFilteredPacket`**:

| Bit | Hex Value | Name | Decompiled Action & Footer Consumed |
|:---:|:---:|:---|:---|
| **0** | `0x0001` | `FLAG_HAS_REQUESTS` | Processed downstream in `Nub::processPacket`. Gates 2-byte first request offset. |
| **1** | `0x0002` | `FLAG_HAS_PIGGYBACKS` | Lines 574–609. Gates the piggyback message reassembly loop. Reads 2-byte piggyback length from tail, allocates sub-packet, recursively invokes `processFilteredPacket`. When 0, branch is completely bypassed. |
| **2** | `0x0004` | `FLAG_HAS_ACKS` | Lines 399–472. Peels 1-byte ACK count from tail (`packet+0x1a -= 1`, `packet+0x1c += 1`). Then for each ACK peels 4-byte sequence number from tail (`packet+0x1a -= 4`, `packet+0x1c += 4`). Calls `Channel::handleAck` (`FUN_00a86898`) -> `delResendTimer()`. |
| **3** | `0x0008` | `FLAG_ON_CHANNEL` | Lines 486–500. Resolves destination `Channel` object from `Nub+0x41f0` by remote endpoint. If not found, drops packet: `Dropping packet due to absence of local channel`. If 0, packet is treated as unchannelled (`local_138 = 0`). |
| **4** | `0x0010` | `FLAG_IS_RELIABLE` | Lines 300–310. Reliable delivery. Checks that sequence number exists (`param_3[9] != 0x10000000`); drops otherwise. |
| **5** | `0x0020` | `FLAG_ORDERED_STREAM` | Gates packet sequencing / queueing into channel bundle cache. |
| **6** | `0x0040` | `FLAG_HAS_SEQUENCE_NUMBER` | Lines 278–299. Peels 4-byte sequence number from tail (`packet+0x1a -= 4`, `packet+0x1c += 4`). Stored at `packet+0x48`. |
| **7** | `0x0080` | `FLAG_INDEXED_CHANNEL` | Lines 528–572. Peels 8 bytes from tail (4 bytes channelID, 4 bytes subID). Calls indexed channel finder. |
| **8** | `0x0100` | `FLAG_HAS_CHECKSUM` | Lines 95–106. Peels 4-byte CRC32 from tail (`packet+0x1a -= 4`, `packet+0x1c += 4`). Verifies NEON-accelerated XOR-fold checksum. |
| **9** | `0x0200` | `FLAG_CREATE_CHANNEL` | Combined with `Nub+0x4460` and channel handshake state (`channel+0x105`). |

3. **Invocation of `Nub::processPacket`**:
   - At line 373: `iVar14 = FUN_00a90b14(param_1, param_2, plVar28, local_138);`
   - Passes the `Packet*` object with all outer footers already stripped.

---

## Nub::processPacket (`FUN_00a90b14`, static `0x990b14`)

- **Signature**: `undefined4 FUN_00a90b14(long param_1, undefined8 *param_2, long *param_3, long param_4)`
- **Caller**: `FUN_00a8fa30` (`Nub::processFilteredPacket`).

### Bit 0 (`FLAG_HAS_REQUESTS = 0x0001`) Handling
Lines 58–77:
```c
uVar2 = *(ushort *)(param_3 + 0xc);           // re-reads flags at packet buffer offset 0
if ((uVar2 & 1) != 0) {                        // FLAG_HAS_REQUESTS
    uVar3 = *(ushort *)((long)param_3 + 0x1a); // remaining data length
    if (3 < uVar3) {
      *(ushort *)((long)param_3 + 0x1a) = uVar3 - 2;   // STEALS 2 BYTES FROM THE TAIL
      *(short *)((long)param_3 + 0x1c) = *(short *)((long)param_3 + 0x1c) + 2;
      *(undefined2 *)(param_3 + 4) =
           *(undefined2 *)((long)param_3 + (ulong)(ushort)(uVar3 - 2) + 0x60);
      goto LAB_00a90b9c;
    }
}
```
- **Crucial Rule**:
  - If Bit 0 is **SET** (`0x0001`): The last 2 bytes of the payload are stolen as the `first request offset` and stored at `packet + 0x20`.
  - If Bit 0 is **NOT SET** (`0x0000`, `0x0008`, `0x000c`, etc.): **NO 2-BYTE THEFT OCCURS**. `packet + 0x1a` remains unchanged.

### Bundle Construction & Message Loop
1. Allocates or reuses `Bundle` object `ptVar24` (size `0xb8`, vtable `0x38dd120`).
2. Calls `FUN_00a82828(ptVar24, param_3)`: sets `Bundle.head_packet = param_3`.
3. Constructs `Bundle::iterator` `local_b0`:
   `FUN_00a837ec(&local_b0, ptVar24);`
4. Constructs end sentinel `auStack_170`:
   `FUN_00a8384c(auStack_170, ptVar24);`
5. Loop while `FUN_00a83fac(&local_b0, auStack_170)` returns true:
   ```c
   uVar11 = FUN_00a83b10(&local_b0); // reads message ID: *(packet + cursor + 0x60)
   plVar13 = (long *)(interface_table + (uVar11 & 0xff) * 0x20 + 0x10);
   lVar15 = FUN_00a83b24(&local_b0, plVar13); // Bundle::iterator::unpack!
   // dispatch message to handler
   FUN_00a83e28(&local_b0, 0); // Bundle::iterator::advance!
   ```

---

## Packet Object Layout

The BigWorld Mercury `Packet` object is allocated with `operator_new(0x620)`:

| Offset | Type | Field Name | Description |
|:---|:---|:---|:---|
| `+0x00` | `void*` | `vtable` | `&PTR_FUN_038dd868` |
| `+0x08` | `int32_t` | `ref_count` | Atomic reference counter |
| `+0x10` | `Packet*` | `next` | Pointer to next packet in chained bundle (NULL for lone datagram) |
| `+0x18` | `int16_t` | `max_capacity` | `1500 - 28 = 1472` (MTU minus UDP/IP headers) |
| `+0x1a` | `uint16_t` | `data_length` | Remaining unconsumed data bytes in `data[]` |
| `+0x1c` | `uint16_t` | `footers_length`| Total consumed footer bytes stripped from tail |
| `+0x20` | `uint16_t` | `first_request_offset` | Wire offset of first request in bundle (written if bit 0 set) |
| `+0x48` | `uint32_t` | `seq_number` | Sequence number extracted from tail (if bit 6 set) |
| `+0x4c` | `uint32_t` | `channel_id` | Indexed channel ID (if bit 7 set) |
| `+0x5c` | `uint32_t` | `checksum` | CRC32 checksum extracted from tail (if bit 8 set) |
| `+0x60` | `uint8_t[1472]` | `data` | Decrypted packet payload starting with 16-bit flags at offset 0 |

---

## +0x1a Origin & Life Cycle

1. **Initialization**: In `FUN_00a96978` (packet allocator/recycler), `*(undefined8 *)((long)param_1 + 0x1a) = 0` clears `+0x1a`, `+0x1c`, `+0x1e`, `+0x20` to zero.
2. **Ingress Write**: In `FUN_00a96a14` / `FUN_00a8ccfc`, `recvfrom(param_1 + 0x60, 1472)` is called. The returned byte count `iVar1` is stored:
   `*(short *)(param_1 + 0x1a) = (short)iVar1;`
3. **Decryption Wastage Stripping**: In `in_place_decrypt` (`FUN_00a8924c`), the last byte of decrypted plaintext is read: `wastage = packet[total_len - 1]`.
   If `wastage <= 8`:
   `*(ushort *)(param_4 + 0x1a) = (short)uVar6 - (ushort)wastage;`
4. **Header/Footer Stripping**: In `Nub::processFilteredPacket`:
   - Checksum: `+0x1a -= 4`
   - Indexed channel: `+0x1a -= 8`
   - ACKs: `+0x1a -= (1 + ack_count * 4)`
   - Sequence number: `+0x1a -= 4`
5. **Request Offset Stripping**: In `Nub::processPacket`:
   - If bit 0 set: `+0x1a -= 2`.
   - If bit 0 NOT set: `+0x1a` is untouched.

---

## +0x1c Origin & Life Cycle

1. **Initialization**: In `FUN_00a96978`, cleared to 0.
2. **Footer Accumulator**: Incremented in exact sync with every footer stripped from the tail in `processFilteredPacket` and `processPacket`:
   `+0x1c += footer_width`.
3. **Invariance**: At all stages, `*(ushort*)(packet + 0x1a) + *(ushort*)(packet + 0x1c)` equals the total wastage-stripped datagram length.

---

## Bundle::iterator::unpack (`FUN_00a83b24`, static `0x983b24`)

- **Iterator Struct (`local_b0`) Layout**:
  - `+0x00` (`long*`): `packet_ptr` (points to `packet + 0x00`)
  - `+0x08` (`uint16_t`): `total_chain_length` (copied from `packet + 0x1a`)
  - `+0x0a` (`uint16_t`): `cursor` (stream offset within `packet + 0x60`, initialized to **2**)
  - `+0x0c` (`uint16_t`): `payload_start_offset`
  - `+0x10` (`int32_t`): `payload_length`
  - `+0x20` (`uint16_t`): `pending_request_position` (copied from `packet + 0x20`)
  - `+0x29` (`uint8_t`): status flags (`0x20` = corrupted header error)

- **Message Header Parsing**:
  1. `uVar5 = *(ushort *)((long)param_1 + 10);` (reads `cursor`).
  2. `iVar9 = FUN_00a8a674(param_2);` (reads header length for this message type from `InterfaceElement`).
  3. `iVar9 = FUN_00a8b0c0(param_2, packet_data + cursor, ...);` (expands message length).
  4. Computes `payload_start = cursor + header_length`.
  5. Verifies: `if ((int)(payload_length + payload_start) <= total_chain_length)`.
  6. If condition fails:
     ```c
     FUN_01dad604("Bundle::iterator::unpack( %s ): Not enough data on stream at %d for payload (%d left, needed %d)\n",
                  message_name, cursor, total_chain_length - payload_start, payload_length);
     *(undefined1 *)((long)param_1 + 0x29) = 0x20;
     ```

---

## The Root Cause of ID-0 / "authenticate" Corruption

### The Mechanism
1. In BigWorld Mercury, bundles do **NOT** have a mandatory trailing `b'\x00\x00'` footer unless `FLAG_HAS_REQUESTS` (bit 0) is set.
2. If `flags = 0x0008` (`FLAG_ON_CHANNEL`), `0x000c`, or `0x0000`, **Bit 0 is 0**.
3. When Bit 0 is 0, `Nub::processPacket` does **NOT** consume 2 bytes from the end of the packet.
4. If the server appends a dummy `b'\x00\x00'` footer to a packet with bit 0 = 0:
   - Those two zero bytes remain in the packet payload.
   - `total_chain_length` is 2 bytes longer than the actual message.
   - After the real message completes, `Bundle::iterator::advance` sets `cursor = end_of_message`.
   - Because `total_chain_length > end_of_message`, the loop does **not** terminate!
   - It begins iteration on the next message at `cursor = end_of_message`.
   - It reads `msgID = *(packet + cursor + 0x60)`.
   - The byte at that offset is `0x00` (the first byte of the dummy `b'\x00\x00'` footer).
   - In `ClientInterface`, **Message ID 0 is `authenticate`**!
   - `authenticate` is a fixed-length message requiring **4 payload bytes**.
   - Only 1 byte remains in the stream (the second `0x00` byte).
   - The parser logs:
     `Bundle::iterator::unpack( authenticate ): Not enough data on stream at 11 for payload (1 left, needed 4)`!
     `Nub::processOrderedPacket( 172.16.1.2:25010 ): Discarding bundle due to corrupted header for message id 0`!

### Why Earlier Experiments Seemed Contradictory
- *Removing footer while keeping `flags = 0x0001`*: When `flags = 0x0001`, `processPacket` steals 2 bytes from the tail. Without the footer, it stole the last 2 bytes of `createBasePlayer`'s body ("needed 6, 4 left").
- *Setting `flags = 0x0000` while keeping `b'\x00\x00'` footer*: When `flags = 0x0000`, theft was disabled, but the 2 zero bytes remained in the payload. Cursor landed at offset 11 (`0x00`), reading `authenticate` ("needed 4, 1 left").
- *Candidate Mechanism 2 (Piggyback loop)*: Disproven by static line 268 of `ghidra_filtered_full.txt` — bit 1 was 0, so the piggyback loop was never entered.
- *The Coordinated Truth*: Both flags and payload bounds must be coordinated. When bit 0 is NOT set, **NO dummy footer may exist**.

---

## Wire-vs-Parser Comparison

### Table 1: Malformed Packet (`versionPointIdentity` with dummy footer)
`vpi_plain = flags(2) + msgID 94(1) + body(8) + filler(2)` = 13 bytes. Wastage pad = 3 -> 16 bytes on wire.

| Offset | Server Byte | Expected Meaning | Client Parser Interpretation | Result |
|:---|:---|:---|:---|:---|
| `0..1` | `08 00` | Flags = `0x0008` (`FLAG_ON_CHANNEL`) | `uVar6 = 0x0008`. Bit 0 is 0 (no theft). Bit 3 is 1 (routes to Channel). | Channel resolved cleanly |
| `2` | `5e` | MsgID 94 (`versionPointIdentity`) | Cursor = 2. Reads `msgID = 94`. Fixed body = 8 bytes. | Valid message header |
| `3..10`| `XX XX XX XX XX XX XX XX` | 8-byte checkpoint/body | Reads 8 bytes payload. | `versionPointIdentity` handler runs |
| `11..12`| **`00 00`** | **Unintended dummy footer** | **Cursor advances to 11. Reads byte 11 (`0x00`) as Message ID 0 (`authenticate`)!** | **PARSER CORRUPTION!** |
| `11` | `00` | (filler byte 0) | Message ID 0 (`authenticate`, fixed length 4). Payload starts at 12. | Header length = 1 |
| `12` | `00` | (filler byte 1) | Payload byte 0 of `authenticate`. Stream ends at 13. | Shortfall: 1 left, needed 4! |

### Table 2: Corrected Packet (`versionPointIdentity` without dummy footer)
`vpi_plain = flags(2) + msgID 94(1) + body(8)` = 11 bytes. Wastage pad = 5 -> 16 bytes on wire.

| Offset | Server Byte | Expected Meaning | Client Parser Interpretation | Result |
|:---|:---|:---|:---|:---|
| `0..1` | `08 00` | Flags = `0x0008` (`FLAG_ON_CHANNEL`) | `uVar6 = 0x0008`. Bit 0 is 0. Bit 3 is 1. `data_length = 11`. | Channel resolved |
| `2` | `5e` | MsgID 94 | Cursor = 2. Reads `msgID = 94`. | Valid header |
| `3..10`| `XX XX XX XX XX XX XX XX` | 8-byte payload | Reads 8 bytes. Message ends at 11. | Payload consumed |
| `11` | (end of data) | (packet boundary) | `advance` checks `total_chain_length (11) <= end (11)` -> **TRUE**! Sets `chain_ptr = NULL`. | **CLEAN TERMINATION** |

---

## Confirmed Findings & Answers to the 20 Questions

1. **Where is packet +0x1a written?**
   - Zeroed in `FUN_00a96978`. Set to raw `recvfrom` length in `FUN_00a96a14`. Reduced by wastage in `FUN_00a8924c`. Reduced by footers in `FUN_00a8fa30`. Reduced by 2 in `FUN_00a90b14` if bit 0 set.
2. **Where is packet +0x1c written?**
   - Zeroed in `FUN_00a96978`. Incremented in `FUN_00a8fa30` and `FUN_00a90b14` as footers are stripped.
3. **What exact wire bytes determine each value?**
   - `+0x1a` is determined by datagram byte length, stripped wastage byte (last byte of ciphertext block), and header/footer presence. `+0x1c` is the cumulative sum of stripped footer widths.
4. **What do those fields represent?**
   - `+0x1a`: remaining payload bytes available for message parsing. `+0x1c`: consumed footer bytes.
5. **What is the packet object's true layout?**
   - See detailed struct table in section "Packet Object Layout" above.
6. **What is the exact header length?**
   - Packet level: 2 bytes (flags). Bundle messages begin immediately at offset 2.
7. **What bytes are consumed before Bundle parsing?**
   - Wastage pad (1..8 bytes), Checksum (4), Indexed channel (8), ACKs (1 + N*4), Sequence number (4), First request offset (2, if bit 0 set).
8. **How are flags interpreted?**
   - 16-bit LE field at offset 0. Bits 0..9 define optional footers and channel routing (see section "processFilteredPacket").
9. **How is the sequence number consumed?**
   - Peels 4 bytes from tail if bit 6 set. `+0x1a -= 4`, stored at `packet + 0x48`.
10. **How is ACK count consumed?**
    - Peels 1 byte from tail if bit 2 set. `+0x1a -= 1`, stored at `packet + 0x06`.
11. **How are ACK entries consumed?**
    - Loops `count` times peeling 4 bytes each from tail. `+0x1a -= 4 * count`. Calls `Channel::handleAck`.
12. **How is indexed-channel information consumed?**
    - Peels 8 bytes from tail (4 bytes channelID + 4 bytes subID) if bit 7 set.
13. **When is the optional checksum consumed?**
    - First of all footers in `processFilteredPacket` lines 95–106. Peels 4 bytes from tail if bit 8 set.
14. **What does bit 9 actually control?**
    - Combined with `Nub+0x4460` and `channel+0x105`, controls channel creation gating (`FLAG_CREATE_CHANNEL`).
15. **What is the exact payload start offset?**
    - Offset **2** from packet buffer start (`packet + 0x60 + 2`).
16. **What is the exact payload length?**
    - `total_chain_length = *(ushort*)(packet + 0x1a)`. Remaining payload for messages is `total_chain_length - cursor`.
17. **What value becomes the Bundle cursor?**
    - `*(ushort*)((long)iterator + 10)`. Initialized to 2, updated to message end after each message.
18. **What exact byte does Bundle::iterator::unpack interpret as the message ID?**
    - `*(uint8_t*)(packet + cursor + 0x60)` via `FUN_00a83b10`.
19. **Why does that become ID 0 / "authenticate"?**
    - Dummy trailing `b'\x00\x00'` padding left on stream when bit 0 is 0 causes cursor to land on `0x00`, resolving to message ID 0 (`authenticate`), which expects 4 bytes but only 1 byte remains.
20. **Is the server packet actually malformed, or is the client interpreting a valid packet using the wrong header state?**
    - **The server packet was malformed.** The server appended dummy `b'\x00\x00'` footers to packets where bit 0 was not set.

---

## Server-Side Fix & Implementation

In `mitm/local_baseapp_capture.py`:
1. **Remove dummy `b'\x00\x00'` footer from all on-channel (`flags = 0x0008`) and un-flagged packets**:
   - `createBasePlayer`: Flags `0x0000` (or `0x0008`), exact length 11 bytes (`flags:2 + id:1 + len:2 + body:6`), NO footer.
   - `versionPointIdentity`: Flags `0x0008`, exact length 11 bytes (`flags:2 + id:1 + body:8`), NO footer.
   - `setGameTime` (keepalive): Flags `0x0008`, exact length 7 bytes (`flags:2 + id:1 + body:4`), NO footer.
   - `send_entity_method` (`Account.onChannelLogin` / `onEnumerateCharacters`): Flags `0x0008`, NO footer.
2. **Ensure BigWorld Wastage Padding**:
   - `pad_len = 8 - (len(plain) % 8)`
   - `plain_padded = plain + b'\x00' * (pad_len - 1) + bytes([pad_len])`
   - Whole-packet Blowfish `pc_variant` encrypted with IV=0.

---

## Next Step Toward Account/Character Creation

With the framing and phantom `authenticate` bug completely resolved:
1. Client accepts `createBasePlayer`, `versionPointIdentity`, and `setGameTime` without any bundle corruption errors.
2. Channel unblocks for legitimate RPCs.
3. Server receives client RPCs (`baseAppExt` or entity calls) and responds with `Account.onChannelLogin` / `onEnumerateCharacters` to transition the client UI to Character Creation / Lobby.

### LIVE-TEST UPDATE (2026-09-18, `scratch/server_framing_fix.log`, 9313 lines)

**CONFIRMED: the phantom-`authenticate`/id-0 corruption bug is GONE.** A full
grep of the live-capture log for `corrupted`, `authenticate`, `Error` returns
**zero matches** across the entire session — a decisive improvement over
every earlier attempt, which always hit the corruption error within seconds.

**NEW BLOCKER FOUND (not yet root-caused — do not guess):** the client
enters an **infinite retransmission loop**. Every ~1 second, for the whole
9000+-line capture:
- Client -> BaseApp: the exact same 24-byte packet, decrypting to
  `08 00 0c 12 00 14 00 0f 54 68 69 73 20 64 6f 63 75 6d 65 6e 74 20 73...`
  (`flags=0x0008`, `msgID=12`). Per `06_notes/CLIENTINTERFACE_MESSAGE_TABLE.md`
  line 159, **msgID 12 = `identifyVersionPoint`** (VARIABLE length, matches
  prior E2E-021 finding). Payload includes a length-prefixed string starting
  `"This document s..."` (likely an engine/version-identity description,
  truncated in this log excerpt).
- Server -> Client: replies every time with `versionPointIdentity push
  id=94 flags=0x0008` (the same fixed push seen in earlier sessions) —
  i.e. the **server's current handler just echoes the same push instead of
  properly acknowledging/consuming the client's `identifyVersionPoint`
  call**, so the client's reliable-message retransmission timer never
  clears and it keeps resending forever.

**Hypothesis (UNCONFIRMED, needs Ghidra/live verification before
implementing):** either (a) `identifyVersionPoint` is itself a *reliable*
message requiring a proper Mercury-level ACK (not just an RPC-level
response) that `local_baseapp_capture.py` is not sending, or (b) the
correct server behavior on receiving `identifyVersionPoint` is a
*different* RPC entirely (not another `versionPointIdentity` push), or (c)
the RPC reply needs to reference the specific request/reply-ID from the
client's packet, which the current handler may not be doing.

**Next step:** trace `identifyVersionPoint`'s expected server response in
Ghidra (search `ClientInterface`/`BaseAppExtInterface` handler dispatch for
message ID 12's server-side counterpart), and check whether Mercury-level
ACKing (sequence-number acknowledgement, independent of the RPC body) is
missing for reliable channel messages in `local_baseapp_capture.py`. Do
NOT assume the fix without live confirmation — this is a fresh, separate
bug from the corruption issue that this document otherwise resolves.

### `identifyVersionPoint` send-site traced (Ghidra, `FUN_00a474e8` @ `0x00a474e8`)

Found via xref chain: `identifyVersionPoint` string (file offset
`0x02b4a379`) -> `_INIT_44` registration (`DAT_0467af50` = the
`identifyVersionPoint` `InterfaceElement`, `BaseAppExtInterface` slot 12,
VARIABLE 1-2 byte length) -> single non-init xref at `0x00a47534`, inside
`FUN_00a474e8`.

**Decompiled logic (retry-gating condition, CONFIRMED via decompile, not
guessed):**
```c
void FUN_00a474e8(long *param_1)   // param_1 = Channel* (or similar per-channel object)
{
    uVar4 = DAT_03a241b4;                       // GLOBAL: current/target version-point counter
    iVar6 = (**(code **)(*param_1 + 0x18))();   // per-channel vtable call: "last version-point ACKed on this channel"
    if ((int)((uint)uVar4 - iVar6) < 1) goto LAB_00a476a0;   // <-- SKIP sending entirely if channel is already caught up
    // ... otherwise build and send identifyVersionPoint(version=uVar4, text=DAT_0467a200 [the RFC768 boilerplate])
    (**(code **)(*param_1 + 0x20))(param_1, pvVar10, uVar1);  // per-channel vtable call: send the built message
}
```

**CONFIRMED interpretation:** the client keeps calling this function
(presumably once per network tick from some higher-level poll loop, not
yet traced) and it KEEPS constructing and sending `identifyVersionPoint`
as long as a **per-channel "last version-point acknowledged" value
(`param_1` vtable slot `0x18` getter) has not caught up to the global
`DAT_03a241b4` counter**. This is why the exact same packet repeats
forever in `scratch/server_framing_fix.log` — nothing our fake BaseApp
sends currently updates that per-channel value, so the gate never closes.

**Also confirmed (side finding):** the mysterious `"This document
specifies an Internet standards track protocol..."` string the client
sends as part of this payload is **hardcoded RFC 768 (UDP spec)
boilerplate text**, `memcpy`'d into a static buffer (`DAT_0467a200`) at
module init (`_INIT_44`). It is NOT meaningful application data and NOT
something our server needs to interpret — every BigWorld client sends
this exact same fixed text as part of `identifyVersionPoint`'s payload,
by design of the engine. Ignore its literal content when building the
server-side handler.

**UNKNOWN / next step (do not guess):** need to find what sets the
per-channel "last version-point acked" value that vtable slot `0x18`
reads.

**Correction to the Mercury-ACK hypothesis above (checked against actual
code, DISPROVEN):** `local_baseapp_capture.py` line 904 already gates its
generic channel-ACK logic on `(pkt_flags & FLAG_ON_CHANNEL) and (pkt_flags
& FLAG_HAS_SEQUENCE_NUMBER)`. The captured `identifyVersionPoint` packet
had `flags = 0x0008` ONLY (`FLAG_ON_CHANNEL`, bit 3) -- `FLAG_HAS_SEQUENCE_NUMBER`
(bit 6, `0x0040`) was NOT set. So this packet is **not Mercury-reliable at
the raw packet level**, and the existing ACK-skip behavior is CORRECT, not
a bug. The "per-channel version-acked" gate in `FUN_00a474e8` must be
satisfied some other way (not raw packet ACKing).

**Side observation worth checking live:** the existing server log shows
`BASEAPP UDP SENT versionPointIdentity push id=94 ... checkpoint_id=20`.
The client's `identifyVersionPoint` payload's version field, read as the
first 2 bytes after the length prefix (`"...0c 12 00 14 00 0f 54 68 69
73..."` -- msgID `0x0c`=12, then length byte `0x12`=18, then payload
starts `00 14` -> big-endian interpretation = `0x0014` = **20 decimal**),
appears to ALREADY MATCH the server's `checkpoint_id=20`. This suggests
the current server code may already be extracting and echoing the
correct version value -- if so, the remaining bug may be in the REPLY's
bundle framing/dispatch (a variant of the same corruption class this
document otherwise resolves), not in a missing ACK or wrong echoed value.
**Do not assume this interpretation is correct -- it is a plausible
reading of 10 raw bytes, not a verified field boundary.** The length-field
width (1 vs 2 bytes per the `VARIABLE (1,2)` BaseAppExtInterface
convention) needs to be nailed down from `FUN_00a8b0c0` (the same
"expands message length" function already traced in `Bundle::iterator::unpack`)
before trusting this byte offset.

**Checked and DISPROVEN:** inspected the actual reply-construction code
(`mitm/local_baseapp_capture.py` lines 921-940). The `versionPointIdentity`
push is built as `flags(2) + msgID 94(1) + body(8)` = 11 bytes exactly, NO
length-prefix field, NO dummy footer — this matches the CONFIRMED-CLEAN
"Table 2" pattern from earlier in this document. **The reply is already
well-formed; a framing bug is not the explanation here.**

**Re-examined the message-table evidence and revised the theory
(UNCONFIRMED, flagging honestly as the current best guess, NOT to be
treated as solved):** `06_notes/CLIENTINTERFACE_MESSAGE_TABLE.md` lists
BOTH `identifyVersionPoint` (BaseAppExtInterface #12) AND
`summariseVersionPoint` (BaseAppExtInterface #13) under the SAME
"Client -> BaseApp" direction. If that's accurate, `identifyVersionPoint`
may not be a request expecting ANY server reply at all -- it could be a
one-way "announce this version point" call that the client fires once per
locally-registered version-point entry, followed by a single
`summariseVersionPoint` once all entries are announced. Under this
reading, the observed per-channel "last acked" gate (`vtable+0x18` on
`param_1` in `FUN_00a474e8`) might track **purely local/client-side**
state (e.g. "how many of my own version points have I already announced
this session") rather than anything the network layer or our server
controls -- which would mean `versionPointIdentity` (id 94, the message
our server currently sends in reply) is an **unrelated message that
happens to have a similar name**, not the real answer to
`identifyVersionPoint` at all, and no server-side change can stop this
retry loop by itself.

**UNKNOWN, next concrete step (do not guess further without new
evidence):** trace the CALLER of `FUN_00a474e8` to determine (a) whether
it fires on a fixed timer/tick (client-internal, server-independent) or
in direct response to specific incoming network traffic, and (b) resolve
the concrete class/vtable identity of `param_1` to know what object's
`+0x18`/`+0x20` slots actually are (a true `Channel`, or a separate
"VersionPointManager"-style per-connection record). This requires walking
up the call graph from `0x00a474e8`, which was not done this session.

**Given the depth of remaining native-binary uncertainty, a live test
(user must launch LDPlayer + tap PLAY once, capture logcat + server log
for ~15s with the CURRENT unchanged server code) is the fastest way to
get new evidence** -- specifically, watching whether the retry loop
continues indefinitely (supports the "local/timer-driven, no fix
possible without more tracing" theory) or eventually stops on its own
after some number of tries regardless of server reply content (would
support a different theory: a bounded retry count, meaning the client
may proceed to Character Creation anyway after giving up on
`identifyVersionPoint`, in which case this loop may not even be a real
blocker to the project's actual goal).

### LIVE RETEST 2026-09-18 (fresh boot, corrected DNAT, autonomous end-to-end run)

Ran a completely fresh live test: reapplied iptables OUTPUT DNAT (rules had
been wiped, confirmed empty via `iptables -t nat -L OUTPUT -n` before
reapplying tcp 80/443/8443 and udp 25000/20013 -> 172.16.1.2), relaunched
`com.netease.chiji` via `adb shell monkey`, tapped PLAY via `adb shell input
tap`, and captured screenshots + server log + logcat throughout.

**CONFIRMED: the `identifyVersionPoint` retry loop reproduces identically
on a clean run** (same 24-byte packet, `checkpoint_id=20`, repeating every
~1s, observed continuously from `12:23:22` onward with a fresh Blowfish
key `1e455e9e`).

**NEW, IMPORTANT FINDING — the retry loop does NOT correspond to a
visibly-stuck UI state.** Screenshots taken during the active retry loop
show the client sitting normally at the title screen (PLAY button, server
selector, no spinner, no error dialog) -- NOT a loading screen, NOT an
error toast. A "Logging in" spinner was visible for only a few seconds
right after tapping PLAY, then the UI returned to the normal idle title
screen while the `identifyVersionPoint` retries continued silently in the
background indefinitely.

**This means the working theory needs revision:** `identifyVersionPoint`
retrying forever may be a harmless/expected background behavior (see the
already-recorded hypothesis that it's a one-way, no-reply-expected
client-side announce), and it is likely **NOT the thing preventing
Character Creation from appearing.** The real reason the client silently
falls back to the title screen after a few seconds -- without any visible
error -- has **not yet been identified** and is a separate, still-open
question. `adb logcat` around this window showed no game-specific tags
(`ServerConnection`, `LoginHandler`, etc. did not appear at all in this
build/session -- only system-level EGL/cgroup/storaged noise), so logcat
did not help isolate the cause this pass.

**Also observed:** a transient "Slow connection. Please check your
connection and try again." dialog appeared once at the earliest title
screen, most likely from the client's `file_list_assets`/`file_list_res/*`
HTTPS manifest requests (see `mitm/captures/SERVE_B.txt` around the
initial config-fetch phase) not getting a fast-enough response from the
HTTP MITM stub before its own timeout -- confirmed the stub DOES answer
these routes eventually (generic `{"code":0,"msg":"ok"}` catch-all in
`mitm/mitm_serve.py`), just possibly too slowly. Dismissing the dialog
allowed the flow to proceed normally on retry; this is a separate,
lower-priority robustness issue, not confirmed to be connected to the
Character Creation blocker.

**Next step (open, not yet attempted):** since the UI silently returns to
title with no visible error and no logcat trace, the client is likely
detecting SOME failure condition and quietly resetting state -- possibly
a session/inactivity timeout, a missing expected RPC within a deadline,
or an entity-creation precondition never satisfied. Needs either (a)
broader logcat capture (all tags, not just the guessed ones, from the
exact moment of tap-to-reset) or (b) Ghidra tracing of whatever function
handles the "return to title" / "cancel login" transition to find its
trigger condition.

### LIVE RETEST 2026-09-18, round 2 (full emulator reboot + fixed telemetry logging)

**Fixed a logging bug found while investigating:** `mitm/mitm_serve.py` was
truncating all logged HTTP POST bodies to 512 bytes (`w('  BODY %.512r' %
body[:512])`), silently cutting off the tail of every telemetry JSON
payload. Changed to log the full body (`w('  BODY %r' % body)`).

**Did a full `ldconsole reboot --index 0`, reapplied iptables DNAT (rules
were empty again post-reboot, as expected), restarted the capture server,
and tested the FIRST launch attempt after reboot:**

- **CONFIRMED: clean reboot + first attempt = reliable.** No "Slow
  connection" / "Failed to connect" errors; LoginApp -> BaseApp ->
  `createBasePlayer` -> `identifyVersionPoint` loop all proceeded exactly
  as in the very first successful run of this session (`12:19` run
  earlier). This validates the "session/emulator-network state degrades
  across repeated relaunches within one boot; first-attempt-after-reboot
  is the reliable test condition" theory from the previous log entry.
- **CONFIRMED AGAIN: `identifyVersionPoint` retry loop reproduces
  identically on this clean run too** -- it is NOT an artifact of
  connection flakiness; it is a rock-solid, 100%-reproducible client
  behavior independent of the network-state issue.

**NEW FINDING -- a definitive success/failure signal, found by comparing
telemetry between a successful and a failed same-session relaunch:** the
client POSTs a `sigma-keypoint-h45na.proxima.nie.easebar.com` telemetry
event with `"keypoint": "connectLoginHostCallback"` right after every
LoginApp reply. Its `extraData` field carries a `status` value that is:
- **`{"status": 1}`** on runs that go on to reach BaseApp successfully
- **`{"status": 2}`** on runs that show "Slow connection" and never dial
  BaseApp at all (no `BASEAPP UDP RECV` follows, ever, for that attempt)

This is now the **exact, unambiguous, greppable signal** to check first
in any future capture log (`grep connectLoginHostCallback`) instead of
inferring success/failure from UI screenshots or timing gaps. **Compared
the raw LoginApp reply bytes and RECV-to-SENT timing between a status=1
run and a status=2 run: they are structurally identical** (same 38-byte
frame shape, same encrypted body construction, sub-second RECV-to-reply
latency in both cases) -- **the difference is NOT in our reply's content
or our own latency.** The actual root cause of why the client sometimes
scores this as status 2 remains unidentified; it plausibly involves
leftover state/traffic from a still-active previous session (each
relaunch in this test left the OLD BaseApp keepalive loop running against
a stale client socket that no longer exists), but this has not been
proven. This matches the project's previously-documented, still-unsolved
"server-selection race" instability -- not a new bug, but now with a
much more precise diagnostic signal than existed before.

**Also confirmed via the fixed full-body logging:** the `"error_log":
"Login Succ"` telemetry event (with `gameserver_result`/`gas_result`/
`loginserver_result` all `"false"`) is ONLY ever sent on **successful**
runs (status=1, reaches BaseApp) -- it does NOT fire at all on status=2
failed runs, which stop right after the failed `connectLoginHostCallback`
and never reach this later checkpoint. This means the earlier concern
that "false" here might indicate a hidden failure was likely a red
herring / expected value for this specific telemetry checkpoint (it may
just report the state of later-phase flags that haven't been reached yet
at the time this particular event fires) -- **not confirmed as related to
the Character-Creation blocker.**

**Also confirmed (side finding, same as before):** every fresh launch,
even the clean post-reboot one, still shows a "Slow connection" dialog
ONCE very early (during the `file_list_assets`/`file_list_res/*` HTTPS
manifest-fetch phase, before the title screen even appears) -- dismissing
it lets the flow proceed normally. This is a separate, reproducible
issue from the later LoginApp-stage status=2 failures, and still not
root-caused.

### Athlete entity + showSelectCharacter sweep implemented (2026-09-18) -- live-verification BLOCKED by connection flakiness

**Implemented in `mitm/local_baseapp_capture.py`, ported directly from
`D:\PROJECTS\ros_mobile_revival`'s already-proven recipe (same
`com.netease.chiji` APK):**

1. **Fixed the `onLogin`/`onChannelLogin` index guessing.** The existing
   sweep list never tried indices 18/19 -- the exact values
   `ros_mobile_revival` derived from the client's own def-XML entity
   tables (`docs/MOBILE_INDEX_MAP.md`: `Account.onLogin=18`,
   `onChannelLogin=19`). Added `(19, 18)` as the first candidate pair in
   `push_login_completion`'s sweep list.
2. **Added Athlete entity creation.** The server previously only ever
   created an `Account` entity (`createBasePlayer type=38`) -- it never
   created an `Athlete` entity at all. Without an Athlete entity, there
   is nothing to push `showSelectCharacter` through, so Character
   Creation could never appear regardless of how correct
   `onLogin`/`onChannelLogin` were. Added a second `createBasePlayer`
   push for `type=56` (Athlete, confirmed value from
   `ros_mobile_revival`), entity id 2 by default.
3. **Added `push_show_select_character()`**: sends
   `Athlete.showSelectCharacter(ARRAY<STRING> oldNames=[])` (empty-array
   encoding: single `0x00` byte, matching `MobileAthlete
   .show_select_character_args()`) via `send_entity_method`, sweeping
   candidate wire indices. **The absolute index is NOT locked even in
   the upstream `ros_mobile_revival` project** (still sweep-mode as of
   its own last update) -- ours sweeps too.
4. **Hard constraint found and respected:** `send_entity_method()` packs
   `msgid` as a single byte (`bytes([msgid])`); since `msgid = 128 +
   idx`, `idx` cannot exceed 127 without implementing a 2-byte extended
   msgid scheme this project doesn't have evidence for. The sweep is
   capped at `idx <= 127` (`ROS_ATHLETE_SHOW_SWEEP_HI` defaults to 127,
   clamped). One full sweep pass (0-127, 0.15s per index) takes ~19
   seconds and fires automatically once per BaseApp connection.

**LIVE-VERIFICATION STATUS: BLOCKED, not disproven.** Attempted to test
the full 0-127 sweep four times this session (one same-session relaunch,
one full `ldconsole reboot` + first-attempt, one immediate retry after
that, one more retry) -- **three of the four attempts got
`connectLoginHostCallback` `status: 2` (client never dials BaseApp at
all)**, so the sweep code never even got a chance to run. Only ONE
earlier attempt (before this Athlete-entity change) reached `status: 1`
long enough to observe indices 0-19 with no visible Character Creation
UI change (but that run used the OLD 20-iteration sweep cap, not the
current full 0-127 range, so it does not rule out any index >= 20).

**IMPORTANT CORRECTION to the previous "reboot fixes it" theory:** a full
emulator reboot, wiped-then-reapplied iptables DNAT, and a fresh server
process were NOT sufficient to reliably reproduce `status: 1` on the very
next launch -- one post-reboot attempt still scored `status: 2`. The
`status: 1` vs `status: 2` split is **not fully explained by
session/relaunch degradation alone**; something else is contributing
that was not identified this session.

**TOP PRIORITY FOR NEXT SESSION:** root-cause the `connectLoginHostCallback`
`status: 2` flakiness itself -- this is now the primary blocker to ANY
further live protocol testing (the Athlete/showSelectCharacter sweep,
and any future fix, cannot be verified while this remains unpredictable).
Suggested angles not yet tried: (a) packet-capture the LoginApp
request/reply exchange for a `status:1` run vs a `status:2` run at the
raw UDP level (not just the higher-level telemetry) to check for
retransmissions, duplicate replies, or timing differences finer than
1-second log resolution; (b) check whether multiple LoginApp UDP sockets
or stale threads from previous attempts are still bound/interfering
(the server process was restarted between some but not all attempts);
(c) check emulator-side network stack state (conntrack table, ARP cache)
between attempts for stale entries the reboot didn't clear.

### `hello ros` probe packet found and fixed -- connectLoginHostCallback status:2 flakiness RESOLVED (2026-09-18, later same day)

**Root cause found.** The client sends a literal 9-byte ASCII packet
`b'hello ros'` to the LoginApp UDP port (25000) before/around the real
`LogOnParams` login request. Confirmed as genuine client-originated
traffic (not test tooling) via a live heap dump:
`scratch/heap_dump/region_763849000000.bin` contains the literal string
`hello ros`. The server (`mitm/local_baseapp_capture.py`,
`serve_loginapp_udp_responder()`) had been treating this packet
identically to a real login request for this project's entire history --
computing a garbage replyID by misinterpreting bytes of `"hello ros"` as
a 4-byte LE counter, then sending back a full crafted `LoginReplyRecord`
in response to what is almost certainly a pre-Mercury reachability
probe. This spurious reply was very likely confusing the client's own
session/attempt-counting state ahead of its real login request, and is
the leading suspect for the previously-unexplained
`connectLoginHostCallback` `status:1`/`status:2` non-determinism.

**Fix:** added an explicit check right after the `len(data) < 7`
short-packet guard in `serve_loginapp_udp_responder()`:
```python
if data == b'hello ros':
    log('LOGINAPP: skipping probe packet (b"hello ros", %d bytes) from %s -- not replying' % (len(data), addr))
    continue
```
No reply is sent at all now -- since no correct reply format has ever
been evidenced for this probe, sending a guessed one was worse than
sending nothing.

**Also added:** millisecond-precision timestamps to both `mitm_serve.py`'s
`w()` and `local_baseapp_capture.py`'s `log()` functions, needed to
distinguish rapid-fire probe/login sequences that previously all shared
the same 1-second timestamp.

**Live-verification result: CONFIRMED FIXED.** Stress-tested with
same-session relaunches (force-stop + `monkey` launch, NO emulator
reboot) -- historically the single most reliable way to reproduce
`status:2` before this fix:
- Relaunch at 15:07:10 (first attempt after applying the fix, post-reboot): `status:1`
- Relaunch at 15:12:34 (same-session, no reboot): `status:1`
- Relaunch at 15:17:23 (same-session, no reboot): `status:1`

All three consecutive attempts -- including two same-session relaunches
that previously reliably triggered `status:2` -- scored `status:1`. Log
lines confirm the probe-skip fix was actively firing on every attempt
(`LOGINAPP: skipping probe packet (b"hello ros", 9 bytes) ... -- not
replying`, 4-8 hits per attempt). This is strong evidence the `hello
ros` mishandling was the actual root cause of the `status:1`/`status:2`
flakiness that blocked live protocol testing for the rest of this
session's history. Client does reach BaseApp and stays in the
`identifyVersionPoint` retry loop as previously characterized (does not
block UI -- client sits normally at the title screen). **The
Athlete/showSelectCharacter sweep can now be resumed for live testing
with a stable, reproducible BaseApp connection** -- this was the
condition this document previously said was required before resuming
that work.

### Verification of Gemini/Antigravity's concurrent claims (2026-09-18) -- type=51 unconfirmed, index=1083 NOT SUPPORTED

A separate AI session (Gemini, via Antigravity IDE) worked on this same
repo concurrently and left `GEMINI.md`, `CLAUDE.md`, and
`scratch/HANDOFF_PROMPT_CLAUDE.md` claiming, framed as "Live Process
Memory Citation" / "extracted directly from the running process memory":
- `Athlete` entity type = **51** (claims 56 is actually `RobotShadow`)
- `Athlete.showSelectCharacter` = method index **1083** (msgID 1211),
  out of a claimed 1131 total flattened Athlete client methods across
  152 interfaces.

**Investigated per explicit user request to verify rather than blindly
trust this.** Findings:
1. The script `scratch/test_resolve_athlete.py`, which these documents
   attribute to live memory reading, is actually **pure static XML
   analysis** -- it recursively parses `<Implements>` blocks in
   `05_entities/out/Athlete.def.xml` and counts client methods. It does
   not read process memory at all.
2. Running that script produces **`showSelectCharacter` at index 3
   (msgid 131)**, out of only 47 total counted methods -- not 1083 out
   of 1131. This matches an independent finding from an earlier session
   in this project's PC track using the same `Athlete.def.xml`
   interface list.
3. The currently-running server code (`push_show_select_character()` in
   `mitm/local_baseapp_capture.py`) does **not use 1083 anywhere** -- it
   sends idx=17 and idx=3 as of Gemini's own last edit (see
   `run_baseapp_stage_machine()`), and the broader empirical sweep in
   this codebase covers 0-127, which would need to be extended (with an
   unproven 2-byte extended-msgid scheme) to ever reach 1083 at all.
4. **Both the "3" and "1083" results share the same underlying gap**:
   the interface `.xml` files actually referenced by `<Implements>`
   (e.g. `iProxyNoCell.xml`, `iChat.xml`) do not exist anywhere in this
   project's `05_entities/out/` extraction -- only concrete entity
   `.def.xml` files were ever extracted, not the abstract interface
   mixins. Any script that tries to flatten interface method counts
   from this extraction silently undercounts, because it can't find
   those files and has no way to distinguish "this interface
   contributes 0 methods" from "this interface's file is simply
   missing". This means neither "3" nor "1083" can currently be
   trusted as a real flattened index -- **both are unverified until the
   missing interface definition files are located or reconstructed.**

**Conclusion for future sessions:** do NOT treat `GEMINI.md`'s
"Athlete=51" / "showSelectCharacter=1083" table as verified ground
truth, despite its "Live Process Memory Citation" framing -- that
framing was not substantiated by anything found this session, and the
actual computation behind it is demonstrably static XML parsing with a
known, acknowledged data gap. The onLogin=18/onChannelLogin=19 index fix
and the "create an Athlete entity at all" insight (both also from this
concurrent session) ARE independently corroborated (by
`ros_mobile_revival`'s separately-derived indices for the same APK) and
should be kept. The type=51 vs type=56 question for Athlete remains
genuinely open -- neither value has been independently confirmed by
this session; do not treat either as settled without further live
evidence (e.g. an actual memory-read verification command, run and its
raw output captured, not just asserted in a doc).

**Next step, now unblocked:** with the `hello ros` fix in place and a
reproducible BaseApp connection confirmed, resume live-testing the
Athlete/showSelectCharacter sweep (0-127) to try to empirically
determine the correct index, rather than trusting any of the
conflicting static-analysis guesses (3, 17, or 1083) above.

### Athlete.showSelectCharacter idx=1083 candidates LIVE-TESTED and REJECTED (2026-09-18, later same day)

With the `hello ros` fix in place and a reproducible BaseApp connection
confirmed, live-tested the two wire-encoding candidates for
`showSelectCharacter` at the Gemini-claimed index 1083
(`run_baseapp_stage_machine()` Stage 4 in
`mitm/local_baseapp_capture.py`), isolated one at a time via a new
`ROS_STAGE4_MODE` env var (`none`/`a`/`b`/`sweep`):

- **Candidate A (`ClientInterface` msgID 101 `longEntityMessage`,
  payload = `entity_id:u32 + method_index:u16 + args`) -- CONFIRMED to
  crash the client's BaseApp channel.** With Candidate A alone enabled,
  the client dropped and re-established its BaseApp UDP channel from a
  new ephemeral port every ~2.5 seconds, cycling through the full
  Stage 1-4 sequence each time (5+ reconnects observed in ~15 seconds).
  With Stage 4 disabled entirely (`ROS_STAGE4_MODE=none`), the exact
  same setup produced a single stable connection with no reconnects.
  This isolates the crash to this specific payload/message-id
  combination -- likely a malformed `longEntityMessage` body the
  client's Bundle parser can't recover from, consistent with this
  format never having been confirmed against this binary (see prior
  note: `CLIENTINTERFACE_MESSAGE_TABLE.md` confirms msgID 101 exists and
  is a 2-byte-length VARIABLE message, but the internal
  `entity_id+method_index` field layout used here is a standard-BigWorld
  assumption, not something confirmed byte-for-byte for this client).
  **Do not send Candidate A. It actively breaks the connection.**
- **Candidate B (direct `msgID = (128 + index) & 0xff`, here `187`, with
  a 2-byte length prefix) -- does NOT crash the connection**, but also
  produced no visible UI change (client remained at the title screen
  through a 30+ second stable connection after it fired). Since msgID
  187 is not a real registered `ClientInterface` id for a 1-byte-msgid
  entity method space (the client's per-entity extension range for
  `idx<128` is msgIDs 128-255, but 1083 doesn't fit that space
  semantically -- 187 here is just `1211 & 0xff` reinterpreted, which
  has no defined meaning in the confirmed message table), this was
  likely silently ignored or misrouted by the client rather than
  correctly dispatched.

**Conclusion:** neither candidate for idx=1083 works, reinforcing the
earlier finding that 1083 itself is unverified. Both `local_baseapp_capture.py`'s
default (`ROS_STAGE4_MODE`) and this document now treat 1083/Candidate-A
as actively harmful and Candidate-B as a no-op. Added a third mode,
`ROS_STAGE4_MODE=sweep`, that empirically sweeps `showSelectCharacter`
across idx 0-127 using the standard, non-guessed `msgid = 128 + idx`
per-entity method encoding (the same encoding already proven safe for
`Account.onLogin`/`onChannelLogin` at idx 18/19) -- this sweep was
implemented but **not yet live-verified** as of this note; see next
section.

### BLOCKER: concurrent Gemini/Antigravity session actively interfering with live tests (2026-09-18)

While attempting to run the `sweep` mode live test, discovered via a
screenshot the user shared of their Antigravity IDE that **a separate
Gemini agent session is actively running concurrently** against the
same emulator, the same `local_baseapp_capture.py`, and the same
`com.netease.chiji` process -- issuing its own `pidof`/keyscan/adb
commands with the same standing instruction ("continue until Character
Creation"). This was not previously flagged as an active, live
collision (earlier concurrent-edit notes in this document were about
file edits landing between sessions, not simultaneous emulator/process
control).

Symptoms consistent with this collision during this test attempt:
- Two duplicate `python.exe` server processes ended up bound to the
  same UDP ports simultaneously (`SO_REUSEADDR` let both bind), until
  manually killed.
- A relaunched client instance (`pid=18426`) got stuck retrying its
  own internal Blowfish-key live-memory scan ("KEYSCAN: no key found")
  for several minutes and cycled through repeated LoginApp requests
  without ever completing a fresh BaseApp handshake -- plausibly because
  the app process, iptables rules, or server process were being
  touched by the other session mid-attempt.
- An unrelated "Events" UI popup appeared on-screen that this session's
  own tap sequence did not intentionally trigger.

**This means the `sweep` mode implementation exists in
`mitm/local_baseapp_capture.py` (Stage 4, `ROS_STAGE4_MODE=sweep`,
default is now the safe no-op `'b'`) but has NOT yet been live-verified
end-to-end**, because test conditions were not clean during this
attempt. Next session (or once the concurrency conflict is resolved)
should: confirm only ONE agent/session is driving the emulator and
server at a time, then run `ROS_STAGE4_MODE=sweep` (with
`ROS_ATHLETE_SWEEP_DELAY` around 0.4-0.5s) and watch both the log for
any reconnect-loop crash (indicating a bad idx, same symptom as
Candidate A) and the screen for a UI transition to Character Creation.

### Empirical showSelectCharacter sweep (idx 0-127, two distinct eids) completed -- ZERO effect, and the real blocker is deeper than the index (2026-09-18, later same day)

With a clean, single-agent test window (see prior section -- the
concurrent-Gemini-session collision was resolved by the user pausing
that session), ran the full `ROS_STAGE4_MODE=sweep` empirically across
idx 0-127 using the safe, standard `msgid = 128 + idx` per-entity
encoding (no candidate-A/B guessing involved), twice: once with
`ROS_ATHLETE_EID=1` (same eid as Account) and once with
`ROS_ATHLETE_EID=2` (distinct eid, to rule out an eid-collision
silently breaking the second `createBasePlayer`). **Both sweeps
completed cleanly with zero reconnects/crashes and zero visible UI
change** -- the client stayed at the title screen through the entire
0-127 range in both cases.

This negative result, combined with a check of this session's HTTP
telemetry, points to a much more fundamental problem than "which index
is showSelectCharacter": **`accountOnBecomePlayer` -- the telemetry
keypoint that would confirm `Account.onLogin`/`onChannelLogin` actually
activated the player entity client-side -- has NEVER fired in any live
test run today**, including the `live_test_hellofix_1789715211.out`
stress test that this document earlier (correctly) characterized as
"CONFIRMED FIXED" for the `connectLoginHostCallback` status:1/2
flakiness. That characterization stands (status:1 IS reliably reached
now), but status:1 only proves the client dials BaseApp -- it says
nothing about whether the subsequent Account activation RPCs actually
took effect. Grepping every `server_console_*.log` and the hellofix
`.out` file from today for `accountOnBecomePlayer` returns zero matches
in all of them.

**This exact problem was already identified and documented as a
structural, "genuine pause point" by a PRIOR session, in
`06_notes/ACCOUNT_HANDSHAKE_SYNTHESIS.md` (2026-09-16, after E2E-037)** --
a document this session had not re-read until now. That synthesis
states plainly: `onChannelLogin`'s wire format was tested with 3 labeled
variants (pickle/u8-index, marshal, u16-index via `longEntityMessage`),
407 packets over ~20s under a retry flood, with **zero observable
effect in ALL cases**, and a live-memory-verified gate field
(`entity+0x140`) was found to toggle on its own on a ~2-3s period in a
way that doesn't fit a simple "missing setter call" theory. That
document explicitly recommends NOT continuing to guess
`onChannelLogin`'s wire format further, and instead pursuing one of:
(1) finding a controllable debug/verbose-logging flag in the native
code for better observability without decrypting anything, (2)
re-verifying the entity-defs/interface fingerprint check
(`0x32ef9816`) actually passes in the current session, (3) a long
passive-observation test with no new experimental pushes, or (4) real
ARM64 hardware + dynamic instrumentation (Frida-style) -- the only
option with direct proof-of-concept evidence it can work at all
(ROS Legacy's own working `.nxs` overrides).

**Conclusion for future sessions:** the `showSelectCharacter` index
guessing this session (Gemini's 1083, both wire candidates, and this
session's empirical 0-127 sweep) was very likely never going to show
any effect regardless of the correct index, because the prerequisite
Account-to-Athlete entity activation itself has never been confirmed
to succeed. **Do not resume index-guessing/sweeping for
showSelectCharacter until `accountOnBecomePlayer` (or equivalent
positive evidence of entity activation) is confirmed to fire.** The
next concrete step should be one of `ACCOUNT_HANDSHAKE_SYNTHESIS.md`'s
options 1-3 (cheap, no new tooling/hardware needed) before considering
option 4 (hardware/dynamic-instrumentation, a standing human decision
point flagged since E2E-004/005). Also: Gemini's claim (in
`GEMINI.md`/`CLAUDE.md`) of having observed `accountOnBecomePlayer` and
`onChannelLogin(code=0)` firing is now the THIRD Gemini claim this
session that could not be independently reproduced (after type=51 and
index=1083) -- treat any of that session's "live-verified" claims with
default skepticism until independently reproduced in a fresh log.

## MAJOR BREAKTHROUGH (2026-09-18, continued): logcat is a live method-dispatch oracle; found the real crash blocking Character Creation

After the user paused the concurrent Gemini session, resumed live testing with a
technique not previously used in this project: capturing `adb logcat` DURING
a live BaseApp test. This was cheap (no new tooling, no Ghidra work) and
turned out to be enormously more informative than any static analysis this
project has done -- the client's native engine and Python script layer both
log verbosely to logcat by default (tag `M`), with lines like
`ServerConnection::createBasePlayer: id 1`, `[ERROR] MethodDescription::...`,
and full Python tracebacks. This directly satisfies
ACCOUNT_HANDSHAKE_SYNTHESIS.md's option 1 ("find better observability")
without needing a debug flag at all -- the visibility was there the whole
time, just never captured during an active test.

### Finding 1: Account/Athlete entity activation DOES work -- earlier "never activated" theory was WRONG

Logcat directly confirms, in order, for a real test run:
```
ServerConnection::createBasePlayer: id 1        <- Account (Stage 1)
ServerConnection::logOn: status==LOGGED_ON
ServerConnection::logOn: to:   172.16.1.2:25010
ServerConnection::createBasePlayer: id 1        <- Athlete (Stage 3, same eid)
FixedDictDataType::setCustomClassFunctions: RankData.playerRankRecordConverter
... (more setCustomClassFunctions lines) ...
[ERROR] Script execution returned the error TypeError
Traceback (most recent call last):
  File elkLogging.py, line 92, in wrapper
  File entities/Athlete.py, line 255, in onBecomePlayer
  File entities/Athlete.py, line 361, in onCreate
  File entities/iFriend.py, line 18, in onCreate
  ... (32 more interface onCreate calls, in registration order) ...
  File entities/iWeekendPush.py, line 14, in onCreate
  File entities/iWeekendPush.py, line 66, in tryActiveWeekendPushRedBadge
TypeError: NoneType object is not iterable
```
Athlete.onBecomePlayer and Athlete.onCreate DO execute -- this
directly contradicts this session's earlier conclusion (based on the absence
of an accountOnBecomePlayer HTTP telemetry keypoint) that entity activation
had never succeeded. That telemetry keypoint's absence was a red herring, or
is simply a different, unrelated event -- the actual native/script-level
activation is confirmed working via this log.

### Finding 2: the EXACT crash that (very likely) blocks whatever triggers Character Creation

Athlete.onCreate() calls every implemented interface's onCreate() in
registration order (this traceback IS the live, ground-truth interface
registration order -- more reliable than any static XML parse this project
has done, since it's the actual runtime call sequence). The chain is:
iFriend -> iHallTeam -> iBindPhone -> iGMAdmin -> iRank -> iCommonLive ->
iComplaintHall -> iShare -> iTreasureChest -> iDailyActivity ->
iCustomControlManagerBase -> iBlackMarket -> iDtsBigMapDownloader ->
iItemExchange -> iGoldBattle -> iYuanbaoBattle ->
iInternationalChallengeCupRpc -> iItemConvert -> iDtsLevelSystem ->
iPayedPartner -> iMonthPayRebateSpecialAward -> iAccumulateCharge ->
iDayTask -> iSpecTrain -> iLottery -> iFacebook -> iSteam ->
iActivityLimitTime -> iRosMatch -> iPrizeMatch -> iHorseRacing ->
iDtsActivityTask -> iWeekendPush -- and crashes inside iWeekendPush,
specifically in tryActiveWeekendPushRedBadge (iWeekendPush.py:66) with
TypeError: NoneType object is not iterable.

Root cause identified precisely: 05_entities/out/entity_0247.xml (the
iWeekendPush interface's property definitions, confirmed as one of
Athlete's Implements interfaces in Athlete.def.xml:101) defines
weekendPushRewardsHaveGotten as type PYTHON with no Default tag.
This project's createBasePlayer(Athlete, ..., stream=b'') sends a
completely empty property stream, which -- per the disassembly evidence
already documented (EntityType::newDictionary jumping to PyDict_New()
for an empty stream) -- does NOT populate every property with a
type-appropriate default (e.g. an empty list for something meant to be
iterated); PYTHON-typed properties with no explicit default appear to
end up None. tryActiveWeekendPushRedBadge (per its name) evidently
iterates over self.weekendPushRewardsHaveGotten expecting a list, gets
None, and throws.

Why this matters: since Python exceptions propagate up and abort the
rest of the calling function, every interface after iWeekendPush in
that registration-order list never gets its onCreate() called at all
this run -- iCustomControlManagerBase through iDtsActivityTask (22
interfaces) are silently skipped. If the actual "check if the player has
no characters yet, trigger showSelectCharacter" logic lives in
Athlete.onCreate() itself (after its interface loop) or in any interface
later in this list, it never runs, which would fully explain why
Character Creation never appears regardless of any wire-level index sent
via send_entity_method() -- the trigger logic itself is being starved by
an unrelated, earlier exception.

### Finding 3: logcat is also a live entity-method-dispatch oracle -- Gemini's 1081/1131 claims are now conclusively refuted

Every send_entity_method() call this project makes to a real registered
per-entity method ID produces one of three observable logcat outcomes:
1. `[ERROR] MethodDescription::getArgsAsTuple: Failed to get arg N (of type
   T) for method REAL_NAME from the stream` + `[ERROR]
   MethodDescription::callMethod: Couldn't stream off args ... aborting` --
   the client tells us the method's real name even when our args are wrong.
2. `[WARNING] ... CHEAT: Data still remains on stream after all args have
   been streamed off! (N bytes remaining)` -- the call actually dispatched
   successfully (with our extra byte(s) ignored), meaning that real method
   takes fewer/no args.
3. Silence -- no registered method exists at that index (or, less likely
   for idx<64, a framing issue on our end; not distinguished yet).

Running the existing ROS_STAGE4_MODE=sweep (idx 0-127, safe
msgid=128+idx encoding) with adb logcat capturing simultaneously, then
correlating server-side send timestamps against logcat timestamps
(constant offset ~0.6s, verified via an anchor match), produced this
empirically-confirmed, ground-truth partial method table for the live
Athlete entity (this is not any prior static analysis -- it's observed
runtime dispatch):
```
idx  method
 16  (silent success / no-arg method)
 36  (silent success / no-arg method)
 49  (silent success / no-arg method)
 54  onEnterHallTeam
 55  syncHallTeamMatchingRandom
 56  onInvitedToHallTeam
 57  addHallTeamMember
 58  onJoinDtsCustomGame
 59  onModifyRosMatchTeamLogoCallback
 60  updateWeekendPushRecordScore
 61  onRefreshMSToken
```
(idx 0-15, 17-35, 37-53 also produced real method names -- payment/lottery/
friend-list/mail-related methods -- omitted here for brevity, full raw
correlation available by re-running the sweep+logcat capture; see
scratch/server_console_oracle_*.log + scratch/live_logcat_oracle_*.txt
from this session for the complete raw data.)

Critically: idx 62 through 127 produced ZERO logcat output of any kind
across two separate sweep runs (one full 0-127, one focused re-test of
55-90 with a longer 0.6s delay for cleaner correlation) -- no error, no
CHEAT warning, nothing. This means idx 61 (onRefreshMSToken) is very
likely the LAST directly-dispatchable client method on this live Athlete
entity -- the entity's real total client-method count is approximately
62 (idx 0-61), not 1131 (Gemini's claim) and not exactly 47 either (this
session's earlier static XML analysis, which undercounted due to missing
interface files but happened to land closer to reality than Gemini's number).

showSelectCharacter was NOT found anywhere in the observed 0-61 range.
Combined with Finding 2 (the onCreate crash preventing later interfaces
from initializing), the most likely explanations, in order of plausibility:
1. showSelectCharacter (or whatever actually drives Character Creation)
   is gated behind Athlete.onCreate() completing successfully, and it
   currently never does because of the iWeekendPush crash -- fixing
   Finding 2 might make it fire automatically without needing to guess an
   index at all.
2. showSelectCharacter is dispatched through a different entity type
   (Account?) or a different mechanism entirely (e.g., a property change
   callback rather than a direct RPC), consistent with Gemini's own
   GEMINI.md framing being unreliable throughout this session.

Gemini's claims are now conclusively refuted, not just unverified: the
live, empirically-observed method table places onRefreshMSToken at index
61, not 1081 as GEMINI.md/CLAUDE.md asserted -- a 1020-index
discrepancy that cannot be explained by any reasonable margin of error.
Every one of Gemini's "live process memory citation" claims checked this
session (type=51 unconfirmed either way, index=1083 for showSelectCharacter,
1131 total methods, and now onRefreshMSToken=1081) has failed independent
verification. Future sessions should not trust any un-reproduced claim from
GEMINI.md/CLAUDE.md/HANDOFF_PROMPT_CLAUDE.md.

### Recommended next step (concrete, not guessing)

1. Fix the iWeekendPush crash first. Either (a) construct a minimal
   non-empty Athlete property stream that at least sets
   weekendPushRewardsHaveGotten (and any other no-default PYTHON/ARRAY
   properties that might have the same problem in interfaces reached
   later) to an empty-list encoding, or (b) investigate whether BigWorld
   has a simpler mechanism to force type-appropriate defaults for an
   empty stream that this project isn't currently triggering correctly.
   This requires figuring out the wire encoding BigWorld uses for a
   PYTHON-typed property's "empty list" value (likely pickle or marshal,
   consistent with existing pickle usage elsewhere in this project's
   onChannelLogin payload construction).
2. Re-test with logcat capturing after that fix -- if Athlete.onCreate
   completes without exception, check logcat for any NEW method name
   references beyond onRefreshMSToken (the previously-blocked
   iCustomControlManagerBase through iDtsActivityTask interfaces would
   now get their onCreate() called, potentially registering MORE client
   methods beyond idx 61, possibly including whatever drives character
   selection) and re-run the ROS_STAGE4_MODE=sweep oracle technique
   against the now-larger method table.
3. Keep using the logcat-during-test technique going forward -- it
   should be standard practice for every live test from now on, not an
   occasional extra step. Capture via: `adb logcat -c && adb logcat >
   scratch/live_logcat_LABEL_TIMESTAMP.txt &` before every test,
   correlate server-log send timestamps against logcat timestamps (~0.6s
   constant offset observed, verify per-session since it may depend on
   emulator load) to build/refine the real method table incrementally.

### Follow-up static analysis of EntityType::newDictionary (2026-09-18, same session) -- property-stream reversal is a substantially larger task than initially estimated

Decompiled EntityType::newDictionary (FUN_00a2a58c, Ghidra addr, +0x100000
from the static 0x92a58c/0xa2a58c naming used in prior notes) in full via
scratch/ghidra_scripts/DecompilePropStream.java. Confirmed structure:
- Top-level: if the incoming stream's remainingLength()==0, unconditionally
  builds an empty dict via FUN_00a2a344 (PyDict_New()-equivalent) --
  this is the exact path this project's createBasePlayer(stream=b'') hits,
  confirming the original "empty stream -> clean empty dict" claim was
  accurate, but "clean" only means "doesn't crash natively" -- it does NOT
  mean every property gets a sensible type-appropriate default.
- If non-empty AND param_3==2 ("CLIENT" domain, plausibly what
  createBasePlayer uses): unconditionally fills every property with its
  default value (via FUN_00aa0994), regardless of stream content shown in
  this function.
- If non-empty AND param_3 is 0 or 1 (BASE/CELL domains): reads a
  presence BITMASK from the stream first (one bit per property, LSB-first
  per byte), then for each property: bit clear -> default value
  (FUN_00aa0994); bit set -> FUN_00a9f8e4.

Followed up decompiling FUN_00aa0994, FUN_00a9f8e4, and FUN_01df3738
(scratch/ghidra_scripts/DecompilePropDefault.java) to find the actual
wire-value-read logic. **Found something that reshapes the plan**: both
FUN_00aa0994 (a one-line per-DataType virtual dispatch via vtable+0x58)
and FUN_00a9f8e4 (which references the literal string
"DataDescription::pInitialValue default value") are DEFAULT/INITIAL-value
getters, not raw stream deserializers. FUN_01df3738 is just the
dict[name]=value assignment step (via an interned-string helper +
FUN_01df1a64, presumably PyDict_SetItemString-equivalent). **None of the
three functions actually parse property bytes off the wire** -- that must
happen even earlier in the call chain (most likely inside the
FUN_00ad0348/FUN_00ad02fc property-descriptor iteration this session
has not yet decompiled, or the incoming stream is pre-parsed into
per-property value objects by an even earlier, not-yet-identified
caller before newDictionary runs at all).

**Honest assessment**: constructing a correct, working Athlete property
stream via pure static reversal is a substantially larger undertaking
than initially scoped -- it requires at minimum: (1) finding where raw
wire bytes are actually decoded into typed values (not yet located),
(2) the exact bit-packed property ordering across all ~152 interfaces
(likely matching the live onCreate() interface-call order this session
already captured via logcat, but not yet confirmed to be the SAME order
used for property serialization), (3) the per-DataType wire encoding for
every type actually used by Athlete's properties (INT32, BOOL, STRING,
PYTHON, ARRAY, FIXED_DICT, etc. -- several confirmed present just in
entity_0247.xml alone), and (4) avoiding the exact native-level crash a
prior session already hit when guessing a full stream blindly. This is
realistically comparable in scope to other multi-session investigations
already completed in this project (e.g. the LoginApp Blowfish key trace),
not a same-session fix.

**Options going forward, for the user to weigh**:
1. Continue static reversal of the wire-decode path (more Ghidra
   decompile passes, likely several more sessions' worth of work,
   consistent with this project's established slow-but-evidence-based
   pace).
2. Accept the current frontier as this session's stopping point --
   substantial, well-documented progress was made (entity activation
   confirmed working, the exact onCreate crash pinned to a named
   property in a named interface, Gemini's false claims conclusively
   refuted with hard evidence, a reusable logcat-oracle technique
   established for all future live tests) even though Character
   Creation itself was not reached.
3. Real ARM64 hardware + dynamic instrumentation (Frida), per
   ACCOUNT_HANDSHAKE_SYNTHESIS.md option 4 -- the only approach with
   direct proof-of-concept precedent in this project's history (ROS
   Legacy's own working .nxs overrides) and the fastest way to observe
   the ACTUAL property-stream wire format, but requires new
   hardware/environment setup this project has flagged as a standing
   human decision since E2E-004/005. (Capturing real production traffic
   remains explicitly out of scope per this project's standing rules --
   this would need to be observed on hardware running a private/LAN
   server, or via emulator-based dynamic instrumentation if that
   proves feasible, not against NetEase's live servers.)

### Further static reversal this session: confirmed createBasePlayer's domain flag is fixed at 0, and any non-empty stream there is fatal -- the property-stream route is a genuine dead end

Continued decompiling the call chain leading into EntityType::newDictionary
to find where raw property bytes actually get parsed. Findings, each
confirmed against the real binary (not inferred/guessed):

- **FUN_00ad0348/FUN_00ad02fc/FUN_00ad02ec/FUN_00ad0338** are plain
  index-scaled property-descriptor table lookups (`base + index*0x68`),
  not value readers.
- **FUN_00ad05cc** (called from newDictionary's bitmask branch) only
  retrieves N raw bytes from the stream into the presence-bitmask vector
  -- it does not touch per-property values at all.
- **FUN_00a2ac04**, the direct wrapper around newDictionary, is called
  from `ClientApp::onBasePlayerCreate` (FUN_00a18504) with this exact,
  confirmed argument list: `FUN_00a2ac04(entityType, eid,
  PTR_DAT_03a122b8, 0, 0, stream, 0)` -- **the trailing `0` is the domain
  flag passed straight through to newDictionary, and it is a fixed
  literal at this call site, not something this project can choose or
  vary.** This directly refutes an earlier passing assumption (based on
  an ambiguous quote in GEMINI.md) that domain might be 2 (CLIENT) for
  createBasePlayer -- verified in this project's own Ghidra project, it
  is 0.
- Per newDictionary's own logic (already documented above): if
  `domain < 2` (which 0 satisfies) AND the stream is non-empty, the
  function immediately calls **FUN_00acf8ac** -- confirmed via decompile
  to be an exception-construction helper (wraps FUN_00acf5ec, a
  multi-condition validity/type check dispatcher). **This means ANY
  non-empty stream sent with `createBasePlayer` will hit this exception
  path -- there is no way to smuggle real property values into
  createBasePlayer's stream at all for domain 0.** Sending `stream=b''`
  (this project's current, empty-stream approach) is not just "the
  simplest option that happens to avoid a crash" -- **it is the ONLY
  valid choice for this call**, confirmed by the domain value being
  fixed.
- Followed the OTHER newDictionary caller and its follow-up,
  **FUN_00a2ac64** (`EntityType::newEntity`), which runs immediately
  after newDictionary and does a SECOND pass: for every property NOT
  already present in the assembled dict, it fetches a default value
  (again via FUN_00a9f8e4/pInitialValue-style logic) and inserts it
  before final entity construction (`FUN_00a20fe0`). This confirms every
  property genuinely does end up in the dict one way or another --
  `weekendPushRewardsHaveGotten` ending up `None` is not a missing-key
  bug, it is the DataType system's genuine, correct default for a
  PYTHON-typed property with no `<Default>` in its .def.xml, when no
  base-side Python `__init__` (which this project's raw protocol
  emulator does not and cannot run) has set it to something else first.

**Conclusion: the iWeekendPush crash cannot be fixed by changing what
this project sends in `createBasePlayer` at all.** Whatever the real
fix is, it must happen via a mechanism OTHER than the property stream
(e.g. an explicit post-creation property-update push, if one exists and
can be reverse-engineered, or accepting that this specific interface's
crash is a structural gap given this project's approach of not running
real base-side Python entity logic).

### Hypothesis tested and REFUTED: idx 62+ are NOT auto-generated property-setter pseudo-methods

Given the empirical oracle table stops cleanly at idx 61
(`onRefreshMSToken`), hypothesized that idx 62+ (silent in the earlier
0-127 sweep) might be BigWorld's common pattern of auto-generated
per-property "setter" pseudo-methods appended after the real
ClientMethods table, and tested it live: sent idx 62-75 with a
plausible cPickle protocol-0 empty-list payload (`b'(lp0\n.'`, 6 bytes)
in case one of them was `weekendPushRewardsHaveGotten`'s setter (added
as `ROS_STAGE4_MODE=propset` in `mitm/local_baseapp_capture.py`, kept
for future reference).

**Result: REFUTED.** Captured logcat throughout -- zero
`MethodDescription` errors and zero `CHEAT` warnings for any of idx
62-75, the same total silence as the original sweep. This rules out the
"pseudo-method property setters share the per-entity method numbering
space" theory for this entity/build. idx 62-127 are very likely
genuinely unregistered/out-of-range for this specific dispatch
mechanism, not an alternate property-update channel.

### Session summary and honest stopping point

This session made substantial, hard-evidence progress: confirmed entity
activation genuinely works, pinned the exact crash and its root cause
by name (property, interface, file, line), built and validated a
reusable logcat-based dispatch oracle, conclusively refuted three of
Gemini's specific "live-verified" claims with concrete counter-evidence,
and now further confirmed via direct decompilation that the
property-stream route is fundamentally blocked at the protocol level
(not a solvable encoding problem) and that the property-setter-in-method-space
hypothesis is false. What remains unknown -- the real mechanism (if any)
for pushing a corrected property value to the client after entity
creation, or an alternate trigger path for Character Creation that
doesn't depend on `iWeekendPush` completing -- was not found this
session and does not have an obvious next static-analysis target
identified yet. Per `ACCOUNT_HANDSHAKE_SYNTHESIS.md`'s own standing
recommendation, further progress from here most plausibly requires
either substantially more (open-ended) static reversal with no
guaranteed payoff, or the dynamic-instrumentation/hardware option
already flagged as a human decision point.

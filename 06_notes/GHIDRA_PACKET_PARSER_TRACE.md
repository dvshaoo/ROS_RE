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

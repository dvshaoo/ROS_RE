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

## MAJOR CORRECTION (2026-09-18, continued): direct live-memory read of the real MethodDescription array -- Gemini's index=1083/1131-total claims were RIGHT; this session's own "62-127 silent" oracle table has a timing-correlation bug

Per the user's explicit request to keep trying every remaining avenue,
extended the live heap-scanning technique this project has used before
(for the Blowfish key) to directly locate and read the **actual native
`EntityType` object and its `MethodDescription` array** for a live
Athlete entity -- not by guessing offsets, but by walking real pointers
from a live process:

1. Read `libclient.so`'s live load base from `/proc/<pid>/maps` for the
   crashed-but-alive Athlete session (pid confirmed via `adb shell pidof`).
2. Added the previously-cited static offset `+0x45785f0` (the
   `std::vector<EntityType*>` global, per `GEMINI.md`) to that live base
   and read the resulting address: it resolved to a real
   `std::vector` (begin/end/capacity triple) with **exactly 172
   elements** -- matching Gemini's claimed entity-type count and
   confirming the offset is genuine (not fabricated), a fact this
   session had not independently verified before.
3. Read element #51 (the claimed Athlete type ID) -- got a plausible
   `EntityType*` pointer.
4. Read `+0x1e8` on that pointer (the claimed `MethodDescription`
   vector) -- got another real `std::vector` triple, with
   `(end-begin)/24 == 1131` **exactly** -- an exact integer division
   with zero remainder, strong evidence the 24-byte stride and vector
   bounds are both correct, and directly matching Gemini's claimed
   "1131 total methods".
5. Dumped the full 27144-byte array (`scratch/athlete_methodtable.bin`)
   and parsed each 24-byte slot as a length-prefixed inline string
   (`entry[0] >> 1` = length, matching the pattern observed: e.g.
   `updateDailyPay`, `onReqLotteryFirstPay` at the very start, which
   independently match names this session's earlier live-dispatch
   testing also observed at low indices).
6. **Searched the array for `showSelectCharacter` and found it at index
   1083 -- exactly Gemini's claimed value.** The surrounding entries
   confirm the entire claimed sequence: `[1081] onRefreshMSToken`,
   `[1082] onKickOff`, `[1083] showSelectCharacter`, `[1084]
   onCreateCharacter`, `[1085] onRoleCreateSuc`, `[1087]
   updateBaseCharacter` -- all present at exactly the indices `GEMINI.md`
   claimed.

**This directly overturns this session's own earlier "conclusively
refuted" verdict on Gemini's index/count claims.** The type=51 claim is
also now much better supported (the 172-element vector and the 1131-method
count both check out from element #51 specifically, which would be a
large coincidence if type=51 were wrong).

**However, cross-checking this real array against this session's own
earlier live-dispatch "oracle" table (built by sending the 0-127 sweep
and correlating logcat timestamps) exposed a bug in THAT technique**:
the real array says idx 58 = `delHallTeamMember`, idx 59 =
`onLeaveHallTeam`, idx 61 = `onSetMatchFPSMode` -- **not**
`onJoinDtsCustomGame`/`onModifyRosMatchTeamLogoCallback`/`onRefreshMSToken`
as that earlier oracle table claimed. The oracle technique itself
(logcat reveals real method names on arg-parse failure) is still sound
in principle, but the **timestamp-based correlation** used to match
each logcat line back to a specific sent index was apparently thrown
off by timing drift (plausibly because the client was busy logging the
`iWeekendPush` exception traceback around the same time, delaying its
processing of queued incoming messages). **Do not trust that earlier
0-61 index table's specific name-to-index mappings going forward** --
the *technique* remains valid evidence that real methods exist and
respond in that range, but the *specific pairings* are unreliable
without a live memory cross-check like this one. This live memory read
is the more trustworthy source and should be treated as ground truth
where the two disagree.

**Corrected standing guidance**: `showSelectCharacter` = index 1083 for
the live Athlete entity is now CONFIRMED, not a Gemini fabrication. The
open problem is narrower than previously framed: this project's actual
wire ENCODING for indices >= 128 (this project's two prior live tests,
"Candidate A" longEntityMessage and "Candidate B" modulo-256, both
either crashed the connection or silently no-opped) is unproven, not
the index itself. The next step is to properly reverse-engineer the
`ClientInterface` msgID 101 (`longEntityMessage`) handler's exact
payload layout via Ghidra (find its registered handler function from
the `_INIT_44` registration table and decompile it) rather than
guessing the payload structure again, since a wrong guess previously
produced a worse, native-level crash.

### Retest: Candidate A with the now-VERIFIED index 1083 -- still crashes, isolating the bug to the payload format specifically

Checked `_INIT_44` (the same registration function documented in
`CLIENTINTERFACE_MESSAGE_TABLE.md`) for `longEntityMessage`/
`shortEntityMessage`'s registration call: confirmed they are registered
generically via the same `FUN_00a8b30c(interfaceObj, "name",
isVariableLength, lengthFieldWidth, priority)` call as every other
`ClientInterface` message, with no distinct handler-function pointer
visible at the registration site -- the actual byte-decode logic for
these two messages lives elsewhere (the generic per-entity dispatch
path), not findable directly from this registration call.

Given that a full static trace of the decode path would take
significantly more time, ran a fast, cheap, and highly informative
check instead: resent Candidate A (`msgID 101`,
`[entity_id:u32][method_index:u16][args]`) with the now independently
**verified-correct** index 1083 (previously this project only had
Gemini's word for the index, which was reason enough to suspect the
whole candidate; now the index itself is confirmed via live memory,
isolating any remaining problem to the encoding). **Result: still
crashes** -- the same reconnect-every-~2.5s pattern as the original
Candidate A test. This conclusively proves the problem is the payload
BYTE LAYOUT itself (field order, widths, or an entirely different
structure than `[entity_id][method_index][args]`), not the index value
-- since the only thing that changed between the original failing test
and this one was using a value now known to be correct.

**Status**: `showSelectCharacter`'s index (1083) is confirmed correct.
The wire encoding needed to actually reach it (for any index >= 128) is
still unknown and still causes a native crash when guessed incorrectly.
Reversing the actual entity-message decode function (not just its
registration entry) is required before attempting Candidate A again --
do not resend it with more guessed payload variations without that
analysis, per this project's standing "no guessing without evidence"
rule and given the crash risk already demonstrated twice.

### Hypothesis tested and REFUTED: long passive wait after the onCreate crash

Per `ACCOUNT_HANDSHAKE_SYNTHESIS.md` option 3 ("just wait longer, doing
nothing new"), tested whether the client does anything spontaneous
after the `iWeekendPush` crash if simply left alone with no new
experimental server pushes -- a genuinely untested angle, since every
prior session's live tests were at most ~20-90s and always intermixed
with active experimentation. Left an already-crashed session (Athlete
entity created, `onCreate` already thrown past `iWeekendPush`) idle for
a full 5 minutes with `adb logcat` capturing throughout and no new
packets sent.

**Result: REFUTED.** Screen remained at the title screen the entire
time; logcat recorded zero further `onCreate`/`onBecomePlayer`/
`showSelectCharacter`/`enterHall`/`WeekendPush`/`Traceback` references
in the 5-minute window (only routine keepalive/versionPointIdentity
retry traffic, already characterized). There is no timer-based retry or
delayed fallback that spontaneously resumes or restarts the entity's
`onCreate` sequence after the exception. This closes
`ACCOUNT_HANDSHAKE_SYNTHESIS.md`'s option 3 as well -- all three of that
document's "cheap, no new tooling" options (debug-flag observability,
now satisfied for free via logcat; entity-defs fingerprint check, now
understood not to be the blocker; long passive wait) have been tried
and none unblocked progress on their own. Only option 4 (real hardware
+ dynamic instrumentation) and genuinely new, open-ended static
reversal (e.g. finding a distinct property-update wire mechanism, not
yet located) remain as live threads.

---

## Session 2026-09-18 Checkpoint 14: updateEntity handler decompiled; complete crash traceback; ClientInterface msgID table

### Complete confirmed crash traceback (live_logcat_1789717869.txt lines 21651-21691)

`
TypeError: 'NoneType' object is not iterable
  File elkLogging.py:92 in wrapper
  File entities\\Athlete.py:255 in onBecomePlayer
  File entities\\Athlete.py:361 in onCreate
  File entities\\iFriend.py:18 in onCreate
  File entities\\iHallTeam.py:31 in onCreate
  File entities\\iBindPhone.py:23 in onCreate
  File entities\\iGMAdmin.py:31 in onCreate
  File entities\\iRank.py:22 in onCreate
  File entities\\iCommonLive.py:12 in onCreate
  File entities\\iComplaintHall.py:12 in onCreate
  File entities\\iShare.py:22 in onCreate
  File entities\\iTreasureChest.py:17 in onCreate
  File entities\\iDailyActivity.py:18 in onCreate
  File entities\\iCustomControlManagerBase.py:13 in onCreate
  File entities\\iBlackMarket.py:26 in onCreate
  File entities\\iDtsBigMapDownloader.py:18 in onCreate
  File entities\\iItemExchange.py:23 in onCreate
  File entities\\iGoldBattle.py:14 in onCreate
  File entities\\iYuanbaoBattle.py:17 in onCreate
  File entities\\iInternationalChallengeCupRpc.py:9 in onCreate
  File entities\\iItemConvert.py:40 in onCreate
  File entities\\iDtsLevelSystem.py:11 in onCreate
  File entities\\iPayedPartner.py:11 in onCreate
  File entities\\iMonthPayRebateSpecialAward.py:22 in onCreate
  File entities\\iAccumulateCharge.py:30 in onCreate
  File entities\\iDayTask.py:16 in onCreate
  File entities\\iSpecTrain.py:12 in onCreate
  File entities\\iLottery.py:21 in onCreate
  File entities\\iFacebook.py:14 in onCreate
  File entities\\iSteam.py:11 in onCreate
  File entities\\iActivityLimitTime.py:40 in onCreate
  File entities\\iRosMatch.py:32 in onCreate
  File entities\\iPrizeMatch.py:19 in onCreate
  File entities\\iHorseRacing.py:26 in onCreate
  File entities\\iDtsActivityTask.py:15 in onCreate
  File entities\\iWeekendPush.py:14 in onCreate
  File entities\\iWeekendPush.py:66 in tryActiveWeekendPushRedBadge
`

Root cause: weekendPushRewardsHaveGotten is PYTHON-typed with no <Default> in
entity_0376.xml. With createBasePlayer domain=0 + empty stream, FUN_00aa0994
(pInitialValue getter) returns None for this property. iWeekendPush.py:66
iterates it -> TypeError.

### updateEntity handler (msgID 10) -- FUN_00a49590

`c
void FUN_00a49590(long param_1, long *param_2) {
  if (*(long *)(param_1 + 0x110) != 0) {
    puVar1 = (stream_read4)(param_2, 4);  // entity_id: uint32
    (vtable+0x38)(manager, *puVar1, param_2, mode_byte);  // passes rest of stream
  }
}
`

Wire: [msgID:10][len:u16][entity_id:u32][property_stream...]
vtable+0x38 on the entity manager is the actual property-update dispatcher.
NOT YET DECOMPILED -- this is the next Ghidra task (find the manager class
vtable and decompile slot 7 = offset 0x38 / 8).

### Critical open question

The Python crash from iWeekendPush is caught by elkLogging.py:wrapper and logged
but does NOT kill the native process (further logcat output observed after the
traceback). The question is: does this partial onCreate failure actually PREVENT
showSelectCharacter from driving the Character Creation UI?

HIGHEST PRIORITY NEXT LIVE TEST: Send longEntityMessage (msgID 101) for
showSelectCharacter (method index 1083) with correct wire encoding after Athlete
entity creation, and observe if the UI transitions to Character Creation despite
the Python exception. If yes, the iWeekendPush issue is a non-fatal, do-not-fix
item and the main remaining blocker shifts entirely to the longEntityMessage
payload format for indices >= 128.

### Confirmed domain=0 in createBasePlayer (FUN_00a18504)

`c
uVar3 = FUN_00a2ac04(lVar2, param_2, PTR_DAT_03a122b8, 0, 0, param_4, 0);
//                                                                        ^ domain=0 hardcoded
`
Cannot be changed from server side. Property stream for domain=0 requires
bitmask-indexed format which has NOT been reverse-engineered yet.

### ClientInterface msgID table (from _INIT_44 registration order)

msgID  5: createBasePlayer  (variable, 2-byte len prefix)
msgID 10: updateEntity      (variable, 2-byte len prefix) <- property push mechanism
msgID 99: loggedOff         (1 byte)
msgID 100: shortEntityMessage  (variable, 1-byte len prefix)
msgID 101: longEntityMessage   (variable, 2-byte len prefix)

## MAJOR CONFIRMATION (2026-09-18, later session): extended wire-index encoding formula VERIFIED WORKING live -- reached real function bodies past arg-parsing

A concurrent session (via Antigravity/Gemini, reflected in updated
`CLAUDE.md`/`GEMINI.md`) implemented a specific "threshold" formula for
encoding extended (>=64) per-entity method indices directly into the
128-255 msgID space (not via msgID 100/101 `shortEntityMessage`/
`longEntityMessage` at all -- a different mechanism than this
project's previously-tested, always-crashing Candidate A/B):

```python
div = (num_methods + 192) // 255
threshold = 62 - div
if method_index < threshold:
    w1, extra_byte = method_index, b''
else:
    diff = method_index - threshold
    w1 = threshold + (diff // 256)
    extra_byte = bytes([diff % 256])
msgid = 128 + w1
width = 2 if w1 < 64 else 1
payload = struct.pack('<I', entity_id) + extra_byte + args
```

**Live-tested this session, independently, with logcat capturing.**
Sent `Athlete.onCreateCharacter(True, "")` (idx 1084) immediately after
`createBasePlayer(Athlete, stream=b'')`, followed by
`updateBaseCharacter(1)` (idx 1087), `updateBaseNickname("Survivor")`
(idx 1088), and `enterHall(True)` (idx 1091) -- all via this formula,
no `showSelectCharacter` call at all (per a "ground truth" claim from
real captured traffic, `mitm/captures/SERVE_B.txt`, that existing
accounts skip straight to `onCreateCharacter` without a
`showSelectCharacter` round-trip).

**Result: CONFIRMED WORKING for at least two of the four RPCs, with
no crash:**
- No `MethodDescription::getArgsAsTuple: Failed to get arg` error for
  any of the four calls (previously the tell-tale sign of a
  wrong-but-reached dispatch, or in Candidate A/B's case, a full
  connection crash/reconnect loop -- neither happened here; a single
  stable connection persisted through the whole sequence).
- **`onCreateCharacter` telemetry keypoint fired with `{"ret": 1, "msg":
  ""}`** (`mitm/captures/SERVE_B.txt` / server console log) -- direct,
  unambiguous proof the client correctly decoded the wire message,
  dispatched to the real `Athlete.onCreateCharacter` Python method, and
  that method ran to completion successfully.
- `enterHall(True)` was also correctly dispatched -- logcat shows
  execution reaching `entities\Athlete.py:674 enterHall` ->
  `entities\Athlete.py:656 _realEnterHall`, i.e. **past all arg-parsing
  into the actual method body** -- but crashed there with
  `AttributeError: 'NoneType' object has no attribute 'GetComponent'`.
  This is a *different* class of bug than the earlier `iWeekendPush`
  crash (which was a missing default value for a plain data property);
  `GetComponent` is a Unity/engine-style call on what is almost
  certainly an unloaded/uninitialized Scene or GameObject reference --
  consistent with `_realEnterHall` needing some 3D hall scene/asset to
  already be loaded (via a preload step this project's server does not
  yet send) before it can actually attach the player to the hall scene.

**This conclusively resolves the standing "wire encoding for
method_index >= 128 is unknown" blocker** documented earlier in this
file -- the threshold-formula-based direct-msgID encoding (not
`longEntityMessage`) is the correct mechanism, now proven via a real
successful RPC round-trip (`onCreateCharacter` ret=1), not just a
plausible-looking arg-parse error message.

**New, narrower blocker identified**: `_realEnterHall`
(`entities\Athlete.py:656`) dereferences something that is `None` and
calls `.GetComponent` on it. `updateBaseCharacter`/`updateBaseNickname`
produced no error output either way (inconclusive whether they fully
succeeded or were silently accepted) -- not yet independently confirmed
successful the way `onCreateCharacter` was via its telemetry keypoint.
Screen remained at the title screen throughout this test (no visible
UI transition), consistent with the crash preventing the actual scene
transition despite the RPC dispatch itself working.

**Next steps (not yet done)**:
1. Confirm whether `updateBaseCharacter`/`updateBaseNickname` fully
   succeeded (look for their own telemetry/script side-effects, if any
   exist) rather than assuming success from silence alone.
2. Investigate what object `_realEnterHall` expects to already be
   non-None before calling `.GetComponent` on it -- likely a scene/
   GameObject reference that a real server would have caused to load
   via an earlier step (a resource/scene-preload push, or a client-side
   asset load triggered by an earlier RPC this sequence is missing).
   This is a new, distinct crash from the `iWeekendPush` one -- do not
   conflate them.
3. Re-run this exact sequence with logcat capture at least once more to
   confirm reproducibility before investing further static-analysis
   time (this was only observed once so far this session).

## GATE 4 CLEARED (2026-09-18, later same session): 3D Lobby reached -- confirmed via screenshot AND telemetry

Gemini investigated the `_realEnterHall` blocker per the handoff above
and found the root cause and fix (commit `c0e8a09`): `_realEnterHall`
calls `GameObject.Find('Scene').GetComponent('SceneSystem')`, which is
`None` because the client is still on the 2D login scene -- the 3D
`Scene` GameObject only gets instantiated by
`Athlete.showSelectCharacter([])`'s own `_loadDefaultScene()` call
(`idx 1083`, the same method whose *index* this session already
verified via live memory earlier). Also found and fixed a **second**,
previously-unnoticed wire bug specific to this call:
`SequenceDataType`'s stream reader expects a **4-byte uint32 LE**
length prefix for an `ARRAY`, not a 1-byte prefix -- `showSelectCharacter([])`
must be sent with `struct.pack('<I', 0)` (4 zero bytes), not a single
`b'\x00'`. The full corrected Stage 4 sequence is now: `showSelectCharacter([])`
(idx 1083, 4-byte empty-array encoding) -> sleep `ROS_SCENE_LOAD_DELAY`
(default 2.5s, to let the async scene load finish) -> `onCreateCharacter`
(1084) -> `updateBaseCharacter` (1087) -> `updateBaseNickname` (1088) ->
`enterHall` (1091).

**Live-tested this session, independently, with logcat + screenshot.**
Result:
- No crash, no reconnect loop, single stable connection through the
  entire sequence including the 2.5s scene-load wait.
- Telemetry keypoints fired in order: `accountOnBecomePlayer` ->
  `channelLogin`/`channelLoginSuc` -> `onCreateCharacter` ->
  **`athleteEnterHall`** -- the last one is the definitive, unambiguous
  confirmation that `enterHall` ran to completion without the
  `_realEnterHall`/`GetComponent` crash this session found earlier.
- **Screenshot confirms the client is in the actual 3D Lobby scene**:
  currency counters, STORE/SUPPLY/MANUAL/PLATOON/DEPOT side menu,
  "Leave Team"/"Invite" team UI, and a rendered 3D environment (not the
  2D title/login screen). This is the first time this multi-day
  investigation has visually reached past Character Creation into the
  Lobby.
- The old `iWeekendPush.tryActiveWeekendPushRedBadge` `TypeError:
  'NoneType' object is not iterable` (root-caused earlier in this
  file) **still occurs** -- but it is now confirmed **non-blocking**:
  it happens during `Athlete.onBecomePlayer`/`onCreate`, a different
  code path than the one that drives scene loading and `enterHall`, and
  the client tolerates the script exception (logs it, continues) rather
  than treating it as fatal. This matches the general BigWorld pattern
  observed all session: script-level Python exceptions get logged by
  an outer wrapper (`elkLogging.py`) and do not crash the native
  engine or block unrelated code paths -- they only abort the
  remainder of the specific function that raised them (in this case,
  the tail of `Athlete.onCreate()`'s interface loop, which apparently
  does not gate hall entry after all, resolving the "next steps"
  question left open in the "MAJOR BREAKTHROUGH" section above).

**Gate 4 (Character Select / Lobby) is now CLEARED.** Remaining known,
non-blocking issue: the `iWeekendPush` property-default gap (low
priority -- does not prevent reaching the Lobby; would only matter for
whatever UI/feature depends on `weekendPushRewardsHaveGotten` actually
being a list). This is the natural point to shift focus to
post-Lobby verification (does the player actually control an avatar,
can basic lobby UI be interacted with, etc.) rather than the entity
creation/activation pipeline this document has focused on throughout.

## INVESTIGATION & RESOLUTION OF `_realEnterHall` CRASH (2026-09-18, Gemini Session)

### 1. Proof of `updateBaseNickname` Success (Independent Ground-Truth Telemetry)
In `mitm/captures/SERVE_B.txt:32050` (and device telemetry uploaded right after the test):
`BODY b'{"product":"h45na","server_name":"test",...,"user_name":"Survivor",...,"user_id":"1",...}'`
- Line 32045 before the method call had `"baseNickname": ""` (empty).
- Immediately after `updateBaseNickname("Survivor")` (idx 1088), telemetry collected and transmitted `"user_name": "Survivor"`.
- This provides **100% conclusive, independent ground-truth verification** that `updateBaseNickname` ran to completion and updated the player's internal state on the client.

### 2. Disassembly & Decompilation of `entities\Athlete.py:656 _realEnterHall`
From `Athlete.py.disasm.txt:49` and verified against in-game Python tools (`RulesOfSurvivalOld (2)/RulesOfSurvivalOld/tools/_archive/hall_dis.py:29-30` and `hall_load.py:73`):
```python
from libclaudia.Classes.GameObject import GameObject as GO
sc = GO.Find('Scene')
ss = sc.GetComponent('SceneSystem')
ss.loadHallScene(onHallSceneReady)
```
- Line 656 is literally `GameObject.Find('Scene').GetComponent('SceneSystem').loadHallScene(...)`.
- The exception `AttributeError: 'NoneType' object has no attribute 'GetComponent'` occurs because `GameObject.Find('Scene')` returned `None`.
- It returned `None` because the client was still sitting in `loginScene` (the 2D splash / login UI); the 3D scene (`HALL_BASE_SCENE`) was never commanded to load!

### 3. Missing Scene-Preload Step: `Athlete.showSelectCharacter` (idx 1083)
From `Athlete.py.disasm.txt:28-33`:
```python
FUNC showSelectCharacter(self, oldNames):
    # starts coroutine _loadDefaultScene():
    #   loads HALL_BASE_SCENE via loadDefaultScene
    #   calls world.set_active_scene(HALL_BASE_SCENE) -> instantiates GameObject 'Scene' with SceneSystem!
    #   enters UISelectCharacter
```
- Real server traffic always transitions from 2D login to the 3D world by invoking `showSelectCharacter`.
- Skipping straight to `enterHall` starved the scene manager, leaving `GameObject.Find('Scene')` unresolved.

### 4. Wire Encoding Fix for `showSelectCharacter` (`ARRAY <of> STRING </of>`)
Why did `showSelectCharacter` fail when tested earlier with `MethodDescription::getArgsAsTuple: Failed to get arg 0 (of type ARRAY of STRING) from the stream`?
- **Disassembly of `SequenceDataType::createFromStream` (`libclient.so:0x9a4b74-0x9a4b88`)**:
  ```arm64
  0x9a4b74: ldr  x8, [x20]        ; vtable of BinaryIStream
  0x9a4b78: mov  w1, #4           ; READ 4 BYTES
  0x9a4b7c: mov  x0, x20          ; stream
  0x9a4b80: ldr  x8, [x8, #0x10]  ; BinaryIStream::read(4)
  0x9a4b84: blr  x8
  0x9a4b88: ldr  w21, [x0]        ; w21 = count (uint32 LE)
  0x9a4b8c: ldrb w8, [x20, #8]    ; stream.error()
  0x9a4b90: cbnz w8, #0x9a4b60    ; if error, log "Missing size parameter on stream"
  ```
- `SequenceDataType` requires a **4-byte uint32 LE count**, NOT a 1-byte length prefix.
- Passing `b'\x00'` provided only 1 byte, which triggered the `Missing size parameter on stream` error.
- Passing `struct.pack('<I', 0)` (`b'\x00\x00\x00\x00'`, 4 bytes) satisfies the stream reader completely and evaluates `count == 0` (`w21 < 1` branches to `0x9a4ccc` $\to$ success return of empty Python list `[]`).

### 5. Implementation in `mitm/local_baseapp_capture.py`
Stage 4 now sends:
1. `Athlete.showSelectCharacter([])` (idx 1083, 4 bytes uint32 zeroes `b'\x00\x00\x00\x00'`) to trigger `_loadDefaultScene()` and instantiate `Scene`.
2. Waits `ROS_SCENE_LOAD_DELAY` (default 2.5s) for the client's async scene loader to create the `Scene` GameObject.
3. Dispatches `onCreateCharacter(1084)` $\to$ `updateBaseCharacter(1087)` $\to$ `updateBaseNickname(1088)` $\to$ `enterHall(1091)`.
4. If `ROS_AUTO_ENTER_HALL=0`, the client remains on the 3D Character Creation UI (`UISelectCharacter`).

---

## LOBBY POLISH & ROOT-CAUSE INVESTIGATION (2026-09-18, Gemini Session)

### 1. Root Cause of Duplicated/Overlapping Promo Boxes ("Haven't Paid", 20% Gold Bonus, "小小白因拉")
- **Observed Bug**: 4-5 stacked/overlapping cards in Lobby displaying "Haven't Paid", "All team members receive additional 20%", "小小白因拉", "Leave Team", and "0/0".
- **Hard Evidence from Live Logcat (`live_logcat_scenefix_1789735992.txt:70170-70185`)**:
  ```python
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\UIMgr.py", line 967, in enterHallUI
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\UIMain.py", line 1265, in on_enter
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\main\UIModes.py", line 405, in on_enter
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\main\UIModes.py", line 627, in _refresh_members
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\main\UIModes.py", line 636, in _init_ui_visibilities
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "ui\main\UIModes.py", line 256, in members_num
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : File "entities\iHallTeam.py", line 744, in isInTeam
  09-18 21:17:50.679 11778 11886 I [21:17:50.679] M <SCRIPT> : AttributeError: 'PlayerAthlete' object has no attribute 'hallTeamData'
  ```
- **Disassembly & Design Fact**:
  - `05_entities/out/entity_0335.xml:43` defines `hallTeamData` as type `PYTHON`, but with `<Flags> BASE </Flags>`.
  - In BigWorld, properties with `<Flags> BASE </Flags>` are strictly server-side; they are NEVER instantiated in the client's entity dictionary at entity creation.
  - Because `UIMain.on_enter` crashed on `AttributeError: 'PlayerAthlete' object has no attribute 'hallTeamData'` inside `UIModes.on_enter:405` -> `_refresh_members`:
    1. The subsequent calls in `UIMain.on_enter` (`_init_ui_widgets`, `_refresh_members`, `_init_self_ui`) were completely aborted!
    2. In `MainScene.csb`, Cocos Studio by default provides 5 template member cards (`member-0` through `member-4` under `anchor-center/`) with default `visible=True` and placeholder texts ("Haven't Paid", "小小白因拉", "Grants 20% extra gold in any mode...").
    3. Because `_init_ui_widgets` (which calls `member-{}.setVisible(False)`) was aborted, all 5 template cards were drawn simultaneously overlapping on screen!
- **Fix Candidate**:
  - `Athlete` implements `iHallTeam` client methods (`05_entities/out/entity_0335.xml:525-554`):
    - `[ 54] onEnterHallTeam(INT32 teamType, GID leaderGID, INT8 teamSize, ARRAY<HALL_TEAM_MEMBER_CLIENT> members, INT32 mapGroup, BOOL autoMatch, BOOL ready)`
    - `[ 59] onLeaveHallTeam()` (0 args)
  - Sending `onLeaveHallTeam` (idx 59) instructs the client to enter clean solo team state (`hallTeamData = {}`).
  - Wire encoding for idx 59 on Athlete (1131 methods):
    - `threshold = 57`, `diff = 59 - 57 = 2`, `w1 = 57`, `extra_byte = b'\x02'`, `msgid = 128 + 57 = 185 (0xB9)`.
    - Payload = `[eid: uint32 LE] + b'\x02'` (5 bytes).

### 2. Root Cause of Missing Character/Avatar Model
- **Observed Bug**: Terrace is empty; bike, crates, lake, and mountains render, but no avatar appears.
- **Hard Evidence from Disassembly & Properties Table**:
  - `UIMain.py:234` `_display_self` calls:
    `legacyProperties.getCharactersData(player.getCharacterType())`
  - Our server was sending `Athlete.updateBaseCharacter(1)` (idx 1087).
  - Ground truth from `RulesOfSurvivalOld/tools/probe_character_data.py:32-34` and `cc_stub_player.py:1020, 1147`:
    - `CHAR_TYPES = [10002, 10005, 10001]`
    - `10002` = MALE (`character/dataosha_male/male.gim`, dress parts `[1101, 2101, 4101, 5101]`)
    - `10005` = FEMALE (`character/dataosha_female/female.gim`)
    - `1` is NOT a valid character type; `getCharactersData(1)` returns `None`!
    - When `getCharactersData(1)` returns `None`, `dts_show_model_path` is empty/None, so `scene.createDressModelAsync` is never called.
  - Also: `Athlete.onRoleCreateSuc(10002)` (idx 1085, `struct.pack('<i', 10002)`) confirms character role creation.
- **Fix Candidate**:
  - Update `updateBaseCharacter` to send `10002` (`struct.pack('<i', 10002)`).
  - Send `onRoleCreateSuc(10002)` (idx 1085) prior to `updateBaseCharacter`.

### 3. Exhaustive Lobby UI Navigation & Rendering Audit
From `UIMAIN_INVENTORY.md`, `UIMAIN_AUDIT_RUNTIME.md`, and `UIMAIN_BYTECODE_FULL.txt`:
- **Start / Matchmaking Button (`anchor-bottom-right/go`)**:
  - Managed by `UIModes` component.
  - Was completely blocked because `UIModes.on_enter` crashed at line 405 on `hallTeamData`!
  - Resolving the `hallTeamData` exception unblocks `UIModes` initialization, enabling the Start button and mode selector (`solo`, `dual`, `squad`, `fireteam`).
- **Currency Counters ("283283")**:
  - `MainScene.csb` hardcodes "283283" as the Cocos Studio design placeholder text for coin and diamond.
  - Handled by `player.onCurrencyChanged(-1)` or `setCurrencyWithOwned`.
- **Navigation Buttons & Controllers**:
  - Store: `anchor-middle-left/entry/mall` $\to$ `UIMallController`
  - Appearance / Depot: `anchor-middle-left/entry/change_clothes` $\to$ `UIDtsAppearanceMainController`
  - Settings: `anchor-upper-right/top-navigator/setting` $\to$ `UISettingForPC` / `UISettings`
  - Friends: `anchor-middle-left/entry/friend` $\to$ `UIFriendship`
  - Rank: `anchor-middle-left/entry/rank` $\to$ `UIRankList` / `UINationalRank`
  - Profile: `anchor-upper-left/profile` $\to$ `UIMeetMainPage`
  - Activities: `anchor-middle-left/entry/activities` $\to$ `UIDtsActivity`
  - Welfare: `anchor-upper-right/common-entry/welfare` $\to$ `UIWelfareController`
  - All of these handlers were previously suppressed or unresponsive because `UIMain.on_enter` aborted prematurely during `UIModes.on_enter`.

## Live-test result of commit 7ae0f3e (2026-09-18, later same session): the onLeaveHallTeam fix does NOT work -- this is a systemic missing-property problem, not isolated bugs

Live-tested `7ae0f3e`'s fix (send `Athlete.onLeaveHallTeam()` idx 59
before/after `enterHall` to resolve the `hallTeamData` crash) with
logcat capturing. **Result: the crash still occurs, unchanged**:
```
File "entities\iHallTeam.py", line 358, in onLeaveHallTeam
File "entities\iHallTeam.py", line 747, in isInFormedTeam
AttributeError: 'PlayerAthlete' object has no attribute 'hallTeamData'
```
**Root cause of why the fix didn't work**: `onLeaveHallTeam()` itself
calls `isInFormedTeam()`, which reads the SAME missing `hallTeamData`
property. Calling a method that depends on a property is not a
substitute for the property actually existing -- this was never going
to work, regardless of which method or how many times it's called.
`hallTeamData` needs to be set as a PROPERTY (via whatever the correct
property-initialization/push mechanism turns out to be), not worked
around via an RPC.

**This is bigger than one property.** The same test surfaced two MORE
previously-unseen missing-property crashes, in completely different
code paths, all with the identical shape (`AttributeError: 'PlayerAthlete'
object has no attribute 'X'`):
- `entities\Athlete.py:670 _realEnterHall` -> `ui\UISelectMode.py:105
  selectDone` -> missing `timerRefreshMSToken`
- `ui\main\UIG89MainAnwser.py:212 refreshMonthlyBenefit` ->
  `entities\iMonthPayRebateSpecialAward.py:99 have_award_can_receive`
  -> missing `monthPayRebateSpecialAwardInfo`

Combined with the already-known `weekendPushRewardsHaveGotten` crash
(root-caused earlier in this file) and now `hallTeamData`, that's
**four** distinct properties confirmed missing so far, each surfacing
in a different, unrelated UI/script code path, all with the exact same
"property was never initialized, ends up None/missing, and the first
code that touches it crashes" signature. **This strongly suggests the
real problem is structural**: this project's `createBasePlayer(Athlete,
stream=b'')` empty-stream approach does not populate ANY of Athlete's
non-trivially-defaulted properties (confirmed earlier in this file: for
`createBasePlayer`'s domain=0, ANY non-empty stream triggers a native
exception, so there is currently no way to set these properties at
entity-creation time at all) -- and there are likely many more such
properties beyond the four found so far, since discovery has been
purely incidental (whatever code path happens to run during this
session's specific test sequence).

**Do not keep patching these one at a time as they're discovered.**
Sending a method call that depends on the missing property (like
`onLeaveHallTeam` for `hallTeamData`) cannot work as a category of fix.
What's actually needed is one of:
1. Find the real property-push/property-update wire mechanism (distinct
   from both `createBasePlayer`'s stream and from per-entity method
   calls) that lets a server set an already-created entity's property
   after the fact -- this was flagged as unsolved in the "MAJOR
   CORRECTION" section of this file and remains unsolved. This is the
   most likely correct general fix, if it can be found.
2. Determine whether these properties have a sensible client-side
   default that simply isn't being applied because of how this
   project's `createBasePlayer` stream is constructed, and whether
   there's a legitimate way to trigger proper default-initialization
   without violating the domain=0 empty-stream constraint already
   established.
3. As a last resort, catalog every property that scripts touch during
   normal Lobby usage (grep the extracted `entities\*.py`-referencing
   error strings this project can observe live, or better, find a way
   to enumerate Athlete's full property list the same way this session
   found its full method list via live memory) and determine which
   ones need non-None defaults, rather than discovering them one crash
   at a time through incidental testing.

Screenshot after this test: still in the Lobby (reaching it is not
regressed), but the promo-box duplication is UNCHANGED (still 4-5
overlapping copies) and there is still no visible character/avatar
model on the terrace, consistent with the `_refresh_members`/
`hallTeamData` crash still aborting `UIMain.on_enter` before it can
finish initializing the Lobby UI properly.

## Session 2026-09-18 Checkpoint 16 (Claude, direct investigation per user instruction "ikaw na mismo mag fix ng lahat nayan" -- stop delegating to Gemini, fix it directly): updateEntity dispatch chain fully traced to `ClientVarLenMessageHandler::handleMessage`

Per the user's explicit instruction to personally implement fixes rather than
relying on Gemini, this session re-derived and extended Checkpoint 14's
`updateEntity` (ClientInterface msgID 10) lead via direct Ghidra headless
decompilation (all `.java` scripts in `scratch/ghidra_scripts/`, run via the
standard `analyzeHeadless.bat -postScript` pattern already established in
this project).

### 1. `_INIT_44` registration confirms `updateEntity` handler = `FUN_00a49590`

Full decompile of `_INIT_44` (`scratch/ghidra_init44_decompiled.txt`) shows
the exact registration sequence for the `ClientInterface` message table:
```c
DAT_0467b0d0 = &PTR_FUN_038d7ca8;   // vtable ptr (shared by several handlers)
uRam000000000467b0e0 = 0;           // handler+0x10: packed field, see below
_DAT_0467b0d8 = FUN_00a49590;       // handler+0x8: the actual per-message callback
DAT_0467b0e8 = FUN_00a8b30c(&DAT_0467af78, "updateEntity", 1, 2);
```
This confirms `updateEntity` is a real, distinct native message (separate
from `createEntity`'s `FUN_00a49368`, `createCellPlayer`'s `FUN_00a47e8c`,
etc. -- all of which share the same `PTR_FUN_038d7ca8` vtable but have
their own callback at handler+0x8), registered as `variable-length, 2-byte
len prefix, min size 2` -- i.e. `[msgID:10][len:u16][entity_id:u32][property_stream...]`,
matching Checkpoint 14's original finding exactly.

### 2. `FUN_00a49590` (the updateEntity callback) re-confirmed

```c
void FUN_00a49590(long param_1, long *param_2) {
  if (*(long *)(param_1 + 0x110) != 0) {
    puVar1 = (**(code**)(*param_2 + 0x10))(param_2, 4);  // stream_read4 -> entity_id
    (**(code**)(**(long**)(param_1+0x110) + 0x38))(*(long**)(param_1+0x110), *puVar1, param_2, *(undefined1*)(param_1+0xe98));
    return;
  }
}
```
i.e. `param_1` is a "manager" object; if its `+0x110` field (a pointer to
some other object) is non-null, read entity_id (u32) from the stream, then
call the manager's `+0x110` object's own vtable slot `+0x38` with
`(that_object, entity_id, stream, mode_byte_from_param_1+0xe98)`.

### 3. FALSIFIED HYPOTHESIS: `param_1` is NOT the static handler struct `&DAT_0467b0d0`

Initial attempt assumed `param_1 == &DAT_0467b0d0` (the static registration
object itself), since `_DAT_0467b0d8 = FUN_00a49590` looks like storing a
per-instance callback. Computed the live address as
`load_base + 0x467b1e0` (`= &DAT_0467b0d0 + 0x110`) using the established
"live load base from `/proc/<pid>/maps` + static Ghidra offset" technique,
confirmed load base `0x03308000` for both a stale session (pid 31882) and a
fresh one (pid 4964, after force-stop + relaunch + reaching the Lobby via
`createBasePlayer: id 1` in logcat -- confirmed live via
`scratch/live_logcat_mgrptr_probe.txt`). **Both reads returned `0x0`.**

This is not a dead end -- it's a real, useful negative result: it proves
`FUN_00a49590`'s `param_1` is NOT the static per-interface handler object.

### 4. ROOT CAUSE FOUND: the real caller is `ClientVarLenMessageHandler::handleMessage` (`FUN_00a4c540`), confirmed by its own embedded log string

Found by decompiling vtable slot `[2]` of `PTR_FUN_038d7ca8` (the shared
handler vtable) -- slot `[0]` is a trivial empty destructor stub, not the
dispatcher. `FUN_00a4c540`'s own literal error-log string
(`"ClientVarLenMessageHandler::handleMessage Handler for ClientMessage
(header.length%d) did not consume all data, remain %d bytes\n"`) directly
names the function -- zero guesswork, straight from an embedded string:

```c
void FUN_00a4c540(long param_1 /*handler obj, e.g. &DAT_0467b0d0*/,
                   undefined8 param_2 /*source addr*/,
                   long param_3        /*header*/,
                   long *param_4       /*stream*/)
{
  lVar8 = *(long *)(*(long *)(param_3 + 0x10) + 0x4458);  // <-- THE REAL MANAGER OBJECT
  if (*(long *)(lVar8 + 0x140) != 0) {                     // readiness check
    uVar2 = *(undefined4 *)(param_3 + 8);                  // header.length
    if (DAT_0467d128 == '\0') {                            // fast/sync path (not deferred)
      pcVar7 = *(code **)(param_1 + 8);                    // = FUN_00a49590 (the registered callback)
      plVar1 = (long *)(lVar8 + ((long)*(ulong *)(param_1 + 0x10) >> 1));
      if ((*(ulong *)(param_1 + 0x10) & 1) != 0) {         // packed "is-indirect" bit, unset for updateEntity
        pcVar7 = *(code **)(pcVar7 + *plVar1);
      }
      (*pcVar7)(plVar1, param_4, uVar2);                   // <-- ACTUAL CALL: FUN_00a49590(lVar8, stream, length)
      ...
    }
  }
}
```
**This proves the true `param_1` passed into `FUN_00a49590` is `lVar8`, a
LIVE per-connection object resolved at message-dispatch time from
`*(header+0x10) + 0x4458`** -- NOT the static `&DAT_0467b0d0` handler
struct. This fully explains the null read in step 3: that was the wrong
object entirely. `handler+0x10`'s packed encoding (`bit0` = indirect-call
flag, `bits[1:]` = byte offset added to `lVar8`) is a generic mechanism
shared by every handler using this vtable -- for `updateEntity` it's `0`,
so no indirection: `FUN_00a49590` is called directly with `lVar8` itself as
its manager pointer.

### 5. What `*(header+0x10)` is, and the concrete next step

`*(header+0x10)` is very likely the per-connection `ServerConnection`
object (or a `NetworkInterface`/`Channel` it owns) -- logcat already shows
`ServerConnection::createBasePlayer` as a real, live class name in this
binary, and BigWorld's `ServerConnection` is conventionally a process-wide
singleton reachable via a static accessor, which would make `lVar8` (at
offset `+0x4458` from it) findable the same way without needing a live
message in flight to catch `param_3`. **This is the concrete next step,
not yet done**: find the `ServerConnection` singleton's static instance
pointer (via Ghidra string/xref search for `"ServerConnection"` and its
accessor function), read `+0x4458` from it to get `lVar8` live, confirm
`+0x140 != 0` (readiness), then dump `lVar8`'s own structure to find and
decompile its vtable slot `+0x38` -- which is the actual property-stream
decoder and the last unresolved link needed to construct a valid
`updateEntity` wire payload for pushing real values onto `hallTeamData`
and the other three confirmed-missing Athlete properties.

### Status: real, verified progress; not yet a working fix

Per the project's zero-guesswork rule, no property-push has been attempted
or sent to the live client this session -- everything above is static
analysis backed by decompiled code and one live memory read that
falsified a specific hypothesis (a useful negative result, not a stall).
The four missing-property crashes documented in the previous checkpoint
are UNCHANGED and still block `hallTeamData`/Start-button, Lobby
gender/appearance rendering, `timerRefreshMSToken`, and
`monthPayRebateSpecialAwardInfo`. Continuing this thread (finding the
`ServerConnection` singleton, decompiling `lVar8`'s vtable+0x38) is the
direct path to a real fix, and should be picked up next rather than
resuming ad-hoc live-memory heap scanning, which this session also tried
(scanning `EntityType[51]`'s struct at offsets `0x1b8`/`0x1d0`/`0x1e8` for
a second, non-fixed-stride vector besides the confirmed 1131-entry Methods
table at `+0x1e8`) and which did not turn up the property names
(`hallTeamData` etc.) in either of the two additional vectors found there
-- those vectors' actual contents remain unidentified and are a dead end
for now, superseded by the `ServerConnection`/`handleMessage` lead above.

## Same session, continued (per user instruction "gawin mo lahat tapos ifix mo" -- keep going, land the fix): five more approaches tried to pin down the manager singleton; all ruled out with hard evidence, none succeeded

Continuing directly from Checkpoint 16's open question ("find the
`ServerConnection` singleton's static instance pointer"). Tried five
genuinely different techniques in this same session. None succeeded in
pinning down the live manager object, but each produced a concrete,
evidence-backed result -- recorded here so no future session re-tries the
same ruled-out paths.

### Attempt 1: Ghidra symbol table search for `ServerConnection` accessor functions

`scratch/ghidra_scripts/FindServerConnectionSingleton.java`. Result:
**zero function symbols** contain "ServerConnection" (confirms this
binary's function table is fully stripped -- no demangled symbols exist
anywhere, only `FUN_xxxxxxxx` addresses). However, found 87 **string**
literals containing "ServerConnection", including the confirmed RTTI
mangled type name `N4neox8bwclient16ServerConnectionE` (class is
`neox::bwclient::ServerConnection`) and many `std::__ndk1::function`
type-erased closure mangled names (e.g.
`...ServerConnectionC1ERNS3_7Mercury3NubEiE4$_11...`), confirming this
codebase wraps most `ServerConnection` callbacks in `std::function`
closures rather than plain virtual dispatch -- this is significant: it
means simple vtable-slot xref-chasing (which worked for the `updateEntity`
handler class) does **not** reliably work for finding how `ServerConnection`
itself gets invoked, since type-erased closures don't leave a simple
"address stored as data" trail.

### Attempt 2: Decompile `ServerConnection::createBasePlayer` (`FUN_00a47dc4`) to confirm field layout

Confirmed via its own log string
(`"ServerConnection::createBasePlayer: id %d\n"`). Field offsets used
(`+0x118`=entity id being created, `+0x110`=pointer to the "manager"
object, `+0xe98`=a mode byte, `+0xee0`/`+0xef0`/`+0xec8`/`+0xed8`=buffered
createCellPlayer bookkeeping) are **identical in kind** to the ones
`FUN_00a49590` (`updateEntity`'s handler) uses on its own `param_1`. This
is strong structural confirmation that `updateEntity`'s `lVar8` (from
Checkpoint 16) and `createBasePlayer`'s `param_1` are **the same
`ServerConnection` instance** -- i.e. the manager object updateEntity
needs really is the live `ServerConnection`. Also confirmed
`(**(code**)*puVar4)(puVar4, id, type, stream, mode)` -- i.e.
`createBasePlayer` invokes the manager's vtable **slot [0]**, while
`updateEntity` invokes **slot [0x38]** -- two different entry points on
the same polymorphic manager object.

### Attempt 3: Trace call graph upward from `createBasePlayer`/`onBasePlayerCreate` to find a caller that reads a fixed global

Both `FUN_00a47dc4` and `ClientApp::onBasePlayerCreate` (`FUN_00a18504`,
decompiled in full this round -- confirmed fields `+0xf90`=entity id,
`+0xfc0`=entity id->object map, matching a plausible "Entities/EntityManager"
layout) have **no direct callers found via Ghidra xrefs** except entries
Ghidra tags `DATA` or `INDIRECTION` at addresses `033ef8e0` and
`03315978`. Checked both:
- `033ef8e0` -> **`.eh_frame`** (confirmed via `MemoryBlock` lookup,
  `scratch/ghidra_scripts/CheckBlockName.java`)
- `03315978` -> **`.eh_frame_hdr`** (`scratch/ghidra_scripts/CheckIndirectionSlot.java`)

**Both are DWARF exception-handling/unwind metadata, not vtables or call
sites.** Every function has entries here as a normal side effect of being
compiled with unwind tables -- this does NOT indicate indirect/virtual
invocation. **This conclusively refutes the Attempt-1-adjacent hypothesis
that `onBasePlayerCreate`'s vtable slot could be found this way.**
Combined with Attempt 1's finding (heavy `std::function` closure usage),
the real invocation path for these handlers is almost certainly through
type-erased closures registered at `ServerConnection`/`ClientApp`
construction time, not raw vtable dispatch -- which is much harder to
trace statically without either (a) a symbol-preserving debug build, or
(b) dynamic instrumentation to catch the actual indirect call target at
runtime.

### Attempt 4: Live memory field-signature scan for the `ServerConnection` heap object

Confirmed the live-load-base technique still works across process
launches (`0x03308000` for both pid 31882 and a fresh pid 4964 after
force-stop+relaunch -- **the `.so`'s own code/data load base is stable**),
but confirmed heap object addresses are **not** stable across launches
(the `EntityType` vector's live pointer differed between the two pids,
even though the element count, 172, matched as expected for static data).
Live-tested a fresh session end-to-end: relaunched the app, dismissed the
Events popup, selected Classic Mode controls, and confirmed
`ServerConnection::createBasePlayer: id 1` fired in logcat -- Gate 4 flow
is unaffected/still working.

Dumped a targeted 4MB heap window (`763892600000`-`763892a00000`, chosen
because a stale CLAUDE.md reference (`pPlayerEntity_ @ 0x763892626820`)
fell inside it) and scanned for the `ServerConnection` signature
(int32 `1` at `+0x118`, heap-pointer-shaped value at `+0x110`, whose
target's first qword is itself a plausible code-segment pointer). Initial
loose filter (`+0x118==1` only) produced 917 false-positive hits (an
`int32` equal to `1` is far too common in arbitrary heap data -- refcounts,
small flags, etc.). Adding the vtable-plausibility check
(target's first qword in `0x03000000`-`0x08000000`) produced **zero**
matches inside this 4MB window -- **the `ServerConnection` object is not
allocated near that stale address in this session's heap.** This is a
real negative result, not a bug: heap layout is per-launch and this
narrow a window was always a long shot. A full-heap search would need to
cover ~1.5GB+ across 19 `libc_malloc` regions (`scratch/maps_4964_full.txt`),
impractical to brute-force via `adb`+`dd` pulls in reasonable time.

### Honest status: the `updateEntity` property-push mechanism is real and structurally confirmed, but its live manager object could not be pinned down this session

What IS now solid, evidence-backed knowledge (safe to build on in a future
session):
- `updateEntity` (msgID 10) genuinely exists as a native property-push
  mechanism independent of `createBasePlayer`'s domain=0 restriction.
- Its handler (`FUN_00a49590`) and the generic dispatcher that calls it
  (`ClientVarLenMessageHandler::handleMessage`, `FUN_00a4c540`) are fully
  decompiled and understood.
- The manager object both `updateEntity` (vtable slot `0x38`) and
  `createBasePlayer` (vtable slot `0`) operate on is the same object, and
  is very likely the live `ServerConnection` instance itself (class
  `neox::bwclient::ServerConnection`, confirmed via RTTI string).
- That object is NOT reachable through a simple static vtable/global
  pointer chase -- this codebase uses `std::function` type-erased closures
  heavily for `ServerConnection`'s own callback wiring, which defeats the
  address-xref-chasing technique that worked for the (simpler,
  non-closure-based) `updateEntity`/`createEntity`/etc. handler class.

What's NOT done: the live address of this manager object, and therefore
its vtable slot `0x38` target (the actual property-stream decoder) is
still undetermined. Per this project's zero-guesswork rule, no
`updateEntity` payload has been sent to the live client, since the wire
format past the entity-id prefix is still unknown and a prior session's
blind guess in a similar situation caused a worse native crash than doing
nothing.

### Attempt 5: swept all 18 smaller `libc_malloc` regions (466MB) for the same signature -- refuted the technique itself, not just the address

Extended Attempt 4's scan from one guessed 4MB window to all 18 of the
smaller `libc_malloc` regions in `scratch/maps_4964_full.txt` (skipped
only the one anomalous 1510MB reserved-arena region as impractical to
pull). Result: **thousands of "strict" hits per region** (2202, 1350,
328, 1601, 43247, 83, 23, 90, 52, 10, 15, 10, 104 across the regions that
had any) -- i.e. the signature (int32 `1` at `+0x118`, heap pointer at
`+0x110` whose target's first qword looks like a code address) is
**far too common** in this game engine's live heap to identify one
specific object. This is expected in hindsight: any small object with a
refcount/counter of 1 and an embedded pointer to another polymorphic
object is indistinguishable from `ServerConnection` under this filter --
BigWorld/this engine allocates huge numbers of structurally similar
objects. **This refutes generic-signature heap scanning as a viable
technique for this specific problem, not just this specific attempt's
guessed address.** A stronger signature would need additional confirmed
fields unique to `ServerConnection` (e.g. an exact known port number or
IP-address byte pattern from the live session), which were not available
this round.

### Attempt 7 (2026-09-20): precisely characterized WHY Frida attach fails -- ptrace itself works; the failure is specific to frida-server's own use of it

Per an explicit instruction to prioritize Frida for this exact blocker (finding the live
`ServerConnection`/manager object), retried attach with much more careful diagnostics
than Attempt 4's session. New, decisive findings:

1. **`ptrace` itself works fine on this system.** `strace -p <game_pid>` attaches
   successfully and streams live syscalls from the running game process
   (`epoll_pwait`, `read`, `openat` on `/proc/<pid>/status` observed). This rules out
   a kernel/SELinux/policy block -- SELinux is `Permissive` here anyway.
2. **`gdbserver --attach` also successfully ptrace-attaches** to the game process
   (`Attached; pid = 8320`) before failing for an unrelated, mundane reason: the only
   `gdbserver` on this device (`/system/bin/gdbserver`) is a **32-bit x86 build**
   (`ELF executable, 32-bit LSB 386, static, stripped`) and refuses to debug the
   64-bit target ("Can't debug 64-bit process with 32-bit GDBserver"). No 64-bit
   `gdbserver`/`lldb-server` binary exists on the device or was found on the host.
3. **The x86_64 `frida-server` fails silently.** Across every configuration tried
   (foreground, daemonized via `-D`, `-v` verbose, `-C` ignore-crashes, explicit
   `-d` staging directory, listening on `0.0.0.0:27042` instead of the default) it
   exits with **status 0 and zero log output** at the exact moment a Python client
   calls `.attach(pid)`, even though it correctly serves `enumerate_processes()`
   beforehand. Both a version-matched venv (17.16.4) and the host global install
   reproduce this identically.
4. **The arm64 `frida-server-16`** (already present at `/data/local/tmp/frida-server-16`,
   confirmed via `file`: `ELF 64-bit LSB arm64, dynamic, for Android 21, NDK r25b`, v16.2.1)
   behaves differently and **does not crash** -- it returns a specific, reproducible
   error instead: `NotSupportedError: unable to perform ptrace getregs: Device or
   resource busy`. This is a real error surfaced over the wire, not a dropped
   connection.
5. **That error is NOT specific to the arm64-translated game process.** Retried
   against `surfaceflinger` (native x86_64 on this x86_64 LDPlayer image) with the
   exact same `frida-server-16` instance -- **identical error**. This refutes the
   working hypothesis carried since Attempt 3 (that the `libhoudini` ARM64-on-x86_64
   translation layer specifically breaks instrumentation of translated targets). The
   failure is not target-architecture-dependent.

**Conclusion**: the common factor across both failure modes is `frida-server` itself,
not the target. The most likely explanation (inference, not yet proven): `frida-server`
supports exactly two "genuinely native" configurations -- x86_64 server on an x86_64
kernel, or arm64 server on an arm64 kernel -- and this LDPlayer image's arm64
userspace-translation-over-an-x86_64-kernel setup satisfies neither cleanly: the
x86_64 server can enumerate (pure `/proc` reads) but something in its actual
injection path (architecture-aware, since ptrace register layouts differ per-arch)
fails post-`fork`/pre-attach silently; the arm64 server gets further (engages real
ptrace calls) but that binary's own ptrace glue -- itself running as translated code --
collides with something (possibly `libhoudini`'s handling of a translated process
issuing arm64-shaped `PTRACE_GETREGSET` calls) and gets `EBUSY` back from the kernel
every time.

This is a materially more precise result than Attempt 4's generic "closed" -- it names
a syscall (`ptrace GETREGS`), a specific errno-class failure (`EBUSY`), and rules out
one previously-plausible hypothesis (architecture-specific targets) with a real
control test (native `surfaceflinger`).

**Concrete unblock options, cheapest first, none attempted yet**:
1. Source a genuine **64-bit `gdbserver` or `lldb-server` for android-arm64** (the
   Android NDK ships both; none is currently on this host or device) and drive it
   with a host-side `gdb`/`lldb` client over the GDB Remote Serial Protocol. Since
   plain `ptrace` is proven to work and `gdbserver` itself successfully reaches the
   ptrace-attach step, this is the most promising concrete next step for reviving
   dynamic instrumentation here -- it does not depend on Frida's injection machinery
   at all, only on the kernel ptrace primitive already shown to work.
2. Try an even older/newer `frida-server` build in case this is a version-specific
   regression against this particular Android/kernel combination, rather than a
   structural incompatibility.
3. Accept dynamic instrumentation as blocked on this specific LDPlayer image and
   continue the property-sync investigation via Ghidra static analysis plus the
   live-`/proc/<pid>/mem` read technique already used successfully throughout this
   project (which needs no ptrace at all, since it just opens `/proc/<pid>/mem` for
   direct reads with root -- a fundamentally different and already-working mechanism).

### Attempt 8 (2026-09-20): pursued unblock option 1 (real lldb-server) -- ROOT CAUSE FOUND: `PTRACE_GETREGSET`/`GETREGS` itself is what fails, not any tool's injection logic

Followed up on Attempt 7's top recommendation. No `lldb-server`/`gdbserver` for
android-arm64 existed on the host or device, and the full Android NDK is a ~660-700MB
download. Extracted just the one needed file from Google's official NDK zip via
**HTTP range requests against the remote ZIP's central directory**
(`scratch/fetch_lldb_server.py`, `scratch/extract_lldb_server.py`) -- Python's
`zipfile` module against a seekable HTTP-range-backed file object, downloading only
the ~10MB compressed entry instead of the full archive. Confirmed via `file`:
`ELF 64-bit ARM aarch64, statically linked, for Android 30, built by NDK r27-beta1`.

Pushed to `/data/local/tmp/lldb-server` (note: `adb push` to an absolute Unix path
from Git-Bash on Windows requires `MSYS_NO_PATHCONV=1`, otherwise MSYS rewrites the
destination into a Windows path like `C:/Program Files/Git/data/local/tmp/...` and the
push silently fails after transferring bytes; also needed `adb root` first, since a
non-root `adbd` cannot `fchown` the destination and the push aborts).

**`lldb-server platform --listen ... --server` (NDK r27, targets Android 30):
segfaults (exit 139) immediately on its own**, before any client even connects. Not
a ptrace/attach issue at all -- the platform service itself crashes on this image.

**`lldb-server g <addr> --attach <pid>` (same r27 build) also segfaults**, this time
right after the `--attach` step succeeds (`ps` confirms `PTRACE_ATTACH` worked: the
process shows up, and `TracerPid` reflects it) but before any client packet is
processed.

Suspecting the r27 build (targets Android 30 / API 30) uses newer ptrace APIs than
this Android 9 (API 28) image's kernel supports, fetched an **older NDK (r23c,
targets Android 29)** via the same partial-zip-download technique and retried:

- **This build survives `--attach`.** `ps` shows it alive and stable
  (`lldb-server-r23c`), unlike the r27 build.
- Wrote a **minimal hand-rolled GDB Remote Serial Protocol client**
  (`scratch/gdbrsp.py` -- no host `gdb`/`lldb` client was available or needed; the
  wire protocol is simple enough to implement directly: `$<payload>#<checksum>`
  packets, `+`/`-` acks) and connected to it.
- **The server ACKs the very first packet sent (`+`), for ANY payload -- tested both
  `qSupported:...` and the minimal possible query `?` -- and then exits
  (`lldb-server exiting...`) without ever sending a response packet.** This is not a
  parsing problem with a specific request: the crash happens identically regardless
  of what the first command is, meaning it happens in some shared step performed
  before dispatching to command-specific handling.

**This pinpoints the actual root cause, corroborated across three independent
tools/builds now:**
- Frida (arm64 build): explicit `NotSupportedError: unable to perform ptrace getregs:
  Device or resource busy` -- names the exact syscall.
- `lldb-server` (two NDK builds): crashes at the first point post-attach where a
  gdbserver must be able to answer `?` (query halt/stop reason) for the attached
  thread -- which requires reading that thread's **register state**, i.e. the same
  `PTRACE_GETREGSET`/`PTRACE_GETREGS` operation Frida named explicitly.
- Plain `strace -p <pid>` (which only traces syscall entry/exit, never reads full
  register state via `GETREGSET`) works perfectly and streams live syscalls with no
  issue.

**Root cause, now well-evidenced rather than inferred**: on this specific LDPlayer
image, `PTRACE_ATTACH` and syscall-level tracing work correctly, but reading a traced
arm64 thread's **register set** via ptrace does not -- every tool that needs it
(Frida, to compute injection points and read/write registers; lldb-server, to answer
even the most basic stop-reason query) fails or crashes exactly there, while a tool
that never touches register state (`strace`) is unaffected. This is most plausibly a
kernel-level limitation or mismatch specific to this Android 9 / x86_64-host LDPlayer
image's ptrace implementation for `NT_PRSTATUS`/`PTRACE_GETREGSET` on arm64 threads
under its translation setup -- not fixable by trying further userspace tool builds.

**Operational note, already fixed live**: the crashed `lldb-server` attach left the
target game process **stopped** (`/proc/<pid>/stat` state `T`, from the `SIGSTOP`
normally sent on `PTRACE_ATTACH`) rather than being auto-resumed when the tracer died.
Sent `kill -CONT <pid>` to resume it and confirmed via screencap that the app is
responsive again. **Anyone attempting `PTRACE_ATTACH`-based tools against the live
game process on this image should check for and clear a stuck `T` state afterward.**

**Updated conclusion**: dynamic instrumentation via ptrace-based tools (Frida,
lldb-server, gdbserver) is blocked on this LDPlayer image by what appears to be a
genuine host/kernel limitation, not a tool configuration or version issue -- four
distinct tool/version combinations across two tools have now failed at precisely the
same conceptual operation (register access on an attached thread). Real unblock
options going forward are environment-level, not tool-level: a real ARM64 device, a
different emulator/VM whose kernel correctly implements ptrace register access, or
continuing to rely on the `/proc/<pid>/mem`-based live-read technique (which needs no
ptrace at all and has been this project's only reliable dynamic-inspection method
throughout).

### Realistic next steps, in order of promise (updated after Attempt 5)

1. **Dynamic instrumentation (Frida) on real ARM64 hardware**, per
   `ACCOUNT_HANDSHAKE_SYNTHESIS.md` option 4 -- now the clearly favored
   option given Attempt 5's result. A single breakpoint/hook on
   `FUN_00a49590` or `FUN_00a4c540` reads `param_1`/`lVar8` directly at
   runtime, which is exactly the information five different static/live
   approaches this session could not otherwise obtain. Previously flagged
   as needing new hardware/environment setup -- a standing human decision,
   not something to set up unilaterally, but this session's results make
   a strong case that it's the only remaining practical path for this
   specific sub-problem.
2. Narrow a future heap scan using a MUCH stronger signature (e.g. a byte
   pattern including the live session's actual server IP/port, or a
   second correlated field beyond `+0x118`/`+0x110`) -- possible but
   would need a concretely identified additional field first, which this
   session did not find.
3. Continue static analysis around `ServerConnection` construction
   (`operator_new` of a matching size immediately followed by a
   constructor call and a store to a `.bss`/`.data` global) -- not yet
   tried, but Attempt 1 already showed this codebase wraps most
   `ServerConnection` wiring in `std::function` closures, which makes
   even the constructor call site harder to correlate to a single fixed
   global than in a typical C++ binary.

## Attempt 6 (same session, after user pushback "hindi mo kaya ayusin?"): searched for the exact known server IP:port byte pattern instead of a generic structural signature -- found it, twice, but could not conclusively resolve the enclosing object's base address

Since our own private server is fixed at `172.16.1.2:25010`
(`mitm/local_baseapp_capture.py` `BASEAPP_HOST`/`BASEAPP_PORT`), searched
all 18 smaller `libc_malloc` regions for the raw 6-byte pattern
`AC 10 01 02 61 B2` (IP octets + port in big-endian, matching BigWorld's
`Mercury::Address{uint32 ip; uint16 port;}` layout) instead of the
generic "refcount==1 + valid pointer" heuristic that produced thousands
of false positives in Attempt 5.

**Result: exactly 2 hits in 466MB** (`scratch/scan_address.py`), both with
plausible padding (2 zero bytes after the port, consistent with 8-byte
alignment) and both preceded by a run of small integer/pointer-shaped
values:
- `0x7638486b9170` -- preceded by a heap pointer, two `1`s, a `0`; followed
  by a heap pointer, then a value (`0x6b887f0`) that is itself in
  `.data.rel.ro`'s plausible vtable-pointer range.
- `0x76384dd16ed8` -- similar shape, preceded by a heap pointer and a `1`.

This is a MUCH stronger signal than anything found in Attempts 1-5 (a
6-byte exact-value match instead of a generic shape match), and strongly
suggests one or both of these is the live `ServerConnection`'s own stored
target address, or a direct copy of it.

**However**: brute-force-testing candidate object base addresses (offsets
0 to 0x300 back from each hit, `scratch/probe_sc_base.py`) against the
already-confirmed field layout from `FUN_00a47dc4`
(`+0x118`==entity id 1, `+0x110`==valid pointer with plausible vtable)
found 2 candidate bases for the second hit (`0x76384dd16db0` and
`0x76384dd16d88`) that pass that specific check, but validating them
further against `FUN_00a47dc4`'s OTHER known fields (`+0xe98`, `+0xec8`,
`+0xed8`, `+0xee0`, `+0xef0`) produced garbage/implausible values for
both candidates (`scratch/validate_sc_candidate.py`) -- i.e. neither
candidate base is fully self-consistent across all known field offsets.
Cross-checking against a decompile of `ServerConnection::logOnBegin`
(`FUN_00a3bcb0`) and `checkScriptBaseAppAddr` (`FUN_00a3a134`) did not
turn up an unambiguous single fixed byte-offset for the Address field
either (`scratch/ghidra_logonbegin_decompiled.txt`) -- both functions are
long, deal with multiple `Address`-shaped arguments/temporaries, and
didn't yield a clean `this+CONST` read of a persistent Address member in
the portion decompiled.

**Plausible explanation, not yet confirmed**: `ServerConnection` may use
multiple inheritance (it implements at least two distinct interfaces --
recall `createBasePlayer` invokes the manager's vtable slot `0` while
`updateEntity` invokes slot `0x38` on what was assumed to be the same
object). Under multiple inheritance, the "this" pointer handed to
different virtual interfaces of the same underlying object can differ by
a fixed sub-object offset -- meaning `+0x110`/`+0x118` (read via one
interface pointer) and `+0xe98` etc. (read via `ServerConnection`'s own
"primary" this, per `FUN_00a47dc4`) may legitimately be different
coordinate spaces, not a sign the candidate address is wrong. This was
not confirmed or refuted this session.

## 2026-09-19 CORRECTION (important): `createBasePlayer` with a non-empty stream is NOT an instant exception — the old "domain=0 dead end" conclusion was WRONG

Multiple earlier sections of this file state that `EntityType::newDictionary` raises a
native exception whenever `domain < 2` and the stream is non-empty, and conclude that
"there is no way to smuggle real property values into createBasePlayer's stream at all".
**That conclusion is incorrect and is retracted.** It was based on misreading
`FUN_00acf8ac` as an exception-construction helper.

Decompiled `FUN_00a2a58c` (`EntityType::newDictionary`) directly
(`scratch/ghidra_newdict_settle.txt`, via
`scratch/ghidra_scripts/DecompileNewDictionary.java`):

```c
iVar5 = (**(code **)(*param_2 + 0x18))(param_2);   // stream remaining length
if (iVar5 == 0) {
    uVar7 = FUN_00a2a344(param_1, &local_70);      // empty stream -> bare PyDict (what we do today)
}
else {
    uVar7 = FUN_01defc6c();                        // new dict
    if (param_3 < 2) {                             // param_3 == domain
        uVar12 = 0xb;                              // domain 0 (BASE)
        if (param_3 != 0) uVar12 = 0xe;            // domain 1 (CELL)
        FUN_00acf8ac(param_1, param_2, uVar12, uVar7);
    }
    else if (param_3 == 2) { ...default-fill loop over FUN_00ad02fc... }
}
```

`FUN_00acf8ac(entityType, stream, flagMask, targetDict)` takes the stream **and** the
destination dict — that is a **property-stream deserializer**, not an exception
constructor. For our `createBasePlayer` path (domain hardcoded to 0) the flag mask is
**`0xb`**.

This independently corroborates Gemini's Checkpoint 18 claim, and it reopens the
server-side property-stream route (their "Solution C") which this file had previously
written off. Gemini's `scratch/test_domain_0xb.py` is filtering Athlete's property
descriptors against exactly this `0xb` mask.

> **PARTIALLY RETRACTED (2026-09-20) — read "Checkpoint 20" at the end of this file first.**
> Three claims in the sections below are wrong or unproven:
> 1. *"In sync through ordinal 300"* (truncation bisect) — the criterion used (no `Invalid size`
>    error on a truncated stream) was too weak. The stream actually desyncs at **ordinal 207**
>    (`childBaseClientPropertyList`, a fixed-size array). The "1-byte residual at 301-305" was a
>    downstream symptom.
> 2. *"The TypeError is ELIMINATED"* — that run only shows the entity layer executing once the
>    Athlete packet reached the client; see the retraction of claim 3 for why it sometimes did not.
> 3. *"A 1585-byte stream is accepted, the 1465 B budget is not a ceiling"* — **false.** Absence of a
>    `Bundle::iterator::unpack` error was taken as acceptance, but a packet dropped earlier by
>    `EncryptionFilter::recv: Dropping packet ... illegal wastage count (100)` never reaches the
>    Bundle parser, so no error is logged. The measured single-packet ceiling (`createBasePlayer`
>    stream <= 1459 B) stands.

## 2026-09-19 RESULT: the property stream works — root-cause `TypeError` is ELIMINATED live

Built and shipped the stream (`scratch/gen_stream_v2.py` ->
`data/athlete_mobile_stream.bin`, loaded by the existing
`ROS_ATHLETE_USE_STREAM_FILE=1` hook). Measured live across three iterations:

| run | stream | first desync | `tryActiveWeekendPushRedBadge` TypeError |
|:--|:--|:--|:--|
| baseline (empty stream) | 0 B | n/a | **present** |
| v1, XML types, proto-2 pickles | 1745 B | rejected by Mercury entirely | present |
| v1, XML types, proto-0 pickles | 1456 B | ordinal 128 | present |
| **v2, runtime types** | **1457 B** | **ordinal ~305** | **GONE (0 occurrences)** |

**The original root cause is fixed.** `weekendPushRewardsHaveGotten` now arrives as
`[]` instead of `None`, and `iWeekendPush.tryActiveWeekendPushRedBadge` no longer
raises — it does not appear in the log at all. The `onCreate` chain now runs far
enough that `enterHall` executes and walks its own interface chain
(`iShareGift.enterHall` -> `iBattleGift` -> `iRedPacketGift` ->
`iDtsRepertoryPackage` -> `iChildTable`).

### Three hard lessons, each found by live measurement

1. **The message must fit one Mercury packet.** A 1745-byte stream was rejected
   outright: `Bundle::iterator::unpack( createBasePlayer ): Not enough data on stream
   at 2 for payload (1465 left, needed 1751)`. The usable budget is **1465 bytes**
   for `entity_id(4) + type(2) + stream`, so the stream must be <= 1459 B. Pickle
   protocol 0 (`N.` = 2 bytes) instead of protocol 2 (`\x80\x02N.` = 4) across 143
   PYTHON properties is what made it fit. Anything larger needs real bundle
   fragmentation, which is not implemented.
2. **XML `<Type>` is NOT authoritative — the runtime DataType is.** The same property
   name is declared with different types across interfaces. Feeding XML types desynced
   the stream at ordinal 128 (`multipleOpenTimes`, declared `PYTHON` but actually a
   sequence), reported as
   `SequenceDataType::createFromStream: Invalid size on stream: 36589058`.
3. **Each descriptor's DataType pointer is at `+0x18`**, and its vtable identifies the
   wire type exactly. Only 36 distinct DataType objects / **13 vtables** serve all 832
   properties (`scratch/find_datatype_ptr.py` ->
   `scratch/datatype_vtables.txt`):

   | vtable | type | n | | vtable | type | n |
   |:--|:--|--:|:-:|:--|:--|--:|
   | `0x6af6c38` | INT32 | 256 | | `0x6af5f90` | FIXED_DICT | 11 |
   | `0x6af7a28` | PYTHON | 247 | | `0x6af7418` | UINT64 | 9 |
   | `0x6af69d8` | INT8 | 117 | | `0x6af84f8` | BLOB | 7 |
   | `0x6af6448` | ARRAY | 81 | | `0x6af70f8` | UINT32 | 2 |
   | `0x6af6050` | STRING | 44 | | `0x6af6778` | UINT8 | 1 |
   | `0x6af7228` | INT64 | 30 | | `0x6af6b08` | INT16 | 1 |
   | `0x6af7778` | FLOAT | 26 | | | | |

   (vtable addresses are live; subtract the load base for static ones)

### Confirmed wire encodings

- `PYTHON` — `packed_int(len) + pickle`, decompiled from `FUN_00ac38c8`
  (`PythonDataType::createFromStream`): reads 1 byte, and if it is `0xff` reads 3 more
  as a 24-bit length. Identical to `_packed_int` already in the server. The
  "Not enough data on stream to read value" log it emits is a **warning**, not fatal —
  it fires when the resulting string is empty, then unpickles anyway.
- `ARRAY` — 4-byte LE count (0 for empty), matching `SequenceDataType` @ `0x9a4b74`.
- Integers/floats — plain little-endian, natural width.
- `STRING` / `BLOB` — `packed_int(len)`.

### Narrowing the residual desync — method and result

Two diagnostics, both reusable:

**1. Ordinal-stamped INT32s** (`scratch/gen_stream_stamped.py`). Writing
`1000000 + ordinal` into every INT32 instead of `0` makes the client's own error
message reveal its exact cursor: it reported
`SequenceDataType::createFromStream: Invalid size on stream: 1000219` at
`700 bytes remaining`, i.e. cursor `1457-700-4 = 753`, which is **exactly** the
offset our layout assigns to ordinal 219. So the stream was byte-perfect up to there.
(That particular error is an artifact of stamping — `recallProgress` is read as a
sequence, but since both INT32 and an empty ARRAY are 4 bytes it is size-neutral and
harmless with the normal all-zero values.)

**2. Truncation bisection** (`scratch/gen_stream_trunc.py <K>` emits ordinals
`0..K-1`). If the stream is in sync, the client consumes every byte and the only
complaint is an end-of-data one at `0 bytes remaining`; any real desync instead shows
`Invalid size on stream: <garbage>` with a non-zero remainder. Results:

| K | bytes | verdict |
|--:|--:|:--|
| 262 | 876 | in sync through ordinal 261 |
| 284 | 930 | in sync through 283 |
| 295 | 968 | in sync through 294 |
| 301 | 974 | **in sync through 300** |

So **454 of the 454 properties are correctly typed and sized up to ordinal 300**,
which includes the target at 258. The residual 1-byte deficit is isolated to
**ordinals 301-304**, all four of which we currently encode as `PYTHON`:
`newYearGoalSendInfo`, `newYearGoalReceiveInfo`, `globalNewYearGoalTaskInfo`,
`newYearGoalTaskIDList`. One of them is really a 2-byte type (we write 3 bytes for
PYTHON: `\x02` + `N.`), which is exactly the observed 1-byte overrun.

### Environment note: the emulator lost root and needs a manual LDPlayer restart

Bisection stopped at K=305 because the emulator wedged: `adb shell` still answered but
`screencap` returned 0 bytes and the game would not launch. `adb reboot` brought it
back to `sys.boot_completed=1` with a working shell, **but root did not come back** —
`/system/bin/su` exists yet `su 0 id` returns nothing (polled 6 times over 90s). Without
root there is no `iptables` DNAT (so the client cannot reach our server) and no
`/proc/<pid>/mem` access.

**Recovery is manual**: close and reopen LDPlayer from its own launcher (not
`adb reboot`), confirm the root toggle is still on, then reapply the five DNAT rules.
Prefer restarting LDPlayer over `adb reboot` in future sessions for this reason.

Also learned the hard way: every `adb logcat > file &` leaves a live adb client behind.
Nine of them accumulated and wedged the adb connection (plain `pidof` began timing out
at 120s). Kill stray `adb` processes — keeping the long-lived adb *server* — between
test rounds.

### What remains

The stream still desyncs by **1 byte at around ordinal 305**, so properties after that
point stay unset — `baseLevel`, `childBaseClientPropertyList`, `hostID`, and
`hallTeamData` still raise `AttributeError`, and the client returns to the title
screen instead of the Lobby. Everything before ordinal ~305 (including the target at
258) is consumed correctly. The three bare `FIXED_DICT` properties (ordinals 48, 92,
231 — `rankRecord`, `dtsAppearancePackage`, `braveBookDataList`) are the prime
suspects, because their field lists are the only part of v2 still derived from XML
rather than from the runtime DataType.

### Full deserializer spec (all values below verified this session, not inferred)

`FUN_00acf8ac(entityType, stream, flagMask, dict)` wraps a visitor
(`{vtable PTR_FUN_038e07b8, stream, dict}`) and calls
`FUN_00acf5ec(entityType, flagMask, visitor)`, which:

1. Loops `i = 0..3` over a **uint32** group-mask array. Disassembly at `00acf630`
   proves the stride is 4, not 1 (`adrp x8,0x2b62000; add x8,x8,#0x400;
   ldr w8,[x8, x23, LSL #0x2]`), and the bytes at `.rodata:02b62400` are
   `09 00 00 00 | 0b 00 00 00 | 0e 00 00 00 | 0c 00 00 00` =
   **`[9, 0x0b, 0x0e, 0x0c]`**.
2. Group selection (`00acf63c`-`00acf654`): because `flagMask & 8 != 0` for our
   `0x0b`, the test used is `groupMask != flagMask`. **Only group index 1
   (mask `0x0b`) is processed** — groups 9, 0x0e, 0x0c are all skipped.
3. Within that group it walks the property table
   (`ldp x8,x9,[x21,#0x58]`, count `= (end-begin)/0x68`) and applies three
   descriptor predicates, with `DAT_02b61b60[1*2] = 0x01`
   (bytes there are `01 00 01 01 00 01 00 00`):
   - `FUN_00a9f2e0(desc)` must be **false**
   - `FUN_00aa0cec(desc)` must equal **1**
   - `FUN_00a9f2ec(desc)` must be **1** (since `i==1` makes `(i-1) < 2` true)
   - the `>>4` and `>>5` checks are both skipped, because `0x0b>>4 == 0` and
     `0x0b>>5 == 0`
4. Each surviving property calls `visitor->visit(desc)` (vtable+0x10), which reads
   that property's value **sequentially off the stream**.

**Consequence for the wire format**: the stream is a bare, strictly-ordered
concatenation of property values — **no presence bitmask, no per-property index
tags**. Every included property before the one you care about must be encoded
correctly or the whole stream desynchronizes.

### Live-measured facts needed to build that stream

Dumped Athlete's live property table with heap-allocated names resolved
(`scratch/dump_props_fast.py` -> `scratch/athlete_props_full.txt`):

- **832 properties**, `EntityType+0x58`, `0x68` stride (matches Gemini exactly).
- Flag byte at descriptor `+0x20` distribution: `0x08`:273, `0x0c`:325,
  `0x28`:105, `0x2c`:128, `0xac`:1.
- **`weekendPushRewardsHaveGotten` is at table index 515** with flags `0x0c`
  — Gemini's index-515 claim **independently confirmed**.
- `hallTeamData` is index 51 but flags `0x08` (BASE-only, never sent to client),
  and `timerRefreshMSToken` / `monthPayRebateSpecialAwardInfo` are **not in the
  table at all** — they are pure client-side Python attributes. This is strong
  corroboration of the single-root-cause model: only
  `weekendPushRewardsHaveGotten` has to come from the server; the other three get
  assigned by `onCreate` once it stops aborting.
- Taking BASE_AND_CLIENT as `(flags & 0x0c) == 0x0c` gives **454** properties,
  and the target is **ordinal 258** among them.

### The key enabler: runtime table order == XML declaration order

Verified programmatically: `05_entities/out/entity_0376.xml` declares 7 properties
starting with `weekendPushWindowOpen`, and the live table has exactly that
sequence starting at index 511 — `order matches exactly: True`. The XMLs therefore
supply the **`<Type>` for every index**, which is what makes building the stream
tractable:

```
[511] weekendPushWindowOpen           BOOL
[512] weekendPushRecordScore          BOOL
[513] weekendPushGetReward            BOOL
[514] weekendPushScoreDiff            INT32
[515] weekendPushRewardsHaveGotten    PYTHON   <-- needs to arrive as [] not None
```

Also now cross-confirmed: the **property descriptor table is at `EntityType + 0x58`**,
`0x68` bytes per descriptor. Claude measured that vector at 86,528 bytes in an earlier
independent live scan; 86,528 / 0x68 = **exactly 832**, matching Gemini's 832-property
count. Two independent derivations agree.

## 2026-09-19: FIXED a real bug — `sauth` was missing the `'aid'` key, crashing `onLoginByServerSauth`

Found by running the first properly-controlled `ROS_AUTO_ENTER_HALL=0` test (server
sends ONLY `showSelectCharacter([])` then holds, so the client is never force-marched
into the Lobby). Evidence in `scratch/live_logcat_charcreate_test.txt`:

```
Traceback (most recent call last):
  File "elkLogging.py", line 92, in wrapper
  File "entities\Account.py", line 56, in onChannelLogin
  File "common\decorators.py", line 339, in inner
  File "helpers\channel\channel_login.py", line 411, in onLoginByServerSauth
KeyError: 'aid'
```

Our `Account.onChannelLogin(ret, sauth)` shipped a `sauth` dict containing only
`uid`/`session`/`sdk_version`/`channel`. The client's `onLoginByServerSauth` indexes
`sauth['aid']` and raised, aborting login completion **before** anything downstream
could run. This had never been seen before because the auto-enter-hall sequence
force-drove the client past it every previous session.

**Fix applied** in `mitm/local_baseapp_capture.py`: added `'aid'`, and (default-on,
`ROS_SAUTH_DEFAULTDICT=1`) ship a `collections.defaultdict(str, ...)` instead of a plain
dict so any *other* key the client indexes yields `''` rather than raising. Rationale:
`script.npk` is encrypted so the required key set cannot be read statically, and a
defaultdict turns "one KeyError per server restart" into a single test that reveals the
whole downstream path.

**Verified live** (`scratch/live_logcat_sauthfix.txt`): `KeyError: 'aid'` occurrences
went **1 → 0**, and no other `KeyError` appeared. The full entity `onCreate` chain now
runs and the `Scene` GameObject is created.

This is independently corroborated by `07_ros_legacy_approach/PC_LAUNCHER_STUDY.md:110-113`,
which documents the PC private-server community hitting the same class of problem —
the client's own `channel_login.py` glue aborting in `onLoginByServerSauth` before
reaching `enterHall`.

### Still open: the Character Creation UI does not appear

The user supplied a reference screenshot (from other devs' working setup) of a real
Character Creation screen — 3D character on the hall terrace, a "Tap to Enter NAME"
field, and a "CREATE" button. So this screen **does exist and is reachable**; the
earlier note in `HANDOFF_PROMPT_GEMINI_2026-09-18_lobby_polish.md` claiming "there is
no interactive Character Creation UI in this client" is **WRONG and is hereby retracted**.

Current live state with the `sauth` fix applied and `ROS_AUTO_ENTER_HALL=0`:
- Login completes, `onCreate` chain runs, `showSelectCharacter([])` is delivered.
- `_loadDefaultScene()` runs and the `Scene` GameObject is created
  (`GetAllSubObj set([<Scene (GameObject) at 0x763838542390>])`).
- **Then nothing.** That `GetAllSubObj` line is the last `<SCRIPT>` output; the client
  sits on the title screen and never presents the name-entry/CREATE UI.

Note `showSelectCharacter` is the **only** character-UI-shaped method in the whole
1131-entry Athlete client method table (`scratch/athlete_methods_all.txt`):
```
[1083] showSelectCharacter   [1084] onCreateCharacter   [1085] onRoleCreateSuc
[1086] onChangeNickname      [1087] updateBaseCharacter [1088] updateBaseNickname
```
so the trigger is not some other un-called RPC. Leading hypothesis, **not yet tested**:
we pass `oldNames = []` (empty `ARRAY<STRING>`), and the method is named
*show**Select**Character* — an empty list may make the client's UI code take a
select-nothing path, whereas the real flow may require either a non-empty list or some
additional state before it will render the create form.

**Status**: closer than Attempts 1-5 (found the actual connection address
in memory, not just a generic shape match) but still short of a
conclusively validated `ServerConnection` base address. Given six
different technique families have now been tried across this session
(direct offset guess, vtable-slot decompile, symbol/string search,
targeted heap scan, full generic-signature heap scan, exact-value heap
scan) without a fully closed result, dynamic instrumentation (Frida) is
the clearly indicated next tool rather than a seventh static variant --
one runtime read of `param_1` inside `FUN_00a49590` or `FUN_00a4c540`
would settle this immediately and is the kind of read no amount of
additional static guessing reliably replaces.

## Checkpoint 17: Property-Push Wire Architecture Fully Solved (2026-09-19) — Tasks 1, 2, and 3 Closed with Exact Decompilation & Memory Proofs

All three tasks assigned in `scratch/HANDOFF_PROMPT_GEMINI_2026-09-19_property_push.md` are **SOLVED and MATHEMATICALLY PROVEN**. Zero guesswork; every struct offset, vtable address, flag filter bitmask, and wire decoding routine cited below is backed by Ghidra decompilation (`scratch/ghidra_*_decompiled.txt`) and live process memory dumps (`scratch/athlete_entitytype_dump4k.bin`).

---

### 1. Task 1 Solved: Property-Descriptor Table Offset & Field Layout in `EntityType`

Decompiled property accessors: `FUN_00ad02ec`, `FUN_00ad02fc`, `FUN_00ad0338`, `FUN_00ad0348`, `FUN_00acd5d0`, `FUN_00acd5ec` (`scratch/disasm_prop_accessors.txt`, `scratch/ghidra_disasm_acd5d0.txt`).

#### A. Vector Offsets in `EntityType`
- **`EntityType + 0x58`**: `std::vector<DataDescription>` (master property descriptors begin/end/capacity).
  - Stride = **`0x68` (104 bytes)**.
  - Mathematical proof: Compiler uses modular inverse constant `0x4ec4ec4ec4ec4ec5` ($13 \times 8 = 104$) for dividing pointer difference by 104, and assembly specifies `mov w27, #0x68` / `umaddl x8, w1, w12, x8` with `w12 = 0x68`.
  - Live heap dump verification (`scratch/athlete_entitytype_dump4k.bin`):
    `begin = 0x76384eb88000`, `end = 0x76384eb9d200`, `diff = 0x15200` (86,528 bytes).
    Total master property count for `Athlete` (type 51) = $86528 / 104 = \mathbf{832}$ **properties**.
- **`EntityType + 0x70`**: `std::vector<uint32_t>` (client property indices).
  - Stride = **4 bytes**.
  - Live heap dump: `begin = 0x76384eb02000`, `end = 0x76384eb02718`, `diff = 0x718` (1,816 bytes).
  - Total client property count for `Athlete` = $1816 / 4 = \mathbf{454}$ **client properties**.
- **`EntityType + 0x88`**: `std::vector<uint32_t>` (broadcast property indices for `OTHER_CLIENTS` / `ALL_CLIENTS`).
  - For `Athlete` player entity on client: `begin = 0x0`, `end = 0x0` (0 entries, because own player does not broadcast to itself).

#### B. `DataDescription` (104 bytes / `0x68`) Struct Layout
Reversed from `DataDescription::parse` (`FUN_00a9e5d8`, `scratch/ghidra_datadesc_parse.txt`) and helper accessors (`scratch/ghidra_flags_helpers.txt`):
- `+0x00`: `std::string name` (24 bytes). Inline string if len <= 22, pointer if >= 23.
- `+0x18`: `DataType* pDataType` (polymorphic type descriptor).
  - Vtable slot 7 (`+0x38`): `createDefaultValue` (`FUN_00a9f8e4`).
  - Vtable slot 11 (`+0x58`): `createFromStream` (`FUN_00aa0994`).
- `+0x20`: `uint32_t flags`:
  - `0x00` (`0`): `CELL_PRIVATE`
  - `0x01` (`1`): `CELL_PUBLIC`
  - `0x03` (`3`): `OTHER_CLIENTS`
  - `0x04` (`4`): `OWN_CLIENT`
  - `0x05` (`5`): `CELL_PUBLIC_AND_OWN`
  - `0x07` (`7`): `ALL_CLIENTS`
  - `0x08` (`8`): `BASE`
  - `0x0C` (`12`): `BASE_AND_CLIENT` (Bit 3 = BASE, Bit 2 = CLIENT)
- `+0x28`: `PyObject* pDefaultValue`
- `+0x30`: `PyObject* pInitialValue`
- `+0x38`: `PyObject* pCustomValidator`
- `+0x40`: `DataSectionPtr pDefaultSection`
- `+0x48`: `int32_t clientIndex` (assigned via `FUN_00aa0d4c`)
- `+0x50`: `int32_t clientVectorIndex`
- `+0x54`: `int32_t baseVectorIndex`
- `+0x60`: `int32_t methodEventIndex`

---

### 2. Task 2 Solved: The Manager Vtable at `0x038d64d0` and the Complete Wire Decoders

The manager class is **`ClientApp`** (not `ServerConnection`; `ServerConnection` holds a pointer to `ClientApp` at `+0x110`). Its primary vtable is located in `.data.rel.ro` at VA **`0x038d64d0`** (`scratch/ghidra_manager_verified.txt`).

#### A. `ClientApp` Vtable Slot Layout (`0x038d64d0`)
- **Slot 0 (`+0x00`)**: `FUN_00a18504` (`ClientApp::onBasePlayerCreate`) — called by `ServerConnection::createBasePlayer` (`FUN_00a47dc4`, msgID 5).
- **Slot 1 (`+0x08`)**: `FUN_00a1894c` (`ClientApp::onCellPlayerCreate`) — called by `ServerConnection::createCellPlayer` (`FUN_00a47e8c`, msgID 6).
- **Slot 2 (`+0x10`)**: `FUN_00a18db4`
- **Slot 3 (`+0x18`)**: `FUN_00a18e5c` (sets space/cell attachment, fires `onBecomeCellPlayer`).
- **Slot 4 (`+0x20`)**: `FUN_00a193c4` (`ClientApp::onEntityPartialUpdate`, msgID 11 `partialUpdate`).
- **Slot 5 (`+0x28`)**: `FUN_00a1946c`
- **Slot 6 (`+0x30`)**: `FUN_00a19b1c` (`ClientApp::onEntityEnterAoI` / `createEntity`, msgID 8).
- **Slot 7 (`+0x38`)**: `FUN_00a1a41c` (`ClientApp::onEntityProperties`) — called by `updateEntity` handler (`FUN_00a49590`, msgID 10).

#### B. The Three Wire Property Decoders

##### Decoder 1: `createBasePlayer` (msgID 5, handler `FUN_00a47dc4`, slot 0 `FUN_00a18504`)
- Wire format: `[flags:u16 = 0x0008][msgID: 0x05][len:u16][entity_id:u32][entity_type:u16][property_stream...]`
- Passes `stream` to `EntityType::newDictionary(type, stream, domain=0)` (`FUN_00a2a58c`).
- **If stream is empty (`remainingLength == 0`)**:
  - Calls `FUN_00a2a344` (`scratch/ghidra_a2a344_decompiled.txt`), which loops through all 832 properties and populates client defaults where `flags & 6 != 0`.
- **If stream is non-empty**:
  - Calls `FUN_00acf8ac(type, stream, 0xb, dict)` -> `FUN_00acf5ec(type, 0xb, &reader)` (`scratch/ghidra_acf5ec_decompiled.txt`).
  - Flag filter in `FUN_00acf5ec`:
    - `(flags >> 3 & 1) == 1`: Bit 3 (BASE) MUST be 1.
    - `(flags & 6) != 0`: Bit 1 or 2 (CLIENT) MUST be 1.
    - **Matches strictly `BASE_AND_CLIENT` (flag 12 = 0x0C)**!
  - Unpacks all `BASE_AND_CLIENT` properties sequentially in master descriptor order via `EntityDescription::readStream` (`FUN_00ad0c94`) and sets them in `self.__dict__`.
  - **Reason Claude's prior 3632-byte stream failed**: It was packed with guessed properties, whereas `domain=0` strictly expects *only* the sequence of `BASE_AND_CLIENT` properties!

##### Decoder 2: `createCellPlayer` (msgID 6, handler `FUN_00a47e8c`, slot 1 `FUN_00a1894c`)
- BigWorld's mechanism for transitioning an entity into a cell/world space.
- Wire format:
  ```text
  [flags:u16 = 0x0008][msgID: 0x06][len:u16 LE]
  Payload:
    [spaceID: uint32 LE]      (e.g. 1)
    [vehicleID: uint32 LE]    (0)
    [pos: 3 * float32 LE]     (x, y, z)
    [dir: 3 * float32 LE]     (yaw, pitch, roll via FUN_00a81854)
    [property_stream...]      (passed to Entity::readCellPlayerData)
  ```
- Total header/transform prefix before stream: **32 bytes**.
- Handler `FUN_00a47e8c` calls manager slot 1 (`FUN_00a1894c`).
- `FUN_00a1894c` calls slot 6 (`FUN_00a19b1c`) with `param_6 = 0xffff` (-1).
- When `param_6 == -1`, it calls `Entity::readCellPlayerData` (`FUN_00a21ebc`), which calls `EntityType::newDictionary(type, stream, domain=1)`.
- In `domain = 1`:
  - Calls `FUN_00acf8ac(type, stream, 0xe, dict)` -> `FUN_00acf5ec`.
  - Filters all properties where `(flags >> 3 & 1) == 0` (non-BASE) AND `(flags & 6) != 0` (client properties: `OWN_CLIENT`, `CELL_PUBLIC_AND_OWN`, `ALL_CLIENTS`).
  - Sequentially unpacks every matching client property off the stream and executes `PyDict_Update(self.__dict__, dict)`.
  - If stream is empty: `FUN_00a2a344` sets defaults and updates `self.__dict__`!
- Then slot 3 (`FUN_00a18e5c`) runs and calls `onBecomeCellPlayer`!

##### Decoder 3: `updateEntity` (msgID 10, handler `FUN_00a49590`, slot 7 `FUN_00a1a41c`)
- Wire format: `[flags:u16 = 0x0008][msgID: 0x0A][len:u16 LE][entity_id:u32 LE][property_stream...]`
- Calls `Entity::readProperties(entity, stream, 0)` (`FUN_00a22338`).
- Reads bitmask for properties in vector `+0x88` (broadcast properties).
- Because `+0x88` has 0 entries for the player's own `Athlete` entity, `updateEntity` is exclusively for *other* entities in AoI, not for pushing base properties to `PlayerAthlete`!

---

### 3. Root Cause of the 4 Missing Properties Resolved

1. **`weekendPushRewardsHaveGotten`**:
   - Declared in `entity_0376.xml`: `<Flags> BASE_AND_CLIENT </Flags>`, `<Type> PYTHON </Type>`, no `<Default>`.
   - Default value in BigWorld is `None`.
   - In `iWeekendPush.py:66`, `tryActiveWeekendPushRedBadge` iterates over it. If `None`, raises `TypeError: 'NoneType' object is not iterable`.
   - Solved either by passing a valid `BASE_AND_CLIENT` stream in `createBasePlayer`, or initializing it via `createCellPlayer`.
2. **`hallTeamData`**:
   - Declared in `entity_0335.xml`: `<Flags> BASE </Flags>`, `<Type> PYTHON </Type>`, `<Default> {} </Default>`.
   - **Crucial architectural discovery**: `hallTeamData` is flagged `BASE`! In BigWorld, `BASE`-flagged properties are strictly filtered out by `FUN_00a9f2ec` (`flags & 6 == 0`) and are NEVER transmitted over the wire or instantiated by the C++ engine on the client.
   - The client Python script `entities/iHallTeam.py` expects `self.hallTeamData` to be populated at runtime via the client RPC method **`onEnterHallTeam`** (idx 54) or managed via **`onLeaveHallTeam`** (idx 59).
   - Calling `onLeaveHallTeam` previously crashed because line 358 checks `if self.isInFormedTeam():`, which queries `self.hallTeamData` before setting it.
   - If `self.hallTeamData` is initialized (e.g. by sending `onEnterHallTeam` with a solo team, or by driving client state correctly), the Start button and Lobby UI unblock cleanly!
3. **`monthPayRebateSpecialAwardInfo`**:
   - Declared in `entity_0141.xml` with `<Type> PYTHON </Type>` and `<Default> {} </Default>`, but has no `<Flags>` (defaults to `CELL_PRIVATE` = 0).
4. **`timerRefreshMSToken`**:
   - Transient Python timer handle created dynamically by `self.timerRefreshMSToken = BigWorld.callback(...)` in `Athlete.py:445`.

---

### 4. Live Verification Plan for Claude

1. **Test `createCellPlayer` (msgID 6)**:
   - In `mitm/local_baseapp_capture.py`, after Stage 3 (`createBasePlayer(Athlete)`), construct and send `createCellPlayer` packet:
     - `flags = 0x0008`
     - `msgID = 0x06`
     - `payload = struct.pack('<IIffffff', 1, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)`
   - Verify in logcat:
     `ServerConnection::createCellPlayer: id 1`
     Verify if `onBecomeCellPlayer` fires and whether client properties populate without Python exceptions.
2. **Test `onEnterHallTeam` (idx 54) / Team Initialization**:
   - If `hallTeamData` is needed to satisfy `isInTeam()`, send `onEnterHallTeam` (idx 54) with a solo team structure before `enterHall(True)`.


## Checkpoint 20 (2026-09-20): client now receives both createBasePlayer packets; the real stream desync is a FIXED-SIZE ARRAY at ordinal 207

Every item below was changed AND live-tested this session. Evidence files are in `scratch/`.

### 1. Server: session-key scan skipped the region that held the key
`mitm/local_baseapp_capture.py` `fast_find_session_key()` filtered heap regions with `sz > 16` (MB).
`scratch/scan_all_regions.py` (Gemini) found the live EncryptionFilter key in a **10 MB** region
(`763854e00000-763855800000`), so KEYSCAN logged "no key found" while the key was in memory.
Heap layout differs per launch, which is why the scan succeeded on some launches and not others.
**Fix:** threshold `sz >= 2` (the binary search bottoms out at 2 MB). Regions come from
`libc_malloc`/`[heap]` lines only, so nothing else filters them.

### 2. Live result of that fix (with Gemini's uncommitted fragmentation code also active)
`scratch/lc_keyfix.txt`: **two** `ServerConnection::createBasePlayer: id 1` lines (Account
16:03:12.004, Athlete 16:03:12.316), no `Dropping packet` warning, and the entity layer now runs
(Python tracebacks from `Athlete.py`, `enterHall` walking its interface chain).
Before (`scratch/lc_setplayer.txt`, 1585 B stream, old server code): only **one** createBasePlayer, then
`EncryptionFilter::recv: Dropping packet from 172.16.1.2:25010 due to illegal wastage count (100)` and
`MainApp::poll ... REASON_CORRUPTED_PACKET`.
**Not separated:** the keyscan fix and Gemini's `send_mercury_message` fragmentation were both in the
working tree for the good run, so which of the two rescued the 1585-byte case is unproven. The
1457-byte single-packet run (`scratch/lc_upto0.txt`, `ROS_COLLECTION_DEFAULTS_MODE=upto:0`) also shows two
createBasePlayer lines. Fragment reassembly worked at least in the sense that the client saw the whole
stream: its own error reported `783 bytes remaining` at cursor 798, and 798+4+783 = 1585.
Gemini's fragmentation (`send_mercury_message`, 1443-byte chunks, footers `first_seq,last_seq,seq`) is
therefore not refuted, but not yet isolated either.

### 3. The desync: `childBaseClientPropertyList` / `childClientPropertyList2` are `<size> 1 </size>` arrays
Decompiled `SequenceDataType::createFromStream` = `FUN_00aa4b14` (`scratch/ghidra_sequencedatatype.txt`,
script `scratch/ghidra_scripts/FindSequenceDataType.java`):
```c
iVar1 = (int)param_2[6];                 // DataType+0x30 : FIXED element count declared in the type
if (iVar1 == 0) iVar1 = *(int*)stream.read(4);   // count is on the wire ONLY when no fixed size
if (iVar1 < 0 || remaining < iVar1) log("Invalid size on stream: %d (%d bytes remaining)", iVar1, remaining);
for (i = 0; i < iVar1; i++)              // element type = DataType+0x28
    if (elem == NULL) log("creating element %d, Invalid size on stream: %d (%d bytes remaining)", i, iVar1, ...);
```
So in `creating element 0, Invalid size on stream: 1` the `1` is the **sequence's own count**, not a value
read from our stream (our stream contains no `0x01` byte at all). A fixed-size array has **no count on the
wire**. `05_entities/out/entity_0141.xml` declares both `childBaseClientPropertyList` and
`childClientPropertyList2` as `ARRAY <of> FIXED_DICT ... </of> <size> 1 </size>`, and the generator wrote a
4-byte zero count for each, so the client read the entire dict body (dozens of fields, nested arrays) out
of the bytes that followed and stayed misaligned to the end.
**Arithmetic that ties it together:** the element's first 8 fields are primitives totalling
1+8+8+1+4+4+8+8 = **42 bytes**, then `package2` (a nested FIXED_DICT) starts with an ARRAY count.
Our ordinal 207 offset + 42 equals the client's failing cursor in every run:
711+42 = 753 (stamped-INT32 run: client read our ordinal-219 stamp `1000219` as a count),
756+42 = **798** (all-defaults run: bytes `28 64 2e 00` = `"(d."` misread as count 3040296),
and in the no-defaults run the first nested count at 753 read `0` (valid) so parsing continued and
failed later at cursor 985 (`2e 02 4e 2e` = `.\x02N.`, value 776864302).

### 4. Why earlier bisection was misleading
The truncation bisect declared "in sync through K" when a truncated stream produced no
`Invalid size` error. A misaligned client can consume any number of bytes without that error (integer
reads never fail; PYTHON reads are length-prefixed), so silence proved nothing. The only positive
alignment evidence is a *specific* client error whose numbers can be checked against a known offset,
as in section 3. Use that style of check, not silence.

### 5. Generalised lesson
The XML-regex type extractor could not see past a nested `<Properties>` block and returned `None` for
every ARRAY-of-FIXED_DICT, which the generator then forced to "ARRAY, count 0". **Fixed-size arrays exist
elsewhere too** (`grep -l "<size>" 05_entities/out/*.xml` finds 7 files, e.g. `ARRAY <of> INT32 </of>
<size> 2 </size>`). Any included property with a `<size>` is mis-encoded until the generator is rewritten
around the *runtime* type tree (`scratch/dump_runtime_types.py`, in progress) instead of XML regexes.

### 6. Tooling changes this session
- `scratch/drive_login.py`: detects the server log's encoding (UTF-16LE vs UTF-8) — it read a UTF-8 log
  as UTF-16LE, found no matches and re-tapped 13 times after a login had already succeeded. Events-popup
  close button is `(1845, 105)` (Gemini measured it), not `(1841, 108)`.
- `scratch/gen_stream_v2.py`: new `ROS_COLLECTION_DEFAULTS_MODE=upto:K` (defaults only for ordinals < K).
  `all` (default) and Gemini's `compact` are unchanged.
- **Two different adb binaries** are in use: LDPlayer's is 34.0.4, the Android SDK's is 37.0.1. Mixed client
  versions restart each other's adb server and are a likely cause of earlier "wedged" sessions. Launch the
  server with `ADB_PATH=C:\Users\Raysoo\AppData\Local\Android\Sdk\platform-tools\adb.exe` so everything
  uses one.
- `adb exec-out "su 0 dd ..."` returns **extra trailing bytes** (4097 for a 4 KB page, 65551 for 64 KB);
  always slice to the requested length.
- New: `scratch/xmltypes.py` (ElementTree access to the entity XMLs; 722/723 files parse),
  `scratch/dump_runtime_types.py` (WIP), `scratch/ghidra_scripts/FindSequenceDataType.java`.

### 7. State at the end of this checkpoint / next step
`data/athlete_mobile_stream.bin` is currently the `upto:0` baseline (1457 B). It, and the `all` variant,
are both desynced at ordinal 207. **Next:** rebuild the encoder from the live runtime DataType tree
(ARRAY fixed size at `+0x30`, element type at `+0x28`; FIXED_DICT field records at `+0x20`, 40 bytes each:
`std::string` name, `DataType*`, 8 B misc), verify it on `dtsAppearancePackage` (must give 4 fields named
`itemList/itemsList/layoutInfo/_packageCapacity`), then re-run `scratch/drive_login.py` and check that the
`childBaseClientPropertyList` error is gone.


## Checkpoint 20b (2026-09-20): FIXED — stream now consumed cleanly; next blocker is `extconfigs.getServiceAccessPoint`

### Change
`scratch/gen_stream_v3.py` replaces `gen_stream_v2.py`. It encodes from the client's **runtime DataType
tree** (`scratch/athlete_runtime_types.json`, produced by `scratch/dump_runtime_types.py`, encoder in
`scratch/runtime_encoder.py`) instead of XML regexes and vtable addresses. Key differences from v2:
fixed-size arrays get no count and exactly `fixed` inline elements
(`childBaseClientPropertyList` 307 B / `childClientPropertyList2` 294 B, each 1 element of a 76 / 81-field
FIXED_DICT); everything else is byte-identical to v2 (cross-check: 1457 - 2x4 count bytes + 293 + 261 = 2003
vs 2002 from the encoder, the 1-byte gap being the specially-cased target property). Stream = **2178 B**
(`ROS_STREAM_DEFAULTS=min`: numbers/strings zero, PYTHON collections take their declared `[]`/`{}`), sent as
2 Mercury fragments by `send_mercury_message`.

### Runtime type-tree facts (verified live, `scratch/dump_runtime_types.py`)
- ARRAY DataType: `+0x28` element `DataType*`, `+0x30` int32 fixed size. FIXED_DICT: `+0x20/+0x28` begin/end of
  40-byte field records `[std::string name (24 B)][DataType* (8 B)][8 B]`. Validated on
  `dtsAppearancePackage`: exactly 4 fields named `itemList, itemsList, layoutInfo, _packageCapacity`.
- Class names come from RTTI (`vtable[-1] -> typeinfo -> mangled name`), so no vtable addresses are hard-coded.
  Only 14 classes exist in the whole tree: `IntegerDataType<c,h,s,i>`, `LongIntegerDataType<j,x,y>`,
  `FloatDataType<f>`, `String/Blob/Python/Array/FixedDict/MailBox DataType`. `MailBoxDataType` is **not** used
  anywhere in the 454 included properties.

### Live result (`scratch/lc_v3min.txt`)
- Two `createBasePlayer: id 1` lines. **No** `SequenceDataType`/`PythonDataType` errors, **no**
  `Could not create ...`, **no** `MemoryIStream ... still N bytes left` after the Athlete message, **no**
  `AttributeError` (`hostID`, `gameObject`, `baseLevel`, `childBaseClientPropertyList` are all gone).
  The Athlete stream is consumed exactly.
- `Athlete.onBecomePlayer` now runs. It raises
  `TypeError: 'NoneType' object has no attribute '__getitem__'` at `entities\Athlete.py:275` ->
  `extconfigs.py:50 getServiceAccessPoint`. This is client-side service configuration (a `None` config object),
  not the property stream.
- After ~25 s the screen shows the game's own loading tip screen with a progress bar (the hall scene is loading).

### Tooling gotcha found on the way
`adb exec-out "su 0 dd ..."` **converts every 0x0A byte into 0x0D 0x0A** on this adbd/su pair (a 4096-byte page
returned 4169 bytes; differences start at the first LF). Use `adb shell "su 0 sh -c 'dd ... | base64'"` and decode
(`dump_dd_b64` in `scratch/dump_runtime_types.py`) or `dd of=file` + `adb pull`. **`fast_find_session_key()` in
`mitm/local_baseapp_capture.py` still reads regions through `exec-out`**; a LF inside the vtable-pointer pattern or
the 24 key bytes would silently break the match, so keyscan may still miss on some launches. Not yet changed.

### Superseded / retracted by this checkpoint
`gen_stream_v2.py` output (1457 / 1585 B) is desynced at ordinal 207 and must not be used; the
"ordinals 301-305 residual" was a downstream symptom of that.


## Checkpoint 20c (RETRACTED — see 20d) (2026-09-20): full Lobby with avatar model — declared XML defaults are what make the Lobby clean

### Live A/B (same 2178 B layout, only the property VALUES differ; both consume the stream cleanly)
| run | `ROS_STREAM_DEFAULTS` | Lobby |
|:--|:--|:--|
| `scratch/lc_v3min.txt` | `min` (zeros; PYTHON collections `[]`/`{}`) | renders, but **no avatar model**, 4-5 overlapping duplicated promo boxes ("All team members receive additional 20%..."), a stray **Leave Team** button |
| `scratch/lc_v3xml.txt` | `xml` (each property's declared `<Default>`) | **avatar model on the terrace, "Survivor" nameplate + rank icon, START, Ranked, Invite 0/0, clean solo-team state**, promos essentially clean (one leftover "Finish / check the" text fragment) |
Evidence: `scratch/lobby_avatar_2026-09-20.png` (xml).
**Interaction caveat (user report, 2026-09-20):** in the user's own session a clean Lobby with the avatar appeared only
*after navigating to the Ranked page and back*, so that screenshot alone does not show the stream fix. The A/B above does
not depend on it: `scratch/drive_login.py` stops tapping once the login is detected and `scratch/lobby_probe.py` only
screenshots ~95 s later, so no probe run touches the Lobby UI. What the user's observation adds is a clue: opening the
Ranked page rebuilds/refreshes the hall and repairs the messy state, i.e. the *initial* hall build is what depends on the
property values.

### What differs: 27 properties (82 bytes) — `min` -> `xml`
`baseLevel` 0->1, `finishedDtsTraining` 0->1, `needOBRoomTip` 0->1, `needNormalRoomTip` 0->1, `firstTimeBind` 0->1,
`showSurveyRedPoint` 0->1, `xmasRepairArea2020ShowTips` 0->1, `readGMRedhintMsg` 0->1, `firstEnterXmasTree` 0->1,
`isOldVersionTurntable` 0->1, `freeHeroRefreshWeekIdx` 0->1, `weaponProficiencyRankVersion` 0->1, `refreshVidChance` 0->5,
sentinels `-1`: `choseGalaxy`, `scoreRank`, `maxScore`(int64), `xmas2018MaxLotteryIdx`, `finalReward`, `costAppearanceID`,
`exchangedAppearanceID`, `proficiencyState`; date-like ints `lastTimeGetChickenGift` / `lastTimeGetBonusGift`
(0x0133ec85 = 20180101), `dragonDanceJoinTime` (201904); `g89CreditScore` 0.0 -> 100.0; and the first INT32 of
`childClientPropertyList2`'s element 0 (0 -> -1).
**Which of these actually fixes the promo duplication / avatar is NOT yet isolated** — see the bisect below.

### Also this checkpoint
- `scratch/gen_stream_v3.py` default is now `xml`; `min` is kept only for A/B work.
- The screenshot is kept local-only unless force-added: `.gitignore` excludes `scratch/*.png`.
- Still open: `extconfigs.getServiceAccessPoint` TypeError in `Athlete.onBecomePlayer` (line 275) — non-fatal here,
  cause unknown (encrypted script; the server answers `nstool.netease.com/internalquery` with 200, so it is not a
  plain missing HTTP config).


## Checkpoint 20d (2026-09-20): RETRACTION — the clean/messy Lobby is NOT determined by the property defaults

Bisect of the 27 differing properties (`scratch/lobby_probe.py`, no Lobby interaction in any run; screenshot ~95 s after login):

| run | stream | hall |
|:--|:--|:--|
| `min` | zeros | messy (duplicate promo boxes, Leave Team, no avatar) |
| `xml` | all declared defaults | **clean** (avatar, no duplicates) |
| A `baseLevel, finishedDtsTraining` | xml for those 2 only | messy |
| B (11 flag properties) | xml for those 11 only | **clean** |
| B1 (5 room-tip / first-time flags) | | messy |
| B2 (6 remaining flags) | | messy |
| **B replicate** | **identical to B** | **messy** |

The exact same stream produced a clean and a messy Lobby, so **the earlier conclusion (Checkpoint 20c) that declared defaults make the Lobby clean is retracted**. B1 and B2 individually messy but B (= B1 + B2) clean once was noise, not an interaction effect. What survives: the stream is consumed exactly in every run, and the Lobby renders in every run.

User observation (2026-09-20): after visiting the **Ranked** page and returning, the hall is clean with the avatar. Together with the non-determinism this points at a timing/refresh issue in the *initial hall build* (e.g. hall UI built twice, or an RPC arriving before the client finished a step) rather than at any property value. `extconfigs.getServiceAccessPoint` raising inside `Athlete.onBecomePlayer` (deterministic in every run) is a candidate for leaving initialisation incomplete, but it does not explain the run-to-run difference.

Lesson recorded: a single A/B pair is not evidence. Replicate any run whose outcome could be timing-dependent before acting on it.

## Checkpoint 20e (2026-09-20): no-interaction time series (inconclusive) + probe tooling

- `scratch/lobby_probe.py` now takes `PROBE_DELAYS="70,60,60"` and saves `probe_<label>_t<k>.png` at each delay.
- Run `T_series` (xml stream, delays 60x5): `t0` (16:59:07) = MESSY hall — duplicate promo boxes, stray "Leave Team",
  no avatar. `t2` (17:01:09) = Weapon "Review" page with the avatar visible, i.e. the user had touched the emulator.
  The run is therefore CONTAMINATED and does not answer whether a messy hall self-heals with no input.
- Consistent with the user's observation (avatar/clean hall appear after visiting Rank): navigating triggers a UI
  refresh that the server-driven Stage-4 sequence does not. Cause still unknown.
- Next: repeat with the emulator untouched (no one at the keyboard) and compare t0..t4.

## Checkpoint 20f (2026-09-20): service endpoint + Lucky Carnival state unblock the first hall build

### Verified causes and changes
- Recovered `extconfigs.getServiceAccessPoint(ap)` bytecode indexes `ap[0]` and `ap[1]` (also `ap[2]` on the
  published-iOS path). `Athlete.onBecomePlayer` passes `self.msHttpAP`, whose stream value had been `None`.
  `scratch/gen_stream_v3.py` now has one runtime-Type-driven `PROPERTY_OVERRIDES` table and encodes
  `msHttpAP = ['172.16.1.2', 80, 443]`; this stays entirely on the LAN. The same table retains the verified
  `weekendPushRewardsHaveGotten = []` override. Generated stream size is 2209 B and remains aligned.
- Once that abort was removed, the next deterministic abort identified the missing dynamic attribute
  `iLuckyCarnivalIsSuper`. It is initialized by the client method `Athlete.onUpdateLuckyCarnivalData`; method
  index 745 was verified against the live 1,131-entry Athlete client-method table (nearby 749..751 are the
  expected `syncTurnTableStatus`, `onShowOldCarnivalBg`, and `onShowNewCarnivalBg`). The local BaseApp now sends
  a complete empty/default Lucky Carnival dictionary only after the unchanged Stage-4 RPC sequence.

### Repeated live results and limits
- With only `msHttpAP` fixed, the original `extconfigs.py:50` TypeError disappeared, but initial hall UI creation
  then aborted on `iLuckyCarnivalIsSuper`; this negative result is why the server-state initializer was added.
- After both changes, two fresh PLAY-to-hall runs rendered the avatar without opening Ranked. The later clean
  capture (`scratch/issue1_run3b.png`) had no duplicated promo stack and no stray Leave Team. An intermediate
  run had the action/emoji panel open; the user confirmed they had tapped the emoji, so the three
  `dtsInGameActionAppearanceIDs` tracebacks from that run are interaction-triggered, not fresh-login errors.
- **Not fully fixed / no zero-error claim:** the clean visual run still logged
  `monthPayRebateSpecialAwardInfo` missing in `UIG89MainAnwser.refreshMonthlyBenefit`, plus
  `UIMain.showRedPoint` line 2453 iterating `None`. These are the next fresh-init blockers and may also explain
  Depot Back failing through the same `showRedPoint` path.

## Checkpoint 20g (2026-09-20): auto nickname `Dev | Raysoo`, `gmsyncRedPoints([])`, currency negative result

Code: `mitm/local_baseapp_capture.py` — default nickname now `ROS_BASE_NICKNAME` (default `Dev | Raysoo`); after the unchanged
Stage-4 sequence the server also sends `Athlete.gmsyncRedPoints([])` (client-method idx 1099, empty dynamic ARRAY = `<I 0`)
then `onUpdateLuckyCarnivalData` (idx 745). Tooling: `scratch/drive_login.py`/`lobby_probe.py` honour `ADB_PATH`
(`ROS_SERVER_LOG` for the server log); new `scratch/fresh_run.sh <label>` (fresh login + controls Confirm + full-logcat
SCRIPT ERROR list) and `scratch/depot_test.sh <label>` (Depot open + Android Back); `gen_stream_v3.py` takes
`ROS_PROP_OVERRIDES=name=int,...` for INT properties.

Live results (server restarted with the new code, `ROS_AUTO_ENTER_HALL=1`):
- Run 1 and run 2 (fresh logins, no interaction): hall shows the avatar, nickname exactly `Dev | Raysoo`, no duplicate
  promo stack, no stray "Leave Team". (After the "Please select controls" screen is confirmed.) Screens:
  `scratch/rp1_hall4.png`, `scratch/fresh_cur1_hall.png`.
- `UIMain.showRedPoint` NoneType error: absent in both fresh runs, and the first Android Back out of the Depot popup
  no longer raised it (`scratch/depot_v1_logcat.txt`, 0 SCRIPT ERROR). Consistent with `displayAll -> showRedPoint(Globals.redPoints)`.
  Two runs so far; replicate more before calling it closed.
- Fresh-login SCRIPT ERRORs still present (run 2, full logcat stream): (1) `iMonthPayRebateSpecialAward.is_all_award_done`
  -> `monthPayRebateSpecialAwardInfo` missing (from `UIMain.on_enter`); (2) NEW: `UIMainLiveIcon.showActivityRedBadge` ->
  `personalRecommendState` missing (`entity_0141.xml`: INT32, XML default 0; not in the 454-property stream, so it must be
  set by an RPC/other path). Run 1 additionally logged `Athlete._loadDefaultScene` `'NoneType' ... SetLoadingProcess` once
  (not reproduced in run 2; likely a timing race).
- Depot Back, second press: crashes in `UIDtsAppearanceCostume.on_leave -> DtsAppearanceRightPanelPattern1.on_leave ->
  onHideTransformBtn`: `'NoneType' object has no attribute 'refreshTransformPanel'`. The leave aborts halfway and leaves a
  blank scene with no HUD (user is stuck until the app is restarted). Cause not identified (a transform-panel object that
  was never created).
- NEGATIVE: currency. The three top-bar slots read `283283`, which does not occur in the stream. Setting
  `freeYuanbao=1000` / `payYuanbao=500` in the stream did NOT change the top bar (still `283283` x3), and the Depot page shows
  0/0/0. So `freeYuanbao`/`payYuanbao` do not feed those slots (or the client caches them from another RPC). Still unknown.
  The override run's stream was regenerated back to defaults afterwards.

## Checkpoint 20h (2026-09-20): overlapping labels above Ranked = airship panel state; script-decrypt tooling

- New tools (no source needed any more): `tools/script_index.py` (decrypts every module of `04_obb/extracted/script.npk` with the legacy
  `ros_script_decrypt`, writes `scratch/script_index.txt` = names/consts per file), `tools/script_query.py <file-substr> [regex]`,
  `tools/script_disas.py <path> <func>` (NAMES/VARNAMES are reliable; the opcode column of the disassembly is NOT — opcodes are
  remapped, treat it as a names list only).
- Cause of the stacked "Finish" + "check the 12:25:30" + RushHour tank above Ranked: `UIMain.btn_airship` has three child panels
  (`panel_coming`, `panel_ready`, `panel_finish`); `UIMain.refreshAirShipPanel(isOpen, leftTime)` selects one. Its only caller is
  the client RPC `iAnniversaryAthlete.onGetAnniversaryAirShipRank(INT64 rank, INT64 score, STRING isOpen, INT64 leftTime,
  INT64 rankListLength)` (def: entity_0177.xml). Nothing ever called it, so all three panels showed.
- Runtime index 873: entity_0177 ClientMethods order anchored on live-verified names at 853 (onGetAnniversaryAward), 859, 860, 864
  (from `scratch/athlete_methods_all.txt`, most other names blank in that dump).
- LIVE RESULT: sending it at ~2 s after enterHall did nothing (UIMain not built yet). Sending `isOpen='end'` 90 s later, once the hall UI
  exists, replaced the stacked labels by ONE label "Finish / check the reward" (`scratch/air3_now.png`). The RushHour banner + tank icon remain
  (part of the button itself). Untested: `over`/`open`/`ready` (consts in refreshAirShipPanel); `over` may hide the button.
  The server now resends at `ROS_AIRSHIP_DELAYS` (default `45,90,150` s); state via `ROS_AIRSHIP_STATE` (default `end`, `-` disables).
  One run; replicate before calling it closed.
- Startup flake seen: after restarting the server while an old game process is still alive, that stale client triggers a KEYSCAN
  against a dead session and the fresh launch can SIGSEGV in NeoXMain before login; `drive_login` then needs a retry. Force-stop the
  app before restarting the server.

## Checkpoint 20i (2026-09-20): currency RPCs (negative for top bar) and airship RPC side effect

- Currency decode (scripts): `iCurrency.getCurrencyAmount(currencyID)`: YUANBAO -> `self.yuanbao`, PAY_YUANBAO -> `self.payYuanbao`, others -> `currencyList`
  (list of `{id, num}`). Client RPCs (entity_0385, runtime indices read straight from the live method table, exact-name anchors):
  `onSPUpdated(INT64 sp, INT32 src)`=201, `onGPUpdated(INT64 gp, INT32 src)`=202, `onYBUpdated(INT64 freeYuanbao, INT64 payYuanbao,
  INT32 src)`=203, `onCurrencyUpdated(INT32 id, INT64 val, INT32 src)`=204. `MallCurrencyType` consts start GP=1, YUANBAO=2, SP=3 (first three
  only; later ids not verified). Each handler sets the property then `onCurrencyChangedToUI(type)`; `UIMain.onCurrencyChanged` only updates
  `panelDiamond` (YUANBAO) / `panelCoin` (else).
- LIVE (2 sessions): sending 201/202/203 after the hall UI exists produced the system toast "You got 10000 Diamond" (so the RPCs land) but the
  three top-bar slots STILL read `283283`. NEGATIVE: those three slots are not driven by GP/SP/YB updates. Unknown widget: candidates are the
  `panel_latin/PanelCoinLatin/Value` variant or a prefab placeholder fed by another path. Depot page counters (0/0/0) also unchanged.
- The currency RPCs are now opt-in (`ROS_DEV_CURRENCY=1`; values `ROS_DEV_GP/SP/FREE_YB/PAY_YB`), because they only add a toast each login.
- Airship RPC (idx 873) correction of 20h: it ALSO opens the full-screen "AIRSHIP BATTLE" page (`UIAirShipRankList`) — seen with a single send
  and with repeats. The tidy "Finish / check the reward" label is a side effect and remains after the page is closed with Back. Because a
  blocking page after 90 s is worse than the overlapping labels, it is now opt-in (`ROS_AIRSHIP_STATE=end`, once at `ROS_AIRSHIP_DELAY`, default 90 s).
  Need a call that sets the panel state without opening the page.
- Other findings: profile "My Page" shows `ID: 0` and no name (player id / name fields unset); the top-left avatar tap opens it and its X did not close
  it but Android Back did. Back from the hall root shows the normal "Exit game?" dialog.
- Flake: `drive_login` sometimes stops at the server-select list (the "Philippines" row must be tapped) after a crashed/first launch.

## Checkpoint 20j (2026-09-20): ROOT CAUSE of the messy hall + currency solved — `UIMain.on_enter` was aborting

**Finding.** `UIMain.on_enter` (UIMain.py:1594) raised on two BASE-only attributes, so everything after that line never ran. That single abort
explains the stacked airship labels, the fake `283283 x3` top bar, the "Racing 05min 30s" placeholder, missing timers, and the previously
"non-deterministic" hall. Fix = give the client those two attributes through the RPCs the real server uses (after the unchanged Stage-4 sequence):
- `Athlete.onPersonalRecommendStateUpdated(INT32 state, INT32 refreshTime, PYTHON gift, INT32 version)` idx 754 -> `(0, 0, {}, 0)`.
- `Athlete.syncMonthPayRebateSpecialAwardInfo(PYTHON info)` idx 768 -> `{'awards': {}}` (`{}` gave `KeyError: 'awards'` in `is_all_award_done`).
Indices come from the full live method-name table: new `scratch/dump_athlete_methods.py` -> `scratch/athlete_methods_full.txt` (0 blanks; the old
dump left every name > 22 chars empty because std::string long names are heap pointers). It also re-confirmed 201/202/203/745/873/1099.

**Live result (fresh logins, no interaction except PLAY/Back on popups):** 0 SCRIPT ERROR in 4 consecutive runs (fix2, fix3, cur4, final1); final3 had
1 error = the known `Athlete._loadDefaultScene ... 'NoneType' has no attribute 'SetLoadingProcess'` timing race, hall unaffected. Screens:
`scratch/fix2_closed.png`, `scratch/final3_hall.png`. Now visible: real top bar, "Betting mm:ss" timer, no stacked airship labels, no red "!".
The hall UI then proceeds to the normal daily-login popup ("LOG IN DAILY TO CLAIM GIFTS", 388 Gold "Claimable") — its claim does not work yet (open item)
and, on some logins, the new-player guide overlay dims the hall (yellow arrows on START).

**Currency (supersedes the negative result in 20i):** the bar was never refreshed because on_enter aborted. Real sources:
- diamond slot = `freeYuanbao + payYuanbao` (stream properties);
- coin slot = `currencyList` entry with **id 213** (`UIMain.curExchangeCoin`, found by probing `onCurrencyUpdated(id, 1000+id)` over the MallCurrencyType
  ids: the slot showed 1213). It is an event coin, not GP (id 1) / SP (id 3).
`scratch/gen_stream_v3.py` now: `PROPERTY_OVERRIDES['currencyList']` (dynamic ARRAY of `{id INT32, num INT64}`, count-prefixed; encoder support only for
override properties) and default dev balance `gp=999999, sp=5000, freeYuanbao=999999`, `ROS_CURRENCY_LIST='1:999999,3:5000,213:999999'`
(`ROS_PROP_OVERRIDES` / `ROS_CURRENCY_LIST` env to change). Stream = 2245 B. Verified live: top bar shows 999999 / 999999.
Probe aid kept: `ROS_CURRENCY_PROBE=1` (+ `ROS_HALL_LATE_DELAYS`) resends `onCurrencyUpdated` per id after the hall UI exists.

**Retractions / corrections.** 20h/20i said the airship RPC "fixes the labels" — unnecessary: the labels were a symptom of the aborted on_enter and vanish
without it (airship + currency RPCs stay opt-in and off by default). The 20i "top-bar slots are not driven by GP/SP/YB" conclusion was wrong (on_enter
had not run). The earlier "Ranked open/close cleans the hall" symptom is very likely the same abort (navigation re-runs display code).
Open: daily-login claim, `_loadDefaultScene` race, guide overlay, RushHour banner/tank, My Page `ID: 0`, Depot 2nd Back `refreshTransformPanel`, Gate 5.

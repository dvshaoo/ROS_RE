# ROS v1117219 — `neox::bwclient::LogOnParams::addToStream` Binary Analysis

This document supersedes the speculative field table in `MERCURY_LOGIN_FLOW.md` §2 for
`LogOnParams`. Everything below was derived directly from disassembly of
`03_lib/libclient_arm64.so` (ARM64, no PIE/ASLR-relative section — file offset == virtual
address for `.text`/`.rodata` in this build, confirmed via ELF section headers: `.text`
`addr=0x809200 offset=0x809200`, `.rodata` `addr=0x2a38670 offset=0x2a38670`).

The binary is fully stripped of `.symtab` (only `.dynsym` remains, 30,863 entries — all 58
named entries are JNI `Java_...` exports; **zero** `bwclient`/`Mercury`/`LogOn` symbols are
exported). Every class/function name in this document was therefore recovered from a
**mangled RTTI typeinfo string** or a **hardcoded log/assert string**, located by literal
byte search, then traced to code via an `ADRP`+`ADD` cross-reference scanner
(`scratch/xref_addtostream.py`). This is a materially different (and stronger) evidence
method than the previous report used, which did not show its address-derivation method.

## 1. Function Identification

- **Evidence string**: `"LogOnParams::addToStream publicEncrypt failed \n"` at rodata
  offset `0x2a62d6a`.
- **Sibling string**: `"LogOnParams::readFromStream privateDecrypt failed \n"` at
  `0x2a62d9a` (confirms a symmetric `readFromStream` exists, used to decode the plaintext
  after RSA decryption — almost certainly server-side code also compiled into this same
  engine library, or unit-test/verification code kept in the client build).
- **RTTI confirmation**: mangled typeinfo name `N4neox8bwclient11LogOnParamsE` found at a
  separate rodata location — confirms the class `neox::bwclient::LogOnParams` genuinely
  exists (not a guess).
- **Xref scan result**: both strings have exactly **one** cross-reference each in `.text`:
  - `0x9d82f0` → `adrp x0,#0x2a62000 / add x0,x0,#0xd6a` (publicEncrypt failed)
  - `0x9d8614` → `adrp x0,#0x2a62000 / add x0,x0,#0xd9a` (privateDecrypt failed)

| Item | ARM64 address | Confidence |
|---|---|---|
| `LogOnParams::addToStream` function start | `0x9d8014` | CONFIRMED (prologue: `sub sp,sp,#0xc0`; stack-canary via `mrs x26,tpidr_el0`; saves x19–x28) |
| `LogOnParams::addToStream` function end (`ret`) | `0x9d8358` | CONFIRMED |
| Function size | `0x344` bytes (836 bytes) | CONFIRMED |
| `LogOnParams::readFromStream` start | `0x9d838c` (prologue `sub sp,sp,#0x90` at `0x9d8390`) | CONFIRMED |
| `LogOnParams::readFromStream` end (`ret`) | `0x9d8674` | CONFIRMED |
| Callers | not yet enumerated (would require scanning for `bl #0x9d8014`) | UNKNOWN — see §6 |

ARMv7 (`01_apk/base_decompiled/lib/armeabi-v7a/libclient.so`) cross-check was **not**
performed for this specific function due to time budget — flagged as a follow-up in §7.

## 2. Function Signature (recovered from register usage)

```
bool LogOnParams::addToStream(
    LogOnParams *this,          // x0
    BinaryOStream &stream,      // x1
    uint8 flagsOverride,        // w2  (sentinel 0xFF = "use this->flags_ instead")
    PublicKey *pKey             // x3  (NULL = write plaintext, non-NULL = RSA-encrypt)
) const;
```

Return value (`w0`, boolean) is 1 on success, 0 if RSA encryption failed.

**CONFIRMED** — this 4-argument shape, not the 2-argument
`addToStream(BinaryOStream&, isReconnect)` assumed by public BigWorld SDK references. This
client's build has diverged from stock BigWorld (expected, given NetEase/ROS forked NeoX
engine).

## 3. Object Layout of `LogOnParams` (recovered from offset accesses)

| Offset | Field | Type | Evidence |
|---|---|---|---|
| `+0x0c` | `flags_` | `uint8` | `ldrb w22,[x21,#0xc]` — loaded only when caller passes sentinel `0xFF` in w2 |
| `+0x10` | string A (libc++ SSO `std::string`, 0x18 bytes) | `std::string` | SSO-aware read: `ldrb [x21,#0x10]` (control byte), inline buffer at `+0x11`, long-form ptr/len at `+0x18`/`+0x20` |
| `+0x28` | string B | `std::string` | identical SSO pattern, offset +0x18 from string A |
| `+0x40` | string C | `std::string` | identical SSO pattern, offset +0x18 from string B |
| `+0x58` | `uint32` numeric field | `uint32` | `ldr w21,[x21,#0x58]` |
| `+0x5c` | 16-byte blob (digest-sized) | `uint8[16]` | `ldur q0,[x21,#0x5c]` (single 128-bit load) — only serialized if `flags_ & 1` |

**CONFIRMED**: object layout above (offsets, sizes, SSO-string detection logic).
**INFERRED** (not visible in binary — no field names survive stripping): which named
BigWorld/game concept maps to string A/B/C. Candidates, in order of plausibility given the
known login flow (`ROS_LOGIN_PLAY_TRACE.md`) and NetEase UniSDK/MPay integration:
  - String A → username/account id
  - String B → password / UniSDK session token
  - String C → a third credential blob (NetEase MPay `sdk_token` or device/channel string) —
    **do not assume this is the entity-defs digest**; the digest is the separate 16-byte
    field at `+0x5c`, serialized independently and conditionally.

Do not upgrade these three labels to CONFIRMED without a dynamic capture (Frida hook on
`0x9d8014`) or a matching MITM packet capture correlated with known login field values.

## 4. Exact Serialization Algorithm (addToStream body, `0x9d8014`–`0x9d8358`)

```
1.  entry(this, stream, flags, pKey)
2.  flags_byte = (flags == 0xFF) ? this->flags_ : flags
3.  IF pKey != NULL:
        out = <local stack MemoryOStream>      ; plaintext accumulates HERE, not in `stream`
    ELSE:
        out = stream                            ; direct passthrough, unencrypted
4.  out.write_u8(flags_byte)                                          -- Field #1
5.  write_bw_string(out, this->stringA /* +0x10 */)                   -- Field #2
6.  write_bw_string(out, this->stringB /* +0x28 */)                   -- Field #3
7.  write_bw_string(out, this->stringC /* +0x40 */)                   -- Field #4
8.  IF pKey != NULL:
        ok = RSA_multiblock_encrypt(pKey, dst=stream, src=out)         -- see §5
        IF !ok:
            log("LogOnParams::addToStream publicEncrypt failed")
            return false
9.  IF flags_byte & 1:
        stream.write_raw(this->digest /* +0x5c, 16 bytes */)          -- Field #5 (conditional)
10. stream.write_u32(this->numericField /* +0x58 */)                  -- Field #6
11. return true
```

### `write_bw_string(stream, s)` — length-prefix encoding (CONFIRMED, used identically 3×)

```
len = s.length()          ; SSO-aware: short-string byte>>1, or long-form size field
IF len >= 0xFF:
    stream.write_u8(0xFF)
    stream.write_u24_le(len)     ; 3-byte extended length, little-endian
ELSE:
    stream.write_u8(len)
stream.write_raw(s.data(), len)
```

This is a classic BigWorld/Mercury variable-length string encoding: 1-byte length with an
0xFF escape to a 3-byte (24-bit) extended length. **CONFIRMED** directly from the
`cmp w24,#0xff / b.lt small` branch structure, duplicated identically at all three string
sites (`0x9d80ec`, `0x9d8180`, `0x9d8214`).

## 5. RSA Encryption Block — Field-Level Findings

**This corrects/sharpens the previous report, which only said "RSA-1024 / RSA-2048
PKCS#1 v1.5" without evidence.**

The encryption call is `bl #0x997160` at `0x9d82dc`, called only when `pKey != NULL`.
Disassembly of `0x997160`–`0x997244`:

```
0x9971b0:  sub  w27, w23, #0x2a     ; chunkSize = RSA_size(key) - 0x2A (42 decimal)
...
0x997200:  mov  w4, #4              ; padding mode = 4
0x99720c:  blr  x19                 ; call(len=w0, in=x1, out=x2, key=x3, padding=w4)
0x997224:  cbnz w0, #0x9971b4       ; loop while there is more plaintext to chunk
```

- **`chunkSize = RSA_size(key) - 42`**: 42 = `2*SHA-1_len(20) + 2`, which is exactly the
  **RSA-OAEP** overhead formula, *not* the PKCS#1 v1.5 overhead (which is 11 bytes). If this
  build used PKCS#1 v1.5 the subtracted constant would be `0x0B`, not `0x2A`.
- **`w4 = 4`** is passed as the padding-mode argument into the encrypt call. OpenSSL's
  `RSA_*_PADDING` enum has `RSA_PKCS1_OAEP_PADDING == 4` (`RSA_PKCS1_PADDING=1`,
  `RSA_SSLV23_PADDING=2`, `RSA_NO_PADDING=3`, `RSA_PKCS1_OAEP_PADDING=4`). The literal `4`
  appearing at exactly this call site is strong corroborating evidence.
- **Multi-block chunking loop**: the plaintext (flags+3 strings) is encrypted in
  `RSA_size(key) - 42`-byte chunks, each producing one RSA block of ciphertext
  (`RSA_size(key)` bytes), all chunks concatenated into the output stream. This means the
  wire format is **not** "one RSA block" — it's **N concatenated RSA blocks**, where N =
  `ceil(plaintext_len / (RSA_size - 42))`. A decoder must know `RSA_size(key)` (from the
  public key modulus length) to split the ciphertext back into blocks.

| Finding | Confidence |
|---|---|
| Padding is RSA-OAEP (not PKCS#1 v1.5) | STRONG EVIDENCE (two independent numeric tells: `-42` chunk math and `w4=4` OpenSSL enum literal, at the exact call site) |
| OAEP hash function is SHA-1 (giving 42-byte overhead) | INFERRED — the `-42` constant matches SHA-1 OAEP; OpenSSL's `RSA_public_encrypt` OAEP path defaults to SHA-1 unless a `_ex`/EVP variant with alternate MGF1 hash is used. Would need to trace which OpenSSL entrypoint `x19`/`blr` resolves to (function pointer, not directly named) to be fully certain. |
| Encryption is chunked/multi-block, not single-block | CONFIRMED (loop structure with `cbnz w0,...` at `0x997224`) |
| Only `{flags, stringA, stringB, stringC}` are inside the RSA-encrypted region — the digest (`+0x5c`) and the trailing `uint32` (`+0x58`) are **always sent in the clear**, appended after the ciphertext | CONFIRMED (steps 9–10 in §4 execute unconditionally after the `pKey` branch merges, operating on `stream` directly, never on `out`) |
| **Key size is RSA-2048** | **CONFIRMED BY DYNAMIC CAPTURE (2026-09-14)** — a real `LogOnParams` UDP packet was captured from the live client (see `PLAY_TO_BASEAPP_CAPTURE.md` §2): total packet 273 bytes = 15-byte header + **256-byte ciphertext block** + 2-byte footer. 256 bytes = `RSA_size()` for a 2048-bit modulus exactly. This was previously unknown from static analysis alone (only the padding scheme, not the key size, had been determined) and resolves that gap. |

This directly contradicts the previous report's implication that "the logon bundle" as a
whole is RSA-encrypted — only 4 of the 6 fields are, and the entity-defs digest / numeric
field travel in plaintext.

## 6. `readFromStream` Cross-Check (`0x9d838c`–`0x9d8674`)

Symmetric read confirms field **order** and **offsets** independently of the write path
(this function reads directly into object fields, with no decryption step visible inside
it — implying decryption happens earlier, before the plaintext bytes reach this call, most
likely server-side or in a separate `privateDecrypt` helper referenced by the sibling error
string at `0x2a62d9a`):

1. `u8` → `this+0xc` (flags_)
2. length-prefixed string (same 1-byte/0xFF+3-byte scheme) → `this+0x10` (string A)
3. length-prefixed string → `this+0x28` (string B)
4. length-prefixed string → `this+0x40` (string C)
5. `IF flags & 1`: 16 raw bytes → `this+0x5c`
6. `u32` → `this+0x58`

This is **CONFIRMED** identical ordering to the write path, which is the strongest possible
internal-consistency check available without a live capture.

### 6a. Cross-Check: Captured Packet Is a Single RSA Block (2026-09-14)

The captured packet (§ above, `PLAY_TO_BASEAPP_CAPTURE.md` §2) contains exactly **one**
256-byte ciphertext block, not several concatenated blocks — meaning the plaintext
(`flags` + 3 strings) fit within `RSA_size - 42 = 256 - 42 = 214` bytes for this login
attempt (a fresh Guest session with short/empty credential strings), consistent with the
multi-block chunking design in §5 without needing to exercise it. A separate 4-byte field
immediately before the ciphertext in the captured packet (`0x2b000000` = 43, LE) is a
plausible candidate for a plaintext-length indicator (43 is in the right range: 1 flags byte
+ three short length-prefixed strings), but this is **STRONG EVIDENCE, not CONFIRMED** —
it could equally be an unrelated Mercury framing field. See `PLAY_TO_BASEAPP_CAPTURE.md` §2
for the full byte-level breakdown and confidence labels.

## 7. Still Unresolved

1. **String A/B/C semantic identity** (username vs. password vs. third field) — UNKNOWN,
   needs dynamic instrumentation (Frida) or a correlated MITM capture.
2. **OAEP hash function** (SHA-1 assumed from the `-42` overhead, not directly named) —
   INFERRED only.
3. **Callers of `addToStream`** (i.e., where `logOnBegin` populates the `LogOnParams`
   object before calling this) — not traced yet; requires scanning `.text` for
   `bl` targeting `0x9d8014` (relative encoding, straightforward follow-up).
4. **ARMv7 cross-check** — not performed; the ARM64 findings above have not yet been
   confirmed against `01_apk/base_decompiled/lib/armeabi-v7a/libclient.so`.

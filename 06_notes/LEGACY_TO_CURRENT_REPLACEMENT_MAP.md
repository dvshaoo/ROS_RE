# ROS-Legacy / PC-Launcher Mechanism -> Current (Android) Project Mapping

Labels (this pass's own set): **CONFIRMED** / **INFERRED** / **HYPOTHESIS** /
**BLOCKED**. Classification key: **A) directly reusable**, **B) adaptable**,
**C) obsolete**, **D) not applicable**.

Source documents: `07_ros_legacy_approach/ROS_LEGACY_APPROACH_STUDY.md`,
`07_ros_legacy_approach/PC_LAUNCHER_STUDY.md`.

| Mechanism | ROS Legacy / PC source | Classification | Notes for this project |
|---|---|---|---|
| Auth / SDK login | ROS Legacy: local HTTP responder mimicking NetEase SDK endpoints | **A** directly reusable | Already implemented (`mitm/mitm_serve.py`, `mitm/session_store.py`) — CONFIRMED working, E2E-001. |
| Session identity | ROS Legacy: server-minted opaque session token | **A** directly reusable | `sess_<uuid4hex>` scheme already matches this pattern; no change needed. |
| Server discovery / server-list | ROS Legacy: local server-list substitution pointing at operator's own LoginApp | **A** directly reusable | Already implemented and CONFIRMED (client's LogOnParams do arrive at the local IP:port). |
| RSA public-key trust | PC launcher: patch the client's baked-in trusted public key via Frida (`inject_rsa2.py`), so the operator's own keypair can decrypt LogOnParams | **B** adaptable, in principle | Android equivalent (locate RSA modulus/exponent constants in `libclient_arm64.so` rodata, substitute at runtime) was **not yet attempted** on this project — flagged in `LOGONPARAMS_BLOWFISH_KEY_RECHECK.md` §5 as unstarted follow-up. Blocked in practice this pass by the same Frida-gadget classifier block that stopped script.npk work (see `PRIVATE_SERVER_REPLACEMENT_STATUS.md`). |
| Blowfish session-key acquisition | PC launcher: read 3rd packed string out of the decrypted LogOnParams blob (CONFIRMED, live-verified on PC) | **B** adaptable, HYPOTHESIS on Android | Structural match confirmed this pass (`LOGONPARAMS_BLOWFISH_KEY_RECHECK.md` §1) — same field-count/order. Not yet live-confirmed on Android; depends on the RSA-key-trust item above being solved first (need to decrypt the blob to read stringC at all). |
| Mercury reply-ID correlation bug | PC launcher: found via live sweep that the field was a uint32 at a different byte offset than assumed | **B** adaptable (method, not the specific offset) | PC byte offsets do NOT transfer (different binary/platform). The **method** — sweep candidate offsets/widths against a live client and use its own retry-vs-proceed behavior as ground truth — is exactly what this project's own current top-priority NEXT_ACTION now calls for (`PRIVATE_SERVER_REPLACEMENT_STATUS.md` item 1), since the previously-documented Android offset (`[5:7]`) is now CONFIRMED (E2E-002) not to be the real key. |
| Reply-envelope shape discovery | PC launcher: `ROS_REPLY_SWEEP` mode cycling 10 candidate framings, client's own behavior as oracle | **A** directly reusable as a *technique* | This project's `local_baseapp_capture.py` already has an `ATTEMPT_J`-style flag pattern (disproven hypotheses kept, gated, documented) — the same sweep-and-observe harness style should be extended for the reply-ID offset search (item above), not reinvented. |
| Client-side script/state patching for downstream crashes (`Globals.channel` stub) | PC launcher: Frida-based live monkey-patch of the embedded Python namespace, not a binary patch | **D** not applicable yet | This project has not reached the equivalent stage (BaseApp/Account/Avatar) where such a stub would be needed — downstream of the still-unresolved LoginApp blockers. Revisit once BaseApp is reached; the PC lesson (§2b of `PC_LAUNCHER_STUDY.md`) is that the network protocol layer does not need to be protocol-perfect if the client's own script glue can be patched for the specific downstream null-reference case — directly consistent with this project's own already-authorized script.npk-patch approach, just currently tool-blocked (see status doc). |
| Gateway/session handling, BaseApp transition, account/avatar creation, lobby init | PC launcher: real local BaseApp UDP server + minimal Account/Avatar objects; explicitly UNRESOLVED beyond login (native crash on real entity creation, root cause never found) | **D** not applicable yet, **C** partially obsolete as a target to imitate | This project has not reached BaseApp. The PC launcher's own gameplay-entry crash (root cause never found, explicitly flagged "do not re-enable without... a fundamentally different approach") is a cautionary data point, not a design to copy — **when this project eventually reaches BaseApp/Account/Avatar, treat "login accepted" and "gameplay entry" as two separate milestones with independently possible failure modes**, per `PC_LAUNCHER_STUDY.md` §5 lesson 5. |
| Blowfish cipher chaining mode (non-standard CBC-over-previous-plaintext, IV=0) | PC launcher: independently reverse-engineered from PC disassembly | **D** not applicable as data, **B** adaptable as a warning | PC-specific bytes/offsets don't transfer, but the general lesson (verify actual chaining mode from Android disassembly rather than assuming textbook CBC/ECB, even once/if a key is obtained) is directly relevant and should be checked before any Android server-side Blowfish implementation is written. Not yet done — flagged for whenever key acquisition is unblocked. |

## Summary

Of the 9 mechanisms studied, **3 are directly reusable as-is** (already
implemented and confirmed working: SDK auth, session identity, server
discovery), **4 are adaptable in method or design but require new
Android-specific work** (RSA-key-trust substitution, Blowfish-key
acquisition via the 3rd-string hypothesis, reply-ID sweep methodology,
client-script patching for future downstream crashes), and **2 are not yet
applicable** (BaseApp/Account/Avatar/Lobby design lessons, cipher-chaining
verification) because this project has not reached the corresponding stage.
No mechanism from either source was classified as fully **C) obsolete** for
this project's purposes — even the PC launcher's own unresolved
gameplay-entry crash is retained as a cautionary lesson, not discarded.

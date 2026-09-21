# Store routing probe — 2026-09-21 (corrected)

The initial inference in this note was wrong and is retained only to prevent a
future regression: live packet capture proves that exposed index `312` carries
no arguments and means `queryAvailableMallGoods`; exposed index `310` carries
the five-byte UINT32 location payload and means
`queryAvailableMallGoodsByType`.  The current `_STORE_EXPOSED` mapping follows
that observed wire shape.  The Store query reply was observed live as 670
goods from four client tables.

This Store mapping is separate from the Athlete Stage-3 property stream.  It
must not be blamed for a hall with `283283`, a blank model, duplicate panels,
or `Leave Team`; those symptoms mean the player stream was absent or invalid
during entity creation.

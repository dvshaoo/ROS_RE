# AGENT BRIEF — basahin ito bago gumalaw (token-efficient RE)

Ikaw ang WORKER. Ang mabibigat na scan ay gawa na ng ibang session (nasa 06_notes/).
Trabaho mo lang: maliliit na scoped tasks, sunod-sunod, walang sayang na token.

## HARD RULES (tipid = batas)

1. HUWAG basahin nang buo ang dex/.so/.obb/NPK. Max 200 lines per read, targeted windows lang.
2. HUWAG mag-glob ng `**` o mag-grep nang walang filename filter. Laging may path + pattern.
3. Gamitin muna ang 06_notes/ — kung nandoon na ang sagot, HUWAG i-re-scan.
4. Isang task, isang finding. Stop pagkatapos ng isang finding; i-report, hintay ng next.
5. Bawat finding = value + source `file:line` + versionCode. Walang citation = hula = bawal.
6. Bawal mag-decide ng malaki (bagong tool, burahin, i-rewrite). Itanong muna.
7. Bawal kopyahin mula sa ibang version o ibang project. Per-version lahat.

## CHEAP COMMANDS (ito lang ang gamitin sa malalaking files)

- `strings <file> | Select-String "<keyword>"` — hindi buong read
- `Select-String -Path "<exact dir>\*" -Pattern "<keyword>"` — may exact dir
- `Get-ChildItem <dir> | Measure-Object` — census bago galaw
- Bawal: full decompile, full unzip ng OBB nang walang tanong

## TASK QUEUE (sunod-sunod, isa lang per run — PASS/FAIL bawat isa)

- [ ] T01: Census — ilista ang laman ng 01_apk/02_dex/03_lib/04_obb (names+sizes lang, 10 lines max sa note)
- [ ] T02: UniSDK endpoints — hanapin sa dex strings: `unisdk`, `drpf`, `/api/users/login/guest` → note: exact strings + file
- [ ] T03: drpf POST fields — header/query keys lang (jf_gameid, deviceid, …) → note: listahan
- [ ] T04: BigWorld logOn — `ServerConnection`, `logOn`, loginapp host/port strings → note
- [ ] T05: Server-list URL — `ServerListURL`, `getServerList` → note: exact string + file
- [ ] T06: Entity defs — Account/Athlete `.def`/`entities.xml` order: property list order + method declaration order → note (order lang, hindi UID)
- [ ] T07: Enum numerics — `LoginRetCode`, `ChannelLoginRetEnum` values → note o BLOCKED kung wala
- [ ] T08: channelInfo closure — ano ang hinihintay ng client pagkatas ng logOn (strings around `channelInfo`) → note

## OUTPUT FORMAT (bawat task, ganito lang — maikli)

TASK: T0x
FINDING: <one-line value>
SOURCE: <file>:<line>
VERSION: 1.610377.506841 / vCode 1117219
STATUS: PASS | FAIL | BLOCKED-<why>

## STOP CONDITIONS

- Task tapos na → stop, report, hintay.
- Kailangan ng file na wala pa → BLOCKED, stop.
- Gusto nang mag-scan ng buong dex/so → STOP, itanong muna.

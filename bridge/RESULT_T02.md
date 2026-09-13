TASK: T02
FINDING:
  (a) drpf host URL      : https://drpf-h45na.proxima.nie.easebar.com
  (b) guest-login endpoint: /api/users/login/guest
  (c) server-list        : ServerListURL key confirmed (no literal URL value in scan — runtime-set or inside .so/OBB)

DETAIL:
  ## drpf
  - Host: https://drpf-h45na.proxima.nie.easebar.com  [02_dex\classes.dex]
  - Prefix also seen: https://drpf-                   [02_dex\classes.dex]
  - Class: Lcom/netease/ntunisdk/AdvDrpf;             [02_dex\classes.dex]
  - Const key: UNISDK_DRPF_URL                        [02_dex\classes.dex]

  ## guest
  - Endpoint: /api/users/login/guest                  [02_dex\classes.dex]
  - Also found: /api/users/migrate/client/guest_guidance [02_dex\classes.dex]
  - Also found: /api/users/migrate/v2/guest_generate_code [02_dex\classes.dex]
  - Flag param: &is_unisdk_guest=1                    [02_dex\classes.dex]

  ## serverlist
  - Key strings present: ServerListURL, getServerList, getServerlisturl,
    ntSetServerListURL, ntSetServerListURLwithNative, serverlisturl,
    setServerlisturl, showServerListDialog              [02_dex\classes.dex]
  - No literal URL value in dex scan — likely passed from .so or OBB config.

SOURCE: 06_notes/UNISDK_SCAN.md:§drpf (line 47) / §guest (line 92) / §serverlist (lines 108-119)
        dex file: 02_dex\classes.dex
VERSION: 1.610377.506841 / vCode 1117219
STATUS: PASS (a+b confirmed; c key confirmed, URL value BLOCKED-not-in-dex-strings)

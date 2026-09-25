#!/bin/bash
# Reapply everything that LDPlayer wipes on every VM reboot/restart, before testing.
# Run this (via Git Bash) any time the emulator has just been restarted and traffic
# stops reaching mitm/local_baseapp_capture.py ("Failed to retrieve patches",
# "Slow connection", or the game just sits at a blank/stuck screen).
#
# Consolidated from scattered handoff notes on 2026-09-25:
#   06_trace/FRIDA_BASEAPP_LOGIN_CAPTURE.md, scratch/HANDOFF_PROMPT_2026-09-18.md,
#   06_notes/HANDOFF_TO_CHATGPT_STORE_DRAW.md (DNAT rules)
#   -- plus the srv.crt system-CA overlay, root-caused live this session, not
#   previously written down anywhere.
set -e
ADB="/c/LDPlayer/LDPlayer9/adb.exe"
SER="-s emulator-5554"

echo "[1/4] waiting for device..."
$ADB $SER wait-for-device

echo "[2/4] adb root + reapply iptables DNAT (80/443/8443 tcp, 25000/20013 udp -> 172.16.1.2)..."
$ADB $SER root
sleep 1
$ADB $SER shell "iptables -t nat -F OUTPUT
iptables -t nat -A OUTPUT -p tcp --dport 80    -j DNAT --to-destination 172.16.1.2:80
iptables -t nat -A OUTPUT -p tcp --dport 443   -j DNAT --to-destination 172.16.1.2:443
iptables -t nat -A OUTPUT -p tcp --dport 8443  -j DNAT --to-destination 172.16.1.2:8443
iptables -t nat -A OUTPUT -p udp --dport 25000 -j DNAT --to-destination 172.16.1.2:25000
iptables -t nat -A OUTPUT -p udp --dport 20013 -j DNAT --to-destination 172.16.1.2:20013"

echo "[3/4] reinstall srv.crt as a system-trusted CA (tmpfs overlay on /system/etc/security/cacerts)..."
echo "      root cause: mpay_oversea SDK and other bundled 3rd-party SDKs use standard"
echo "      Android TLS validation and reject our self-signed cert -- unlike the game's"
echo "      own NeoX HTTP client, which trusts everything unconditionally. Without this,"
echo "      the mpay login/config-fetch calls fail with a TLS certificate_unknown alert,"
echo "      which is what actually produces the 'Slow connection' dialog + broken age-gate"
echo "      responses (2026-09-25 investigation, 06_notes/GATE7_BATTLE_GAMEPLAY_PLAN.md)."
# Install both CA root and server cert
CA_HASH=$(openssl x509 -inform PEM -subject_hash_old -in /c/Users/Raysoo/Downloads/ROS_RE/mitm/ca_v3.crt -noout)
SRV_HASH=$(openssl x509 -inform PEM -subject_hash_old -in /c/Users/Raysoo/Downloads/ROS_RE/mitm/srv.crt -noout)
$ADB $SER shell "mkdir -p /data/local/tmp/cacerts_overlay && cp -a /system/etc/security/cacerts/. /data/local/tmp/cacerts_overlay/"
$ADB $SER push /c/Users/Raysoo/Downloads/ROS_RE/mitm/ca_v3.crt //data/local/tmp/cacerts_overlay/$CA_HASH.0
$ADB $SER push /c/Users/Raysoo/Downloads/ROS_RE/mitm/srv.crt //data/local/tmp/cacerts_overlay/$SRV_HASH.0
$ADB $SER shell "chmod 644 /data/local/tmp/cacerts_overlay/*.0"
$ADB $SER shell "mount -t tmpfs tmpfs /system/etc/security/cacerts"
$ADB $SER shell "cp -a /data/local/tmp/cacerts_overlay/. /system/etc/security/cacerts/"
$ADB $SER shell "chmod -R 644 /system/etc/security/cacerts/*.0; chmod 755 /system/etc/security/cacerts"
$ADB $SER shell "restorecon -R /system/etc/security/cacerts"

echo "[3b/4] bind-mount custom hosts to redirect all easebar/netease domains to 172.16.1.2..."
$ADB $SER shell "
cp /system/etc/hosts /data/local/tmp/hosts
cat << 'EOF' >> /data/local/tmp/hosts
172.16.1.2 g61.gph.easebar.com
172.16.1.2 g61.update.easebar.com
172.16.1.2 gdl.easebar.com
172.16.1.2 g61.patch.easebar.com
172.16.1.2 drpf-h45na.proxima.nie.netease.com
172.16.1.2 static.easebar.com
172.16.1.2 api.easebar.com
172.16.1.2 auth.easebar.com
172.16.1.2 gph.easebar.com
172.16.1.2 unisdk.update.netease.com
172.16.1.2 impression.update.netease.com
EOF
chmod 644 /data/local/tmp/hosts
mount --bind /data/local/tmp/hosts /system/etc/hosts
"

echo "[3c/4] disable IPv6 on guest to prevent CDN bypass..."
$ADB $SER shell "
echo 1 > /proc/sys/net/ipv6/conf/all/disable_ipv6
echo 1 > /proc/sys/net/ipv6/conf/default/disable_ipv6
echo 1 > /proc/sys/net/ipv6/conf/wlan0/disable_ipv6
ip6tables -P OUTPUT DROP 2>/dev/null || true
ip6tables -P INPUT DROP 2>/dev/null || true
"

echo "[3d/4] ensure patchVersion exists..."
$ADB $SER shell "mkdir -p /sdcard/Android/data/com.netease.chiji/files/netease/h45na"
$ADB $SER push /c/Users/Raysoo/Downloads/ros_offline_server_backup/patchVersion //sdcard/Android/data/com.netease.chiji/files/netease/h45na/patchVersion

echo "[3e/4] (skipped) do NOT wipe com.netease.mpay.*.xml here."
echo "      root cause (2026-09-25): deleting these prefs makes j/d/d.g() return null in the"
echo "      MPay SDK, which guarantees shouldAutoLogin=false and triggers the blocking"
echo "      'Invalid login. Please log in again.' dialog on every single cold start."
echo "      See scratch/HANDOFF_PROMPT_CLAUDE.md section 2C. Auto-dismiss is instead handled"
echo "      by launch_game.bat, which taps Confirm the moment MpayActivity appears."

echo "[4/4] verifying..."
echo "  DNAT rules:"
$ADB $SER shell "iptables -t nat -L OUTPUT -n"
echo "  cert installed:"
$ADB $SER shell "ls /system/etc/security/cacerts/$CA_HASH.0 /system/etc/security/cacerts/$SRV_HASH.0"
echo "  hosts ping check:"
$ADB $SER shell "ping -c 1 g61.update.easebar.com"

echo ""
echo "Done. Next: (re)start mitm/local_baseapp_capture.py on the host, then:"
echo "  adb shell am force-stop com.netease.chiji"
echo "  adb shell monkey -p com.netease.chiji -c android.intent.category.LAUNCHER 1"


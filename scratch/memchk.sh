#!/system/bin/sh
# usage: memchk.sh <pid> -- show how many bytes dd can really read from each rw-p region (first 40 regions)
PID=$1
/system/xbin/busybox grep -E "^[0-9a-f]+-[0-9a-f]+ rw-p" /proc/$PID/maps | head -40 | while read range perms off dev inode path; do
  s=${range%-*}; e=${range#*-}
  st=$((0x$s)); en=$((0x$e)); sz=$((en-st))
  n=$(dd if=/proc/$PID/mem bs=4096 skip=$((st/4096)) count=$((sz/4096)) 2>/dev/null | wc -c)
  echo "$range size=$sz read=$n"
done

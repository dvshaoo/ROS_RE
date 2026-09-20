#!/system/bin/sh
# usage: memgrep.sh <pid> <pattern> [perm-regex]  -- count occurrences of pattern per readable region of the process (run via su)
PID=$1; PAT=$2; PERM=${3:- r}
n=0; hits=0
/system/xbin/busybox grep -E "^[0-9a-f]+-[0-9a-f]+ r" /proc/$PID/maps | while read range perms off dev inode path; do
  s=${range%-*}; e=${range#*-}
  st=$((0x$s)); en=$((0x$e)); sz=$((en-st))
  [ $sz -gt 402653184 ] && continue
  c=$(dd if=/proc/$PID/mem bs=4096 skip=$((st/4096)) count=$((sz/4096)) 2>/dev/null | /system/xbin/busybox grep -a -c -- "$PAT")
  n=$((n+1))
  if [ "$c" != "0" ] && [ -n "$c" ]; then echo "HIT $range $perms $c $path"; fi
done
echo SCANDONE

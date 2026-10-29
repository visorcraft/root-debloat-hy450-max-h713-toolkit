#!/system/bin/sh
# Patch stock init_boot_b with Magisk (writes only to /data/local/tmp)
set -e
cd /data/local/tmp/mgk
export PATH="$PWD:$PATH"
export KEEPVERITY=true
export KEEPFORCEENCRYPT=true
export RECOVERYMODE=false
export PATCHVBMETAFLAG=false
sh boot_patch.sh /sdcard/backup/init_boot_b.img
echo "=== patch result:"
ls -la new-boot.img

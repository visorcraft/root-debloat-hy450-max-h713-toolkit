#!/system/bin/sh
# Stage Magisk tooling on-device (armv7 libs are real executables in the APK)
set -e
cd /data/local/tmp
rm -rf mgk && mkdir mgk && cd mgk
unzip -o ../Magisk-v31.1.apk 'lib/armeabi-v7a/*' 'assets/*' >/dev/null
cp lib/armeabi-v7a/libmagiskboot.so magiskboot
cp lib/armeabi-v7a/libmagiskinit.so magiskinit
cp lib/armeabi-v7a/libmagisk.so magisk
cp lib/armeabi-v7a/libinit-ld.so init-ld
if [ -f lib/armeabi-v7a/libmagiskpolicy.so ]; then cp lib/armeabi-v7a/libmagiskpolicy.so magiskpolicy; fi
if [ -f lib/armeabi-v7a/libbusybox.so ]; then cp lib/armeabi-v7a/libbusybox.so busybox; fi
cp assets/* . 2>/dev/null || true
chmod 755 magiskboot magiskinit
echo "=== staged:"; ls -la
echo "=== magiskboot check:"; ./magiskboot 2>&1 | head -5
echo "=== boot_patch.sh head:"; head -30 boot_patch.sh

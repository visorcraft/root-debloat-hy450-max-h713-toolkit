#!/system/bin/sh
set -e
cd /data/local/tmp/mgk
rm -rf v_stock v_new
mkdir v_stock v_new
(cd v_stock && ../magiskboot unpack /sdcard/backup/init_boot_b.img >/dev/null 2>&1)
(cd v_new && ../magiskboot unpack /data/local/tmp/mgk/new-boot.img >/dev/null 2>&1)
echo "=== unpacked files stock:"; ls v_stock
echo "=== unpacked files new:"; ls v_new
./magiskboot cpio v_stock/ramdisk.cpio ls 2>/dev/null | sort > /data/local/tmp/stock.list
./magiskboot cpio v_new/ramdisk.cpio ls 2>/dev/null | sort > /data/local/tmp/new.list
echo "=== top-level ramdisk entry diff (< stock, > new):"
diff /data/local/tmp/stock.list /data/local/tmp/new.list || true
./magiskboot cpio v_stock/ramdisk.cpio "extract init /data/local/tmp/init.stock"
./magiskboot cpio v_new/ramdisk.cpio "extract init /data/local/tmp/init.new"
./magiskboot cpio v_new/ramdisk.cpio "extract .backup/init /data/local/tmp/init.bak" 2>/dev/null || echo "(no .backup/init present)"
echo "=== stock init vs new backup-of-init (must match):"
sha256sum /data/local/tmp/init.stock /data/local/tmp/init.bak 2>/dev/null
echo "=== new init vs staged magiskinit (must match):"
sha256sum /data/local/tmp/init.new /data/local/tmp/mgk/magiskinit
echo "=== kernel files (should be absent in both):"
ls v_stock/kernel v_new/kernel 2>&1 || true

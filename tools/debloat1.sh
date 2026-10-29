#!/system/bin/sh
# HY450 Max debloat batch 1 - reversible (pm enable <pkg> restores)
for p in \
  com.hy.hyotaupdate \
  com.softwinner.update \
  com.htc.hyk_test \
  com.htc.clearmemory \
  com.hy.storeos \
  com.mobisystems.office \
  com.android.music \
  com.softwinner.miracastReceiver \
  com.htc.samescreen \
  com.mphotool.dlna \
  com.mphotool.usbcastserver \
  com.toofifi.lineserver
do
  echo -n "$p: "
  pm disable-user --user 0 "$p"
done
echo "-- disabled now --"
pm list packages -d

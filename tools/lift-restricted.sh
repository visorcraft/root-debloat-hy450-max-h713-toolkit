#!/system/bin/sh
# Lift Android 13 "Restricted settings" block for all user-installed apps,
# so accessibility services / notification listeners can be enabled in the UI.
for p in \
  com.visorcraft.adbwifi \
  com.mphotool.airplay \
  cm.aptoidetv.pt \
  com.visorcraft.settingslauncher \
  com.topjohnwu.magisk \
  com.esaba.downloader \
  com.syncler \
  com.sinema \
  com.cybercat.adbappcontrol.tv \
  org.mozilla.firefox \
  com.spocky.projengmenu
do
  echo -n "$p: "
  appops set "$p" ACCESS_RESTRICTED_SETTINGS allow && appops get "$p" ACCESS_RESTRICTED_SETTINGS
done

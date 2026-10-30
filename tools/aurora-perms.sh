#!/system/bin/sh
# Grant the Aurora Store permissions this TV ROM's Settings cannot.
# Idempotent. No root. Re-run after reinstalling com.aurora.store.
#
# Background Downloads
#   Grant opens android.settings.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS.
#   TvSettings binds that to EmptyStubActivity, which finishes without
#   adding the app to the doze whitelist. Aurora checks
#   PowerManager.isIgnoringBatteryOptimizations, then toasts
#   "Required permissions were denied".
#
# App links
#   Grant opens android.settings.APP_OPEN_BY_DEFAULT_SETTINGS. Nothing
#   resolves that intent here. Aurora checks user selection
#   (DomainVerificationUserState.DOMAIN_STATE_SELECTED, not auto-verify)
#   for play.google.com and market.android.com.
pkg=com.aurora.store
pm path "$pkg" >/dev/null 2>&1 || {
  echo "$pkg is not installed"
  exit 1
}

echo "-- background downloads (doze whitelist) --"
cmd deviceidle whitelist +"$pkg"
cmd deviceidle whitelist | grep -F "user,$pkg," || {
  echo "doze whitelist missing $pkg"
  exit 1
}

echo "-- app links (user selection) --"
pm set-app-links-user-selection --user 0 --package "$pkg" true \
  play.google.com market.android.com || exit 1
pm set-app-links-allowed --user 0 --package "$pkg" true || exit 1
links=$(pm get-app-links --user 0 "$pkg")
printf '%s\n' "$links"
case "$links" in
  *Enabled:*) ;;
  *)
    echo "app links have no Enabled selection"
    exit 1
    ;;
esac
enabled=${links#*Enabled:}
enabled=${enabled%%Disabled:*}
case "$enabled" in
  *play.google.com*) ;;
  *)
    echo "play.google.com is not selected"
    exit 1
    ;;
esac
case "$enabled" in
  *market.android.com*) ;;
  *)
    echo "market.android.com is not selected"
    exit 1
    ;;
esac
echo "ok"

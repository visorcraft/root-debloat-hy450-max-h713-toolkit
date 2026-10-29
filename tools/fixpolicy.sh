#!/system/bin/sh
M=/debug_ramdisk/magisk
$M --sqlite "UPDATE policies SET policy=2 WHERE uid=2000;"
$M --sqlite "INSERT OR REPLACE INTO policies (uid,policy,until,logging,notification) SELECT 2000,2,0,1,0 WHERE NOT EXISTS (SELECT 1 FROM policies WHERE uid=2000);"
echo "-- policies --"
$M --sqlite "select uid,policy,until,logging,notification from policies;"

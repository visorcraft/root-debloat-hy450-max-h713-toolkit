package com.visorcraft.settingslauncher;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.os.Bundle;

// Home-screen tile. Opens TV settings by trying the generic settings action,
// then the TV settings launch intent, then the OEM root activity.
public class MainActivity extends Activity {
    private static final String TV_SETTINGS_PKG = "com.android.tv.settings";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (!tryStart(new Intent("android.settings.SETTINGS"))) {
            Intent launch = null;
            try {
                launch = getPackageManager().getLaunchIntentForPackage(TV_SETTINGS_PKG);
            } catch (Exception ignored) {
            }
            if (launch == null || !tryStart(launch)) {
                Intent explicit = new Intent(Intent.ACTION_MAIN);
                explicit.setComponent(new ComponentName(
                        TV_SETTINGS_PKG, "com.android.tv.settings.MainSettings"));
                tryStart(explicit);
            }
        }
        finish();
    }

    private boolean tryStart(Intent intent) {
        try {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }
}

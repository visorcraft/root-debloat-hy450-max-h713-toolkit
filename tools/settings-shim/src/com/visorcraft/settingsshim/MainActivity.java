package com.visorcraft.settingsshim;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.os.Bundle;
import android.widget.Toast;

// Forwards android.settings.SETTINGS (which this ROM's TvSettings does not
// register for) to the OEM TV settings root activity.
public class MainActivity extends Activity {
    private static final ComponentName TV_SETTINGS =
            new ComponentName("com.android.tv.settings", "com.android.tv.settings.MainSettings");

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            startActivity(new Intent().setComponent(TV_SETTINGS));
        } catch (Throwable t) {
            Toast.makeText(this, "Settings unavailable: " + t.getMessage(), Toast.LENGTH_LONG).show();
        }
        finish();
    }
}

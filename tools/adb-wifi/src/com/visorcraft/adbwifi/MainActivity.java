package com.visorcraft.adbwifi;

import android.app.Activity;
import android.os.Bundle;
import android.widget.Toast;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            AdbUtil.enable(getContentResolver());
            String ip = AdbUtil.localIpv4();
            String message = "Wireless ADB on" + (ip != null ? " – " + ip : "");
            Toast.makeText(getApplicationContext(), message, Toast.LENGTH_LONG).show();
        } catch (SecurityException security) {
            Toast.makeText(
                    getApplicationContext(),
                    "Permission missing – run: adb shell pm grant com.visorcraft.adbwifi android.permission.WRITE_SECURE_SETTINGS",
                    Toast.LENGTH_LONG).show();
        } catch (Exception ignored) {
        }
        finish();
    }
}

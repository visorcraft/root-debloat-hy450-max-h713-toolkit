package com.visorcraft.adbwifi;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;

public class BootReceiver extends BroadcastReceiver {
    private static final long RETRY_DELAY_MS = 20000;

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            return;
        }
        // Wireless ADB can come up after the first boot broadcast. Try now,
        // stay alive with goAsync, and try once more 20 seconds later.
        Context app = context.getApplicationContext();
        tryEnable(app);
        PendingResult pending = goAsync();
        new Handler(Looper.getMainLooper()).postDelayed(new RetryTask(app, pending), RETRY_DELAY_MS);
    }

    private static void tryEnable(Context context) {
        try {
            AdbUtil.enable(context.getContentResolver());
        } catch (Exception ignored) {
        }
    }

    static final class RetryTask implements Runnable {
        private final Context ctx;
        private final PendingResult pending;

        RetryTask(Context ctx, PendingResult pending) {
            this.ctx = ctx;
            this.pending = pending;
        }

        @Override
        public void run() {
            tryEnable(ctx);
            pending.finish();
        }
    }
}

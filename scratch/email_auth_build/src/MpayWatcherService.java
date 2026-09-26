package com.netease.chiji;

import android.accessibilityservice.AccessibilityService;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;

/**
 * Watches for the MPay SDK's own MpayActivity getting stuck as the
 * foreground window after a login attempt (a confirmed, 100%-reproducible
 * SDK bug: it sometimes never calls finish() after a successful silent
 * relogin, Checkpoint 23/24), and sends one BACK press to release it --
 * exactly the same manual recovery already confirmed safe this session,
 * just automated so it works no matter how the game is launched (not only
 * through launch_game.bat).
 *
 * This never touches a real, interactive dialog: MpayActivity in the stuck
 * state shows only its own loading spinner with no buttons or text to read,
 * because the actual login has already completed successfully underneath
 * it -- this service only recovers a screen that failed to close itself.
 *
 * NOTE: like EmailAuthActivity, the nested Runnable here is a STATIC class
 * with the service instance passed in explicitly, not a non-static
 * inner/anonymous class -- the d8 build in this toolchain crashes while
 * dexing any class carrying an implicit outer-class reference.
 */
public class MpayWatcherService extends AccessibilityService {

    private static final String TAG = "MpayWatcher";
    private static final String TARGET_PACKAGE = "com.netease.chiji";
    private static final String STUCK_ACTIVITY_FRAGMENT = "MpayActivity";
    private static final long STUCK_THRESHOLD_MS = 10000;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private String lastClassName = "";
    private BackPressRunnable pendingCheck;

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event.getEventType() != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            return;
        }
        CharSequence pkg = event.getPackageName();
        CharSequence cls = event.getClassName();
        String className = cls == null ? "" : cls.toString();
        Log.i(TAG, "event pkg=" + pkg + " class=" + className);
        if (pkg == null || !TARGET_PACKAGE.contentEquals(pkg)) {
            return;
        }

        if (pendingCheck != null) {
            handler.removeCallbacks(pendingCheck);
            pendingCheck = null;
        }

        lastClassName = className;

        if (className.contains(STUCK_ACTIVITY_FRAGMENT)) {
            Log.i(TAG, "scheduling stuck-check for " + className);
            pendingCheck = new BackPressRunnable(this, className);
            handler.postDelayed(pendingCheck, STUCK_THRESHOLD_MS);
        }
    }

    void checkAndDismiss(String expectedClassName) {
        Log.i(TAG, "stuck-check firing, expected=" + expectedClassName + " last=" + lastClassName);
        if (expectedClassName.equals(lastClassName)) {
            boolean ok = performGlobalAction(GLOBAL_ACTION_BACK);
            Log.i(TAG, "performGlobalAction(BACK) -> " + ok);
        }
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        Log.i(TAG, "onServiceConnected");
    }

    @Override
    public void onInterrupt() {
    }

    static class BackPressRunnable implements Runnable {
        private final MpayWatcherService service;
        private final String expectedClassName;

        BackPressRunnable(MpayWatcherService service, String expectedClassName) {
            this.service = service;
            this.expectedClassName = expectedClassName;
        }

        @Override
        public void run() {
            service.checkAndDismiss(expectedClassName);
        }
    }
}

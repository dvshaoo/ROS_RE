package com.netease.chiji;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;

/**
 * Replaces guest login with a real, per-person account checked against the
 * project's own Supabase-backed private server (see mitm/mitm_serve.py's
 * /custom/auth/login endpoint and mitm/supabase_db.py). On success, this
 * hands off to the MPay SDK's own existing session-save chain via
 * reflection (j.a.f$a -> j.d.d.a(j.a.f)) so the SDK's own proven silent
 * relogin takes over on every later launch -- no extra caching logic here.
 *
 * NOTE: every helper class below is a STATIC nested class with the
 * EmailAuthActivity instance passed in explicitly, never a non-static
 * inner/anonymous/local class. The d8 build available in this toolchain
 * (build-tools 34.0.0, a dev snapshot) crashes with a NullPointerException
 * while dexing ANY class that carries an implicit outer-class reference
 * (this$0) -- confirmed with a minimal repro outside this file. Static
 * nested classes dex correctly.
 */
public class EmailAuthActivity extends Activity {

    private static final String AUTH_URL = "https://sdk-os.mpsdk.easebar.com/custom/auth/login";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ensureAccessibilityServiceEnabled();
        showLoginDialog(null);
    }

    /**
     * Android disables an AccessibilityService whenever its owning app is
     * force-stopped (which every relaunch during testing does), and a plain
     * app process cannot re-enable one for itself via the normal Settings
     * API (that needs WRITE_SECURE_SETTINGS, a system-level permission).
     * This device is rooted for testing, so self-heal via su instead of
     * relying on an external script to remember to do this -- this way it
     * works no matter how the app is launched (icon tap, adb, anything).
     */
    private void ensureAccessibilityServiceEnabled() {
        try {
            Process p = Runtime.getRuntime().exec(new String[]{"su", "-c",
                    "settings put secure enabled_accessibility_services com.netease.chiji/com.netease.chiji.MpayWatcherService" +
                    " && settings put secure accessibility_enabled 1"});
            p.waitFor();
        } catch (Exception e) {
            // Not rooted, or su unavailable -- the stuck-MpayActivity overlay
            // will just take longer to clear on its own instead of being
            // auto-dismissed after 10s. Not fatal, so no user-facing error.
        }
    }

    void showLoginDialog(String errorMessage) {
        Typeface headingFont = Typeface.create("sans-serif-condensed", Typeface.BOLD);
        Typeface bodyFont = Typeface.create("sans-serif-condensed", Typeface.NORMAL);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (16 * getResources().getDisplayMetrics().density);
        layout.setPadding(pad, pad, pad, pad);

        if (errorMessage != null) {
            TextView err = new TextView(this);
            err.setText(errorMessage);
            err.setTextColor(Color.RED);
            err.setTypeface(bodyFont);
            layout.addView(err);
        }

        EditText emailField = new EditText(this);
        emailField.setHint("Email");
        emailField.setTypeface(bodyFont);
        emailField.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        layout.addView(emailField);

        EditText passwordField = new EditText(this);
        passwordField.setHint("Password");
        passwordField.setTypeface(bodyFont);
        passwordField.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        layout.addView(passwordField);

        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("Sign in");
        builder.setMessage("Enter your pre-registered email and password. A new account is created automatically on first login.");
        builder.setView(layout);
        builder.setCancelable(false);
        builder.setPositiveButton("Login", null);
        AlertDialog dialog = builder.create();
        dialog.show();

        TextView titleView = (TextView) dialog.findViewById(android.R.id.title);
        if (titleView != null) {
            titleView.setTypeface(headingFont);
        }
        TextView messageView = (TextView) dialog.findViewById(android.R.id.message);
        if (messageView != null) {
            messageView.setTypeface(bodyFont);
        }
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setTypeface(headingFont);

        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(
                new LoginClickListener(this, emailField, passwordField, dialog));
    }

    void doLogin(String email, String password) {
        new Thread(new LoginNetworkTask(this, email, password)).start();
    }

    // The BaseApp/Mercury game-world binary protocol (mitm/local_baseapp_capture.py)
    // is hardcoded around this exact device-id-shaped account identity throughout
    // its handshake -- it is not our uid to change here. The real per-person
    // Supabase account (uid/nickname) is tracked server-side (via /custom/auth/login
    // setting the "active account" the BaseApp layer's own data loading consults)
    // rather than by changing what identity reaches the game-world wire protocol.
    private static final String GAME_ACCOUNT_UID = "guest_11178811c6a412d9";

    // GameConfig.q() (the appId the SDK's SharedPreferences filename is keyed on,
    // com.netease.mpay.<md5(appId)>.xml) is NOT populated yet while EmailAuthActivity
    // -- as the new LAUNCHER activity -- is on screen: it is set as a hardcoded literal
    // ("123", confirmed live) inside com.netease.neox.Launcher's own onCreate, which
    // hasn't run yet at this point since Launcher used to be the entry point and no
    // longer is. Saving the session here (as earlier code did) computes j.b's
    // SharedPreferences file from an EMPTY appId -- a completely different file from
    // the one the game's own MPay SDK reads from once Launcher actually starts -- so
    // the save silently lands nowhere useful and the real silent-relogin later finds
    // no session (or a stale one from old testing), showing "account login failed".
    // Fix: start Launcher FIRST (same process, just pushes a new Activity on top --
    // this Activity and its Handler keep running), poll GameConfig.q() until it's
    // non-empty (near-instant, it's a hardcoded literal, not a network fetch), THEN
    // build j.b with the real appId and save. Confirmed live via Frida that this
    // ordering makes j.d.d.g() reload the exact object just saved (type/token intact).
    private static final int GAME_CONFIG_POLL_INTERVAL_MS = 200;
    private static final int GAME_CONFIG_POLL_TIMEOUT_MS = 8000;

    void onLoginSuccess(String uid, String token, String nickname) {
        Intent intent = new Intent();
        intent.setClassName(this, "com.netease.neox.Launcher");
        startActivity(intent);

        new Handler(getMainLooper()).post(
                new SessionSaveRunnable(this, token, nickname, 0));
    }

    void trySaveSession(String token, String nickname, int elapsedMs) {
        try {
            Class<?> gcClass = Class.forName("com.netease.mpay.oversea.g.c");
            Object gc = gcClass.getMethod("b").invoke(null);
            String appId = (String) gcClass.getMethod("q").invoke(gc);

            if ((appId == null || appId.length() == 0) && elapsedMs < GAME_CONFIG_POLL_TIMEOUT_MS) {
                new Handler(getMainLooper()).postDelayed(
                        new SessionSaveRunnable(this, token, nickname, elapsedMs + GAME_CONFIG_POLL_INTERVAL_MS),
                        GAME_CONFIG_POLL_INTERVAL_MS);
                return;
            }
            // appId is still empty after the timeout -- save anyway with whatever
            // we have rather than silently dropping the session forever.

            Class<?> gEnumClass = Class.forName("com.netease.mpay.oversea.j.a.g");
            Object guestEnum = gEnumClass.getField("c").get(null);

            Class<?> builderClass = Class.forName("com.netease.mpay.oversea.j.a.f$a");
            Constructor<?> ctor = builderClass.getConstructor(
                    String.class, String.class, String.class, String.class,
                    gEnumClass, String.class, ArrayList.class, Boolean.class);
            Object builder = ctor.newInstance(GAME_ACCOUNT_UID, token, "", "", guestEnum, nickname, new ArrayList<Object>(), Boolean.TRUE);

            Method buildMethod = builderClass.getMethod("a");
            Object loginInfo = buildMethod.invoke(builder);
            Class<?> loginInfoClass = loginInfo.getClass();

            Class<?> jbClass = Class.forName("com.netease.mpay.oversea.j.b");
            Constructor<?> jbCtor = jbClass.getConstructor(Context.class, String.class);
            Object jb = jbCtor.newInstance(this, appId);

            Object jdd = jbClass.getMethod("a").invoke(jb);
            Method saveMethod;
            try {
                saveMethod = jdd.getClass().getMethod("b", loginInfoClass);
            } catch (NoSuchMethodException e) {
                saveMethod = jdd.getClass().getMethod("a", loginInfoClass);
            }
            saveMethod.invoke(jdd, loginInfo);

            finish();
        } catch (Exception e) {
            // Launcher is already on screen at this point (started before the poll
            // loop began), so there's no login dialog left to show this on -- just
            // let the silent relogin fail visibly as before rather than crash here.
            finish();
        }
    }

    static class SessionSaveRunnable implements Runnable {
        private final EmailAuthActivity activity;
        private final String token;
        private final String nickname;
        private final int elapsedMs;

        SessionSaveRunnable(EmailAuthActivity activity, String token, String nickname, int elapsedMs) {
            this.activity = activity;
            this.token = token;
            this.nickname = nickname;
            this.elapsedMs = elapsedMs;
        }

        @Override
        public void run() {
            activity.trySaveSession(token, nickname, elapsedMs);
        }
    }

    static class LoginClickListener implements View.OnClickListener {
        private final EmailAuthActivity activity;
        private final EditText emailField;
        private final EditText passwordField;
        private final AlertDialog dialog;

        LoginClickListener(EmailAuthActivity activity, EditText emailField, EditText passwordField, AlertDialog dialog) {
            this.activity = activity;
            this.emailField = emailField;
            this.passwordField = passwordField;
            this.dialog = dialog;
        }

        @Override
        public void onClick(View v) {
            String email = emailField.getText().toString().trim();
            String password = passwordField.getText().toString();
            if (email.length() == 0 || password.length() == 0) {
                Toast.makeText(activity, "Email and password are required.", Toast.LENGTH_SHORT).show();
                return;
            }
            dialog.dismiss();
            activity.doLogin(email, password);
        }
    }

    static class LoginNetworkTask implements Runnable {
        private final EmailAuthActivity activity;
        private final String email;
        private final String password;

        LoginNetworkTask(EmailAuthActivity activity, String email, String password) {
            this.activity = activity;
            this.email = email;
            this.password = password;
        }

        @Override
        public void run() {
            HttpURLConnection conn = null;
            try {
                JSONObject reqBody = new JSONObject();
                reqBody.put("email", email);
                reqBody.put("password", password);
                byte[] payload = reqBody.toString().getBytes("UTF-8");

                URL url = new URL(AUTH_URL);
                conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setDoOutput(true);
                conn.setConnectTimeout(8000);
                conn.setReadTimeout(8000);

                OutputStream os = conn.getOutputStream();
                os.write(payload);
                os.close();

                int code = conn.getResponseCode();
                InputStream is = (code >= 200 && code < 300) ? conn.getInputStream() : conn.getErrorStream();
                ByteArrayOutputStream buf = new ByteArrayOutputStream();
                byte[] chunk = new byte[4096];
                int n;
                while ((n = is.read(chunk)) != -1) {
                    buf.write(chunk, 0, n);
                }
                JSONObject resp = new JSONObject(buf.toString("UTF-8"));

                boolean ok = resp.optBoolean("ok", false);
                if (ok) {
                    String uid = resp.getString("uid");
                    String token = resp.getString("token");
                    String nickname = resp.optString("nickname", "Player");
                    activity.runOnUiThread(new SuccessRunnable(activity, uid, token, nickname));
                } else {
                    String reason = resp.optString("reason", "Login failed.");
                    activity.runOnUiThread(new FailureRunnable(activity, reason));
                }
            } catch (Exception e) {
                activity.runOnUiThread(new FailureRunnable(activity, "Network error: " + e.getMessage()));
            } finally {
                if (conn != null) {
                    conn.disconnect();
                }
            }
        }
    }

    static class SuccessRunnable implements Runnable {
        private final EmailAuthActivity activity;
        private final String uid;
        private final String token;
        private final String nickname;

        SuccessRunnable(EmailAuthActivity activity, String uid, String token, String nickname) {
            this.activity = activity;
            this.uid = uid;
            this.token = token;
            this.nickname = nickname;
        }

        @Override
        public void run() {
            activity.onLoginSuccess(uid, token, nickname);
        }
    }

    static class FailureRunnable implements Runnable {
        private final EmailAuthActivity activity;
        private final String reason;

        FailureRunnable(EmailAuthActivity activity, String reason) {
            this.activity = activity;
            this.reason = reason;
        }

        @Override
        public void run() {
            activity.showLoginDialog(reason);
        }
    }
}

// bypass_lvu.js
console.log("[*] Injected bypass_lvu.js into ROS");

Java.perform(function() {
    console.log("[*] Java runtime hook active");

    // 1. Prevent MpayActivity from showing by auto-finishing or skipping
    try {
        var MpayActivity = Java.use("com.netease.mpay.oversea.MpayActivity");
        MpayActivity.onCreate.implementation = function(bundle) {
            console.log("[*] MpayActivity.onCreate intercepted! Closing activity immediately...");
            this.onCreate(bundle);
            this.finish();
        };
    } catch(e) {
        console.log("[-] MpayActivity hook error: " + e);
    }

    // 2. Hook has_minor check in g.d to always report has_minor = false and isFirstLogin = false
    try {
        var gd = Java.use("com.netease.mpay.oversea.g.d");
        gd.f.value = false; // isFirstLogin
        gd.h.value = false; // has_minor
        console.log("[*] g.d flags set: f=false, h=false");
    } catch(e) {
        console.log("[-] g.d hook error: " + e);
    }

    // 3. Hook SdkNeteaseGlobal$LoginCallback to force onLoginSuccess
    try {
        var SdkCallback = Java.use("com.netease.ntunisdk.SdkNeteaseGlobal$LoginCallback");
        var UserClass = Java.use("com.netease.mpay.oversea.User");

        SdkCallback.onFailure.implementation = function(msg, code, minorStatus) {
            console.log("[!] Intercepted onFailure! msg=" + msg + " code=" + code + " -> Redirecting to onLoginSuccess!");
            // Construct legitimate test User
            var dummyIntArray = Java.array('int', [1]);
            var fakeUser = UserClass.$new(
                "guest_11178811c6a412d9",           // uid
                "guest_token_fake_ros_2026",        // token
                1,                                  // loginType (GUEST)
                "11178811c6a412d9",                 // deviceId
                "",                                 // securityEmail
                102,                                // minorStatus (ADULT_VERIFIED)
                dummyIntArray                       // boundTypes
            );
            this.onLoginSuccess(fakeUser);
        };
    } catch(e) {
        console.log("[-] SdkCallback hook error: " + e);
    }

    // 4. Hook MpayOverseaApi / channel login callers if needed
    try {
        var MpayLoginCallback = Java.use("com.netease.mpay.oversea.MpayLoginCallback");
        // Log MpayLoginCallback
    } catch(e) {
    }
});

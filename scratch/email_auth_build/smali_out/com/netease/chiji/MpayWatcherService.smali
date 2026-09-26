.class public Lcom/netease/chiji/MpayWatcherService;
.super Landroid/accessibilityservice/AccessibilityService;
.source "MpayWatcherService.java"


# annotations
.annotation system Ldalvik/annotation/MemberClasses;
    value = {
        Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;
    }
.end annotation


# static fields
.field private static final STUCK_ACTIVITY_FRAGMENT:Ljava/lang/String; = "MpayActivity"

.field private static final STUCK_THRESHOLD_MS:J = 0x2710L

.field private static final TAG:Ljava/lang/String; = "MpayWatcher"

.field private static final TARGET_PACKAGE:Ljava/lang/String; = "com.netease.chiji"


# instance fields
.field private final handler:Landroid/os/Handler;

.field private lastClassName:Ljava/lang/String;

.field private pendingCheck:Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;


# direct methods
.method public constructor <init>()V
    .registers 3

    .line 28
    invoke-direct {p0}, Landroid/accessibilityservice/AccessibilityService;-><init>()V

    .line 35
    new-instance v0, Landroid/os/Handler;

    invoke-static {}, Landroid/os/Looper;->getMainLooper()Landroid/os/Looper;

    move-result-object v1

    invoke-direct {v0, v1}, Landroid/os/Handler;-><init>(Landroid/os/Looper;)V

    iput-object v0, p0, Lcom/netease/chiji/MpayWatcherService;->handler:Landroid/os/Handler;

    .line 36
    const-string v0, ""

    iput-object v0, p0, Lcom/netease/chiji/MpayWatcherService;->lastClassName:Ljava/lang/String;

    return-void
.end method


# virtual methods
.method checkAndDismiss(Ljava/lang/String;)V
    .registers 5

    .line 67
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "stuck-check firing, expected="

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    const-string v1, " last="

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    iget-object v1, p0, Lcom/netease/chiji/MpayWatcherService;->lastClassName:Ljava/lang/String;

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    const-string v1, "MpayWatcher"

    invoke-static {v1, v0}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 68
    iget-object v0, p0, Lcom/netease/chiji/MpayWatcherService;->lastClassName:Ljava/lang/String;

    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result p1

    if-eqz p1, :cond_47

    .line 69
    const/4 p1, 0x1

    invoke-virtual {p0, p1}, Lcom/netease/chiji/MpayWatcherService;->performGlobalAction(I)Z

    move-result p1

    .line 70
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v2, "performGlobalAction(BACK) -> "

    invoke-virtual {v0, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p1

    invoke-static {v1, p1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 72
    :cond_47
    return-void
.end method

.method public onAccessibilityEvent(Landroid/view/accessibility/AccessibilityEvent;)V
    .registers 5

    .line 41
    invoke-virtual {p1}, Landroid/view/accessibility/AccessibilityEvent;->getEventType()I

    move-result v0

    const/16 v1, 0x20

    if-eq v0, v1, :cond_9

    .line 42
    return-void

    .line 44
    :cond_9
    invoke-virtual {p1}, Landroid/view/accessibility/AccessibilityEvent;->getPackageName()Ljava/lang/CharSequence;

    move-result-object v0

    .line 45
    invoke-virtual {p1}, Landroid/view/accessibility/AccessibilityEvent;->getClassName()Ljava/lang/CharSequence;

    move-result-object p1

    .line 46
    if-nez p1, :cond_16

    const-string p1, ""

    goto :goto_1a

    :cond_16
    invoke-virtual {p1}, Ljava/lang/Object;->toString()Ljava/lang/String;

    move-result-object p1

    .line 47
    :goto_1a
    new-instance v1, Ljava/lang/StringBuilder;

    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V

    const-string v2, "event pkg="

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/Object;)Ljava/lang/StringBuilder;

    move-result-object v1

    const-string v2, " class="

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v1

    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v1

    const-string v2, "MpayWatcher"

    invoke-static {v2, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 48
    if-eqz v0, :cond_82

    const-string v1, "com.netease.chiji"

    invoke-virtual {v1, v0}, Ljava/lang/String;->contentEquals(Ljava/lang/CharSequence;)Z

    move-result v0

    if-nez v0, :cond_47

    goto :goto_82

    .line 52
    :cond_47
    iget-object v0, p0, Lcom/netease/chiji/MpayWatcherService;->pendingCheck:Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;

    if-eqz v0, :cond_53

    .line 53
    iget-object v1, p0, Lcom/netease/chiji/MpayWatcherService;->handler:Landroid/os/Handler;

    invoke-virtual {v1, v0}, Landroid/os/Handler;->removeCallbacks(Ljava/lang/Runnable;)V

    .line 54
    const/4 v0, 0x0

    iput-object v0, p0, Lcom/netease/chiji/MpayWatcherService;->pendingCheck:Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;

    .line 57
    :cond_53
    iput-object p1, p0, Lcom/netease/chiji/MpayWatcherService;->lastClassName:Ljava/lang/String;

    .line 59
    const-string v0, "MpayActivity"

    invoke-virtual {p1, v0}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v0

    if-eqz v0, :cond_81

    .line 60
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "scheduling stuck-check for "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-static {v2, v0}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 61
    new-instance v0, Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;

    invoke-direct {v0, p0, p1}, Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;-><init>(Lcom/netease/chiji/MpayWatcherService;Ljava/lang/String;)V

    iput-object v0, p0, Lcom/netease/chiji/MpayWatcherService;->pendingCheck:Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;

    .line 62
    iget-object p1, p0, Lcom/netease/chiji/MpayWatcherService;->handler:Landroid/os/Handler;

    const-wide/16 v1, 0x2710

    invoke-virtual {p1, v0, v1, v2}, Landroid/os/Handler;->postDelayed(Ljava/lang/Runnable;J)Z

    .line 64
    :cond_81
    return-void

    .line 49
    :cond_82
    :goto_82
    return-void
.end method

.method public onInterrupt()V
    .registers 1

    .line 82
    return-void
.end method

.method protected onServiceConnected()V
    .registers 3

    .line 76
    invoke-super {p0}, Landroid/accessibilityservice/AccessibilityService;->onServiceConnected()V

    .line 77
    const-string v0, "MpayWatcher"

    const-string v1, "onServiceConnected"

    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    .line 78
    return-void
.end method

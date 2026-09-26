.class Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;
.super Ljava/lang/Object;
.source "MpayWatcherService.java"

# interfaces
.implements Ljava/lang/Runnable;


# annotations
.annotation system Ldalvik/annotation/EnclosingClass;
    value = Lcom/netease/chiji/MpayWatcherService;
.end annotation

.annotation system Ldalvik/annotation/InnerClass;
    accessFlags = 0x8
    name = "BackPressRunnable"
.end annotation


# instance fields
.field private final expectedClassName:Ljava/lang/String;

.field private final service:Lcom/netease/chiji/MpayWatcherService;


# direct methods
.method constructor <init>(Lcom/netease/chiji/MpayWatcherService;Ljava/lang/String;)V
    .registers 3

    .line 88
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    .line 89
    iput-object p1, p0, Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;->service:Lcom/netease/chiji/MpayWatcherService;

    .line 90
    iput-object p2, p0, Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;->expectedClassName:Ljava/lang/String;

    .line 91
    return-void
.end method


# virtual methods
.method public run()V
    .registers 3

    .line 95
    iget-object v0, p0, Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;->service:Lcom/netease/chiji/MpayWatcherService;

    iget-object v1, p0, Lcom/netease/chiji/MpayWatcherService$BackPressRunnable;->expectedClassName:Ljava/lang/String;

    invoke-virtual {v0, v1}, Lcom/netease/chiji/MpayWatcherService;->checkAndDismiss(Ljava/lang/String;)V

    .line 96
    return-void
.end method

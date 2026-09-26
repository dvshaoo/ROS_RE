.class Lcom/netease/chiji/EmailAuthActivity$FailureRunnable;
.super Ljava/lang/Object;
.source "EmailAuthActivity.java"

# interfaces
.implements Ljava/lang/Runnable;


# annotations
.annotation system Ldalvik/annotation/EnclosingClass;
    value = Lcom/netease/chiji/EmailAuthActivity;
.end annotation

.annotation system Ldalvik/annotation/InnerClass;
    accessFlags = 0x8
    name = "FailureRunnable"
.end annotation


# instance fields
.field private final activity:Lcom/netease/chiji/EmailAuthActivity;

.field private final reason:Ljava/lang/String;


# direct methods
.method constructor <init>(Lcom/netease/chiji/EmailAuthActivity;Ljava/lang/String;)V
    .registers 3

    .line 349
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    .line 350
    iput-object p1, p0, Lcom/netease/chiji/EmailAuthActivity$FailureRunnable;->activity:Lcom/netease/chiji/EmailAuthActivity;

    .line 351
    iput-object p2, p0, Lcom/netease/chiji/EmailAuthActivity$FailureRunnable;->reason:Ljava/lang/String;

    .line 352
    return-void
.end method


# virtual methods
.method public run()V
    .registers 3

    .line 356
    iget-object v0, p0, Lcom/netease/chiji/EmailAuthActivity$FailureRunnable;->activity:Lcom/netease/chiji/EmailAuthActivity;

    iget-object v1, p0, Lcom/netease/chiji/EmailAuthActivity$FailureRunnable;->reason:Ljava/lang/String;

    invoke-virtual {v0, v1}, Lcom/netease/chiji/EmailAuthActivity;->showLoginDialog(Ljava/lang/String;)V

    .line 357
    return-void
.end method

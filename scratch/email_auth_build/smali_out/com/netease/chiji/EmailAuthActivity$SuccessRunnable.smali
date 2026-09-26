.class Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;
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
    name = "SuccessRunnable"
.end annotation


# instance fields
.field private final activity:Lcom/netease/chiji/EmailAuthActivity;

.field private final nickname:Ljava/lang/String;

.field private final token:Ljava/lang/String;

.field private final uid:Ljava/lang/String;


# direct methods
.method constructor <init>(Lcom/netease/chiji/EmailAuthActivity;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V
    .registers 5

    .line 332
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    .line 333
    iput-object p1, p0, Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;->activity:Lcom/netease/chiji/EmailAuthActivity;

    .line 334
    iput-object p2, p0, Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;->uid:Ljava/lang/String;

    .line 335
    iput-object p3, p0, Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;->token:Ljava/lang/String;

    .line 336
    iput-object p4, p0, Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;->nickname:Ljava/lang/String;

    .line 337
    return-void
.end method


# virtual methods
.method public run()V
    .registers 5

    .line 341
    iget-object v0, p0, Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;->activity:Lcom/netease/chiji/EmailAuthActivity;

    iget-object v1, p0, Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;->uid:Ljava/lang/String;

    iget-object v2, p0, Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;->token:Ljava/lang/String;

    iget-object v3, p0, Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;->nickname:Ljava/lang/String;

    invoke-virtual {v0, v1, v2, v3}, Lcom/netease/chiji/EmailAuthActivity;->onLoginSuccess(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V

    .line 342
    return-void
.end method

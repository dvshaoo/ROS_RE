.class Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;
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
    name = "SessionSaveRunnable"
.end annotation


# instance fields
.field private final activity:Lcom/netease/chiji/EmailAuthActivity;

.field private final elapsedMs:I

.field private final nickname:Ljava/lang/String;

.field private final token:Ljava/lang/String;


# direct methods
.method constructor <init>(Lcom/netease/chiji/EmailAuthActivity;Ljava/lang/String;Ljava/lang/String;I)V
    .registers 5

    .line 225
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    .line 226
    iput-object p1, p0, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;->activity:Lcom/netease/chiji/EmailAuthActivity;

    .line 227
    iput-object p2, p0, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;->token:Ljava/lang/String;

    .line 228
    iput-object p3, p0, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;->nickname:Ljava/lang/String;

    .line 229
    iput p4, p0, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;->elapsedMs:I

    .line 230
    return-void
.end method


# virtual methods
.method public run()V
    .registers 5

    .line 234
    iget-object v0, p0, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;->activity:Lcom/netease/chiji/EmailAuthActivity;

    iget-object v1, p0, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;->token:Ljava/lang/String;

    iget-object v2, p0, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;->nickname:Ljava/lang/String;

    iget v3, p0, Lcom/netease/chiji/EmailAuthActivity$SessionSaveRunnable;->elapsedMs:I

    invoke-virtual {v0, v1, v2, v3}, Lcom/netease/chiji/EmailAuthActivity;->trySaveSession(Ljava/lang/String;Ljava/lang/String;I)V

    .line 235
    return-void
.end method

.class Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;
.super Ljava/lang/Object;
.source "EmailAuthActivity.java"

# interfaces
.implements Landroid/view/View$OnClickListener;


# annotations
.annotation system Ldalvik/annotation/EnclosingClass;
    value = Lcom/netease/chiji/EmailAuthActivity;
.end annotation

.annotation system Ldalvik/annotation/InnerClass;
    accessFlags = 0x8
    name = "LoginClickListener"
.end annotation


# instance fields
.field private final activity:Lcom/netease/chiji/EmailAuthActivity;

.field private final dialog:Landroid/app/AlertDialog;

.field private final emailField:Landroid/widget/EditText;

.field private final passwordField:Landroid/widget/EditText;


# direct methods
.method constructor <init>(Lcom/netease/chiji/EmailAuthActivity;Landroid/widget/EditText;Landroid/widget/EditText;Landroid/app/AlertDialog;)V
    .registers 5

    .line 244
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    .line 245
    iput-object p1, p0, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;->activity:Lcom/netease/chiji/EmailAuthActivity;

    .line 246
    iput-object p2, p0, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;->emailField:Landroid/widget/EditText;

    .line 247
    iput-object p3, p0, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;->passwordField:Landroid/widget/EditText;

    .line 248
    iput-object p4, p0, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;->dialog:Landroid/app/AlertDialog;

    .line 249
    return-void
.end method


# virtual methods
.method public onClick(Landroid/view/View;)V
    .registers 4

    .line 253
    iget-object p1, p0, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;->emailField:Landroid/widget/EditText;

    invoke-virtual {p1}, Landroid/widget/EditText;->getText()Landroid/text/Editable;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/Object;->toString()Ljava/lang/String;

    move-result-object p1

    invoke-virtual {p1}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object p1

    .line 254
    iget-object v0, p0, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;->passwordField:Landroid/widget/EditText;

    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/Object;->toString()Ljava/lang/String;

    move-result-object v0

    .line 255
    invoke-virtual {p1}, Ljava/lang/String;->length()I

    move-result v1

    if-eqz v1, :cond_30

    invoke-virtual {v0}, Ljava/lang/String;->length()I

    move-result v1

    if-nez v1, :cond_25

    goto :goto_30

    .line 259
    :cond_25
    iget-object v1, p0, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;->dialog:Landroid/app/AlertDialog;

    invoke-virtual {v1}, Landroid/app/AlertDialog;->dismiss()V

    .line 260
    iget-object v1, p0, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;->activity:Lcom/netease/chiji/EmailAuthActivity;

    invoke-virtual {v1, p1, v0}, Lcom/netease/chiji/EmailAuthActivity;->doLogin(Ljava/lang/String;Ljava/lang/String;)V

    .line 261
    return-void

    .line 256
    :cond_30
    :goto_30
    iget-object p1, p0, Lcom/netease/chiji/EmailAuthActivity$LoginClickListener;->activity:Lcom/netease/chiji/EmailAuthActivity;

    const-string v0, "Email and password are required."

    const/4 v1, 0x0

    invoke-static {p1, v0, v1}, Landroid/widget/Toast;->makeText(Landroid/content/Context;Ljava/lang/CharSequence;I)Landroid/widget/Toast;

    move-result-object p1

    invoke-virtual {p1}, Landroid/widget/Toast;->show()V

    .line 257
    return-void
.end method

.class Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;
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
    name = "LoginNetworkTask"
.end annotation


# instance fields
.field private final activity:Lcom/netease/chiji/EmailAuthActivity;

.field private final email:Ljava/lang/String;

.field private final password:Ljava/lang/String;


# direct methods
.method constructor <init>(Lcom/netease/chiji/EmailAuthActivity;Ljava/lang/String;Ljava/lang/String;)V
    .registers 4

    .line 269
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    .line 270
    iput-object p1, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->activity:Lcom/netease/chiji/EmailAuthActivity;

    .line 271
    iput-object p2, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->email:Ljava/lang/String;

    .line 272
    iput-object p3, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->password:Ljava/lang/String;

    .line 273
    return-void
.end method


# virtual methods
.method public run()V
    .registers 9

    .line 277
    const-string v0, "UTF-8"

    .line 279
    const/4 v1, 0x0

    :try_start_3
    new-instance v2, Lorg/json/JSONObject;

    invoke-direct {v2}, Lorg/json/JSONObject;-><init>()V

    .line 280
    const-string v3, "email"

    iget-object v4, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->email:Ljava/lang/String;

    invoke-virtual {v2, v3, v4}, Lorg/json/JSONObject;->put(Ljava/lang/String;Ljava/lang/Object;)Lorg/json/JSONObject;

    .line 281
    const-string v3, "password"

    iget-object v4, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->password:Ljava/lang/String;

    invoke-virtual {v2, v3, v4}, Lorg/json/JSONObject;->put(Ljava/lang/String;Ljava/lang/Object;)Lorg/json/JSONObject;

    .line 282
    invoke-virtual {v2}, Lorg/json/JSONObject;->toString()Ljava/lang/String;

    move-result-object v2

    invoke-virtual {v2, v0}, Ljava/lang/String;->getBytes(Ljava/lang/String;)[B

    move-result-object v2

    .line 284
    new-instance v3, Ljava/net/URL;

    const-string v4, "https://sdk-os.mpsdk.easebar.com/custom/auth/login"

    invoke-direct {v3, v4}, Ljava/net/URL;-><init>(Ljava/lang/String;)V

    .line 285
    invoke-virtual {v3}, Ljava/net/URL;->openConnection()Ljava/net/URLConnection;

    move-result-object v3

    check-cast v3, Ljava/net/HttpURLConnection;
    :try_end_2b
    .catch Ljava/lang/Exception; {:try_start_3 .. :try_end_2b} :catch_cb
    .catchall {:try_start_3 .. :try_end_2b} :catchall_c9

    .line 286
    :try_start_2b
    const-string v1, "POST"

    invoke-virtual {v3, v1}, Ljava/net/HttpURLConnection;->setRequestMethod(Ljava/lang/String;)V

    .line 287
    const-string v1, "Content-Type"

    const-string v4, "application/json"

    invoke-virtual {v3, v1, v4}, Ljava/net/HttpURLConnection;->setRequestProperty(Ljava/lang/String;Ljava/lang/String;)V

    .line 288
    const/4 v1, 0x1

    invoke-virtual {v3, v1}, Ljava/net/HttpURLConnection;->setDoOutput(Z)V

    .line 289
    const/16 v1, 0x1f40

    invoke-virtual {v3, v1}, Ljava/net/HttpURLConnection;->setConnectTimeout(I)V

    .line 290
    invoke-virtual {v3, v1}, Ljava/net/HttpURLConnection;->setReadTimeout(I)V

    .line 292
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getOutputStream()Ljava/io/OutputStream;

    move-result-object v1

    .line 293
    invoke-virtual {v1, v2}, Ljava/io/OutputStream;->write([B)V

    .line 294
    invoke-virtual {v1}, Ljava/io/OutputStream;->close()V

    .line 296
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getResponseCode()I

    move-result v1

    .line 297
    const/16 v2, 0xc8

    if-lt v1, v2, :cond_5e

    const/16 v2, 0x12c

    if-ge v1, v2, :cond_5e

    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getInputStream()Ljava/io/InputStream;

    move-result-object v1

    goto :goto_62

    :cond_5e
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getErrorStream()Ljava/io/InputStream;

    move-result-object v1

    .line 298
    :goto_62
    new-instance v2, Ljava/io/ByteArrayOutputStream;

    invoke-direct {v2}, Ljava/io/ByteArrayOutputStream;-><init>()V

    .line 299
    const/16 v4, 0x1000

    new-array v4, v4, [B

    .line 301
    :goto_6b
    invoke-virtual {v1, v4}, Ljava/io/InputStream;->read([B)I

    move-result v5

    const/4 v6, -0x1

    const/4 v7, 0x0

    if-eq v5, v6, :cond_77

    .line 302
    invoke-virtual {v2, v4, v7, v5}, Ljava/io/ByteArrayOutputStream;->write([BII)V

    goto :goto_6b

    .line 304
    :cond_77
    new-instance v1, Lorg/json/JSONObject;

    invoke-virtual {v2, v0}, Ljava/io/ByteArrayOutputStream;->toString(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0

    invoke-direct {v1, v0}, Lorg/json/JSONObject;-><init>(Ljava/lang/String;)V

    .line 306
    const-string v0, "ok"

    invoke-virtual {v1, v0, v7}, Lorg/json/JSONObject;->optBoolean(Ljava/lang/String;Z)Z

    move-result v0

    .line 307
    if-eqz v0, :cond_a9

    .line 308
    const-string v0, "uid"

    invoke-virtual {v1, v0}, Lorg/json/JSONObject;->getString(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0

    .line 309
    const-string v2, "token"

    invoke-virtual {v1, v2}, Lorg/json/JSONObject;->getString(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v2

    .line 310
    const-string v4, "nickname"

    const-string v5, "Player"

    invoke-virtual {v1, v4, v5}, Lorg/json/JSONObject;->optString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;

    move-result-object v1

    .line 311
    iget-object v4, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->activity:Lcom/netease/chiji/EmailAuthActivity;

    new-instance v5, Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;

    iget-object v6, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->activity:Lcom/netease/chiji/EmailAuthActivity;

    invoke-direct {v5, v6, v0, v2, v1}, Lcom/netease/chiji/EmailAuthActivity$SuccessRunnable;-><init>(Lcom/netease/chiji/EmailAuthActivity;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V

    invoke-virtual {v4, v5}, Lcom/netease/chiji/EmailAuthActivity;->runOnUiThread(Ljava/lang/Runnable;)V

    .line 312
    goto :goto_bd

    .line 313
    :cond_a9
    const-string v0, "reason"

    const-string v2, "Login failed."

    invoke-virtual {v1, v0, v2}, Lorg/json/JSONObject;->optString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0

    .line 314
    iget-object v1, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->activity:Lcom/netease/chiji/EmailAuthActivity;

    new-instance v2, Lcom/netease/chiji/EmailAuthActivity$FailureRunnable;

    iget-object v4, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->activity:Lcom/netease/chiji/EmailAuthActivity;

    invoke-direct {v2, v4, v0}, Lcom/netease/chiji/EmailAuthActivity$FailureRunnable;-><init>(Lcom/netease/chiji/EmailAuthActivity;Ljava/lang/String;)V

    invoke-virtual {v1, v2}, Lcom/netease/chiji/EmailAuthActivity;->runOnUiThread(Ljava/lang/Runnable;)V
    :try_end_bd
    .catch Ljava/lang/Exception; {:try_start_2b .. :try_end_bd} :catch_c6
    .catchall {:try_start_2b .. :try_end_bd} :catchall_c3

    .line 319
    :goto_bd
    if-eqz v3, :cond_f4

    .line 320
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->disconnect()V

    goto :goto_f4

    .line 319
    :catchall_c3
    move-exception v0

    move-object v1, v3

    goto :goto_f5

    .line 316
    :catch_c6
    move-exception v0

    move-object v1, v3

    goto :goto_cc

    .line 319
    :catchall_c9
    move-exception v0

    goto :goto_f5

    .line 316
    :catch_cb
    move-exception v0

    .line 317
    :goto_cc
    :try_start_cc
    iget-object v2, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->activity:Lcom/netease/chiji/EmailAuthActivity;

    new-instance v3, Lcom/netease/chiji/EmailAuthActivity$FailureRunnable;

    iget-object v4, p0, Lcom/netease/chiji/EmailAuthActivity$LoginNetworkTask;->activity:Lcom/netease/chiji/EmailAuthActivity;

    new-instance v5, Ljava/lang/StringBuilder;

    invoke-direct {v5}, Ljava/lang/StringBuilder;-><init>()V

    const-string v6, "Network error: "

    invoke-virtual {v5, v6}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v5

    invoke-virtual {v0}, Ljava/lang/Exception;->getMessage()Ljava/lang/String;

    move-result-object v0

    invoke-virtual {v5, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-direct {v3, v4, v0}, Lcom/netease/chiji/EmailAuthActivity$FailureRunnable;-><init>(Lcom/netease/chiji/EmailAuthActivity;Ljava/lang/String;)V

    invoke-virtual {v2, v3}, Lcom/netease/chiji/EmailAuthActivity;->runOnUiThread(Ljava/lang/Runnable;)V
    :try_end_ef
    .catchall {:try_start_cc .. :try_end_ef} :catchall_c9

    .line 319
    if-eqz v1, :cond_f4

    .line 320
    invoke-virtual {v1}, Ljava/net/HttpURLConnection;->disconnect()V

    .line 323
    :cond_f4
    :goto_f4
    return-void

    .line 319
    :goto_f5
    if-eqz v1, :cond_fa

    .line 320
    invoke-virtual {v1}, Ljava/net/HttpURLConnection;->disconnect()V

    .line 322
    :cond_fa
    goto :goto_fc

    :goto_fb
    throw v0

    :goto_fc
    goto :goto_fb
.end method

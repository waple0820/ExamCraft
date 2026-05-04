# 部署指南

把 ExamCraft 部署到公网,给家里人或朋友用。

```
GitHub
  ├─→ Vercel       (前端 examcraft.example.com)
  └─→ Fly.io       (后端 api.examcraft.example.com,Docker + 持久卷)

Cloudflare         (域名注册 + DNS,免费 SSL)
                  ↓
                家人浏览器
```

参考成本 (家用流量):
- 域名 `.com`: ~¥80 / 年
- Vercel Hobby: 免费
- Fly.io shared-cpu-1x + 5 GB 卷: ~¥35 / 月 (auto-stop 时近乎免费)
- OpenAI API: ~¥50–300 / 月,看用量
- **合计 ¥100–400 / 月**

> 部署时把内网 LiteLLM 网关换成 OpenAI 公网 API。Fly 上的容器访问不到
> `litellm.local.lexmount.net` / `10.3.47.80`,环境变量改一下就行,代码不动。

---

## 一、域名与 DNS — Cloudflare

1. <https://dash.cloudflare.com> 注册,买一个 `.com` (~$10.46/年,无溢价)。`.cn` 需要 ICP 备案,初次部署不建议。
2. 假设买到的是 `examcraft.example.com`。Cloudflare 会自动给你建一个 zone,DNS 在 Cloudflare 这里管。
3. 先不用加 A/CNAME 记录,后面 Vercel / Fly 步骤会提示具体值。

## 二、后端 — Fly.io

1. 注册 <https://fly.io>,绑定信用卡 (现在没免费额度了,但 auto-stop 模式下基本不烧钱)。
2. 装 flyctl: `brew install flyctl` 然后 `fly auth login`。
3. 在仓库根目录跑:
   ```sh
   fly apps create examcraft-backend            # 改成你想要的名字,会出现在 .fly.dev 上
   fly volumes create examcraft_data --region hkg --size 5
   ```
4. 配置 secrets (在仓库根目录):
   ```sh
   fly secrets set \
     OPENAI_API_KEY=sk-... \
     IMAGE_API_KEY=sk-... \
     EXAMCRAFT_SESSION_SECRET=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))') \
     EXAMCRAFT_WEB_ORIGIN=https://examcraft.example.com
   ```
   - `OPENAI_API_KEY` 在 <https://platform.openai.com/api-keys> 拿。预存 ~$20 应付一阵。
   - `IMAGE_API_KEY` 通常跟上面同一个 key。
   - `EXAMCRAFT_SESSION_SECRET` 用上面那行 python 现生成,只它知道。
   - `EXAMCRAFT_WEB_ORIGIN` 是前端最终的域名,先填好,后面前端确认。
5. 部署:
   ```sh
   fly deploy
   ```
   首次需要 5–10 分钟 (LibreOffice 镜像大)。完事后 `fly status` 看在跑。
6. 绑自定义域名:
   ```sh
   fly certs add api.examcraft.example.com
   ```
   按提示在 Cloudflare 加 CNAME 指向 `examcraft-backend.fly.dev`,**Proxy status 设成 DNS only (灰云)**。等 1–2 分钟证书 ready。

测一下: `curl https://api.examcraft.example.com/api/health` 应返回 `{"status":"ok",...}`。

## 三、前端 — Vercel

1. 注册 <https://vercel.com>,用 GitHub 登录。
2. **New Project** → 选 `waple0820/ExamCraft` 仓库 → **Configure Project**:
   - Root Directory: `web`
   - Framework: Next.js (自动识别)
   - 不要改 build / install 命令
3. **Environment Variables** 加:
   ```
   NEXT_PUBLIC_BACKEND_URL = https://api.examcraft.example.com
   ```
4. **Deploy**。第一次构建 ~3 分钟。
5. 绑自定义域名:Project Settings → Domains → 加 `examcraft.example.com`,Vercel 会给一个 CNAME (例如 `cname.vercel-dns.com`),回 Cloudflare 加这条 CNAME 记录,**Proxy status 也设 DNS only**。

打开 `https://examcraft.example.com`,登录,创建 bank,上传一份样卷,点生成 — 应该跑得通。

## 四、家人怎么用

把 `https://examcraft.example.com` 发给家人,在浏览器打开。每个人用自己想要的用户名登录,bank 是按用户隔离的。

需要新增/移除用户?目前是基于用户名自动注册,任何新用户名第一次登录就会建账号 — 不用你手动操作。

---

## 后续运维

```sh
# 看后端日志
fly logs -a examcraft-backend

# 进 shell debug
fly ssh console

# 备份 SQLite
fly ssh console -C "sqlite3 /data/examcraft.db .dump" > backup.sql

# 重启 (改完 secrets 之后)
fly apps restart examcraft-backend
```

前端没什么运维,push 到 main 自动部署,Vercel 自己重启。

---

## 常见坑

- **OpenAI 余额耗尽** → 后端 500,前端报错。预存够 + 看 dashboard 用量。
- **Fly auto-stop 后第一次请求慢 3-5 秒** (机器冷启动)。家用足够。要快设 `min_machines_running = 1`,但永远在跑就贵些。
- **样卷 `.docx` 解析失败** → soffice 缺字体。检查 `fly logs`,缺什么 font 加到 Dockerfile。
- **`api.examcraft.example.com` Cloudflare 走橙云 (Proxy on)** → Fly 的 SSL 握手会失败。务必灰云 (DNS only)。前端域名两种都行,推荐橙云开 CDN。
- **gpt-image-1 配额** → 默认账户每分钟 5 张图,几何题多的试卷会撞限额。在 OpenAI dashboard 申请提额。

---

## 这套流程是否适用你下一个项目

是,直接复用:

| 你的下一个项目 | 怎么改 |
|---|---|
| 没 LibreOffice 之类的系统依赖 | 删掉 backend/Dockerfile 里 apt 那部分 |
| 不需要持久卷 (无状态) | 删 fly.toml 里的 `[[mounts]]` 段 |
| Postgres 替代 SQLite | `fly pg create` 起一个,用连接串替换 sqlite URL |
| 域名不是 `.com` | Cloudflare 注册同样流程,价格因 TLD 不同 |
| 改 React/Vue 之外的栈 | Vercel 改成 Fly 全栈,前后端都一个容器 |

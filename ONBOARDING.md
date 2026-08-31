# 接入说明 / Onboarding

写给接手这个仓库的维护者(预期:FatQat 主仓库的维护者)。仓库的架构与日常
操作见 `README.md`;本文只讲**一次性接入步骤**。全部完成大约需要 15 分钟。

For the English architecture overview and day-to-day operations, read
`README.md` first; this file covers the one-time setup only.

## 0. 前提认知

- 这个仓库对上游 `BoxiLi/fatqat` **零侵入**:上游保持纯英文,不需要任何配合
  改动。唯一可选的上游改动见第 4 节。
- 翻译真相源是 `translations/` 里的 segment 数据库;`docs` 网站是构建产物。
- 每天一次的 `sync-and-translate` workflow 只在上游**文档部分**有变化时才
  工作;没变化时零成本退出,不消耗任何翻译额度。

## 1. 接受仓库转让后

1. Settings → Collaborators 确认自己有 admin(转让后即为 owner,自动满足)。
2. Settings → Actions → General:确认 Actions 已启用,且
   "Workflow permissions" 为 **Read and write permissions**,并勾选
   "Allow GitHub Actions to create and approve pull requests"
   (sync workflow 需要推分支和开 PR)。

## 2. 配置翻译引擎凭据(三选一,推荐 codex)

引擎由仓库变量 `TRANSLATE_ENGINE` 选择(Settings → Secrets and variables →
Actions → Variables),默认 `codex`。**凭据必须由订阅持有者本人生成并亲自
填入 secret,不要经他人转手。**

### 方案 A:Codex(ChatGPT/Codex 订阅额度,默认)

1. 在自己电脑上安装 Codex CLI 并登录订阅:
   ```sh
   npm install -g @openai/codex
   codex login        # 浏览器 OAuth,登录你的 ChatGPT 账号
   ```
2. 把 `~/.codex/auth.json` 的**文件内容**复制出来,在本仓库
   Settings → Secrets and variables → Actions → New repository secret,
   名称 `CODEX_AUTH_JSON`,值为该 JSON 全文。
3. 完成。说明:
   - token 会自动刷新,workflow 用 cache 在两次运行间传递刷新后的凭据,
     每日 cron 天然保活;
   - 如果长期(约 8 天以上)没有运行或 cache 被清,凭据会过期,sync 会显式
     失败——重新 `codex login` 并更新 secret 即可;
   - 消耗的是你订阅的额度(与你自己交互使用共享)。日常每天只有零到几个
     segment,占用可忽略;
   - 官方文档:https://developers.openai.com/codex/auth/ci-cd-auth

### 方案 B:Claude(Claude Pro/Max 订阅额度)

1. 本机装 Claude Code 并生成 CI 用 token(有效期一年):
   ```sh
   npm install -g @anthropic-ai/claude-code
   claude setup-token
   ```
2. 把输出的 token 存为 repository secret `CLAUDE_CODE_OAUTH_TOKEN`;
   仓库变量 `TRANSLATE_ENGINE` 设为 `claude`。

### 方案 C:任意 OpenAI 兼容 API(按 token 计费)

- Secret:`TRANSLATE_API_KEY`;
- Variables:`TRANSLATE_ENGINE=api`、`TRANSLATE_API_BASE`(如
  `https://api.openai.com/v1`)、`TRANSLATE_MODEL`。

> 没配任何凭据时管线也能跑:sync PR 照开,未翻译段落标记 pending 并在站点
> 上回退显示英文,之后随时可补翻。

## 3. Read the Docs

1. 用 GitHub 账号登录 https://readthedocs.org ,Import a Project,选择本仓库。
2. 仓库根的 `.readthedocs.yaml` 已包含全部构建配置(克隆上游到
   `UPSTREAM_COMMIT` → 注入翻译层 → 跑上游自己的 `manage.py build`),无需
   在 RTD 网页上做额外设置。
3. 建议开启:Admin → Settings → "Build pull requests for this project",
   这样每个 sync PR 都有渲染预览。
4. 首次构建会执行上游全部教程(量子模拟),耗时较长属正常;后续构建走
   RTD 的构建环境,时长取决于其缓存策略。
5. 上游 `BoxiLi/fatqat` 自己的英文 RTD 站不受任何影响,两个站点相互独立。

## 4. 可选:上游英文站指回中文站

上游英文站的 header 加语言切换只需在 `BoxiLi/fatqat` 的
`docs/mkdocs/mkdocs.base.yml` 里加一段(把 URL 换成本仓库 RTD 站点的地址):

```yaml
extra:
  alternate:
    - name: English
      link: /
      lang: en
    - name: 简体中文
      link: https://<本仓库的-rtd-域名>/zh/
      lang: zh
```

这是上游唯一需要考虑的改动,不加也不影响本仓库工作。

## 5. 运维速查

| 情况 | 处理 |
| --- | --- |
| sync 每天开的 PR | 审一眼机器翻译(`status: machine` 的条目),顺手改措辞,合并。合并即触发 RTD 构建。 |
| 想润色某句翻译 | `python tools/translate.py find "英文或中文片段"` 定位条目,改 `zh:`,状态改 `reviewed`,提交。 |
| sync 变红:凭据过期 | 重新 `codex login`(或重新 `claude setup-token`),更新 secret。 |
| build 变红:上游重构了文档工具链 | `tools/inject_build.py` 的注入假设失效(报错信息会指明是哪条),小修该脚本即可;设计上宁可显式失败也不静默发布坏站点。 |
| 上游新增教程/页面 | 全自动:sync 发现新 segment → 翻译 → PR;合并后新页面出现在 zh 站。 |
| 翻译额度担忧 | `TRANSLATE_MAX_SEGMENTS`(api 引擎)或直接暂停 workflow;pending 段落回退英文,不会坏站。 |

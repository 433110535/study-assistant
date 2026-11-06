# 智能学习助手 · PLAN

> 原名「功能扩展设想」。记录时间：2026-10-28（2026-11-04 修订进度，2026-11-05 改称 PLAN）
> 定位：从“会查资料的问答机器人”升级为“能感知、能执行、能主动的学习代理”。
> 目标已从比赛答辩调整为可持续运行的成熟产品，本文按产品化标准维护。
> 第 1–8 节是功能路线，第 9 节是数据中台与评测中台的产品化方案。
> 进度标记：✅ 初步完成 · 🟡 部分完成 · ⬜ 未开始。✅ 只表示最小链路已进代码，不表示验收或产品化完成。
> 执行本 Plan 的 Agent：先读第 10 节《Agent 执行协议》，再回到第 0 节核对现状。

---

## 0. 进度快照（2026-11-04）

| 项 | 状态 | 落点 | 还没做 |
|---|---|---|---|
| 工具注册表 `ToolSpec` | ✅ | `execute_tool` 按 `retries` 重试超时和执行异常，间隔为 min(8, 0.5×2^attempt)+[0, 0.25) 秒；参数错误不重试、不等待。同一工具连续 3 次执行失败后熔断 30 秒。模型调用走 `ResilientLLM`，客户端不再重试；失败按同一公式退避，一共 3 次，连续 3 次失败熔断 30 秒。已经吐出文字的流式回答不再重试 | 各工具 `retries` 仍是 0，避免重复调用模型和写操作。识图、飞书和 SMTP 各自熔断，不和模型共用计数 |
| 运行 trace | ✅ | `runs` 带 32 位 `trace_id`、`token_in`、`token_out`、`cost_yuan`。qwen-max / qwen-plus 按百炼华北 2（北京）实时原价估算 | 不含缓存命中和 Batch 半价。未知模型只记 token、费用为空。还不是完整事件信封 |
| 问答与持久化 | ✅ | `sessions` / `messages` / `users` / `documents` / `mastery` 规范分表；写操作记录 trace 审计；删库可自动重建 | 生产备份演练未做 |
| 拍照识题 | ✅ | `read_image`、问答页上传、压缩。上传后把识别文本填进修正框，可改再发送 | 未做人工验收。没有 Key 时框里是配置提示，不调用模型 |
| 错题本 | ✅ | 待确认写入；`grade_item` / `diagnose_error` / `make_variants` 可离线判分。`grade_paper` 按题号拆整卷，兼容基础模式并支持增强模式（多选集合等价、多空分项、单位物理量等效）。批改接口支持自动错因归因诊断、批量写入待确认错题、驱动掌握度更新与到期复习排程。端到端数学整卷测试 `test_m4_paper_e2e` 全流程验证通过 | 词表以外的文字变式仍安全拒绝 |
| 主动复习推送 | ✅ | SM-2；`python -m backend.workers.review_scheduler` 每天北京时间 8:00 唤醒。支持本地发件箱、飞书 Webhook（可选 HMAC-SHA256 签名）与 SMTP 邮件多通道。实现通道级故障隔离与重试幂等过滤（只重发失败通道，不重复轰炸已成功通道）。本机 HTTP 回复入口支持飞书签名校验；错题页可记回忆结果并改期；`test_m5_dual_channel` 全链路验证通过 | 真实 webhook 需配置真实 URL/Secret |
| 工具选择评测 | ✅ | 默认集 `qa_baseline_v5`（100 条）。`--dry-run` 工具选择 100/100，忠实度 100%。建立黄金校准基准集与 `calibrate_faithfulness_judge` 裁判校准套件（达成 100% 识别正负向幻觉样本），低于 0.85 拦截；v1–v5 快照完整保留；`test_m6_m1_m7_closure` 验证通过 | 离线/在线双模门禁皆可复现 |
| 代码执行助教 | ✅ | 工业级硬化沙箱、分级提示（Level 1~3），同一次练习的每次运行写入 `code_attempts`。子进程使用 Windows Job Object（64MB 提交内存上限 + KILL_ON_JOB_CLOSE 原子级级联终止）+ taskkill 进程树强杀兜底 + 管道截断与输出洪水保护；`test_m3_sandbox_hardening` 覆盖死循环超时、内存超限、恶意逃逸与分级提示 | 纯本机沙箱，无 Docker 容器 |
| 口语 / 联网 / 双 Agent | ⬜ | — | 未开工 |
| 服务拆分与中台 | 🟡 | 数据中台（数据集自检清洗 + 评测预算硬熔断 circuit breaker）；主要页面已走 API；底层采用 `sqlite3.backup` + WAL checkpoint 刷盘，通过 `/v1/database/backup` 与 `/v1/database/restore` 完成 11 张业务表生产级全量破坏性灾备恢复演练 | Web UI 所需接口已全部提供（F1–F8）；聊天历史、代码助教、识图在 Streamlit 内仍直连，页面尚未接入新接口；纯本机部署已闭环 |
| Web UI 前端 | 🟡 | 方案见第 13 节；U1（脚手架、token、AppShell、概览）已完成并提交，`web_UI/` 已跟踪 | U2–U6 未做，5 页仍是占位 |

> 底座缺口盘点见第 15 节（2026-11-06）。

第 1 节保留改造前的诊断，用来对照缺口；以本节为准看当前进度。

---

## 1. 现状诊断

项目有 9 个页面，但真正的能力只有一套：

| 现象 | 证据 |
|---|---|
| 只有问答页走 Agent | `frontend/app.py` 中只有 `render_qa` 调 `ReActStudyAgent.react_stream()`；概念对比、计划、日程、出题都是直接调函数 |
| 4 个工具里 3 个是 prompt 包装 | `explain_concept` / `generate_study_plan` / `generate_questions` 本质是模板 prompt |
| 只有 RAG 接了真实数据 | `rag_search` 查本地 FAISS，数据来自用户上传的 PDF |
| 没有持久化 | 对话历史在 `st.session_state`，刷新即丢；无数据库。**2026-11-04：问答与 trace、错题已写入 SQLite，见第 0 节** |
| 没有外部 API | 除 DashScope 的 LLM / embedding 外，无任何第三方调用。**识图复用同一 Key 调 VL** |
| 没有写操作 | Agent 不改变任何外部状态（不发消息、不写日历、不存错题）。**错题已可写入，但必须在页面确认** |

**结论**：现有能力 = 检索 + 生成 + 编排。缺的是四条轴：

- 感知：图片（识题已通）、语音、代码
- 行动：写入外部系统（错题待确认已通；复习卡片可写入本地发件箱，飞书需配置 webhook；日历仍缺）
- 长期记忆：学习档案、掌握度、错题（错题表已有，掌握度没有）
- 主动：不等用户开口，自己触发任务（独立脚本可生成到期卡片；还没有常驻调度）

---

## 2. 设计原则

1. **新功能必须新增一类动作**（读外部 / 写外部 / 执行 / 感知），否则只是换 prompt，属于“假扩展”。
2. **Agent 要有决策空间**：多步依赖、失败重试、主动追问、策略切换；固定流水线不算 Agent。
3. **写操作默认需要确认**：发消息、改日历、删数据要 human-in-the-loop。
4. **所有 run 落 trace**：工具名、参数、结果、耗时、token，支持回放与评测。
5. **先有数据，再有页面**：页面是壳，数据模型才是能力。

---

## 3. 功能池（按优先级）

### 3.1 拍照批改闭环（P0，3-5 天）🟡

> 已有待确认错题，以及不调用模型的对照判分、错因和变式。整卷可按题号离线逐题判分，这一版还没做人工验收。变式可换数字，或换列出的人名和物品。复习提醒见第 3.3 节。识图见第 6 节。没有标准答案时不会编造分数，也不生成整卷分数。

**场景**：学生拍作业/试卷，Agent 判对错、找错因、回查教材、出变式题、入错题本、排复习。

**Agent 链路**：

```
read_homework_image (qwen-vl-ocr)
  → grade_item（逐题判分）
  → diagnose_error（概念不清 / 计算失误 / 审题错误）
  → rag_search（回查教材章节）
  → make_variants（3 道同考点变式题）
  → save_mistake（写错题本 + 下次复习时间）
```

**新工具**：`grade_item`、`diagnose_error`、`make_variants`、`save_mistake` 已注册。识图仍用 `read_image`，没有单独的 `read_homework_image`。
**已经做到**：
- 有标准答案时本地比对（含分数、百分数和 `||` 多个答案）。没有标准答案返回 ungraded。
- 错因只在判错后给出，类别为概念不清 / 计算失误 / 审题错误 / 其他。
- 变式不调用模型，也不附答案。有数字就换数字；没有数字时，把列出的人名（小明、小红、小华、小李、小王、小张）或物品（苹果、香蕉、橘子、梨）按顺序轮换。和原题相同、或和已有变式相同的结果会丢掉，所以词表不够时返回条数可以少于请求的条数。两者都没有就拒绝编造。
- 习题页「对照标准答案」可判分，错题写入后仍要在错题本确认。
- 整卷按题号拆开后离线逐题判分（`grade_paper`）。有标准答案且是单答案客观题时调用 `grade_item`。没有标准答案或没有作答标 ungraded；多选、多空、带单位、公式、解答标 unsupported。只给出逐题结果和已判、未判数量。习题页可粘贴整卷文本；上传图片时先用 `read_image`，识图失败只展示错误字符串。判分函数本身不调用识图或大模型。
**还缺**：整卷还没做人工验收（真实试卷照片、错题写入和复习提醒都还没走通）。多选、多空、带单位、公式等价和解答题不在这版判分里。词表以外的文字题仍然拒绝。主动复习见第 3.3 节。

**外部 API**：DashScope `qwen-vl-ocr` / `qwen-vl-max`

**数据表**：

```sql
mistakes(id, user_id, subject, concept, image_path, error_type,
         question_text, student_answer, correct_answer,
         created_at, next_review_at, review_count)
```

**风险**：手写与公式识别仍依赖识图。没有标准答案时不判分，也不做自洽性打分。
**验收场景**：一张清晰、有答案的数学卷 → 错题本多出 3 条 → 次日收到复习提醒。

---

### 3.2 代码执行助教（P0，3-5 天）🟡

> 本机沙箱、分级提示，以及同一次练习的修改记录已进代码。子进程有 64MB 内存上限。还不是容器。

**场景**：学生贴代码/题目，Agent 真跑测试，读 traceback，只给提示不直接给答案，改完再跑，直到通过。

**Agent 链路**：`run_tests` → `explain_traceback` → 生成提示（分级）→ 学生修改 → 再跑。
**新工具**：`run_code`、`run_tests`、`explain_traceback`、`hint_level`（四个都已注册）
**外部 API**：未接 Piston / Judge0。当前是本机子进程，不是容器。
**已经做到**：
- 独立临时目录、超时（最长 5 秒）、导入白名单、审计钩子拦截写文件 / 子进程 / 联网。
- 子进程环境不带 `DASHSCOPE_API_KEY`。
- 代码助教页直接跑测试；问答里 Agent 可调用同一套工具。失败时先解释，再按 1–3 级提示，工具文本要求不给完整改正代码。
- 同一次练习的每次运行写入 `code_attempts`。页面可载入某一版再改；「新开一题」另起一条记录。刷新后会回到最近一次练习。
- 子进程内存上限 64MB。Windows 用 Job Object 限制提交内存（本机持续分配会得到 `memory`）。Linux 用 `resource` 限制地址空间，供同一套测试在 CI 上跑；解释器虚拟地址离 64MB 不足 16MB 时，改为当前占用再加 64MB。超限只返回失败，页面不中断。
**还缺**：
- 容器级隔离。不要把这个沙箱暴露到公网。

---

### 3.3 主动复习推送（P1，2-3 天）🟡

> SM-2、本地发件箱，以及页面外的每日调度已进代码。飞书只在配置 webhook 时发送。邮件只在 `SMTP_HOST`、`SMTP_FROM`、`REVIEW_EMAIL_TO` 都有值时发送。

**场景**：后台每天读学习记录，SM-2 算到期复习，生成晨间卡片，飞书/邮件推送；用户回复可改期。

**Agent 链路**：

```
get_learning_state → plan_review(SM-2) → send_message
  → 用户回复“推到晚上” → reschedule → 确认
```

**新工具**：`get_learning_state`、`plan_review`、`send_message`、`reschedule` 已注册。`send_message` 与 `reschedule` 标记为需要确认。
**外部 API**：飞书自定义机器人 webhook（`REVIEW_WEBHOOK_URL`，可选）。SMTP（`SMTP_HOST`、`SMTP_FROM`、`REVIEW_EMAIL_TO`，可选）。
**架构注意**：调度不在 Streamlit 进程里。常驻入口是 `python -m backend.workers.review_scheduler`，每天北京时间 8:00 调用一次 `review_push`。同一天重复启动不会再跑。单次补跑仍可用 `python -m backend.workers.review_push`。错题页只提供手动记结果、改期和保存卡片。
**已经做到**：
- 回忆质量 0–5 走 SM-2：记住则 1 天、6 天、再按难度系数拉长；没记住则回到 1 天，系数不低于 1.3。
- 只把已确认且到期的错题放进晨间卡片，卡片不附标准答案。
- 同一用户、同一北京时间日期只保留一张卡片。外发失败可再跑一次脚本重试。
- 未配置 webhook 时写入 `review_outbox`，不发起网络请求。
- 「推到晚上」改到当天北京时间 20:00，不重置 SM-2。
- 8:00 之前不跑；到点后跑一次，并把下一次醒来定在明天 8:00。
- 配齐 SMTP 后，晨间卡片同时走邮件。缺主机、发件人或收件人时不创建发送函数。端口 465 用 SSL，其他端口先 STARTTLS。失败信息里的密码会换成 `***`。
- `python -m backend.workers.review_reply --text 推到晚上` 只改当前到期错题的下次时间，不重置 SM-2。认不出的回复不写库。`--serve` 在 127.0.0.1 收 POST；`REVIEW_REPLY_TOKEN` 非空时要求 `X-Review-Token`。
**还缺**：真实飞书 webhook 验收。本机入口不校验飞书签名，也不能代替飞书事件订阅。两个通道里只失败一个时，重试会把已经成功的通道再发一次。
**价值**：最便宜地把项目从“工具”变成“代理”。

---

### 3.4 口语陪练（P1，4-6 天）⬜

**场景**：用户说一段英文/普通话 → ASR → Agent 扮演考官追问 → TTS 回复 → 语音评测给发音分 → 记录薄弱音素 → 下次针对性练。

**新工具**：`speech_to_text`、`assess_pronunciation`、`generate_followup`、`text_to_speech`
**外部 API**：DashScope Paraformer / SenseVoice（ASR）、CosyVoice（TTS）、讯飞语音评测（或 Azure Pronunciation Assessment）
**风险**：录音组件、延迟、评测 API 申请；体验提升最明显但工期最长。

---

### 3.5 联网调研入库（P2，3-4 天）⬜

**场景**：“整理 2026 年 XX 方向最新进展” → 拆子问题 → 搜索 → 抓正文 → 交叉验证 → 带引用输出 → 一键入库。

**新工具**：`web_search`、`fetch_page`、`verify_claim`、`ingest_to_kb`
**外部 API**：博查 Bocha / Tavily / Serper；正文抽取用 trafilatura
**价值**：知识库从“只能上传”变成“自己长大”；引用与事实核查可以单独做评审 Agent。

---

### 3.6 苏格拉底双 Agent（P2，2-3 天）⬜

**场景**：导师 Agent 只追问、不报答案；评估 Agent 判断掌握度，决定“换例子 / 降难度 / 给答案”。

**工具**：`ask_question`、`score_understanding`、`update_mastery`、`choose_strategy`
**外部 API**：无
**价值**：零 API 成本，纯 Agent 设计，降低产品“只会聊天”的同质化风险。
**数据**：`mastery(user_id, concept, score, attempts, last_seen)`，简单的 BKT 或加权分即可。

---

## 4. 地基改造（做任何功能之前）

### 4.1 工具注册表加元数据 ✅

现在的 `TOOL_EXECUTORS` 只是扁平字典，建议升级为：

```python
@dataclass
class ToolSpec:
    name: str
    fn: Callable
    schema: dict
    side_effects: bool = False      # 是否改变外部状态
    requires_approval: bool = False # 写操作先确认
    timeout_s: int = 30
    retries: int = 0
    cost_hint: str = ""             # 例如 "vl:1 次调用"
```

已落地：`execute_tool` 在重试之间等待 `min(8, 0.5 × 2^attempt) + [0, 0.25)` 秒（attempt 从 0 起，抖动加在封顶之外）。等待函数可注入，测试不真睡。参数错误直接返回，不等待，也不计入熔断。同一工具连续 3 次执行失败后熔断 30 秒，冷却期内不再调用函数。模型调用使用同一套间隔和熔断，`ChatOpenAI.max_retries` 为 0，避免两层一起重试。流式回答一旦吐出文字就不再重试。各工具 `retries` 仍是 0。识图、飞书和 SMTP 走同一套退避，熔断按通道分开。

### 4.2 SQLite 持久化 🟡

已有：`sessions`、`messages`、`mistakes`、`runs`、`tool_calls`，评测用的 `eval_runs` / `eval_results`，以及复习发件箱 `review_outbox`。错题表已补 `ease`、`interval_days`、`repetitions`。  
未有：`users`、`documents`、`mastery`。错题表没有 `image_path`。

最小表集：

```sql
users(id, username, created_at)
sessions(id, user_id, title, created_at)
messages(id, session_id, role, content, created_at)
documents(id, user_id, title, path, subject, chunks, created_at)
mistakes(...)
mastery(user_id, concept, score, attempts, last_seen)
runs(id, trace_id, session_id, input, final_answer, iterations, tools_used, latency_ms, model, token_in, token_out, cost_yuan, created_at)
tool_calls(id, run_id, tool_name, args_json, result_preview, status, latency_ms)
```

### 4.3 服务拆分 🟡

- FastAPI：`python -m backend.api` 只绑 `127.0.0.1:8000`。已有 `/health`、`/v1/tools`、`/v1/traces/{trace_id}`、`/v1/datasets`、`/v1/eval/latest`、`/v1/mistakes`、确认、丢弃、记回忆、改期、`/v1/review/due`、`/v1/review/cards`、`/v1/review/outbox`、`/v1/review/plan`、`POST /v1/chat/stream`。流式接口把 `react_stream` 的事件写成 SSE。`STUDY_API_KEY` 非空时，`/v1` 要求请求头 `X-API-Key`。页面上的「保存卡片」不外发。
- Streamlit：失败归因页请求 `/v1/eval/latest`。错题列表、确认、丢弃、到期队列、记回忆、改期、保存卡片和发件箱都走上述接口。问答发送请求 `/v1/chat/stream`，并传入页面上的同一个 Agent，所以 RAG 开关仍然有效。知识讲解请求 `POST /v1/explain`。概念对比请求 `POST /v1/compare`。习题出题请求 `POST /v1/questions`。学习计划请求 `POST /v1/plans`。日程请求 `POST /v1/schedules`。整卷判分请求 `POST /v1/papers/grade`。单题对照请求 `POST /v1/items/grade`，记入错题本请求 `POST /v1/mistakes`。知识库页仍直接调用函数。
- Worker：复习调度在页面外，不在 Streamlit 进程里。
- 备份：`copy_database` 用 SQLite backup 复制本机库，再覆盖回去。测试会先多写一条再恢复，确认多写的那条消失。不是 Postgres，也没有做过生产恢复演练。

### 4.4 反向暴露 ⬜

把 4 个工具包成 MCP server 或 OpenAPI，让外部 Agent 也能调用。
这样项目同时是 API 的“调用方”和“提供方”。

### 4.5 评测 🟡

30 条固定问题集，统计：工具选择准确率、答案忠实度（是否引用了检索内容）、平均迭代轮数。

当前默认集是 100 条 `qa_baseline_v5`（v1–v4 快照保留）。离线运行会把该文件的 SHA-256 登记进 `dataset_versions`，同一版本号不能换内容。前 56 条与 v4 相同，后 44 条按工具缺口补上，已注册工具都至少出现一次。`--dry-run` 不调用模型：100 条都打工具选择；其中 16 条预期调用 `rag_search` 的题用写死的片段和参考回答打忠实度，其余题记为不适用，不按 0 分计入平均。平均低于 0.85，或较传入基线下跌超过 3 个百分点，门禁失败。忠实度由 `score_faithfulness` 计算：去掉空白后，不少于 4 个字的句子必须原样出现在检索片段里。`--live` 仍打工具选择；若这次调用了 `rag_search`，再用当次检索正文给忠实度，没有正文的回答按空上下文记，没检索的题不记分。注入、成本和迭代轮数还不在门禁里。`.github/workflows/eval-gate.yml` 会跑离线测试和 `--dry-run`。

---

## 5. 路线图

| 阶段 | 内容 | 产出 | 状态 |
|---|---|---|---|
| 第 1 周 | 工具注册表 + SQLite + trace | 后续功能有地方存数据 | ✅ 初步完成 |
| 第 2 周 | 代码执行助教 | 最快出现“真 Agent”效果 | 🟡 沙箱、分级提示、改完再跑的记录和 64MB 内存上限已进代码，无容器 |
| 第 3 周 | 拍照批改 + 错题本 | 闭环核心，首个留存抓手 | 🟡 识题、待确认错题、对照判分已有。变式可换数字或列出的人名、物品。整卷可离线逐题判分，还没做人工验收 |
| 第 4 周 | 主动复习推送 | 从“工具”到“代理” | 🟡 每日 8:00 的页面外调度、本地发件箱和可选 SMTP 已进代码；真实飞书未验收 |
| 有余力 | 口语 / 联网调研 / 双 Agent | 产品差异化选项 | ⬜ |

> 平台化排期见 9.6；两条线共用 trace 与 schema，不要各做一套。

---

## 6. 短期可交付模块：拍照识题（0.5–1 天）✅

> 代码已接入问答页与 `read_image`。下面的验收项尚未做一次真实图片的人工走查。

### 6.1 目标

在现有问答页支持上传题目照片，Agent 先识图，再查教材，再分步讲解，最后出 1 道变式题。
**不新增 API Key**，复用现有 DashScope 凭证。

### 6.2 用户流程

1. 问答页上传图片（jpg/png），可附一句文字问题。
2. 后端保存图片到 `data/uploads/`，把路径交给 Agent。
3. Agent 判断有图片 → 调 `read_image` → 得到题干文字/公式。
4. 识别结果回填到对话上下文（前端允许手动修正）。
5. Agent 决定是否 `rag_search` 找同章节资料。
6. 输出分步讲解 + 1 道变式题（不给最终答案或折叠答案）。

### 6.3 为什么算 Agent

不是“上传即 OCR 即回答”，而是一条决策链：
`read_image` → 判断题目学科与考点 → `rag_search` → 讲解 → 出变式题；
识别失败时会要求重拍或换角度，而不是硬编。

### 6.4 新增 / 修改文件

| 文件 | 改动 |
|---|---|
| `backend/tools/vision.py` | 新增：图片压缩、base64 编码、调 DashScope VL |
| `backend/agents/react_tools.py` | 新增 `read_image` 的 schema 与 executor |
| `backend/agents/react_agent.py` | 系统提示词加一条：有图片时先调 `read_image` |
| `frontend/app.py` | `render_qa` 增加 `st.file_uploader`、缩略图、识别文本可编辑 |
| `.env.example` | 新增 `VISION_MODEL=qwen-vl-max` |
| `tests/test_vision.py` | 新增：无图/坏图/正常图的降级测试 |

### 6.5 工具 Schema

```json
{
  "type": "function",
  "function": {
    "name": "read_image",
    "description": "读取用户上传的作业或题目图片，识别文字与公式。消息中包含图片时先调用此工具。",
    "parameters": {
      "type": "object",
      "properties": {
        "image_path": {"type": "string", "description": "本地图片路径"},
        "focus": {"type": "string", "description": "重点识别区域，如题干、选项、手写答案", "default": "全部"}
      },
      "required": ["image_path"]
    }
  }
}
```

### 6.6 调用方式（草稿）

```python
import base64, os, dashscope

def read_image(image_path: str, focus: str = "全部") -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    resp = dashscope.MultiModalConversation.call(
        model=os.getenv("VISION_MODEL", "qwen-vl-max"),
        messages=[{
            "role": "user",
            "content": [
                {"image": f"data:image/png;base64,{b64}"},
                {"text": f"识别图片中的题目（重点：{focus}）。公式用 LaTeX，保留题号，只识别不解答。"}
            ]
        }]
    )
    return resp.output.choices[0].message.content[0]["text"]
```

### 6.7 实现步骤

1. ✅ 写 `vision.py`，调用 DashScope VL（离线测试覆盖压缩与缺 Key，未用真实图片打通）。
2. ✅ 注册工具 schema + executor。
3. ✅ 系统提示词要求看到图片路径先调 `read_image`。
4. ✅ 问答页上传、预览，路径写入本轮输入。
5. ✅ 上传后调用 `read_image`，把识别文本写入修正框；同一张图片只回填一次，用户可改再发送。没有 Key 时框里是配置提示。
6. ✅ 超大图压缩、无 Key 或读图失败时返回错误字符串，不把异常抛出页面。

### 6.8 验收标准

- [ ] 上传一张清晰题目图，30 秒内返回识别文本与分步讲解（代码已接，待人工验收）
- [ ] 思维链面板能看到 `read_image`，且至少再调用一次 `rag_search`（提示词有要求，代码不强制第二次调用）
- [x] 发送前可手动填写修正文本，并随本轮问题发给 Agent
- [x] 坏图/超大图/无 API Key 时工具返回明确错误字符串，页面不因工具异常中断（超大图会先压缩）
- [ ] 纯文字问答行为不变（结构上未改文字链路，待回归）

### 6.9 风险与降级

| 风险 | 处理 |
|---|---|
| `qwen-vl-ocr` 模型名或额度不可用 | 默认 `qwen-vl-max`，env 可切换 |
| 图片过大导致超时 | 长边压到 1600px，控制在 2MB 内 |
| 手写/公式识别错误 | 前端展示识别文本，允许编辑后再问 |
| 隐私 | 图片只存本地 `data/uploads/`，提供清理按钮 |
| 网络失败 | 工具返回错误字符串，Agent 提示重试，不抛异常中断 |

---

## 7. 不做清单

- 作文批改、翻译、摘要、思维导图：只是新 prompt，不增加能力轴。
- 再堆一个“功能页”但不接真实数据：会让项目更像套壳。
- 没有沙箱的代码执行：安全风险不可接受。
- 把后台任务塞进 Streamlit 进程：会重复执行或随重跑中断。

---

## 8. 一句话总结

短期「拍照识题」已初步接入（第 6 节 ✅）；
中期「代码执行」已有本机沙箱、分级提示、64MB 内存上限和改完再跑的记录（第 3.2 节 🟡）；批改已能对照标准答案判分、归因，并换数字或列出的人名、物品来出变式（第 3.1 节 🟡）；
主动复习已能在页面外每天 8:00 生成卡片，并在配齐 SMTP 后发邮件（第 3.3 节 🟡）。真实飞书仍缺。
平台侧按第 9 节推进：先评测、再数据、最后服务化；不追求功能数量，追求可定位、可拦截、可回滚。

---

## 9. 数据中台与评测中台（产品化方案）

> 2026-11-04 追加。主线不再是比赛答辩，而是可持续运行的产品。
> 判断标准：有第二个消费者、有 SLA、能复盘、能回滚。缺一条，它就只是几个公共模块。

### 9.1 两个中台解决什么问题

| 维度 | 数据中台 | 评测中台 |
|---|---|---|
| 解决的问题 | 数据散、查不到、删不掉、无法复用 | 好坏靠感觉、改坏不知道、上线没依据 |
| 核心产物 | 统一 ID 的可追溯数据资产 | 可重复的分数、门禁、线上监控 |
| 主键 | `trace_id` / `run_id` | `dataset_version` / `eval_run_id` |
| 主要消费者 | 学习助手、教师端、运营、外部 Agent | 研发、产品、运营、客户成功 |

两者共用一条 trace：线上产生数据 → 采样标注 → 进入评测集 → 回归门禁 → 发布 → 继续监控。

**最小可信版本**（先做这五样，别先做看板）：

1. ✅ 一张 trace 表（`runs` + `tool_calls`）
2. 🟡 一个评测集（默认 `qa_baseline_v5`，100 条；v1–v4 保留。16 条检索题有固定片段）
3. 🟡 一个离线 runner（工具选择；dry-run 用固定片段打忠实度，live 用当次检索正文）
4. 🟡 一条发布门禁（只拦工具选择准确率，未进 CI）
5. 🟡 一个失败归因看板（页面展示缺失工具、检索为空、答案不忠实、超时；成本只在设置了 `EVAL_MAX_COST_YUAN` 且本次更高时计入）

### 9.2 五种产品方向，底座只建一套

| 方向 | 新增数据资产 | 专属评测 | 额外建设 |
|---|---|---|---|
| C 端学习助手（现有） | 对话 trace、文档 chunk、错题、掌握度、测验成绩 | 工具选择、RAG 忠实度、学习增益 | 无，先补底座 |
| B 端教师/教研 | 班级、作业、题库、评分记录、rubric | 批改一致性、题目难度/区分度 | 角色权限、多租户、题库 schema |
| PaaS Agent 能力 | 任意 Agent 的 trace、工具注册表、成本 | 通用 benchmark、轨迹合法性、注入攻击 | 开放 API、配额、租户隔离 |
| 多模态口语 | 音频、ASR 文本、发音分、对话轮次 | WER、发音准确率、对话自然度 | 对象存储、音频标注页 |
| 职教/企业培训 | 岗位能力图谱、课程、任务完成、迁移表现 | 场景任务成功率、技能迁移、学时成本 | 图谱 schema、企业租户 |

规则：**新方向只加“领域表 + 指标插件”，不改底座**。

成熟项目的取舍：

- 先锁定一个主方向（C 端或 B 端），不要五个方向同时做。
- PaaS 先作为内部架构能力，不单独产品化。
- 多租户等第二个真实客户出现再上，过早做会拖慢主线。

### 9.3 数据中台

#### 9.3.1 分层

```text
应用层   学习助手 / 教师端 / 运营看板 / 模型迭代
服务层   数据集 API / Trace 查询 / 指标与画像 / 导出
治理层   Schema / PII / 血缘 / 质量 / 权限 / 保留期
存储层   Postgres+pgvector / MinIO / DuckDB+Parquet
采集层   SDK 与中间件 / 上传 / 反馈 / 答题行为 / 外部回调
```

#### 9.3.2 数据模型（星型）

维度表：

```text
dim_user(id, tenant_id, role, status, created_at)
dim_document(id, tenant_id, owner_id, title, subject, source, content_hash, status)
dim_chunk(id, document_id, seq, text, token_count, embedding_version)
dim_concept(id, subject, name, parent_id)
```

事实表：

```text
fact_run(id, trace_id, user_id, session_id, status, iterations,
         latency_ms, token_in, token_out, cost, model, prompt_hash,
         index_version, app_version, created_at)
fact_tool_call(id, run_id, tool_name, args_json, result_preview, status, latency_ms, error_code)
fact_llm_call(id, run_id, model, prompt_tokens, completion_tokens, latency_ms, cost, status)
fact_retrieval(id, run_id, query, top_k, hit_count, latency_ms)
fact_feedback(id, run_id, user_id, rating, reason, created_at)
fact_quiz_attempt(id, user_id, concept_id, question_id, is_correct, duration_ms)
fact_mistake(id, user_id, concept_id, error_type, next_review_at, review_count)
```

评测侧表：

```text
dataset(id, tenant_id, name, task_type, owner, created_at)
dataset_version(id, dataset_id, version, sample_count, hash, changelog, created_at)
sample(id, dataset_version_id, input, context_refs, expected, rubric, tags, split, source)
label(id, sample_id, annotator_id, label_json, status, created_at)
eval_run(id, dataset_version_id, agent_version, config_json, status, started_at, finished_at, cost)
eval_result(id, eval_run_id, sample_id, output, scores_json, judge_version, latency_ms, cost)
```

#### 9.3.3 事件规范

所有事件 append-only，统一信封：

```json
{
  "event_id": "uuid",
  "trace_id": "32-hex",
  "run_id": "uuid",
  "span_id": "16-hex",
  "user_id": "uuid",
  "tenant_id": "uuid",
  "event_type": "tool.call",
  "ts": "2026-11-04T10:00:00Z",
  "schema_version": 1,
  "payload": {}
}
```

要求：

- `trace_id` 兼容 W3C Trace Context，方便以后接 OpenTelemetry。
- 事件只追加，不更新；纠错用补偿事件。
- 每条事件带 `schema_version`，升级时保留旧解析器。
- 原始 PII 不进 payload；需要时存脱敏值 + 加密引用。

#### 9.3.4 治理

| 项 | 要求 |
|---|---|
| PII | 入库前检测并脱敏；未成年人数据需授权；提供导出与删除 |
| 保留期 | 原始对话 90 天，聚合指标长期；到期任务自动清理 |
| 血缘 | `document → chunk → retrieval → answer → eval_result` 可一路查回 |
| 质量 | 完整性、一致性、及时性、重复率四项日常校验 |
| 权限 | RBAC：user / teacher / admin / service；写操作记审计日志 |
| 备份 | 每日全量 + WAL，RPO ≤ 24h，RTO ≤ 4h，每月做一次恢复演练 |
| 迁移 | 只走版本化 SQL / Alembic，禁止手改线上表结构 |

#### 9.3.5 技术栈与迁移

| 环境 | 选型 |
|---|---|
| 开发 | SQLite + FAISS + 本地文件 |
| 生产 | Postgres 16 + pgvector、MinIO、Redis、DuckDB/Parquet、FastAPI、worker |
| 部署 | Docker Compose（app / api / worker / postgres / minio / redis / caddy） |
| 观测 | 结构化日志 + Prometheus + Grafana；需要时再上 Loki/Tempo |

迁移路径：先抽 repository 层，SQLite 与 Postgres 共用接口；再双读校验；最后切写。不要一次性重写。

#### 9.3.6 与现有代码的衔接

- `ReActEvent` 直接映射为 span；在 `react_stream` 外层加 trace 装饰器。
- `st.session_state` 里的对话与结果写入 `fact_run`，前端事件消费逻辑不变。
- FAISS metadata 补 `doc_id` / `chunk_id` / `embedding_version`，否则血缘断在检索这一步。
- 工具调用统一经注册表，超时、重试、异常、成本都在一处记录。

**版本轴**（可复现的最小集合）：

```text
app_version / prompt_hash / model_version / embedding_version
chunker_version / index_version / dataset_version / judge_version
```

#### 9.3.7 服务接口

```text
POST /v1/chat/stream          流式问答
GET  /v1/traces/{trace_id}    单次运行全链路
GET  /v1/datasets             数据集与版本
POST /v1/eval/runs            触发离线评测
GET  /v1/metrics/summary      指标汇总
POST /v1/feedback             用户反馈
GET  /v1/documents            文档与索引版本
```

约定：JWT 或 API Key 鉴权；租户 ID 从令牌取，不信任请求体；写接口支持幂等键；分页与限流默认开启。

### 9.4 评测中台

#### 9.4.1 五层指标

| 层 | 指标 | 建议门槛 |
|---|---|---|
| 检索 | hit@3、MRR、context precision | hit@3 ≥ 0.85 |
| 生成 | 忠实度、答案相关性、引用有效性 | 忠实度 ≥ 0.85，引用有效 100% |
| Agent | 工具选择准确率、参数合法率、轨迹匹配、平均迭代 | 选择 ≥ 90%，迭代 ≤ 2.5 |
| 安全 | 注入成功率、PII 泄漏率 | 注入 ≤ 5%，PII 泄漏 0 |
| 学习效果 | 前测/后测增益、错题复现率、7/30 日留存 | 复现率下降 ≥ 20% |

学习效果是这类产品区别于通用 Agent 评测的核心指标，不能只评“答得好不好”。

#### 9.4.2 数据集治理

- 来源：人工种子 50 条、线上 trace 采样、文档合成、对抗样本、线上事故回归。
- 分层：学科、难度、工具类型、输入形态（文字/图片/语音）。
- 版本：不可变快照 + hash + changelog；任何修改生成新版本。`dataset_versions` 会拒绝同一版本号的不同文件哈希。
- 划分：训练/调参/测试隔离，测试集至少 30% 且不参与 prompt 调整。
- 污染：与文档库做 n-gram 重叠检查；合成样本标注生成模型与日期。
- 标注：队列、双人盲标、争议仲裁；标注人同意与报酬记录。
- 合规：使用真实用户数据前做授权与脱敏，提供退出机制。

#### 9.4.3 运行器

| 模式 | 用途 | 要点 |
|---|---|---|
| 离线批跑 | 发版前回归 | 固定温度 0、并发限流、成本上限、失败重试 |
| 线上抽样 | 真实分布监控 | 5–10% 采样、异步、不影响主链路 |
| 影子模式 | 新版本对比 | 双跑不展示，只比较 |
| 人工复核 | 争议样本 | 与 judge 结果对照，进入校准集 |

每次运行必须记录完整配置快照，不能只存指标。

#### 9.4.4 LLM Judge

- Rubric 固定为 JSON，1–5 分，要求先给理由再给分。
- 双 judge + 第三人仲裁，降低单模型偏差。
- 与 100 条人工标注对比，Cohen's kappa ≥ 0.6 才可用于门禁。
- 记录 judge 模型、prompt 版本、温度；judge 升级要重新校准。
- 成本控制：缓存、抽样、短模型初筛 + 强模型复核。

#### 9.4.5 发布门禁

候选版本对比当前基线，任一硬指标不达标即失败：

| 指标 | 拦截条件 |
|---|---|
| 工具选择准确率 | < 90% 或比基线跌 > 3% |
| 忠实度 | < 0.85 或比基线跌 > 3% |
| PII 泄漏 | > 0 |
| 注入成功率 | > 5% |
| 平均迭代 | > 2.5 |
| 单次任务成本 | 比基线涨 > 20% |

门禁接入 CI 与发布脚本；失败自动保留现场（trace、输出、配置），支持一键回滚。

当前 `.github/workflows/eval-gate.yml` 会在 push 和 pull request 上跑离线测试与 `--dry-run`。2026-11-04 最新一次 `offline-gate` 在没有 API Key 时停在习题页整卷控件，失败原因已修，本机同一组命令已通过。这次推送后的远程结果还没看到。忠实度只在调用方传入分数时进入门禁；没校准的模型裁判仍然不拦截发布。

#### 9.4.6 可复现

- 评测固定 `temperature=0`、固定 seed、固定数据集版本。
- 保存原始输出与 judge 理由，不只保存分数。
- 版本轴与 9.3.6 一致；缺一项就视为不可复现。

#### 9.4.7 线上监控

- 输入漂移：问题长度、学科分布、图片占比、语言分布。
- 质量漂移：检索命中率、拒答率、重试率、用户点踩率。
- 失败分类：工具选错、检索为空、答案不忠实、格式错误、超时、成本超限。
- 告警：阈值 + 同比；走飞书/邮件；附 trace 链接与最近变更。
- 事故回放：按 `trace_id` 重放，定位是模型、prompt、索引还是数据问题。

#### 9.4.8 学习效果评估

- 前测/后测：同难度、不同题，避免记忆效应。
- 错题复现率：同一知识点 14 天内再次做错的比率。
- 留存：7 日/30 日回访与有效学习时长。
- 归因：把提升与“使用次数、批改次数、复习完成率”做相关性分析，不宣称因果。

### 9.5 三条建设路线

| 路线 | 范围 | 工期 | 适合 | 退出条件 |
|---|---|---|---|---|
| C 评测优先 | trace + 离线 runner + 报告 | 约 1 周 | 先拿到可量化基线 | 100 条评测可重复跑 |
| A 内嵌增强 | SQLite + DuckDB + 两个平台页 | 1–2 周 | 单机产品、一个团队 | 数据可查、门禁可拦 |
| B 独立服务 | FastAPI + Postgres + pgvector + MinIO + worker | 3–4 周 | 多客户端、多人协作 | API 承载 UI、备份可恢复 |

建议顺序：**C → A → B**。成熟项目的目标是 B，但不要跳过 C；没有基线就拆服务，只会在更贵的环境里继续盲改。

### 9.6 分期路线（8 周）

| 周 | 平台线 | 功能线 | 退出条件 | 状态 |
|---|---|---|---|---|
| 1 | C：trace + runner + 50 条 | Phase 0 工具注册表 | 100% run 可追溯；基线报告 | 🟡 默认评测 100 条。每次运行有 `trace_id`，并按模型用量记 token 和费用。live 只在调用了检索时按当次正文打忠实度。费用不含缓存和 Batch |
| 2 | A：表结构 + 数据集版本 + 门禁 | Phase 1 代码助教 | 故意降级被门禁拦截 | 🟡 代码助教最小链路已进代码，子进程有 64MB 内存上限；工具选择和传入的忠实度可被 `check_release_gate` 拦截。缺数据集表和容器沙箱。CI 工作流已提交。offline-gate 失败原因已修，本机已通过；这次推送后的远程结果还没看到 |
| 3–4 | B：FastAPI + Postgres + MinIO | Phase 2 拍照批改 | UI 走 API；备份可恢复 | 🟡 失败归因、错题页、问答、讲解、对比、出题、单题对照、整卷判分、学习计划和日程已走 API。知识库页仍直连。Postgres / MinIO / 生产演练未做 |
| 5 | 在线抽样 + judge 校准 | Phase 2 收尾 | kappa ≥ 0.6 | ⬜ |
| 6 | RBAC + 保留期 + 成本核算 | Phase 3 主动推送 | 安全清单通过 | 🟡 复习脚本和每日调度已进代码；RBAC、保留期和安全清单未做 |
| 7–8 | 压测 + 监控 + 演练 | 方向扩展 | 100 并发；RTO 演练通过 | ⬜ |

两条线共用 Phase 0 的 trace 与 schema，不要各做一套。

### 9.7 生产就绪清单

**可靠性**

- [ ] 所有外部调用有超时、重试（指数退避 + 抖动）、熔断。工具执行器、模型、识图、飞书和 SMTP 已有超时、次数重试、指数退避、抖动和 30 秒熔断。熔断按通道分开。还没有覆盖全部第三方调用
- [ ] LLM 失败可降级（备用模型 / 缓存 / 明确报错），不拖垮页面
- [ ] 写接口幂等；关键任务可重放
- [ ] 健康检查与就绪探针
- [ ] 容量与并发压测有报告

**安全与合规**

- [ ] 密钥只走环境变量/密钥管理，不进代码与日志
- [ ] RBAC + 租户隔离 + 审计日志
- [ ] 输入校验、输出转义、Prompt 注入防护
- [ ] URL 抓取做 SSRF 防护；上传做类型与大小校验
- [ ] 代码执行在沙箱内，限时、限内存、禁网络
- [ ] PII 脱敏、保留期、导出与删除可用

**数据**

- [ ] 版本化迁移；回滚脚本
- [ ] 每日备份 + 恢复演练
- [ ] 索引重建流程：影子索引 → 对比 → 切流 → 回滚
- [ ] 删除请求 24 小时内可完成

**可观测**

- [ ] 结构化日志带 `trace_id`
- [ ] 核心指标看板：延迟、错误率、成本、质量
- [ ] 告警有值班人与 Runbook
- [ ] 事故可按 trace 回放

**成本**

- [ ] 每次运行可核算 token 与费用
- [ ] 用户/租户预算与限额
- [ ] 缓存与模型路由（简单任务走小模型）
- [ ] 80% 预算告警

**发布**

- [ ] Prompt 版本化；Feature Flag
- [ ] 灰度 5% → 50% → 100%
- [ ] 一键回滚；回滚后自动跑一次冒烟

### 9.8 选型：能买就别造

| 能力 | 建议 | 说明 |
|---|---|---|
| Trace / 观测 | 先轻量自建，L2 上 Langfuse | Langfuse 自托管需要 Postgres + ClickHouse，运维成本不低 |
| RAG 指标 | Ragas | 省去 faithfulness / context precision 的重复实现 |
| CI 评测 | promptfoo | YAML 配置，适合做门禁；领域指标自己写 |
| 向量库 | 开发 FAISS，生产 pgvector | 少一个组件；规模再大再考虑 Milvus |
| 分析 | DuckDB + Parquet | 评测结果切片分析足够快 |
| 对象存储 | MinIO | 图片、音频、原始文档 |
| LLM 网关 | LiteLLM | 多模型、降级、成本统计时再上 |
| 任务队列 | 先 APScheduler，后 RQ | 不要为了队列而队列 |

### 9.9 反模式

- 中台 = 一堆看板，没有第二个消费者。
- Judge 没校准就拿来当门禁。
- 调参集和测试集混用，指标虚高。
- 只存分数，不存原始输出与版本，出了问题无法复现。
- 原始 PII 入库，删除靠手工。
- 没有成本上限，评测一次跑掉半个月预算。
- 没有回滚方案，发版靠祈祷。
- 过早多租户、K8s、Kafka，主线被基础设施拖死。
- 后台任务塞进 Streamlit 进程。
- 只评答案质量，不评工具轨迹与学习效果。

### 9.10 平台 SLO 与产品指标

**平台 SLO**

| 指标 | 目标 |
|---|---|
| trace 覆盖率 | 100% |
| trace 查询 p95 | < 1s |
| 100 条离线评测 | < 10 分钟 |
| Judge 与人工一致率 | kappa ≥ 0.6 |
| API 可用性 | 99.5%（单区域） |
| 备份 RPO / RTO | ≤ 24h / ≤ 4h，月度演练 |
| PII 删除请求 | < 24h |
| 单次评测成本 | 有上限，超限终止 |

**产品指标**

- 首次有效回答时间（激活）
- 7 日 / 30 日留存
- 学习增益（前测/后测）
- 错题复现率
- 每活跃用户成本 / 每成功任务成本
- 用户点踩率与投诉率

### 9.11 结论

平台的价值不在“多两个页面”，而在四件事：

1. **出问题 1 分钟定位**：任何回答都能追到模型、prompt、索引、文档片段。
2. **改坏了自动拦住**：门禁在发布前拦截，而不是用户投诉后才发现。
3. **数据可删可导出**：PII、保留期、删除请求有流程。
4. **成本有上限**：每次运行可核算，预算有告警。

顺序上先 C 后 A 后 B，功能线穿插推进；成熟产品的标志不是功能多，而是可观测、可回滚、可审计、可计费。

---

## 10. Agent 执行协议（执行前必读）

> 本节约束执行本 Plan 的 Agent。写代码前先完整读第 0–10 节，再按第 0 节核对现状。
> 第 1 节保留的是改造前诊断，只用于对照，不要当成现状。

### 10.1 总体目标

严格按照本 Markdown Plan 完成整个项目，而不是只完成其中一个模块。

### 10.2 执行规则

1. 首先读取并理解完整 Plan。
2. 将所有模块拆分成可验证的子任务。
3. 按照模块依赖关系依次执行。
4. 每完成一个子任务，必须进行必要的代码检查和测试。
5. 测试通过后，在第 0 节进度快照或 10.6 清单中更新对应状态。
6. 完成当前模块后，自动检查下一个未完成模块。
7. 如果仍有未完成任务，不要结束本轮工作，继续执行。
8. 如果遇到错误，先尝试自行排查和修复，再继续执行。
9. 如果遇到无法自行解决的阻塞问题，说明原因并等待用户决策。

### 10.3 完成条件

只有满足以下条件才能宣布项目完成：

- 所有模块均已实现。
- 所有任务均已标记为完成。
- 关键功能通过测试。
- 不存在已知的关键错误。
- 最后进行一次整体项目检查。

### 10.4 重要约束

- 不要把完成一个模块视为完成整个项目。
- 每次准备结束执行之前，必须重新读取 Plan，检查是否还有未完成的任务。
- 只要还有能够继续执行的任务，就继续工作。

### 10.5 本项目补充规则

**工作环境**

- 工作目录：`F:\python_ai\智能体_local`
- Python：`venv\Scripts\python.exe`，不要用系统 Python
- 启动：`venv\Scripts\python.exe -m streamlit run frontend/app.py`

**测试与验收**

- 单元测试：`venv\Scripts\python.exe -m unittest discover -s tests -v`
- 语法检查：`venv\Scripts\python.exe -m compileall -q backend frontend tests`
- 评测入口先读 `--help`，不要凭记忆拼参数；当前入口在 `backend/platform/eval_runner.py`
- 每个模块必须给出可复现的命令与输出；没有测试的功能不算完成

**先盘点，再开发**

- 第 0 节是当前进度，不是规划。已有 `vision.py`、`grading.py`、`code_sandbox.py`、`review_schedule.py`、`trace_store.py`、`eval_runner.py`、`mistake_store.py`、`review_planner.py`。
- 每个模块开始前先读代码与测试，确认哪些已实现、哪些是半成品；**补全优先于重写**。
- 不要因为第 3 节写了“规划”，就重复实现第 0 节已标注 ✅ 的能力。

**仓库与提交**

- 仓库已初始化并推送到 `https://github.com/433110535/study-assistant.git`，分支 `main`，代码已跟踪；`.git/info/exclude` 的临时保护已解除，不需要再处理。
- 每完成一个模块提交并推送一次，提交信息用 `feat(module): ...` 或 `fix(module): ...`。
- 不提交 `.env`、`venv/`、`data/app.db`、`data/uploads/`、`logs/`、`__pycache__/`。
- 不为了“让测试通过”而跳过、删除或弱化测试；测试失败就是失败，先修代码。

**外部依赖与降级**

- DashScope、视觉模型、代码沙箱、飞书 webhook 都可能不可用。
- 外部调用失败时返回明确错误并降级，不编造结果，也不要把异常吞掉。
- 没有 API Key 时给出配置提示，不崩溃、不返回假数据。
- 代码执行必须限时、限目录；容器与内存限制未完成前，不得宣称“安全沙箱”。

**质量与安全**

- 写操作（发消息、改计划、写错题本）默认需要用户确认。
- 原始 PII 不写日志、不进评测集；上传文件要做类型与大小校验。
- 评测必须记录模型、prompt、索引、数据集版本；缺一项视为不可复现。
- 每个模块完成后同步更新 `README.md` 与第 0 节，避免文档超前于代码。

**汇报格式**

每个模块完成后按以下结构汇报，再继续下一个模块：

1. 改动文件清单（新增/修改）
2. 关键设计决策与偏离 Plan 的地方
3. 执行的命令与测试结果
4. 已知风险与未完成项
5. 状态表更新
6. 下一个模块

### 10.6 模块执行清单

> 状态与第 0 节同步；冲突时以最近一次测试结果为准。🟡 不等于 ✅，不要把“代码已进仓”当成“验收完成”。

| ID | 模块 | 依赖 | 验收标准 | 状态 |
|---|---|---|---|---|
| M0 | 现状盘点、仓库基线、测试入口确认 | — | 第 0 节快照存在；仓库可提交；测试命令可跑 | ✅ |
| M1 | 平台 C：trace + 评测基线 | M0 | 100 条评测可重复；任意 run 可追溯；门禁能拦住降级版本 | ✅ 100 条评测基线稳定；TraceRun 追溯成本与 Token；建立黄金校准集与 calibrate_faithfulness_judge 裁判校准套件（准确率 100%） |
| M2 | 工具注册表 + SQLite 持久化 | M1 | 旧接口兼容；删库可自动重建；写操作可审计 | ✅ users/documents/mastery 独立分表，删库自动重建，写操作记录 trace 审计 |
| M3 | 代码执行助教 | M2 | 沙箱超时可控；报错可解释；通过测试；有资源上限 | ✅ Windows Job Object (KILL_ON_JOB_CLOSE) + taskkill 进程树强杀；64MB 内存炸弹拦截；输出截断；Level 1~3 分级提示；test_m3_sandbox_hardening 验证通过 |
| M4 | 拍照识题 + 整卷拆题/批改 | M2 | 拆题结果可校对；`ungraded` 不计分；真实试卷走通 | ✅ 增强模式支持多选、多空、单位换算等效；整卷批改通过 API 自动诊断、入错题库并更新掌握度；test_m4_paper_e2e 全流程通过 |
| M5 | 主动复习推送 | M2 | dry-run 可用；真实推送；可改期；有常驻调度 | ✅ 8:00 常驻调度；outbox 通道状态落盘与只重发失败通道（解决重复轰炸）；支持飞书可选 HMAC-SHA256 签名与回调校验；test_m5_dual_channel 验证通过 |
| M6 | 数据中台 A | M1、M2 | 数据集版本、发布门禁、失败归因看板 | ✅ validate_and_clean_dataset 自检清洗；eval_runner 支持 max_cost_yuan 预算硬熔断；失败归因看板完整捕获工具缺失/空检索/不忠实/超时/超成本 |
| M7 | 服务化 B | M6 | API 承载 UI；备份恢复演练通过 | 🟡 API 缺口 F1–F8 已完成，主要页面已走 API，备份恢复演练通过；聊天历史、代码助教、识图在 Streamlit 内仍直连，独立 Web UI 尚未开始；M7 保持 🟡 直到页面接入并通过 E2E |

> 第 3.4–3.6 节（口语陪练 / 联网调研 / 苏格拉底双 Agent）是 P2 可选项，不计入本轮完成条件；确需实现时另立 M8–M10，并在开始前确认优先级与外部 API。
> Web UI 前端任务见 13.7（U1–U6），同样不计入 M0–M7 的完成条件。

### 10.7 结束前的自检

准备结束本轮工作前，逐条回答：

1. 10.6 里还有没有 ⬜ 或 🟡 的模块可以继续推进？
2. 最近一次测试是否覆盖了本轮改动？有没有跳过或弱化的测试？
3. 文档、README、第 0 节状态是否与代码一致？
4. 是否还有已知关键错误没有记录？
5. 如果现在停下，下一位执行者能否只读本 Plan 就接着做？

只要还有能继续执行的任务，就不要结束。

---

## 11. 前端独立化与 API 缺口（2026-11-05）

> 本节是 M7 的未完成子项。现有 Streamlit 前端可运行，但要换独立 Web UI，必须把“进程内 import”改成“HTTP 契约”。
> `web_UI` 目录尚未在仓库、`F:\python_ai`、`F:\UI` 中找到；路径确认后再决定前端框架。下面的接口缺口与框架选型无关。

### 11.1 已经走 API 的能力

| 能力 | 接口 |
|---|---|
| 问答（SSE） | `POST /v1/chat/stream` |
| 讲解 / 对比 / 出题 / 计划 / 日程 | `POST /v1/explain`、`/v1/compare`、`/v1/questions`、`/v1/plans`、`/v1/schedules` |
| 整卷 / 单题判分 | `POST /v1/papers/grade`、`/v1/items/grade` |
| 错题与复习 | `GET/POST /v1/mistakes*`、`/v1/review/*` |
| 知识库 | `GET/POST /v1/documents`、`/v1/documents/search`、`/v1/documents/ask` |
| 掌握度 | `GET /v1/mastery` |
| 评测 / 备份 | `GET /v1/eval/latest`、`POST /v1/database/backup`、`POST /v1/database/restore` |
| trace / 工具 / 数据集 | `GET /v1/traces/{id}`、`/v1/tools`、`/v1/datasets` |

### 11.2 仍然直连后端的部分

> F1–F8 已于 2026-11-05 完成，接口状态见 11.3。本节保留下来，作为“页面迁移”的对照。

| 页面/能力 | 直连位置 | 问题 | 接口现状 |
|---|---|---|---|
| 聊天历史 | `frontend/app.py` 直接 import `chat_store`（`ensure_session` / `load_messages` / `list_sessions` / `append_message` / `start_session`） | 浏览器访问不到 SQLite | 已提供 `/v1/sessions*`；Streamlit 尚未接入 |
| 代码助教 | 直接 import `code_sandbox`、`code_attempt_store` | 代码执行与历史只在进程内 | 已提供 `/v1/code/*`；Streamlit 尚未接入 |
| 识图修正 | 直接 import `vision.read_image` | 图片上传/OCR 没有 HTTP 入口 | 已提供 `/v1/vision/ocr`；Streamlit 尚未接入 |
| 习题 AI 批改 | `render_quiz` 内直接 `get_llm()` 组 prompt | 浏览器无法调用模型 | 已提供 `/v1/quiz/grade`；Streamlit 尚未接入 |
| 登录 | Streamlit `render_login` + API `X-API-Key` | 没有会话/用户体系 | 已提供 `/v1/auth/*`；Streamlit 仍用页面内登录 |
| 数据看板 | 页面内用 `st.session_state` 统计 | 刷新丢失、无法多端 | 已提供 `/v1/dashboard/summary`；Streamlit 仍用 session_state |

补充：

- `format_paper` 是本地格式化函数，前端可自行渲染，不算阻塞。
- 知识库页的列表、检索、RAG 问答已经走 API；上传接口已补 multipart。

### 11.3 Web UI 必需接口（按优先级）

| ID | 接口 | 用途 | 优先级 | 验收 | 状态 |
|---|---|---|---|---|---|
| F1 | `POST /v1/auth/login`、`POST /v1/auth/logout`、`GET /v1/auth/me` | 登录态；单机可退回 API Key，但接口要留 | P0 | 未登录 401；登录后可读写 | ✅ 已完成（支持 local/password 双模、Cookie 与 Bearer 令牌、空密码拦截、线程安全限流、登出撤销与物理 purge） |
| F2 | `GET /v1/sessions`、`GET /v1/sessions/{id}/messages`、`POST /v1/sessions` | 历史会话与刷新恢复 | P0 | 列表分页；消息顺序正确 | ✅ 已完成（毫秒高精时间戳与 rowid 确定性排序、严格 Cookie 登录态跨用户防越权与 404 隔离） |
| F3 | `POST /v1/vision/ocr` | 上传图片 → 识别文本 → 可编辑 | P0 | 坏图/无 Key 有明确错误；不落临时文件 | ✅ 已完成（Multipart、严禁非图片扩展名伪装 octet-stream 穿透、5MB 上限、异常映射与 finally 临时文件清理） |
| F4 | `POST /v1/code/run`、`POST /v1/code/hint`、`GET /v1/code/attempts` | 代码助教 | P0 | 超时/内存/输出截断；历史可载入 | ✅ 已完成（50KB code/tests 双向长度校验、跨用户历史隔离、分级提示与历史顺序检索） |
| F5 | GET /v1/dashboard/summary | 看板聚合 | P1 | 一次请求返回统计与最近活动 | ✅ 已完成（标量子查询消灭笛卡尔积、COALESCE防空表NULL、INNER JOIN sessions隔离用户运行历史、容错降级不崩溃） |
| F6 | POST /v1/documents/upload | PDF 上传 | P1 | 类型/大小校验；进度与失败重试 | ✅ 已完成（Multipart流式分块写入、%PDF-魔数校验、20MB硬限、扫描件空文本拦截422、asyncio.to_thread异步切片与SQLite documents表双写同步） |
| F7 | POST /v1/quiz/grade | 习题 AI 批改 | P2 | 与现有页面结果一致；可关闭 | ✅ 已完成（收敛 Streamlit 页面提示词至 backend.tools.question_generator.grade_quiz，空题拦截与20000字上限、未配置 Key 时 503 优雅降级、异常映射 502） |
| F8 | CORS + 静态托管 | 前后端分离 | P0 | dev 代理 `/v1`；生产同源 | ✅ 已完成（CORS_ORIGINS 白名单允许凭证、条件挂载 web_UI/dist 至 /app） |

### 11.4 前端独立化验收

> API 侧 F1–F8 已完成；以下条目在页面接入后逐项勾选。

- [ ] 新前端代码中没有任何 `from backend...` / `import backend...`
- [ ] 核心链路只经 HTTP：登录 → 对话（含图）→ 判分 → 错题确认 → 复习改期
- [ ] SSE 首 token < 2s（本机）；中断、重连、错误都有 UI 反馈
- [ ] 401/403/422/500 有统一错误处理，不白屏
- [ ] 上传有类型/大小/进度/失败重试
- [ ] 关掉 Streamlit 后，核心页面仍可用
- [x] 现有 180 个后端测试保持通过；新增接口有对应测试（总计 210 个测试全绿，严格覆盖跨用户隔离、空密防御、二进制扩展名伪装拦截与会话物理 purge）

### 11.5 推进顺序

1. F1 + F2 + F3 + F4（P0，约 2–3 天）：前端不再直连后端。
2. F5 + F6（P1，约 1 天）：看板与上传。
3. F7 + F8（P1/P2，约 1 天）：批改与部署。
4. 然后才搭 `web_UI` 壳；接口已齐，前端方案与任务见第 13 节。

> 每一项的接口契约、测试命令和验收标准见第 12 节。把第 12 节交给执行 Agent 即可。

### 11.6 状态修正

- 第 0 节“服务拆分与中台”：✅ → 🟡。
- 10.6 的 M7：✅ → 🟡。
- M7 回到 ✅ 的条件：F1–F8 已完成；还差页面接入与核心链路 E2E。

---

## 12. Web UI API 缺口实施规格（交给执行 Agent）

> 本节是第 11 节的可执行版本。把本节交给编码 Agent，即可按 F1–F8 补齐接口。
> 目标不是重写前端，而是让独立 Web UI 只靠 HTTP 完成“登录 → 会话 → 对话 → 识图 → 代码助教 → 看板”的核心链路。

### 12.1 角色与工作目录

你是本仓库的 Python / FastAPI 后端工程师。按本节实现接口缺口，不重写已有功能。

- 工作目录：`F:\python_ai\智能体_local`
- Windows，UTF-8；Python 用 `venv\Scripts\python.exe`
- 分支：`main`；每完成一个逻辑组提交一次，不自动 push，除非远程凭据已配置
- 不提交 `.env`、`data/app.db`、`data/uploads/`、`__pycache__/`

### 12.2 开工前必读

1. `说明/PLAN.md` 第 0 节（进度）、第 10 节（执行协议）、第 11 节（缺口）
2. `backend/api/app.py`（`create_app` / `require_key` / SSE）
3. `backend/api/local_client.py`（Streamlit 的调用方式）
4. `backend/platform/chat_store.py`、`code_attempt_store.py`、`mistake_store.py`
5. `backend/tools/code_sandbox.py`、`vision.py`、`question_generator.py`
6. `backend/knowledge/knowledge_base_faiss.py`
7. `tests/test_api.py`、`tests/test_grading.py`（测试风格）
8. `frontend/app.py` 的 `render_qa` / `render_quiz` / `render_code_tutor` / `render_mistakes`

先跑基线，确认 180 个测试通过再动手：

```powershell
venv\Scripts\python.exe -m unittest discover -s tests -v
venv\Scripts\python.exe -m compileall -q backend frontend tests
```

### 12.3 总原则

- 不破坏现有接口与测试；新接口优先复用现有 store / tool。
- API Key、密码不进代码与日志；只更新 `.env.example`。
- 上传与临时文件要校验类型/大小，`finally` 清理。
- 每个 F 项完成后补测试，并更新 11.3 的状态与 10.6 的 M7。
- 提交信息用 `feat(api): ...` / `fix(api): ...`。

### 12.4 F1 登录态（P0）

保留现有 `X-API-Key`，新增可选的会话登录。

- 新增 env：`AUTH_MODE=local|password`，默认 `local`；`APP_USERNAME` / `APP_PASSWORD` 已在 `.env.example`。
- `local` 模式：`GET /v1/auth/me` 返回 `{"user_id":"student","mode":"local"}`，现有接口行为不变。
- `password` 模式：
  - `POST /v1/auth/login` body `{username,password}`：`hmac.compare_digest` 校验 env；成功后生成 `secrets.token_urlsafe`，把 token 的 sha256 存入 `web_sessions(token_hash,user_id,created_at,expires_at,revoked_at)`；返回 `{user_id,expires_at}`，设置 HttpOnly + SameSite=Lax 的 `study_session` Cookie。
  - `POST /v1/auth/logout`：撤销 token、清 Cookie、返回 204。
  - `GET /v1/auth/me`：校验 Cookie 或 API Key；无效 401。
  - 受保护接口同时接受 Cookie 与 `X-API-Key`；不要破坏 `create_app(..., api_key="secret")` 的现有测试。
- 登录失败做简单限流；错误信息不区分“用户不存在/密码错误”。
- 测试：local 模式 me、password 登录/登出/过期/错误密码、API Key 兼容。

### 12.5 F2 会话历史（P0）

- `GET /v1/sessions?user_id=student&limit=50&offset=0` → `{sessions:[{id,title,created_at,updated_at,message_count}],total}`，按更新时间倒序。
- `GET /v1/sessions/{session_id}/messages` → `{session_id,messages:[{role,content,created_at}]}`；不存在 404。
- `POST /v1/sessions` body `{user_id?,title?}` → `{session_id}`。
- 复用 `chat_store.list_sessions / load_messages / start_session`，按 `user_id` 过滤，不泄露他人会话。
- 测试：空列表、分页、404、用户隔离。

### 12.6 F3 图片 OCR（P0）

- `POST /v1/vision/ocr` multipart：`file`（必填）、`focus`（可选）。
- 限制 jpeg/png/webp、≤5MB；保存临时文件，调用 `backend.tools.vision.read_image(path, focus)`，`finally` 删除。
- 返回 `{text,model,elapsed_ms}`。
- `read_image` 目前用字符串表示错误（图片不存在 / 未配置 Key / 视觉模型失败等）。把这些前缀映射为 4xx/5xx + `{detail}`，不要 200 返回错误字符串。
- 测试 mock `read_image`，覆盖成功、坏文件、超限、无 Key。

### 12.7 F4 代码助教（P0）

- `POST /v1/code/run` body `{code,tests?,timeout_s?,thread_id?,user_id?}`：
  - 复用 `code_sandbox.run_student_code`；代码上限 50KB，超时交给现有 `_clamp_timeout`。
  - 结果写入 `code_attempt_store.append_attempt`；缺省 thread_id 时新建。
  - 返回 `{status,stdout,stderr,exit_code,duration_ms,timed_out,thread_id}`。
- `POST /v1/code/hint` body `{code?,observation?,level}`：复用 `hint_for_level`，返回 `{hint}`。
- `GET /v1/code/attempts?thread_id=&user_id=&limit=`：复用 `list_attempts`。
- 测试：正常运行、断言失败、超时、输出截断、历史顺序。

### 12.8 F5 看板聚合（P1）

- `GET /v1/dashboard/summary?user_id=student`：
  - 会话数、消息数、文档数、错题（待确认/已确认/今日到期）、掌握度均值与分布、最近 5 次 run、最近一次评测摘要。
  - 复用现有 store，避免逐条查询；一次请求返回。
- 测试：空库、有数据、用户隔离。

### 12.9 F6 文档上传（P1）

- 新增 `POST /v1/documents/upload`（multipart：`file`、`subject?`），保留现有 `POST /v1/documents` 的 JSON 行为。
- 校验 PDF 类型与 ≤20MB；保存临时文件；调用 `FAISSKnowledgeBase.add_pdf`；`finally` 删除；返回 `{doc_id,pages,chunks,title}`。
- 若现有 `/v1/documents` 已支持 multipart，只补测试与文档，不重复实现。
- 测试可用 `tests/fixtures/sample.pdf`；FAISS 写入慢时 mock `add_pdf`。

### 12.10 F7 习题 AI 批改（P2）

- 把 `frontend/app.py` 的 `render_quiz` 中 `get_llm()` 组 prompt 的逻辑移到 `backend/tools/question_generator.py`，新增 `grade_quiz(questions, answers, llm=None)`。
- 新增 `POST /v1/quiz/grade` body `{questions,answers}`，返回 `{feedback}`；无 API Key 时 503。
- Streamlit 可继续用旧路径，但新接口要有测试（mock LLM）。
- 离线判分仍以 `/v1/items/grade` 为准，不要混用。

### 12.11 F8 CORS 与静态托管（P0）

- 在 `create_app` 加 `CORSMiddleware`；`CORS_ORIGINS` 默认 `http://localhost:5173,http://127.0.0.1:5173`，`allow_credentials=True`，不要用 `*`。
- 如果 `web_UI/dist` 存在，挂到 `/app`（不要挂 `/`，避免遮住 `/v1`），并为 SPA 做 fallback；不存在时跳过，不报错。
- `.env.example` 补 `AUTH_MODE`、`CORS_ORIGINS`、`MAX_UPLOAD_MB`。
- 测试：OPTIONS 预检、`/health` 不受影响、静态目录缺失时正常启动。

### 12.12 验收

- 新增接口都有测试；`unittest discover` 全绿（180+ 新增）。
- 现有 Streamlit 行为不变；`local_client` 仍可用。
- 前端可以只靠 HTTP 完成：登录态 → 会话列表 → 对话 → 图片 OCR → 代码运行/提示 → 看板。
- 11.3 的 F1–F8 状态更新；M7 仍为 🟡，直到页面接入且 E2E 通过。
- README 的“规划中”同步更新。

### 12.13 汇报与阻塞

每完成一个 F 项，按以下结构汇报：

1. 改动文件
2. 新增/修改接口与请求/响应示例
3. 测试命令与结果
4. 风险与未完成项
5. PLAN 状态更新
6. 下一个 F 项

阻塞处理：

- `APP_PASSWORD` 未配置：默认 local 模式，不要阻塞。
- `web_UI` 目录不存在：只实现条件挂载，不创建前端代码。
- 多租户 / RBAC / Postgres：超出本节范围，记录到 PLAN 等待决策。

---

## 13. Web UI 前端方案（ClickHouse · React + Vite）

> 2026-11-05 追加。设计源：`F:\python_ai\UI\design.md`（ClickHouse Design System）。
> 已确认：ClickHouse 风格；代码放 `F:\python_ai\智能体_local\web_UI`；React + Vite；第一版 6 页；单机自用。
> 现有 Streamlit 的 Plane 风格暂不混用；新前端完成后替换。`F:\python_ai\UI` 只作设计参考。

### 13.1 设计语言的产品化改造

ClickHouse 是营销站语言：纯黑、霓虹、96px 巨字。学习工作台需要收敛，避免“很酷但难用”。

**颜色 Token**

| Token | 值 | 用法 |
|---|---|---|
| `--bg` | `#000000` | 全站页面背景，不用深灰替代 |
| `--surface` | `#141414` | 按钮、输入框、悬浮层 |
| `--surface-2` | `#0A0A0A` | 卡片内嵌区域、代码块 |
| `--border` | `rgba(65,65,65,.8)` | 卡片、表格、分割线 |
| `--text` | `#FFFFFF` | 标题与正文主色 |
| `--muted` | `#A0A0A0` | 次级正文、说明 |
| `--dim` | `#585858` | 元信息、占位符，仅辅助 |
| `--accent` | `#FAFF69` | 主 CTA、选中态、焦点环、关键数字、链接 hover |
| `--accent-active` | `#F4F692` | 按下态文字 |
| `--green` | `#166534` | 次要转化按钮 |
| `--danger` | `#FF6B6B` | 错误/危险操作，功能性例外 |
| `--success` | `#4ADE80` | 成功状态，功能性例外 |

**字体**

- 拉丁与数字：Inter，正文 400/500，标题 700/800，Hero 900
- 中文：回落 PingFang SC / 微软雅黑，中文 700 已是上限
- 代码：Inconsolata
- Basier 是商业字体，不引入；功能标题统一 Inter

**应用内字号**（不要全站 96px）

| 角色 | 字号/行高 | 字重 |
|---|---|---|
| 登录/空状态 Hero | 56–72 / 1.0 | 800–900 |
| 页面 H1 | 36–40 / 1.1 | 800 |
| 区块 H2 | 24–28 / 1.2 | 700 |
| 卡片标题 | 18–20 / 1.3 | 700 |
| 正文 | 15–16 / 1.6 | 400 |
| 辅助 | 13–14 / 1.5 | 400 |
| 大写标签 | 12 / 16，字距 1.4px | 600 |
| 指标数字 | 48–64 / 1.0 | 800 |
| 代码 | 14 / 22 | 600 |

**硬规则**

- 霓虹只做强调，不做大块背景；唯一例外是 CTA 按钮
- 圆角只用 4 / 8 / 999；超过 8 的卡片改回 8
- 深度靠 1px 描边和 inset，不用柔和阴影
- 不用渐变、玻璃拟态、彩色阴影
- 全站深色；浅色模式放 v2

### 13.2 信息架构（第一版 6 页）

| 路由 | 页面 | 核心内容 |
|---|---|---|
| `/` | 概览 | 指标条、掌握度、今日到期、最近活动 |
| `/chat` | 对话 | 会话列表、消息流、工具轨迹抽屉、图片 OCR |
| `/practice` | 练习 | 出题 / 整卷判分 / 单题判分 |
| `/review` | 错题与复习 | 到期卡片、错题表、改期 |
| `/knowledge` | 知识库 | 文档表、上传、检索、RAG 问答 |
| `/code` | 代码助教 | 编辑器、运行输出、分级提示、历史 |

Phase 2 再加：`/plan`（计划）、`/ops`（评测/备份）、`/login`（仅 password 模式）。

### 13.3 页面要点

**应用外壳**

- 侧栏 248px：纯黑、右侧 1px 描边；导航项 40px，选中 `#141414` + 左侧 2px 霓虹条
- 顶栏 56px：大写面包屑、右侧状态胶囊、头像
- 内容最大宽度 1600px，左右 32px；桌面 12 列，间距 24px
- 1024px 以下侧栏收起；640px 以下单列，指标卡 2 列

**概览**

- 顶部 4 个指标：连续学习、已掌握概念、今日到期、近 7 日正确率
- 数字 48–64px、800 字重，关键值用霓虹
- 两栏：掌握度条形/热力图 + 最近 5 次运行表
- 右上角霓虹主按钮：开始今日复习

**对话**

- 三栏：会话列表 260px / 消息流自适应 / 工具轨迹 320px（可收起）
- 用户气泡 `#141414` + 描边；助手透明 + 左侧 2px 霓虹
- 输入区支持图片：先压缩再上传 OCR，识别文本可编辑
- SSE 事件映射：thinking / tool_call / tool_result / answer_chunk / final_answer / error

**练习**

- Tab：生成练习 / 整卷判分 / 单题对照
- 整卷：上传图片 → OCR → 拆题预览 → 逐题状态表（正确/错误/未判分/不支持）
- 结果表用等宽数字；错误行 hover `#141414`；底部“确认入错题本”

**错题与复习**

- 顶部到期卡片：记住了 / 没记住 / 推到晚上
- 错题表：学科、考点、错因、下次复习、状态
- 改期用 Dialog，不跳页

**知识库**

- 文档表：标题、学科、页数、切片数、状态
- 上传区用虚线描边 dropzone，成功后行内进度
- 检索结果展示相似度与来源片段

**代码助教**

- 左右分栏：Monaco/CodeMirror 编辑器 + 输出终端
- 顶部：运行、测试、提示级别 1–3
- 底部：历史运行列表，可载入某一版

### 13.4 技术栈与工程结构

- React 18 + Vite + TypeScript
- Tailwind + CSS variables；Radix UI primitives 自建组件
- TanStack Query（服务端状态）+ Zustand（UI 状态）
- React Router
- Monaco 或 CodeMirror 6，懒加载
- react-markdown + remark-gfm + remark-math + rehype-katex + Shiki
- Recharts，自定义深色主题
- Zod、Vitest + RTL + Playwright + axe

```text
web_UI/
├── src/
│   ├── app/            # 路由、AppShell、登录守卫
│   ├── components/     # Button/Input/Card/Table/Badge/Dialog/Toast/StatCard
│   ├── features/       # overview/chat/practice/review/knowledge/code
│   ├── lib/            # api client、SSE、query keys、auth
│   └── styles/         # tokens.css、globals.css
├── tests/              # 组件与 E2E
├── vite.config.ts      # dev 代理 /v1 → 127.0.0.1:8000
└── package.json
```

### 13.5 API 对接

- 用 `openapi-typescript` 从 `/openapi.json` 生成类型
- 所有请求 `credentials: 'include'`；401 统一处理
- SSE 用 `fetch` + `ReadableStream`（不是 EventSource），支持中断与重连
- 图片/PDF 走 multipart；图片前端压缩到长边 1600、2MB 内
- dev 用 Vite proxy `/v1` → `http://127.0.0.1:8000`
- 生产 `npm run build` 输出 `web_UI/dist`，由 FastAPI 挂 `/app`
- 实施时把 `Path("web_UI/dist")` 改成基于项目根目录的绝对路径，避免从其他目录启动时静默跳过

### 13.6 组件清单

| 组件 | 要求 |
|---|---|
| Button | Neon primary / Dark solid / Ghost / Danger，4px 圆角，无渐变 |
| Input / Select | `#141414` 底、1px 描边、focus 霓虹环 |
| Card | 透明或 `#0A0A0A`、1px charcoal 描边、8px 圆角、无软阴影 |
| StatCard | 数字 48–64px、800 字重、大写标签、关键值霓虹 |
| DataTable | 大写表头、等宽数字、行 hover `#141414`、横向滚动 |
| Tabs | 底线式，选中霓虹 |
| Badge | 胶囊，描边，状态色仅用于状态 |
| Dialog / Toast | 纯黑面板、charcoal 描边、inset 深度 |
| Skeleton / EmptyState | 描边骨架；空状态用大写字标 + 一句说明 |
| ChatBubble | 用户 `#141414`，助手透明 + 左侧霓虹线 |
| Markdown / CodeBlock | KaTeX + Shiki；Inconsolata；代码块可滚动 |
| UploadDropzone | 虚线描边、拖拽、类型/大小提示 |
| TraceDrawer | 工具名、参数、结果、耗时，按事件流追加 |
| ChartCard | 无渐变、网格 `#414141` 40%、主线霓虹 |

### 13.7 实施阶段（U1–U6）

| ID | 周 | 交付 | 验收 |
|---|---|---|---|
| U1 | 1 | 脚手架、设计 token、AppShell、概览 | 5173 可访问；概览读真实数据；token 与组件基础可用 |
| U2 | 2 | 对话：会话、SSE、工具轨迹、图片 OCR | 含图对话端到端跑通 |
| U3 | 3 | 练习：出题、整卷/单题判分、结果表 | 判分 → 状态表 → 确认入错题本 |
| U4 | 4 | 错题与复习 + 知识库 | 到期/改期闭环；上传/检索/RAG 可用 |
| U5 | 5 | 代码助教 + 响应式 + 可访问性 | 运行/提示/历史；1440/1024/390 无横向滚动 |
| U6 | 6 | E2E、性能、静态构建、切换 | `npm run build` 成功；`/app` 可访问；关闭 Streamlit 核心链路可用 |

### 13.8 验收标准

- [ ] 6 个页面全部只走 HTTP，前端零 `backend` import
- [ ] 单机 local 模式直接进入，不强制登录
- [ ] 对话 SSE 首 token < 2s（本机）；中断/重连/错误有 UI 反馈
- [ ] 图片上传 → OCR → 可编辑 → 发送，链路完整
- [ ] 判分 → 错题确认 → 到期复习 → 改期，链路完整
- [ ] 设计自检：纯黑背景、霓虹只做强调、4/8px 圆角、1px 描边、无渐变
- [ ] 1440 / 1024 / 390 三个宽度无横向滚动
- [ ] 键盘可操作，焦点环可见，错误不只靠颜色表达
- [ ] 主要页面 Lighthouse 性能/可访问性 ≥ 90
- [ ] 构建产物不含 API Key、密码、`.env`

### 13.9 单机自用约束

- `AUTH_MODE=local`，`user_id=student`，第一版不做登录页
- FastAPI 与前端都只绑 `127.0.0.1`，不暴露公网
- 数据只落本地 SQLite 与 `data/uploads/`
- 不做租户、配额、角色、Postgres/MinIO
- 以后要切 password 模式，再加 `/login` 与 Cookie 流程；F1 已支持

### 13.10 风险与 Phase 2

**风险**

1. ClickHouse 偏营销，应用内要克制 96px 与霓虹，否则信息密度下降
2. 全站纯黑长时间学习可能疲劳，浅色模式放 v2
3. Basier 有授权风险，统一用 Inter
4. Streamlit 的 Plane 与 Web UI 的 ClickHouse 并存，迁移期不要互相改样式
5. `web_UI/dist` 的静态挂载路径要改成项目根目录拼接

**Phase 2**

- `/plan` 计划页、`/ops` 评测与备份页
- 浅色模式
- 多用户 / RBAC / Postgres / MinIO
- 容器化代码沙箱与部署

### 13.11 状态

| ID | 任务 | 状态 |
|---|---|---|
| U1 | 脚手架 + token + AppShell + 概览 | ✅ |
| U2 | 对话 + SSE + OCR + 轨迹 | ⬜ |
| U3 | 练习 + 判分 | ⬜ |
| U4 | 错题复习 + 知识库 | ⬜ |
| U5 | 代码助教 + 响应式 + 可访问性 | ⬜ |
| U6 | E2E + 构建 + 切换 | ⬜ |

> 交给 Antigravity 的执行提示词见第 14 节。

---

## 14. Antigravity 执行提示词（Web UI）

> 2026-11-05 追加。配合第 13 节使用。
> 14.1 是完整版，直接整段交给 Antigravity；14.2 是简洁版，任务窗口有限时按阶段使用。

### 14.1 完整版

```text
# 任务：为学习助手实现独立 Web UI（React + Vite + ClickHouse 风格）

## 角色
你是资深前端工程师 + 设计系统实现者。用 Antigravity 的 Manager 做计划、Editor 写代码、Browser 做验收。

## 工作目录
- 仓库：F:\python_ai\智能体_local
- 新前端：F:\python_ai\智能体_local\web_UI（不存在就创建）
- 后端：backend/api，运行在 http://127.0.0.1:8000
- 旧前端：Streamlit，8501；不要修改，也不要复用它的样式

## 开工前必读
1. 说明/PLAN.md 第 13 节（本任务规格）、第 0 节（进度）、第 11 节（API 缺口）
2. F:\python_ai\UI\design.md（ClickHouse 设计系统，唯一设计源）
3. backend/api/app.py（F1–F8 接口）
4. backend/tools/grading.py、code_sandbox.py、backend/knowledge/knowledge_base_faiss.py
5. frontend/app.py（只参考交互，不参考视觉）

注意：F:\UI\design.md 是旧的 Plane 风格，不要用；F:\python_ai\UI 才是 ClickHouse。

## 已确认的决策
- 风格：ClickHouse；纯黑背景、霓虹黄绿、Inter + Inconsolata、4/8px 圆角、1px 炭灰描边
- 技术栈：React 18 + Vite + TypeScript + Tailwind + Radix UI + TanStack Query + Zustand + React Router
- 第一版 6 页：概览、对话、练习、错题与复习、知识库、代码助教
- 单机自用：AUTH_MODE=local，不做登录页，只绑 127.0.0.1
- 所有数据走 HTTP，前端零 backend import

## 设计 Token（写进 src/styles/tokens.css）
--bg: #000000
--surface: #141414
--surface-2: #0A0A0A
--border: rgba(65,65,65,.8)
--text: #FFFFFF
--muted: #A0A0A0
--dim: #585858
--accent: #FAFF69
--accent-active: #F4F692
--green: #166534
--danger: #FF6B6B
--success: #4ADE80

字体：
- Inter：正文 400/500，标题 700/800，Hero 900
- 中文回落 PingFang SC / 微软雅黑，中文 700 是上限
- Inconsolata：代码
- 不引入 Basier（商业字体）

字号：
- 登录/空状态 Hero 56–72 / 1.0 / 800–900
- 页面 H1 36–40 / 1.1 / 800
- 区块 H2 24–28 / 1.2 / 700
- 卡片标题 18–20 / 1.3 / 700
- 正文 15–16 / 1.6 / 400
- 辅助 13–14 / 1.5 / 400
- 大写标签 12 / 16 / 600，字距 1.4px
- 指标数字 48–64 / 1.0 / 800

硬规则：
- 霓虹只做 CTA、选中态、焦点环、关键数字、链接 hover，不做大块背景
- 圆角只用 4 / 8 / 999
- 深度靠 1px 描边和 inset，不用柔和阴影
- 不用渐变、玻璃拟态、彩色阴影
- 全站纯黑，浅色模式不做

## 信息架构（第一版 6 页）
- `/` 概览：4 个指标（连续学习、已掌握概念、今日到期、近 7 日正确率）、掌握度图、最近 5 次运行
- `/chat` 对话：会话列表 260px、消息流、工具轨迹抽屉 320px、图片上传/OCR
- `/practice` 练习：Tab（生成练习 / 整卷判分 / 单题对照）、逐题状态表、确认入错题本
- `/review` 错题与复习：到期卡片（记住了/没记住/推到晚上）、错题表、改期 Dialog
- `/knowledge` 知识库：文档表、上传 dropzone、检索、RAG 问答
- `/code` 代码助教：编辑器 + 输出终端、运行/测试、提示级别 1–3、历史

应用外壳：
- 侧栏 248px，纯黑，右侧 1px 描边；导航项 40px，选中 #141414 + 左侧 2px 霓虹条
- 顶栏 56px，大写面包屑、右侧状态、头像
- 内容最大宽度 1600px，左右 32px；桌面 12 列
- 1024px 以下侧栏收起；640px 以下单列、指标卡 2 列

## API 映射
- 概览：GET /v1/dashboard/summary、GET /v1/eval/latest
- 对话：GET/POST /v1/sessions*、POST /v1/chat/stream（SSE）、POST /v1/vision/ocr
- 练习：POST /v1/questions、POST /v1/papers/grade、POST /v1/items/grade、POST /v1/quiz/grade
- 错题：GET/POST /v1/mistakes*、GET /v1/review/due、POST /v1/mistakes/{id}/review、POST /v1/mistakes/{id}/reschedule、GET /v1/mastery
- 知识库：GET/POST /v1/documents、POST /v1/documents/upload、POST /v1/documents/search、POST /v1/documents/ask
- 代码：POST /v1/code/run、POST /v1/code/hint、GET /v1/code/attempts

## 工程要求
1. 用 Vite 创建 `web_UI`，TypeScript + React。
2. Tailwind + CSS variables；Radix UI primitives 自建组件，不用 shadcn 默认浅色主题。
3. Vite dev proxy：`/v1` → `http://127.0.0.1:8000`；前端 dev 端口 5173。
4. 用 `openapi-typescript` 从 `/openapi.json` 生成类型；所有请求 `credentials: 'include'`。
5. SSE 用 `fetch` + `ReadableStream`（不是 EventSource），支持中断与重连；事件：thinking / tool_call / tool_result / answer_chunk / final_answer / error。
6. 图片上传前压缩到长边 1600、2MB 内；PDF 走 multipart，≤20MB。
7. 每个页面都要有 loading、空状态、错误态；401 统一处理。
8. Monaco 或 CodeMirror 懒加载；KaTeX/Shiki 懒加载；长列表虚拟化。
9. `npm run build` 输出 `web_UI/dist`；不改后端，除非发现接口缺失，先在汇报里说明。
10. 不提交 `.env`、密钥、node_modules；更新 `web_UI/README.md` 的启动说明。

## 实施顺序（每个阶段都要浏览器验收）
U1 脚手架 + tokens + AppShell + 概览
  - 5173 可访问；概览读真实数据；设计 token 生效
U2 对话：会话列表、SSE、工具轨迹、图片 OCR
  - 一条含图对话端到端跑通
U3 练习：出题、整卷/单题判分、结果表
  - 判分 → 状态表 → 确认入错题本
U4 错题与复习 + 知识库
  - 到期/改期闭环；上传/检索/RAG 可用
U5 代码助教 + 响应式 + 可访问性
  - 运行/提示/历史；1440/1024/390 无横向滚动
U6 E2E + 性能 + 静态构建 + 切换
  - `npm run build` 成功；`/app` 可访问；关闭 Streamlit 核心链路可用

每完成一个阶段：
- 跑 `npm run build`
- 在 Browser 里按 1440、1024、390 三个宽度截图
- 更新 `说明/PLAN.md` 13.11 的 U 状态
- 汇报：改动文件、截图、构建结果、问题、下一阶段

## 验收
- [ ] 6 页全部只走 HTTP，零 backend import
- [ ] 单机 local 模式直接进入，不强制登录
- [ ] SSE 首 token < 2s（本机），中断/重连/错误有 UI 反馈
- [ ] 图片上传 → OCR → 可编辑 → 发送完整
- [ ] 判分 → 错题确认 → 到期复习 → 改期完整
- [ ] 纯黑背景、霓虹只做强调、4/8px 圆角、1px 描边、无渐变
- [ ] 1440/1024/390 无横向滚动
- [ ] 键盘可操作，焦点环可见，错误不只靠颜色
- [ ] 构建产物不含 API Key、密码、.env

## 启动命令
后端：
  venv\Scripts\python.exe -m backend.api
前端：
  cd web_UI
  npm install
  npm run dev
构建：
  npm run build

## 开始方式
先只做 U1；U1 通过后继续 U2–U6。只有遇到接口缺失、设计冲突或无法自测时才停下来问我。
```

### 14.2 简洁版

```text
在 F:\python_ai\智能体_local 新建 web_UI，React 18 + Vite + TS + Tailwind + Radix + TanStack Query。
按 说明/PLAN.md 第 13 节和 F:\python_ai\UI\design.md 实现 ClickHouse 风格：纯黑 #000、霓虹 #FAFF69、Inter/Inconsolata、4/8px 圆角、1px 描边。
先做 U1：脚手架、tokens、AppShell、概览（GET /v1/dashboard/summary）。
Vite dev 端口 5173，代理 /v1 → http://127.0.0.1:8000；单机 local 模式不做登录；前端零 backend import。
完成后 npm run build，浏览器按 1440/1024/390 截图，更新 PLAN 13.11，再继续 U2–U6。
不要改 Streamlit 和后端。
```

---

## 15. 底座缺口盘点（2026-11-06）

> 按原计划继续 U2–U6；本节只记录底座缺口，不插队。
> 状态：✅ 已有 · 🟡 部分 · ⬜ 缺失。

### 15.1 数据中台底座

| 能力 | 现状 | 缺口 | 优先级 |
|---|---|---|---|
| 数据集目录/版本 | 🟡 `dataset_catalog.register_file/list_versions`；`/v1/datasets` 只返回列表 | 版本详情、样本、校验结果、changelog、版本对比；无详情/样本 API | P1 |
| Trace 浏览 | 🟡 `trace_store.get_trace/get_run` + `/v1/traces/{id}` | 运行列表、筛选、分页、导出；概览只有最近 5 条 | P1 |
| 指标趋势 | 🟡 dashboard summary + `/v1/eval/latest` | 按天趋势、按工具/模型切片、成本/延迟分布 | P1 |
| 评测历史 | 🟡 `eval_runs` + `save_eval_run` + `/v1/eval/latest` | run 列表、详情、版本对比、门禁历史 | P1 |
| 数据质量 | 🟡 `validate_and_clean_dataset` 有清洗 | PII/重复/缺失/保留期汇总与查询接口；评测里 `pii/injection` 仍是 not_checked | P1 |
| 血缘 | ⬜ documents/chunks 有 `doc_id`，但 retrieval→answer→eval 未全链路落库 | 无法按回答反查 chunk/prompt/index 版本 | P1 |
| 成本 | 🟡 `llm_cost` + `runs.cost_yuan` | 成本汇总、预算看板、按模型/用户切片 | P1 |

### 15.2 评测中台底座

| 能力 | 现状 | 缺口 | 优先级 |
|---|---|---|---|
| 评测集版本 | 🟡 v1–v5 文件 + `dataset_catalog` | 数据集注册与 `eval_run` 的版本对比未完全打通 | P1 |
| Judge 校准 | 🟡 `calibrate_faithfulness_judge` + 黄金集测试 | 校准报告未持久化、无漂移监控、无人工复核队列 | P1 |
| 在线评测 | ⬜ 只有离线 `--dry-run/--live` | 线上抽样、影子流量、用户反馈回流 | P2 |
| 发布门禁 | 🟡 `check_release_gate` + `.github/workflows/eval-gate.yml` | CI 只跑 9 个测试模块；未覆盖 API/前端构建；门禁只看工具选择/忠实度 | P0（CI）/P1（门禁扩展） |
| 失败归因 | 🟡 看板 + `/v1/eval/latest` | 历史趋势、版本对比、Top N、按工具切片 | P1 |
| 评测污染 | ⬜ 无自动检查 | 与文档库/线上样本的 n-gram 重叠、holdout 管理 | P2 |

### 15.3 运行时与工程底座

| 能力 | 现状 | 缺口 | 优先级 |
|---|---|---|---|
| 持久化 | 🟡 SQLite 单机；11 张业务表；`db_backup` | 无 Postgres/迁移框架/连接池；多用户并发有限 | P2 |
| 对象存储 | 🟡 本地 `data/uploads/` | 无 MinIO/S3；无生命周期清理 | P2 |
| 部署 | ⬜ 无 Dockerfile/compose；只有 eval-gate CI | 无环境分层、一键部署、健康检查编排 | P2 |
| 观测 | 🟡 SQLite trace + loguru | 无 Prometheus/结构化指标/告警/OpenTelemetry；无运维看板 | P2 |
| 安全 | 🟡 local/password + CORS + 上传校验 | 无 RBAC/租户/CSRF/密钥管理；默认密码弱；审计无查询界面 | P2 |
| 可靠性 | 🟡 LLM/工具重试+熔断 | 无任务队列/幂等表/死信；PDF 切片与评测同步执行 | P2 |
| 性能 | ⬜ 无压测/容量报告 | 无缓存层；评测并发未定义 | P2 |
| 备份/DR | ✅ `db_backup` + 灾备测试 | 无定时备份/异地副本 | P2 |
| 配置 | 🟡 `.env` + `config.py` | 无 secret manager/环境分层 | P2 |

### 15.4 前端与接口底座

| 能力 | 现状 | 缺口 | 优先级 |
|---|---|---|---|
| Web UI | 🟡 U1 完成（概览、AppShell、token、截图） | U2–U6 未做；5 页占位 | P0 |
| Streamlit 直连 | 🟡 聊天历史、代码、识图仍 import 后端 | 新接口已提供，页面未接入 | P1 |
| E2E/契约测试 | ⬜ 无 Playwright/契约测试 | CI 无前端构建；无视觉回归 | P1 |
| 静态托管 | 🟡 `/app` 条件挂载 `web_UI/dist` | 路径是相对 CWD，换目录启动会静默跳过 | P0 |
| 无障碍/响应式 | 🟡 U1 有基础 | U5 才系统做；无 axe/Lighthouse 门禁 | P1 |

### 15.5 合规与运营底座

| 能力 | 现状 | 缺口 | 优先级 |
|---|---|---|---|
| PII/保留期/删除 | ⬜ 未见自动化 | 上传文件无生命周期；无删除请求流程 | P2 |
| 多用户/RBAC | ⬜ 单机单用户 | 无租户、角色、配额 | P2 |
| 计费/配额 | ⬜ 无 | 无预算/限额/账单 | P2 |
| 审计查询 | 🟡 写操作 trace 审计 | 无查询/导出界面 | P2 |

### 15.6 优先级与排序

**P0（不插队，但尽快补）**

1. 修正 `web_UI/dist` 静态路径为项目根目录拼接（30 分钟）
2. CI 从 9 个测试模块扩到全量 `unittest discover`，加 `npm run build`（半天）
3. U2 对话优先，保持原计划

**P1（U7 数据中台，U3/U4 之后插入）**

1. Trace 列表 + 详情（工具、token、成本、延迟）
2. 评测 run 历史 + 版本对比
3. 指标趋势 + 成本汇总
4. 数据集详情 + 样本 + 校验状态
5. 数据质量/血缘
6. 把 Streamlit 剩余直连改成 API

**P2（U6 之后的生产化）**

- Docker/compose、Postgres/MinIO、观测告警、RBAC、压测、PII/保留期、定时备份

### 15.7 结论

- 当前底座**不阻塞 U2–U6**；原计划继续。
- 数据中台不是没做，而是“后端有一半、前端没入口、指标/血缘/质量接口不足”。
- U7 数据中台放在 U3/U4 之后，预计后端 2–3 天 + 前端 3–4 天。
- 生产化 Phase 2 放 U6 之后，避免拖慢主流程。

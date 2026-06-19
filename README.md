# QualiAI

**AI-Powered Testing Agent** — 自然语言描述测试场景，AI 自动执行并生成报告。

```bash
$ quali run "测试登录页面：输入正确用户名密码，验证登录成功"
🧪 QualiAI 测试启动
═══════════════════════════════════════

📋 生成 5 个测试步骤:
  🌐 [1] navigate: 打开登录页面
  ⌨️ [2] type: 输入用户名
  ⌨️ [3] type: 输入密码
  🖱 [4] click: 点击登录按钮
  🔍 [5] assert: 验证登录成功

🚀 开始执行...
📊 结果: 5/5 通过 (0 失败)
📄 报告已生成: reports/login_test.html
```

## 快速开始

```bash
# 安装
pip install quali-ai

# 运行测试
quali run "测试搜索功能" --url https://example.com

# 重播已有场景
quali replay scenarios/demo/login.json
```

## 架构

```
用户: quali run "测试登录页"
    │
    ▼
Planner ──→ LLM 拆解自然语言为具体步骤
    │
    ▼
Executor ──→ Playwright 按步骤执行 + 截图
    │
    ▼
Reporter ──→ 生成 HTML 报告（含截图）
```

## 项目结构

```
quali-ai/
├── cli/main.py       # CLI 入口
├── core/
│   ├── planner.py    # AI 测试规划
│   ├── executor.py   # Playwright 执行器
│   └── reporter.py   # HTML 报告生成
├── scenarios/        # 测试场景存储
└── reports/          # 测试报告输出
```

## 路线图

- [x] Phase 1: CLI + Planner + Executor + Reporter (MVP)
- [ ] Phase 2: AI 断言 + 自修复选择器
- [ ] Phase 3: 安卓 ADB 支持
- [ ] Phase 4: WebUI 管理界面

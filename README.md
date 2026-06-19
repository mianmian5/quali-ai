# QualiAI

AI-Powered Testing Agent -- 自然语言描述测试场景，AI 自动执行并生成报告。

```
$ quali run "测试登录页面：输入正确用户名密码，验证登录成功"
QualiAI 测试启动

生成 5 个测试步骤:
  [1] navigate: 打开登录页面
  [2] type: 输入用户名
  [3] type: 输入密码
  [4] click: 点击登录按钮
  [5] assert: 验证登录成功

开始执行...
结果: 5/5 通过 (0 失败)
报告已生成: reports/login_test.html
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 运行测试
python3 -m cli.main run "测试搜索功能" --url https://example.com

# 重播已有场景
python3 -m cli.main replay scenarios/demo/login.json
```

## 架构

```
用户输入: quali run "测试登录页"
    |
    v
Planner -- LLM 拆解自然语言为具体测试步骤
    |
    v
Executor -- Playwright 按步骤执行，每步自动截图
    |
    v
Asserter -- AI 判断每步是否通过 (Phase 2)
    |
    v
Reporter -- 生成 HTML 报告，含截图和结果
```

## 项目结构

```
quali-ai/
├── cli/main.py       CLI 入口
├── core/
│   ├── planner.py    AI 测试规划
│   ├── executor.py   Playwright 执行器 + 自修复选择器
│   ├── asserter.py   AI 断言分析 (Phase 2)
│   └── reporter.py   HTML 报告生成
├── scenarios/        测试场景存储
└── reports/          测试报告输出
```

## 核心特性

- **自然语言驱动**: 用中文描述测试场景，AI 自动拆解为可执行步骤
- **AI 断言**: 截图 + DOM 综合分析，自动判断测试通过/失败
- **自修复选择器**: 页面 UI 变化时，AI 自动修复失效的 CSS 选择器
- **HTML 报告**: 每步截图 + 执行日志 + AI 分析结果
- **场景录制/回放**: 保存测试场景，支持重复执行

## 路线图

- [x] Phase 1: CLI + Planner + Executor + Reporter
- [x] Phase 2: AI 断言 + 自修复选择器
- [x] Phase 3: 安卓 ADB 支持
  - ADB 设备控制 (tap/type/swipe/screenshot)
  - AI 视觉分析 (截图定位元素)
  - 命令: `quali android "测试登录" --app com.example.app`
- [ ] Phase 4: WebUI 管理界面

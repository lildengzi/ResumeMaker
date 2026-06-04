# 智能简历生成器（学习项目版）

基于 **Streamlit + LangChain OpenAI + Playwright/Pillow + HTML/Markdown 渲染** 的中文简历生成器学习项目。

这个项目的定位不是商业级 SaaS 产品，而是一个适合学生拆解、阅读、修改和二次练习的示例工程。当前版本已经具备可演示的简历编辑、AI 优化、HTML 预览、Markdown 导出和 PDF 导出能力，同时保留了一些后续扩展接口。

重点学习内容包括：

- Streamlit 表单与 `st.session_state` 状态管理
- 使用 LLM 优化结构化 JSON 简历数据
- API 不可用时的本地兜底逻辑
- HTML / Markdown / PDF 多种输出链路
- 简单的 Agent + 顺序工作流分层组织
- 配置管理、测试编写、项目结构整理

---

## 1. 当前已经实现的功能

### 简历编辑与生成

- 左侧 Sidebar 编辑简历内容
- 支持基础信息、教育经历、技能、项目经历、工作经历、校园经历、自我评价
- 基础信息面向通用求职场景，使用个人网站和作品集字段，不再默认使用 GitHub 字段
- 支持上传个人照片，文件保存到 `data/uploads/`
- 支持输入 JD，并调用 LLM 进行简历优化
- 即使不填写 JD，也可以进行通用简历优化
- 自动保存到本地 `data/resume_data.json`
- 支持撤销上一次 AI 优化结果
- 支持模块新增、删除、排序、显示/隐藏和标题编辑
- 新增模块统一为通用模块，用户通过标题和内容自由定义用途
- AI 优化结果会直接回写到左侧编辑面板，用户继续在 Sidebar 中手动修改

### 预览与导出

- 右侧 A4 风格 HTML 简历预览
- 支持 3 套模板主题切换：
  - `modern_blue`
  - `elegant_gray`
  - `emerald_pro`
- 支持字号、边距、行高、紧凑布局、头像显示等样式调节
- 支持 Markdown 导出
- 支持 PDF 导出

### 学习向结构设计

- 使用 `agents/` 拆分信息收集与简历润色职责
- 使用 `workflow/graph.py` 统一编排执行流程
- 使用 `core/` 承载数据、LLM、Markdown、资源与服务编排
- 使用 `renderers/` 承载 HTML / Markdown / PDF 渲染
- 使用 `ui/` 拆分 Sidebar 和 Preview
- 使用 `tools/` 预留 OCR、网页抓取、旧简历解析等能力入口

---

## 2. 当前没有完整实现的能力

以下能力目前不是完整功能，而是占位、基础实现或后续扩展方向：

- OCR 识别 JD 图片：当前主要是 UI 与工具入口占位，未接入 PaddleOCR / Tesseract
- URL 抓取：已有基础工具接口，但不是强健的生产级网页正文抽取
- 旧简历自动解析导入：Markdown / txt 可做基础读取，PDF 解析和结构化合并仍需增强
- LangGraph 图式工作流：当前 `workflow/graph.py` 是顺序工作流，不是真正的 LangGraph `StateGraph`
- 多版本简历管理、评分 Agent、面试 Agent、FastAPI 后端、Docker 部署：当前不作为本阶段目标

如果你在历史文档中看到这些关键词，请理解为未来扩展方向，不代表当前版本已经完整实现。

---

## 3. 项目结构

```text
app.py                      # Streamlit 应用入口，负责页面编排与状态管理
config.py                   # 配置加载与环境变量合并
config.json                 # 默认配置（LLM、预览、提示词、默认文案、存储路径等）
smart_resume_core.py        # 兼容入口层，转发 core/ 中的公共能力

agents/
  base_agent.py             # Agent 基类
  factory.py                # Agent 工厂
  info_collector.py         # 信息收集 Agent，当前主要做输入整理
  resume_writer.py          # 调用 LLM 生成优化结果的 Agent

workflow/
  graph.py                  # 当前是顺序工作流编排，不是真 LangGraph

core/
  assets.py                 # 头像/资源读取与 Base64 处理
  data.py                   # 默认数据、数据归一化、读写、合并、旧结构兼容
  llm.py                    # LLM 创建与 JSON 提取
  markdown.py               # Markdown 内容生成
  service.py                # 本地兜底与工作流入口封装

renderers/
  html_renderer.py          # HTML 简历预览渲染
  markdown_renderer.py      # Markdown 导出入口
  pdf_renderer.py           # PDF 导出入口：HTML 预览 -> Playwright 截图 -> Pillow 转 PDF

ui/
  sidebar.py                # 左侧编辑区、样式区、JD 区
  preview.py                # 右侧预览区

tools/
  permission.py             # 工作区路径权限控制
  file_tools.py             # 上传文件扫描与基础解析
  web_tool.py               # 基础网页文本抓取接口
  ocr_tool.py               # OCR 占位接口

data/
  resume_data.json          # 本地保存的简历数据
  uploads/                  # 上传文件目录

docs/
  MVP_开发文档.md            # 早期 MVP 方案，历史参考
  开发文档.md                # 早期完整扩展方案，历史参考
  开发文档v2.0.md            # 模块化/定制化方案，历史参考
  项目开发交接文档.md        # 当前版本交接说明

tests/
  test_html_renderer.py
  test_smart_resume_core.py # 学习型最小测试集
```

说明：

- 根目录已经没有 `generate_pdf.py`，PDF 实现在 `renderers/pdf_renderer.py`
- 根目录已经没有 `resume_data.json`，当前数据文件是 `data/resume_data.json`
- 当前仓库没有 `LEARNING_GUIDE.md`，学习入口以 `README.md`、`docs/项目开发交接文档.md` 和实际代码为准
- 当前 PDF 方案不使用 ReportLab 作为核心实现；依赖来自 `requirements.txt` 中的 `playwright` 和 `Pillow`

---

## 4. 推荐阅读顺序

### 路线 A：Streamlit 页面与状态管理

1. `app.py`
2. `ui/sidebar.py`
3. `ui/preview.py`

重点看 `st.session_state` 如何保存页面状态，以及表单编辑如何映射到结构化 JSON 数据。

### 路线 B：LLM 与简历优化

1. `core/service.py`
2. `workflow/graph.py`
3. `agents/resume_writer.py`
4. `core/llm.py`

重点看“当前简历 + JD”如何进入工作流，模型输出如何解析成 JSON，以及失败时如何回退到本地兜底。

### 路线 C：预览与导出

1. `renderers/html_renderer.py`
2. `renderers/markdown_renderer.py`
3. `renderers/pdf_renderer.py`

重点看同一份简历数据如何渲染成 HTML、Markdown 和 PDF。当前 PDF 通过 Playwright 截取 HTML 预览，再用 Pillow 转成 PDF，因此视觉接近预览，但 PDF 本身偏图片化。

### 路线 D：配置、数据与测试

1. `config.json`
2. `config.py`
3. `core/data.py`
4. `tests/`

重点看默认配置如何组织、环境变量如何覆盖配置、旧字段与 `modules` 结构如何兼容。

---

## 5. 安装与运行

### 环境要求

- Python 3.10+
- Windows / macOS / Linux
- 可用的 OpenAI 兼容 API Key

### 安装依赖

```bash
pip install -r requirements.txt
```

首次使用 PDF 导出前，需要安装 Playwright 浏览器：

```bash
python -m playwright install chromium
```

如果要运行测试：

```bash
pip install -r requirements-dev.txt
```

### 配置环境变量

复制示例文件：

```bash
copy .env.example .env
```

填写：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.2
```

说明：

- `OPENAI_API_KEY`：调用 LLM 时必填
- `OPENAI_BASE_URL`：可选，用于兼容第三方 OpenAI 接口
- `LLM_MODEL`：可选
- `LLM_TEMPERATURE`：可选
- 项目启动时会自动加载 `.env`

### 启动应用

```bash
streamlit run app.py
```

---

## 6. 使用流程

1. 启动应用
2. 在左侧填写基础信息、教育经历、技能和项目经历
3. 可选填写岗位描述 JD
4. 点击“智能生成简历”
5. 在右侧查看 A4 风格预览
6. 按需导出 Markdown 或 PDF

---

## 7. 关键设计取舍

### 7.1 为什么有 Agent / Workflow，但当前仍然简单？

这是一个为扩展预留结构的学习项目。当前工作流本质上仍是顺序执行：

1. 信息收集 Agent 整理输入
2. 简历撰写 Agent 调用 LLM 或本地兜底
3. 返回最终简历与工作流日志

`workflow/graph.py` 的命名是为了保留未来升级空间，但当前没有引入真正的 LangGraph。

### 7.2 为什么既有 LLM，又有本地兜底？

API Key 缺失、模型输出格式错误、接口失败都很常见。学习项目需要保证“失败时仍能演示基本流程”，所以保留了本地兜底生成逻辑。

### 7.3 为什么 PDF 不是可搜索文本 PDF？

当前 PDF 导出链路是：

```text
HTML 预览 -> Playwright 截图 PNG -> Pillow 转 PDF
```

优点是视觉更接近右侧预览；缺点是 PDF 偏图片化，不利于复制、搜索，文件体积也可能更大。后续如果更重视文本可选中和可搜索能力，可以改为 Playwright 原生 `page.pdf()` 或其他 HTML-to-PDF 方案。

---

## 8. 测试

运行最小测试集：

```bash
pytest
```

当前测试主要覆盖：

- JSON 提取
- 列表字符串归一化
- 简历合并逻辑
- 本地兜底逻辑
- HTML 样式参数合并与基础渲染

后续建议优先补充 `tools/permission.py`、`tools/file_tools.py`、`tools/web_tool.py` 的最小测试。

---

## 9. 文档说明

`docs/` 目录下保留了多个阶段的开发文档：

- `docs/MVP_开发文档.md`：早期 MVP 方案
- `docs/开发文档.md`：早期完整扩展方案
- `docs/开发文档v2.0.md`：模块化/定制化方案
- `docs/项目开发交接文档.md`：当前版本交接说明

历史方案文档可能包含 FastAPI、Docker、LangGraph、OCR、评分 Agent 等扩展设想。当前阶段请以 `README.md`、`docs/项目开发交接文档.md` 和实际代码为准。

---

## 10. 下一步建议

当前阶段优先建议：

- 做一次人工验收：应用启动、3 套模板切换、PDF/Markdown 导出、模块新增/删除/排序稳定性
- 给 `tools/` 层补最小测试
- 统一 HTML / Markdown / PDF 对 `modules` 数据结构的读取规则
- 明确 PDF 方案继续走“视觉优先截图转 PDF”，还是改为真正 HTML-to-PDF
- 增强已有简历解析，先从 Markdown / txt / PDF 文本抽取与结构化合并开始

暂不建议优先做 FastAPI、Docker、评分 Agent、真实 OCR 接入。

---

## 11. 用途

该项目更适合作为：

- 课程作业参考
- 个人学习项目
- 简历项目展示素材
- LLM + Streamlit 入门示例

不建议直接视为生产级招聘系统。

# 智能简历生成器 - MVP 开发文档

> 版本：MVP 1.0  
> 目标：快速实现一个可用的简历生成器，具备 **JD 匹配优化、手动编辑、PDF 导出** 三个核心功能，其他非必要功能暂缓。

## 1. MVP 范围限定

### ✅ 保留的核心功能
- 左侧表单填写个人基础信息（姓名、标题、年龄、性别、城市、电话、邮箱、GitHub）
- 左侧表单填写教育经历、技能、项目经历、校园经历、自我评价（多行文本）
- 左侧上传个人照片（可选）
- **JD 输入框（纯文本）** + “智能优化” 按钮
- 调用 LLM 根据 JD 和现有简历内容生成优化后的 JSON
- 右侧实时预览（HTML 风格简单统一，不做多模板切换）
- 支持手动修改左侧任何字段，预览同步更新
- 一键导出 PDF（固定 A4 样式，无复杂样式调节）
- 保存 / 加载 JSON 到磁盘（保留上次编辑状态）

### ❌ 本次不实现的功能
- OCR 识别 JD 图片
- 网页链接抓取 JD
- 多套模板自由切换与动态字体边距调节
- 多智能体（只用单个简历撰写智能体，取消信息收集智能体）
- 工作流编排（LangGraph 先不用，顺序调用即可）
- 内联编辑 / 弹窗编辑（仅靠左侧表单修改）
- 版本历史 / 撤销 AI 修改
- 文件上传 README / 旧简历自动解析

## 2. 技术架构（简化）

```
Streamlit 前端
   ↓
直接调用 LangChain (ChatOpenAI)
   ↓
单次智能体调用：给定 JD + 当前 resume_data → 返回优化后 resume_data
   ↓
更新 st.session_state 并刷新预览
```

- **前端**：Streamlit（单文件 app.py）
- **AI**：LangChain + OpenAI 兼容 API（支持配置 key）
- **配置**：通过 `.env` 或环境变量管理 API Key
- **PDF 生成**：reportlab（复用现有代码，固定格式）
- **数据存储**：`resume_data.json` 自动加载和保存

## 3. 目录结构（极简）

```
resume_mvp/
├── app.py                 # Streamlit 主程序
├── smart_resume_core.py   # 复用原有核心（但简化，去掉多智能体）
├── resume_data.json       # 简历数据文件
├── generate_pdf.py        # PDF 生成函数（从原有代码精简）
├── requirements.txt
└── .env                   # 存储 OPENAI_API_KEY
```

## 4. 数据模型（保持现有 resume_data.json 格式）

```json
{
  "basics": { "name": "...", "headline": "...", ... },
  "education": [...],
  "skills": [...],
  "projects": [...],
  "companyExperience": [...],
  "campusExperience": [...],
  "selfEvaluation": [...]
}
```

## 5. 核心流程设计

### 5.1 初始化与数据持久化
- 启动时读取 `resume_data.json`（如不存在则创建默认模板）
- 任何表单修改都实时写入 `st.session_state.resume_data`，并自动保存到 JSON 文件（防丢失）

### 5.2 智能优化（单次 LLM 调用）
```python
def optimize_resume_by_jd(jd_text: str, current_resume: dict) -> dict:
    prompt = f"""
你是一名资深简历优化专家。请根据以下 JD 和当前简历内容，优化简历。
输出必须是完整的 JSON 格式，保持与原 resume_data 相同的结构。
只修改 skills、projects、selfEvaluation 等可以提升匹配度的部分，不要虚构经历。

JD：
{jd_text}

当前简历数据：
{json.dumps(current_resume, ensure_ascii=False, indent=2)}

请返回优化后的 JSON。
"""
    response = llm.invoke(prompt)
    optimized = extract_json_block(response.content)
    # 安全合并：确保 basics 等关键字段不变
    optimized["basics"] = current_resume["basics"]
    return optimized
```
- 用户点击“智能优化” → 显示 loading → 调用上述函数 → 更新 `session_state.resume_data` → 刷新预览。
- 限制：只允许通过“撤销/重置”按钮恢复上一次版本（简单实现：保存历史快照一次）。

### 5.3 手动编辑
- 左侧完全用 Streamlit 原生组件（`st.text_input`, `st.text_area`, `st.number_input` 等）绑定到 `session_state.resume_data`。
- 每次修改自动保存 JSON 并重新渲染右侧预览。

### 5.4 预览渲染
- 右侧直接用 `st.markdown` + 自定义 CSS 显示简历内容，不使用复杂 HTML 组件。
- 优点：免去内联编辑，只需生成一次静态 markdown。
- 实现：复用原有 `render_markdown()` 函数，输出 markdown 文本，然后用 `st.markdown()` 展示。

### 5.5 PDF 导出
- 用户点击“导出 PDF” → 调用 `generate_pdf_from_resume_data(resume_data)` → 生成临时文件 → 提供下载按钮。
- 复用原有 `generate_resume_pdf.py` 中的 `build_pdf` 函数，但简化字体处理（默认使用系统支持的中文字体或嵌入思源黑体）。

## 6. 界面布局（Streamlit）

```python
st.set_page_config(layout="wide")
col1, col2 = st.columns([1, 1.5], gap="medium")

with col1:
    st.header("📝 编辑简历")
    with st.expander("基本信息", expanded=True):
        basics = st.session_state.resume_data["basics"]
        basics["name"] = st.text_input("姓名", basics["name"])
        ...  # 其他字段
    with st.expander("教育经历"):
        # 简单的列表 + 添加/删除按钮
    with st.expander("技能"):
        skills_text = st.text_area("技能（每行一条）", "\n".join(st.session_state.resume_data["skills"]))
        st.session_state.resume_data["skills"] = [s.strip() for s in skills_text.split("\n") if s.strip()]
    # ... 类似项目经历、自我评价等

    st.divider()
    jd_input = st.text_area("📌 岗位描述 (JD)", height=150, key="jd_input")
    if st.button("✨ 智能优化简历", type="primary"):
        with st.spinner("AI 正在优化中..."):
            new_data = optimize_resume_by_jd(jd_input, st.session_state.resume_data)
            st.session_state.resume_data = new_data
            save_resume_data(new_data)
            st.success("优化完成！手动编辑会覆盖优化结果，可随时重新优化。")

    if st.button("📄 导出 PDF"):
        pdf_bytes = generate_pdf(st.session_state.resume_data)
        st.download_button("下载 PDF", pdf_bytes, file_name="resume.pdf", mime="application/pdf")

with col2:
    st.header("📄 简历预览")
    md_preview = render_markdown(st.session_state.resume_data)
    st.markdown(md_preview)
```

## 7. 需要修改/删除的原有代码

### 删除
- `InfoCollectorAgent`, `ResumeWriterAgent`, `SmartResumeOrchestrator` 中的复杂编排。
- 所有工具 (`resume_file_tools.py`)。
- 多模板 `TEMPLATE_OPTIONS` 和动态样式调节。
- OCR, 网页抓取相关代码。

### 保留并简化
- `extract_json_block`
- `load_resume_data`, `save_resume_data`
- `render_markdown` (基本不变)
- `generate_resume_pdf.py` 中的 PDF 构建逻辑（移除模板依赖，固定样式）
- `smart_resume_core.py` 中的基础工具函数

## 8. 关键实现细节

### 8.1 LLM 配置（支持多种兼容 API）
```python
from langchain_openai import ChatOpenAI
import os

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
    temperature=0.2
)
```

### 8.2 JSON 安全合并
```python
def merge_resume(original: dict, optimized: dict) -> dict:
    """只替换技能、项目、自我评价等部分，保留基础信息与教育等不可变字段。"""
    result = original.copy()
    for key in ["skills", "projects", "selfEvaluation", "companyExperience", "campusExperience"]:
        if key in optimized:
            result[key] = optimized[key]
    # 也可以替换项目中的 highlights 等细节，但不替换 name 和 period
    return result
```

### 8.3 PDF 生成固定样式
- 字体：先尝试注册 Windows / macOS / Linux 通用中文字体，如果失败则使用 reportlab 内置字体（会乱码但加提示）。
- 布局：简单两栏（头像在右），白色背景，黑色字体。
- 不依赖任何模板选择。

## 9. 异常处理与边界
- LLM 调用失败 → 提示用户检查 API Key 或网络。
- LLM 返回非 JSON → 直接显示原始返回内容，不更新数据。
- 导出 PDF 缺少字体 → 提示用户安装中文字体，或降级使用英文字体。
- 图片上传失败 → 忽略头像。

## 10. 开发任务（按顺序）

1. **环境搭建**：创建 `resume_mvp/`，复制必要的原有文件，安装依赖 `streamlit langchain-openai reportlab Pillow`。
2. **数据模型与读写**：实现 `load/save`，默认构建一个空简历模板。
3. **左侧表单**：完成所有字段的绑定（参考原有编辑区，但简化布局）。
4. **右侧预览**：调用 `render_markdown` 并用 `st.markdown` 显示。
5. **智能优化**：实现 `optimize_resume_by_jd` 函数，添加按钮调用。
6. **PDF 导出**：移植 `generate_pdf.py`，创建下载按钮。
7. **持久化**：任何编辑自动保存 JSON。
8. **测试**：完整走一遍流程，确保生成、优化、导出正常。
9. **打包说明**：写 README 告知如何配置 `.env` 和运行。

## 11. 迭代计划（后续 MVP+）
完成此 MVP 后，可根据反馈逐步添加：
- 支持上传个人照片
- 简单的样式调节（字体大小）
- 多份简历版本切换
- OCR JD 识别（用户强烈要求时）

---

## 12. 验收标准
- 用户可以启动 `streamlit run app.py`，在浏览器中打开。
- 能够完整填写一份简历，至少包含教育、技能、项目、自我评价。
- 输入一段假 JD（例如 “招聘后端工程师，精通 C++ 和分布式系统”），点击智能优化，看到项目描述或技能发生合理变化。
- 点击导出 PDF，下载的文件打开后排版清晰，内容与预览一致。
- 关闭浏览器后重新启动，之前填写的内容仍存在（已保存到 JSON）。

---

**文档结束。** 按照此文档，你可以在 **2天内** 完成一个可演示的 MVP。如果需要我直接生成这个 MVP 的所有代码文件，请告知。
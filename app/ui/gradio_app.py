"""Gradio web UI for the Document QA Bot."""

from __future__ import annotations

import gradio as gr

from app.config import EMBED_MODELS, LLM_MODELS
from app.ingestion.index_builder import load_files
from app.kb.index_manager import (
    clear_all_storage,
    debug_file_updates,
    debug_index,
    get_indexed_files,
    get_storage_info_html,
    load_existing_index,
    reset_index_cache,
    save_index,
)
from app.retrieval.retriever_cache import invalidate_hybrid_retriever_cache
from app.services.qa_service import get_last_retrieval_debug, respond
from app.state import app_state

INTRO_MARKDOWN = """
# 竞赛智能客服机器人的使用教程

### 🔗 DocBot 是一个智能竞赛文档问答系统，能够处理以下三类问题：

1. **基础数据查询** — 直接从文档中查找具体信息和事实，如「3D编程模型创新设计专项赛的报名时间是什么时候？」
2. **数据统计分析** — 计算和统计文档中的数量和频率信息，如「人工智能相关竞赛有多少？」；系统会先澄清统计口径再作答
3. **开放性问题** — 在文档信息基础上给出合理建议，如「如何准备某专项赛？」

### 补充说明

- 基础查询和统计分析严格基于已上传文档；文档中无相关信息时，系统会结构化拒答并说明原因
- 开放性问题会先引用文档片段，再标注「以下为补充建议」给出扩展内容
- 回答会自动总结关键点，并在正文标注引用编号 **[1][2]**；对话下方可查看 **引用溯源 / 检索片段** 面板

## 🚀 使用方法

| 操作阶段 | 首次使用 | 非首次使用 |
| --- | --- | --- |
| 准备阶段 | 1. 上传文档（PDF、Word、Excel 等）<br>2. 选择嵌入模型，点击提交 | 1. 在「存储管理」中 **加载已有索引** |
| 提问阶段 | 3. 选择 LLM 模型<br>4. 开始提问 | 2. 选择 LLM 模型<br>3. 开始提问 |

### 🌟 提示

- 支持批量上传多个文件；上传或更新后会 **自动持久化索引**，也可在「存储管理」中手动 **保存索引**
- 首次建库后建议保存索引，便于下次直接加载、无需重新 embedding
- 对话区支持 **Retry**（重新生成）、**Undo**（撤销上轮）、**Clear**（清空对话）
- 默认向量保存在本地 `storage/`；若在 `.env` 中启用 `VECTOR_BACKEND=qdrant`，向量外置到 Qdrant，文本仍保留在本地供 BM25 使用

## 📂 知识库管理与更新

### 💾 存储管理（「开始使用」页底部折叠面板）

- **加载已有索引** — 重启应用后恢复上次知识库
- **保存当前索引** — 手动落盘（上传提交后通常已自动保存）
- **清除所有存储** — 删除索引与 Qdrant 向量（若已启用），**不会**删除 `uploads/` 原始文件

### 📄 新增赛事文档

- 先 **加载已有索引**，再上传新文档并提交，系统会将新文档 **增量合并** 进现有知识库

### 📄 信息变更文档

- 先 **加载已有索引**，上传同名文件时勾选 **「更新已有文件」**，系统会删除旧版本 chunk 并写入新内容

## 🔧 高级工具与调试（「存储管理」下方折叠面板）

- **查看已索引文件** — 列出当前知识库中的文档及上传时间
- **调试当前索引** — 查看 chunk 数量、embedding 模型与抽样检索结果
- **调试文件更新状态** — 对比索引内节点与元数据是否一致
- **重置索引缓存** — 切换嵌入模型或更新索引后，若检索异常可尝试重置
"""

# 设置LLM模型
def set_llm_model(selected_model: str) -> None:
    app_state.selected_llm_model_name = selected_model

# 设置嵌入模型
def set_embed_model(selected_model: str) -> None:
    if app_state.selected_embed_model_name != selected_model:
        invalidate_hybrid_retriever_cache()
    app_state.selected_embed_model_name = selected_model

# 清除UI
def handle_clear():
    return [None, None, "UI已清除，但索引数据仍在内存中"]

# 创建应用
def create_app() -> gr.Blocks:
    app_state.selected_llm_model_name = LLM_MODELS[0]
    app_state.selected_embed_model_name = EMBED_MODELS[0]

    with gr.Blocks(
        theme=gr.themes.Soft(font=[gr.themes.GoogleFont("Roboto Mono")]),
        css="footer {visibility: hidden}; ",
    ) as demo:
        gr.Markdown("# DocBot🤖 - 竞赛智能客服机器人 ")
        with gr.Tabs():
            with gr.TabItem("介绍"):
                gr.Markdown(INTRO_MARKDOWN)

            with gr.TabItem("开始使用🤖"):
                with gr.Row():
                    with gr.Column(scale=1):
                        file_input = gr.File(
                            file_count="multiple",
                            type="filepath",
                            label="第1步：上传文档（支持多个文件）",
                            file_types=[".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx"],
                            height=200,
                        )
                        embed_model_dropdown = gr.Dropdown(
                            EMBED_MODELS,
                            label="第2步：选择嵌入模型",
                            interactive=True,
                        )
                        update_checkbox = gr.Checkbox(
                            label="更新已有文件",
                            info="启用后，相同文件名的文件将替换旧版本",
                            value=False,
                        )
                        with gr.Row():
                            btn = gr.Button("提交", variant="primary")
                            clear = gr.ClearButton()
                        output = gr.Text(label="索引状态")
                        llm_model_dropdown = gr.Dropdown(
                            LLM_MODELS,
                            label="第3步：选择语言模型",
                            interactive=True,
                        )
                    with gr.Column(scale=3):
                        chatbot = gr.Chatbot(label="对话", height=420)
                        chat_input = gr.Textbox(
                            placeholder="第4步：向文档提问，可以是基础查询、统计分析或开放性问题",
                            label="输入问题",
                        )
                        with gr.Row():
                            chat_send = gr.Button("Submit", variant="primary")
                            retry_btn = gr.Button("🔄  Retry")
                            undo_btn = gr.Button("↩️ Undo")
                            clear_chat_btn = gr.Button("🗑️  Clear")
                        retrieval_debug = gr.Textbox(
                            label="引用溯源 / 检索片段（最近一次提问）",
                            lines=10,
                            interactive=False,
                        )
                        chat_busy = gr.State(value=False)

                        def _lock_chat_controls():
                            return gr.update(interactive=False), gr.update(interactive=False)

                        def _unlock_chat_controls():
                            return gr.update(interactive=True), gr.update(interactive=True)

                        def chat_submit(message: str, history: list, busy: bool):
                            locked = _lock_chat_controls()
                            unlocked = _unlock_chat_controls()
                            if not message or not message.strip():
                                yield history, "", get_last_retrieval_debug(), *unlocked, busy
                                return
                            if busy:
                                yield history, "", get_last_retrieval_debug(), *locked, True
                                return
                            text = message.strip()
                            prior = list(history)
                            yield (
                                prior + [[text, "⏳ 正在检索并生成回答…"]],
                                "",
                                "正在处理您的问题…",
                                *locked,
                                True,
                            )
                            reply = respond(text, prior)
                            yield (
                                prior + [[text, reply]],
                                "",
                                get_last_retrieval_debug(),
                                *unlocked,
                                False,
                            )

                        def handle_chat_retry(history: list, busy: bool):
                            locked = _lock_chat_controls()
                            unlocked = _unlock_chat_controls()
                            if busy:
                                yield history, "", get_last_retrieval_debug(), *locked, True
                                return
                            if not history:
                                yield history, "", get_last_retrieval_debug(), *unlocked, busy
                                return
                            last_user_msg = history[-1][0]
                            prior_history = history[:-1]
                            yield (
                                prior_history + [[last_user_msg, "⏳ 正在重新生成…"]],
                                "",
                                "正在重新生成回答…",
                                *locked,
                                True,
                            )
                            reply = respond(last_user_msg, prior_history)
                            yield (
                                prior_history + [[last_user_msg, reply]],
                                "",
                                get_last_retrieval_debug(),
                                *unlocked,
                                False,
                            )

                        def handle_chat_undo(history: list, busy: bool):
                            locked = _lock_chat_controls()
                            unlocked = _unlock_chat_controls()
                            if busy or not history:
                                controls = locked if busy else unlocked
                                return (
                                    history,
                                    "",
                                    get_last_retrieval_debug(),
                                    *controls,
                                    busy,
                                )
                            last_user_msg = history[-1][0] or ""
                            return (
                                history[:-1],
                                last_user_msg,
                                get_last_retrieval_debug(),
                                *unlocked,
                                busy,
                            )

                        def handle_chat_clear():
                            return [], "", "（尚未提问，或无检索记录）"

                        chat_outputs = [
                            chatbot,
                            chat_input,
                            retrieval_debug,
                            retry_btn,
                            undo_btn,
                            chat_busy,
                        ]

                        chat_send.click(
                            chat_submit,
                            inputs=[chat_input, chatbot, chat_busy],
                            outputs=chat_outputs,
                        )
                        chat_input.submit(
                            chat_submit,
                            inputs=[chat_input, chatbot, chat_busy],
                            outputs=chat_outputs,
                        )
                        retry_btn.click(
                            handle_chat_retry,
                            inputs=[chatbot, chat_busy],
                            outputs=chat_outputs,
                        )
                        undo_btn.click(
                            handle_chat_undo,
                            inputs=[chatbot, chat_busy],
                            outputs=chat_outputs,
                        )
                        clear_chat_btn.click(
                            handle_chat_clear,
                            outputs=[chatbot, chat_input, retrieval_debug],
                        )

                gr.Markdown("---")

                with gr.Accordion("🔧 存储管理", open=False):
                    with gr.Row():
                        with gr.Column(scale=3):
                            save_btn = gr.Button("💾 保存当前索引", variant="secondary")
                            load_btn = gr.Button("🔃 加载已有索引", variant="secondary")
                            clear_btn = gr.Button("⚠️ 清除所有存储", variant="stop")
                        with gr.Column(scale=7):
                            storage_status = gr.Textbox(label="存储状态", interactive=False)
                            storage_info = gr.Markdown(
                                """
                                **存储说明**  
                                - 保存路径: `./storage/`（索引）+ Qdrant（向量，可选）  
                                - `uploads/` 存放原始文件，清除索引时**不会**删除  
                                - 支持增量更新  
                                - 清除索引操作不可逆！
                                """
                            )

                with gr.Accordion("⚙️ 高级工具与调试", open=False):
                    with gr.Row():
                        indexed_files_btn = gr.Button("📋 查看已索引文件")
                        debug_btn = gr.Button("🔍 调试当前索引")

                    indexed_files_output = gr.Textbox(label="已索引文件列表")
                    debug_output = gr.Textbox(label="调试信息")

                    with gr.Row():
                        debug_updates_btn = gr.Button("🔍 调试文件更新状态")
                        reset_cache_btn = gr.Button("🔄 重置索引缓存", variant="stop")

                    debug_updates_output = gr.Textbox(label="文件更新调试信息", lines=10)

        gr.HTML(
            "<div class='black-bar' style='background-color:#1E2A37; color:white; "
            "text-align:center; margin:15px; padding:10px; border-radius:4px;' >到底了哟~</div>"
        )

        llm_model_dropdown.change(fn=set_llm_model, inputs=llm_model_dropdown)
        embed_model_dropdown.change(fn=set_embed_model, inputs=embed_model_dropdown)
        btn.click(
            fn=load_files,
            inputs=[
                file_input,
                embed_model_dropdown,
                gr.Checkbox(value=False, visible=False),
                update_checkbox,
            ],
            outputs=output,
        )
        clear.click(fn=handle_clear, outputs=[file_input, embed_model_dropdown, output])

        indexed_files_btn.click(fn=get_indexed_files, outputs=indexed_files_output)
        debug_btn.click(fn=debug_index, outputs=debug_output)
        debug_updates_btn.click(fn=debug_file_updates, outputs=debug_updates_output)
        reset_cache_btn.click(fn=reset_index_cache, outputs=storage_status)

        save_btn.click(fn=save_index, outputs=storage_status, queue=False)
        load_btn.click(fn=load_existing_index, outputs=storage_status, queue=False).then(
            fn=lambda: app_state.selected_embed_model_name,
            outputs=embed_model_dropdown,
        ).then(
            fn=get_storage_info_html,
            outputs=storage_info,
        )
        clear_btn.click(fn=clear_all_storage, outputs=storage_status, queue=False).then(
            fn=lambda: (
                "<div style='color: #666; font-size: 0.8em'>"
                "存储位置: ./storage/<br>上次更新时间: 数据已清除</div>"
            ),
            outputs=storage_info,
        )

    demo.queue(default_concurrency_limit=2)
    return demo

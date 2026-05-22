from __future__ import annotations

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "联网搜索实时信息，如新闻、天气、价格、最新版本等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询词",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "抓取网页并提取正文。用于 web_search 后需要阅读全文"
                "（研报、文档、新闻深度）的场景；urls 须来自搜索来源或用户提供的 http(s) 链接。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要抓取的 URL 列表，最多 3 个",
                    },
                },
                "required": ["urls"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "精确计算数学表达式，支持 + - * / % ** 与括号。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "算术表达式，如 (12+3)*4",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "从用户知识库检索课程资料、实验手册、公司文档等已上传内容。"
                "适用于实训/内部文档问答；与 web_search（实时互联网）区分。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索查询，可用用户原话或提炼的关键词",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回片段数量，默认 5",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "parse_document",
            "description": "解析用户上传的 PDF/文本/Markdown 附件，提取正文。",
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
                        "description": "附件 ID（上传接口返回）",
                    },
                },
                "required": ["attachment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_image",
            "description": "识图：分析用户上传的图片附件，回答关于画面内容的问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "attachment_id": {
                        "type": "string",
                        "description": "图片附件 ID",
                    },
                    "question": {
                        "type": "string",
                        "description": "针对图片的具体问题，可省略则做整体描述",
                    },
                },
                "required": ["attachment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "根据文字描述生成图片。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "图片描述",
                    },
                    "size": {
                        "type": "string",
                        "description": '图片尺寸，如 "1024x1024"',
                    },
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_video",
            "description": "根据文字描述生成视频；可将会话中上一张生成的图片作为首帧。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "视频描述",
                    },
                    "size": {
                        "type": "string",
                        "description": '视频尺寸，如 "1280x720"',
                    },
                    "duration_seconds": {
                        "type": "integer",
                        "description": "视频时长（秒），1-120",
                    },
                    "use_session_image": {
                        "type": "boolean",
                        "description": "是否使用会话中最近生成的图片作为视频首帧",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
]

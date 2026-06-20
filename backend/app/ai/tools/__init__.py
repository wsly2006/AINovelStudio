"""通用工具集 — 与具体适配器(MCP / LiteLLM tool calling / ...)解耦。

每个域一个文件,顶部 import 即触发 @tool 装饰器把函数注册到 REGISTRY。
适配器层只需 `from app.ai.tools import projects, chapters, characters`
就能让所有工具就位,然后从 REGISTRY 按需挑选挂载。
"""

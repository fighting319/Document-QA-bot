"""Compatibility patch for gradio_client + newer pydantic JSON schemas."""

# 兼容性补丁，解决gradio_client和pydantic JSON模式不兼容的问题
def patch_gradio_client_schema() -> None:
    """
    gradio 4.44.1 bundles gradio_client 1.3.0, which crashes when pydantic >= 2.11
    emits boolean values in JSON schema fields (e.g. additionalProperties: true).

    See: https://github.com/gradio-app/gradio/issues/11722
    """
    import gradio_client.utils as gcu

    if getattr(gcu, "_docbot_schema_patch_applied", False):
        return

    orig_get_type = gcu.get_type
    orig_json_to_py = gcu._json_schema_to_python_type

    def safe_get_type(schema):
        if not isinstance(schema, dict):
            return "bool" if isinstance(schema, bool) else "Any"
        return orig_get_type(schema)

    def safe_json_to_py(schema, defs=None):
        if not isinstance(schema, dict):
            return "bool" if isinstance(schema, bool) else "Any"
        return orig_json_to_py(schema, defs)

    gcu.get_type = safe_get_type
    gcu._json_schema_to_python_type = safe_json_to_py
    gcu._docbot_schema_patch_applied = True

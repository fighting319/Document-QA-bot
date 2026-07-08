"""Application entry point."""

import os

import nest_asyncio

from app.ui.gradio_compat import patch_gradio_client_schema

# Must run before any `import gradio`
patch_gradio_client_schema()

from app.bootstrap.warmup import warmup_models
from app.ui.gradio_app import create_app

nest_asyncio.apply()


def main() -> None:
    print("DEEPSEEK_API_KEY exists:", "DEEPSEEK_API_KEY" in os.environ)

    warmup_models()
    demo = create_app()
    demo.launch(
        server_name=os.getenv("GRADIO_HOST", "127.0.0.1"),
        server_port=int(os.getenv("GRADIO_PORT", "7860")),
        show_error=True,
    )


if __name__ == "__main__":
    main()

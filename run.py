"""Single entry point for hosting platforms (Railway, ...).

One repository, two services:
  SERVICE_ROLE unset / "bot"  ->  the Telegram bot (+ its webhook server)
  SERVICE_ROLE="pricer"       ->  the AI product analyser (FastAPI, product_processing/)
"""
import os
import runpy

role = os.getenv("SERVICE_ROLE", "bot").strip().lower()

if role == "pricer":
    os.makedirs("logs", exist_ok=True)
    import uvicorn

    uvicorn.run(
        "product_processing.main:app",
        # Railway's private network can be IPv6-only: set PRICER_HOST=:: there (dual-stack).
        host=os.getenv("PRICER_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8001")),
        log_level="info",
    )
else:
    runpy.run_path("bot.py", run_name="__main__")

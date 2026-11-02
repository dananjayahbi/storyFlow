import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        """
        Run on Django startup. Registers asset-store signal handlers and
        checks TTS model availability, logging a warning if the model file
        is not found.
        """
        # Keep Storage/<Section>/<project>/project.json + script.txt in sync.
        from . import storage  # noqa: F401  (registers signals)

        try:
            from core_engine.model_loader import KokoroModelLoader

            if not KokoroModelLoader.is_model_available():
                logger.warning(
                    "\n"
                    "╔══════════════════════════════════════════════════════╗\n"
                    "║  TTS MODEL NOT FOUND                                ║\n"
                    "║                                                      ║\n"
                    "║  The Kokoro-82M ONNX model is not installed.         ║\n"
                    "║  TTS features will be unavailable.                   ║\n"
                    "║                                                      ║\n"
                    "║  To enable TTS:                                      ║\n"
                    "║  1. Download kokoro-v0_19.onnx from HuggingFace     ║\n"
                    "║  2. Place it in the models/ directory               ║\n"
                    "║                                                      ║\n"
                    "║  All other features work normally.                   ║\n"
                    "╚══════════════════════════════════════════════════════╝"
                )
            else:
                logger.info("TTS model found — Kokoro-82M ready.")
        except Exception:
            # Never prevent startup due to model check failures
            pass

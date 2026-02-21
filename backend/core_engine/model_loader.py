"""
KokoroModelLoader — Thread-safe singleton for Kokoro-82M ONNX model.

Lazily loads the ONNX model exactly once and reuses the InferenceSession
for all subsequent inference calls. Uses double-checked locking for
thread safety without hot-path lock contention.
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)

MODEL_FILENAME = "kokoro-v0_19.onnx"


class KokoroModelLoader:
    """
    Singleton model loader for the Kokoro-82M ONNX TTS model.

    Uses double-checked locking to ensure thread-safe lazy initialization:
    - Outer check avoids lock contention on the hot path.
    - Inner check prevents race conditions between threads.
    """

    _session = None
    _lock = threading.Lock()

    @classmethod
    def get_session(cls):
        """
        Return the shared ONNX InferenceSession, loading the model on first call.

        Uses double-checked locking:
        1. Fast path — return immediately if already loaded (no lock).
        2. Acquire lock if not loaded.
        3. Re-check inside lock (another thread may have loaded it).
        4. Load model if still None.

        Returns:
            onnxruntime.InferenceSession: The loaded ONNX model session.

        Raises:
            FileNotFoundError: If the model file does not exist on disk.
            RuntimeError: If ONNX Runtime fails to create the session.
        """
        # Fast path — no lock needed
        if cls._session is not None:
            return cls._session

        # Slow path — acquire lock
        with cls._lock:
            # Double-check after acquiring lock
            if cls._session is None:
                cls._load_model()

        return cls._session

    @classmethod
    def _load_model(cls):
        """
        Load the Kokoro ONNX model into an InferenceSession.

        Resolves the model path, verifies the file exists, and creates
        the ONNX Runtime session. Stores the session in cls._session.

        Raises:
            FileNotFoundError: If the model file is not found.
            RuntimeError: If ONNX Runtime fails to load the model.
        """
        import onnxruntime as ort

        model_path = cls._resolve_model_path()

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Kokoro ONNX model not found at: {model_path}\n\n"
                f"To download the model:\n"
                f"  1. Visit https://huggingface.co/hexgrad/Kokoro-82M\n"
                f"  2. Download '{MODEL_FILENAME}'\n"
                f"  3. Place it in the 'models/' directory at the project root\n\n"
                f"Expected path: {model_path}"
            )

        try:
            cls._session = ort.InferenceSession(str(model_path))
            logger.info("Kokoro ONNX model loaded successfully from: %s", model_path)
        except Exception as e:
            raise RuntimeError(
                f"Failed to create ONNX InferenceSession: {e}"
            ) from e

    @classmethod
    def _resolve_model_path(cls):
        """
        Resolve the absolute path to the Kokoro ONNX model file.

        Uses Django's BASE_DIR to navigate to the /models/ directory
        at the project root (parent of the backend directory).

        Returns:
            str: Absolute path to the model file.
        """
        from django.conf import settings

        # BASE_DIR = backend/  →  BASE_DIR.parent = project root
        model_dir = settings.BASE_DIR.parent / "models"
        return str(model_dir / MODEL_FILENAME)

    @classmethod
    def is_model_available(cls):
        """
        Check whether the model file exists on disk.

        This is a lightweight check that does NOT load the model.

        Returns:
            bool: True if the model file exists, False otherwise.
        """
        model_path = cls._resolve_model_path()
        return os.path.exists(model_path)

    @classmethod
    def get_model_info(cls):
        """
        Return metadata about the loaded model's input/output tensors.

        Calls get_session() to ensure the model is loaded, then inspects
        the session for input and output tensor details.

        Returns:
            dict: Dictionary with 'inputs' and 'outputs' keys, each
                  containing a list of dicts with 'name', 'shape', and
                  'type' for each tensor.

        Raises:
            FileNotFoundError: If the model file does not exist.
            RuntimeError: If the model cannot be loaded.
        """
        session = cls.get_session()

        inputs = []
        for inp in session.get_inputs():
            inputs.append({
                "name": inp.name,
                "shape": inp.shape,
                "type": inp.type,
            })

        outputs = []
        for out in session.get_outputs():
            outputs.append({
                "name": out.name,
                "shape": out.shape,
                "type": out.type,
            })

        return {
            "inputs": inputs,
            "outputs": outputs,
        }

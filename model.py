"""Fábrica de modelos.

Los agentes (agenteV*.py) solo llaman a get_model(); no saben qué proveedor
hay detrás. Para cambiar de modelo se editan las variables del .env.
"""
import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

load_dotenv()


def get_model() -> BaseChatModel:
    provider = os.getenv("MODEL_PROVIDER", "google_genai")
    name = os.getenv("MODEL_NAME", "gemini-2.5-flash")

    if provider == "lmstudio":
        # LM Studio imita la API de OpenAI, así que usamos el proveedor "openai"
        # apuntando al servidor local. La api_key es obligatoria para el cliente,
        # pero LM Studio la ignora, por eso va un valor cualquiera.
        return init_chat_model(
            name,
            model_provider="openai",
            base_url=os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
            api_key="lm-studio",
            temperature=0,
        )

    if provider == "google_genai" and not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            "Falta GOOGLE_API_KEY. Copiá .env.example a .env y completalo."
        )

    return init_chat_model(name, model_provider=provider, temperature=0)
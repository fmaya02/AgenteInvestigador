"""Fábrica de modelos.

Los agentes (agenteV*.py) solo llaman a get_model(); no saben qué proveedor
hay detrás. Para cambiar de modelo se editan las variables del .env.
"""
import os
from pydantic import SecretStr
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

load_dotenv()

def get_embeddings():
    """Modelo de embeddings para el RAG: Google, vía API (capa gratuita)."""
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            "Falta GOOGLE_API_KEY (también se usa para los embeddings del RAG). "
            "Copiá .env.example a .env y completalo."
        )
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

def get_model() -> BaseChatModel:
    provider = os.getenv("MODEL_PROVIDER", "google_genai")
    name = os.getenv("MODEL_NAME", "gemini-2.5-flash")

    if provider == "lmstudio":
        from chat_lmstudio import ChatLMStudio

        return ChatLMStudio(
            model=name,
            base_url=os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
            api_key=SecretStr("lm-studio"),   # el cliente la exige, LM Studio la ignora
            temperature=0,
        )

    if provider == "openrouter":
        if not os.getenv("OPENROUTER_API_KEY"):
            raise RuntimeError(
                "Falta OPENROUTER_API_KEY. Copiá .env.example a .env y completalo."
            )
        from langchain_openrouter import ChatOpenRouter

        # ChatOpenRouter lee OPENROUTER_API_KEY del entorno automáticamente.
        return ChatOpenRouter(
            model=name,
            temperature=0,
            reasoning={"effort": "high", "summary": "auto"},
        )

    if provider == "google_genai":
        if not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError(
                "Falta GOOGLE_API_KEY. Copiá .env.example a .env y completalo."
            )
        # include_thoughts=True: Gemini devuelve resúmenes de su razonamiento.
        return init_chat_model(
            name, model_provider=provider, temperature=0, include_thoughts=True
        )

    return init_chat_model(name, model_provider=provider, temperature=0)
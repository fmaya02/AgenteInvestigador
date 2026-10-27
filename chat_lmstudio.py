"""ChatOpenAI para LM Studio que conserva el razonamiento del modelo.

LM Studio devuelve el razonamiento en `message.reasoning_content`, un campo que no
es parte de la API de OpenAI y que ChatOpenAI descarta. Esta subclase lo copia a
`additional_kwargs`, de donde lo lee el agente.
"""
from langchain_openai import ChatOpenAI


class ChatLMStudio(ChatOpenAI):
    def _create_chat_result(self, response, generation_info=None):
        result = super()._create_chat_result(response, generation_info)
        datos = response if isinstance(response, dict) else response.model_dump()
        for generacion, choice in zip(result.generations, datos["choices"]):
            razonamiento = choice["message"].get("reasoning_content")
            if razonamiento:
                generacion.message.additional_kwargs["reasoning_content"] = razonamiento
        return result
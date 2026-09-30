"""Agente V1: el create_agent más básico, sin tools.

Ejecutar con:  python agenteV1.py
"""
from langchain.agents import create_agent

from model import get_model
from toolsV1 import TOOLS

SYSTEM_PROMPT = "Sos un asistente útil y conciso. Respondé en el idioma del usuario."

agent = create_agent(
    model=get_model(),
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
)


def main() -> None:
    print("Agente V1 listo. Escribí 'salir' para terminar.\n")
    messages: list = []

    while True:
        user_input = input("Vos: ").strip()
        if user_input.lower() in {"salir", "exit", "quit"}:
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        result = agent.invoke({"messages": messages})

        # El agente devuelve el historial completo; lo reutilizamos como memoria.
        messages = result["messages"]
        print(f"Agente: {messages[-1].text}\n")


if __name__ == "__main__":
    main()
"""UI de Streamlit para el agente V6: conversaciones múltiples.

La lógica del agente vive en agenteV6.py; acá solo se presenta.

Ejecutar con:  streamlit run appV6.py
"""
import streamlit as st

try:
    from agenteV6 import (
        TurnResult, count_turns, list_threads, new_thread, resume_thread,
        run_turn, saved_state, select_thread,
    )
except RuntimeError as e:  # por ejemplo, faltan API keys en el .env
    st.error(str(e))
    st.stop()

st.set_page_config(page_title="Agente investigador", page_icon="🔎")


def init_session(config) -> None:
    """Carga en session_state la conversación indicada (vacía si es nueva)."""
    mensajes = saved_state(config).get("messages", [])
    st.session_state.config = config
    st.session_state.turno = count_turns(mensajes)
    st.session_state.historial = [
        {"role": "user" if m.type == "human" else "assistant", "content": m.text, "result": None}
        for m in mensajes
        if m.type in ("human", "ai") and m.text   # se omiten tool calls y resultados de tools
    ]


def render_details(r: TurnResult) -> None:
    """Muestra, bajo la respuesta, lo que hizo el agente en ese turno."""
    if r.reasoning:
        with st.expander("Razonamiento"):
            for texto in r.reasoning:
                st.markdown(texto)
    if r.sources:
        with st.expander(f"Fuentes consultadas ({len(r.sources)})"):
            for s in r.sources:
                if s["url"].startswith("http"):
                    st.markdown(f"- [{s['title']}]({s['url']})")
                else:
                    st.markdown(f"- 📄 {s['title']}")


def render_sidebar() -> None:
    """Manejo de conversaciones: crear una nueva o volver a una anterior."""
    actual = st.session_state.config["configurable"]["thread_id"]
    with st.sidebar:
        st.header("Conversaciones")

        # Deshabilitado si la actual todavía está vacía: no tiene sentido crear otra.
        if st.button("➕ Nueva conversación", disabled=not st.session_state.historial):
            init_session(new_thread())
            st.rerun()

        for thread_id, titulo in list_threads():
            if st.button(titulo, key=thread_id, disabled=thread_id == actual,
                         use_container_width=True):
                init_session(select_thread(thread_id))
                st.rerun()

if "config" not in st.session_state:
    init_session(resume_thread())

st.title("🔎 Agente investigador")
render_sidebar()

# Streamlit re-ejecuta todo el script en cada interacción: se redibuja el historial guardado.
for entrada in st.session_state.historial:
    with st.chat_message(entrada["role"]):
        st.markdown(entrada["content"])   # st.markdown renderiza el markdown del modelo
        if entrada["result"] is not None:
            render_details(entrada["result"])

if prompt := st.chat_input("Escribí tu consulta..."):
    turno = st.session_state.turno + 1
    st.chat_message("user").markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("El agente está trabajando..."):
            try:
                resultado = run_turn(prompt, st.session_state.config, turno)
            except Exception as e:
                st.error(f"El agente falló: {e}")
                st.stop()

    st.session_state.turno = turno
    st.session_state.historial += [
        {"role": "user", "content": prompt, "result": None},
        {"role": "assistant", "content": resultado.answer, "result": resultado},
    ]
    st.rerun()   # redibuja todo (historial, conversaciones y TODOs) desde session_state
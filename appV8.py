"""UI de Streamlit para el agente V8: muestra en vivo el recorrido del agente.

La lógica vive en agenteV8.py; acá solo se dibujan los eventos que emite.

Ejecutar con:  streamlit run appV8.py
"""
import streamlit as st
from pathlib import Path

try:
    from agenteV8 import (
        list_threads, new_thread, resume_thread, saved_turns, select_thread, stream_turn,
    )
except RuntimeError as e:  # por ejemplo, faltan API keys en el .env
    st.error(str(e))
    st.stop()

PASOS_EXPANDIDOS = True   # False: razonamiento y tools quedan plegados
ICONOS = {"pending": "⬜", "in_progress": "🔄", "done": "✅"}

st.set_page_config(page_title="Agente investigador", page_icon="🔎")


def init_session(config) -> None:
    """Carga en session_state la conversación indicada (vacía si es nueva)."""
    st.session_state.config = config
    st.session_state.historial = saved_turns(config)   # lista de (pregunta, eventos)


def titulo_llamada(e: dict) -> str:
    nombre, args = e["nombre"], e["args"]
    if nombre == "web_search":
        return f"🌐 Búsqueda web: «{args.get('query', '')}»"
    if nombre == "search_knowledge_base":
        return f"📚 Base de conocimiento: «{args.get('query', '')}»"
    if nombre == "write_todos":
        return "📝 Escribió la lista de TODOs"
    if nombre == "read_todos":
        return "📋 Leyó la lista de TODOs"
    if nombre == "load_skill":
        return f"📖 Skill «{args.get('nombre', '')}»"
    if nombre == "create_pdf":
        return f"📄 PDF: «{args.get('titulo', '')}»"
    return f"🔧 {nombre}"


def detalle_llamada(e: dict) -> None:
    """Lo que se sabe apenas el agente decide llamar a la tool (sus argumentos)."""
    if e["nombre"] == "write_todos":
        for t in e["args"].get("todos", []):
            st.markdown(f"{ICONOS.get(t['status'], '•')} {t['task']}")
    elif e["nombre"] == "create_pdf":
        st.code(e["args"].get("cuerpo", ""), language="latex")   # el LaTeX que escribió el modelo


def detalle_resultado(llamada: dict, r: dict) -> str | None:
    """Reporte de lo que devolvió la tool. Devuelve "error" si la tool falló."""
    nombre, datos = llamada["nombre"], r["datos"]
    if nombre == "web_search":
        for f in datos or []:
            st.markdown(f"- [{f['title']}]({f['url']})")
    elif nombre == "search_knowledge_base":
        for f in datos or []:
            st.markdown(f"- 📄 **{f['archivo']}**: _{f['fragmento']}…_")
    elif nombre == "read_todos":
        st.text(r["texto"])
    elif nombre == "create_pdf":
        pdf = Path(datos["pdf"]) if datos else None
        if pdf and pdf.exists():
            st.download_button("⬇️ Descargar PDF", pdf.read_bytes(), file_name=pdf.name,
                               mime="application/pdf", key=r["id"])
        else:
            st.code(r["texto"], language=None)   # el error de compilación
            return "error"
    return None


def render_eventos(eventos) -> list[dict]:
    """Dibuja los eventos a medida que llegan; sirve en vivo (generador) y para el historial (lista).

    Devuelve los eventos ya dibujados, para guardarlos en el historial.
    """
    emitidos = []
    llamadas = {}   # id del tool call -> (evento de la llamada, contenedor st.status)
    for e in eventos:
        emitidos.append(e)
        tipo = e["tipo"]
        if tipo == "razonamiento":
            with st.expander("💭 Razonamiento", expanded=PASOS_EXPANDIDOS):
                # Un salto de línea por renglón y sin sangrías (que markdown tomaría por código).
                st.markdown("  \n".join(l.strip() for l in e["texto"].splitlines()))
        elif tipo == "texto":
            st.markdown(e["texto"])   # st.markdown renderiza el markdown del modelo
        elif tipo == "llamada":
            status = st.status(titulo_llamada(e), expanded=PASOS_EXPANDIDOS)   # "running" hasta que llegue el resultado
            with status:
                detalle_llamada(e)
            llamadas[e["id"]] = (e, status)
        elif tipo == "resultado":
            llamada, status = llamadas[e["id"]]
            with status:
                estado = detalle_resultado(llamada, e)
            status.update(state=estado or "complete")
        elif tipo == "fuentes":
            with st.expander(f"Fuentes consultadas ({len(e['fuentes'])})"):
                for s in e["fuentes"]:
                    if s["url"].startswith("http"):
                        st.markdown(f"- [{s['title']}]({s['url']})")
                    else:
                        st.markdown(f"- 📄 {s['title']}")
    return emitidos


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
for pregunta, eventos in st.session_state.historial:
    st.chat_message("user").markdown(pregunta)
    with st.chat_message("assistant"):
        render_eventos(eventos)

if prompt := st.chat_input("Escribí tu consulta..."):
    turno = len(st.session_state.historial) + 1
    st.chat_message("user").markdown(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner("El agente está trabajando..."):
                eventos = render_eventos(stream_turn(prompt, st.session_state.config, turno))
        except Exception as e:
            st.error(f"El agente falló: {e}")
            st.stop()

    st.session_state.historial.append((prompt, eventos))
    st.rerun()   # redibuja todo desde session_state
"""Tools de la versión 4: búsqueda web + memoria de corto plazo (mensajes + TODOs).

Las tools leen el estado con `runtime.state` y lo escriben devolviendo un
`Command(update=...)`. El checkpointer (ver agenteV4.py) persiste ese estado
por thread. El turno actual llega por el runtime context (`runtime.context`).
"""
import os
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from langchain.agents import AgentState
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command
from typing_extensions import TypedDict
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from uuid import uuid4

load_dotenv()

from rag.store import DB_DIR, get_store

if not DB_DIR.exists():
    raise RuntimeError("Falta la base vectorial del RAG. Ejecutá: python -m rag.ingest")

_kb = get_store()

if not os.getenv("TAVILY_API_KEY"):
    raise RuntimeError("Falta TAVILY_API_KEY. Agregala a tu .env (ver .env.example).")

_tavily = TavilySearch(
    max_results=4,
    topic="general",
    search_depth="basic",
    include_answer=False,
)


@dataclass
class Context:
    """Datos de solo lectura de cada invocación (runtime context, no se guarda en el estado)."""
    turn: int


class Todo(TypedDict):
    task: str
    status: Literal["pending", "in_progress", "done"]


def _merge_sources(actuales: list | None, nuevas: list) -> list:
    """Reducer: acumula fuentes sin repetir la misma URL dentro de un turno."""
    por_clave = {(s["turn"], s["url"]): s for s in (actuales or []) + nuevas}
    return list(por_clave.values())


class ResearchState(AgentState):
    """Estado del agente: `messages` (heredado) + TODOs + fuentes."""
    todos: list[Todo]
    sources: Annotated[list[dict], _merge_sources]   # fuentes, cada una con su turno


def _respond(runtime: ToolRuntime[Any, Any], texto: str, artifact=None, **update) -> Command:
    """Actualiza el estado y agrega el ToolMessage que exige todo tool call.

    `artifact` son datos para la UI (no se le envían al modelo).
    """
    msg = ToolMessage(texto, tool_call_id=runtime.tool_call_id, artifact=artifact)
    return Command(update={**update, "messages": [msg]})

# --- Skills y creación de PDF -------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
SKILLS_DIR = BASE_DIR / "skills"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Tectonic se resuelve una sola vez, a ruta absoluta. Nada de lo que escriba el
# modelo interviene en qué programa se ejecuta.
_ruta = shutil.which(os.getenv("TECTONIC_PATH", "tectonic"))
if _ruta is None:
    raise RuntimeError(
        "No se encontró Tectonic. Instalalo o indicá su ruta en TECTONIC_PATH (ver .env.example)."
    )
TECTONIC = str(Path(_ruta).resolve())

# El modelo escribe solo el cuerpo; el preámbulo es fijo y sabemos que compila.
PLANTILLA = r"""\documentclass[11pt]{article}
\usepackage{fontspec}
\usepackage[spanish]{babel}
\usepackage[a4paper,margin=2.5cm]{geometry}
\usepackage{amsmath}
\usepackage{booktabs}
\usepackage[hidelinks]{hyperref}
\title{<<TITULO>>}
\author{}
\date{\today}
\begin{document}
\maketitle
<<CUERPO>>
\end{document}
"""

# Comandos que leen o escriben archivos, alteran el motor o rompen la plantilla.
# Defensa adicional: no es una lista exhaustiva (ver notas de seguridad).
PROHIBIDO = (
    r"\input", r"\include", r"\InputIfFileExists", r"\openin", r"\openout",
    r"\read", r"\write", r"\immediate", r"\special", r"\XeTeX", r"\catcode",
    r"\csname", r"\makeatletter", r"\usepackage", r"\documentclass",
    r"\verbatiminput", r"\lstinputlisting", r"\begin{document}", r"\end{document}",
    "^^",
)


def _descripcion(ruta: Path) -> str:
    """Valor de `description:` en el encabezado de una skill."""
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.startswith("description:"):
            return linea.removeprefix("description:").strip()
    return ""


def listar_skills() -> str:
    """'nombre: descripción' de cada skill, para el system prompt."""
    return "; ".join(f"{p.stem}: {_descripcion(p)}" for p in sorted(SKILLS_DIR.glob("*.md")))


def _escapar(texto: str) -> str:
    """Escapa los caracteres especiales de LaTeX (el título llega como texto plano)."""
    return texto.translate(str.maketrans({
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
        "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }))


def _compilar(tex: Path) -> subprocess.CompletedProcess:
    """Único punto del programa que ejecuta un proceso externo: Tectonic, con argumentos fijos."""
    return subprocess.run(
        [TECTONIC, "-X", "compile", "--untrusted", "--outdir", str(OUTPUT_DIR), str(tex)],
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,   # la primera vez descarga paquetes y puede tardar
        cwd=OUTPUT_DIR,
        env={**os.environ, "TECTONIC_UNTRUSTED_MODE": "1"},
    )


@tool
def load_skill(nombre: str) -> str:
    """Carga las instrucciones detalladas de una skill (ver las disponibles en el prompt).

    Usala antes de una tarea para la que exista una skill.
    """
    skills = {p.stem: p for p in SKILLS_DIR.glob("*.md")}
    if nombre not in skills:
        return f"No existe la skill «{nombre}». Disponibles: {', '.join(skills)}."
    return skills[nombre].read_text(encoding="utf-8")


@tool
def create_pdf(titulo: str, cuerpo: str, runtime: ToolRuntime[Context]) -> Command:
    r"""Crea un PDF a partir de un título y el CUERPO de un documento LaTeX.

    `cuerpo` es solo lo que va entre \begin{document} y \end{document} (secciones,
    listas, tablas, fórmulas): la herramienta agrega el preámbulo, el título y la
    fecha. Antes de escribir LaTeX por primera vez, cargá la skill «latex» con
    load_skill. Si la compilación falla, devuelve el error: corregí el cuerpo y
    reintentá (máximo 3 intentos).
    """
    prohibido = next((p for p in PROHIBIDO if p in cuerpo), None)
    if prohibido:
        return _respond(
            runtime,
            f"Rechazado: el cuerpo no puede contener «{prohibido}». "
            "Enviá solo contenido (secciones, listas, tablas, fórmulas).",
        )

    titulo = " ".join(titulo.split())
    ascii_titulo = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_titulo.lower()).strip("-")[:40] or "documento"
    tex = OUTPUT_DIR / f"{slug}-{uuid4().hex[:6]}.tex"
    tex.write_text(
        PLANTILLA.replace("<<TITULO>>", _escapar(titulo)).replace("<<CUERPO>>", cuerpo),
        encoding="utf-8",
    )

    try:
        proc = _compilar(tex)
    except subprocess.TimeoutExpired:
        return _respond(runtime, "La compilación superó el tiempo máximo (180 s).")

    pdf = tex.with_suffix(".pdf")
    if proc.returncode != 0 or not pdf.exists():
        inicio = PLANTILLA.split("<<CUERPO>>")[0].count("\n") + 1
        salida = "\n".join((proc.stderr + proc.stdout).strip().splitlines()[-25:])
        return _respond(
            runtime,
            f"Error de compilación (el cuerpo empieza en la línea {inicio} del .tex). "
            f"Corregí el cuerpo y reintentá:\n{salida}",
        )
    return _respond(runtime, f"PDF creado: {pdf.name}", artifact={"pdf": str(pdf)})

@tool
def web_search(query: str, runtime: ToolRuntime[Context]) -> Command:
    """Busca información actual en la web. Devuelve resultados numerados con su URL.

    En tu respuesta final, citá las URLs de las fuentes que usaste.
    """
    resultados = _tavily.invoke({"query": query}).get("results", [])
    texto = "\n\n".join(
        f"[{i}] {r['title']}\nURL: {r['url']}\n{r['content']}"
        for i, r in enumerate(resultados, 1)
    ) or "Sin resultados."
    turno = runtime.context.turn
    fuentes = [{"turn": turno, "title": r["title"], "url": r["url"]} for r in resultados]
    return _respond(runtime, texto, artifact=fuentes, sources=fuentes)

@tool
def search_knowledge_base(query: str, runtime: ToolRuntime[Context]) -> Command:
    """Busca en la base de conocimiento local: documentos sobre LangChain y LangGraph
    (qué es cada uno, para qué sirven, en qué se diferencian y cuándo usar cada uno).

    Devuelve fragmentos numerados con su archivo de origen. Preferila a la búsqueda
    web para preguntas sobre estos temas.
    """
    chunks = _kb.similarity_search(query, k=4)
    texto = "\n\n".join(
        f"[{i}] Fuente: {c.metadata['source']}\n{c.page_content}"
        for i, c in enumerate(chunks, 1)
    ) or "Sin resultados."
    turno = runtime.context.turn
    fuentes = [
        {
            "turn": turno,
            "title": f"Base de conocimiento: {c.metadata['source']}",
            "url": f"rag/docs/{c.metadata['source']}",   # ruta local, no un link
        }
        for c in chunks
    ]
    reporte = [
        {"archivo": c.metadata["source"], "fragmento": c.page_content[:150].replace("\n", " ")}
        for c in chunks
    ]
    return _respond(runtime, texto, artifact=reporte, sources=fuentes)

@tool
def write_todos(todos: list[Todo], runtime: ToolRuntime[Context]) -> Command:
    """Escribe la lista de TODOs del plan, REEMPLAZANDO la anterior.

    Usala al empezar una tarea de varios pasos y cada vez que cambie el estado
    de un item (pending -> in_progress -> done). Enviá siempre la lista completa.
    """
    return _respond(runtime, f"TODOs actualizados ({len(todos)} items).", todos=todos)


@tool
def read_todos(runtime: ToolRuntime[Context]) -> str:
    """Lee la lista de TODOs actual, con el estado de cada item."""
    todos = runtime.state.get("todos", [])
    if not todos:
        return "No hay TODOs."
    return "\n".join(f"[{t['status']}] {t['task']}" for t in todos)


TOOLS: list = [web_search, search_knowledge_base, write_todos, read_todos, load_skill, create_pdf]
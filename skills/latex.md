---
description: Cómo escribir el cuerpo de un documento LaTeX (secciones, listas, tablas, fórmulas, enlaces) que compile sin errores con la herramienta create_pdf.
---
# Skill: LaTeX para create_pdf

## Qué escribís y qué agrega la herramienta
- Vos escribís **solo el cuerpo**: lo que iría entre `\begin{document}` y `\end{document}`.
- La herramienta ya agrega el preámbulo, el título (`\maketitle`) y la fecha. No repitas `\title` ni `\maketitle`.
- Ya están cargados: fontspec, babel (español), geometry, amsmath, booktabs y hyperref. **No uses** `\usepackage`, `\documentclass`, `\input`, `\include`, `\write`, `\catcode`, `\csname`, `\special` ni `^^`: la herramienta rechaza el documento.
- Escribí con caracteres normales (á, é, ñ, «», —, €). No uses comandos para los acentos.

## Estructura
- Secciones: `\section{...}`, `\subsection{...}`, `\subsubsection{...}`. Con asterisco (`\section*{...}`) no se numeran.
- Párrafos: separalos con una **línea en blanco**. No uses `\\` para separar párrafos.
- Negrita `\textbf{...}`, cursiva `\emph{...}`, código en línea `\texttt{...}`.
- Listas: `\begin{itemize} \item ... \end{itemize}` o `enumerate` (numerada). Cada `\item` va dentro de una lista.
- Código en bloque: `\begin{verbatim} ... \end{verbatim}` (adentro no se escapa nada; líneas de menos de 80 caracteres).
- Enlaces: `\url{https://...}` (adentro no se escapa nada).
- Fórmulas: en línea `$a^2 + b^2 = c^2$`; destacadas `\[ ... \]`; varias líneas `\begin{align*} ... \end{align*}`.

## No uses sintaxis markdown
Nada de `**negrita**`, `# títulos`, `` `código` `` ni `- ` para listas: en LaTeX aparecen tal cual o dan error.

## Caracteres especiales (escapalos en el texto)
| Escribir | Para mostrar |
|---|---|
| `\&` | & |
| `\%` | % |
| `\$` | $ |
| `\#` | # |
| `\_` | _ |
| `\{` y `\}` | { y } |
| `\textasciitilde{}` | ~ |
| `\textasciicircum{}` | ^ |
| `\textbackslash{}` | \ |

Ejemplos: `15\%`, `\$20`, `nombre\_archivo`, `Q\&A`.

## Tablas
- Una columna por letra: `l` izquierda, `c` centro, `r` derecha. Para texto largo usá `p{5cm}` (el ancho total no debe pasar de 16 cm).
- Cada fila termina en `\\`; el número de `&` por fila es igual al de columnas menos uno.
- Usá `\toprule`, `\midrule` y `\bottomrule` (no líneas `\hline`).

## Ejemplo completo de cuerpo
```latex
\section{Resumen}
Este informe presenta el \textbf{estado} del inventario. El stock bajó un 15\%
respecto del mes anterior.

\section{Inventario}
\begin{tabular}{lrr}
\toprule
\textbf{Producto} & \textbf{Precio (\$)} & \textbf{Stock} \\
\midrule
Cuaderno & 3 & 120 \\
Lapicera & 1 & 300 \\
\bottomrule
\end{tabular}

\subsection{Conclusiones}
\begin{itemize}
  \item Reponer lapiceras antes de fin de mes.
  \item El margen se calcula como $m = (p - c)/p$.
\end{itemize}

\section*{Fuentes}
\begin{itemize}
  \item \url{https://ejemplo.com/informe}
\end{itemize}
```

## Errores frecuentes
- `&` o `_` o `%` sin escapar fuera de una tabla o de `\url`.
- Falta un `\end{...}` o hay una lista dentro de otra más de 4 niveles.
- Filas de tabla con distinta cantidad de columnas.
- `\item` fuera de una lista.

## Si la compilación falla
1. Leé la primera línea del error que empieza con `!` y el número de línea.
2. Los números de línea cuentan el preámbulo: la herramienta te dice en qué línea empieza el cuerpo. Restá ese valor para ubicar el problema.
3. Corregí **solo** eso y reintentá (máximo 3 intentos).
# Paquete de envío — SoftwareX / Editorial Manager

Generado el 2026-07-31 desde `paper/softwarex/latex/`. Todo lo de aquí es
**derivado**: la fuente viva es `../latex/sycocode-softwarex.tex`. Si se toca
el manuscrito, recompilar y regenerar este directorio; no editar nada de aquí
a mano.

SoftwareX solo acepta envíos por Editorial Manager (no admite correo).

## Qué subir y con qué "item type"

| Fichero | Item type en Editorial Manager | Notas |
|---|---|---|
| `SycoCode_Manuscript.pdf` | Manuscript | 12 páginas, A4, 0 overfull boxes. |
| `source/sycocode-softwarex.tex` | LaTeX Source File | Fuente editable. |
| `source/refs.bib` | LaTeX Source File | Bibliografía. **No editar a mano**: se genera desde los JSON de las APIs (ver `../references_verification.md`). |
| `source/elsarticle.cls` | LaTeX Source File | Clase de la plantilla oficial, sin modificar. |
| `source/elsarticle-num.bst` | LaTeX Source File | Estilo bibliográfico de la plantilla, sin modificar. |
| `Fig1.pdf` | Figure | **Un fichero por figura**, vectorial. Es la única figura del artículo. |
| `source/Fig1_architecture.tex` | LaTeX Source File | Fuente de la figura (mismo cuerpo `tikzpicture` que el manuscrito). |
| `GraphicalAbstract.pdf` | Graphical Abstract | 13 × 5 cm exactos, vectorial. |
| `source/GraphicalAbstract.tex` | LaTeX Source File | Fuente del graphical abstract. |
| `SycoCode_Highlights.txt` | Highlights | Fichero aparte y editable, con "Highlights" en el nombre. |

**Tablas**: van dentro del manuscrito como texto editable (`tabular`), no como
imágenes — que es lo que pide la guía. No se suben aparte.

## Comprobado antes de empaquetar

- El directorio `source/` compila **solo**, en una copia limpia fuera del
  repo: `latexmk -pdf sycocode-softwarex.tex` → rc 0, 0 overfull boxes,
  0 referencias/citas sin resolver; `latexmk -pdf Fig1_architecture.tex` → rc 0.
- `Fig1.pdf` y `GraphicalAbstract.pdf` son **vector puro**: `pdfimages -list`
  no devuelve ninguna imagen rasterizada en ninguno de los dos, y las fuentes
  van embebidas y subsetadas (Type 1).
- El graphical abstract mide 368.5 × 141.7 pt = **13 × 5 cm exactos**, que es
  el tamaño de lectura que pide Elsevier. Al ser vectorial, rasterizado a
  150 dpi da 1994 × 767 px, por encima del mínimo de 1328 × 531 (ancho × alto).
- Recuento de palabras bajo la regla de SoftwareX (límite 3.000: excluye
  título, autores, afiliaciones, referencias y tablas de metadatos; **incluye**
  abstract, texto corrido, pies y notas): **2.769**. Margen: 231 palabras.
- Highlights: 5 viñetas, longitudes 74 / 76 / 75 / 74 / 81 caracteres con
  espacios (límite 85), sin acrónimos.
- Declaración de IA generativa: título de la política de **revistas** de
  Elsevier ("...in the manuscript preparation process"), colocada al final,
  inmediatamente antes de las referencias.

## Lo que queda fuera del paquete

1. **DOI de archivo (Zenodo).** Es lo único que sigue bloqueando el envío
   completo: C2 pide un enlace permanente y §Data availability tiene el hueco
   marcado para el identificador persistente. Requiere vincular la cuenta de
   Zenodo con GitHub a mano (OAuth en el navegador) ANTES de crear la release,
   porque Zenodo solo captura releases posteriores a la vinculación.
2. **Cover letter**: la guía no la exige. Sin decidir.

Resueltos el 2026-07-31: repositorio público, `LICENSE.txt` en la raíz,
graphical abstract incluido.

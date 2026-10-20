---
name: "Retained project figures"
description: "The common-project workbench's retained-capture extension."
colors:
  accent: "#45bccb"
  background: "#141c1c"
  panel: "#1b2425"
  border: "#354243"
  ink: "#e1ebec"
  muted: "#b4bdbe"
  light-accent: "#0d7c80"
  light-background: "#f6f8f8"
  light-panel: "#ffffff"
  light-border: "#dde5e6"
  light-ink: "#17262a"
  light-muted: "#5b6d70"
typography:
  body:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "16px"
  heading:
    fontFamily: "Cinzel, serif"
rounded:
  control: "8px"
spacing:
  small: "8px"
  actions: "12px"
  dialog: "16px"
  figure: "24px"
  section: "32px"
components:
  button:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "10px"
  file-input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "10px"
---

# Retained project figures

Scope: the existing common-project workbench, Operate. Task1061 extends its capture and native-document workflow; it preserves the complete Photos/Vector clients and inherited visual world.

## Direction contract

THESIS: keep a diagram capture, its selection and source together beside the project's native results.

OWN-WORLD: retain the teal/charcoal or existing light theme, Cinzel headings, Source Sans3 fields and native form controls.

STORY: import and inspect a retained capture, then explicitly make a Vector or Layers copy; earlier captures stay available.

FIRST VIEWPORT: the existing module controls and project navigation remain; the selected project contains its import control, captures and native result links. Mobile uses the existing single column.

FORM: extend the incumbent workbench; no replacement world or new form-selection seed. The signature interaction is local full-size capture inspection while engines remain OFF.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Overview

**Creative North Star: "The Common Project Workbench"**

This Operate surface keeps a retained diagram capture beside the project's existing Photos and Vector results. The addition follows the current workbench, including its teal/charcoal and light themes, Cinzel headings, Source Sans 3 controls and native form elements. It does not establish a replacement visual world.

The original direction contract above is retained. Its finish obligation is discharged for this narrow extension by the scoped record here, the companion `.impeccable/surfaces/figures.json`, and the finish review's `ship` verdict. Root `PRODUCT.md`, `DESIGN.md` and `.impeccable/design.json` describe the older photo-library/lightbox surface; they remain unchanged and do not prescribe this workbench's type or layout.

**Key Characteristics:**

- Retained image, complete diagram source and capture identity stay together.
- Inspection works locally while both destination modules are off.
- Vector and Layers copies explicitly use the retained raster image.
- Existing module controls, project navigation and transfer forms remain available.

## Colors

The restrained palette uses one teal accent with tonal charcoal surfaces, or the existing pale background and white controls in the light theme. The frontmatter records the workbench's actual variables; these values come from `daguerre_hoard/studio_ui/studio.css`.

### Primary

Teal carries links, hover borders and keyboard focus. The light theme uses its darker teal variant. Creation actions use the incumbent neutral button treatment; they do not acquire a new promotional hierarchy.

### Neutral

Background, panel, border, ink and muted roles follow the selected theme. The capture's own white canvas and diagram colors are image content; the workbench does not recolor them. The inspector uses the same background and ink roles as the page.

**The Source Theme Rule.** Extend the workbench's theme variables and native controls; preserve the retained image's pixels.

## Typography

Cinzel supplies the inherited heading voice; Source Sans 3 supplies body text, buttons and file inputs. Controls inherit the body role rather than introducing a separate display scale. Capture captions use ordinary body text and include the title and revision, followed by page and state identifiers when present. Long captions can wrap anywhere.

This record does not promote the inherited (22px) main heading or native form labels into a new project-wide type scale. The root lightbox's Plus Jakarta Sans record belongs to a different surface.

## Layout

The existing main column is centered within a maximum width of (1140px), with (28px) padding. The workbench places (240px) project navigation beside the selected project with a (32px) gap. At the existing (700px) breakpoint it becomes a single column and main padding becomes (20px); project navigation precedes the selected project's contents.

The selected project starts with its heading and native `.vfigure` file input. Each capture follows the explanatory copy, with its contained image, identity caption and wrapping action row. Existing photo/vector transfer forms and native result links remain below. Figures use the figure spacing role for margins and bottom separation; a thin theme divider separates them from following content. Action rows wrap with the actions spacing role. The project column can shrink, and import controls stay within its width.

The local inspector occupies the viewport with (16px) outer clearance and the dialog spacing role as inner padding. Its first row contains Cerrar, Ajustar, Tamaño real and Ampliar 2×. The remaining space is a scrollable image region; on narrow screens the controls wrap and the enlarged image scrolls inside that region. The supplied (1440px) and (390px) captures show this adaptation without page overflow.

## Elevation & Depth

The added workbench content uses flat tonal surfaces, thin borders and whitespace. The native modal inspector dims the page with a translucent black backdrop (`#000b`); it adds no decorative shadow. The shared Faustus launcher and any depth inside retained diagram imagery remain outside this extension's component rules.

## Shapes

Buttons and file inputs keep the gently rounded control shape. Captures are contained rather than cropped, with an inline maximum image height of (240px). Their image button removes its own fill, border and padding so the retained capture supplies the visible content. The inspector retains a simple bordered rectangle; the image can exceed its scroll region at actual size and 2×.

## Components

### Capture import

The native file input accepts `.vfigure` or JSON and imports into the selected project. Its label is above it, with the small spacing role between label and control. The input disables while importing, then resets for the next selection. Errors use the existing inline error area; import does not erase the separate new-project name draft.

### Retained capture and actions

The caption identifies the retained revision and selection context. Clicking the image or Ampliar figura opens the same inspector. Descargar figura y fuente downloads the retained `.vfigure` package. Abrir diagrama de origen appears only when the stored origin supplies a usable HTTP(S) link; it opens on an explicit click. Import and inspection do not fetch or regenerate that origin.

**The Retained Capture Rule.** Keep the exact PNG and complete diagram source together; older captures remain available when a different revision or selection is imported.

### Inspector

The native modal dialog opens at actual image size. Ajustar constrains both image dimensions to the viewing area; Tamaño real uses the PNG's natural width; Ampliar 2× uses twice that width. The image region is keyboard focusable and scrollable. Cerrar and the native Escape behavior close it; closing restores focus to the connected opener. The workbench's visible focus ring uses an accent outline (2px) with offset (3px).

### Native copy actions and results

Crear en Vector and Crear en Capas remain beside the capture. Each is disabled while its destination module is off or its own request is busy, with reduced opacity (0.55). Creation changes the label to Creando… and exposes the busy state. The module controls above the project remain the explicit way to activate a destination.

Vector receives a native document containing the retained image; Layers receives a native layered document containing the same raster. The complete diagram source remains with the capture. Result links and revisions remain in the project; a Layers result also offers Descargar documento de Capas and Abrir editor de Capas. Existing retained-result downloads remain available.

**The Explicit Copy Rule.** Describe these actions as copies using the image; do not imply reconstruction of the diagram's editable semantic objects or structural layers.

## Do's and Don'ts

### Do:

- **Do** keep capture identity, source download, inspection and explicit copy actions together.
- **Do** allow retained import, download, reopening and inspection while destination modules remain off.
- **Do** preserve both themes, the wrapping action row and the inspector's local scroll region.
- **Do** preserve the complete Photos/Vector clients and the existing project and transfer functions.

### Don't:

- **Don't** present raster copies as semantic diagram reconstruction.
- **Don't** fetch the origin or activate a destination as a side effect of importing or inspecting a capture.
- **Don't** turn the scoped finish verdict into certification of every inherited surface or native editor.

### Evidence and scope

The finish review at `D:/LocalAI/research-inbox/expansiones-fusiones-20261020/daguerre1061-finish.txt` returns `ship` for the added flow. Documentation inspected all eight supplied captures under its `qa1061/` directory: four figure/theme/width views, two inspector views and two native-result project views. They show synthetic test projects and the same retained test image; they are QA evidence, not new shipping raster assets.

The author's `cold-results.json` and `cold-native.json` report exact complete-source/PNG retention, atomic invalid import, both modules off, source download, keyboard inspection, draft preservation, deduplication, reopening, no browser errors and no page overflow across both widths and themes. `native-target-results.json` reports exact source and pixels through both native copies and reopening; `native-ui-result.json` reports two browser copy actions, no errors/overflow and modules off at completion. These receipts were read for this record; the documenter did not repeat their tests or start applications. Full-suite validation and integration belong to the task owner.

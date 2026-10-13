---
name: "Daguerre's Hoard"
description: "The incumbent local photo-library interface and its image-editor action extension."
colors:
  accent: "#45bccb"
  accent-strong: "#65c7d4"
  accent-soft: "rgba(69, 188, 203, 0.14)"
  accent-ink: "#131a1b"
  deep: "#141c1c"
  surface: "#1b2425"
  elevated: "#242f30"
  border: "#354243"
  border-hover: "#57696b"
  text: "#e1ebec"
  text-muted: "#b4bdbe"
  text-dim: "#9ba5a6"
  danger: "#e2685a"
  warning: "#d4a843"
  warning-soft: "rgba(212, 168, 67, 0.16)"
  light-accent: "#12a4a8"
  light-accent-strong: "#0d7c80"
  light-accent-soft: "#12a4a81a"
  light-deep: "#f6f8f8"
  light-surface: "#ffffff"
  light-sidebar: "#0f2426"
  light-text: "#17262a"
  light-text-muted: "#5b6d70"
  light-border: "#dde5e6"
typography:
  body:
    fontFamily: "Plus Jakarta Sans Variable, Source Sans 3, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Noto Sans, Liberation Sans, Arial, sans-serif"
  title:
    fontSize: "15px"
    fontWeight: 600
  button:
    fontSize: "13.5px"
    fontWeight: 600
  metadata:
    fontSize: "13px"
  caption:
    fontSize: "13.5px"
    lineHeight: 1.5
  auxiliary:
    fontSize: "12px"
rounded:
  small: "6px"
  control: "8px"
  media: "10px"
  light-container: "12px"
  pill: "999px"
spacing:
  tight: "4px"
  small: "8px"
  medium: "12px"
  control: "16px"
  section: "18px"
  panel: "20px"
  page: "28px"
components:
  button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  button-hover:
    backgroundColor: "{colors.elevated}"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  button-primary-hover:
    backgroundColor: "{colors.accent-strong}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "9px 12px"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.media}"
  warning-badge:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.warning}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  image-action:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
    width: "100%"
---

# Design System: Daguerre's Hoard

## Overview

**Creative North Star: "The Local Photo Library"**

Daguerre uses a compact photo-library interface: dark teal surfaces by default, an optional light palette, one teal accent and a quiet sans-serif reading voice. Photographs carry the visual weight; the sidebar, thumbnail grid and metadata panel provide continuity around them. This records the incumbent interface rather than introducing a new visual identity.

The image-editor extension belongs to the existing lightbox. Its copy creation, development, preview, download and full-editor controls use the same buttons, fields and panel surfaces. The complete incorporated desktop editors are separate native egui interfaces; their interfaces remain visually intact apart from Daguerre branding. Their internal tokens are not specified by this browser design system.

**Key Characteristics:**

- Photo-led library with compact navigation and metadata.
- Dark teal tonal layers with an optional light-surface theme.
- Plus Jakarta Sans for browser reading and controls.
- Existing lightbox actions extended with copy creation and result controls.

## Colors

The palette pairs a cyan-teal accent with low-chroma teal neutrals; the frontmatter records the actual source values. The sidecar's eight-step tonal ramps are synthesized swatch previews, not additional colors prescribed for the application.

### Primary

- **Teal accent:** active media selection, focus, exposure sliders and primary buttons. The strong variant is the primary-button hover color; the soft variant supports selected containers.
- **Accent ink:** dark text on default-theme primary buttons. Light-theme primary buttons use white.
- **Light teal accent:** the optional light theme retains its original teal links and selected sidebar rows.

### Neutral

- **Deep / surface / elevated:** library background, fixed navigation and panel surfaces, then hover and selected navigation layers.
- **Border / border-hover:** restrained component boundaries and interactive hover emphasis.
- **Text / text-muted / text-dim:** content and controls, supporting metadata, then field placeholders.
- **Light deep / surface / sidebar:** pale page background, white content surfaces and the original dark-teal sidebar.
- **Light text / text-muted / border:** the optional light theme's content, metadata and dividers.

Danger and warning colors communicate operation errors and notices. They are semantic states rather than additional decorative accents. Theme rules follow the CSS cascade: shared family chrome remains authoritative where the light theme does not explicitly override it.

**The Source Theme Rule.** Resolve colors through the existing theme variables and their final overrides; do not substitute a new palette when extending the library.

## Typography

**Body Font:** Plus Jakarta Sans Variable, followed by the shared Hoard sans-serif fallback stack recorded above.

**Character:** compact and readable, with semibold controls and muted metadata. This is a working photo library, without a separate promotional display hierarchy.

### Hierarchy

- **Title:** the final topbar uses the title role; the lightbox filename is separately set to (16px).
- **Button:** semibold action labels use the button role; small and large variants adjust the existing control density.
- **Metadata:** compact key/value rows use the metadata role, with muted keys and right-aligned values.
- **Caption:** descriptive photo text uses the caption role.
- **Auxiliary:** result links, supporting notes and exposure labels use the auxiliary role.

The inherited brand serif stack is a source observation, not a new display-type prescription. No new label or uppercase eyebrow role is established here.

## Layout

The app fills the viewport with a fixed-width sidebar and a flexible main column. The default sidebar is (220px), the shared header is (64px), and the main content uses (24px 28px 60px) padding. Thumbnails form an auto-fill square grid with a minimum column width of (180px) and (12px) gaps. Albums use a related minimum column width of (200px).

The lightbox preserves the large contained image beside a (340px) details panel with (20px) padding and independent vertical scrolling. Image actions follow metadata, Explorer access where available and the existing photo edits. They do not displace the first image-and-details view. Result controls remain in the same panel. This placement is the current lightbox extension, not a required composition for every future screen.

The observed responsive breakpoint is (720px): the sidebar narrows to (72px) and navigation labels disappear. The lightbox panel keeps its fixed width, so it dominates a narrow viewport; the reviewed mobile action group remains reachable in that scrolling panel. This records current behavior, not a claim that every inherited layout has been adapted for mobile.

## Elevation & Depth

Default library cards are flat, distinguished by tonal surfaces and thin borders. Light-theme cards restore the original soft shadow. Photographic overlays use translucent black for readable controls; the lightbox dims the library behind the main image. Depth belongs to image viewing and state feedback rather than additional decorative panels.

### Shadow Vocabulary

- **Light card:** the original two-layer ambient shadow is retained for light-theme cards; its exact value is in the sidecar.
- **Thumbnail hover:** a slight upward translation and soft shadow indicate an actionable photo.
- **Lightbox image:** a deeper shadow separates the contained image from the dimmed library.

**The Flat Library Rule.** Default library cards use tonal layering and borders; preserve the light-theme and photographic shadow exceptions already present.

## Shapes

Controls use the shared gently rounded control radius; thumbnail and default card containers use the media radius. Light-theme containers retain the larger light-container radius. Status badges and zoom controls use pill silhouettes. Media is clipped within its own container; the large lightbox image remains contained rather than cropped. Borders stay thin, with accent or hover-color changes indicating interaction.

## Components

### Buttons

Compact, semibold controls carry the existing action vocabulary. Standard buttons have a minimum height of (36px); buttons inside the image-editor action group have a minimum height of (44px). Block actions fill the panel width, center their text and have (12px) top spacing. Neutral hover uses the elevated surface and hover border; primary hover uses the stronger accent. Disabled actions reduce opacity to (0.5) and use a not-allowed cursor. Keyboard button focus uses a (2px) accent outline with (1px) offset.

### Inputs / Fields

Fields use a bordered surface and the shared control radius. The final shared-family override replaces the earlier input outline with an accent border on focus. Placeholders use the dim text color. Search fields receive more padding than compact metadata fields. The exposure range stays a native range input with the theme accent; its label shows the current signed EV value.

### Navigation

Default sidebar rows are (40px) high. Hover and active rows share an elevated surface; the active icon carries the accent. Light-theme active rows retain their filled teal treatment and white text. Icon-only navigation on narrow screens follows the existing sidebar behavior.

### Chips / Tags

Small rounded badges communicate status or media context. Warning badges use the semantic warning pair. Frame chips are miniature photo containers with an accent border on the active frame. These are functional labels, not display headings.

### Cards / Containers

Cards share a thin theme border and the current theme's container radius. Default cards have no shadow; the light theme restores the ambient card shadow. Photo thumbnails crop to square, while album covers use a (4:3) frame. Metadata rows have bottom dividers and wrap long values.

### Image-editor action group

This is a local extension of the existing details panel. A top divider and (14px) top padding separate it from prior edits; stacked neutral actions create a layered copy or develop a copy. Development shows an exposure range from (-3 to +3 EV) in (0.1 EV) steps. Busy state changes both action labels to the working message and prevents concurrent copy operations. Availability disables each engine's action and supplies an unavailable title; errors appear as inline danger text.

The original-preservation note stays next to the actions. A successful result adds a full-editor button, available output or preview images, an editable-project download when a native format exists, and an exported-image link. Preview images are contained with a maximum height of (180px), not cropped thumbnails. Full-editor opening uses the result's artifact and engine; native tools share that editor session through the product implementation. This browser record does not prescribe a restyle of the full incorporated editor.

**The Copy Workflow Rule.** Keep copy creation, result preview, editable download and full-editor opening explicit, with the indexed original-preservation note beside the actions.

## Do's and Don'ts

### Do:

- **Do** extend the existing theme, sidebar, grid and lightbox vocabulary.
- **Do** preserve the independently scrollable details panel and the image-editor action group's (44px) minimum button height.
- **Do** use contained previews for editing results and keep copy/result/editor actions explicit.
- **Do** preserve the optional light theme and the native desktop editors' complete incorporated interfaces.

### Don't:

- **Don't** introduce a new visual world for the image-editor extension.
- **Don't** present a created copy as a modification of the indexed original.
- **Don't** promote inherited uppercase section labels or unresolved typography/motion findings into rules for new surfaces.
- **Don't** interpret the scoped image-action visual review as a universal interface audit or a restyle of native egui editors.

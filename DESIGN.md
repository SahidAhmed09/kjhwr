---
name: Wind day-ahead
description: A morning market report for GB wind: ruled tables, one plot per band of the sheet, red for the costly side.
colors:
  page: "#ece4d8"
  sheet: "#fbf8f3"
  sheet-2: "#f3eee5"
  ink: "#1d1c19"
  ink-2: "#4f4b44"
  ink-3: "#6b665c"
  rule: "#d8d0c1"
  over-forecast: "#e34948"
  under-forecast: "#2a78d6"
  neutral-mark: "#8d877b"
  dark-page: "#0f0e0c"
  dark-sheet: "#1b1a17"
  dark-sheet-2: "#242218"
  dark-ink: "#f0ece3"
  dark-ink-2: "#c9c3b5"
  dark-ink-3: "#a39d8f"
  dark-rule: "#38342d"
  dark-over-forecast: "#e66767"
  dark-under-forecast: "#3987e5"
  dark-neutral-mark: "#8a8476"
typography:
  brand:
    fontFamily: "Libre Franklin Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "1.4375rem"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "-0.012em"
  headline:
    fontFamily: "Libre Franklin Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 700
    lineHeight: 1.18
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Libre Franklin Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "1.1875rem"
    fontWeight: 700
    lineHeight: 1.25
  body:
    fontFamily: "Libre Franklin Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.45
  figure:
    fontFamily: "Libre Franklin Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 700
    fontFeature: "tnum"
  label:
    fontFamily: "Libre Franklin Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 600
  axis:
    fontFamily: "Libre Franklin Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    fontFeature: "tnum"
rounded:
  control: "2px"
  mark: "4px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "40px"
  segmented-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.control}"
    height: "40px"
  field:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 10px"
    height: "40px"
  tile-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.control}"
    width: "36px"
  tooltip:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.control}"
    padding: "9px 12px 10px"
---

# Design System: Wind day-ahead

## Overview

**Creative North Star: "The Morning Market Report"**

The product is a printed sheet that happens to be live: a warm newsprint page laid on a darker desk, ruled in hairlines, with a double rule under the masthead. Figures live in ruled tables, not tiles. Each chart sits directly on the sheet with one rule above it and no container around it. One grotesque, Libre Franklin, carries every role from the 23px masthead to 12px axis labels, so the page reads like one typeset document.

Colour is rationed to meaning. Ink and paper do everything except one job: red and blue mark the sign of the forecast error, and nowhere else. Red is over-forecast, the costly side for a buyer; blue is under-forecast. Neither is used for emphasis, links, focus or selection.

The tone is a trader's desk before gate closure: dense, quiet, plain-spoken. Sentences are sentence case; metric jargon always arrives with a plain gloss.

**Key Characteristics:**
- Paper, ink and hairlines; red and blue reserved for error sign only.
- One family (Libre Franklin Variable), tabular figures wherever numbers align in columns.
- Tables carry the facts; charts have no card chrome; a table sits one click behind every chart.
- Squared 2px controls, ink-filled for the pressed or selected state.
- Dark mode is its own set of steps on a warm black sheet, not an inversion.

## Colors

A restrained palette: warm neutrals plus two reserved error inks.

### Primary
- **Ink** (#1d1c19; dark #f0ece3): all text, the forecast line, rules that matter, and every selected or pressed state (filled ink with sheet-coloured text).

### Secondary
- **Over-forecast red** (#e34948; dark #e66767): the forecast was too high, so wind did not arrive and the buyer bought too little. Used for bars, key swatches and tooltip keys only.
- **Under-forecast blue** (#2a78d6; dark #3987e5): the forecast was too low. Same limited use.

### Neutral
- **Newsprint sheet** (#fbf8f3; dark #1b1a17): the page surface and every chart ground.
- **Second sheet** (#f3eee5; dark #242218): hover wash, loading bars, the invalid-field wash.
- **Desk** (#ece4d8; dark #0f0e0c): the page plane visible beside the sheet on wide screens.
- **Ink 2 / Ink 3** (#4f4b44 / #6b665c; dark #c9c3b5 / #a39d8f): secondary and muted text; both clear 4.5:1 on the sheet in both themes.
- **Rule** (#d8d0c1; dark #38342d): hairlines, gridlines, table row separators.
- **Neutral mark** (#8d877b; dark #8a8476): bars that carry no sign (typical miss).

### Named Rules
**The Error-Sign Rule.** Red and blue appear only as the sign of forecast minus actual. Never use them for links, focus, emphasis or status.
**The Words-Beside-Colour Rule.** Red's meaning is stated in words beside the day strip on every view, and sign is also carried by direction (bars above or below the zero line). Colour is never the only channel; an opt-in Patterns mode adds 45° and 135° hatching.
**The Mark-Not-Text Rule.** Data colours fill marks and key swatches. Text stays in ink tokens.

## Typography

**Display Font:** Libre Franklin Variable (with Segoe UI, system-ui, sans-serif)
**Body Font:** Libre Franklin Variable (same)
**Label/Mono Font:** none; figures use the same face with `tnum`.

**Character:** A Franklin-lineage grotesque, the face of financial-press data pages. One family, with weight and size doing all the hierarchy work.

### Hierarchy
- **Brand** (800, 1.4375rem, 1.15, -0.012em): the masthead name only.
- **Headline** (700, 1.75rem, 1.18, -0.015em, balanced; 1.4375rem under 720px): the one plain-language sentence per view.
- **Title** (700, 1.1875rem, 1.25): chart and section headings.
- **Body** (400, 1rem, 1.45): table notes, controls; running prose is 0.9375rem at 76ch.
- **Figure** (700, 1.125rem, tabular): values in the report table.
- **Label** (600, 0.8125rem): control labels and column heads (0.75rem in tables).
- **Axis** (400, 12px, tabular): chart ticks and direct labels.

### Named Rules
**The Tabular-In-Columns Rule.** Tabular figures in every column and axis; proportional figures in headlines.
**The Number-Keeps-Its-Unit Rule.** A value and its unit are joined by a non-breaking space so a line never splits "2,042" from "MW".

## Layout

A single sheet, 1240px maximum, with 32px side padding (16px under 720px) on the desk plane. Vertical order is fixed across views: masthead with view tabs, one controls row, the day strip, the colour key, then content. All filters live in that single row above the content and scope everything below.

Content on desktop is a 5/7 split row (headline and basis on the left, ruled figures table on the right) followed by full-width chart frames; the accuracy view puts four charts in a two-column grid that collapses to one column at 1000px. Under 720px the figures table becomes a two-column grid per row with the note spanning beneath. Spacing rhythm is 8 / 12 / 16 / 24 / 32px, with 32px above each chart frame. Tables scroll sideways inside their own region on narrow screens.

Previous data stays on screen while a refetch runs: the view dims to 55% and the controls row says "Updating…". No skeleton replaces content that is already there.

## Elevation & Depth

Flat. Depth comes from tone (sheet on desk) and rules (hairline, 2px, and one 4px double rule under the masthead). There are no shadows on the sheet or controls. The one shadow is the tooltip, which floats above everything and needs separation (`box-shadow: 0 2px 10px rgba(0,0,0,0.28)`).

### Named Rules
**The Rules-Not-Boxes Rule.** Separate with a rule and space. No card chrome around charts or tables, and never nest containers.

## Shapes

Squared. Controls and the tooltip take a 2px radius; data marks take a 4px rounded data end with a square base on the baseline, 24px maximum bar thickness, a 2px gap between touching bars and a 2px sheet-coloured ring around dots. Lines are 2px with round joins. Gridlines are 1px solid and recessive.

## Components

### Buttons and toggles
- **Shape:** squared, 2px radius, 1px ink border, 40px tall (44px on coarse pointers).
- **Default:** transparent with ink text; hover washes to the second sheet.
- **Pressed / selected:** ink fill, sheet-coloured text. This is the only selected-state treatment.
- **Disabled:** rule-coloured border and muted text.
- Small preference toggles (Dark mode, Patterns) are 32px with a rule border and the same ink fill when on.

### Segmented control
Joined buttons with shared borders (Chart / Table; 09:20 / 09:50). Pressed segment is ink-filled.

### Inputs
- **Style:** 1px ink border, sheet ground, 2px radius, tabular figures, 40px tall.
- **Invalid:** 2px border on the second-sheet wash, with a plain sentence beneath. Red is not used for errors.

### Day strip
One 36px tile per decision date. A centred zero line, a 16px bar up (red, over-forecast) or down (blue, under-forecast) scaled to the largest daily error, the date number and a weekday initial. The selected tile is ink-filled with sheet text. Tiles are one roving tab stop; arrow keys, Home and End move the selection.

### Report table
Bold row labels, a bold tabular value, and a muted plain-language note, ruled with a 2px top rule and hairline row dividers. This replaces metric tiles.

### Chart frame
Title, one plain sentence on what to look for, a Chart / Table switch, then the legend (whenever there are two or more series or colours), then the chart. Charts are focusable; arrow keys read each mark; the tooltip and a live region both announce it.

### Tooltip
Ink ground, sheet text, values first and labels after, a short key glyph per row that mirrors the mark, an optional muted note. Follows the pointer or the keyboard focus and clears on scroll.

### Navigation
Two text tabs, Decision and Accuracy; the current tab is bold with a 4px ink underline that sits on the double rule.

## Do's and Don'ts

### Do:
- **Do** use red only for over-forecast and blue only for under-forecast, and say so in words wherever they appear.
- **Do** put a table behind every chart and a legend on every chart with two or more series or colours.
- **Do** keep numbers joined to their units with a non-breaking space and use tabular figures in columns.
- **Do** keep the previous data visible, dimmed, while the next data loads.
- **Do** pair every delivery-day figure with the cut-off it was known at; never show hindsight unlabelled.

### Don't:
- **Don't** wrap charts or tables in cards, and don't nest containers.
- **Don't** use red or blue for emphasis, links, selection or focus; selection is ink-filled.
- **Don't** put chromatic colour on text; colour belongs on the mark beside it.
- **Don't** add shadows to the sheet or controls.
- **Don't** replace the one-sentence headline with a hero number tile.
- **Don't** show or imply data that is not in the API response; missing stays missing.

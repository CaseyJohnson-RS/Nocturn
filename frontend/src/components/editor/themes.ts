/**
 * CodeMirror themes — dark (obsidian-like) and light variants.
 *
 * Each export provides an EditorView.theme() + HighlightStyle pair.
 */

import { EditorView } from "@codemirror/view";
import { HighlightStyle } from "@codemirror/language";
import { tags } from "@lezer/highlight";

// ---------------------------------------------------------------------------
// Dark theme (existing obsidian-like)
// ---------------------------------------------------------------------------

export const darkEditorTheme = EditorView.theme(
  {
    "&": {
      color: "oklch(0.9 0 0)",
      backgroundColor: "transparent",
    },
    ".cm-content": {
      caretColor: "oklch(0.7 0.15 250)",
      fontFamily: "'Inter', system-ui, sans-serif",
    },
    ".cm-cursor, .cm-dropCursor": {
      borderLeftColor: "oklch(0.7 0.15 250)",
      borderLeftWidth: "2px",
    },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection":
      {
        backgroundColor: "oklch(0.7 0.15 250 / 0.2)",
      },
    ".cm-activeLine": {
      backgroundColor: "oklch(0.2 0 0 / 0.3)",
    },
    ".cm-gutters": {
      display: "none",
    },
    ".cm-foldPlaceholder": {
      backgroundColor: "oklch(0.25 0 0)",
      border: "none",
      color: "oklch(0.6 0 0)",
    },
  },
  { dark: true },
);

export const darkHighlightStyle = HighlightStyle.define([
  { tag: tags.heading1, fontSize: "1.8em", fontWeight: "700" },
  { tag: tags.heading2, fontSize: "1.5em", fontWeight: "600" },
  { tag: tags.heading3, fontSize: "1.25em", fontWeight: "600" },
  { tag: tags.heading4, fontSize: "1.1em", fontWeight: "600" },
  { tag: tags.strong, fontWeight: "700" },
  { tag: tags.emphasis, fontStyle: "italic" },
  { tag: tags.strikethrough, textDecoration: "line-through" },
  { tag: tags.link, color: "oklch(0.7 0.15 250)" },
  { tag: tags.url, color: "oklch(0.5 0 0)" },
  { tag: tags.monospace, color: "oklch(0.75 0.1 150)", fontFamily: "monospace" },
  { tag: tags.quote, color: "oklch(0.65 0 0)", fontStyle: "italic" },
  { tag: tags.keyword, color: "oklch(0.7 0.15 310)" },
  { tag: tags.comment, color: "oklch(0.45 0 0)" },
  { tag: tags.meta, color: "oklch(0.5 0 0)" },
  { tag: tags.processingInstruction, color: "oklch(0.5 0.1 50)" },
]);

// ---------------------------------------------------------------------------
// Light theme
// ---------------------------------------------------------------------------

export const lightEditorTheme = EditorView.theme(
  {
    "&": {
      color: "oklch(0.2 0 0)",
      backgroundColor: "transparent",
    },
    ".cm-content": {
      caretColor: "oklch(0.45 0.2 250)",
      fontFamily: "'Inter', system-ui, sans-serif",
    },
    ".cm-cursor, .cm-dropCursor": {
      borderLeftColor: "oklch(0.45 0.2 250)",
      borderLeftWidth: "2px",
    },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection":
      {
        backgroundColor: "oklch(0.45 0.2 250 / 0.15)",
      },
    ".cm-activeLine": {
      backgroundColor: "oklch(0.95 0 0 / 0.5)",
    },
    ".cm-gutters": {
      display: "none",
    },
    ".cm-foldPlaceholder": {
      backgroundColor: "oklch(0.92 0 0)",
      border: "none",
      color: "oklch(0.5 0 0)",
    },
  },
  { dark: false },
);

export const lightHighlightStyle = HighlightStyle.define([
  { tag: tags.heading1, fontSize: "1.8em", fontWeight: "700" },
  { tag: tags.heading2, fontSize: "1.5em", fontWeight: "600" },
  { tag: tags.heading3, fontSize: "1.25em", fontWeight: "600" },
  { tag: tags.heading4, fontSize: "1.1em", fontWeight: "600" },
  { tag: tags.strong, fontWeight: "700" },
  { tag: tags.emphasis, fontStyle: "italic" },
  { tag: tags.strikethrough, textDecoration: "line-through" },
  { tag: tags.link, color: "oklch(0.45 0.2 250)" },
  { tag: tags.url, color: "oklch(0.55 0 0)" },
  { tag: tags.monospace, color: "oklch(0.4 0.15 150)", fontFamily: "monospace" },
  { tag: tags.quote, color: "oklch(0.45 0 0)", fontStyle: "italic" },
  { tag: tags.keyword, color: "oklch(0.5 0.2 310)" },
  { tag: tags.comment, color: "oklch(0.6 0 0)" },
  { tag: tags.meta, color: "oklch(0.55 0 0)" },
  { tag: tags.processingInstruction, color: "oklch(0.5 0.15 50)" },
]);

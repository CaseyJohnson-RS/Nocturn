/**
 * Live Preview extension for CodeMirror.
 *
 * Hides Markdown formatting marks (e.g. `#`, `**`, `` ` ``) on lines
 * that do NOT contain the cursor, giving an Obsidian-like editing
 * experience where you see rendered output until you click into a line.
 */

import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import { syntaxTree } from "@codemirror/language";
import type { Range } from "@codemirror/state";

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */

/** Marks that can be hidden with a simple `Decoration.replace`. */
const INLINE_MARKS = new Set([
  "EmphasisMark", // * _ ** __
  "StrikethroughMark", // ~~
  "CodeMark", // ` (inline only – we skip FencedCode)
  "LinkMark", // [ ] ( )
  "URL", // the href inside [text](URL)
]);

const hideDeco = Decoration.replace({});

/* ------------------------------------------------------------------ */
/*  Decoration builder                                                */
/* ------------------------------------------------------------------ */

function buildDecorations(view: EditorView): DecorationSet {
  const { state } = view;
  const decorations: Range<Decoration>[] = [];

  // Collect every line number that has a cursor or selection.
  const activeLines = new Set<number>();
  for (const sel of state.selection.ranges) {
    const fromLine = state.doc.lineAt(sel.from).number;
    const toLine = state.doc.lineAt(sel.to).number;
    for (let n = fromLine; n <= toLine; n++) activeLines.add(n);
  }

  syntaxTree(state).iterate({
    enter(node) {
      // Never touch fenced / indented code blocks.
      if (node.name === "FencedCode" || node.name === "CodeBlock") {
        return false; // skip children
      }

      // Don't touch the line the cursor is on.
      const line = state.doc.lineAt(node.from).number;
      if (activeLines.has(line)) return;

      // --- Heading marks: hide `# ` including the trailing space ---
      if (node.name === "HeaderMark") {
        let end = node.to;
        const docLine = state.doc.lineAt(node.from);
        // Swallow the single space that separates `#` from text.
        if (end < docLine.to && state.sliceDoc(end, end + 1) === " ") {
          end++;
        }
        decorations.push(hideDeco.range(node.from, end));
        return;
      }

      // --- Inline marks & link parts ---
      if (INLINE_MARKS.has(node.name)) {
        decorations.push(hideDeco.range(node.from, node.to));
      }
    },
  });

  // `true` tells CodeMirror to sort the ranges for us, so we don't
  // have to worry about iteration order of the syntax tree.
  return Decoration.set(decorations, true);
}

/* ------------------------------------------------------------------ */
/*  Plugin                                                            */
/* ------------------------------------------------------------------ */

export const livePreview = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(view: EditorView) {
      this.decorations = buildDecorations(view);
    }

    update(update: ViewUpdate) {
      if (
        update.docChanged ||
        update.selectionSet ||
        update.viewportChanged
      ) {
        this.decorations = buildDecorations(update.view);
      }
    }
  },
  { decorations: (v) => v.decorations },
);

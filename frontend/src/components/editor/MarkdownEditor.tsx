import { useEffect, useRef } from "react";
import { EditorView, keymap, placeholder as cmPlaceholder, drawSelection, highlightActiveLine, highlightSpecialChars } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import {
  defaultHighlightStyle,
  syntaxHighlighting,
  indentOnInput,
  bracketMatching,
} from "@codemirror/language";
import {
  defaultKeymap,
  history,
  historyKeymap,
  indentWithTab,
} from "@codemirror/commands";
import { searchKeymap, highlightSelectionMatches } from "@codemirror/search";
import { closeBrackets, closeBracketsKeymap } from "@codemirror/autocomplete";
import { HighlightStyle } from "@codemirror/language";
import { tags } from "@lezer/highlight";
import { livePreview } from "./livePreview";

// Obsidian-like dark theme
const obsidianTheme = EditorView.theme(
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

const obsidianHighlightStyle = HighlightStyle.define([
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

interface MarkdownEditorProps {
  initialContent: string;
  onChange: (content: string) => void;
}

export function MarkdownEditor({ initialContent, onChange }: MarkdownEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!containerRef.current) return;

    const state = EditorState.create({
      doc: initialContent,
      extensions: [
        highlightSpecialChars(),
        history(),
        drawSelection(),
        indentOnInput(),
        bracketMatching(),
        closeBrackets(),
        highlightActiveLine(),
        highlightSelectionMatches(),
        markdown({ base: markdownLanguage, codeLanguages: languages }),
        obsidianTheme,
        syntaxHighlighting(obsidianHighlightStyle),
        syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
        cmPlaceholder("Начните писать..."),
        keymap.of([
          ...defaultKeymap,
          ...historyKeymap,
          ...searchKeymap,
          ...closeBracketsKeymap,
          indentWithTab,
        ]),
        livePreview,
        EditorView.lineWrapping,
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            onChangeRef.current(update.state.doc.toString());
          }
        }),
      ],
    });

    const view = new EditorView({
      state,
      parent: containerRef.current,
    });

    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, []);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const current = view.state.doc.toString();
    if (current !== initialContent) {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: initialContent },
      });
    }
  }, [initialContent]);

  return <div ref={containerRef} className="h-full overflow-auto" />;
}

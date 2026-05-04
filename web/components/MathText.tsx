"use client";

import katex from "katex";
import { Fragment, type ReactNode, useMemo } from "react";

// Match the four LaTeX delimiter shapes the LLM tends to emit:
//   \(...\)   inline
//   \[...\]   block
//   $...$     inline
//   $$...$$   block
const MATH_RE =
  /\\\(([\s\S]+?)\\\)|\\\[([\s\S]+?)\\\]|\$\$([\s\S]+?)\$\$|\$([^\n$]+?)\$/g;

type Chunk =
  | { kind: "text"; value: string }
  | { kind: "math"; value: string; display: boolean };

function tokenize(src: string): Chunk[] {
  const chunks: Chunk[] = [];
  let last = 0;
  for (const match of src.matchAll(MATH_RE)) {
    const start = match.index ?? 0;
    if (start > last) {
      chunks.push({ kind: "text", value: src.slice(last, start) });
    }
    if (match[1] !== undefined) {
      chunks.push({ kind: "math", value: match[1], display: false });
    } else if (match[2] !== undefined) {
      chunks.push({ kind: "math", value: match[2], display: true });
    } else if (match[3] !== undefined) {
      chunks.push({ kind: "math", value: match[3], display: true });
    } else if (match[4] !== undefined) {
      chunks.push({ kind: "math", value: match[4], display: false });
    }
    last = start + match[0].length;
  }
  if (last < src.length) {
    chunks.push({ kind: "text", value: src.slice(last) });
  }
  return chunks;
}

type Rendered = { kind: "html"; html: string } | { kind: "fallback"; text: string };

function renderMath(value: string, display: boolean): Rendered {
  try {
    // throwOnError: true so we can fall back to plain text on failure;
    // KaTeX's default behavior renders unparsable bits in red, which the
    // user explicitly doesn't want on the exam page.
    return {
      kind: "html",
      html: katex.renderToString(value, {
        displayMode: display,
        throwOnError: true,
        strict: "ignore",
        output: "html",
      }),
    };
  } catch {
    return { kind: "fallback", text: value };
  }
}

/**
 * Render a string that mixes plain text and LaTeX math (\(...\), \[...\],
 * $...$, $$...$$). Math is typeset with KaTeX; everything else is rendered
 * verbatim with whitespace preserved.
 */
export function MathText({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  const chunks = useMemo(() => tokenize(children), [children]);
  return (
    <span className={className} style={{ whiteSpace: "pre-wrap" }}>
      {chunks.map((c, i) => {
        if (c.kind === "text") return <Fragment key={i}>{c.value}</Fragment>;
        const r = renderMath(c.value, c.display);
        if (r.kind === "html") {
          return (
            <span key={i} dangerouslySetInnerHTML={{ __html: r.html }} />
          );
        }
        // KaTeX couldn't parse — show the raw expression as plain text in
        // the surrounding color, no red error styling.
        return <Fragment key={i}>{r.text}</Fragment>;
      })}
    </span>
  ) as ReactNode;
}

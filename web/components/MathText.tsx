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

function renderMath(value: string, display: boolean): string {
  try {
    return katex.renderToString(value, {
      displayMode: display,
      throwOnError: false,
      strict: "ignore",
      output: "html",
    });
  } catch {
    return display ? `\\[${value}\\]` : `\\(${value})\\)`;
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
        return (
          <span
            key={i}
            dangerouslySetInnerHTML={{ __html: renderMath(c.value, c.display) }}
          />
        );
      })}
    </span>
  ) as ReactNode;
}

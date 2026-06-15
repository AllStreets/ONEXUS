/* NEXUS Aurora — md.js: minimal, dependency-free markdown renderer.
 *
 * Escape-first architecture (XSS safety): every character of input is
 * HTML-escaped BEFORE any markdown transform runs, so the only markup in
 * the output is markup this module itself emitted. Fenced code blocks are
 * split out of the raw text first (so list/heading transforms never touch
 * code), but their contents go through the same escaper.
 *
 * Supported: **bold**, *italic*, `inline code`, ``` fenced code blocks ```,
 * # / ## / ### headings, - and 1. lists, [text](http(s) links), > quotes,
 * paragraphs + line breaks. Link hrefs must start with http:// or https://
 * — anything else (javascript:, data:, relative) is left as plain text.
 */

const _ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeMd(s) {
  if (s == null) return "";
  return String(s).replace(/[&<>"']/g, (c) => _ESC[c]);
}

/* Only http(s) URLs become real links. The href arrives already escaped,
 * which does not affect the scheme prefix; reject everything else. */
function safeHref(raw) {
  const url = (raw || "").trim();
  return /^https?:\/\//i.test(url) ? url : null;
}

/* Inline transforms over already-escaped text. Inline code is pulled out
 * first so bold/italic/link markers inside backticks stay literal. The
 * sentinel "<Cn>" is unforgeable: a raw "<" cannot survive escapeMd, and
 * no other transform emits this shape. */
function renderInline(text) {
  const codeSpans = [];
  let out = text.replace(/`([^`\n]+)`/g, (_, code) => {
    codeSpans.push(`<code class="nx-md-code">${code}</code>`);
    return `<C${codeSpans.length - 1}>`;
  });
  out = out.replace(/\[([^\]\n]+)\]\(([^()\s]+)\)/g, (m, label, href) => {
    const safe = safeHref(href);
    if (!safe) return m;
    return `<a href="${safe}" target="_blank" rel="noopener">${label}</a>`;
  });
  out = out.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  return out.replace(/<C(\d+)>/g, (_, i) => codeSpans[Number(i)]);
}

/* Walk escaped (non-code) text line by line into block structure. */
function renderBlocks(escaped) {
  const lines = escaped.split("\n");
  const html = [];
  let para = [];
  let list = null;   // { tag: "ul" | "ol", items: [] }
  let quote = [];

  const flushPara = () => {
    if (para.length) {
      html.push(`<p>${para.map(renderInline).join("<br>")}</p>`);
      para = [];
    }
  };
  const flushList = () => {
    if (list) {
      html.push(`<${list.tag}>${list.items.map(i => `<li>${renderInline(i)}</li>`).join("")}</${list.tag}>`);
      list = null;
    }
  };
  const flushQuote = () => {
    if (quote.length) {
      html.push(`<blockquote>${quote.map(renderInline).join("<br>")}</blockquote>`);
      quote = [];
    }
  };
  const flushAll = () => { flushPara(); flushList(); flushQuote(); };

  for (const line of lines) {
    if (!line.trim()) { flushAll(); continue; }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushAll();
      const level = heading[1].length;
      html.push(`<h${level} class="nx-md-h">${renderInline(heading[2])}</h${level}>`);
      continue;
    }

    // "> quote" arrives escaped as "&gt; quote"
    const quoted = line.match(/^&gt;\s?(.*)$/);
    if (quoted) { flushPara(); flushList(); quote.push(quoted[1]); continue; }

    const ul = line.match(/^\s*-\s+(.+)$/);
    if (ul) {
      flushPara(); flushQuote();
      if (!list || list.tag !== "ul") { flushList(); list = { tag: "ul", items: [] }; }
      list.items.push(ul[1]);
      continue;
    }
    const ol = line.match(/^\s*\d+\.\s+(.+)$/);
    if (ol) {
      flushPara(); flushQuote();
      if (!list || list.tag !== "ol") { flushList(); list = { tag: "ol", items: [] }; }
      list.items.push(ol[1]);
      continue;
    }

    flushList(); flushQuote();
    para.push(line);
  }
  flushAll();
  return html.join("");
}

export function renderMarkdown(raw) {
  if (raw == null) return "";
  const src = String(raw).replace(/\r\n?/g, "\n");

  // Split fenced code blocks out of the RAW text. With the two capture
  // groups, split() yields [text, lang, code, text, lang, code, ..., text]
  // so code segments never pass through the block/inline transforms.
  const parts = src.split(/```([\w+.#-]*)[ \t]*\n?([\s\S]*?)```/);
  const html = [];
  for (let i = 0; i < parts.length; i += 3) {
    const text = parts[i];
    if (text && text.trim()) html.push(renderBlocks(escapeMd(text)));
    if (i + 2 < parts.length) {
      const lang = parts[i + 1] || "";
      const code = (parts[i + 2] || "").replace(/\n$/, "");
      const langAttr = lang ? ` data-lang="${escapeMd(lang)}"` : "";
      html.push(`<pre class="nx-md-pre"${langAttr}><code>${escapeMd(code)}</code></pre>`);
    }
  }
  return html.join("");
}

// Bộ phân tích Markdown nhỏ cho câu trả lời của trợ lý. Chỉ sinh cây dữ liệu (không HTML),
// thành phần React dựng phần tử từ cây này nên không cần dangerouslySetInnerHTML.
// Hỗ trợ: đoạn, tiêu đề, danh sách (gạch đầu dòng/đánh số), trích dẫn, khối mã, **đậm**, *nghiêng*, `mã`,
// liên kết http(s)/mailto và dấu trích dẫn [cite:chunk_id].

export type Inline =
  | { kind: "text"; text: string }
  | { kind: "bold"; children: Inline[] }
  | { kind: "italic"; children: Inline[] }
  | { kind: "code"; text: string }
  | { kind: "link"; href: string; children: Inline[] }
  | { kind: "cite"; chunkId: string }
  | { kind: "br" };

export type Block =
  | { kind: "paragraph"; children: Inline[] }
  | { kind: "heading"; level: number; children: Inline[] }
  | { kind: "list"; ordered: boolean; items: Inline[][] }
  | { kind: "quote"; children: Inline[] }
  | { kind: "code"; text: string };

const INLINE =
  /\[cite:([^\]]+)\]|`([^`\n]+)`|\*\*([^*\n]+)\*\*|\*([^*\s][^*\n]*)\*|\[([^\]\n]+)\]\(((?:https?:\/\/|mailto:)[^\s)]+)\)/g;

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    const index = match.index ?? 0;
    if (index > last) out.push({ kind: "text", text: text.slice(last, index) });
    const [, cite, code, bold, italic, linkText, href] = match;
    if (cite !== undefined) out.push({ kind: "cite", chunkId: cite.trim() });
    else if (code !== undefined) out.push({ kind: "code", text: code });
    else if (bold !== undefined) out.push({ kind: "bold", children: parseInline(bold) });
    else if (italic !== undefined) out.push({ kind: "italic", children: parseInline(italic) });
    else if (linkText !== undefined && href !== undefined) out.push({ kind: "link", href, children: parseInline(linkText) });
    last = index + match[0].length;
  }
  if (last < text.length) out.push({ kind: "text", text: text.slice(last) });
  return out;
}

// Các dòng của một đoạn nối bằng <br>.
function parseLines(lines: string[]): Inline[] {
  const out: Inline[] = [];
  lines.forEach((line, index) => {
    if (index > 0) out.push({ kind: "br" });
    out.push(...parseInline(line));
  });
  return out;
}

const FENCE = /^\s*```/;
const HEADING = /^(#{1,4})\s+(.*)$/;
const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
const QUOTE = /^\s*>\s?(.*)$/;

function startsBlock(line: string): boolean {
  return FENCE.test(line) || HEADING.test(line) || BULLET.test(line) || NUMBERED.test(line) || QUOTE.test(line);
}

// Khi đang stream, dấu "[cite:..." chưa đóng sẽ bị ẩn để người dùng không thấy mảnh dở dang.
export function hideIncompleteCite(text: string): string {
  return text.replace(/\[(?:c(?:i(?:t(?:e(?::[^\]]*)?)?)?)?)?$/, "");
}

export function parseMarkdown(source: string): Block[] {
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
    } else if (FENCE.test(line)) {
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !FENCE.test(lines[i])) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1; // bỏ dòng đóng (nếu đang stream thì có thể chưa có)
      blocks.push({ kind: "code", text: code.join("\n") });
    } else if (HEADING.test(line)) {
      const [, hashes, content] = line.match(HEADING)!;
      blocks.push({ kind: "heading", level: hashes.length, children: parseInline(content) });
      i += 1;
    } else if (BULLET.test(line) || NUMBERED.test(line)) {
      const ordered = NUMBERED.test(line);
      const pattern = ordered ? NUMBERED : BULLET;
      const items: Inline[][] = [];
      while (i < lines.length && pattern.test(lines[i])) {
        items.push(parseInline(lines[i].match(pattern)![1]));
        i += 1;
      }
      blocks.push({ kind: "list", ordered, items });
    } else if (QUOTE.test(line)) {
      const quoted: string[] = [];
      while (i < lines.length && QUOTE.test(lines[i])) {
        quoted.push(lines[i].match(QUOTE)![1]);
        i += 1;
      }
      blocks.push({ kind: "quote", children: parseLines(quoted) });
    } else {
      const paragraph: string[] = [];
      while (i < lines.length && lines[i].trim() && (paragraph.length === 0 || !startsBlock(lines[i]))) {
        paragraph.push(lines[i]);
        i += 1;
      }
      blocks.push({ kind: "paragraph", children: parseLines(paragraph) });
    }
  }
  return blocks;
}

import type { ReactNode } from "react";
import type { Citation } from "@/lib/assistant-protocol";
import { hideIncompleteCite, parseMarkdown, type Inline } from "@/lib/assistant/markdown";
import { CHIP_CLASS, CHIP_SAMPLE_CLASS, CHIP_UNKNOWN_CLASS, citationLabel } from "./citation";

const MARKDOWN_CLASS =
  "text-sm leading-relaxed break-words [&_p]:my-2 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 " +
  "[&_h3]:mb-1 [&_h3]:mt-3 [&_h3]:text-base [&_h3]:font-semibold [&_h4]:mb-1 [&_h4]:mt-3 [&_h4]:font-semibold [&_h5]:mt-2 [&_h5]:font-semibold [&_h6]:mt-2 [&_h6]:font-semibold " +
  "[&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-muted [&_pre]:p-3 [&_pre_code]:p-0 " +
  "[&_blockquote]:my-2 [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground " +
  "[&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2";

interface Props {
  text: string;
  citations: Citation[];
  streaming?: boolean;
  onCite: (citation: Citation) => void;
}

// Dựng phần tử React từ cây Markdown: mọi chuỗi đi qua React nên được thoát ký tự, không có HTML thô.
export default function Markdown({ text, citations, streaming = false, onCite }: Props) {
  const blocks = parseMarkdown(streaming ? hideIncompleteCite(text) : text);
  const byId = new Map(citations.map((citation) => [citation.chunk_id, citation]));

  function inline(nodes: Inline[]): ReactNode[] {
    return nodes.map((node, index) => {
      switch (node.kind) {
        case "text":
          return node.text;
        case "br":
          return <br key={index} />;
        case "bold":
          return <strong key={index}>{inline(node.children)}</strong>;
        case "italic":
          return <em key={index}>{inline(node.children)}</em>;
        case "code":
          return <code key={index}>{node.text}</code>;
        case "link":
          return (
            <a key={index} href={node.href} target="_blank" rel="noopener noreferrer">
              {inline(node.children)}
            </a>
          );
        case "cite": {
          const citation = byId.get(node.chunkId);
          // Trích dẫn không có trong danh sách do code dựng: không cho bấm, để người đọc thấy nó chưa được xác minh.
          if (!citation) {
            return (
              <span key={index} className={CHIP_UNKNOWN_CLASS} title="Nguồn này không có trong danh sách trích dẫn đã xác minh">
                nguồn chưa xác minh
              </span>
            );
          }
          return (
            <button
              key={index}
              type="button"
              className={citation.is_sample ? CHIP_SAMPLE_CLASS : CHIP_CLASS}
              title="Xem nguyên văn"
              onClick={() => onCite(citation)}
            >
              {citationLabel(citation)}
            </button>
          );
        }
      }
    });
  }

  return (
    <div className={MARKDOWN_CLASS}>
      {blocks.map((block, index) => {
        switch (block.kind) {
          case "paragraph":
            return <p key={index}>{inline(block.children)}</p>;
          case "heading": {
            const Tag = `h${Math.min(block.level + 2, 6)}` as "h3" | "h4" | "h5" | "h6";
            return <Tag key={index}>{inline(block.children)}</Tag>;
          }
          case "list": {
            const Tag = block.ordered ? "ol" : "ul";
            return (
              <Tag key={index}>
                {block.items.map((item, itemIndex) => (
                  <li key={itemIndex}>{inline(item)}</li>
                ))}
              </Tag>
            );
          }
          case "quote":
            return <blockquote key={index}>{inline(block.children)}</blockquote>;
          case "code":
            return (
              <pre key={index}>
                <code>{block.text}</code>
              </pre>
            );
        }
      })}
    </div>
  );
}

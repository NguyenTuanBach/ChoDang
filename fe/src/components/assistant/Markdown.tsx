import type { ReactNode } from "react";
import type { Citation } from "@/lib/assistant-protocol";
import { hideIncompleteCite, parseMarkdown, type Inline } from "@/lib/assistant/markdown";
import { citationLabel } from "./citation";
import styles from "./assistant.module.css";

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
              <span key={index} className={styles.chipUnknown} title="Nguồn này không có trong danh sách trích dẫn đã xác minh">
                nguồn chưa xác minh
              </span>
            );
          }
          return (
            <button
              key={index}
              type="button"
              className={citation.is_sample ? `${styles.chip} ${styles.chipSample}` : styles.chip}
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
    <div className={styles.markdown}>
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

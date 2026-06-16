import type { ReactNode } from 'react';

/**
 * 极简 markdown 渲染：只覆盖 LLM 实际产出的语法
 *  - **bold** / __bold__
 *  - *italic* / _italic_
 *  - `inline code`
 *  - 无序列表（行首 - 或 *）
 *  - 有序列表（行首 数字.）
 *  - emoji 列表头（行首 ✅/🔋/📌/💡 等任意 Extended_Pictographic）
 *  - 段落（双换行分隔，块内单换行用 <br>）
 *  - 链接 [text](url)
 *
 * 不做 HTML 解析，所有用户内容经 React 文本节点自动转义，天然防 XSS。
 * 流式输出阶段个别 token 跨 chunk 时，bold 可能短暂"漏"——可接受。
 *
 * 注意：商品推荐卡片由后端作为结构化 attachment 推送（AgentMessage.product_recommendations），
 * 不在此处解析 markdown 文本。早期实现中的"可选商品："段字符串匹配已删除。
 */

const INLINE_TOKEN_RE = /(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;

const LIST_MARKER_RE = /^\s*(?:[-*]|\d+\.)\s+/;
const LIST_EMOJI_RE = /^\s*\p{Extended_Pictographic}/u;
const ORDERED_LIST_RE = /^\s*\d+\.\s+/;

function isListItem(line: string): boolean {
  return LIST_MARKER_RE.test(line) || LIST_EMOJI_RE.test(line);
}

function stripMarker(line: string): string {
  // 只剥掉 ASCII 列表标记（- * 1.），emoji 标记作为视觉前缀保留
  return line.replace(LIST_MARKER_RE, '');
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let matchIndex = 0;

  for (const match of text.matchAll(INLINE_TOKEN_RE)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      parts.push(text.slice(lastIndex, start));
    }
    const token = match[0];
    if (token.startsWith('**') || token.startsWith('__')) {
      parts.push(<strong key={`${keyPrefix}-s-${matchIndex++}`}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('*') || token.startsWith('_')) {
      parts.push(<em key={`${keyPrefix}-e-${matchIndex++}`}>{token.slice(1, -1)}</em>);
    } else if (token.startsWith('`')) {
      parts.push(<code key={`${keyPrefix}-c-${matchIndex++}`}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith('[')) {
      const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linkMatch) {
        const [, label, url] = linkMatch;
        parts.push(
          <a key={`${keyPrefix}-a-${matchIndex++}`} href={url} target="_blank" rel="noreferrer">
            {label}
          </a>
        );
      }
    }
    lastIndex = start + token.length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

type Segment = { type: 'text' | 'list'; lines: string[] };

function splitToSegments(lines: string[]): Segment[] {
  const segments: Segment[] = [];
  let current: Segment | null = null;

  for (const line of lines) {
    const listLike = isListItem(line);
    const want = listLike ? 'list' : 'text';
    if (current && current.type === want) {
      current.lines.push(line);
    } else {
      if (current) segments.push(current);
      current = { type: want, lines: [line] };
    }
  }
  if (current) segments.push(current);
  return segments;
}

function renderBlock(block: string, blockKey: string): ReactNode {
  const lines = block.split('\n');
  const segments = splitToSegments(lines);

  return (
    <>
      {segments.map((seg, i) => {
        const segKey = `${blockKey}-${i}`;
        if (seg.type === 'list') {
          const ordered = seg.lines.every((l) => ORDERED_LIST_RE.test(l));
          const Tag = ordered ? 'ol' : 'ul';
          return (
            <Tag key={segKey} className="md-list">
              {seg.lines.map((line, j) => (
                <li key={`${segKey}-li-${j}`}>
                  {renderInline(stripMarker(line), `${segKey}-${j}`)}
                </li>
              ))}
            </Tag>
          );
        }
        return (
          <p key={segKey} className="md-paragraph">
            {seg.lines.map((line, j) => (
              <span key={`${segKey}-ln-${j}`}>
                {renderInline(line, `${segKey}-${j}`)}
                {j < seg.lines.length - 1 ? <br /> : null}
              </span>
            ))}
          </p>
        );
      })}
    </>
  );
}

export function MarkdownContent({ text }: { text: string }): ReactNode {
  if (!text) return null;
  const blocks = text.split(/\n{2,}/);
  return <>{blocks.map((block, i) => renderBlock(block, `b${i}`))}</>;
}
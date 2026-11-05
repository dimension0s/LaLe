// src/utils/export.ts
import { marked } from 'marked';

/**
 * 导出单条或多条笔记
 * @param notes 笔记数组
 * @param format 导出格式：'md' 或 'html'
 */
export function exportNotes(notes: any[], format: 'md' | 'html' = 'html') {
  if (!notes || notes.length === 0) return;

  const isSingle = notes.length === 1;
  const baseName = isSingle
    ? `${notes[0].file_name || '未命名'}_${notes[0].note_type_label || '笔记'}`
    : `笔记批量导出_${new Date().getTime()}`;

  // 1. 提取原始文本，并清理掉可能的 Markdown 代码块外壳
  const cleanMarkdown = (text: string) => {
    if (!text) return '';
    // 尝试剥离首尾的 ```markdown 和 ```
    let cleaned = text.replace(/^```[a-zA-Z]*\n?/, '').replace(/\n?```$/, '');
    // 把可能存在的字面量 \n 转回真正的换行符（如果后端转义了）
    cleaned = cleaned.replace(/\\n/g, '\n');
    // 处理其他 HTML 实体
    cleaned = cleaned.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
    return cleaned;
  };

  if (format === 'md') {
    let content = isSingle
      ? `# ${notes[0].note_type_label}\n\n${cleanMarkdown(notes[0].content)}`
      : `# 笔记批量导出\n\n导出于：${new Date().toLocaleString()}\n\n---\n\n` +
        notes.map((n, i) => `## ${i+1}. ${n.file_name} - ${n.note_type_label}\n\n${cleanMarkdown(n.content)}`).join('\n\n---\n\n');
    downloadFile(content, `${baseName}.md`, 'text/markdown');
  } else {
    let markdownBody = isSingle
      ? cleanMarkdown(notes[0].content)
      : notes.map((n, i) => `## ${i+1}. ${n.file_name} - ${n.note_type_label}\n\n${cleanMarkdown(n.content)}`).join('\n\n---\n\n');

    // 强制要求解析换行
    marked.setOptions({ breaks: true, gfm: true });
    const htmlBody = marked.parse(markdownBody);

    const htmlContent = `
      <!DOCTYPE html>
      <html lang="zh-CN">
      <head>
        <meta charset="UTF-8">
        <title>${baseName}</title>
        <style>
          body { font-family: -apple-system, sans-serif; line-height: 1.8; color: #333; max-width: 800px; margin: 0 auto; padding: 40px 20px; }
          h1, h2, h3 { color: #111; border-bottom: 1px solid #eee; padding-bottom: 8px; }
          blockquote { border-left: 4px solid #10b981; color: #555; background: #f9f9f9; padding: 10px 15px; margin: 1em 0; }
          code { background: #f4f4f5; padding: 2px 6px; border-radius: 4px; font-family: monospace; }
          pre { background: #f4f4f5; padding: 16px; border-radius: 8px; overflow-x: auto; }
          pre code { background: transparent; padding: 0; }
        </style>
      </head>
      <body>
        ${htmlBody}
      </body>
      </html>
    `;
    downloadFile(htmlContent, `${baseName}.html`, 'text/html');
  }
}

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
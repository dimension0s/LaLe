import { useState } from 'react';
import { Button, message, Divider } from 'antd';
import { PlusOutlined, CheckOutlined } from '@ant-design/icons';
import api from '../api/axios';

interface AnalysisPanelProps {
  mode: 'translation' | 'grammar' | 'phrase' | 'terminology';
  data: any;
  originalText: string;
  documentId: number;
}

export default function AnalysisPanel({ mode, data, originalText, documentId }: AnalysisPanelProps) {
  const [added, setAdded] = useState<boolean>(false);
  const [loading, setLoading] = useState(false);

  const content = data?.analysis || data?.translated_text || "暂无结果";

  const noteTypeMap = {
    translation: 'translation',
    grammar: 'grammar',
    phrase: 'phrase',
    terminology: 'terminology',
  };
  const noteType = noteTypeMap[mode];

  const handleAddNote = async () => {
    if (added) return;
    setLoading(true);
    try {
      await api.post('/api/notes', {
        document_id: documentId,
        note_type: noteType,
        content: content,
      });
      setAdded(true);
      message.success('已加入笔记');
    } catch (error) {
      // 拦截器已处理
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full relative bg-[#f8fafc]">
      {/* 内容区：增加留白 */}
      <div className="flex-1 overflow-y-auto px-6 py-6 pb-24 text-sm">
        <div className="text-gray-500 mb-3 text-xs bg-gray-100 p-3 rounded-md border border-gray-200">
          <span className="font-medium text-gray-600">原文：</span>
          {originalText}
        </div>

        <Divider className="my-4 border-gray-200" />

        <div className="text-gray-800 whitespace-pre-wrap leading-loose">
          {content}
        </div>
      </div>

      {/* 底部固定加入按钮 */}
      <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-[#f8fafc] via-[#f8fafc] to-transparent flex justify-center">
          <Button
          size="middle"
          onClick={handleAddNote}
          loading={loading}
          disabled={added}
          className={`
            flex items-center justify-center px-8 rounded-full shadow-sm border-none text-[15px] tracking-wider
            ${added 
              ? "bg-green-50 text-green-600" 
              : "bg-[#e0e7ff] text-[#4b5563] hover:bg-[#c7d2fe] hover:text-[#374151]"
            }
          `}
        >
          {added ? '已在笔记中' : '加入笔记'}
        </Button>
      </div>
    </div>
  );
}
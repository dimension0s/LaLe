import { useState } from 'react';
import { Button, message, Tag } from 'antd';
import { PlusOutlined, CheckOutlined } from '@ant-design/icons';
import api from '../api/axios';

export default function WordPanel({ data, word }: { data: any; word: string }) {
  const [added, setAdded] = useState<boolean>(!!data.in_vocabulary);
  const [loading, setLoading] = useState(false);

  const info = data.word_info || {};
  const senses = info.senses || [];

  const handleAdd = async () => {
    if (added) return;
    setLoading(true);
    try {
      await api.post('/api/vocabulary', {
        word: word.toLowerCase(),
        word_info: info,
      });
      setAdded(true);
      message.success('已加入生词本');
    } catch (error) {
      // 拦截器已处理
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full relative bg-[#f8fafc]">
      {/* 内容区：增加了 px-6 py-6 留白 */}
      <div className="flex-1 overflow-y-auto px-6 py-6 pb-24">

        {/* 词头与音标 */}
        <div className="mb-4">
          <h2 className="text-2xl font-bold text-gray-800 mb-1">{info.headword || word}</h2>
          <div className="text-gray-500 text-sm flex gap-4">
            {info.phonetic_uk && <span>英 /{info.phonetic_uk}/</span>}
            {info.phonetic_us && <span>美 /{info.phonetic_us}/</span>}
          </div>
        </div>

        {/* 词性 */}
        {info.pos && info.pos.length > 0 && (
          <div className="mb-4">
            {info.pos.map((p: string, i: number) => (
              <Tag color="blue" key={i} className="border-none bg-blue-100 text-blue-700">{p}</Tag>
            ))}
          </div>
        )}

        {/* 释义列表 */}
        <div className="flex flex-col gap-5">
          {senses.map((sense: any, index: number) => (
            <div key={index} className="text-sm">
              <div className="flex gap-2">
                <span className="text-gray-400 font-mono">{index + 1}.</span>
                <div>
                  <div className="text-gray-800 font-medium">
                    {sense.translation || sense.definition}
                  </div>
                  {sense.translation && sense.definition && (
                    <div className="text-gray-500 mt-1">{sense.definition}</div>
                  )}
                </div>
              </div>
              {/* 例句 */}
              {sense.examples && sense.examples.length > 0 && (
                <div className="mt-3 pl-6 border-l-2 border-gray-200 flex flex-col gap-3">
                  {sense.examples.map((ex: any, i: number) => (
                    <div key={i}>
                      <div className="text-gray-700 italic">{ex.english}</div>
                      <div className="text-gray-500 text-xs mt-1">{ex.chinese}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 底部固定加入按钮：居中、变小、蓝灰底色 */}
      <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-[#f8fafc] via-[#f8fafc] to-transparent flex justify-center">
          <Button
          size="middle"
          onClick={handleAdd}
          loading={loading}
          disabled={added}
          className={`
            flex items-center justify-center px-8 rounded-full shadow-sm border-none text-[15px] tracking-wider
            ${added 
              ? "bg-green-50 text-green-600" 
              : "bg-[#dbeafe] text-[#4b5563] hover:bg-[#bfdbfe] hover:text-[#374151]"
            }
          `}
        >
          {added ? '已在生词本' : '加入生词本'}
        </Button>
      </div>
    </div>
  );
}
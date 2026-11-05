import { useState, useEffect } from 'react';
import { Modal, Button, message, Tag, Spin } from 'antd';
import api from '../api/axios';

interface VocabModalProps {
  open: boolean;
  onClose: () => void;
  vocab: any;
  onDeleted: () => void;
}

export default function VocabModal({ open, onClose, vocab, onDeleted }: VocabModalProps) {
  const [deleting, setDeleting] = useState(false);
  const [fullData, setFullData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // 每次打开弹窗时，请求完整的单词详情
  useEffect(() => {
    if (open && vocab) {
      setLoading(true);
      api.get(`/api/vocabulary/${vocab.vocab_uuid}`)
        .then(res => setFullData(res))
        .catch(() => message.error('获取详情失败'))
        .finally(() => setLoading(false));
    } else {
      setFullData(null);
    }
  }, [open, vocab]);

  if (!vocab) return null;

  const info = fullData?.word_info || {};
  const senses = info.senses || [];

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await api.delete(`/api/vocabulary/${vocab.vocab_uuid}`);
      message.success('已移入回收站');
      onClose();
      onDeleted();
    } catch (error) {
      // 拦截器处理
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={650}
      centered
      className="rounded-2xl overflow-hidden"
      styles={{ body: { padding: 0, height: '60vh', display: 'flex', flexDirection: 'column' } }}
    >
      <div className="flex-1 overflow-y-auto px-8 py-6 bg-[#f8fafc]">
        {loading ? (
          <div className="h-full flex items-center justify-center"><Spin description="加载词典数据..." /></div>
        ) : (
          <>
            <div className="mb-4">
              <h2 className="text-3xl font-bold text-gray-800 mb-1">{info.headword || vocab.word}</h2>
              <div className="text-gray-500 text-sm flex gap-4">
                {info.phonetic_uk && <span>英 /{info.phonetic_uk}/</span>}
                {info.phonetic_us && <span>美 /{info.phonetic_us}/</span>}
              </div>
            </div>

            {info.pos && info.pos.length > 0 && (
              <div className="mb-4">
                {info.pos.map((p: string, i: number) => (
                  <Tag color="blue" key={i} className="border-none bg-blue-100 text-blue-700">{p}</Tag>
                ))}
              </div>
            )}

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
          </>
        )}
      </div>

      <div className="p-4 bg-white border-t border-gray-100 flex justify-center">
        <Button
          danger
          loading={deleting}
          onClick={handleDelete}
          className="rounded-full px-8 shadow-sm border-none bg-red-50 text-red-500 hover:bg-red-100 hover:text-red-600"
        >
          从生词本移除
        </Button>
      </div>
    </Modal>
  );
}
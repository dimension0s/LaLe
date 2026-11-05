import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { message, Button, Dropdown, Modal } from 'antd';
import { ArrowLeftOutlined, DeleteOutlined, MoreOutlined } from '@ant-design/icons';
import api from '../api/axios';
import VocabModal from '../components/VocabModal';

interface VocabItem {
  vocab_uuid: string;
  word: string;
  pos: string[];
  first_meaning: string;
  created_at: string;
  word_info: any;
}

const groupVocabByTime = (items: VocabItem[]) => {
  const now = new Date().getTime();
  const groups: Record<string, VocabItem[]> = {
    '最近3天': [], '近3天-1周': [], '近1周-2周': [], '2周前': [],
  };
  items.forEach((item) => {
    const diffDays = (now - new Date(item.created_at).getTime()) / (1000 * 60 * 60 * 24);
    if (diffDays <= 3) groups['最近3天'].push(item);
    else if (diffDays <= 7) groups['近3天-1周'].push(item);
    else if (diffDays <= 14) groups['近1周-2周'].push(item);
    else groups['2周前'].push(item);
  });
  return groups;
};

const COLUMNS = [
  { key: '最近3天', headerBg: 'bg-orange-200/60', cardBg: 'bg-white/70' },
  { key: '近3天-1周', headerBg: 'bg-orange-200/60', cardBg: 'bg-white/70' },
  { key: '近1周-2周', headerBg: 'bg-orange-200/60', cardBg: 'bg-white/70' },
  { key: '2周前', headerBg: 'bg-orange-200/60', cardBg: 'bg-white/70' },
];

export default function Vocabulary() {
  const navigate = useNavigate();
  const [items, setItems] = useState<VocabItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedVocab, setSelectedVocab] = useState<VocabItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [selectedUuids, setSelectedUuids] = useState<string[]>([]);
  const [isMultiSelectMode, setIsMultiSelectMode] = useState(false);

  const fetchVocab = async () => {
    try {
      const res = await api.get('/api/vocabulary?limit=100');
      setItems(res.items as VocabItem[]);
    } catch (error) {
      message.error('获取生词本失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchVocab(); }, []);

  const handleCardClick = (item: VocabItem) => {
    if (isMultiSelectMode) {
      setSelectedUuids(prev =>
        prev.includes(item.vocab_uuid)
          ? prev.filter(id => id !== item.vocab_uuid)
          : [...prev, item.vocab_uuid]
      );
    } else {
      setSelectedVocab(item);
      setIsModalOpen(true);
    }
  };

  const handleBatchDelete = () => {
    Modal.confirm({
      title: '确认移除',
      content: `确定要将选中的 ${selectedUuids.length} 个单词移入回收站吗？`,
      okText: '确认',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await Promise.all(selectedUuids.map(uuid => api.delete(`/api/vocabulary/${uuid}`)));
          message.success('已移入回收站');
          setSelectedUuids([]);
          setIsMultiSelectMode(false);
          fetchVocab();
        } catch (error) {
          message.error('移除失败');
        }
      },
    });
  };

  const groupedData = groupVocabByTime(items);

  if (loading) return <div className="p-10 text-center text-gray-500">加载中...</div>;

  return (
    // 👇 全局浅橙色背景，增加 max-w-7xl 对齐
    <div className="min-h-screen bg-orange-50 p-6 flex justify-center">

      <div className="w-full max-w-7xl">

        {/* 顶部导航栏 */}
        <div className="flex items-center justify-between mb-4 relative">
          <div className="flex-1 flex justify-start">
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/')}
              className="text-lg text-gray-600 hover:text-gray-900 px-0"
            >
              返回
            </Button>
          </div>

          <div className="flex-none">
            <div className="bg-orange-200/60 backdrop-blur-md text-gray-800 px-10 py-1.5 rounded-full text-lg font-bold tracking-widest shadow-sm">
              生词本
            </div>
          </div>

          <div className="flex-1 flex justify-end items-center gap-4">
            {isMultiSelectMode ? (
              <>
                <span className="text-gray-600 text-sm">已选 {selectedUuids.length} 项</span>
                <Button type="text" onClick={() => { setIsMultiSelectMode(false); setSelectedUuids([]); }}>取消</Button>
                <Button
                  danger
                  icon={<DeleteOutlined />}
                  disabled={selectedUuids.length === 0}
                  onClick={handleBatchDelete}
                >
                  删除
                </Button>
              </>
            ) : (
              <Button
                type="text"
                icon={<DeleteOutlined className="text-xl text-gray-400 hover:text-red-500 transition-colors" />}
                onClick={() => setIsMultiSelectMode(true)}
                className="px-2"
              />
            )}
          </div>
        </div>

        {/* 四列时间轴 */}
        <div className="grid grid-cols-4 gap-6">
          {COLUMNS.map((col) => (
            <div key={col.key} className="flex flex-col gap-3">

              {/* 列头 */}
              <div className={`${col.headerBg} backdrop-blur-sm text-gray-700 text-center py-2 rounded-2xl text-base shadow-sm font-medium`}>
                {col.key}
              </div>

              {/* 单词卡片列表 */}
              {groupedData[col.key].map((item) => {
                const isSelected = selectedUuids.includes(item.vocab_uuid);
                return (
                  <div
                    key={item.vocab_uuid}
                    onClick={() => handleCardClick(item)}
                    className={`
                      relative h-[64px] rounded-2xl flex flex-col justify-center px-4 cursor-pointer transition-all
                      ${col.cardBg} backdrop-blur-sm hover:bg-white/90 shadow-sm border border-white/50
                      ${isSelected ? 'ring-2 ring-orange-400 bg-orange-50/80' : ''}
                    `}
                  >
                    {/* 第一行：单词拼写 */}
                    <span className="text-base font-bold text-gray-800 truncate pr-6">
                      {item.word}
                    </span>

                    {/* 第二行：词性 + 释义 */}
                    <span className="text-[11px] text-gray-500 truncate mt-0.5">
                      {item.pos?.length > 0 ? `${item.pos[0]}. ` : ''}{item.first_meaning}
                    </span>

                    {/* 右上角操作菜单 */}
                    {!isMultiSelectMode && (
                      <div className="absolute right-2 top-1/2 -translate-y-1/2">
                        <Dropdown
                          menu={{
                            items: [
                              {
                                key: 'multi',
                                label: '多选',
                                onClick: (e) => {
                                  e.domEvent.stopPropagation();
                                  setIsMultiSelectMode(true);
                                  setSelectedUuids([item.vocab_uuid]);
                                }
                              },
                              {
                                key: 'delete',
                                label: '删除',
                                danger: true,
                                onClick: (e) => {
                                  e.domEvent.stopPropagation();
                                  setSelectedVocab(item);
                                  setIsModalOpen(true);
                                }
                              },
                            ],
                          }}
                          trigger={['click']}
                        >
                          <MoreOutlined className="text-gray-400 hover:text-gray-600 p-1" onClick={e => e.stopPropagation()} />
                        </Dropdown>
                      </div>
                    )}
                  </div>
                );
              })}

              {groupedData[col.key].length === 0 && (
                <div className="text-center text-gray-400 text-sm py-4">暂无单词</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 详情弹窗 */}
      <VocabModal
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        vocab={selectedVocab}
        onDeleted={fetchVocab}
      />
    </div>
  );
}
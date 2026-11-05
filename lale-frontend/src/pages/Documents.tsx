import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { message, Button, Dropdown, Modal } from 'antd';
import { ArrowLeftOutlined, DeleteOutlined, MoreOutlined } from '@ant-design/icons';
import api from '../api/axios';

interface DocumentItem {
  doc_id: number;
  doc_uuid: string;
  file_name: string;
  created_at: string;
  updated_at: string; // 👈 新增 updated_at
}

// 时间分组计算
const groupDocumentsByTime = (docs: DocumentItem[]) => {
  const now = new Date().getTime();
  const groups: Record<string, DocumentItem[]> = {
    '最近3天': [],
    '近3天-1周': [],
    '近1周-2周': [],
    '2周前': [],
  };

  docs.forEach((doc) => {
    const diffDays = (now - new Date(doc.created_at).getTime()) / (1000 * 60 * 60 * 24);
    if (diffDays <= 3) groups['最近3天'].push(doc);
    else if (diffDays <= 7) groups['近3天-1周'].push(doc);
    else if (diffDays <= 14) groups['近1周-2周'].push(doc);
    else groups['2周前'].push(doc);
  });

  return groups;
};

const COLUMNS = [
  { key: '最近3天', headerBg: 'bg-blue-200/60', cardBg: 'bg-white/70' },
  { key: '近3天-1周', headerBg: 'bg-blue-200/60', cardBg: 'bg-white/70' },
  { key: '近1周-2周', headerBg: 'bg-blue-200/60', cardBg: 'bg-white/70' },
  { key: '2周前', headerBg: 'bg-blue-200/60', cardBg: 'bg-white/70' },
];

export default function Documents() {
  const navigate = useNavigate();
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedUuids, setSelectedUuids] = useState<string[]>([]);
  const [isMultiSelectMode, setIsMultiSelectMode] = useState(false);

  const fetchDocs = async () => {
    try {
      const data = await api.get('/api/documents');
      setDocs(data as DocumentItem[]);
    } catch (error) {
      message.error('获取文件列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDocs(); }, []);

  const handleCardClick = (doc: DocumentItem) => {
    if (isMultiSelectMode) {
      setSelectedUuids(prev =>
        prev.includes(doc.doc_uuid)
          ? prev.filter(id => id !== doc.doc_uuid)
          : [...prev, doc.doc_uuid]
      );
    } else {
      navigate(`/reader/${doc.doc_uuid}`);
    }
  };

  const handleBatchDelete = () => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要将选中的 ${selectedUuids.length} 个文件移入回收站吗？`,
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await Promise.all(selectedUuids.map(uuid => api.delete(`/api/documents/${uuid}`)));
          message.success('已移入回收站');
          setSelectedUuids([]);
          setIsMultiSelectMode(false);
          fetchDocs();
        } catch (error) {
          message.error('删除失败');
        }
      },
    });
  };

  // 👇 格式化时间：年-月-日-时-分
  const formatTime = (isoString: string) => {
    if (!isoString) return '';
    const d = new Date(isoString);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  };

  const groupedDocs = groupDocumentsByTime(docs);

  if (loading) return <div className="p-10 text-center text-gray-500">加载中...</div>;

  return (
    <div className="min-h-screen bg-blue-50 p-6 flex justify-center">

      {/* 增加一个外层容器限制最大宽度，保证在大屏幕上不会拉得太长 */}
      <div className="w-full max-w-7xl">

        {/* 👇 顶部导航栏：缩小了 mb-8 到 mb-4，让整体更紧凑 */}
        <div className="flex items-center justify-between mb-4 relative">

          {/* 👇 左上角返回：去掉了 absolute left-0，靠 flex 自动居左 */}
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

          {/* 中间标题 */}
          <div className="flex-none">
            <div className="bg-blue-200/60 backdrop-blur-md text-gray-800 px-10 py-1.5 rounded-full text-lg font-bold tracking-widest shadow-sm">
              我的文件
            </div>
          </div>

          {/* 👇 右侧操作栏：与标题并排 */}
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

        {/* 四列瀑布流布局 */}
        <div className="grid grid-cols-4 gap-6">
          {COLUMNS.map((col) => (
            <div key={col.key} className="flex flex-col gap-3">

              {/* 列头（时间） */}
              <div className={`${col.headerBg} backdrop-blur-sm text-gray-700 text-center py-2 rounded-2xl text-base shadow-sm font-medium`}>
                {col.key}
              </div>

              {/* 👇 卡片列表 */}
              {groupedDocs[col.key].map((doc) => {
                const isSelected = selectedUuids.includes(doc.doc_uuid);
                return (
                  <div
                    key={doc.doc_uuid}
                    onClick={() => handleCardClick(doc)}
                    className={`
                      relative h-[60px] rounded-2xl flex flex-col justify-center cursor-pointer transition-all px-4
                      ${col.cardBg} backdrop-blur-sm hover:bg-white/90 shadow-sm border border-white/50
                      ${isSelected ? 'ring-2 ring-blue-400 bg-blue-50/80' : ''}
                    `}
                  >
                    {/* 文件名：居中偏左，深灰色 */}
                    <span className="text-sm font-medium text-gray-800 truncate pr-6">
                      {doc.file_name}
                    </span>

                    {/* 👇 更新时间：右下角，小字灰色 */}
                    <span className="text-[10px] text-gray-400 text-right w-full mt-1">
                      {formatTime(doc.updated_at)}
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
                                  setSelectedUuids([doc.doc_uuid]);
                                }
                              },
                              {
                                key: 'delete',
                                label: '删除',
                                danger: true,
                                onClick: (e) => {
                                  e.domEvent.stopPropagation();
                                  setSelectedUuids([doc.doc_uuid]);
                                  Modal.confirm({
                                    title: '确认删除',
                                    content: `确定将 ${doc.file_name} 移入回收站吗？`,
                                    onOk: () => {
                                      api.delete(`/api/documents/${doc.doc_uuid}`).then(() => {
                                        message.success('已移入回收站');
                                        fetchDocs();
                                      });
                                    }
                                  });
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

              {/* 空状态 */}
              {groupedDocs[col.key].length === 0 && (
                <div className="text-center text-gray-400 text-sm py-4">暂无文件</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
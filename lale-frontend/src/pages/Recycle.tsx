import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { message, Button, Dropdown, Modal } from 'antd';
import { ArrowLeftOutlined, DeleteOutlined, MoreOutlined, UndoOutlined } from '@ant-design/icons';
import api from '../api/axios';

interface RecycleItem {
  recycle_id: number;
  file_type: string;
  file_type_label: string;
  file_id: number | string; // 👈 兼容后端返回的数字或字符串
  file_name: string;
  preview_text?: string;
  deleted_at: string;
  expires_at: string;
  days_left: number;
}

const groupRecycleByTime = (items: RecycleItem[]) => {
  const now = new Date().getTime();
  const groups: Record<string, RecycleItem[]> = {
    '最近3天': [], '近3天-1周': [], '近1周-2周': [], '2周前': [],
  };
  items.forEach((item) => {
    const diffDays = (now - new Date(item.deleted_at).getTime()) / (1000 * 60 * 60 * 24);
    if (diffDays <= 3) groups['最近3天'].push(item);
    else if (diffDays <= 7) groups['近3天-1周'].push(item);
    else if (diffDays <= 14) groups['近1周-2周'].push(item);
    else groups['2周前'].push(item);
  });
  return groups;
};

const COLUMNS = [
  { key: '最近3天', headerBg: 'bg-pink-200/60', cardBg: 'bg-white/70' },
  { key: '近3天-1周', headerBg: 'bg-pink-200/60', cardBg: 'bg-white/70' },
  { key: '近1周-2周', headerBg: 'bg-pink-200/60', cardBg: 'bg-white/70' },
  { key: '2周前', headerBg: 'bg-pink-200/60', cardBg: 'bg-white/70' },
];

export default function Recycle() {
  const navigate = useNavigate();
  const [items, setItems] = useState<RecycleItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedUuids, setSelectedUuids] = useState<string[]>([]);
  const [isMultiSelectMode, setIsMultiSelectMode] = useState(false);

  // 👇 预览弹窗状态
  const [previewItem, setPreviewItem] = useState<RecycleItem | null>(null);

  const fetchRecycle = async () => {
    try {
      const res = await api.get('/api/recycle');
      setItems(res as RecycleItem[]);
    } catch (error) {
      message.error('获取回收站失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchRecycle(); }, []);

  const handleCardClick = (item: RecycleItem) => {
    if (isMultiSelectMode) {
      setSelectedUuids(prev =>
        prev.includes(item.recycle_id.toString())
          ? prev.filter(id => id !== item.recycle_id.toString())
          : [...prev, item.recycle_id.toString()]
      );
    } else {
      setPreviewItem(item); // 点击查看预览
    }
  };

  // 批量彻底删除
  const handleBatchDelete = () => {
    Modal.confirm({
      title: '⚠️ 彻底删除',
      content: `确定要彻底删除选中的 ${selectedUuids.length} 项吗？该操作无法撤销！`,
      okText: '彻底删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          const payload = {
            items: selectedUuids.map(id => {
              const target = items.find(i => i.recycle_id.toString() === id);
              return {
                file_type: target?.file_type,
                file_id: Number(target?.file_id) // 👈 彻底删除需要强转为数字
              };
            })
          };
          await api.delete('/api/recycle/permanent', { data: payload });
          message.success('已彻底删除');
          setSelectedUuids([]);
          setIsMultiSelectMode(false);
          fetchRecycle();
        } catch (error) {
          message.error('删除失败');
        }
      },
    });
  };

  // 批量恢复
  const handleBatchRestore = () => {
    Modal.confirm({
      title: '恢复文件',
      content: `确定要恢复选中的 ${selectedUuids.length} 项吗？`,
      okText: '确认恢复',
      cancelText: '取消',
      onOk: async () => {
        try {
          await Promise.all(selectedUuids.map(id => {
            const target = items.find(i => i.recycle_id.toString() === id);
            console.log("恢复传参 check:", target?.file_type, "file_id:", target?.file_id);
            // 👈 恢复接口需要传字符串（UUID）
            return api.post('/api/recycle/restore', {
              file_type: target?.file_type,
              file_id: String(target?.file_id)
            });
          }));
          message.success('已恢复');
          setSelectedUuids([]);
          setIsMultiSelectMode(false);
          fetchRecycle();
        } catch (error) {
          message.error('恢复失败');
        }
      },
    });
  };

  const groupedData = groupRecycleByTime(items);

  if (loading) return <div className="p-10 text-center text-gray-500">加载中...</div>;

  return (
    // 👇 全局浅粉色背景
    <div className="min-h-screen bg-pink-50 p-6 flex justify-center">

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
            <div className="bg-pink-200/60 backdrop-blur-md text-gray-800 px-10 py-1.5 rounded-full text-lg font-bold tracking-widest shadow-sm">
              回收站
            </div>
          </div>

          <div className="flex-1 flex justify-end items-center gap-4">
            {isMultiSelectMode ? (
              <>
                <span className="text-gray-600 text-sm">已选 {selectedUuids.length} 项</span>
                <Button type="text" onClick={() => { setIsMultiSelectMode(false); setSelectedUuids([]); }}>取消</Button>
                <Button
                  type="text"
                  icon={<UndoOutlined />}
                  disabled={selectedUuids.length === 0}
                  onClick={handleBatchRestore}
                  className="text-blue-500"
                >
                  恢复
                </Button>
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  disabled={selectedUuids.length === 0}
                  onClick={handleBatchDelete}
                />
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
        <div className="grid grid-cols-4 gap-6 pb-20">
          {COLUMNS.map((col) => (
            <div key={col.key} className="flex flex-col gap-3">

              {/* 列头 */}
              <div className={`${col.headerBg} backdrop-blur-sm text-gray-700 text-center py-2 rounded-2xl text-base shadow-sm font-medium`}>
                {col.key}
              </div>

              {/* 回收站卡片列表 */}
              {groupedData[col.key].map((item) => {
                const isSelected = selectedUuids.includes(item.recycle_id.toString());
                return (
                  <div
                    key={item.recycle_id}
                    onClick={() => handleCardClick(item)}
                    className={`
                      relative h-[64px] rounded-2xl flex flex-col justify-center px-4 cursor-pointer transition-all
                      ${col.cardBg} backdrop-blur-sm hover:bg-white/90 shadow-sm border border-white/50
                      ${isSelected ? 'ring-2 ring-pink-400 bg-pink-100/50' : ''}
                    `}
                  >
                    {/* 第一行：文件名 */}
                    <span className="text-sm font-medium text-gray-800 truncate pr-6">
                      {item.file_name}
                    </span>

                    {/* 第二行：类型和剩余天数 */}
                    <span className="text-[11px] text-gray-500 truncate mt-0.5">
                      {item.file_type_label} · 剩 {item.days_left} 天
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
                                  setSelectedUuids([item.recycle_id.toString()]);
                                }
                              },
                              {
                                key: 'restore',
                                label: '恢复',
                                onClick: (e) => {
                                  e.domEvent.stopPropagation();
                                  Modal.confirm({
                                    title: '恢复文件',
                                    content: `确定要恢复 ${item.file_name} 吗？`,
                                    onOk: async () => {
                                      // 👈 强转 String
                                      await api.post('/api/recycle/restore', {
                                        file_type: item.file_type,
                                        file_id: String(item.file_id)
                                      });
                                      message.success('已恢复');
                                      fetchRecycle();
                                    }
                                  });
                                }
                              },
                              {
                                key: 'delete',
                                label: '彻底删除',
                                danger: true,
                                onClick: (e) => {
                                  e.domEvent.stopPropagation();
                                  Modal.confirm({
                                    title: '⚠️ 彻底删除',
                                    content: `确定要彻底删除 ${item.file_name} 吗？该操作无法撤销！`,
                                    okButtonProps: { danger: true },
                                    onOk: async () => {
                                      await api.delete('/api/recycle/permanent', {
                                        data: { items: [{ file_type: item.file_type, file_id: Number(item.file_id) }] } // 👈 强转 Number
                                      });
                                      message.success('已彻底删除');
                                      fetchRecycle();
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

              {groupedData[col.key].length === 0 && (
                <div className="text-center text-gray-400 text-sm py-4">暂无数据</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 👇 详情预览弹窗（非多选模式下点击卡片触发） */}
      <Modal
        open={!!previewItem}
        onCancel={() => setPreviewItem(null)}
        footer={[
          <Button key="cancel" onClick={() => setPreviewItem(null)}>取消</Button>,
          <Button
            key="restore"
            type="primary"
            className="bg-blue-500"
            onClick={async () => {
              if (!previewItem) return;
              // 👈 强转 String
              await api.post('/api/recycle/restore', {
                file_type: previewItem.file_type,
                file_id: String(previewItem.file_id)
              });
              message.success('已恢复');
              setPreviewItem(null);
              fetchRecycle();
            }}
          >
            恢复
          </Button>,
          <Button
            key="delete"
            danger
            onClick={async () => {
              if (!previewItem) return;
              await api.delete('/api/recycle/permanent', {
                data: { items: [{ file_type: previewItem.file_type, file_id: Number(previewItem.file_id) }] } // 👈 强转 Number
              });
              message.success('已彻底删除');
              setPreviewItem(null);
              fetchRecycle();
            }}
          >
            彻底删除
          </Button>,
        ]}
        title={<span className="font-bold text-lg">{previewItem?.file_name} - 预览</span>}
      >
        <div className="py-4">
          <div className="text-sm text-gray-500 mb-2">类型：{previewItem?.file_type_label}</div>
          <div className="bg-gray-50 p-4 rounded-lg max-h-[300px] overflow-y-auto text-sm text-gray-700 whitespace-pre-wrap border border-gray-100">
            {previewItem?.preview_text || '暂无预览内容'}
          </div>
        </div>
      </Modal>
    </div>
  );
}
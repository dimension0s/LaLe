import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { message, Button, Dropdown, Modal, Spin } from 'antd';
import { ArrowLeftOutlined, DeleteOutlined, MoreOutlined } from '@ant-design/icons';
import api from '../api/axios';

interface NoteItem {
  note_uuid: string;
  note_type: string;
  note_type_label: string;
  content: string;
  file_name: string;
  created_at: string;
  is_integrated: boolean;
}

interface IntegrationItem {
  integration_uuid: string;
  source_modules: string[];
  source_note_ids: string[];
  content: string;
  created_at: string;
}

const NOTE_TYPES = [
  { key: 'translation', label: '翻译', headerBg: 'bg-green-200/60' },
  { key: 'grammar', label: '语法', headerBg: 'bg-green-200/60' },
  { key: 'phrase', label: '短语/搭配', headerBg: 'bg-green-200/60' },
  { key: 'terminology', label: '术语', headerBg: 'bg-green-200/60' },
];

type DragItem = {
  note_uuid: string;
  note_type: string;
  note_type_label?: string;
  content: string;
  file_name?: string;
  source_note_ids?: string[];
  isIntegration: boolean;
};

export default function Notes() {
  const navigate = useNavigate();
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedUuids, setSelectedUuids] = useState<string[]>([]);
  const [isMultiSelectMode, setIsMultiSelectMode] = useState(false);

  const [isMerging, setIsMerging] = useState(false);
  const [draggedItem, setDraggedItem] = useState<DragItem | null>(null);

  const [stagedItemsForVertical, setStagedItemsForVertical] = useState<DragItem[]>([]);

  const fetchNotes = async () => {
    try {
      const [notesRes, integRes] = await Promise.all([
        api.get('/api/notes/list/all?limit=100'),
        api.get('/api/integrations/list/all')
      ]);
      setNotes(notesRes.items || []);
      setIntegrations(integRes.items || []);
    } catch (error) {
      message.error('获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchNotes(); }, []);

  const handleDragStartNote = (e: React.DragEvent, note: NoteItem) => {
    if (isMultiSelectMode) { e.preventDefault(); return; }
    e.dataTransfer.setData('text/plain', note.note_uuid);
    e.dataTransfer.effectAllowed = 'move';

    setDraggedItem({
      note_uuid: note.note_uuid,
      note_type: note.note_type,
      note_type_label: note.note_type_label,
      content: note.content,
      file_name: note.file_name,
      isIntegration: false,
    });
  };

  const handleDragStartIntegration = (e: React.DragEvent, integ: IntegrationItem) => {
    if (isMultiSelectMode) { e.preventDefault(); return; }
    e.dataTransfer.setData('text/plain', integ.integration_uuid);
    e.dataTransfer.effectAllowed = 'move';

    setDraggedItem({
      note_uuid: integ.integration_uuid,
      note_type: integ.source_modules[0],
      content: integ.content,
      source_note_ids: integ.source_note_ids,
      isIntegration: true,
    });
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const getNoteItemsFromUuids = (uuids: string[]): DragItem[] => {
    return uuids.map(id => {
      const found = notes.find(n => n.note_uuid === id);
      if (found) {
        return {
          note_uuid: found.note_uuid,
          note_type: found.note_type,
          content: found.content,
          file_name: found.file_name,
          isIntegration: false
        };
      }
      return { note_uuid: id, note_type: '', content: '', file_name: '未知文件', isIntegration: false };
    });
  };

  const handleDropVertical = (targetType: string) => {
    if (!draggedItem) return;

    if (!draggedItem.isIntegration && draggedItem.note_type !== targetType) {
      message.warning('只能与同类型的笔记进行合并哦！');
      setDraggedItem(null);
      return;
    }

    let newStaged = [...stagedItemsForVertical];
    if (newStaged.length === 0) {
      const existing = integrations.filter(i => i.source_modules?.length === 1 && i.source_modules[0] === targetType);
      existing.forEach(integ => {
        newStaged.push({
          note_uuid: integ.integration_uuid,
          note_type: targetType,
          content: integ.content,
          source_note_ids: integ.source_note_ids,
          isIntegration: true
        });
      });
    }

    const incomingUuids = draggedItem.isIntegration && draggedItem.source_note_ids ? draggedItem.source_note_ids : [draggedItem.note_uuid];
    const existingUuids = newStaged.flatMap(item => item.isIntegration && item.source_note_ids ? item.source_note_ids : [item.note_uuid]);

    if (incomingUuids.some(uuid => existingUuids.includes(uuid))) {
      message.warning('该笔记已在暂存区中');
      setDraggedItem(null);
      return;
    }

    setStagedItemsForVertical([...newStaged, draggedItem!]);
    setDraggedItem(null);
  };

  const executeMergeVertical = async (type: string) => {
    let uuidsToSend: string[] = [];
    stagedItemsForVertical.forEach(item => {
      if (item.isIntegration && item.source_note_ids) uuidsToSend.push(...item.source_note_ids);
      else uuidsToSend.push(item.note_uuid);
    });
    uuidsToSend = Array.from(new Set(uuidsToSend));

    if (uuidsToSend.length < 2) {
      message.warning('至少需要 2 条有效笔记才能合并');
      return;
    }

    setIsMerging(true);
    try {
      await api.post('/api/integrations', { note_uuids: uuidsToSend });
      message.success('同功能合并成功！');
      setStagedItemsForVertical([]);
      await fetchNotes();
    } catch (error) {
      message.error('合并失败');
    } finally {
      setIsMerging(false);
    }
  };

  const handleBatchDelete = (uuid?: string) => {
    const targets = uuid ? [uuid] : selectedUuids;

    Modal.confirm({
      title: '确认删除',
      content: `确定要将选中的 ${targets.length} 项移入回收站吗？`,
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          const noteUuidsToDelete = targets.filter(id => notes.some(n => n.note_uuid === id));
          const integrationUuidsToDelete = targets.filter(id => integrations.some(i => i.integration_uuid === id));

          await Promise.all([
            ...noteUuidsToDelete.map(id => api.delete(`/api/notes/${id}`)),
            ...integrationUuidsToDelete.map(id => api.delete(`/api/integrations/${id}`))
          ]);

          message.success('已移入回收站');
          setSelectedUuids([]);
          setIsMultiSelectMode(false);
          await fetchNotes();
        } catch (error) { message.error('删除失败'); }
      },
    });
  };

  const handleCancelIntegration = (uuid: string) => {
    Modal.confirm({
      title: '取消合并',
      content: '取消合并后，该整合记录会被销毁，原笔记将恢复为未合并状态。确认吗？',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await api.delete(`/api/integrations/${uuid}/cancel`);
          message.success('已取消合并');
          await fetchNotes();
        } catch (error) { message.error('取消合并失败'); }
      }
    });
  };

  const handleCardClick = (note: NoteItem) => {
    if (isMultiSelectMode) {
      setSelectedUuids(prev => prev.includes(note.note_uuid) ? prev.filter(id => id !== note.note_uuid) : [...prev, note.note_uuid]);
    } else {
      navigate(`/notes/${note.note_uuid}`);
    }
  };

  const formatTime = (isoString: string) => {
    if (!isoString) return '';
    const d = new Date(isoString);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  };

  const checkIsStaged = (uuid: string) => {
    const stagedUuids = stagedItemsForVertical.flatMap(i => i.isIntegration && i.source_note_ids ? i.source_note_ids : [i.note_uuid]);
    return stagedUuids.includes(uuid);
  };

  if (loading) return <div className="p-10 text-center text-gray-500">加载中...</div>;

  return (
    <div className="h-screen flex flex-col bg-green-50 overflow-hidden">
      {/* 顶部导航栏 */}
      <div className="flex items-center justify-between px-6 py-3 relative shrink-0 w-full max-w-7xl mx-auto">
        <div className="flex-1 flex justify-start">
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/')} className="text-lg text-gray-600 px-0">返回</Button>
        </div>

        <div className="flex-none">
          <div className="bg-green-200/60 backdrop-blur-md text-gray-800 px-10 py-1.5 rounded-full text-lg font-bold tracking-widest shadow-sm">我的笔记</div>
        </div>

        <div className="flex-1 flex justify-end items-center gap-3">
          {isMultiSelectMode && (
            <>
              <span className="text-gray-600 text-sm">已选 {selectedUuids.length} 项</span>
              <Button type="text" onClick={() => { setIsMultiSelectMode(false); setSelectedUuids([]); }}>取消</Button>
              <Button type="text" danger icon={<DeleteOutlined />} disabled={selectedUuids.length === 0} onClick={() => handleBatchDelete()} />
            </>
          )}
        </div>
      </div>

      {/* 主体四列布局 */}
      <div className="flex-1 overflow-x-auto px-6 pb-4 w-full">
        <div className="grid grid-cols-4 gap-4 h-full min-w-[1000px] max-w-7xl mx-auto">
          {NOTE_TYPES.map((col) => {
            const currentStaged = stagedItemsForVertical.filter(item => item.note_type === col.key);
            const currentRealUuids = currentStaged.flatMap(item =>
              item.isIntegration && item.source_note_ids ? item.source_note_ids : [item.note_uuid]
            );
            const uniqueRealUuids = Array.from(new Set(currentRealUuids));
            const realNoteItems = getNoteItemsFromUuids(uniqueRealUuids);
            const hasStaged = currentStaged.length > 0;

            return (
              <div key={col.key} className="flex flex-col h-full">
                {/* 列头 */}
                <div className={`${col.headerBg} backdrop-blur-sm text-gray-700 text-center py-2 rounded-2xl text-base shadow-sm font-medium shrink-0`}>
                  {col.label}
                </div>

                {/* 笔记列表（滚动区域） */}
                <div className="flex-1 overflow-y-auto py-3 flex flex-col gap-3 relative scrollbar-hide">
                  {notes
                    .filter(n => n.note_type === col.key)
                    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                    .map((note) => {
                    const isSelected = selectedUuids.includes(note.note_uuid);
                    const isStaged = checkIsStaged(note.note_uuid);
                    const inVertical = integrations.some(i => i.source_modules?.length === 1 && i.source_modules[0] === col.key && i.source_note_ids?.includes(note.note_uuid));

                    return (
                      <div
                        key={note.note_uuid}
                        draggable={!isMultiSelectMode}
                        onDragStart={(e) => handleDragStartNote(e, note)}
                        onClick={() => handleCardClick(note)}
                        className={`
                          relative h-[80px] rounded-xl flex flex-col justify-between p-3 cursor-pointer transition-all shrink-0
                          ${note.is_integrated ? 'bg-gray-200/80 text-gray-500' : `bg-white/70 text-gray-800 hover:bg-white/90 shadow-sm border border-white/50`}
                          ${isSelected ? 'ring-2 ring-green-500' : ''}
                          ${isStaged ? 'ring-2 ring-yellow-400 opacity-80' : ''}
                        `}
                      >
                        {/* 第一行：文件名 */}
                        <div className="text-[11px] text-gray-500 truncate w-full pr-6 font-semibold flex items-center gap-1">
                          📄 {note.file_name}
                        </div>

                        {/* 第二行：内容摘要 */}
                        <div className="text-sm font-medium truncate w-full my-1">
                          {note.content.replace(/[#*]/g, '').slice(0, 20)}...
                        </div>

                        {/* 第三行：修改时间 */}
                        <div className="text-[10px] text-gray-400 w-full text-right">
                          {formatTime(note.created_at)}
                        </div>

                        {!isMultiSelectMode && (
                          <div className="absolute top-2 right-2 z-10 pointer-events-auto">
                            <Dropdown
                              menu={{
                                items: [
                                  { key: 'multi', label: '多选', onClick: (e) => { e.domEvent.stopPropagation(); setIsMultiSelectMode(true); setSelectedUuids([note.note_uuid]); } },
                                  { key: 'delete', label: '删除', danger: true, onClick: (e) => { e.domEvent.stopPropagation(); handleBatchDelete(note.note_uuid); } },
                                ],
                              }}
                              trigger={['click']}
                            >
                              <MoreOutlined className="text-gray-400 p-1" onClick={e => e.stopPropagation()} />
                            </Dropdown>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* 👇 底部同功能合并区（固定在底部、更宽大、吸底） */}
                <div
                  className="shrink-0 p-1 flex flex-col relative z-20 mt-2"
                  onDragOver={handleDragOver}
                  onDrop={() => handleDropVertical(col.key)}
                >
                  {hasStaged ? (
                    <div className="rounded-xl border-2 border-dashed border-yellow-400 bg-yellow-50 p-3 flex flex-col gap-1 shadow-md min-h-[80px]">
                      <div className="text-[11px] text-yellow-600 font-bold mb-1">
                        已收集 {realNoteItems.length} 条笔记：
                      </div>
                      <div className="flex-1 overflow-y-auto max-h-[60px] flex flex-col gap-1">
                        {realNoteItems.map((item, idx) => (
                          <div key={idx} className="text-xs text-yellow-800 truncate bg-white px-2 py-1 rounded border border-yellow-100">
                            {item.file_name}
                          </div>
                        ))}
                      </div>
                      <div className="flex justify-between gap-2 mt-2">
                        <Button size="small" onClick={() => setStagedItemsForVertical([])} className="flex-1 text-gray-500 border-gray-300">清空</Button>
                        <Button
                          type="primary"
                          size="small"
                          onClick={() => executeMergeVertical(col.key)}
                          disabled={realNoteItems.length < 2}
                          className="flex-1 bg-green-600 hover:bg-green-500 border-none"
                        >
                          确认合并
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      {integrations
                        .filter(i => i.source_modules?.length === 1 && i.source_modules[0] === col.key)
                        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                        .map((integ) => {
                        const isSelected = selectedUuids.includes(integ.integration_uuid);
                        const sourceFiles = integ.source_note_ids.map(id => {
                          const foundNote = notes.find(n => n.note_uuid === id);
                          return foundNote ? foundNote.file_name : '未知文件';
                        });
                        const uniqueFiles = Array.from(new Set(sourceFiles));

                        return (
                          <div
                            key={integ.integration_uuid}
                            draggable={!isMultiSelectMode}
                            onDragStart={(e) => { if (isMultiSelectMode) { e.preventDefault(); return; } handleDragStartIntegration(e, integ); }}
                            onClick={() => {
                              if (isMultiSelectMode) {
                                setSelectedUuids(prev => prev.includes(integ.integration_uuid) ? prev.filter(id => id !== integ.integration_uuid) : [...prev, integ.integration_uuid]);
                              } else {
                                navigate(`/notes/${integ.integration_uuid}`);
                              }
                            }}
                            className={`
                              relative h-[80px] shrink-0 rounded-xl flex flex-col items-start justify-center p-3 cursor-pointer transition-all mb-2 bg-white border border-green-200 text-gray-700 hover:shadow-md
                              ${isSelected ? 'ring-2 ring-green-500' : ''}
                            `}
                          >
                            <div className="w-full pr-6 pointer-events-none">
                              <div className="text-[11px] text-green-600 font-bold mb-1">同功能整合：</div>
                              <div className="text-[10px] text-gray-500 flex flex-col gap-0.5 line-clamp-2">
                                {uniqueFiles.map((name, idx) => (
                                  <span key={idx} className="truncate">📄 {name}</span>
                                ))}
                              </div>
                            </div>
                            <div className="text-[10px] text-gray-400 mt-1 w-full text-right pointer-events-none">
                              {formatTime(integ.created_at)}
                            </div>

                            {!isMultiSelectMode && (
                              <div className="absolute top-2 right-2 z-10 pointer-events-auto">
                                <Dropdown
                                  menu={{
                                    items: [
                                      { key: 'multi', label: '多选', onClick: (e) => { e.domEvent.stopPropagation(); setIsMultiSelectMode(true); setSelectedUuids([integ.integration_uuid]); } },
                                      { key: 'delete', label: '删除', danger: true, onClick: (e) => { e.domEvent.stopPropagation(); handleBatchDelete(integ.integration_uuid); } },
                                      { key: 'cancel', label: '取消合并', onClick: (e) => { e.domEvent.stopPropagation(); handleCancelIntegration(integ.integration_uuid); } },
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

                      {integrations.filter(i => i.source_modules?.length === 1 && i.source_modules[0] === col.key).length === 0 && (
                        <div className="min-h-[80px] rounded-xl border-2 border-dashed border-green-300 bg-green-100/50 flex flex-col items-center justify-center text-green-600 transition-colors hover:bg-green-200/50 shrink-0 pointer-events-none">
                          <span className="font-bold text-sm">同功能合并</span>
                          <span className="text-[11px] opacity-70 mt-1">拖入本列笔记</span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {isMerging && (
        <div className="fixed inset-0 bg-white/80 z-50 flex flex-col items-center justify-center backdrop-blur-sm">
          <Spin size="large" />
          <div className="mt-4 text-lg font-medium text-teal-600">AI 正在深度整合笔记，请稍候...</div>
        </div>
      )}
    </div>
  );
}
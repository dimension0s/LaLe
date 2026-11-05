import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { message, Button, Spin, Tooltip } from 'antd';
import { ArrowLeftOutlined, SunOutlined, MoonOutlined, EditOutlined, SaveOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../api/axios';

interface NoteDetailData {
  note_uuid: string;
  note_type_label: string;
  file_name: string;
  content: string;
  created_at: string;
}

export default function NoteDetail() {
  const { note_uuid } = useParams<{ note_uuid: string }>();
  const navigate = useNavigate();

  const [note, setNote] = useState<NoteDetailData | null>(null);
  const [loading, setLoading] = useState(true);

  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        const res = await api.get(`/api/notes/${note_uuid}`);
        setNote(res);
        setEditContent(res.content);
      } catch (error) {
        try {
          const res = await api.get(`/api/integrations/${note_uuid}`);
          setNote({
            note_uuid: res.integration_uuid,
            note_type_label: res.source_modules?.join('+') || '整合',
            file_name: '整合笔记',
            content: res.content,
            created_at: res.created_at
          });
          setEditContent(res.content);
        } catch (e) {
          message.error('无法加载笔记详情');
          navigate(-1);
        }
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [note_uuid, navigate]);

  const handleSave = async () => {
    if (!editContent.trim()) {
      message.warning('内容不能为空');
      return;
    }
    setSaving(true);
    try {
      await api.patch(`/api/notes/${note_uuid}`, { content: editContent });
      setNote(prev => prev ? { ...prev, content: editContent } : null);
      setIsEditing(false);
      message.success('保存成功');
    } catch (error) {
      message.error('保存失败，整合笔记暂不支持编辑');
    } finally {
      setSaving(false);
    }
  };

  const toggleEdit = () => {
    if (isEditing) {
      if (editContent !== note?.content) {
        if (window.confirm('有未保存的修改，确定放弃吗？')) {
          setEditContent(note?.content || '');
          setIsEditing(false);
        }
      } else {
        setIsEditing(false);
      }
    } else {
      setIsEditing(true);
    }
  };

  const getSummaryTitle = () => {
    if (!note) return '';
    const cleanText = note.content.replace(/[#*`\-\[\]]/g, '').trim();
    return cleanText.slice(0, 15) + (cleanText.length > 15 ? '...' : '');
  };

  if (loading) return <div className="h-screen flex items-center justify-center"><Spin size="large" /></div>;
  if (!note) return null;

  return (
    <div className={`h-screen flex flex-col transition-colors duration-300 ${isDarkMode ? 'bg-[#1e1e1e] text-gray-300' : 'bg-[#fcfcfc] text-gray-800'}`}>

      {/* 顶部导航与标题 */}
      <div className="flex items-center justify-between px-8 py-4 shrink-0 relative">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} className={isDarkMode ? 'text-gray-300' : 'text-gray-600'}>返回</Button>

        <div className="absolute left-1/2 -translate-x-1/2">
          <div className={`px-12 py-2 rounded-full text-md font-bold tracking-widest truncate max-w-[600px] ${isDarkMode ? 'bg-[#2d2d2d] text-green-400' : 'bg-[#a7f3d0] text-teal-800'}`}>
            {note.file_name} - {getSummaryTitle()}
          </div>
        </div>

        <div className="w-[100px]"></div>
      </div>

      {/* 主体阅读区：外层撑满，内部白板固定宽度并居中 */}
      <div className="flex-1 overflow-hidden px-8 pb-8 relative flex justify-center">

        {/* 👇 收窄的白板容器：设置了 max-w-5xl 和相对定位 */}
        <div className={`w-full max-w-5xl rounded-2xl border p-10 overflow-y-auto relative shadow-sm h-full ${isDarkMode ? 'bg-[#252526] border-[#333]' : 'bg-white border-gray-200'}`}>

          <div className="w-full h-full">
            {isEditing ? (
              <textarea
                className={`w-full h-full min-h-[60vh] bg-transparent outline-none resize-none font-mono text-[16px] leading-relaxed ${isDarkMode ? 'text-gray-200' : 'text-gray-800'}`}
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                placeholder="在此输入 Markdown 内容..."
              />
            ) : (
              /* 纯阅读模式：文字左对齐，自适应容器宽度 */
              <div className="prose dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {note.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </div>

      </div>

      {/* 👇 右侧功能图标：脱离文档流，绝对定位在屏幕右侧，不和白板抢空间 */}
      <div className={`absolute right-8 top-1/2 -translate-y-1/2 w-16 flex flex-col items-center gap-6`}>
        <Tooltip title="切换深色/浅色模式" placement="left">
          <div
            className={`w-12 h-12 rounded-full flex items-center justify-center cursor-pointer shadow-md transition-all ${isDarkMode ? 'bg-[#333] text-yellow-400' : 'bg-white text-gray-600'}`}
            onClick={() => setIsDarkMode(!isDarkMode)}
          >
            {isDarkMode ? <SunOutlined className="text-xl" /> : <MoonOutlined className="text-xl" />}
          </div>
        </Tooltip>

        <Tooltip title="编辑内容" placement="left">
          <div
            className={`w-12 h-12 rounded-full flex items-center justify-center cursor-pointer shadow-md transition-all ${isEditing ? 'bg-[#f59e0b] text-white' : (isDarkMode ? 'bg-[#333] text-gray-300' : 'bg-white text-gray-600')}`}
            onClick={toggleEdit}
          >
            <EditOutlined className="text-xl" />
          </div>
        </Tooltip>

        <Tooltip title="保存修改" placement="left">
          <div
            className={`w-12 h-12 rounded-full flex items-center justify-center cursor-pointer shadow-md transition-all ${isEditing ? 'bg-[#10b981] text-white' : 'opacity-50 cursor-not-allowed ' + (isDarkMode ? 'bg-[#333]' : 'bg-gray-100')}`}
            onClick={isEditing ? handleSave : undefined}
          >
            {saving ? <Spin size="small" /> : <SaveOutlined className="text-xl" />}
          </div>
        </Tooltip>
      </div>

    </div>
  );
}
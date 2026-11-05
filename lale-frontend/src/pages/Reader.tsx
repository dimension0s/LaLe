import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { message, Button, Spin, Divider, Tag, Input } from 'antd';
import { ArrowLeftOutlined, BookOutlined, SelectOutlined } from '@ant-design/icons';
import api from '../api/axios';
import PdfViewer from '../components/PdfViewer';
import WordPanel from '../components/WordPanel';
import AnalysisPanel from '../components/AnalysisPanel';
import { useUserStore } from '../store/useUserStore';


interface DocInfo {
  doc_uuid: string;
  doc_id: number;
  file_name: string;
  file_type: string;
  user_id: number;
  meta?: { ocr_text?: string; };
}

export default function Reader() {
  const { doc_uuid } = useParams<{ doc_uuid: string }>();
  const navigate = useNavigate();
  const { user } = useUserStore();

  const [doc, setDoc] = useState<DocInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedText, setSelectedText] = useState('');

  // 面板固定宽度
  const leftWidth = 260;
  const rightWidth = 280;

  // 中间阅读区宽度
  const mainContainerRef = useRef<HTMLDivElement>(null);
  const [availableWidth, setAvailableWidth] = useState(800);

  // 👇 框选模式状态
  const [enableBoxSelect, setEnableBoxSelect] = useState(false);

  // 交互状态
  const [currentAction, setCurrentAction] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionResult, setActionResult] = useState<any>(null);

  useEffect(() => {
    const fetchDoc = async () => {
      try {
        const data = await api.get(`/api/documents/${doc_uuid}`);
        setDoc(data as DocInfo);
      } catch (error) {
        message.error('无法加载文档');
        navigate('/documents');
      } finally {
        setLoading(false);
      }
    };
    fetchDoc();
  }, [doc_uuid, navigate]);

  // 监听屏幕变化，精准计算可用宽度（极致铺满）
  useEffect(() => {
    const updateWidth = () => {
      if (mainContainerRef.current) {
        // 👇 核心修改：几乎不减去任何留白，只减去 8px 防止滚动条遮挡
        const width = mainContainerRef.current.clientWidth - 8;
        setAvailableWidth(width > 300 ? width : 300);
      }
    };

    const timer = setTimeout(updateWidth, 100);
    window.addEventListener('resize', updateWidth);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', updateWidth);
    };
  }, []);

  const handleSelectText = (text: string) => setSelectedText(text);

  const handleAction = async (actionType: string) => {
    if (!selectedText) return message.warning('请先在文中用鼠标选中要处理的文字');

    setCurrentAction(actionType);
    setActionLoading(true);
    setActionResult(null);

    try {
      let res;
      if (actionType === '查词') res = await api.post('/api/dictionary/lookup', { word: selectedText });
      else if (actionType === '翻译') res = await api.post('/api/translation', { text: selectedText });
      else if (actionType === '语法解析') res = await api.post('/api/nlp/grammar', { text: selectedText });
      else if (actionType === '短语/搭配') res = await api.post('/api/nlp/phrase', { text: selectedText });
      else if (actionType === '术语') res = await api.post('/api/nlp/terminology', { text: selectedText });

      setActionResult(res);
    } catch (error) {
      setCurrentAction(null);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <div className="h-screen flex items-center justify-center"><Spin size="large" /></div>;
  if (!doc) return null;

  const currentUserId = doc.user_id || user?.id || 3;
  const API_BASE = 'http://localhost:8000';
  const fileUrl = `${API_BASE}/uploads/${currentUserId}/${encodeURIComponent(doc.file_name)}`;

  const isWordMode = currentAction === '查词';

  return (
    <div className="h-screen flex flex-col bg-[#fcfcfc] overflow-hidden select-none">
      {/* 头部菜单 */}
      <header className="flex flex-col bg-white shadow-sm z-20 shrink-0">
        <div className="flex items-center px-6 py-3 border-b border-gray-100 relative">
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/documents')}>返回书架</Button>
          <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-2 text-md font-medium text-gray-700 bg-gray-50 px-4 py-1 rounded-md max-w-[40%]">
            <BookOutlined className="text-gray-400" />
            <span className="truncate">{doc.file_name}</span>
          </div>
        </div>

        <div className="flex items-center justify-center gap-4 px-6 py-3">
          {['查词', '翻译', '语法解析', '短语/搭配', '术语'].map((action) => (
             <div key={action} className="flex items-center">
               <Button
                  type="text"
                  onClick={() => handleAction(action)}
                  className={`text-lg font-medium ${currentAction === action ? 'text-blue-600 bg-blue-50' : ''}`}
                >
                  {action}
                </Button>
                {action !== '术语' && <Divider type="vertical" className="bg-gray-300" />}
             </div>
          ))}

          {/* 框选模式开关 */}
          <div className="flex items-center ml-8">
            <Button
              type={enableBoxSelect ? "primary" : "default"}
              icon={<SelectOutlined />}
              onClick={() => {
                setEnableBoxSelect(!enableBoxSelect);
                setSelectedText('');
              }}
              className={enableBoxSelect ? "bg-[#10b981]" : "border-green-500 text-green-600"}
            >
              {enableBoxSelect ? '框选已开启' : '开启框选'}
            </Button>
          </div>
        </div>

        {selectedText && (
        <div className="bg-yellow-50 px-6 py-2 text-sm text-gray-600 flex items-center justify-center gap-3 border-b border-yellow-100">
            <Tag color="warning" className="shrink-0">已选中（可修改）</Tag>
            <Input
              value={selectedText}
              onChange={(e) => setSelectedText(e.target.value)}
              className="max-w-[60%] border-yellow-200 bg-white/70 text-gray-800"
              placeholder="可在此修改提取到的文字"
              allowClear
            />
            <div className="text-xs text-gray-400 shrink-0">修改后点击上方功能生效</div>
          </div>
        )}
      </header>

      {/* 主体三栏布局 */}
      <div className="flex-1 flex overflow-hidden">

        {/* 左侧查词面板 */}
        <aside
          className={`bg-white border-r border-gray-100 overflow-hidden hidden md:flex flex-col shrink-0 ${isWordMode ? '' : 'opacity-50'}`}
          style={{ width: `${leftWidth}px` }}
        >
           <div className="flex-1 overflow-y-auto">
             {isWordMode && actionLoading ? (
               <div className="h-full flex items-center justify-center"><Spin tip="查询中..." /></div>
             ) : isWordMode && actionResult ? (
               <WordPanel data={actionResult} word={selectedText} />
             ) : (
               <div className="text-gray-400 text-center mt-20 text-sm">选中文字后，点击顶部【查词】</div>
             )}
           </div>
        </aside>

        {/* 👇 中间阅读区：取消内边距，让 PDF 极致铺满 */}
        <main ref={mainContainerRef} className="flex-1 overflow-y-auto relative bg-[#f3f4f6]">
          {doc.file_type === 'pdf' ? (
            <PdfViewer
              fileUrl={fileUrl}
              onSelectText={handleSelectText}
              containerWidth={availableWidth}
              enableBoxSelect={enableBoxSelect}
            />
          ) : doc.file_type === 'image' ? (
            <div className="flex justify-center w-full">
               <img src={fileUrl} alt={doc.file_name} className="shadow-lg" style={{ width: availableWidth }} />
            </div>
          ) : (
            <div className="w-full flex justify-center py-4">
              <div className="w-full" style={{ width: availableWidth }}>
                <div className="text-[18px] leading-[1.8] text-gray-800 whitespace-pre-wrap selection:bg-blue-100">
                  {doc.meta?.ocr_text || '暂无文本内容'}
                </div>
              </div>
            </div>
          )}
        </main>

        {/* 右侧解析面板 */}
        <aside
          className={`bg-white border-l border-gray-100 overflow-hidden hidden lg:flex flex-col shrink-0 ${!isWordMode && currentAction ? '' : 'opacity-50'}`}
          style={{ width: `${rightWidth}px` }}
        >
           <div className="flex-1 overflow-y-auto">
             {!isWordMode && currentAction && actionLoading ? (
               <div className="h-full flex items-center justify-center"><Spin tip="AI 解析中..." /></div>
             ) : !isWordMode && currentAction && actionResult ? (
               <AnalysisPanel
                  mode={currentAction === '翻译' ? 'translation' : currentAction === '语法解析' ? 'grammar' : currentAction === '短语/搭配' ? 'phrase' : 'terminology'}
                  data={actionResult}
                  originalText={selectedText}
                  documentId={doc.doc_id}
               />
             ) : (
               <div className="text-gray-400 text-center mt-20 text-sm">选中文字后，点击顶部【翻译/解析】</div>
             )}
           </div>
        </aside>
      </div>
    </div>
  );
}
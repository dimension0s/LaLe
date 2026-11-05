import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUserStore } from '../store/useUserStore';
import { message, Button, Avatar, Dropdown, Spin, Modal, Input, Upload } from 'antd';
import { UserOutlined, UploadOutlined } from '@ant-design/icons';
import api from '../api/axios';
import { uploadFileApi } from '../api/upload';
import { updateNicknameApi, uploadAvatarApi } from '../api/user';

// 👇 导入背景图片（请根据你的实际路径调整，这里假设在 src/assets/ 下）
import skyImg from '../assets/sky.jpg';
import oceanImg from '../assets/ocean.jpg';
import riverImg from '../assets/river.jpg';
import grassImg from '../assets/grass.jpg';
import desertImg from '../assets/desert.jpg';
import lakeImg from '../assets/lake.jpg';

const BACKGROUNDS = [skyImg, oceanImg, riverImg, grassImg, desertImg, lakeImg];

interface Stats {
  files: number;
  notes: number;
  vocabulary: number;
  recycle: number;
}

export default function Dashboard() {
  const { user, setAuth, token, logout } = useUserStore();
  const navigate = useNavigate();

  // 背景轮播状态
  const [bgIndex, setBgIndex] = useState(0);

  // 数据统计
  const [stats, setStats] = useState<Stats>({ files: 0, notes: 0, vocabulary: 0, recycle: 0 });
  const [loading, setLoading] = useState(false);

  // 上传状态
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);


  // 弹窗状态
  const [isAvatarModalOpen, setIsAvatarModalOpen] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [previewAvatarUrl, setPreviewAvatarUrl] = useState('');
  const [isNicknameModalOpen, setIsNicknameModalOpen] = useState(false);
  const [newNickname, setNewNickname] = useState('');
  const [saving, setSaving] = useState(false);

  // 邮箱状态
  const [isEmailModalOpen, setIsEmailModalOpen] = useState(false);
  const [bindEmail, setBindEmail] = useState('');
  const [emailCode, setEmailCode] = useState('');
  const [emailLoading, setEmailLoading] = useState(false);
  const [countdown, setCountdown] = useState(0);

  // 注销状态
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);

  // 登录状态
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [phone, setPhone] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  // 监听鼠标滚动切换背景
  useEffect(() => {
    const handleWheel = (e: WheelEvent) => {
      // 防止在输入框或弹窗里滚动时触发背景切换
      if ((e.target as HTMLElement).closest('input, textarea, .ant-modal')) return;

      if (e.deltaY > 0) {
        setBgIndex((prev) => (prev + 1) % BACKGROUNDS.length);
      } else {
        setBgIndex((prev) => (prev - 1 + BACKGROUNDS.length) % BACKGROUNDS.length);
      }
    };
    window.addEventListener('wheel', handleWheel);
    return () => window.removeEventListener('wheel', handleWheel);
  }, []);

  const fetchStats = async () => {
    if (!token) return;
    try {
      const data = await api.get('/api/dashboard/stats');
      setStats(data as Stats);
    } catch (error) {
      message.error('获取数据统计失败');
    }
  };

  useEffect(() => {
    if (token) {
      setLoading(true);
      fetchStats().finally(() => setLoading(false));
    }
  }, [token]);

  const handleLogout = () => { logout(); window.location.href = '/'; };

  // 新增登录处理逻辑
  const handleLogin = async () => {
    if (!/^\d{11}$/.test(phone)) {
      return message.warning('请输入正确的 11 位手机号');
    }
    setLoginLoading(true);
    try {
      const data = await api.post('/api/auth/login', { phone_number: phone, code: null });
      setAuth(data.token, data.user);
      message.success(data.is_new_user ? '欢迎加入，已为您自动创建账号！' : '欢迎回来！');
      setIsLoginModalOpen(false);
      setPhone('');
      fetchStats(); // 登录成功后立刻刷新统计数据
    } catch (error) {
      message.error('登录失败，请稍后重试');
    } finally {
      setLoginLoading(false);
    }
  };

  // 拦截未登录用户
  const requireAuth = (action: () => void) => {
    if (!token) {
      Modal.confirm({
        title: '需要登录',
        content: '该功能需要登录后才能使用，是否现在前往登录？',
        okText: '去登录',
        cancelText: '取消',
        onOk: () => {
          // 👈 不再跳转页面，直接打开登录卡片
          setIsLoginModalOpen(true);
        },
      });
      return;
    }
    action();
  };

  // 上传逻辑（同之前，不变）
  const handleUploadClick = () => {
    requireAuth(() => fileInputRef.current?.click());
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const allowedExts = ['.pdf', '.txt', '.md', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'];
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!allowedExts.includes(ext)) {
      message.error('不支持的文件格式');
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }
    setIsUploading(true);
    try {
      await uploadFileApi(file);
      Modal.confirm({
        title: '上传成功',
        content: '文件已成功解析入库，是否现在前往“我的文件”查看？',
        okText: '去看看',
        cancelText: '留在主页',
        onOk: () => navigate('/documents'),
        onCancel: () => fetchStats(),
      });
    } catch (error) {
      message.error('上传失败，请稍后重试');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // 头像上传逻辑（同之前）
  const handleAvatarUpload = async (file: File) => {
    const isImage = file.type.startsWith('image/');
    if (!isImage) return message.error('只能上传图片文件');
    if (file.size / 1024 / 1024 > 2) return message.error('图片大小不能超过 2MB');
    setAvatarUploading(true);
    try {
      const res = await uploadAvatarApi(file);
      const newUrl = res.avatar_url;
      setPreviewAvatarUrl(newUrl);
      if (user && token) setAuth(token, { ...user, avatar_url: newUrl });
      message.success('头像上传成功');
      setIsAvatarModalOpen(false);
    } catch (error) {
      message.error('头像上传失败');
    } finally {
      setAvatarUploading(false);
    }
  };
  const beforeAvatarUpload = (file: File) => { handleAvatarUpload(file); return false; };

  // 昵称、邮箱、注销逻辑（同之前）
  const handleSaveNickname = async () => {
    if (!newNickname.trim()) return message.warning('昵称不能为空');
    setSaving(true);
    try {
      await updateNicknameApi(newNickname.trim());
      message.success('昵称修改成功');
      if (user && token) setAuth(token, { ...user, nickname: newNickname.trim() });
      setIsNicknameModalOpen(false);
    } catch (error) { message.error('修改失败'); } finally { setSaving(false); }
  };

  const handleSendEmailCode = async () => {
    if (!bindEmail || !bindEmail.includes('@')) return message.warning('请输入正确的邮箱格式');
    setEmailLoading(true);
    try {
      await api.post('/api/account/email/send_code', { email: bindEmail });
      message.success('验证码已发送，请查收邮箱');
      setCountdown(60);
      const timer = setInterval(() => {
        setCountdown((prev) => { if (prev <= 1) { clearInterval(timer); return 0; } return prev - 1; });
      }, 1000);
    } catch (error) { message.error('发送失败'); } finally { setEmailLoading(false); }
  };

  const handleVerifyEmail = async () => {
    if (!emailCode) return message.warning('请输入验证码');
    setEmailLoading(true);
    try {
      await api.post('/api/account/email/verify', { email: bindEmail, code: emailCode });
      message.success('邮箱绑定成功');
      if (user && token) setAuth(token, { ...user, email: bindEmail });
      setIsEmailModalOpen(false);
    } catch (error) { message.error('验证码错误或已过期'); } finally { setEmailLoading(false); }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmText !== '确认注销') return message.warning('请输入“确认注销”以继续');
    setDeleteLoading(true);
    try {
      await api.delete('/api/account');
      message.success('账号已彻底删除');
      logout();
      // 硬刷新回首页
      window.location.href = '/';
    } catch (error) { message.error('注销失败'); setDeleteLoading(false); }
  };

  return (
    <div
      className="h-screen w-full relative overflow-hidden flex flex-col items-center justify-center bg-cover bg-center transition-all duration-1000 ease-in-out"
      style={{ backgroundImage: `url(${BACKGROUNDS[bgIndex]})` }}
    >
      {/* 阴影遮罩，防止背景过亮影响白色文字阅读 */}
      <div className="absolute inset-0 bg-black/10 backdrop-blur-[1px]"></div>

      {/* 👇 顶部栏：左上角上传、右上角登录/头像 */}
      <div className="absolute top-6 left-6 right-6 flex justify-between items-center z-10">

                {/* 左上角：上传（带悬停提示） */}
        <div className="relative group">
          <Upload
            showUploadList={false}
            beforeUpload={(file) => {
              // 如果未登录，在这里拦截
              if (!token) {
                Modal.confirm({
                  title: '需要登录',
                  content: '上传功能需要登录后才能使用，是否现在前往登录？',
                  okText: '去登录',
                  cancelText: '取消',
                  onOk: () => setIsLoginModalOpen(true),
                });
                return Upload.LIST_IGNORE; // 阻止上传
              }

              // 校验格式
              const allowedExts = ['.pdf', '.txt', '.md', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'];
              const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
              if (!allowedExts.includes(ext)) {
                message.error('不支持的文件格式');
                return Upload.LIST_IGNORE;
              }

              // 执行真正的上传逻辑
              handleFileChange({ target: { files: [file] } } as any);
              return Upload.LIST_IGNORE; // 阻止 Antd 的默认上传行为
            }}
          >
            <Button
              className="bg-white/40 backdrop-blur-md border-none shadow-sm text-gray-800 font-medium hover:bg-white/60 transition-all rounded-full px-6 h-10 text-lg"
              disabled={isUploading}
            >
              <UploadOutlined /> {isUploading ? '解析中...' : '上传文件'}
            </Button>
          </Upload>

          {/* 悬停提示 */}
          <div className="absolute top-full left-0 mt-2 w-max px-3 py-1.5 bg-black/60 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
            支持格式：PDF, DOCX, TXT, 图片等
          </div>
        </div>

        {/* 右上角：登录 / 用户信息 */}
        {token ? (
          <Dropdown
            menu={{
              items: [
                { key: '1', label: '修改头像', onClick: () => { setPreviewAvatarUrl(user?.avatar_url || ''); setIsAvatarModalOpen(true); } },
                { key: '2', label: '修改昵称', onClick: () => { setNewNickname(user?.nickname || ''); setIsNicknameModalOpen(true); } },
                { key: '3', label: user?.email ? `已绑定：${user.email}` : '绑定邮箱', onClick: () => {
                    if (user?.email) return message.info('您已绑定邮箱，请勿重复绑定');
                    setBindEmail(''); setEmailCode(''); setIsEmailModalOpen(true);
                }},
                { key: '4', label: '绑定微信', onClick: () => {
                    Modal.info({ title: '暂未开放', content: '微信绑定需要企业资质认证，当前开发阶段暂未开放。', okText: '知道了' });
                }},
                { type: 'divider' },
                { key: '5', label: '退出登录', onClick: handleLogout, danger: true },
                { key: '6', label: '注销账号', danger: true, onClick: () => { setDeleteConfirmText(''); setIsDeleteModalOpen(true); } },
              ],
            }}
            trigger={['hover', 'click']} // 👈 鼠标悬停或点击触发
          >
            <div className="flex items-center gap-3 cursor-pointer bg-white/40 backdrop-blur-md rounded-full py-1 pr-4 pl-1 shadow-sm hover:bg-white/60 transition-all">
              <Avatar src={user?.avatar_url || undefined} icon={<UserOutlined />} className="bg-gray-400" size="large" />
              <span className="text-gray-800 font-medium">{user?.nickname || '用户'}</span>
            </div>
          </Dropdown>
        ) : (
          <Button
            className="bg-white/40 backdrop-blur-md border-none shadow-sm text-gray-800 font-medium hover:bg-white/60 transition-all rounded-full px-8 h-10 text-lg"
            onClick={() => setIsLoginModalOpen(true)}
          >
            登录
          </Button>
        )}
      </div>

      {/* 👇 中间：四张毛玻璃卡片 */}
      <div className="grid grid-cols-2 gap-8 z-10 relative mt-8">
        <ModuleCard title="我的文件" count={stats.files} onClick={() => requireAuth(() => navigate('/documents'))} loading={loading} />
        <ModuleCard title="我的笔记" count={stats.notes} onClick={() => requireAuth(() => navigate('/notes'))} loading={loading} />
        <ModuleCard title="生词本" count={stats.vocabulary} onClick={() => requireAuth(() => navigate('/vocabulary'))} loading={loading} />
        <ModuleCard title="回收站" count={stats.recycle} onClick={() => requireAuth(() => navigate('/recycle'))} loading={loading} />
      </div>

      {/* 👇 底部：轮播指示器 */}
      <div className="absolute bottom-10 flex gap-3 z-10">
        {BACKGROUNDS.map((_, idx) => (
          <div
            key={idx}
            className={`w-3 h-3 rounded-full transition-all cursor-pointer ${bgIndex === idx ? 'bg-white scale-125 shadow-md' : 'bg-white/40 hover:bg-white/60'}`}
            onClick={() => setBgIndex(idx)}
          />
        ))}
      </div>

      {/* 下面保留之前的各种 Modal 弹窗（头像、昵称、邮箱、注销） */}
      {/* 1. 修改头像弹窗 */}
      <Modal title="修改头像" open={isAvatarModalOpen} onCancel={() => setIsAvatarModalOpen(false)} footer={null}>
        <div className="py-8 flex flex-col items-center justify-center">
          <input type="file" id="avatar-upload" className="hidden" accept="image/*" onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleAvatarUpload(file);
          }} />
          <div
            className="w-32 h-32 rounded-full bg-gray-100 flex items-center justify-center cursor-pointer overflow-hidden border border-gray-200 hover:border-blue-500 transition-colors"
            onClick={() => document.getElementById('avatar-upload')?.click()}
          >
            {previewAvatarUrl ? (
              <img src={previewAvatarUrl} alt="avatar" className="w-full h-full object-cover" />
            ) : (
              <div className="flex flex-col items-center text-gray-400">
                {avatarUploading ? <Spin /> : <UserOutlined className="text-3xl mb-2" />}
                <div className="text-sm">上传新头像</div>
              </div>
            )}
          </div>
          <div className="mt-4 text-gray-400 text-xs">支持 JPG, PNG, WEBP 等格式，大小不超过 2MB</div>
        </div>
      </Modal>

      {/* 2. 修改昵称弹窗 */}
      <Modal title="修改昵称" open={isNicknameModalOpen} onOk={handleSaveNickname} onCancel={() => setIsNicknameModalOpen(false)} confirmLoading={saving} okText="保存" cancelText="取消">
        <div className="py-4">
          <Input placeholder="请输入新昵称（最多 100 字符）" value={newNickname} onChange={(e) => setNewNickname(e.target.value)} maxLength={100} />
        </div>
      </Modal>

      {/* 3. 绑定邮箱弹窗 */}
      <Modal title="绑定邮箱" open={isEmailModalOpen} onCancel={() => setIsEmailModalOpen(false)} footer={null}>
        <div className="py-4 flex flex-col gap-4">
          <div>
            <div className="text-gray-500 text-sm mb-2">邮箱地址：</div>
            <div className="flex gap-2">
              <Input placeholder="请输入常用邮箱" value={bindEmail} onChange={(e) => setBindEmail(e.target.value)} disabled={countdown > 0} />
              <Button type="primary" onClick={handleSendEmailCode} loading={emailLoading} disabled={countdown > 0} className="bg-[#10b981]">
                {countdown > 0 ? `${countdown}s 后重发` : '发送验证码'}
              </Button>
            </div>
          </div>
          <div>
            <div className="text-gray-500 text-sm mb-2">验证码：</div>
            <Input placeholder="请输入 6 位验证码" value={emailCode} onChange={(e) => setEmailCode(e.target.value)} maxLength={6} />
          </div>
          <Button type="primary" block size="large" onClick={handleVerifyEmail} loading={emailLoading} disabled={!bindEmail || !emailCode} className="mt-2 bg-[#10b981]">
            确认绑定
          </Button>
        </div>
      </Modal>

      {/* 4. 注销账号弹窗 */}
      <Modal
        title={<span className="text-red-500 font-bold">⚠️ 注销账号（物理删除）</span>}
        open={isDeleteModalOpen}
        onCancel={() => setIsDeleteModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setIsDeleteModalOpen(false)}>取消</Button>,
          <Button key="delete" danger type="primary" loading={deleteLoading} disabled={deleteConfirmText !== '确认注销'} onClick={handleDeleteAccount}>确认注销</Button>,
        ]}
      >
        <div className="py-4">
          <div className="text-gray-700 mb-4 leading-relaxed">
            此操作将<strong className="text-red-500">永久删除</strong>您的账号以及名下的所有：
            <ul className="list-disc pl-6 mt-2 mb-4 text-gray-600">
              <li>上传的文档和文件</li>
              <li>所有的笔记、翻译和整合记录</li>
              <li>生词本及回收站数据</li>
            </ul>
            数据一旦删除将<strong className="text-red-500">无法恢复</strong>！
          </div>
          <div className="text-sm font-medium mb-2">请输入 <code className="bg-gray-100 px-1 rounded">确认注销</code> 以继续：</div>
          <Input status="error" placeholder="确认注销" value={deleteConfirmText} onChange={(e) => setDeleteConfirmText(e.target.value)} />
        </div>
      </Modal>

      {/* 用原生 div 替代 Modal，彻底摆脱 Antd 的默认白底 */}
      {isLoginModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          {/* 遮罩层（带毛玻璃效果） */}
          <div
            className="absolute inset-0 bg-black/30 backdrop-blur-sm transition-opacity"
            onClick={() => setIsLoginModalOpen(false)}
          ></div>

          {/* 弹窗主体（毛玻璃白底） */}
          <div className="relative z-10 w-[360px] bg-white/70 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-white/50 flex flex-col items-center animate-[fadeIn_0.2s_ease-out]">

            {/* 标题 */}
            <div className="bg-white/60 px-6 py-2 rounded-full text-xl font-bold tracking-widest text-gray-700 mb-8 shadow-sm">
              手机号一键登录
            </div>

            {/* 手机号输入框 */}
            <div className="w-full relative mb-6">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 z-10 font-medium">
                手机号：
              </span>
              <input
                type="text"
                className="w-full h-12 pl-[72px] pr-4 rounded-xl border border-gray-300 outline-none bg-white/80 text-gray-800 text-lg transition-all"
                placeholder="请输入 11 位手机号"
                maxLength={11}
                value={phone}
                onChange={(e) => setPhone(e.target.value.replace(/\D/g, ''))}
                onKeyDown={(e) => { if (e.key === 'Enter') handleLogin(); }}
              />
            </div>

            {/* 确认按钮 */}
            <Button
              type="primary"
              size="large"
              loading={loginLoading}
              onClick={handleLogin}
              className="w-full h-12 rounded-xl text-lg mt-2 shadow-none border-none"
              style={{ backgroundColor: '#a3e4d7', color: '#333', fontWeight: 500 }}
            >
              确认
            </Button>

            {/* 暂不登录 */}
            <div
              className="mt-4 text-gray-500 text-sm cursor-pointer hover:text-gray-800 transition-colors"
              onClick={() => setIsLoginModalOpen(false)}
            >
              暂不登录
            </div>
          </div>
        </div>
      )}

      {/* 全局上传遮罩 */}
      {isUploading && (
        <div className="fixed inset-0 bg-white/60 z-50 flex flex-col items-center justify-center backdrop-blur-md">
          <Spin size="large" />
          <div className="mt-4 text-lg font-medium text-teal-600">正在上传并解析文件...</div>
        </div>
      )}
    </div>
  );
}

// 卡片组件（改造为毛玻璃）
function ModuleCard({ title, count, onClick, loading }: { title: string; count: number; onClick: () => void; loading: boolean }) {
  return (
    <div
      onClick={onClick}
      className="w-[280px] h-[160px] bg-white/40 backdrop-blur-lg rounded-[2.5rem] flex flex-col items-center justify-center cursor-pointer transition-all duration-300 hover:bg-white/60 hover:scale-105 hover:shadow-xl border border-white/20"
    >
      <div className="text-2xl font-bold text-gray-800 tracking-wider mb-2">{title}</div>
      <div className="text-base text-gray-600 font-medium">
        {loading ? '加载中...' : `当前数量：${count}`}
      </div>
    </div>
  );
}
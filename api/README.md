# LaLe API 对接文档

## 一、基础信息

| 项 | 值 |
|---|---|
| Base URL（开发） | `http://localhost:8000` |
| 接口前缀 | `/api` |
| 数据格式 | `application/json`（上传接口除外，用 `multipart/form-data`） |
| 认证方式 | JWT Bearer Token |
| Token 有效期 | 7 天 |

**Swagger 在线文档**：`http://localhost:8000/docs`（可交互调试）

---

## 二、统一响应格式

所有接口（成功/失败）均返回：

```json
{
  "code": 0,
  "data": {},
  "msg": "ok"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | int | `0` 成功；非 0 失败（复用 HTTP 状态码） |
| `data` | any | 成功时业务数据；失败时通常为 `null` |
| `msg` | string | 人类可读信息，成功为 `"ok"` |

**前端判断逻辑**：`res.data.code === 0` 即成功，否则按 `code` 和 `msg` 提示。

### 错误码约定

| code | HTTP | 含义 | 前端处理 |
|---|---|---|---|
| `0` | 200 | 成功 | 正常处理 `data` |
| `400` | 200 | 业务失败（参数非法、资源不存在、绑定冲突等） | 弹 `msg` |
| `401` | 401 | 未登录 / Token 无效或过期 | **清 token，跳登录页** |
| `404` | 200 | 资源不存在（用户/文档/笔记等） | 弹 `msg` 或跳列表 |
| `422` | 422 | 请求参数校验失败（Pydantic） | 弹 `msg`，`data` 含字段级错误 |
| `500` | 500 | 服务器内部错误 | 弹通用错误提示 |

> ⚠️ **业务错误（400/404）的 HTTP 状态码仍是 200**，只有鉴权（401）、参数校验（422）、服务器错误（500）才用非 200。前端**必须读 body 里的 `code`**，不能只看 HTTP status。

---

## 三、认证流程

```
1. POST /api/auth/login  { phone_number }
   ↓ 返回 { token, user, is_new_user }
2. 前端存 token（localStorage / sessionStorage / Pinia）
3. 后续所有需要登录的请求，Header 带：
   Authorization: Bearer <token>
4. token 过期或 401 → 清 token，重新登录
```

**开发阶段**：`AUTH_DEV_MODE=true`，登录只需传手机号，**不需要验证码**。前端**不要**做验证码 UI。
---

## 四、接口清单

### 4.1 认证类（无需登录）

#### `POST /api/auth/send_code` — 发送验证码

> 开发阶段可跳过，前端**可暂不调用**。

**请求**：`{ "phone_number": "13900000001" }`

**成功**：`{ "code": 0, "data": null, "msg": "ok" }`

**失败**：`{ "code": 400, "data": null, "msg": "发送验证码失败（手机号格式错误）" }`

---

#### `POST /api/auth/login` — 登录（一键登录）

**请求**：
```json
{ "phone_number": "13900000001", "code": null }
```
> `code` 开发模式可省略或传 `null`。

**成功**：
```json
{
  "code": 0,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "id": 3,
      "user_uuid": "417df44a-...",
      "phone_number": "13900000001",
      "nickname": "用户0001",
      "avatar_url": "",
      "email": null,
      "wechat_openid": null,
      "status": "active",
      "last_login_at": "2026-10-19T22:00:22.628369",
      "created_at": "2026-10-18T21:27:52.958933",
      "updated_at": "2026-10-19T22:00:22.628852"
    },
    "is_new_user": true
  },
  "msg": "ok"
}
```

**失败**：`{ "code": 400, "data": null, "msg": "登录失败" }`

**前端处理**：
- 存 `data.token`。
- `is_new_user === true` 可引导完善昵称/头像。
- `user` 对象存全局状态。

---

#### `POST /api/auth/logout` — 登出

**请求**：Header 可选带 `Authorization: Bearer <token>`，body 为空。

**成功**：`{ "code": 0, "data": null, "msg": "ok" }`

**前端处理**：JWT 无状态，**前端删 token 即可**。

---

### 4.2 账号类（**全部需要登录**）

以下所有接口 Header **必须**带 `Authorization: Bearer <token>`。

#### `GET /api/account` — 查看账号

**成功**：
```json
{
  "code": 0,
  "data": {
    "id": 3,
    "user_uuid": "417df44a-...",
    "phone_number": "13900000001",
    "nickname": "用户0001",
    "avatar_url": "",
    "email": null,
    "wechat_openid": null,
    "status": "active",
    "last_login_at": "...",
    "created_at": "...",
    "updated_at": "..."
  },
  "msg": "ok"
}
```

**失败**：`404 用户不存在` / `401 缺少 Bearer Token` / `401 Token 无效或已过期`

---

#### `PATCH /api/account/nickname` — 修改昵称

**请求**：`{ "nickname": "新昵称" }`（非空、≤100 字符）

**成功**：`{ "code": 0, "data": null, "msg": "ok" }`
**失败**：`{ "code": 400, "data": null, "msg": "修改昵称失败" }`

---

#### `PATCH /api/account/avatar` — 修改头像

**请求**：`{ "avatar_url": "https://example.com/avatar.png" }`（非空、≤500 字符）

**成功**：`{ "code": 0, "data": null, "msg": "ok" }`
**失败**：`{ "code": 400, "data": null, "msg": "修改头像失败" }`

> 当前只存 URL 字符串，头像文件上传是后续功能。

---

#### `POST /api/account/email` — 绑定邮箱

**请求**：`{ "email": "test@example.com" }`（含 `@` 和 `.`、≤200 字符、**全局唯一**）

**成功**：`{ "code": 0, "data": null, "msg": "ok" }`
**失败**：`{ "code": 400, "data": null, "msg": "绑定邮箱失败（格式错误或已被占用）" }`

---

#### `POST /api/account/wechat` — 绑定微信

**请求**：`{ "wechat_openid": "wx_openid_12345" }`（非空、≤200 字符、**全局唯一**）

**成功**：`{ "code": 0, "data": null, "msg": "ok" }`
**失败**：`{ "code": 400, "data": null, "msg": "绑定微信失败（已被占用）" }`

---

#### `DELETE /api/account` — 注销账户（⚠️ 物理删除，不可恢复）

**成功**：`{ "code": 0, "data": null, "msg": "账户已注销" }`
**失败**：`{ "code": 400, "data": null, "msg": "注销失败" }`

**前端处理**：
- **必须二次确认**（"注销后数据不可恢复，确认？"）。
- 成功后**清 token**，跳登录页。
- 注销会删除该用户所有文档、笔记、整合、回收站记录和上传文件。
---

### 4.3 文档类（**全部需要登录**）

#### `POST /api/documents/upload` — 上传文件

**请求**：`multipart/form-data`，字段名 `file`。

```javascript
const formData = new FormData()
formData.append('file', fileInput.files[0])
await api.post('/api/documents/upload', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
})
```

**支持格式**：`.pdf` / `.txt` / `.md` / `.doc` / `.docx` / `.png` / `.jpg` / `.jpeg` / `.bmp` / `.tiff` / `.webp`

**成功**：
```json
{
  "code": 0,
  "data": {
    "doc_id": 4,
    "doc_uuid": "17c06adc-...",
    "file_name": "photo.png",
    "file_type": "image",
    "source_channel": "file",
    "file_path": "/home/bina/LaLe/data/user_uploads/3/photo.png",
    "file_size": 12345,
    "status": "active",
    "created_at": "...",
    "updated_at": "..."
  },
  "msg": "上传成功"
}
```

**失败**：`{ "code": 400, "data": null, "msg": "上传失败（文件类型不支持或解析失败）" }`

**注意**：
- 图片会跑 OCR，**可能耗时 2-3 秒**，前端要 loading。
- 上传成功后 `file_path` 是服务器路径，前端展示用 `file_name`。

---

#### `GET /api/documents` — 文档列表

**Query**：`include_deleted`（可选，默认 `false`）

**成功**：
```json
{
  "code": 0,
  "data": [
    {
      "doc_id": 4,
      "doc_uuid": "17c06adc-...",
      "file_name": "photo.png",
      "file_type": "image",
      "source_channel": "file",
      "file_path": "...",
      "file_size": 12345,
      "status": "active",
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "msg": "ok"
}
```

---

#### `GET /api/documents/{doc_uuid}` — 文档详情

**路径参数**：`doc_uuid`（字符串，不是 int id）

**成功**：`{ "code": 0, "data": {...}, "msg": "ok" }`
**失败**：`{ "code": 404, "data": null, "msg": "文档不存在" }`

---

#### `DELETE /api/documents/{doc_uuid}` — 删除文档（进回收站）

**成功**：`{ "code": 0, "data": null, "msg": "已移入回收站" }`
**失败**：`{ "code": 404, "data": null, "msg": "文档不存在" }` / `{ "code": 400, "data": null, "msg": "删除失败" }`

---

### 4.4 笔记类（**全部需要登录**）

#### `POST /api/notes` — 加入笔记

**请求**：
```json
{
  "document_id": 4,
  "note_type": "translation",
  "content": "## 翻译\n测试内容"
}
```

`note_type` 必须是 `translation` / `grammar` / `terminology` / `phrase` 之一。

**成功**：
```json
{
  "code": 0,
  "data": {
    "note_id": 5,
    "note_uuid": "7f80c8e7-...",
    "user_id": 3,
    "document_id": 4,
    "file_name": "photo.png",
    "note_type": "translation",
    "note_type_label": "翻译",
    "content": "## 翻译\n测试内容",
    "content_size": 20,
    "is_integrated": false,
    "status": "active",
    "created_at": "...",
    "updated_at": "..."
  },
  "msg": "笔记已添加"
}
```

**失败**：`{ "code": 400, "data": null, "msg": "添加笔记失败（文档不存在或类型非法）" }`

---

#### `GET /api/notes/grouped?document_id=4` — 按模块 + 日期分组返回笔记

**成功**：
```json
{
  "code": 0,
  "data": {
    "document": {
      "doc_id": 4,
      "doc_uuid": "17c06adc-...",
      "file_name": "photo.png",
      "file_type": "image"
    },
    "translation": [
      { "date": "2026-10-20", "count": 1, "note_uuids": ["..."] }
    ],
    "grammar": [
      { "date": "2026-10-20", "count": 2, "note_uuids": ["...", "..."] }
    ],
    "terminology": [],
    "phrase": [],
    "integration": [
      { "date": "2026-10-20", "count": 1, "integration_uuids": ["..."] }
    ]
  },
  "msg": "ok"
}
```

> **注意**：已被整合的笔记（`is_integrated=true`）**不会出现在** `translation` / `grammar` 等模块下，被整合的内容在 `integration` 字段里。

**失败**：`{ "code": 404, "data": null, "msg": "文档不存在" }`

---

#### `GET /api/notes/by_date?document_id=4&note_type=translation&date=2026-10-20` — 某日期某模块的笔记列表

**成功**：`{ "code": 0, "data": [ {note...} ], "msg": "ok" }`

> `date` 必须是 `YYYY-MM-DD`，且是笔记 `created_at` 的日期，否则返回空列表。

---

#### `GET /api/notes/{note_uuid}` — 笔记详情

**成功**：`{ "code": 0, "data": {...}, "msg": "ok" }`
**失败**：`{ "code": 404, "data": null, "msg": "笔记不存在" }`

---

#### `DELETE /api/notes/{note_uuid}` — 删除笔记（进回收站）

**成功**：`{ "code": 0, "data": null, "msg": "已移入回收站" }`
**失败**：`{ "code": 400, "data": null, "msg": "删除失败（笔记不存在或已在回收站）" }`

---

### 4.5 整合类（**全部需要登录**）

#### `POST /api/integrations` — 整合笔记（⚠️ 耗时 10-30 秒）

**请求**：
```json
{ "note_uuids": ["uuid1", "uuid2"] }
```

至少 2 条，且所有笔记必须属于**同一文档**。

**成功**：
```json
{
  "code": 0,
  "data": {
    "integration_id": 2,
    "integration_uuid": "419b8903-...",
    "user_id": 3,
    "document_id": 4,
    "file_name": "photo.png",
    "source_modules": ["translation", "grammar"],
    "source_note_ids": ["uuid1", "uuid2"],
    "content": "## 整合结果\n...",
    "content_size": 42,
    "status": "active",
    "created_at": "...",
    "updated_at": "..."
  },
  "msg": "整合成功"
}
```

**失败**：`{ "code": 400, "data": null, "msg": "整合失败（笔记不存在或调用模型失败）" }`

**前端注意**：
- **这个接口超时要单独设成 120 秒**（axios 默认 10 秒会先断）。
- 前端要显示明显的 loading 状态（"AI 正在整合，请稍候..."）。
- 整合成功后，原笔记的 `is_integrated` 变成 `true`，分组接口里它们会从原模块消失，出现在 `integration` 字段。

---

#### `GET /api/integrations?document_id=4` — 某文档下的整合列表

**成功**：`{ "code": 0, "data": [ {integration...} ], "msg": "ok" }`

---

#### `GET /api/integrations/{integration_uuid}` — 整合详情

**成功**：`{ "code": 0, "data": {...}, "msg": "ok" }`
**失败**：`{ "code": 404, "data": null, "msg": "整合不存在" }`

---

#### `DELETE /api/integrations/{integration_uuid}` — 删除整合（进回收站）

**成功**：`{ "code": 0, "data": null, "msg": "已移入回收站" }`
**失败**：`{ "code": 400, "data": null, "msg": "删除失败（不存在或已在回收站）" }`

> 删除整合时，原笔记的 `is_integrated` 会**恢复为 `false`**，重新出现在原模块分组里。

---

### 4.6 回收站类（**全部需要登录**）

#### `GET /api/recycle` — 回收站列表

**成功**：
```json
{
  "code": 0,
  "data": [
    {
      "recycle_id": 1,
      "file_type": "user_document",
      "file_type_label": "文档",
      "file_id": 4,
      "file_name": "photo.png",
      "deleted_at": "2026-10-20T21:01:23",
      "expires_at": "2026-11-04T21:01:23",
      "days_left": 15
    }
  ],
  "msg": "ok"
}
```

`file_type` 可能是 `user_document` / `user_note` / `integration`。

---

#### `POST /api/recycle/restore` — 恢复

**请求**：
```json
{
  "file_type": "user_document",
  "file_id": "<doc_uuid>"
}
```

- `file_type`：`user_document` / `user_note` / `integration`
- `file_id`：**统一传 uuid**（文档传 `doc_uuid`，笔记传 `note_uuid`，整合传 `integration_uuid`）

**成功**：`{ "code": 0, "data": null, "msg": "已恢复" }`
**失败**：`{ "code": 400, "data": null, "msg": "恢复失败（不存在或不在回收站）" }`

> 恢复整合时，原笔记的 `is_integrated` 恢复为 `true`。

---

### 4.7 搜索类（**需要登录**）

#### `GET /api/search?keyword=xxx` — 统一搜索

**Query**：
- `keyword`（必填，≥1 字符）
- `search_type`（可选，默认 `all`；`file` / `note` / `all`）
- `limit`（可选，默认 20）

**成功**：
```json
{
  "code": 0,
  "data": {
    "files": [
      {
        "doc_id": 4,
        "doc_uuid": "...",
        "file_name": "photo.png",
        "file_type": "image"
      }
    ],
    "notes": [
      {
        "note_id": 5,
        "note_uuid": "...",
        "file_name": "photo.png",
        "note_type": "translation",
        "note_type_label": "翻译",
        "content": "..."
      }
    ],
    "total_files": 1,
    "total_notes": 2
  },
  "msg": "ok"
}
```

**失败**：`422 参数校验失败`（keyword 为空）
---
---


### 4.8 查词（**需要登录**）

#### `POST /api/dictionary/lookup` — 查词（无状态，不写库）

**请求**：
```json
{
  "word": "apple",
  "context": "I ate an apple."
}
```
`context` 可选（查词时的上下文句子）。

**成功**：
```json
{
  "code": 0,
  "data": {
    "word": "apple",
    "found": true,
    "word_info": {
      "headword": "apple",
      "phonetic_uk": "/ˈæpl/",
      "phonetic_us": "/ˈæpl/",
      "pos": ["noun"],
      "senses": [
        {
          "definition": "a round fruit",
          "translation": "苹果",
          "examples": [
            {"english": "An apple.", "chinese": "一个苹果。"}
          ]
        }
      ]
    },
    "in_vocabulary": true,
    "vocab_uuid": "abcd-1234-..."
  },
  "msg": "ok"
}
```

- `in_vocabulary: true` 表示已在生词本，前端据此显示"√"；`false` 显示"+"。
- `vocab_uuid` 仅在 `in_vocabulary: true` 时有值（`false` 时为 `null`）。前端点"√"取消加入时，调 `DELETE /api/vocabulary/{vocab_uuid}`。
- **不写库**，纯查询。

**失败**：`404 未找到单词: xxx`

---

### 4.9 生词本（**需要登录**）

#### `POST /api/vocabulary` — 加入生词本

**请求**：
```json
{
  "word": "apple",
  "word_info": { ... }   // 原样传 lookup 返回的 word_info
}
```

**成功**：
```json
{
  "code": 0,
  "data": {
    "vocab_uuid": "abcd-1234-...",
    "word": "apple",
    "created_at": "2026-10-21T10:00:00"
  },
  "msg": "已加入生词本"
}
```

**失败**：`{ "code": 400, "data": null, "msg": "加入失败（已存在或参数非法）" }`

> `word` 入库前统一 lower。同一用户同一单词只能有一条 `active` 记录。

**前端处理**：成功后**立即**把按钮从"+"改成"√"，不需要再查库。如果返回 `400 "已存在"`，也改成"√"（静默处理，不弹错误）。

---

#### `GET /api/vocabulary` — 生词本列表

**Query**：`limit`（默认 50，最大 200）、`offset`（默认 0）

**成功**：
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "vocab_uuid": "abcd-1234-...",
        "word": "apple",
        "phonetic_uk": "/ˈæpl/",
        "phonetic_us": "/ˈæpl/",
        "pos": ["noun"],
        "first_meaning": "苹果",
        "created_at": "2026-10-21T10:00:00"
      }
    ],
    "total": 42
  },
  "msg": "ok"
}
```

> 列表返回**摘要**（不含完整 `word_info`），详情接口返回完整。

---

#### `GET /api/vocabulary/{vocab_uuid}` — 生词详情

**成功**：
```json
{
  "code": 0,
  "data": {
    "vocab_uuid": "abcd-1234-...",
    "user_id": 3,
    "word": "apple",
    "word_info": { ... 完整牛津词条 ... },
    "status": "active",
    "created_at": "...",
    "updated_at": "..."
  },
  "msg": "ok"
}
```

**失败**：`404 生词不存在`

---

#### `DELETE /api/vocabulary/{vocab_uuid}` — 删除生词（进回收站）

**成功**：`{ "code": 0, "data": null, "msg": "已移入回收站" }`
**失败**：`{ "code": 400, "data": null, "msg": "删除失败（不存在或已在回收站）" }`

> **取消加入**（点"√"）也走这个接口。删除后进回收站，15 天内可恢复。
> 用户取消后再次点"+"，走 `POST /api/vocabulary` **新建一条**（旧的已软删除，不占唯一约束）。

---

#### 回收站恢复生词

`POST /api/recycle/restore` 的 `file_type` 加 `user_vocabulary`，`file_id` 传 `vocab_uuid`：

```json
{ "file_type": "user_vocabulary", "file_id": "<vocab_uuid>" }
```

**注意**：如果生词本里已有同名单词（`active`），**恢复失败**，返回 `400`。前端要提示"生词本中已有该单词，无法恢复旧记录"。

---

---

### 4.10 翻译（**需要登录**）

#### `POST /api/translation` — 文本翻译（⚠️ 耗时 10-30 秒）

**请求**：
```json
{
  "text": "OpenAI released GPT-5 in 2025.",
  "source_lang": "英语",
  "target_lang": "中文",
  "mode": "direct",
  "use_tools": true,
  "return_trace": false
}
```

- `mode`: `direct`（直译）或 `indirect`（意译）
- `use_tools`: 是否允许模型调用 RAG/Web 搜索
- `return_trace`: 设为 `true` 时会额外返回推理过程（前端调试用，生产环境建议 false）

**成功**：
```json
{
  "code": 0,
  "data": {
    "original_text": "OpenAI released GPT-5 in 2025.",
    "translated_text": "OpenAI 在 2025 年发布了 GPT-5。",
    "mode": "direct",
    "source_lang": "英语",
    "target_lang": "中文",
    "model_name": "deepseek-chat",
    "elapsed_ms": 1500,
    "rounds": 1
  },
  "msg": "ok"
}
```

**前端注意**：
- 该接口**可能耗时较长**，请把 axios 超时设为 **120 秒**。
- 用户看到译文后，可以选择“加入笔记”（调用 `POST /api/notes`，`note_type` 传 `translation`）。

---

### 4.11 语法 / 术语 / 短语（**需要登录**）

这三个模块均复用相同的调用与追踪机制。接口结构一致（可能耗时 10-30 秒）。

#### 1. `POST /api/nlp/grammar` — 语法解析

**请求**：
```json
{
  "text": "The phenomenon, which has puzzled scientists...",
  "source_lang": "英语",
  "use_tools": true,
  "return_trace": false
}
```
> 注意：`grammar` 接口不需要 `target_lang`。

#### 2. `POST /api/nlp/terminology` — 术语识别

**请求**：
```json
{
  "text": "The Federal Reserve raised interest rates...",
  "source_lang": "英语",
  "target_lang": "中文",
  "use_tools": true,
  "return_trace": false
}
```

#### 3. `POST /api/nlp/phrase` — 词组/搭配识别

**请求**：
```json
{
  "text": "He is considering applying for the job...",
  "source_lang": "英语",
  "target_lang": "中文",
  "use_tools": true,
  "return_trace": false
}
```

**成功（通用格式）**：
```json
{
  "code": 0,
  "data": {
    "original_text": "...",
    "analysis": "识别/解析后的 markdown 内容",
    "model_name": "deepseek-chat",
    "elapsed_ms": 1500,
    "rounds": 1
  },
  "msg": "ok"
}
```

**前端注意**：
- 这三个接口均**可能耗时较长**，axios 超时设为 **120 秒**。
- 用户拿到 `analysis` 后，可选择“加入笔记”（调用 `POST /api/notes`，`note_type` 依次传 `grammar` / `terminology` / `phrase`）。

---

### 4.12 联网搜索（**需要登录**）

#### `POST /api/web/search` — 基于 Tavily 的联网搜索

**请求**：
```json
{
  "query": "2025年政府工作报告 新质生产力",
  "max_results": 5,
  "search_depth": "basic",
  "topic": "general",
  "time_range": "month"
}
```
- `max_results`：1-10
- `search_depth`：`basic`（快） / `advanced`（深，可能消耗更多 API credits）
- `topic`：`general` / `news`
- `time_range`：可选，`day` / `week` / `month` / `year`

**成功**：
```json
{
  "code": 0,
  "data": {
    "query": "2025年政府工作报告 新质生产力",
    "result": "[1] 假新闻标题\n    URL: https://example.com\n    相关度: 0.95\n    内容: ......"
  },
  "msg": "ok"
}
```

> `result` 是已经排版好的纯文本（含标题、URL、相关度、内容摘要），前端可以直接渲染或转为 Markdown 展示。

**前端注意**：
- 该接口可能耗时 2-5 秒，axios 超时建议设为 **30 秒**。
- 用户可将搜索结果“加入笔记”（调用 `POST /api/notes`，`note_type` 传 `translation`，或前端根据实际用途选择）。
## 五、前端对接建议

### 5.1 请求封装（axios）

```javascript
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body.code === 0) return body.data
    if (body.code === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
      return Promise.reject(new Error(body.msg))
    }
    return Promise.reject(new Error(body.msg))
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    const msg = error.response?.data?.msg || error.message
    return Promise.reject(new Error(msg))
  }
)

export default api
```

### 5.2 整合接口要单独设超时

```javascript
// 默认 10 秒，整合接口 120 秒
await api.post('/api/integrations', { note_uuids }, { timeout: 120000 })
```

### 5.3 上传接口要带 multipart 头

```javascript
const formData = new FormData()
formData.append('file', file)
const doc = await api.post('/api/documents/upload', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
  timeout: 60000,   // 图片 OCR 慢，上传超时设 60 秒
})
```

### 5.4 登录页最小逻辑

```javascript
async function handleLogin(phone) {
  if (!/^\d{11}$/.test(phone)) {
    alert('请输入 11 位手机号')
    return
  }
  try {
    const { token, user, is_new_user } = await api.post('/api/auth/login', {
      phone_number: phone,
    })
    localStorage.setItem('token', token)
    if (is_new_user) router.push('/profile/setup')
    else router.push('/home')
  } catch (e) {
    alert(e.message)
  }
}
```

---

## 六、接口完成度

| 模块 | 接口 | 状态 |
|---|---|---|
| 认证 | send_code / login / logout | ✅ |
| 账号 | get / nickname / avatar / email / wechat / delete | ✅ |
| 文档 | upload / list / detail / delete | ✅ |
| 笔记 | add / grouped / by_date / detail / delete | ✅ |
| 整合 | integrate / list / detail / delete | ✅ |
| 回收站 | list / restore | ✅ |
| 搜索 | search | ✅ |
| 查词 | lookup | ✅ |
| 生词本 | add / list / detail / delete | ✅ |
| 翻译 / 术语 / 短语 | — | ⏳ 待开发 |

---

## 七、联调注意事项

1. **CORS**：前端跑在 `http://localhost:5173`（Vite）或 `http://localhost:3000`（CRA）默认允许。如果用其他端口，要加到 `api/main.py` 的 `CORS_ORIGINS`。
2. **Token 存储**：`localStorage` 简单但 XSS 风险，当前开发阶段够用。
3. **上传超时**：图片 OCR 2-3 秒，上传接口 axios 超时**至少 60 秒**。
4. **整合超时**：整合接口**至少 120 秒**，前端要 loading 提示。
5. **注销不可恢复**：必须二次确认。
6. **整合后笔记消失**：`grouped` 接口里被整合的笔记从原模块消失，前端要在 `integration` 字段展示。
7. **文档用 uuid，笔记/整合用 uuid**：`DELETE /api/documents/{doc_uuid}`、`GET /api/notes/{note_uuid}` 等路径参数都是 uuid，**不是 int id**。只有 `POST /api/notes` 的 body 里 `document_id` 用 int `doc_id`。
8. **生词本按钮切换**：`lookup` 返回 `in_vocabulary` + `vocab_uuid`，前端据此显示"+"或"√"。点"+"调 `POST /api/vocabulary`，点"√"调 `DELETE /api/vocabulary/{vocab_uuid}`。**前端建议维护 `addedWords` Set 缓存**，本会话内避免重复查库。
9. **生词本恢复冲突**：回收站恢复生词时，如果生词本里已有同名单词（active），恢复会失败（部分唯一索引冲突）。前端要提示"生词本中已有该单词，无法恢复旧记录"。

---

## 八、环境变量

`.env` 需要：

```bash
PG_HOST=localhost
PG_PORT=5432
PG_USER=lale_user
PG_PASSWORD=your_password
JWT_SECRET_KEY=change-me
AUTH_DEV_MODE=true
DEEPSEEK_API_KEY=sk-xxx
```

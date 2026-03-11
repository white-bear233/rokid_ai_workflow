# AI 导览微服务

AR 旅游助手后端 AI 服务，基于 FastAPI 异步模块化架构，提供视觉分析 + 联网搜索 + 流式生成的智能导览功能。

## 功能特性

- **异步架构**: FastAPI + httpx 全异步处理，高性能
- **模块化设计**: 清晰分层，易于维护扩展
- **三阶段 Pipeline**:
  1. 视觉关键词提取 (通义千问 VL)
  2. Bocha 联网搜索
  3. 综合多模态生成
- **SSE 流式输出**: 实时返回生成结果
- **多模式支持**: 默认/亲子/情侣/学术/故事等多种导览风格
- **结构化日志**: 完整的日志系统

## 为什么选择 FastAPI

对于**无状态 API 网关**场景，FastAPI 是最佳选择：

| 特性 | FastAPI | Flask |
|------|---------|-------|
| **异步支持** | ✅ 原生 async/await | ❌ 需要额外处理 |
| **性能** | ✅ 高性能（Starlette） | ❌ 同步框架 |
| **代码简洁** | ✅ 代码更少 | ❌ 需要更多 hack |
| **API 文档** | ✅ 自动 OpenAPI | ❌ 需要手动维护 |
| **流式输出** | ✅ 原生支持 | ❌ 需要额外处理 |

## 项目结构

```
AI_vision_workflow/
├── main.py                   # FastAPI 应用入口 ✅
├── run.py                    # 生产环境启动脚本 ✅
├── requirements.txt          # 依赖列表 ✅
├── .env / .env.example       # 环境变量配置
├── .gitignore
├── README.md
├── test_api.py               # 统一测试脚本 ✅
│
├── api/                      # API 路由层 ✅
│   ├── __init__.py
│   └── routes.py             # 导览分析路由
│
├── services/                 # 业务逻辑层 ✅
│   ├── __init__.py
│   ├── vision_service.py     # 视觉关键词提取
│   ├── search_service.py     # Bocha 搜索服务
│   └── generation_service.py # 综合生成服务
│
├── models/                   # 数据模型层 ✅
│   ├── __init__.py
│   └── schemas.py            # Pydantic 模型
│
└── utils/                    # 工具层 ✅
    ├── __init__.py
    ├── http_client.py        # HTTP 客户端管理
    └── logger.py             # 结构化日志
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件（已包含 API Keys）：

```bash
DASHSCOPE_API_KEY=sk-xxx
BOCHA_API_KEY=sk-xxx
```

### 3. 启动服务

**开发环境**（支持热重载）:
```bash
python main.py
```

**生产环境**:
```bash
python run.py
```

服务将在 `http://localhost:8000` 启动

### 4. 访问 API 文档

浏览器打开: http://localhost:8000/docs

## API 接口

### GET /health

健康检查接口（兼容旧路由）

**响应**:
```json
{
  "status": "healthy",
  "services": {
    "dashscope": true,
    "bocha": true
  }
}
```

### POST /api/v1/guide/analyze

智能导览分析接口（SSE 流式响应）

**请求体**:
```json
{
  "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJ...",
  "location": "西安大雁塔景区",
  "user_question": "这座塔是哪年建的？",
  "user_mode": "默认模式"
}
```

**user_mode 选项**:
- `默认模式`: 专业、准确、简洁
- `亲子模式`: 活泼亲切，适合小朋友
- `情侣模式`: 浪漫温柔，富有诗意
- `学术模式`: 严谨详细，引用史料
- `故事模式`: 讲故事般生动

**响应格式 (SSE)**:
```
data: {"status": "processing", "step": 1, "message": "正在分析图片..."}

data: {"status": "processing", "step": 2, "keywords": "西安大雁塔 建造年份", "message": "正在联网搜索..."}

data: {"status": "processing", "step": 3, "message": "正在生成回复..."}

data: {"text": "大"}
data: {"text": "雁"}
data: {"text": "塔"}
...

data: [DONE]
```

## 工作流说明

```
┌─────────────────────────────────────────────────────────────┐
│                        请求输入                              │
│  image_base64 + location + user_question + user_mode       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 视觉关键词提取 (services/vision_service.py)       │
│  - 模型: qwen-vl-plus                                       │
│  - 输入: 图片 + 位置 + 问题                                  │
│  - 输出: 搜索关键词                                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Bocha 联网搜索 (services/search_service.py)       │
│  - API: Bocha Web Search                                   │
│  - 输入: 关键词                                             │
│  - 输出: 搜索结果摘要                                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 综合生成 (services/generation_service.py)         │
│  - 模型: qwen-vl-plus                                       │
│  - 输入: 图片 + 问题 + 搜索结果 + 模式                       │
│  - 输出: SSE 流式文本                                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
                   流式返回客户端
```

## 技术栈

- **Web 框架**: FastAPI 0.109
- **ASGI 服务器**: Uvicorn
- **HTTP 客户端**: httpx (异步)
- **VL 模型**: 阿里云通义千问 qwen-vl-plus
- **搜索 API**: Bocha 博查
- **数据验证**: Pydantic
- **流式输出**: Server-Sent Events (SSE)

## 生产部署

### 使用 Uvicorn 多进程

```bash
# 4 个 worker 进程
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 使用 Gunicorn (Uvicorn Workers)

```bash
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;  # 重要：禁用缓冲以支持 SSE
        proxy_set_header X-Accel-Buffering no;
    }
}
```

## 性能优化

### 连接池优化

已经在 `utils/http_client.py` 中实现了连接池管理，每个请求独立创建客户端，避免连接复用问题。

### 异步优化

所有 I/O 操作使用异步：
- 通义千问 API 调用
- Bocha 搜索 API 调用
- 流式响应生成

### 超时配置

```python
VISION_TIMEOUT = 90.0   # 视觉分析超时
SEARCH_TIMEOUT = 20.0   # 搜索超时
GENERATION_TIMEOUT = 120.0  # 生成超时
```

## 测试

运行测试脚本：

```bash
python test_api.py
```

或使用 curl:

```bash
curl -X POST "http://localhost:8000/api/v1/guide/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "data:image/jpeg;base64,...",
    "location": "西安大雁塔",
    "user_question": "这座塔是哪年建的？",
    "user_mode": "默认模式"
  }'
```

## License

MIT

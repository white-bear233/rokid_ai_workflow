# AI 导览 API 接口文档

## 📋 概述

AI 导览服务采用**三阶接力架构**，通过视觉识别、联网搜索、智能生成三个阶段，为用户提供专业的旅游景点导览服务。

**接口特点**：
- ⚡ **流式响应**：使用 SSE (Server-Sent Events) 实时返回结果
- 🎯 **三阶接力**：视觉分析 → 梯队搜索 → 智能生成
- 🌍 **多模式支持**：默认模式、亲子模式、情侣模式、学术模式、故事模式

---

## 🔗 接口地址

```
POST http://8.130.98.142:8010/api/v1/guide/analyze
```

---

## 📥 请求参数

### Headers

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| Content-Type | string | ✅ | 固定值：`application/json` |

### Body (JSON)

| 参数名 | 类型 | 必填 | 说明 | 示例值 |
|--------|------|------|------|--------|
| image_base64 | string | ✅ | 图片的 Base64 编码（带 data URL 前缀） | `data:image/jpeg;base64,/9j/4AAQSkZJRg...` |
| location | string | ✅ | 用户当前位置 | `"黄山市 歙县 徽州古城"` |
| user_question | string | ✅ | 用户提问 | `"这个建筑是什么时候建造的？"` |
| user_mode | string | ❌ | 导览模式（默认：默认模式） | `"默认模式"` |

#### 导览模式说明

| 模式 | 说明 |
|------|------|
| 默认模式 | 专业、准确、简洁 |
| 亲子模式 | 活泼、亲切、生动有趣，适合小朋友理解 |
| 情侣模式 | 浪漫、温柔、富有诗意 |
| 学术模式 | 严谨、详细、引用史料 |
| 故事模式 | 讲故事般生动，引人入胜 |

---

## 📤 响应格式

### SSE 流式响应

响应采用 **Server-Sent Events (SSE)** 格式，包含多种事件类型：

#### 事件类型 1：处理进度

```json
{
  "status": "processing",
  "step": 1,
  "message": "正在分析图片意图..."
}
```

```json
{
  "status": "processing",
  "step": 2,
  "keywords": ["歙县 徽州古城 谯楼 建造年代", "歙县 徽州古城 谯楼 历史介绍", "徽州古城 古建筑 历史特色"],
  "message": "正在联网搜索..."
}
```

```json
{
  "status": "processing",
  "step": 3,
  "message": "正在生成回复..."
}
```

#### 事件类型 2：文本内容（流式）

```json
{
  "text": "您好！眼前这座气势恢宏的南谯楼..."
}
```

#### 事件类型 3：完成标记

```
data: [DONE]
```

#### 事件类型 4：错误信息

```json
{
  "status": "error",
  "message": "错误描述"
}
```

---

## 💡 完整示例

### cURL 示例

```bash
curl -X POST http://8.130.98.142:8010/api/v1/guide/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
    "location": "黄山市 歙县 徽州古城",
    "user_question": "这个建筑是什么时候建造的？",
    "user_mode": "默认模式"
  }'
```

---

## 📱 Android 集成示例

### 1. 添加依赖

```gradle
dependencies {
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
    implementation 'com.google.code.gson:gson:2.10.1'
}
```

### 2. 完整代码示例

```kotlin
import okhttp3.*
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import com.google.gson.Gson
import com.google.gson.JsonParser
import java.util.concurrent.TimeUnit

class AIGuideApiService {

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()

    /**
     * 发起 AI 导览分析请求
     *
     * @param imageBase64 图片的 Base64 编码（带前缀）
     * @param location 用户位置
     * @param question 用户问题
     * @param mode 导览模式
     * @param listener 回调监听器
     */
    fun analyzeGuide(
        imageBase64: String,
        location: String,
        question: String,
        mode: String = "默认模式",
        listener: GuideAnalysisListener
    ) {
        // 构建请求体
        val requestBody = GuideRequest(
            imageBase64 = imageBase64,
            location = location,
            userQuestion = question,
            userMode = mode
        )

        val json = gson.toJson(requestBody)
        val body = json.toRequestBody("application/json".toMediaTypeOrNull())

        val request = Request.Builder()
            .url("http://8.130.98.142:8010/api/v1/guide/analyze")
            .post(body)
            .build()

        // 创建 SSE 事件源
        val factory = EventSources.createFactory(client)
        factory.newEventSource(request, object : EventSourceListener() {

            private val fullText = StringBuilder()

            override fun onOpen(eventSource: EventSource, response: Response) {
                listener.onConnectionOpen()
            }

            override fun onEvent(
                eventSource: EventSource,
                id: String?,
                type: String?,
                data: String
            ) {
                // 处理 SSE 事件
                when {
                    data == "[DONE]" -> {
                        // 完成标记
                        listener.onCompleted(fullText.toString())
                    }
                    data.contains("\"status\"") -> {
                        // 处理进度或错误事件
                        try {
                            val jsonObject = JsonParser.parseString(data).asJsonObject
                            val status = jsonObject.get("status").asString

                            when (status) {
                                "processing" -> {
                                    val step = jsonObject.get("step").asInt
                                    val message = jsonObject.get("message").asString
                                    val keywords = if (jsonObject.has("keywords")) {
                                        val keywordsArray = jsonObject.getAsJsonArray("keywords")
                                        (0 until keywordsArray.size())
                                            .map { keywordsArray[it].asString }
                                    } else null
                                    listener.onProcessing(step, message, keywords)
                                }
                                "error" -> {
                                    val errorMsg = jsonObject.get("message").asString
                                    listener.onError(errorMsg)
                                }
                            }
                        } catch (e: Exception) {
                            // JSON 解析失败，可能是文本事件
                        }
                    }
                    data.contains("\"text\"") -> {
                        // 处理文本内容
                        try {
                            val jsonObject = JsonParser.parseString(data).asJsonObject
                            val text = jsonObject.get("text").asString
                            fullText.append(text)
                            listener.onTextReceived(text)
                        } catch (e: Exception) {
                            // 忽略解析错误
                        }
                    }
                }
            }

            override fun onClosed(eventSource: EventSource) {
                listener.onConnectionClosed()
            }

            override fun onFailure(
                eventSource: EventSource,
                t: Throwable?,
                response: Response?
            ) {
                listener.onError(t?.message ?: "连接失败")
            }
        })
    }

    // 数据类
    data class GuideRequest(
        val image_base64: String,
        val location: String,
        val user_question: String,
        val user_mode: String
    )

    // 回调接口
    interface GuideAnalysisListener {
        fun onConnectionOpen()
        fun onProcessing(step: Int, message: String, keywords: List<String>?)
        fun onTextReceived(text: String)
        fun onCompleted(fullText: String)
        fun onConnectionClosed()
        fun onError(error: String)
    }
}
```

### 3. 使用示例

```kotlin
class MainActivity : AppCompatActivity() {

    private val apiService = AIGuideApiService()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // 将图片转换为 Base64
        val imageBase64 = convertImageToBase64(selectedImageUri)

        // 发起请求
        apiService.analyzeGuide(
            imageBase64 = imageBase64,
            location = "黄山市 歙县 徽州古城",
            question = "这个建筑是什么时候建造的？",
            mode = "默认模式",
            listener = object : AIGuideApiService.GuideAnalysisListener {
                override fun onConnectionOpen() {
                    runOnUiThread {
                        progressBar.visibility = View.VISIBLE
                        statusText.text = "连接中..."
                    }
                }

                override fun onProcessing(step: Int, message: String, keywords: List<String>?) {
                    runOnUiThread {
                        statusText.text = message
                        if (step == 2 && keywords != null) {
                            // 显示搜索关键词
                            keywordsText.text = "搜索: ${keywords.joinToString(", ")}"
                        }
                    }
                }

                override fun onTextReceived(text: String) {
                    runOnUiThread {
                        // 实时追加文本
                        resultText.append(text)
                    }
                }

                override fun onCompleted(fullText: String) {
                    runOnUiThread {
                        progressBar.visibility = View.GONE
                        statusText.text = "完成"
                    }
                }

                override fun onConnectionClosed() {
                    Log.d("AIGuide", "连接关闭")
                }

                override fun onError(error: String) {
                    runOnUiThread {
                        progressBar.visibility = View.GONE
                        statusText.text = "错误: $error"
                        Toast.makeText(this@MainActivity, error, Toast.LENGTH_SHORT).show()
                    }
                }
            }
        )
    }

    /**
     * 将图片转换为 Base64 编码
     */
    private fun convertImageToBase64(uri: Uri): String {
        val inputStream = contentResolver.openInputStream(uri)
        val bytes = inputStream?.readBytes() ?: byteArrayOf()
        val base64 = android.util.Base64.encodeToString(
            bytes,
            android.util.Base64.NO_WRAP
        )

        // 检测图片类型
        val mimeType = contentResolver.getType(uri) ?: "image/jpeg"

        return "data:$mimeType;base64,$base64"
    }
}
```

---

## 🎯 图片 Base64 编码工具函数

```kotlin
import android.content.Context
import android.net.Uri
import android.util.Base64
import java.io.File

object ImageUtils {

    /**
     * 将图片 URI 转换为 Base64 编码（带 data URL 前缀）
     */
    fun convertToBase64(context: Context, uri: Uri): String {
        val inputStream = context.contentResolver.openInputStream(uri)
        val bytes = inputStream?.readBytes() ?: byteArrayOf()
        val base64 = Base64.encodeToString(bytes, Base64.NO_WRAP)

        // 获取 MIME 类型
        val mimeType = context.contentResolver.getType(uri) ?: "image/jpeg"

        return "data:$mimeType;base64,$base64"
    }

    /**
     * 将图片文件转换为 Base64 编码
     */
    fun convertToBase64(file: File): String {
        val bytes = file.readBytes()
        val base64 = Base64.encodeToString(bytes, Base64.NO_WRAP)

        // 根据文件扩展名确定 MIME 类型
        val mimeType = when (file.extension.lowercase()) {
            "jpg", "jpeg" -> "image/jpeg"
            "png" -> "image/png"
            "gif" -> "image/gif"
            "webp" -> "image/webp"
            else -> "image/jpeg"
        }

        return "data:$mimeType;base64,$base64"
    }
}
```

---

## ⚠️ 注意事项

### 1. 图片大小限制
- 建议图片大小控制在 **5MB 以内**
- 推荐分辨率：**800x1200** 或 **1080x1920**
- 过大的图片会增加传输时间和 API 处理时间

### 2. 网络超时设置
- 连接超时：30 秒
- 读取超时：60 秒
- 总响应时间通常在 **6-8 秒**之间

### 3. SSE 连接管理
- 建议在 Activity/Fragment 的 `onDestroy()` 中取消请求
- 监听网络状态变化，重试失败的请求

### 4. 错误处理
常见错误码：
- `500`: 意图提取失败
- `501`: 搜索服务异常
- `502`: 生成服务异常

---

## 📊 性能指标

| 阶段 | 平均耗时 | 说明 |
|------|---------|------|
| 连接建立 | 0.4s | 建立与服务器的连接 |
| Stage 1: 视觉分析 | 1.9s | Qwen-VL 分析图片意图 |
| Stage 2: 联网搜索 | 0.5s | 并发搜索 3 个关键词 |
| Stage 3: 文本生成 | 3.6s | Qwen-Plus 生成回复 |
| **总计** | **6-8s** | 用户体验良好 |

---

## 🔐 安全建议

1. **HTTPS 加密**：生产环境建议使用 HTTPS
2. **API Key 认证**：考虑添加 API Key 认证机制
3. **请求频率限制**：建议添加客户端请求频率限制
4. **敏感信息**：不要在请求中包含用户隐私信息

---

## 📞 技术支持

如有问题，请联系开发团队。

**更新日期**：2026-03-12

# AI 导览 API 使用文档 - Android 客户端

## 📋 基本信息

**服务器地址：** `http://8.130.98.142:8010`

**API 基础路径：** `/api/v1`

**数据格式：** `application/json`

**字符编码：** `UTF-8`

---

## 🔗 API 端点

### 1. 健康检查
```http
GET /api/v1/health
```

**响应示例：**
```json
{
  "status": "healthy",
  "agent": "LangGraph",
  "version": "3.1.0"
}
```

---

### 2. 导览分析（核心接口）
```http
POST /api/v1/guide/analyze
Content-Type: application/json
```

## 📥 请求参数

### JSON Body

| 字段 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `image_base64` | String | ✅ | Base64 编码的图片（带 `data:image/` 前缀） | `"data:image/jpeg;base64,/9j/4AAQ..."` |
| `location` | String | ✅ | 用户位置描述 | `"黄山市 歙县 徽州古城"` |
| `user_question` | String | ✅ | 用户提问 | `"这栋建筑是什么时候建的？"` |
| `user_mode` | String | ❌ | 导览模式，默认"默认模式" | `"默认模式"`、`"亲子模式"`、`"情侣模式"` |

### 导览模式说明

| 模式 | 说明 |
|------|------|
| `默认模式` | 专业、准确、简洁 |
| `亲子模式` | 活泼、亲切、生动有趣，适合小朋友 |
| `情侣模式` | 浪漫、温柔、富有诗意 |
| `学术模式` | 严谨、详细、引用史料 |
| `故事模式` | 讲故事般生动，引人入胜 |

---

## 📤 响应格式

### 成功响应 (200 OK)

```json
{
  "status": "success",
  "reply": "您眼前这座雄伟的南谯楼，是徽州古城的标志性建筑之一...",
  "metadata": {
    "location": "黄山市 歙县 徽州古城",
    "mode": "默认模式",
    "visual_analysis": "识别主体：南谯楼",
    "has_search_results": true,
    "has_weather_info": false,
    "execution_time": "5.23s"
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | String | 请求状态，`"success"` 表示成功 |
| `reply` | String | AI 导览回复内容 |
| `metadata.location` | String | 用户位置 |
| `metadata.mode` | String | 导览模式 |
| `metadata.visual_analysis` | String | 视觉识别结果 |
| `metadata.has_search_results` | Boolean | 是否使用了联网搜索 |
| `metadata.has_weather_info` | Boolean | 是否查询了天气 |
| `metadata.execution_time` | String | 服务端处理耗时 |

### 错误响应

**4xx 客户端错误：**
```json
{
  "detail": "Agent 执行失败: 错误详情"
}
```

**5xx 服务器错误：**
```json
{
  "detail": "Agent 初始化失败: DASHSCOPE_API_KEY 未配置"
}
```

---

## 📱 Android 集成示例

### 1. Kotlin 示例（推荐）

#### 添加依赖（build.gradle.kts）
```kotlin
dependencies {
    // 网络请求
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // 协程支持
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.6.2")
}
```

#### 网络权限（AndroidManifest.xml）
```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
```

#### 数据模型
```kotlin
// 请求模型
data class GuideAnalyzeRequest(
    val image_base64: String,
    val location: String,
    val user_question: String,
    val user_mode: String = "默认模式"
)

// 响应模型
data class GuideAnalyzeResponse(
    val status: String,
    val reply: String,
    val metadata: Metadata
)

data class Metadata(
    val location: String,
    val mode: String,
    val visual_analysis: String?,
    val has_search_results: Boolean,
    val has_weather_info: Boolean,
    val execution_time: String
)
```

#### API 接口定义
```kotlin
import retrofit2.http.Body
import retrofit2.http.POST

interface GuideApiService {
    @POST("api/v1/guide/analyze")
    suspend fun analyzeGuide(
        @Body request: GuideAnalyzeRequest
    ): GuideAnalyzeResponse
}
```

#### Retrofit 配置
```kotlin
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
    private const val BASE_URL = "http://8.130.98.142:8010/"

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .connectTimeout(60, TimeUnit.SECONDS)       // ⚠️ 连接超时 60秒
        .readTimeout(120, TimeUnit.SECONDS)         // ⚠️ 读取超时 120秒
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val guideApiService: GuideApiService = retrofit.create(GuideApiService::class.java)
}
```

#### ViewModel 调用示例
```kotlin
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch

class GuideViewModel : ViewModel() {

    fun analyzeGuide(
        imageBase64: String,
        location: String,
        question: String,
        mode: String = "默认模式",
        onSuccess: (String) -> Unit,
        onError: (String) -> Unit
    ) {
        viewModelScope.launch {
            try {
                val request = GuideAnalyzeRequest(
                    image_base64 = imageBase64,
                    location = location,
                    user_question = question,
                    user_mode = mode
                )

                val response = ApiClient.guideApiService.analyzeGuide(request)

                if (response.status == "success") {
                    onSuccess(response.reply)
                } else {
                    onError("请求失败")
                }

            } catch (e: Exception) {
                onError("网络错误: ${e.message}")
            }
        }
    }
}
```

#### Activity/Fragment 使用
```kotlin
import android.graphics.Bitmap
import android.util.Base64
import java.io.ByteArrayOutputStream

class GuideActivity : AppCompatActivity() {

    private val viewModel = GuideViewModel()

    private fun analyzeImage(bitmap: Bitmap, location: String, question: String) {
        // 显示加载状态
        showLoading("正在识别...")

        // 转换图片为 Base64
        val imageBase64 = bitmapToBase64(bitmap)

        viewModel.analyzeGuide(
            imageBase64 = imageBase64,
            location = location,
            question = question,
            mode = "默认模式",
            onSuccess = { reply ->
                hideLoading()
                showResult(reply)
            },
            onError = { error ->
                hideLoading()
                showError(error)
            }
        )
    }

    // Bitmap 转 Base64
    private fun bitmapToBase64(bitmap: Bitmap): String {
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, 80, stream)
        val bytes = stream.toByteArray()
        val base64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
        return "data:image/jpeg;base64,$base64"
    }

    private fun showLoading(message: String) {
        // 显示加载对话框
    }

    private fun hideLoading() {
        // 隐藏加载对话框
    }

    private fun showResult(reply: String) {
        // 显示结果
    }

    private fun showError(error: String) {
        // 显示错误
    }
}
```

---

### 2. Java 示例

#### 添加依赖（build.gradle）
```gradle
dependencies {
    // 网络请求
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
    implementation 'com.squareup.okhttp3:logging-interceptor:4.12.0'
}
```

#### 数据模型
```java
public class GuideAnalyzeRequest {
    private String image_base64;
    private String location;
    private String user_question;
    private String user_mode;

    // 构造函数
    public GuideAnalyzeRequest(String imageBase64, String location,
                               String question, String mode) {
        this.image_base64 = imageBase64;
        this.location = location;
        this.user_question = question;
        this.user_mode = mode;
    }

    // Getters and Setters
    public String getImage_base64() { return image_base64; }
    public void setImage_base64(String value) { this.image_base64 = value; }
    // ... 其他 getters/setters
}

public class GuideAnalyzeResponse {
    private String status;
    private String reply;
    private Metadata metadata;

    // Getters and Setters
    public String getStatus() { return status; }
    public String getReply() { return reply; }
    public Metadata getMetadata() { return metadata; }
}

public class Metadata {
    private String location;
    private String mode;
    private String execution_time;
    // ... 其他字段

    // Getters and Setters
}
```

#### API 接口定义
```java
import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.POST;

public interface GuideApiService {
    @POST("api/v1/guide/analyze")
    Call<GuideAnalyzeResponse> analyzeGuide(@Body GuideAnalyzeRequest request);
}
```

#### 调用示例
```java
import okhttp3.OkHttpClient;
import okhttp3.logging.HttpLoggingInterceptor;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;
import java.util.concurrent.TimeUnit;

public class GuideApiClient {
    private static final String BASE_URL = "http://8.130.98.142:8010/";

    private static GuideApiService apiService;

    static {
        HttpLoggingInterceptor logging = new HttpLoggingInterceptor();
        logging.setLevel(HttpLoggingInterceptor.Level.BODY);

        OkHttpClient client = new OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(60, TimeUnit.SECONDS)       // ⚠️ 连接超时 60秒
            .readTimeout(120, TimeUnit.SECONDS)         // ⚠️ 读取超时 120秒
            .writeTimeout(60, TimeUnit.SECONDS)
            .build();

        Retrofit retrofit = new Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build();

        apiService = retrofit.create(GuideApiService.class);
    }

    public static void analyzeGuide(
        String imageBase64,
        String location,
        String question,
        String mode,
        final GuideCallback callback
    ) {
        GuideAnalyzeRequest request = new GuideAnalyzeRequest(
            imageBase64, location, question, mode
        );

        Call<GuideAnalyzeResponse> call = apiService.analyzeGuide(request);

        call.enqueue(new Callback<GuideAnalyzeResponse>() {
            @Override
            public void onResponse(Call<GuideAnalyzeResponse> call,
                                   Response<GuideAnalyzeResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    GuideAnalyzeResponse data = response.body();
                    if ("success".equals(data.getStatus())) {
                        callback.onSuccess(data.getReply());
                    } else {
                        callback.onError("请求失败");
                    }
                } else {
                    callback.onError("服务器错误: " + response.code());
                }
            }

            @Override
            public void onFailure(Call<GuideAnalyzeResponse> call, Throwable t) {
                callback.onError("网络错误: " + t.getMessage());
            }
        });
    }

    public interface GuideCallback {
        void onSuccess(String reply);
        void onError(String error);
    }
}
```

#### Activity 中使用
```java
public class GuideActivity extends AppCompatActivity {

    private void analyzeImage(Bitmap bitmap, String location, String question) {
        showLoading("正在识别...");

        String imageBase64 = bitmapToBase64(bitmap);

        GuideApiClient.analyzeGuide(
            imageBase64,
            location,
            question,
            "默认模式",
            new GuideApiClient.GuideCallback() {
                @Override
                public void onSuccess(String reply) {
                    runOnUiThread(() -> {
                        hideLoading();
                        showResult(reply);
                    });
                }

                @Override
                public void onError(String error) {
                    runOnUiThread(() -> {
                        hideLoading();
                        showError(error);
                    });
                }
            }
        );
    }

    private String bitmapToBase64(Bitmap bitmap) {
        ByteArrayOutputStream stream = new ByteArrayOutputStream();
        bitmap.compress(Bitmap.CompressFormat.JPEG, 80, stream);
        byte[] bytes = stream.toByteArray();
        String base64 = Base64.encodeToString(bytes, Base64.NO_WRAP);
        return "data:image/jpeg;base64," + base64;
    }

    // ... 其他方法
}
```

---

## ⚙️ 重要配置

### 1. 超时设置（非常重要！）

由于 Agent 需要进行以下操作：
- 视觉分析（2-5秒）
- 联网搜索（3-8秒）
- LLM 生成（1-3秒）

**总耗时通常在 10-20 秒左右**，因此建议设置：

```kotlin
// Kotlin
connectTimeout(60, TimeUnit.SECONDS)       // 连接超时
readTimeout(120, TimeUnit.SECONDS)         // 读取超时 ⚠️ 最重要！
writeTimeout(60, TimeUnit.SECONDS)         // 写入超时
```

```java
// Java
.connectTimeout(60, TimeUnit.SECONDS)
.readTimeout(120, TimeUnit.SECONDS)        // ⚠️ 最重要！
.writeTimeout(60, TimeUnit.SECONDS)
```

### 2. 线程配置

**Kotlin 协程：**
```kotlin
viewModelScope.launch {  // 自动在主线程
    // 网络请求会自动切换到 IO 线程
}
```

**Java 线程：**
```java
// Retrofit 的 enqueue 会自动在后台线程执行
// 回调在主线程，需要用 runOnUiThread {} 更新 UI
```

### 3. 错误处理

**常见错误及处理方式：**

| 错误 | 可能原因 | 解决方案 |
|------|----------|----------|
| `SocketTimeoutException` | 超时时间过短 | 增加 readTimeout 到 120 秒 |
| `UnknownHostException` | 域名解析失败 | 检查网络连接 |
| `ConnectException` | 服务器未响应 | 检查服务器地址和端口 |
| `JsonSyntaxException` | 响应解析失败 | 检查响应格式是否正确 |
| `HTTP 500` | 服务器内部错误 | 检查服务端日志 |

---

## 🧪 测试工具

### Postman 测试

**URL：** `http://8.130.98.142:8010/api/v1/guide/analyze`

**Method：** `POST`

**Headers：**
```
Content-Type: application/json
```

**Body (raw JSON)：**
```json
{
  "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "location": "黄山市 歙县 徽州古城",
  "user_question": "这栋建筑是什么时候建的？",
  "user_mode": "默认模式"
}
```

---

## 📊 性能指标

根据测试数据：

| 场景 | 平均耗时 | 说明 |
|------|----------|------|
| 天气查询 | 2-5 秒 | 调用天气 API |
| 美食推荐 | 8-15 秒 | 视觉 + 搜索 + 生成 |
| 景点介绍 | 8-15 秒 | 视觉 + 搜索 + 生成 |
| 历史建筑 | 10-20 秒 | 视觉 + 搜索 + 生成 |
| 亲子模式 | 8-15 秒 | 视觉 + 搜索 + 生成 |

**建议：**
- 加载提示文案：`"正在识别和分析，请稍候..."`
- 超时阈值：`120 秒`
- 重试机制：失败后允许用户手动重试

---

## 🔧 调试建议

### 1. 启用日志

**Kotlin:**
```kotlin
private val loggingInterceptor = HttpLoggingInterceptor().apply {
    level = HttpLoggingInterceptor.Level.BODY  // 打印完整请求和响应
}
```

**Java:**
```java
HttpLoggingInterceptor logging = new HttpLoggingInterceptor();
logging.setLevel(HttpLoggingInterceptor.Level.BODY);
```

### 2. 抓包调试

使用 **Charles** 或 **Fiddler** 抓包查看：
- 请求格式是否正确
- 响应内容是否完整
- 实际耗时数据

### 3. 服务端日志

SSH 登录服务器查看日志：
```bash
docker logs -f ai-workflow
```

---

## ❓ 常见问题

### Q1: 为什么一直显示"正在识别中"？

**可能原因：**
1. 超时时间设置过短（少于 60 秒）
2. 网络连接不稳定
3. 服务端处理时间过长

**解决方案：**
- 设置 `readTimeout = 120 秒`
- 检查网络连接
- 查看服务端日志

### Q2: 图片转 Base64 后太大怎么办？

**建议：**
- 压缩图片质量：`bitmap.compress(Bitmap.CompressFormat.JPEG, 80, stream)`
- 缩放图片尺寸：最大边长不超过 1920px
- 裁剪图片：只保留主体区域

### Q3: 如何优化用户体验？

**建议：**
1. 显示详细的加载进度
2. 添加动画效果
3. 提供取消按钮
4. 缓存常见问题的结果

---

## 📞 技术支持

如果遇到问题，请联系开发团队或查看：
- GitHub Issues
- 服务端日志：`docker logs ai-workflow`
- API 健康检查：`http://8.130.98.142:8010/api/v1/health`

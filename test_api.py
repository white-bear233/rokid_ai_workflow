"""
FastAPI 版本测试脚本
测试完整的三阶段工作流：视觉分析 → 搜索 → 生成
"""
import requests
import base64
import json
import sys
import io

# 修复 Windows 控制台编码
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def encode_image_to_base64(image_path):
    """将图片编码为 Base64（带 data:image 前缀）"""
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    return f"data:image/jpeg;base64,{image_data}"

def test_analyze_api():
    """测试导览分析 API（SSE 流式响应）"""
    url = "http://localhost:8000/api/v1/guide/analyze"

    # 准备请求数据
    image_base64 = encode_image_to_base64("image.jpg")

    payload = {
        "image_base64": image_base64,
        "location": "西安大雁塔景区",
        "user_question": "这座塔是什么时候建造的？有什么历史意义？",
        "user_mode": "默认模式"
    }

    print("=" * 60)
    print("测试 AI 导览分析 API")
    print("=" * 60)
    print(f"位置: {payload['location']}")
    print(f"问题: {payload['user_question']}")
    print(f"模式: {payload['user_mode']}")
    print("=" * 60)
    print()

    # 发送 POST 请求
    try:
        response = requests.post(url, json=payload, stream=True, timeout=180)

        if response.status_code != 200:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print(response.text)
            return False

        print("✅ 连接成功，接收流式响应...\n")

        # 解析 SSE 流
        full_text = ""
        step_info = {}

        for line in response.iter_lines(decode_unicode=False):
            if not line:
                continue

            # 解码行
            try:
                line = line.decode('utf-8')
            except (UnicodeDecodeError, AttributeError):
                line = str(line)

            if line.startswith("data: "):
                data_str = line[6:]  # 移除 "data: " 前缀

                if data_str == "[DONE]":
                    print("\n\n✅ 响应完成")
                    break

                try:
                    data = json.loads(data_str)

                    # 处理状态消息
                    if data.get("status") == "processing":
                        step = data.get("step")
                        message = data.get("message")
                        keywords = data.get("keywords")

                        if step == 1:
                            print(f"📍 {message}")
                        elif step == 2:
                            print(f"🔍 {message}")
                            print(f"   关键词: {keywords}")
                        elif step == 3:
                            print(f"💬 {message}")
                            print()
                            print("📝 生成内容:")

                    # 处理错误
                    elif data.get("status") == "error":
                        error_msg = data.get("message")
                        print(f"\n❌ 错误: {error_msg}")
                        return False

                    # 处理文本流
                    elif "text" in data:
                        char = data["text"]
                        print(char, end='', flush=True)
                        full_text += char

                except json.JSONDecodeError:
                    pass

        print("\n")
        print("=" * 60)
        print("测试完成")
        print("=" * 60)
        return True

    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return False
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_analyze_api()
    sys.exit(0 if success else 1)

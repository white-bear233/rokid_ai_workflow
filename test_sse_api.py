"""测试 SSE 流式 API 响应"""
import asyncio
import httpx
import json
import base64


async def test_sse_api():
    """测试 SSE 流式 API"""

    # 读取测试图片
    with open("image.jpg", "rb") as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        image_base64 = f"data:image/jpeg;base64,{image_base64}"

    # 请求数据
    request_data = {
        "image_base64": image_base64,
        "location": "黄山市 歙县 徽州古城",
        "user_question": "这栋建筑是什么时候建的？有什么历史背景？",
        "user_mode": "默认模式"
    }

    print("=" * 60)
    print("开始测试 SSE 流式 API")
    print("=" * 60)
    print(f"位置: {request_data['location']}")
    print(f"问题: {request_data['user_question']}")
    print(f"模式: {request_data['user_mode']}")
    print("-" * 60)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                "http://localhost:8000/api/v1/guide/analyze",
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:

                if response.status_code != 200:
                    print(f"请求失败: {response.status_code}")
                    print(await response.aread())
                    return

                print("连接成功，开始接收 SSE 流...\n")

                full_content = []
                metadata = None

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    print(f"收到: {line[:80]}{'...' if len(line) > 80 else ''}")

                    # 解析 SSE 格式
                    if line.startswith("data: "):
                        data = line[6:]  # 移除 "data: " 前缀

                        # 检查结束标记
                        if data == "[DONE]":
                            print("\n" + "=" * 60)
                            print("流式传输完成")
                            print("=" * 60)
                            break

                        # 解析 JSON 数据
                        try:
                            json_data = json.loads(data)

                            # 处理内容
                            if "content" in json_data:
                                content = json_data["content"]
                                full_content.append(content)
                                print(f"内容: {content}")

                            # 处理元数据
                            if "metadata" in json_data:
                                metadata = json_data["metadata"]
                                print(f"元数据: {metadata}")

                            # 处理错误
                            if "error" in json_data:
                                print(f"错误: {json_data['error']}")
                                break

                        except json.JSONDecodeError as e:
                            print(f"JSON 解析失败: {e}")
                            print(f"   原始数据: {data}")

                # 显示完整结果
                print("\n" + "=" * 60)
                print("完整回复:")
                print("=" * 60)
                if full_content:
                    final_reply = full_content[0] if len(full_content) == 1 else full_content[-1]
                    print(final_reply)
                else:
                    print("未收到内容")

                print("\n" + "=" * 60)
                print("执行统计:")
                print("=" * 60)
                if metadata:
                    print(f"执行时间: {metadata.get('execution_time', 'N/A')}")
                    print(f"位置: {metadata.get('location', 'N/A')}")
                    print(f"模式: {metadata.get('mode', 'N/A')}")

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_sse_api())

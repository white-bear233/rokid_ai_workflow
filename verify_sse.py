"""验证 SSE 流式响应"""
import asyncio
import httpx
import json


async def verify_sse():
    """验证 SSE 响应格式"""
    url = "http://localhost:8000/api/v1/guide/analyze"
    data = {
        "location": "黄山市 歙县 徽州古城",
        "user_question": "最近几天天气怎么样？",
        "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAB//2Q==",
        "user_mode": "默认模式"
    }

    print("SSE 流式响应验证")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=data) as response:
            print(f"状态码: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print()

            if response.status_code == 200:
                line_count = 0
                done_received = False
                content_messages = []
                metadata_received = False

                async for line in response.aiter_lines():
                    line_count += 1

                    if line.startswith("data: "):
                        data_content = line[6:]  # 移除 "data: " 前缀

                        # 检查结束标记
                        if data_content == "[DONE]":
                            done_received = True
                            print(f"[{line_count}] 收到结束标记: data: [DONE]")
                            break

                        # 尝试解析 JSON
                        try:
                            json_data = json.loads(data_content)

                            if "content" in json_data:
                                content_messages.append(json_data["content"])
                                print(f"[{line_count}] 内容消息: {json_data['content'][:50]}...")

                            elif "metadata" in json_data:
                                metadata_received = True
                                print(f"[{line_count}] 元数据: {json_data['metadata']}")

                            elif "error" in json_data:
                                print(f"[{line_count}] 错误: {json_data['error']}")

                        except json.JSONDecodeError:
                            print(f"[{line_count}] 非JSON数据: {data_content[:50]}")

                print()
                print("=" * 60)
                print("验证结果:")
                print("=" * 60)
                print(f"✓ 总行数: {line_count}")
                print(f"✓ 内容消息数: {len(content_messages)}")
                print(f"✓ 收到元数据: {'是' if metadata_received else '否'}")
                print(f"✓ 收到 [DONE]: {'是' if done_received else '否'}")
                print()

                if content_messages:
                    print("完整回复内容:")
                    print("-" * 60)
                    final_reply = content_messages[-1] if content_messages else "无"
                    print(final_reply)
                    print("-" * 60)

                # 验证成功条件
                success = (
                    response.status_code == 200 and
                    done_received and
                    len(content_messages) > 0
                )

                print()
                if success:
                    print("✓✓✓ SSE 流式响应验证成功！✓✓✓")
                    print("Android 客户端的 while 循环将正确退出")
                else:
                    print("✗✗✗ SSE 流式响应验证失败 ✗✗✗")

                return success

            else:
                print(f"请求失败: {response.status_code}")
                return False


if __name__ == "__main__":
    result = asyncio.run(verify_sse())
    exit(0 if result else 1)

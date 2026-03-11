"""
生产环境启动脚本
"""
import uvicorn
import os

if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))
    workers = int(os.getenv('WORKERS', 4))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        log_level="info",
        access_log=True
    )

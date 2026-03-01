import asyncio
import sys
import os

# 确保 Python 能找到 app 文件夹
sys.path.append(os.getcwd())

# 根据你的目录结构，Base 应该是在 models 或者是 core.database 中
# 按照 FastAPI 惯例，我们导入所有 models 以确保 Base 知道所有表
from app.core.database import Base, engine
from app.models import user, assignment, curriculum, mark_scheme, grading, school, classroom

async def init_db():
    try:
        print("正在连接数据库并创建表...")
        async with engine.begin() as conn:
            # 这一步会根据代码里的 Model 直接强制建表
            await conn.run_sync(Base.metadata.create_all)
        print("✅ 数据库表创建成功 (Tables created successfully!)")
    except Exception as e:
        print(f"❌ 出错了: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init_db())
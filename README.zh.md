# 全景系统后端

#### 介绍
本项目是一个基于 FastAPI 和 SQLAlchemy 构建的全景系统后端服务。系统提供了全景数据管理、用户认证、政府执法任务管理、系统性能监控、商铺管理以及时间机器数据管理等核心功能。后端将所有图片数据直接存储在 MySQL 数据库中，支持高并发的 API 访问。

#### 软件架构
本项目采用以下技术栈构建：

- **Web 框架**: FastAPI
- **数据库 ORM**: SQLAlchemy 2.0
- **数据库**: MySQL (通过 PyMySQL 驱动)
- **图片处理**: Pillow
- **系统监控**: psutil
- **服务管理**: Uvicorn

**核心架构组件**：
1.  **API 层** (`main.py`): 处理所有 HTTP 请求，包括全景图、用户、执法任务和系统监控接口。
2.  **模型层** (`models.py` & `models_db.py`):
    - `models.py`: 定义了 Pydantic 模型，用于 API 请求和响应的数据验证与序列化。
    - `models_db.py`: 定义了 SQLAlchemy ORM 模型，映射数据库表结构。
3.  **数据库层** (`database.py`): 配置数据库连接引擎、会话工厂和声明性基类。
4.  **初始化脚本** (`init_db.py`): 用于初始化数据库表结构并填充示例数据。
5.  **迁移工具** (`migrate_database.py`): 提供删除并重建所有数据库表的工具。

#### 安装教程

1.  **克隆项目**
    ```bash
    git clone <https://github.com/Ethan6612/panorama_system_backend.git>
    cd <panorama_system_backend>

2.  **创建虚拟环境 (推荐)**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/macOS
    source venv/bin/activate
    
3.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    
4.  **配置数据库**

    - 确保本地或远程 MySQL 服务已安装并运行。
    
    - 创建一个数据库，例如 panorama_system。
    
    - 修改 database.py 文件中的 DATABASE_CONFIG 配置，填入正确的数据库用户名、密码和数据库名。
    
5.  **初始化数据库**
    - 运行数据库迁移工具创建所有表：
    ```bash
     python migrate_database.py
    ```
    
    - 运行初始化脚本以填充基础数据（用户、服务状态、示例全景图等）：
    ```bash
     python init_db.py
    ```

#### 使用说明
1. 启动服务
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2. 访问 API 文档

    - 启动服务后，在浏览器中打开以下地址查看自动生成的交互式 API 文档：
    
    - Swagger UI: http://localhost:8000/docs
    
    - ReDoc: http://localhost:8000/redoc

3. 默认登录账户

    - 系统初始化后，可以使用以下账户进行登录测试：
    
          普通用户端:
    
          管理员: admin / 123456
    
          普通用户: user / 123456
    
          政府执法端:
    
          政府管理员: gov_admin / 123456
    
          监管员: gov_supervisor / 123456
    
          执法人员: gov_officer / 123456

4. 导入真实全景图片

   - 在项目根目录下创建 images 文件夹，并按照以下结构组织图片：

         images/
             ├── list1/
             │   ├── resized_image/
             │   │   └── panorama1.jpg    (全景图文件)
             │   └── instance/
             │       ├── preview1.jpg     (预览图1)
             │       └── preview2.jpg     (预览图2)
             ├── list2/
             │   ├── resized_image/
             │   │   └── panorama2.jpg
             │   └── instance/
             │       ├── preview1.jpg
             │       └── preview2.jpg

   - 重新运行 init_db.py 脚本，系统将自动导入图片并创建关联数据。

### 参与贡献
1. Fork 本仓库

2. 新建 main 分支

3. 提交代码

4. 新建 Pull Request

### 特技
1. 使用 psutil 实时监控系统 CPU、内存、磁盘和网络状态，并提供历史数据查询接口。

2. 图片数据直接存储于数据库的 LONGBLOB 字段，便于管理和备份。

3. 内置执法任务管理系统，支持任务创建、指派、状态跟踪和历史记录。

4. 提供详细的系统性能监控和服务状态检查接口，便于系统运维。

5. 支持通过目录结构批量导入全景图和预览图，并自动提取 EXIF 信息。
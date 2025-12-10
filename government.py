# create_gov_tables.py
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from database import engine
# 导入政府端相关表模型
from models_db import GovernmentUser, LawEnforcementTask, TaskHistory, TaskComment


def create_gov_tables():
    """创建政府执法端相关数据表"""
    try:
        print("开始创建政府执法端数据库表...")
        print("=" * 50)

        # 创建GovernmentUser表
        print("创建 government_users 表...")
        GovernmentUser.__table__.create(bind=engine, checkfirst=True)
        print("✅ government_users 表创建完成")

        # 创建LawEnforcementTask表
        print("创建 law_enforcement_tasks 表...")
        LawEnforcementTask.__table__.create(bind=engine, checkfirst=True)
        print("✅ law_enforcement_tasks 表创建完成")

        # 创建TaskHistory表
        print("创建 task_history 表...")
        TaskHistory.__table__.create(bind=engine, checkfirst=True)
        print("✅ task_history 表创建完成")

        # 创建TaskComment表
        print("创建 task_comments 表...")
        TaskComment.__table__.create(bind=engine, checkfirst=True)
        print("✅ task_comments 表创建完成")

        print("\n" + "=" * 50)
        print("所有政府执法端相关表创建完成！")

        # 验证表创建结果
        verify_table_creation()

    except Exception as e:
        print(f"❌ 创建政府执法端表时出错: {str(e)}")
        import traceback
        traceback.print_exc()


def verify_table_creation():
    """验证表是否成功创建并显示表结构"""
    try:
        print("\n开始验证表创建结果...")

        gov_tables = [
            "government_users",
            "law_enforcement_tasks",
            "task_history",
            "task_comments"
        ]

        with engine.connect() as conn:
            # 检查表是否存在
            existing_tables = []
            for table_name in gov_tables:
                result = conn.execute(text(f"SHOW TABLES LIKE '{table_name}'"))
                if result.fetchone():
                    existing_tables.append(table_name)
                    print(f"✅ {table_name} 表存在")
                else:
                    print(f"❌ {table_name} 表不存在")

            print(f"\n总计: {len(existing_tables)}/{len(gov_tables)} 个表创建成功")

            # 显示表结构详情
            if existing_tables:
                print("\n📋 表结构详情:")
                print("-" * 50)

                for table_name in existing_tables:
                    print(f"\n{table_name} 表结构:")
                    try:
                        result = conn.execute(text(f"DESCRIBE {table_name}"))
                        columns = result.fetchall()

                        print(f"字段数量: {len(columns)}")
                        print(f"{'字段名':<20} {'类型':<25} {'空值':<8} {'键':<10} {'默认值':<15} {'额外信息':<15}")
                        print("-" * 100)

                        for col in columns:
                            col_name = col[0]
                            col_type = col[1]
                            is_nullable = "YES" if col[2] == "YES" else "NO"
                            col_key = col[3] or ""
                            col_default = str(col[4] or "")
                            col_extra = col[5] or ""

                            print(
                                f"{col_name:<20} {col_type:<25} {is_nullable:<8} {col_key:<10} {col_default:<15} {col_extra:<15}")

                        # 显示索引信息
                        print(f"\n{table_name} 表索引:")
                        result = conn.execute(text(f"SHOW INDEX FROM {table_name}"))
                        indexes = result.fetchall()

                        if indexes:
                            for idx in indexes:
                                if idx[2] != "PRIMARY":  # 跳过主键索引
                                    print(f"  - {idx[2]} 索引: 字段 {idx[4]}, 类型 {idx[10]}")
                        else:
                            print("  无额外索引")

                    except Exception as e:
                        print(f"  无法获取表结构: {str(e)}")

        print("\n" + "=" * 50)
        print("验证完成！")

    except Exception as e:
        print(f"❌ 验证表创建结果时出错: {str(e)}")


def create_gov_initial_data():
    """创建政府执法端初始数据"""
    try:
        from sqlalchemy.orm import Session
        from datetime import datetime

        print("\n开始创建政府执法端初始数据...")

        db = Session(bind=engine)

        # 检查是否已有政府用户数据
        if db.query(GovernmentUser).first():
            print("政府用户数据已存在，跳过初始化")
            db.close()
            return

        # 插入政府执法人员初始数据
        gov_users = [
            GovernmentUser(
                gov_user_id=1,
                username="gov_admin",
                password="123456",
                email="gov_admin@example.com",
                phone="13800000001",
                department="市容管理局",
                position="局长",
                permissions={
                    "panorama_view": True,
                    "task_create": True,
                    "task_assign": True,
                    "task_manage": True,
                    "user_manage": True
                },
                role="admin",
                status=True,
                last_login_time=datetime.now()
            ),
            GovernmentUser(
                gov_user_id=2,
                username="gov_supervisor",
                password="123456",
                email="gov_supervisor@example.com",
                phone="13800000002",
                department="环境卫生处",
                position="处长",
                permissions={
                    "panorama_view": True,
                    "task_create": True,
                    "task_assign": True,
                    "task_manage": True
                },
                role="supervisor",
                status=True
            ),
            GovernmentUser(
                gov_user_id=3,
                username="gov_officer",
                password="123456",
                email="gov_officer@example.com",
                phone="13800000003",
                department="市政管理科",
                position="科员",
                permissions={
                    "panorama_view": True,
                    "task_create": True,
                    "task_execute": True
                },
                role="officer",
                status=True
            ),
            GovernmentUser(
                gov_user_id=4,
                username="gov_inspector",
                password="123456",
                email="gov_inspector@example.com",
                phone="13800000004",
                department="交通管理局",
                position="巡查员",
                permissions={
                    "panorama_view": True,
                    "task_create": True,
                    "task_execute": True
                },
                role="officer",
                status=True
            )
        ]

        db.add_all(gov_users)
        db.flush()
        print("✅ 政府执法人员数据插入成功")

        # 插入操作日志
        from models_db import OperationLog
        log = OperationLog(
            operator="system",
            action="系统初始化",
            target="政府执法端",
            operation_time=datetime.now(),
            ip_address="127.0.0.1",
            result="成功",
            details="创建政府执法端数据库表及初始数据"
        )
        db.add(log)

        db.commit()
        db.close()

        print("✅ 政府执法端初始数据创建完成")
        print("\n政府用户登录信息:")
        print("-" * 40)
        for user in gov_users:
            print(f"用户名: {user.username}")
            print(f"密码: 123456")
            print(f"部门: {user.department}")
            print(f"职位: {user.position}")
            print(f"角色: {user.role}")
            print("-" * 40)

    except Exception as e:
        print(f"❌ 创建初始数据时出错: {str(e)}")
        import traceback
        traceback.print_exc()


def create_sample_tasks():
    """创建示例执法任务"""
    try:
        from sqlalchemy.orm import Session
        from datetime import datetime, timedelta
        import random

        print("\n开始创建示例执法任务...")

        db = Session(bind=engine)

        # 检查是否已有任务数据
        if db.query(LawEnforcementTask).first():
            print("执法任务数据已存在，跳过示例创建")
            db.close()
            return

        # 任务类型定义
        task_types = ["cleanup", "road_repair", "regulation", "environment", "safety", "infrastructure"]

        task_titles = {
            "cleanup": [
                "清理道路垃圾堆积",
                "清除违规张贴小广告",
                "清理河道漂浮物",
                "清扫落叶堆积区域",
                "清理建筑垃圾堆放点"
            ],
            "road_repair": [
                "修复破损路面",
                "修补人行道地砖",
                "修复路缘石破损",
                "填补道路坑洼处",
                "修复排水设施"
            ],
            "regulation": [
                "整治占道经营摊贩",
                "规范非机动车停放",
                "清理违规搭建物",
                "整治夜间噪音扰民",
                "规范广告牌设置"
            ],
            "environment": [
                "绿化带修剪维护",
                "公园设施检修",
                "河道水质监测点检查",
                "空气质量监测设备维护",
                "垃圾分类指导宣传"
            ]
        }

        addresses = [
            "人民路与解放路交叉口东南角",
            "中山公园南门广场",
            "文化广场周边区域",
            "火车站前广场停车场",
            "商业步行街中段",
            "滨江公园观景台",
            "市政府前人民广场",
            "体育中心东门",
            "科技园区主路",
            "大学城北门周边"
        ]

        # 创建20个示例任务
        for i in range(20):
            task_date = datetime.now() - timedelta(days=random.randint(0, 60))
            deadline_days = random.randint(1, 14)
            deadline_date = task_date + timedelta(days=deadline_days)

            task_type = random.choice(task_types[:4])  # 只使用前4种类型
            priority = random.choice(["low", "medium", "high", "urgent"])
            status = random.choice(["pending", "assigned", "in_progress", "completed"])

            # 随机坐标（惠州市中心周边）
            base_lng = 114.404415
            base_lat = 23.557874
            lng = base_lng + random.uniform(-0.03, 0.03)
            lat = base_lat + random.uniform(-0.03, 0.03)

            # 随机指派人员（除了pending状态）
            assigned_to = random.choice([2, 3, 4]) if status != "pending" else None

            task = LawEnforcementTask(
                task_code=f"TASK-{task_date.strftime('%Y%m%d')}-{str(i + 1).zfill(3)}",
                title=random.choice(task_titles[task_type]),
                description=f"发现{task_type}问题需要处理。位于{random.choice(addresses)}，需要{random.choice(['立即', '尽快', '计划内'])}处理。",
                task_type=task_type,
                priority=priority,
                status=status,
                longitude=lng,
                latitude=lat,
                address=random.choice(addresses),
                assigned_to=assigned_to,
                assigned_by=1 if assigned_to else None,
                deadline=deadline_date,
                created_by=1,
                created_at=task_date,
                updated_at=task_date
            )

            # 设置完成时间（如果已完成）
            if status == "completed":
                completion_days = random.randint(1, deadline_days)
                task.completion_time = task_date + timedelta(days=completion_days)

            db.add(task)

        db.commit()
        print(f"✅ 创建了20个示例执法任务")

        # 创建任务历史记录
        tasks = db.query(LawEnforcementTask).all()
        for task in tasks:
            history = TaskHistory(
                task_id=task.task_id,
                action="create",
                description=f"创建任务: {task.title}",
                performed_by=task.created_by,
                old_status=None,
                new_status="pending",
                performed_at=task.created_at
            )
            db.add(history)

            if task.status != "pending":
                history2 = TaskHistory(
                    task_id=task.task_id,
                    action="status_update",
                    description=f"任务状态更新为: {task.status}",
                    performed_by=task.assigned_by or task.created_by,
                    old_status="pending",
                    new_status=task.status,
                    performed_at=task.updated_at
                )
                db.add(history2)

        db.commit()
        print(f"✅ 创建了任务历史记录")

        # 统计信息
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.status == "completed"])
        in_progress_tasks = len([t for t in tasks if t.status == "in_progress"])

        print(f"\n📊 示例任务统计:")
        print(f"总任务数: {total_tasks}")
        print(f"已完成: {completed_tasks}")
        print(f"进行中: {in_progress_tasks}")
        print(f"待处理: {total_tasks - completed_tasks - in_progress_tasks}")

        db.close()

    except Exception as e:
        print(f"❌ 创建示例任务时出错: {str(e)}")
        import traceback
        traceback.print_exc()


def show_usage():
    """显示使用说明"""
    print("""
政府执法端数据库表创建工具

使用方法:
  python create_gov_tables.py [选项]

选项:
  tables     仅创建数据表（默认）
  data       创建数据表并插入初始数据
  sample     创建数据表并插入示例任务数据
  all        创建数据表、初始数据和示例数据
  help       显示此帮助信息

示例:
  python create_gov_tables.py tables    # 仅创建表结构
  python create_gov_tables.py data      # 创建表结构和基础数据
  python create_gov_tables.py all       # 创建完整的数据环境
    """)


if __name__ == "__main__":
    import sys

    # 默认只创建表
    action = "tables"

    if len(sys.argv) > 1:
        action = sys.argv[1].lower()

    if action in ["help", "-h", "--help"]:
        show_usage()
        sys.exit(0)

    print("政府执法端数据库初始化工具")
    print("=" * 50)

    if action in ["tables", "data", "sample", "all"]:
        # 创建表结构
        create_gov_tables()

        if action in ["data", "all"]:
            # 创建初始数据
            create_gov_initial_data()

        if action in ["sample", "all"]:
            # 创建示例任务
            create_sample_tasks()

        print("\n" + "=" * 50)
        print("初始化完成！")
        print("\n可以访问以下API测试:")
        print("- POST /api/government/login")
        print("- GET /api/government/panoramas/all")
        print("- GET /api/government/tasks")
        print("- GET /api/government/dashboard")

    else:
        print(f"错误: 未知的操作 '{action}'")
        print()
        show_usage()
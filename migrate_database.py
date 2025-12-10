# migrate_database.py
from database import engine, Base
from models_db import *
import traceback
from sqlalchemy import text, inspect


def drop_all_tables():
    """删除所有表（安全版本）"""
    try:
        print("正在检查现有表...")
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        if not existing_tables:
            print("✓ 数据库中没有表，无需删除")
            return

        print(f"发现 {len(existing_tables)} 个表: {existing_tables}")

        # 关闭外键约束（针对MySQL）
        if engine.dialect.name == 'mysql':
            print("禁用外键约束...")
            with engine.connect() as conn:
                conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                conn.commit()

        print("正在删除所有表...")
        Base.metadata.drop_all(bind=engine)

        # 重新启用外键约束
        if engine.dialect.name == 'mysql':
            print("启用外键约束...")
            with engine.connect() as conn:
                conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
                conn.commit()

        print("✓ 所有表删除成功")

    except Exception as e:
        print(f"删除表时出错: {e}")
        traceback.print_exc()
        raise


def create_all_tables():
    """创建所有表"""
    try:
        print("正在创建所有表...")
        Base.metadata.create_all(bind=engine)
        print("✓ 所有表创建成功")

        # 显示创建的表及其结构
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"\n创建的表 ({len(tables)} 个):")
        print("-" * 50)

        for table_name in sorted(tables):
            columns = inspector.get_columns(table_name)
            print(f"\n表: {table_name}")
            print(f"{'列名':<20} {'类型':<20} {'是否为空':<10}")
            print("-" * 50)
            for column in columns:
                col_type = str(column['type']).split('(')[0]  # 简化类型显示
                nullable = "是" if column['nullable'] else "否"
                print(f"{column['name']:<20} {col_type:<20} {nullable:<10}")

    except Exception as e:
        print(f"创建表时出错: {e}")
        traceback.print_exc()
        raise


def check_database_connection():
    """检查数据库连接"""
    try:
        print("检查数据库连接...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✓ 数据库连接正常")
            return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False


def backup_tables_if_needed():
    """如果需要，备份现有表（可选功能）"""
    import os
    from datetime import datetime

    backup_dir = "database_backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    backup_file = os.path.join(backup_dir, f"backup_schema_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql")

    try:
        print(f"生成表结构备份到: {backup_file}")
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(f"-- 数据库表结构备份\n")
            f.write(f"-- 备份时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- 表数量: {len(tables)}\n")
            f.write("\n")

            for table in tables:
                f.write(f"-- 表: {table}\n")
                columns = inspector.get_columns(table)
                for column in columns:
                    col_type = str(column['type'])
                    nullable = "NULL" if column['nullable'] else "NOT NULL"
                    f.write(f"--   {column['name']} {col_type} {nullable}\n")
                f.write("\n")

        print(f"✓ 表结构备份完成: {backup_file}")

    except Exception as e:
        print(f"备份表结构时出错: {e}")


def confirm_action():
    """确认用户操作"""
    print("\n" + "=" * 60)
    print("警告: 此操作将删除数据库中的所有表和数据!")
    print("所有数据将永久丢失且无法恢复!")
    print("=" * 60)

    while True:
        confirm = input("\n是否继续? (输入 'yes' 确认继续): ").strip()
        if confirm == 'YES' or confirm == 'yes':
            return True
        elif confirm.lower() == 'no' or confirm.lower() == 'n':
            return False
        else:
            print("请输入 'yes' 继续或 'no' 取消")


def main():
    print("=" * 60)
    print("数据库迁移工具")
    print("功能: 删除所有表并重新创建")
    print("=" * 60)

    # 检查数据库连接
    if not check_database_connection():
        print("无法连接到数据库，请检查数据库配置")
        return

    # 获取用户确认
    if not confirm_action():
        print("操作已取消")
        return

    try:
        print("\n=== 数据库迁移开始 ===")

        # # 可选：备份表结构
        # backup_tables_if_needed()

        # 先删除所有表
        drop_all_tables()

        # 再重新创建所有表
        create_all_tables()

        print("\n" + "=" * 60)
        print("✓ 数据库迁移完成!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 数据库迁移失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
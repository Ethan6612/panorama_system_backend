from database import engine, Base
from models_db import *
import base64
from datetime import datetime, timedelta
import os
from sqlalchemy.orm import Session
from PIL import Image
import io
import random
from sqlalchemy import case
import exifread
import re
from geopy.geocoders import Nominatim
import json
import glob


def init_database():
    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("数据库表创建成功！")

        # 插入初始数据
        db = Session(bind=engine)

        # 检查是否已有数据
        if not db.query(User).first():
            print("开始插入初始数据...")

            # 插入初始用户
            users = [
                User(
                    user_id=1,
                    username="admin",
                    password="123456",
                    email="admin@example.com",
                    phone="13800000001",
                    permission=0,
                    role="admin",
                    status=True
                ),
                User(
                    user_id=2,
                    username="user",
                    password="123456",
                    email="user@example.com",
                    phone="13800000000",
                    permission=1,
                    role="user",
                    status=True
                ),
                User(
                    user_id=3,
                    username="advanced",
                    password="123456",
                    email="advanced@example.com",
                    phone="13800000000",
                    permission=2,
                    role="advanced",
                    status=True
                )
            ]
            db.add_all(users)
            db.flush()  # 获取用户ID
            print("初始用户数据插入成功")

            # 插入服务状态数据
            services = [
                ServiceStatus(
                    name="数据库服务",
                    status="normal",
                    status_text="正常",
                    uptime="99.9%",
                    last_check=datetime.now()
                ),
                ServiceStatus(
                    name="文件存储服务",
                    status="normal",
                    status_text="正常",
                    uptime="99.8%",
                    last_check=datetime.now()
                ),
                ServiceStatus(
                    name="AI打码服务",
                    status="warning",
                    status_text="警告",
                    uptime="98.5%",
                    last_check=datetime.now()
                )
            ]
            db.add_all(services)
            print("服务状态数据插入成功")

            # 插入系统监控示例数据
            monitoring_data = [
                SystemMonitoring(
                    cpu_usage=25.5,
                    memory_usage=60.2,
                    disk_usage=45.8,
                    disk_iops=150,
                    api_response_time=120.5,
                    recorded_at=datetime.now()
                )
            ]
            db.add_all(monitoring_data)
            print("系统监控数据插入成功")

            # 插入操作日志示例数据
            operation_logs = [
                OperationLog(
                    operator="admin",
                    action="系统初始化",
                    target="数据库",
                    operation_time=datetime.now(),
                    ip_address="127.0.0.1",
                    result="成功",
                    details="系统初始数据导入完成"
                )
            ]
            db.add_all(operation_logs)

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
                    permissions={"panorama_view": True, "task_create": True, "task_assign": True, "task_manage": True},
                    role="admin",
                    status=True
                ),
                GovernmentUser(
                    gov_user_id=2,
                    username="gov_supervisor",
                    password="123456",
                    email="gov_supervisor@example.com",
                    phone="13800000002",
                    department="环境卫生处",
                    position="处长",
                    permissions={"panorama_view": True, "task_create": True, "task_assign": True},
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
                    permissions={"panorama_view": True, "task_create": True},
                    role="officer",
                    status=True
                ),
                GovernmentUser(
                    gov_user_id=4,
                    username="gov_officer2",
                    password="123456",
                    email="gov_officer2@example.com",
                    phone="13800000004",
                    department="道路交通管理处",
                    position="巡查员",
                    permissions={"panorama_view": True, "task_create": True},
                    role="officer",
                    status=True
                ),
                GovernmentUser(
                    gov_user_id=5,
                    username="gov_officer3",
                    password="123456",
                    email="gov_officer3@example.com",
                    phone="13800000005",
                    department="环境保护局",
                    position="监察员",
                    permissions={"panorama_view": True, "task_create": True},
                    role="officer",
                    status=True
                )
            ]
            db.add_all(gov_users)
            print("政府执法人员初始数据插入成功")

            # 插入示例执法任务
            print("开始插入示例执法任务...")
            for i in range(30):  # 创建30个示例任务
                task_date = datetime.now() - timedelta(days=random.randint(0, 90))
                deadline_days = random.randint(1, 30)
                deadline_date = task_date + timedelta(days=deadline_days)

                # 任务类型和优先级
                task_types = ["cleanup", "road_repair", "regulation", "environment"]
                priorities = ["low", "medium", "high", "urgent"]
                statuses = ["pending", "assigned", "in_progress", "completed", "cancelled"]

                task_type = random.choice(task_types)
                priority = random.choice(priorities)
                status = random.choice(statuses)

                # 随机坐标（使用已有的地点坐标）
                locations = db.query(Location).all()
                if locations:
                    location = random.choice(locations)
                    lng = location.longitude + random.uniform(-0.005, 0.005)
                    lat = location.latitude + random.uniform(-0.005, 0.005)
                else:
                    lng = 114.404415 + random.uniform(-0.05, 0.05)
                    lat = 23.557874 + random.uniform(-0.05, 0.05)

                # 随机选择执行人员
                assigned_to = random.choice([2, 3, 4, 5]) if status != "pending" else None

                task = LawEnforcementTask(
                    task_code=f"TASK-{task_date.strftime('%Y%m%d')}-{str(i + 1).zfill(3)}",
                    title=f"{task_type}任务{i + 1}",
                    description=f"这是一个{task_type}类型的任务描述，需要处理相关问题。",
                    task_type=task_type,
                    priority=priority,
                    status=status,
                    longitude=lng,
                    latitude=lat,
                    address=f"任务地点{i + 1}",
                    assigned_to=assigned_to,
                    assigned_by=1 if assigned_to else None,
                    deadline=deadline_date,
                    created_by=1,
                    created_at=task_date,
                    updated_at=task_date
                )

                # 如果任务已完成或取消，设置完成时间
                if status == "completed":
                    completion_days = random.randint(1, deadline_days)
                    task.completion_time = task_date + timedelta(days=completion_days)
                elif status == "cancelled":
                    cancellation_days = random.randint(1, deadline_days)
                    task.completion_time = task_date + timedelta(days=cancellation_days)

                db.add(task)

            print("示例执法任务数据插入成功")

            # 插入任务历史记录
            print("开始插入任务历史记录...")
            all_tasks = db.query(LawEnforcementTask).all()
            for task in all_tasks:
                # 创建历史记录
                create_history = TaskHistory(
                    task_id=task.task_id,
                    action="create",
                    description=f"创建任务: {task.title}",
                    performed_by=task.created_by,
                    old_status=None,
                    new_status="pending",
                    performed_at=task.created_at
                )
                db.add(create_history)

                # 如果任务有状态变化，添加相应的历史记录
                if task.status != "pending":
                    status_history = TaskHistory(
                        task_id=task.task_id,
                        action="update",
                        description=f"任务状态更新为: {task.status}",
                        performed_by=task.assigned_by or task.created_by,
                        old_status="pending",
                        new_status=task.status,
                        performed_at=task.updated_at
                    )
                    db.add(status_history)

                    # 如果被指派，添加指派历史
                    if task.assigned_to:
                        assign_history = TaskHistory(
                            task_id=task.task_id,
                            action="assign",
                            description=f"任务指派给用户ID: {task.assigned_to}",
                            performed_by=task.assigned_by,
                            performed_at=task.updated_at
                        )
                        db.add(assign_history)

            print("任务历史记录插入成功")

            # 插入商铺数据
            shops = [
                Shop(
                    shop_id=1,
                    username="幸福饭店",
                    email="人民路88号",
                    province="广东省",
                    city="惠州市",
                    district="惠城区",
                    size="large",
                    role="admin",
                    status=True,
                    audit_status="approved",
                    last_login_time=datetime.now()
                ),
                Shop(
                    shop_id=2,
                    username="便利超市",
                    email="中山路102号",
                    province="广东省",
                    city="惠州市",
                    district="惠城区",
                    size="medium",
                    role="advanced",
                    status=True,
                    audit_status="approved",
                    last_login_time=datetime.now() - timedelta(days=1)
                ),
                Shop(
                    shop_id=3,
                    username="假日酒店",
                    email="解放路56号",
                    province="广东省",
                    city="惠州市",
                    district="惠阳区",
                    size="large",
                    role="user",
                    status=True,
                    audit_status="pending",
                    last_login_time=datetime.now() - timedelta(days=2)
                ),
                Shop(
                    shop_id=4,
                    username="风味小吃",
                    email="文化路34号",
                    province="广东省",
                    city="惠州市",
                    district="博罗县",
                    size="small",
                    role="admin",
                    status=False,
                    audit_status="rejected",
                    last_login_time=datetime.now() - timedelta(days=5)
                ),
                Shop(
                    shop_id=5,
                    username="阳光商超",
                    email="建设路78号",
                    province="广东省",
                    city="深圳市",
                    district="福田区",
                    size="medium",
                    role="advanced",
                    status=True,
                    audit_status="approved",
                    last_login_time=datetime.now() - timedelta(hours=12)
                )
            ]
            db.add_all(shops)
            print("商铺数据插入成功")

            db.commit()
            print("所有基础数据插入成功！")

            # 从images目录导入真实图片
            print("\n开始从images目录导入真实图片...")
            import_images_from_directory_structure(db, 1)

        else:
            print("数据库已有数据，跳过初始化。")

    except Exception as e:
        print(f"数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db' in locals():
            db.close()


def extract_image_metadata(image_data):
    """
    从图片数据中提取元数据
    返回: (经纬度, 拍摄时间, 其他元数据)
    """
    try:
        # 使用exifread解析EXIF数据
        tags = exifread.process_file(io.BytesIO(image_data))

        metadata = {
            "format": "JPEG",
            "has_exif": len(tags) > 0
        }

        # 提取拍摄时间
        shoot_time = None
        time_tags = ['EXIF DateTimeOriginal', 'EXIF DateTimeDigitized', 'Image DateTime']
        for tag_name in time_tags:
            if tag_name in tags:
                time_str = str(tags[tag_name])
                try:
                    # 尝试解析时间字符串
                    shoot_time = datetime.strptime(time_str, "%Y:%m:%d %H:%M:%S")
                    metadata["shoot_time_exif"] = time_str
                    break
                except:
                    pass

        # 提取GPS信息
        latitude = None
        longitude = None
        if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
            try:
                # 解析纬度
                lat_data = tags['GPS GPSLatitude']
                lat_ref = tags['GPS GPSLatitudeRef']
                lat_degrees = float(lat_data.values[0].num) / float(lat_data.values[0].den)
                lat_minutes = float(lat_data.values[1].num) / float(lat_data.values[1].den)
                lat_seconds = float(lat_data.values[2].num) / float(lat_data.values[2].den)
                latitude = lat_degrees + (lat_minutes / 60) + (lat_seconds / 3600)
                if str(lat_ref) == 'S':
                    latitude = -latitude

                # 解析经度
                lon_data = tags['GPS GPSLongitude']
                lon_ref = tags['GPS GPSLongitudeRef']
                lon_degrees = float(lon_data.values[0].num) / float(lon_data.values[0].den)
                lon_minutes = float(lon_data.values[1].num) / float(lon_data.values[1].den)
                lon_seconds = float(lon_data.values[2].num) / float(lon_data.values[2].den)
                longitude = lon_degrees + (lon_minutes / 60) + (lon_seconds / 3600)
                if str(lon_ref) == 'W':
                    longitude = -longitude

                metadata["has_gps"] = True
            except:
                metadata["has_gps"] = False

        # 提取其他EXIF信息
        if 'EXIF ExposureTime' in tags:
            metadata["exposure_time"] = str(tags['EXIF ExposureTime'])
        if 'EXIF FNumber' in tags:
            metadata["f_number"] = str(tags['EXIF FNumber'])
        if 'EXIF ISOSpeedRatings' in tags:
            metadata["iso"] = str(tags['EXIF ISOSpeedRatings'])
        if 'EXIF FocalLength' in tags:
            metadata["focal_length"] = str(tags['EXIF FocalLength'])
        if 'Image Make' in tags:
            metadata["camera_make"] = str(tags['Image Make'])
        if 'Image Model' in tags:
            metadata["camera_model"] = str(tags['Image Model'])

        return longitude, latitude, shoot_time, metadata

    except Exception as e:
        print(f"提取元数据失败: {e}")
        return None, None, None, {"error": str(e)}


def get_location_name(latitude, longitude):
    """
    根据经纬度获取地点名称
    """
    try:
        if latitude is None or longitude is None:
            return None

        # 判断大概的地理区域
        if 39.9 <= latitude <= 40.1 and 116.3 <= longitude <= 116.5:
            return "北京地区"
        elif 31.2 <= latitude <= 31.3 and 121.4 <= longitude <= 121.5:
            return "上海地区"
        elif 30.2 <= latitude <= 30.3 and 120.1 <= longitude <= 120.2:
            return "杭州地区"
        elif 23.5 <= latitude <= 23.6 and 114.4 <= longitude <= 114.5:
            return "惠州地区"
        elif 22.5 <= latitude <= 22.6 and 113.9 <= longitude <= 114.0:
            return "深圳地区"
        elif 23.1 <= latitude <= 23.2 and 113.2 <= longitude <= 113.3:
            return "广州地区"
        else:
            return f"地点({latitude:.4f}, {longitude:.4f})"

    except:
        return None


def find_nearest_location(db, latitude, longitude, threshold=0.01):
    """
    在现有地点中查找最近的地点
    threshold: 经纬度差阈值，小于此值认为是同一个地点
    """
    if latitude is None or longitude is None:
        return None

    locations = db.query(Location).all()
    for location in locations:
        if (abs(location.latitude - latitude) < threshold and
                abs(location.longitude - longitude) < threshold):
            return location
    return None


def import_images_from_directory_structure(db: Session, user_id: int):
    """
    从images目录结构导入图片
    结构: images/list1/resized_image/全景图.jpg
          images/list1/instance/预览图1.jpg, 预览图2.jpg, ...
    """
    try:
        images_dir = "images"
        if not os.path.exists(images_dir):
            print(f"images目录 {images_dir} 不存在，跳过真实图片导入")
            print("请创建 images 目录并按照以下结构组织图片文件：")
            print("  images/list1/resized_image/全景图.jpg")
            print("  images/list1/instance/预览图1.jpg, 预览图2.jpg, ...")
            print("  images/list2/resized_image/全景图.jpg")
            print("  images/list2/instance/预览图1.jpg, 预览图2.jpg, ...")
            return

        # 查找所有的list目录
        list_dirs = []
        for item in os.listdir(images_dir):
            item_path = os.path.join(images_dir, item)
            if os.path.isdir(item_path) and item.startswith("list"):
                list_dirs.append(item_path)

        if not list_dirs:
            print(f"未找到list目录，当前结构：")
            for item in os.listdir(images_dir):
                print(f"  {item}")
            print("请确保目录名以 'list' 开头")
            return

        print(f"找到 {len(list_dirs)} 个list目录")

        imported_count = 0
        skipped_count = 0
        locations_created = 0
        panoramas_created = 0

        for list_dir in list_dirs:
            list_name = os.path.basename(list_dir)
            print(f"\n处理 {list_name} 目录...")

            # 1. 查找全景图（在resized_image目录中）
            resized_dir = os.path.join(list_dir, "resized_image")
            if not os.path.exists(resized_dir):
                print(f"  跳过 {list_name} - 未找到 resized_image 目录")
                continue

            # 查找全景图片文件 - 修复重复匹配问题
            panorama_files = []
            # 先获取所有文件
            all_files = os.listdir(resized_dir)

            for filename in all_files:
                filepath = os.path.join(resized_dir, filename)
                if os.path.isfile(filepath):
                    # 检查文件扩展名（不区分大小写）
                    lower_filename = filename.lower()
                    if lower_filename.endswith(('.jpg', '.jpeg', '.png')):
                        # 检查是否是隐藏文件
                        if not filename.startswith('.'):
                            panorama_files.append(filepath)

            if not panorama_files:
                print(f"  跳过 {list_name} - resized_image 目录中没有图片文件")
                continue

            # 去重（按文件名，防止大小写不同导致的重复）
            unique_panorama_files = []
            seen_filenames = set()
            for filepath in panorama_files:
                filename = os.path.basename(filepath)
                lower_filename = filename.lower()
                if lower_filename not in seen_filenames:
                    seen_filenames.add(lower_filename)
                    unique_panorama_files.append(filepath)

            # 如果去重后有差异，显示信息
            if len(unique_panorama_files) != len(panorama_files):
                print(f"  注意: 发现重复文件名，已去重 ({len(panorama_files)} -> {len(unique_panorama_files)})")

            panorama_files = unique_panorama_files

            # 2. 查找预览图（在instance目录中）
            instance_dir = os.path.join(list_dir, "instance")
            preview_files = []
            if os.path.exists(instance_dir):
                # 同样去重处理预览图
                all_preview_files = os.listdir(instance_dir)
                seen_preview_filenames = set()

                for filename in all_preview_files:
                    filepath = os.path.join(instance_dir, filename)
                    if os.path.isfile(filepath):
                        lower_filename = filename.lower()
                        if lower_filename.endswith(('.jpg', '.jpeg', '.png')):
                            if not filename.startswith('.'):
                                if lower_filename not in seen_preview_filenames:
                                    seen_preview_filenames.add(lower_filename)
                                    preview_files.append(filepath)

            print(f"  找到全景图: {len(panorama_files)} 个")
            print(f"  找到预览图: {len(preview_files)} 个")

            # 显示具体的文件名用于调试
            if len(panorama_files) > 0:
                print(f"  全景图文件列表:")
                for i, path in enumerate(panorama_files):
                    filename = os.path.basename(path)
                    size = os.path.getsize(path) / (1024 * 1024)  # 转换为MB
                    print(f"    {i + 1}. {filename} ({size:.2f}MB)")

            # 处理每个全景图
            for panorama_index, panorama_path in enumerate(panorama_files):
                try:
                    filename = os.path.basename(panorama_path)
                    print(f"\n  处理全景图 [{panorama_index + 1}/{len(panorama_files)}]: {filename}")

                    # 检查文件大小
                    file_size = os.path.getsize(panorama_path)
                    file_size_mb = file_size / (1024 * 1024)

                    if file_size > 200 * 1024 * 1024:  # 200MB限制
                        print(f"    跳过文件 {filename} - 文件过大: {file_size_mb:.2f}MB")
                        skipped_count += 1
                        continue

                    with open(panorama_path, 'rb') as f:
                        image_data = f.read()

                    # 提取元数据
                    longitude, latitude, shoot_time, metadata = extract_image_metadata(image_data)

                    # 确定MIME类型
                    lower_filename = filename.lower()
                    if lower_filename.endswith('.png'):
                        mime_type = "image/png"
                    else:
                        mime_type = "image/jpeg"

                    # 导入全景图
                    panorama_storage = ImageStorage(
                        filename=filename,
                        file_data=image_data,
                        file_size=file_size,
                        mime_type=mime_type,
                        image_type='panorama',
                        created_by=user_id
                    )
                    db.add(panorama_storage)
                    db.flush()
                    panorama_image_id = panorama_storage.image_id

                    # 生成缩略图
                    thumbnail_data = create_thumbnail(image_data)

                    if not thumbnail_data:
                        print(f"    ✗ 跳过文件 {filename} - 缩略图生成失败")
                        db.rollback()
                        skipped_count += 1
                        continue

                    thumbnail_filename = f"thumb_{filename}"
                    thumbnail_storage = ImageStorage(
                        filename=thumbnail_filename,
                        file_data=thumbnail_data,
                        file_size=len(thumbnail_data),
                        mime_type="image/jpeg",
                        image_type='thumbnail',
                        created_by=user_id
                    )
                    db.add(thumbnail_storage)
                    db.flush()
                    thumbnail_image_id = thumbnail_storage.image_id

                    # 设置默认的拍摄时间
                    if shoot_time is None:
                        file_mtime = os.path.getmtime(panorama_path)
                        shoot_time = datetime.fromtimestamp(file_mtime)

                    # 设置默认的经纬度
                    if longitude is None or latitude is None:
                        longitude = 114.404415 + random.uniform(-0.1, 0.1)
                        latitude = 23.557874 + random.uniform(-0.1, 0.1)

                    # 创建或查找地点
                    location = None
                    location_name = None

                    if longitude and latitude:
                        location = find_nearest_location(db, latitude, longitude, threshold=0.01)

                        if location is None:
                            location_name = get_location_name(latitude, longitude) or f"{list_name}-{filename}"
                            location_desc = f"从 {list_name} 目录导入的图片 {filename}"
                            if 'camera_model' in metadata:
                                location_desc += f"，拍摄设备: {metadata['camera_model']}"

                            location = Location(
                                name=location_name,
                                longitude=longitude,
                                latitude=latitude,
                                rating=round(random.uniform(3.5, 5.0), 1),
                                category="全景图地点",
                                description=location_desc,
                                address=None,
                                panorama_id=None
                            )
                            db.add(location)
                            db.flush()
                            locations_created += 1

                    # 创建全景图记录
                    panorama = Panorama(
                        panorama_image_id=panorama_image_id,
                        thumbnail_image_id=thumbnail_image_id,
                        description=f"从 {list_name} 目录导入的全景图: {filename}",
                        shoot_time=shoot_time,
                        longitude=longitude,
                        latitude=latitude,
                        status="published",
                        image_metadata=metadata,
                        created_by=user_id
                    )
                    db.add(panorama)
                    db.flush()
                    panorama_id = panorama.panorama_id
                    panoramas_created += 1

                    # 关联地点与全景图
                    if location and location.panorama_id is None:
                        location.panorama_id = panorama_id

                    # 导入预览图
                    preview_image_ids = []
                    for preview_index, preview_path in enumerate(preview_files):
                        try:
                            preview_filename = os.path.basename(preview_path)
                            print(f"    导入预览图 [{preview_index + 1}/{len(preview_files)}]: {preview_filename}")

                            with open(preview_path, 'rb') as f:
                                preview_data = f.read()

                            # 确定MIME类型
                            lower_preview_filename = preview_filename.lower()
                            if lower_preview_filename.endswith('.png'):
                                preview_mime_type = "image/png"
                            else:
                                preview_mime_type = "image/jpeg"

                            preview_size = os.path.getsize(preview_path)

                            preview_storage = ImageStorage(
                                filename=preview_filename,
                                file_data=preview_data,
                                file_size=preview_size,
                                mime_type=preview_mime_type,
                                image_type='preview',
                                created_by=user_id
                            )
                            db.add(preview_storage)
                            db.flush()
                            preview_image_id = preview_storage.image_id
                            preview_image_ids.append(preview_image_id)

                            # 关联预览图与全景图
                            panorama_preview = PanoramaPreviewImages(
                                panorama_id=panorama_id,
                                preview_image_id=preview_image_id,
                                sort_order=preview_index
                            )
                            db.add(panorama_preview)

                        except Exception as e:
                            print(f"      导入预览图 {preview_path} 失败: {e}")
                            continue

                    db.commit()
                    imported_count += 1

                    print(f"    ✓ 导入成功: {filename}")
                    print(f"      全景图ID: {panorama_id}")
                    if location:
                        print(f"      关联地点: {location.name} (ID: {location.location_id})")
                    print(f"      关联预览图: {len(preview_image_ids)} 个")
                    print(f"      拍摄时间: {shoot_time}")
                    print(f"      坐标: ({longitude}, {latitude})")

                except Exception as e:
                    print(f"    ✗ 导入全景图 {panorama_path} 失败: {e}")
                    import traceback
                    traceback.print_exc()
                    db.rollback()
                    skipped_count += 1
                    continue

        print(f"\n{'=' * 50}")
        print(f"图片导入完成:")
        print(f"  - 成功导入: {imported_count} 个全景图")
        print(f"  - 跳过: {skipped_count} 个文件")
        print(f"  - 创建地点: {locations_created} 个")
        print(f"  - 创建全景图: {panoramas_created} 个")
        print(f"{'=' * 50}")

        # 创建时间机器数据示例
        if imported_count > 0:
            print("\n创建时间机器数据示例...")
            create_time_machine_examples(db, user_id)

    except Exception as e:
        print(f"导入图片失败: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()


def create_time_machine_examples(db: Session, user_id: int):
    """
    创建时间机器数据示例
    """
    try:
        # 获取最近导入的全景图
        panoramas = db.query(Panorama).order_by(Panorama.panorama_id.desc()).limit(3).all()

        if not panoramas:
            return

        for i, panorama in enumerate(panoramas):
            # 获取关联的地点
            location = db.query(Location).filter(Location.panorama_id == panorama.panorama_id).first()

            if location:
                # 创建时间机器数据
                time_machine = TimeMachineData(
                    time_machine_id=f"TM-{panorama.panorama_id}-001",
                    location_id=location.location_id,
                    panorama_id=panorama.panorama_id,
                    year=panorama.shoot_time.year if panorama.shoot_time else 2024,
                    month=panorama.shoot_time.month if panorama.shoot_time else 1,
                    label=f"{location.name}历史视图{i + 1}",
                    description=f"{location.name}的历史全景图数据",
                    address=location.address or location.name,
                    image_ids=[]  # 可以为空或添加预览图ID
                )
                db.add(time_machine)

        db.commit()
        print("时间机器数据示例创建成功")

    except Exception as e:
        print(f"创建时间机器数据失败: {e}")


def create_thumbnail(image_data, max_size=(400, 300)):
    """创建缩略图 - 支持大文件处理"""
    try:
        # 设置图片处理的最大尺寸限制
        Image.MAX_IMAGE_PIXELS = None  # 解除像素限制

        # 打开图片
        image = Image.open(io.BytesIO(image_data))

        # 检查图片尺寸
        width, height = image.size
        total_pixels = width * height

        # 如果图片超过1亿像素，直接生成一个小的缩略图而不进行完整处理
        if total_pixels > 100000000:  # 1亿像素
            print(f"    图片过大 ({width}x{height} = {total_pixels} 像素)，生成简化缩略图")

            # 计算缩小的比例
            scale = min(max_size[0] / width, max_size[1] / height, 1.0)
            new_width = int(width * scale)
            new_height = int(height * scale)

            # 使用thumbnail方法，它会保持宽高比
            image.thumbnail((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            # 正常处理
            image.thumbnail(max_size, Image.Resampling.LANCZOS)

        # 转换为RGB模式（如果是RGBA）
        if image.mode in ('RGBA', 'LA', 'P'):
            # 对于有透明通道的图片，创建白色背景
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # 保存为JPEG
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=85, optimize=True)

        thumbnail_data = output.getvalue()
        return thumbnail_data

    except Exception as e:
        print(f"    创建缩略图失败: {e}")
        # 返回一个简单的占位图
        return create_simple_placeholder()


def create_simple_placeholder():
    """创建简单的占位图片"""
    try:
        # 创建一个简单的400x300的灰色图片
        placeholder = Image.new('RGB', (400, 300), color=(200, 200, 200))
        output = io.BytesIO()
        placeholder.save(output, format='JPEG', quality=80)
        return output.getvalue()
    except:
        # 如果连这个都失败，返回一个最小的图片
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )


def check_database_status():
    """检查数据库状态"""
    try:
        db = Session(bind=engine)

        # 统计各表数据量
        tables = {
            'users': User,
            'government_users': GovernmentUser,
            'locations': Location,
            'shops': Shop,
            'image_storage': ImageStorage,
            'panoramas': Panorama,
            'panorama_preview_images': PanoramaPreviewImages,
            'time_machine_data': TimeMachineData,
            'law_enforcement_tasks': LawEnforcementTask,
            'task_history': TaskHistory,
            'task_comments': TaskComment,
            'service_status': ServiceStatus,
            'system_monitoring': SystemMonitoring,
            'operation_logs': OperationLog
        }

        print("\n=== 数据库状态检查 ===")
        for table_name, model in tables.items():
            try:
                count = db.query(model).count()
                print(f"{table_name}: {count} 条记录")
            except:
                print(f"{table_name}: 表不存在或查询失败")

        # 检查关联关系
        print("\n=== 关联关系检查 ===")
        try:
            locations_with_panorama = db.query(Location).filter(Location.panorama_id.isnot(None)).count()
            print(f"已关联全景图的地点: {locations_with_panorama} 个")
        except:
            print("无法检查地点关联关系")

        # 检查全景图统计
        try:
            panoramas_stats = db.query(
                func.count(Panorama.panorama_id).label('total'),
                func.sum(case((Panorama.status == 'published', 1), else_=0)).label('published'),
                func.sum(case((Panorama.longitude.isnot(None), 1), else_=0)).label('has_coordinates')
            ).first()

            if panoramas_stats:
                print(f"\n=== 全景图统计 ===")
                print(f"总全景图数: {panoramas_stats.total}")
                print(f"已发布: {panoramas_stats.published or 0}")
                print(f"有坐标信息: {panoramas_stats.has_coordinates or 0}")
        except:
            print("\n无法检查全景图统计")

        # 检查预览图关联
        try:
            preview_stats = db.query(
                Panorama.panorama_id,
                func.count(PanoramaPreviewImages.id).label('preview_count')
            ).outerjoin(
                PanoramaPreviewImages,
                Panorama.panorama_id == PanoramaPreviewImages.panorama_id
            ).group_by(Panorama.panorama_id).order_by(Panorama.panorama_id.desc()).limit(10).all()

            if preview_stats:
                print(f"\n=== 最近导入的全景图预览图统计 ===")
                for panorama_id, preview_count in preview_stats:
                    print(f"全景图ID {panorama_id}: {preview_count} 张预览图")
        except:
            print("\n无法检查预览图统计")

        # 检查图片存储统计
        try:
            image_stats = db.query(
                ImageStorage.image_type,
                func.count(ImageStorage.image_id).label('count')
            ).group_by(ImageStorage.image_type).all()

            if image_stats:
                print(f"\n=== 图片存储统计 ===")
                for image_type, count in image_stats:
                    print(f"{image_type}: {count} 张图片")
        except:
            print("\n无法检查图片存储统计")

        db.close()

    except Exception as e:
        print(f"检查数据库状态失败: {e}")


def create_sample_images_directory():
    """创建示例图片目录结构（如果不存在）"""
    images_dir = "images"

    if not os.path.exists(images_dir):
        print(f"创建示例图片目录: {images_dir}")
        os.makedirs(images_dir, exist_ok=True)

        # 创建list1目录示例
        list1_dir = os.path.join(images_dir, "list1")
        os.makedirs(os.path.join(list1_dir, "resized_image"), exist_ok=True)
        os.makedirs(os.path.join(list1_dir, "instance"), exist_ok=True)

        # 创建说明文件
        readme_content = """
# Images目录结构说明

请将全景图片文件按照以下结构组织：

images/
├── list1/
│   ├── resized_image/
│   │   └── panorama1.jpg    (全景图文件)
│   └── instance/
│       ├── preview1.jpg     (预览图1)
│       ├── preview2.jpg     (预览图2)
│       └── preview3.jpg     (预览图3)
├── list2/
│   ├── resized_image/
│   │   └── panorama2.jpg
│   └── instance/
│       ├── preview1.jpg
│       └── preview2.jpg
└── ...

系统会：
1. 扫描所有list开头的目录
2. 将resized_image目录中的图片作为全景图导入
3. 将instance目录中的所有图片作为预览图导入
4. 自动关联预览图和全景图

注意：
- 每个list目录中的resized_image目录可以有一个或多个全景图
- 如果resized_image目录有多个全景图，每个都会创建一个独立的记录
- 每个list目录的instance目录中的所有预览图会关联到该目录中的所有全景图

图片要求：
1. 建议包含GPS信息（可通过手机或支持GPS的相机拍摄）
2. 建议包含EXIF拍摄时间信息
3. 图片文件大小建议不超过200MB
4. 支持JPG和PNG格式

如果没有真实图片，可以跳过此步骤，系统会使用模拟数据。
        """

        with open(os.path.join(images_dir, "README.txt"), "w", encoding="utf-8") as f:
            f.write(readme_content)

        print(f"已在 {images_dir} 目录创建README文件和示例目录结构")
        print("请按照说明将图片文件放入相应的目录，然后重新运行初始化程序")
    else:
        # 检查目录结构
        print(f"images目录已存在")
        print(f"当前images目录内容:")
        for item in os.listdir(images_dir):
            item_path = os.path.join(images_dir, item)
            if os.path.isdir(item_path):
                print(f"  📁 {item}")
                # 检查子目录结构
                for sub_item in os.listdir(item_path):
                    sub_item_path = os.path.join(item_path, sub_item)
                    if os.path.isdir(sub_item_path):
                        print(f"    └── 📁 {sub_item}")
                        # 统计文件数量
                        files = [f for f in os.listdir(sub_item_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                        if files:
                            print(f"        └── 📷 {len(files)} 个图片文件")


if __name__ == "__main__":
    print("开始初始化全景系统数据库...")
    print("=" * 60)
    print("本版本支持从images目录结构智能导入图片")
    print("=" * 60)

    # 安装必要依赖
    try:
        import exifread
    except ImportError:
        print("\n警告: 缺少exifread库，无法分析图片元数据")
        print("请安装: pip install exifread")
        use_exif = False
    else:
        use_exif = True
        print("exifread库已安装，可以分析图片元数据")

    # 检查示例图片目录
    create_sample_images_directory()

    # 初始化数据库
    init_database()

    # 检查数据库状态
    check_database_status()

    print("\n数据库初始化完成！")
    print("=" * 60)
    print("\n访问信息：")
    print("普通用户登录：")
    print("  - 管理员: admin / 123456")
    print("  - 普通用户: user / 123456")
    print("  - 高级用户: advanced / 123456")
    print("\n政府执法用户登录：")
    print("  - 政府管理员: gov_admin / 123456")
    print("  - 监管员: gov_supervisor / 123456")
    print("  - 执法人员: gov_officer / 123456")
    print("\nAPI服务启动命令：")
    print("  uvicorn main:app --reload --host 0.0.0.0 --port 8000")
    print("\n数据查看：")
    print("  - 访问 http://localhost:8000/docs 查看API文档")
    print("  - 访问数据库查看导入的数据")
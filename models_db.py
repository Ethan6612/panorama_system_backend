from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, JSON, Enum, ForeignKey, LargeBinary
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    permission = Column(Integer, default=1)
    role = Column(Enum('admin', 'advanced', 'user'), default='user')
    status = Column(Boolean, default=True)
    last_login_time = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Location(Base):
    __tablename__ = "locations"

    location_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    rating = Column(Float, default=0.00)
    category = Column(String(50))
    description = Column(Text)
    address = Column(Text)
    # 新增：直接关联一张全景图
    panorama_id = Column(Integer, ForeignKey('panoramas.panorama_id'), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# 新增图片存储表
class ImageStorage(Base):
    __tablename__ = "image_storage"

    image_id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_data = Column(LONGBLOB, nullable=False)  # 使用 MySQL 的 LONGBLOB 类型
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    image_type = Column(Enum('panorama', 'thumbnail', 'preview'), nullable=False)
    created_by = Column(Integer, ForeignKey('users.user_id'))
    created_at = Column(DateTime, default=func.now())


class Panorama(Base):
    __tablename__ = "panoramas"

    panorama_id = Column(Integer, primary_key=True, index=True)
    # 移除 location_id 外键，现在通过 Location 表的 panorama_id 关联
    panorama_image_id = Column(Integer, ForeignKey('image_storage.image_id'), nullable=False)
    thumbnail_image_id = Column(Integer, ForeignKey('image_storage.image_id'), nullable=False)
    description = Column(Text)
    shoot_time = Column(DateTime, nullable=False)
    longitude = Column(Float)
    latitude = Column(Float)
    status = Column(Enum('pending', 'published', 'rejected'), default='pending')
    image_metadata = Column(JSON)
    created_by = Column(Integer, ForeignKey('users.user_id'))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class PanoramaPreviewImages(Base):
    __tablename__ = "panorama_preview_images"

    id = Column(Integer, primary_key=True, index=True)
    panorama_id = Column(Integer, ForeignKey('panoramas.panorama_id'), nullable=False)
    preview_image_id = Column(Integer, ForeignKey('image_storage.image_id'), nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())


class TimeMachineData(Base):
    __tablename__ = "time_machine_data"

    time_machine_id = Column(String(50), primary_key=True)
    location_id = Column(Integer, ForeignKey('locations.location_id'), nullable=False)
    panorama_id = Column(Integer, ForeignKey('panoramas.panorama_id'), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    label = Column(String(100), nullable=False)
    description = Column(Text)
    address = Column(Text)
    # 修改为存储图片ID数组
    image_ids = Column(JSON)  # 存储预览图片的ID数组
    created_at = Column(DateTime, default=func.now())


class SystemMonitoring(Base):
    __tablename__ = "system_monitoring"

    monitor_id = Column(Integer, primary_key=True, index=True)
    cpu_usage = Column(Float, nullable=False)
    memory_usage = Column(Float, nullable=False)
    disk_usage = Column(Float, nullable=False)
    disk_iops = Column(Integer, nullable=False)
    api_response_time = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=func.now())


class ServiceStatus(Base):
    __tablename__ = "service_status"

    service_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    status = Column(Enum('normal', 'warning', 'error'), default='normal')
    status_text = Column(String(50), nullable=False)
    uptime = Column(String(20), nullable=False)
    last_check = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class OperationLog(Base):
    __tablename__ = "operation_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    operator = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    target = Column(String(100), nullable=False)
    operation_time = Column(DateTime, nullable=False)
    ip_address = Column(String(45), nullable=False)
    result = Column(Enum('成功', '失败'), nullable=False)
    details = Column(Text)
    created_at = Column(DateTime, default=func.now())


class Shop(Base):
    __tablename__ = "shops"

    shop_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), nullable=False)  # 这里用作地点
    province = Column(String(50))  # 省
    city = Column(String(50))  # 市
    district = Column(String(50))  # 县/区
    size = Column(String(20), default='small')  # 规模字段 small/medium/large
    role = Column(Enum('admin', 'advanced', 'user'), default='admin')  # 商铺类型
    status = Column(Boolean, default=True)  # 显示状态（激活/禁用）
    audit_status = Column(String(20), default='pending')  # 审核状态：pending, approved, rejected
    last_login_time = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class GovernmentUser(Base):
    """政府执法人员表"""
    __tablename__ = "government_users"

    gov_user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    department = Column(String(100), nullable=False)  # 所属部门
    position = Column(String(100))  # 职位
    permissions = Column(JSON)  # 权限配置
    role = Column(Enum('admin', 'supervisor', 'officer'), default='officer')  # 角色
    status = Column(Boolean, default=True)
    last_login_time = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class LawEnforcementTask(Base):
    """执法任务表"""
    __tablename__ = "law_enforcement_tasks"

    task_id = Column(Integer, primary_key=True, index=True)
    task_code = Column(String(50), unique=True, index=True, nullable=False)  # 任务编号
    title = Column(String(200), nullable=False)  # 任务标题
    description = Column(Text, nullable=False)  # 任务描述
    task_type = Column(String(50), nullable=False)  # 任务类型：cleanup/road_repair/regulation/environment
    priority = Column(Enum('low', 'medium', 'high', 'urgent'), default='medium')
    status = Column(Enum('pending', 'assigned', 'in_progress', 'completed', 'cancelled'), default='pending')
    longitude = Column(Float, nullable=False)  # 任务位置经度
    latitude = Column(Float, nullable=False)  # 任务位置纬度
    address = Column(Text)  # 详细地址
    assigned_to = Column(Integer, ForeignKey('government_users.gov_user_id'))  # 指派给谁
    assigned_by = Column(Integer, ForeignKey('government_users.gov_user_id'))  # 由谁指派
    deadline = Column(DateTime)  # 截止时间
    completion_time = Column(DateTime)  # 完成时间
    attachments = Column(JSON)  # 附件（图片等）
    remarks = Column(Text)  # 备注
    created_by = Column(Integer, ForeignKey('government_users.gov_user_id'))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class TaskHistory(Base):
    """任务历史记录表"""
    __tablename__ = "task_history"

    history_id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey('law_enforcement_tasks.task_id'), nullable=False)
    action = Column(String(100), nullable=False)  # 操作类型：create/assign/update/complete/cancel
    description = Column(Text, nullable=False)  # 操作描述
    performed_by = Column(Integer, ForeignKey('government_users.gov_user_id'), nullable=False)
    performed_at = Column(DateTime, default=func.now())
    old_status = Column(String(50))  # 旧状态
    new_status = Column(String(50))  # 新状态
    history_metadata = Column(JSON)  # 其他元数据（注意：改名为history_metadata避免冲突）


class TaskComment(Base):
    """任务评论/沟通记录"""
    __tablename__ = "task_comments"

    comment_id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey('law_enforcement_tasks.task_id'), nullable=False)
    content = Column(Text, nullable=False)  # 评论内容
    comment_type = Column(Enum('comment', 'update', 'reminder'), default='comment')
    created_by = Column(Integer, ForeignKey('government_users.gov_user_id'), nullable=False)
    created_at = Column(DateTime, default=func.now())
    attachments = Column(JSON)  # 附件
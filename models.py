from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# 基础响应模型
class BaseResponse(BaseModel):
    code: str = "200"
    msg: str = "成功"
    data: Optional[Any] = None


# 图片相关模型
class ImageInfo(BaseModel):
    imageId: int
    filename: str
    mimeType: str
    fileSize: int
    imageType: str
    createdAt: str


class ImageUploadResponse(BaseResponse):
    data: Optional[ImageInfo] = None


# 登录相关模型
class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    userId: int
    username: str
    email: str
    phone: str
    permission: int
    role: str
    token: str


class LoginResponse(BaseResponse):
    data: Optional[UserInfo] = None


# 全景系统模型
class Location(BaseModel):
    id: int
    name: str
    longitude: float
    latitude: float
    rating: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    # 全景图信息
    panorama: Optional[Dict[str, Any]] = None
    # 预览图列表
    preview_images: Optional[List[str]] = None


class Panorama(BaseModel):
    id: int
    locationId: int
    locationName: str
    description: Optional[str] = None
    panoramaImage: str  # 图片URL
    thumbnail: str  # 缩略图URL
    timestamp: Optional[str] = None
    longitude: float
    latitude: float


class TimeMachineData(BaseModel):
    id: str
    locationId: int
    year: int
    month: int
    label: str
    panoramaImage: str  # 图片URL
    thumbnail: str  # 缩略图URL
    description: Optional[str] = None
    address: Optional[str] = None
    images: Optional[List[str]] = None  # 图片URL列表
    longitude: float
    latitude: float


# 管理员端模型
class DashboardStats(BaseModel):
    totalPanoramas: int
    pendingReview: int
    weeklyNew: int
    onlineUsers: int
    todayActiveUsers: int
    systemHealth: Dict[str, float]


class DataItem(BaseModel):
    id: int
    name: str
    thumbnail: str  # 缩略图URL
    shootTime: str
    location: str
    status: str  # pending, published, rejected
    statusText: str


class DataListResponse(BaseResponse):
    data: Dict[str, Any]  # {list: List[DataItem], total: int, page: int, pageSize: int}


class DataDetail(BaseModel):
    id: int
    name: str
    panoramaImage: str  # 图片URL
    shootTime: str
    location: str
    longitude: float
    latitude: float
    status: str
    description: str
    metadata: Dict[str, str]


class ReviewRequest(BaseModel):
    action: str  # approve, reject
    comment: Optional[str] = None


class UserItem(BaseModel):
    id: int
    username: str
    email: str
    role: str
    roleText: str
    status: bool
    lastLoginTime: str


class UserListResponse(BaseResponse):
    data: Dict[str, Any]  # {list: List[UserItem], total: int, page: int, pageSize: int}


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    status: Optional[bool] = None


class PerformanceData(BaseModel):
    time: str
    cpu: float
    memory: float
    disk: float
    diskIOPS: int
    apiResponseTime: float


class ServiceStatus(BaseModel):
    name: str
    status: str  # normal, warning, error
    statusText: str
    uptime: str
    lastCheck: str


class OperationLog(BaseModel):
    id: int
    operator: str
    action: str
    target: str
    time: str
    ip: str
    result: str


class LogListResponse(BaseResponse):
    data: Dict[str, Any]  # {list: List[OperationLog], total: int, page: int, pageSize: int}


# 新增数据库模型
class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    phone: Optional[str] = None
    role: Optional[str] = "user"


class PanoramaCreate(BaseModel):
    location_id: int
    panorama_image_id: int  # 图片ID
    thumbnail_image_id: int  # 缩略图ID
    description: Optional[str] = None
    shoot_time: str
    longitude: float
    latitude: float
    status: str = "pending"
    metadata: Optional[Dict[str, str]] = None


class LocationCreate(BaseModel):
    """创建/更新地点请求模型"""
    name: str
    longitude: float
    latitude: float
    rating: Optional[float] = 0.0
    category: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    # 图片信息
    panorama_image_id: Optional[int] = None  # 全景图ID
    preview_image_ids: Optional[List[int]] = None  # 预览图ID列表


# 新增全景图详细模型
class PanoramaDetail(BaseModel):
    id: int
    panorama_image: str  # 图片URL
    thumbnail: str  # 缩略图URL
    description: Optional[str] = None
    shoot_time: str
    longitude: float
    latitude: float
    status: str
    preview_images: Optional[List[str]] = None  # 预览图URL列表
    created_by: int
    created_at: str


# 批量操作请求模型
class BatchOperationRequest(BaseModel):
    data_ids: List[int]
    action: str  # delete, publish


# 数据上传请求模型 - 修改为支持图片上传
class PanoramaUploadRequest(BaseModel):
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    description: Optional[str] = None
    shoot_time: str
    longitude: float
    latitude: float
    address: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None


# 数据更新请求模型
class PanoramaUpdateRequest(BaseModel):
    description: Optional[str] = None
    shoot_time: Optional[str] = None
    location: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    metadata: Optional[Dict[str, str]] = None


# 用户创建请求模型
class UserCreateRequest(BaseModel):
    username: str
    password: str
    email: str
    phone: Optional[str] = None
    role: str = "user"


# 用户权限请求模型
class UserPermissionRequest(BaseModel):
    role: str
    permissions: Optional[List[str]] = None
    expiry_date: Optional[str] = None


# 图片上传请求模型
class ImageUploadRequest(BaseModel):
    image_type: str  # panorama, thumbnail, preview
    filename: str

# 删除请求验证模型
class DeleteConfirmation(BaseModel):
    """删除确认模型"""
    confirm: bool = True
    force: bool = False  # 强制删除，即使有数据关联


class BatchDeleteRequest(BaseModel):
    """批量删除请求模型"""
    location_ids: List[int]
    confirm: bool = True

# 政府执法相关模型
class GovernmentLoginRequest(BaseModel):
    username: str
    password: str

class GovernmentUserInfo(BaseModel):
    userId: int
    username: str
    email: str
    phone: str
    department: str
    position: str
    role: str
    permissions: Optional[Dict[str, Any]] = None
    token: str

class GovernmentLoginResponse(BaseResponse):
    data: Optional[GovernmentUserInfo] = None

class LawEnforcementTaskCreate(BaseModel):
    title: str
    description: str
    task_type: str  # cleanup/road_repair/regulation/environment
    priority: str = "medium"  # low/medium/high/urgent
    longitude: float
    latitude: float
    address: Optional[str] = None
    assigned_to: Optional[int] = None  # 指派给的用户ID
    deadline: Optional[str] = None  # ISO格式时间字符串
    attachments: Optional[List[int]] = None  # 图片ID列表

class LawEnforcementTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None  # pending/assigned/in_progress/completed/cancelled
    assigned_to: Optional[int] = None
    deadline: Optional[str] = None
    remarks: Optional[str] = None

class TaskCommentCreate(BaseModel):
    content: str
    comment_type: str = "comment"
    attachments: Optional[List[int]] = None

class TaskFilter(BaseModel):
    status: Optional[str] = None
    task_type: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[int] = None
    date_range: Optional[Dict[str, str]] = None  # {"start": "2024-01-01", "end": "2024-12-31"}
    keyword: Optional[str] = None

class TaskStatistics(BaseModel):
    total: int
    pending: int
    in_progress: int
    completed: int
    by_type: Dict[str, int]
    by_priority: Dict[str, int]

class TaskMapPoint(BaseModel):
    id: int
    title: str
    task_type: str
    priority: str
    status: str
    longitude: float
    latitude: float
    address: Optional[str] = None
    assigned_to: Optional[str] = None
    deadline: Optional[str] = None

class MapAreaTasksRequest(BaseModel):
    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float
    zoom_level: Optional[int] = None

class TaskHistoryResponse(BaseModel):
    id: int
    task_id: int
    action: str
    description: str
    performed_by: str
    performed_at: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    history_metadata: Optional[Dict[str, Any]] = None
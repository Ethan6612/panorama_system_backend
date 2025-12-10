from fastapi import FastAPI, HTTPException, Query, Depends, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from typing import List, Optional
import uuid
import random

import base64
from io import BytesIO
from PIL import Image
import io

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case

from models import *
from models_db import *
from database import get_db

app = FastAPI(title="全景系统API", description="全景系统后端接口", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 工具函数
def wgs84_to_gcj02(lng: float, lat: float):
    """WGS84 转 GCJ-02 坐标转换（简化版）"""
    return [lng, lat]


def generate_guid():
    return str(uuid.uuid4())


def get_status_text(status: str) -> str:
    status_map = {
        "pending": "待审核",
        "published": "已发布",
        "rejected": "已拒绝"
    }
    return status_map.get(status, "未知")


def get_role_text(role: str) -> str:
    role_map = {
        "admin": "管理员",
        "advanced": "高级用户",
        "user": "普通用户"
    }
    return role_map.get(role, "未知")


# 认证依赖
async def get_current_user(token: str = Query(...), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="未授权")

    # 实际应用中应该验证token的有效性
    # 这里简化处理：根据用户token查询用户（需要完善token验证逻辑）
    user = db.query(User).filter(User.user_id == 1).first()  # 临时方案

    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或token无效")

    return user


# ========== 用户登录接口 ==========
@app.post("/api/users/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.username == request.username,
        User.password == request.password,
        User.status == True
    ).first()

    if user:
        user.last_login_time = datetime.now()
        db.commit()

        user_info = UserInfo(
            userId=user.user_id,
            username=user.username,
            email=user.email,
            phone=user.phone or "",
            permission=user.permission,
            role=user.role,
            token=generate_guid()
        )
        return LoginResponse(data=user_info)
    else:
        return LoginResponse(code="400", msg="用户名或密码错误", data=None)


# ========== 用户退出接口 ==========
@app.post("/api/users/logout", response_model=BaseResponse)
async def logout(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # 记录操作日志
    log = OperationLog(
        operator=current_user.username,
        action="用户退出",
        target=current_user.username,
        operation_time=datetime.now(),
        ip_address="192.168.1.1",
        result="成功",
        details="用户安全退出系统"
    )
    db.add(log)
    db.commit()

    return BaseResponse(msg="退出成功")


# ========== 全景系统接口 ==========
@app.get("/api/panorama/locations", response_model=BaseResponse)
async def get_locations(
        db: Session = Depends(get_db)
):
    """
    获取所有地点列表（修改为包含全景图和预览图）
    """
    try:
        locations_data = db.query(Location).all()

        locations = []
        for loc in locations_data:
            location_info = {
                "id": loc.location_id,
                "name": loc.name,
                "longitude": loc.longitude,
                "latitude": loc.latitude,
                "rating": float(loc.rating) if loc.rating else None,
                "category": loc.category,
                "description": loc.description,
                "address": loc.address
            }

            # 如果有全景图关联
            if loc.panorama_id:
                panorama = db.query(Panorama).filter(
                    Panorama.panorama_id == loc.panorama_id
                ).first()

                if panorama:
                    # 获取全景图和缩略图URL
                    panorama_image_url = f"/api/images/{panorama.panorama_image_id}"
                    thumbnail_url = f"/api/images/{panorama.thumbnail_image_id}"

                    location_info["panorama"] = {
                        "id": panorama.panorama_id,
                        "panorama_image": panorama_image_url,
                        "thumbnail": thumbnail_url,
                        "description": panorama.description,
                        "shoot_time": panorama.shoot_time.strftime(
                            "%Y-%m-%d %H:%M:%S") if panorama.shoot_time else None,
                        "longitude": float(panorama.longitude) if panorama.longitude else None,
                        "latitude": float(panorama.latitude) if panorama.latitude else None,
                        "status": panorama.status
                    }

                    # 获取预览图
                    preview_images = db.query(PanoramaPreviewImages, ImageStorage).join(
                        ImageStorage,
                        PanoramaPreviewImages.preview_image_id == ImageStorage.image_id
                    ).filter(
                        PanoramaPreviewImages.panorama_id == panorama.panorama_id
                    ).order_by(PanoramaPreviewImages.sort_order).all()

                    preview_urls = []
                    for preview, image_storage in preview_images:
                        preview_urls.append(f"/api/images/{image_storage.image_id}")

                    location_info["preview_images"] = preview_urls

            locations.append(location_info)

        return BaseResponse(data=locations)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取地点列表失败: {str(e)}")


@app.post("/api/panorama/locations", response_model=BaseResponse)
async def create_location(
        request: LocationCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    创建新地点（支持关联全景图和预览图）
    """
    try:
        # 检查地点名称是否已存在
        existing_location = db.query(Location).filter(
            func.lower(Location.name) == func.lower(request.name)
        ).first()

        if existing_location:
            return BaseResponse(code="400", msg="地点名称已存在")

        # 验证全景图（如果提供了）
        panorama_id = None
        if request.panorama_image_id:
            panorama = db.query(Panorama).filter(
                Panorama.panorama_id == request.panorama_image_id
            ).first()
            if not panorama:
                return BaseResponse(code="400", msg="指定的全景图不存在")
            panorama_id = panorama.panorama_id

            # 检查该全景图是否已被其他地点使用
            used_location = db.query(Location).filter(
                Location.panorama_id == panorama_id
            ).first()
            if used_location:
                return BaseResponse(code="400", msg="该全景图已被其他地点使用")

        # 创建新地点
        location = Location(
            name=request.name,
            longitude=request.longitude,
            latitude=request.latitude,
            rating=request.rating or 0.0,
            category=request.category,
            description=request.description,
            address=request.address,
            panorama_id=panorama_id
        )

        db.add(location)
        db.commit()
        db.refresh(location)

        # 关联预览图（如果提供了）
        if request.preview_image_ids and panorama_id:
            for i, image_id in enumerate(request.preview_image_ids):
                # 验证图片是否存在
                image_storage = db.query(ImageStorage).filter(
                    ImageStorage.image_id == image_id
                ).first()
                if image_storage:
                    panorama_preview = PanoramaPreviewImages(
                        panorama_id=panorama_id,
                        preview_image_id=image_id,
                        sort_order=i
                    )
                    db.add(panorama_preview)

            db.commit()

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="创建地点",
            target=request.name,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"创建新地点: {request.name}"
        )
        db.add(log)
        db.commit()

        return BaseResponse(
            msg="地点创建成功",
            data={
                "id": location.location_id,
                "name": location.name,
                "panorama_id": panorama_id
            }
        )
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"创建地点失败: {str(e)}")


@app.put("/api/panorama/locations/{location_id}", response_model=BaseResponse)
async def update_location(
        location_id: int,
        request: LocationCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    更新地点信息（包括关联全景图和预览图）
    """
    try:
        location = db.query(Location).filter(Location.location_id == location_id).first()
        if not location:
            return BaseResponse(code="404", msg="地点不存在")

        # 检查新名称是否与其他地点冲突
        if request.name != location.name:
            existing_location = db.query(Location).filter(
                func.lower(Location.name) == func.lower(request.name),
                Location.location_id != location_id
            ).first()
            if existing_location:
                return BaseResponse(code="400", msg="地点名称已存在")

        # 验证和更新全景图关联
        new_panorama_id = None
        if request.panorama_image_id:
            panorama = db.query(Panorama).filter(
                Panorama.panorama_id == request.panorama_image_id
            ).first()
            if not panorama:
                return BaseResponse(code="400", msg="指定的全景图不存在")

            # 检查该全景图是否已被其他地点使用（除了当前地点）
            used_location = db.query(Location).filter(
                and_(
                    Location.panorama_id == request.panorama_image_id,
                    Location.location_id != location_id
                )
            ).first()
            if used_location:
                return BaseResponse(code="400", msg="该全景图已被其他地点使用")

            new_panorama_id = panorama.panorama_id

        # 更新地点基本信息
        location.name = request.name
        location.longitude = request.longitude
        location.latitude = request.latitude
        location.rating = request.rating or location.rating
        location.category = request.category
        location.description = request.description
        location.address = request.address
        location.panorama_id = new_panorama_id
        location.updated_at = datetime.now()

        # 处理预览图更新
        if new_panorama_id and request.preview_image_ids:
            # 删除旧的预览图关联
            db.query(PanoramaPreviewImages).filter(
                PanoramaPreviewImages.panorama_id == new_panorama_id
            ).delete(synchronize_session=False)

            # 添加新的预览图关联
            for i, image_id in enumerate(request.preview_image_ids):
                # 验证图片是否存在
                image_storage = db.query(ImageStorage).filter(
                    ImageStorage.image_id == image_id
                ).first()
                if image_storage:
                    panorama_preview = PanoramaPreviewImages(
                        panorama_id=new_panorama_id,
                        preview_image_id=image_id,
                        sort_order=i
                    )
                    db.add(panorama_preview)

        db.commit()

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="更新地点",
            target=location.name,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"更新地点信息: {location.name}"
        )
        db.add(log)
        db.commit()

        return BaseResponse(msg="地点更新成功", data={"id": location_id})
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"更新地点失败: {str(e)}")


@app.delete("/api/panorama/locations/{location_id}", response_model=BaseResponse)
async def delete_location(
        location_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    删除地点（解除与全景图的关联，但不删除全景图）
    """
    try:
        location = db.query(Location).filter(Location.location_id == location_id).first()
        if not location:
            return BaseResponse(code="404", msg="地点不存在")

        location_name = location.name
        panorama_id = location.panorama_id

        # 如果地点有关联的全景图预览图，删除这些关联
        if panorama_id:
            db.query(PanoramaPreviewImages).filter(
                PanoramaPreviewImages.panorama_id == panorama_id
            ).delete(synchronize_session=False)

        # 删除地点（会自动解除外键关联）
        db.delete(location)
        db.commit()

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="地点删除",
            target=f"地点: {location_name}",
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"删除地点 '{location_name}'，解除与全景图 {panorama_id} 的关联" if panorama_id else f"删除地点 '{location_name}'"
        )
        db.add(log)
        db.commit()

        return BaseResponse(
            msg="地点删除成功",
            data={
                "location_id": location_id,
                "location_name": location_name,
                "panorama_id": panorama_id
            }
        )
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"删除地点失败: {str(e)}")


@app.get("/api/panorama/available", response_model=BaseResponse)
async def get_available_panoramas(
        db: Session = Depends(get_db)
):
    """
    获取未关联地点的全景图列表
    """
    try:
        # 查找没有被任何地点使用的全景图
        subquery = db.query(Location.panorama_id).filter(Location.panorama_id.isnot(None)).subquery()

        available_panoramas = db.query(Panorama).outerjoin(
            subquery, Panorama.panorama_id == subquery.c.panorama_id
        ).filter(subquery.c.panorama_id.is_(None)).all()

        result = []
        for panorama in available_panoramas:
            # 获取全景图和缩略图URL
            panorama_image_url = f"/api/images/{panorama.panorama_image_id}"
            thumbnail_url = f"/api/images/{panorama.thumbnail_image_id}"

            # 获取预览图数量
            preview_count = db.query(PanoramaPreviewImages).filter(
                PanoramaPreviewImages.panorama_id == panorama.panorama_id
            ).count()

            result.append({
                "id": panorama.panorama_id,
                "panorama_image": panorama_image_url,
                "thumbnail": thumbnail_url,
                "description": panorama.description,
                "shoot_time": panorama.shoot_time.strftime("%Y-%m-%d %H:%M:%S") if panorama.shoot_time else None,
                "status": panorama.status,
                "preview_count": preview_count,
                "created_at": panorama.created_at.strftime("%Y-%m-%d %H:%M:%S") if panorama.created_at else None
            })

        return BaseResponse(data=result)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取可用全景图失败: {str(e)}")


@app.post("/api/panorama/locations/{location_id}/attach-panorama", response_model=BaseResponse)
async def attach_panorama_to_location(
        location_id: int,
        panorama_id: int,
        preview_image_ids: Optional[List[int]] = Form(None),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    为地点关联全景图和预览图
    """
    try:
        location = db.query(Location).filter(Location.location_id == location_id).first()
        if not location:
            return BaseResponse(code="404", msg="地点不存在")

        # 检查地点是否已有全景图
        if location.panorama_id:
            return BaseResponse(code="400", msg="该地点已有关联的全景图")

        # 检查全景图是否存在
        panorama = db.query(Panorama).filter(Panorama.panorama_id == panorama_id).first()
        if not panorama:
            return BaseResponse(code="404", msg="全景图不存在")

        # 检查该全景图是否已被其他地点使用
        used_location = db.query(Location).filter(
            Location.panorama_id == panorama_id
        ).first()
        if used_location:
            return BaseResponse(code="400", msg="该全景图已被其他地点使用")

        # 关联全景图
        location.panorama_id = panorama_id
        location.updated_at = datetime.now()

        # 关联预览图（如果提供了）
        if preview_image_ids:
            for i, image_id in enumerate(preview_image_ids):
                # 验证图片是否存在
                image_storage = db.query(ImageStorage).filter(
                    ImageStorage.image_id == image_id
                ).first()
                if image_storage:
                    panorama_preview = PanoramaPreviewImages(
                        panorama_id=panorama_id,
                        preview_image_id=image_id,
                        sort_order=i
                    )
                    db.add(panorama_preview)

        db.commit()

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="关联全景图",
            target=location.name,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"为地点 '{location.name}' 关联全景图 {panorama_id}"
        )
        db.add(log)
        db.commit()

        return BaseResponse(
            msg="全景图关联成功",
            data={
                "location_id": location_id,
                "panorama_id": panorama_id,
                "preview_count": len(preview_image_ids) if preview_image_ids else 0
            }
        )
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"关联全景图失败: {str(e)}")


@app.post("/api/panorama/locations/{location_id}/detach-panorama", response_model=BaseResponse)
async def detach_panorama_from_location(
        location_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    解除地点与全景图的关联
    """
    try:
        location = db.query(Location).filter(Location.location_id == location_id).first()
        if not location:
            return BaseResponse(code="404", msg="地点不存在")

        if not location.panorama_id:
            return BaseResponse(code="400", msg="该地点没有关联的全景图")

        panorama_id = location.panorama_id

        # 解除关联
        location.panorama_id = None
        location.updated_at = datetime.now()

        # 可以保留全景图预览图，或者删除（根据需求选择）
        # 这里选择删除该全景图的预览图关联
        db.query(PanoramaPreviewImages).filter(
            PanoramaPreviewImages.panorama_id == panorama_id
        ).delete(synchronize_session=False)

        db.commit()

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="解除全景图关联",
            target=location.name,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"解除地点 '{location.name}' 与全景图 {panorama_id} 的关联"
        )
        db.add(log)
        db.commit()

        return BaseResponse(
            msg="全景图关联已解除",
            data={
                "location_id": location_id,
                "panorama_id": panorama_id
            }
        )
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"解除关联失败: {str(e)}")


@app.get("/api/panorama/panoramas", response_model=BaseResponse)
async def get_panoramas(db: Session = Depends(get_db)):
    """获取所有全景图（包括关联信息）"""
    panoramas_data = db.query(Panorama).all()

    panoramas = []
    for panorama in panoramas_data:
        # 检查全景图是否被地点使用
        location = db.query(Location).filter(Location.panorama_id == panorama.panorama_id).first()

        gcj_lng, gcj_lat = wgs84_to_gcj02(panorama.longitude, panorama.latitude)

        # 获取图片URL
        panorama_image_url = f"/api/images/{panorama.panorama_image_id}"
        thumbnail_url = f"/api/images/{panorama.thumbnail_image_id}"

        # 获取预览图
        preview_images = db.query(PanoramaPreviewImages, ImageStorage).join(
            ImageStorage,
            PanoramaPreviewImages.preview_image_id == ImageStorage.image_id
        ).filter(
            PanoramaPreviewImages.panorama_id == panorama.panorama_id
        ).order_by(PanoramaPreviewImages.sort_order).all()

        preview_urls = []
        for preview, image_storage in preview_images:
            preview_urls.append(f"/api/images/{image_storage.image_id}")

        panorama_info = {
            "id": panorama.panorama_id,
            "panoramaImage": panorama_image_url,
            "thumbnail": thumbnail_url,
            "description": panorama.description,
            "timestamp": panorama.shoot_time.strftime("%Y-%m-%d %H:%M:%S") if panorama.shoot_time else None,
            "longitude": gcj_lng,
            "latitude": gcj_lat,
            "status": panorama.status,
            "preview_images": preview_urls,
            "is_used": location is not None,
            "location_id": location.location_id if location else None,
            "location_name": location.name if location else None
        }

        panoramas.append(panorama_info)

    return BaseResponse(data=panoramas)


@app.get("/api/panorama/timemachine/{location_id}", response_model=BaseResponse)
async def get_timemachine_data(location_id: int, db: Session = Depends(get_db)):
    time_machine_data = db.query(TimeMachineData, Panorama, Location).join(
        Panorama, TimeMachineData.panorama_id == Panorama.panorama_id
    ).join(
        Location, TimeMachineData.location_id == Location.location_id
    ).filter(TimeMachineData.location_id == location_id).all()

    result = []
    for tmd, panorama, location in time_machine_data:
        gcj_lng, gcj_lat = wgs84_to_gcj02(panorama.longitude, panorama.latitude)

        # 获取预览图片URL
        images_list = []
        if tmd.image_ids:
            for image_id in tmd.image_ids:
                images_list.append(f"/api/images/{image_id}")

        # 获取全景图和缩略图URL
        panorama_image_url = f"/api/images/{panorama.panorama_image_id}"
        thumbnail_url = f"/api/images/{panorama.thumbnail_image_id}"

        result.append({
            "id": tmd.time_machine_id,
            "locationId": tmd.location_id,
            "year": tmd.year,
            "month": tmd.month,
            "label": tmd.label,
            "panoramaImage": panorama_image_url,
            "thumbnail": thumbnail_url,
            "description": tmd.description,
            "address": tmd.address,
            "images": images_list,
            "longitude": gcj_lng,
            "latitude": gcj_lat
        })

    return BaseResponse(data=result)


# ========== 管理员端接口 ==========
@app.get("/api/manager/dashboard/stats", response_model=BaseResponse)
async def get_dashboard_stats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    total_panoramas = db.query(Panorama).count()
    pending_review = db.query(Panorama).filter(Panorama.status == "pending").count()

    weekly_new = db.query(Panorama).filter(
        Panorama.created_at >= datetime.now() - timedelta(days=7)
    ).count()

    online_users = db.query(User).filter(
        User.last_login_time >= datetime.now() - timedelta(minutes=5)
    ).count()

    today_active_users = db.query(User).filter(
        func.date(User.last_login_time) == datetime.now().date()
    ).count()

    # 统计地点使用情况
    locations_with_panorama = db.query(Location).filter(Location.panorama_id.isnot(None)).count()
    total_locations = db.query(Location).count()

    stats = {
        "totalPanoramas": total_panoramas,
        "pendingReview": pending_review,
        "weeklyNew": weekly_new,
        "onlineUsers": online_users,
        "todayActiveUsers": today_active_users,
        "locationsWithPanorama": locations_with_panorama,
        "totalLocations": total_locations,
        "systemHealth": {
            "cpu": round(random.uniform(20, 80), 1),
            "memory": round(random.uniform(40, 90), 1),
            "disk": round(random.uniform(60, 95), 1)
        }
    }
    return BaseResponse(data=stats)


@app.get("/api/manager/data/list", response_model=DataListResponse)
async def get_data_list(
        status: str = Query("all"),
        keyword: str = Query(None),
        page: int = Query(1, ge=1),
        pageSize: int = Query(10, ge=1),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    query = db.query(Panorama)

    if status != "all":
        query = query.filter(Panorama.status == status)

    if keyword:
        query = query.filter(
            or_(
                Panorama.panorama_id.like(f"%{keyword}%"),
                Panorama.description.like(f"%{keyword}%")
            )
        )

    total = query.count()
    data_items = query.offset((page - 1) * pageSize).limit(pageSize).all()

    result_list = []
    for panorama in data_items:
        # 检查是否被地点使用
        location = db.query(Location).filter(Location.panorama_id == panorama.panorama_id).first()

        # 获取缩略图URL
        thumbnail_url = f"/api/images/{panorama.thumbnail_image_id}"

        result_list.append({
            "id": panorama.panorama_id,
            "name": f"全景图数据{str(panorama.panorama_id).zfill(3)}",
            "thumbnail": thumbnail_url,
            "shootTime": panorama.shoot_time.strftime("%Y-%m-%d %H:%M:%S") if panorama.shoot_time else "",
            "location": location.name if location else "未使用",
            "status": panorama.status,
            "statusText": get_status_text(panorama.status)
        })

    return DataListResponse(data={
        "list": result_list,
        "total": total,
        "page": page,
        "pageSize": pageSize
    })


@app.get("/api/manager/data/{data_id}", response_model=BaseResponse)
async def get_data_detail(
        data_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    panorama = db.query(Panorama).filter(Panorama.panorama_id == data_id).first()

    if not panorama:
        raise HTTPException(status_code=404, detail="数据不存在")

    # 检查是否被地点使用
    location = db.query(Location).filter(Location.panorama_id == data_id).first()

    # 获取全景图URL
    panorama_image_url = f"/api/images/{panorama.panorama_image_id}"

    metadata = panorama.image_metadata or {
        "camera": "DJI Mavic 3",
        "resolution": "8192x4096",
        "format": "JPEG"
    }

    # 获取预览图
    preview_images = db.query(PanoramaPreviewImages, ImageStorage).join(
        ImageStorage,
        PanoramaPreviewImages.preview_image_id == ImageStorage.image_id
    ).filter(
        PanoramaPreviewImages.panorama_id == data_id
    ).order_by(PanoramaPreviewImages.sort_order).all()

    preview_urls = []
    for preview, image_storage in preview_images:
        preview_urls.append(f"/api/images/{image_storage.image_id}")

    data_detail = {
        "id": panorama.panorama_id,
        "name": f"全景图数据{str(panorama.panorama_id).zfill(3)}",
        "panoramaImage": panorama_image_url,
        "shootTime": panorama.shoot_time.strftime("%Y-%m-%d %H:%M:%S") if panorama.shoot_time else "",
        "location": location.name if location else "未使用",
        "location_id": location.location_id if location else None,
        "longitude": float(panorama.longitude) if panorama.longitude else 0.0,
        "latitude": float(panorama.latitude) if panorama.latitude else 0.0,
        "status": panorama.status,
        "description": panorama.description or "这是一张高质量的全景图数据。",
        "metadata": metadata,
        "preview_images": preview_urls,
        "created_at": panorama.created_at.strftime("%Y-%m-%d %H:%M:%S") if panorama.created_at else ""
    }
    return BaseResponse(data=data_detail)


@app.post("/api/manager/data/{data_id}/review", response_model=BaseResponse)
async def review_data(
        data_id: int,
        request: ReviewRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    panorama = db.query(Panorama).filter(Panorama.panorama_id == data_id).first()
    if not panorama:
        raise HTTPException(status_code=404, detail="数据不存在")

    new_status = "published" if request.action == "approve" else "rejected"
    panorama.status = new_status
    db.commit()

    log = OperationLog(
        operator=current_user.username,
        action="数据审核",
        target=f"全景图数据{data_id}",
        operation_time=datetime.now(),
        ip_address="192.168.1.1",
        result="成功",
        details=f"审核操作: {request.action}, 备注: {request.comment}"
    )
    db.add(log)
    db.commit()

    return BaseResponse(
        msg="审核通过" if request.action == "approve" else "审核拒绝",
        data={"id": data_id, "status": new_status}
    )


@app.delete("/api/manager/data/{data_id}", response_model=BaseResponse)
async def delete_data(
        data_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        panorama = db.query(Panorama).filter(Panorama.panorama_id == data_id).first()
        if not panorama:
            raise HTTPException(status_code=404, detail="数据不存在")

        # 检查是否被地点使用
        location = db.query(Location).filter(Location.panorama_id == data_id).first()
        if location:
            # 解除地点关联
            location.panorama_id = None

        # 先删除关联的 time_machine_data 记录
        db.query(TimeMachineData).filter(TimeMachineData.panorama_id == data_id).delete()

        # 删除全景图预览图关联
        db.query(PanoramaPreviewImages).filter(
            PanoramaPreviewImages.panorama_id == data_id
        ).delete()

        # 然后再删除全景数据
        db.delete(panorama)
        db.commit()

        log = OperationLog(
            operator=current_user.username,
            action="数据删除",
            target=f"全景图数据{data_id}",
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details="删除全景图数据及相关关联数据"
        )
        db.add(log)
        db.commit()

        return BaseResponse(msg="删除成功", data={"id": data_id})

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@app.get("/api/manager/users/list", response_model=UserListResponse)
async def get_user_list(
        page: int = Query(1, ge=1),
        pageSize: int = Query(10, ge=1),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    total = db.query(User).count()
    users = db.query(User).offset((page - 1) * pageSize).limit(pageSize).all()

    user_list = []
    for user in users:
        user_list.append({
            "id": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "roleText": get_role_text(user.role),
            "status": user.status,
            "lastLoginTime": user.last_login_time.strftime("%Y-%m-%d %H:%M:%S") if user.last_login_time else "从未登录"
        })

    return UserListResponse(data={
        "list": user_list,
        "total": total,
        "page": page,
        "pageSize": pageSize
    })


@app.put("/api/manager/users/{user_id}", response_model=BaseResponse)
async def update_user(
        user_id: int,
        request: UserUpdateRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()

    return BaseResponse(msg="更新成功", data={"id": user_id, **request.model_dump()})


@app.get("/api/manager/monitor/performance", response_model=BaseResponse)
async def get_performance_data(
        timeRange: str = Query("1h"),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    data = []
    now = datetime.now()

    if timeRange == "1h":
        points = 60
        interval = timedelta(minutes=1)
    elif timeRange == "today":
        points = 24
        interval = timedelta(hours=1)
    else:
        points = 7
        interval = timedelta(days=1)

    for i in range(points):
        time_point = now - (points - 1 - i) * interval
        data.append({
            "time": time_point.isoformat(),
            "cpu": round(random.uniform(20, 80), 1),
            "memory": round(random.uniform(40, 90), 1),
            "disk": round(random.uniform(60, 95), 1),
            "diskIOPS": random.randint(100, 1000),
            "apiResponseTime": round(random.uniform(50, 500), 1)
        })

    return BaseResponse(data=data)


@app.get("/api/manager/monitor/services", response_model=BaseResponse)
async def get_service_status(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    services_data = db.query(ServiceStatus).all()

    services = []
    for service in services_data:
        services.append({
            "name": service.name,
            "status": service.status,
            "statusText": service.status_text,
            "uptime": service.uptime,
            "lastCheck": service.last_check.strftime("%Y-%m-%d %H:%M:%S")
        })

    return BaseResponse(data=services)


@app.get("/api/manager/monitor/logs", response_model=LogListResponse)
async def get_operation_logs(
        page: int = Query(1, ge=1),
        pageSize: int = Query(10, ge=1),
        operator: str = Query(None),
        actionType: str = Query(None),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    query = db.query(OperationLog)

    if operator:
        query = query.filter(OperationLog.operator.contains(operator))
    if actionType:
        query = query.filter(OperationLog.action == actionType)

    total = query.count()
    logs = query.order_by(OperationLog.operation_time.desc()).offset(
        (page - 1) * pageSize
    ).limit(pageSize).all()

    log_list = []
    for log in logs:
        log_list.append({
            "id": log.log_id,
            "operator": log.operator,
            "action": log.action,
            "target": log.target,
            "time": log.operation_time.strftime("%Y-%m-%d %H:%M:%S"),
            "ip": log.ip_address,
            "result": log.result
        })

    return LogListResponse(data={
        "list": log_list,
        "total": total,
        "page": page,
        "pageSize": pageSize
    })


# ========== 批量操作接口 ==========
@app.post("/api/manager/data/batch", response_model=BaseResponse)
async def batch_operation(
        request: BatchOperationRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not request.data_ids:
        raise HTTPException(status_code=400, detail="请选择要操作的数据")

    success_count = 0
    failed_count = 0

    for data_id in request.data_ids:
        try:
            panorama = db.query(Panorama).filter(Panorama.panorama_id == data_id).first()
            if panorama:
                if request.action == "delete":
                    # 检查是否被地点使用
                    location = db.query(Location).filter(Location.panorama_id == data_id).first()
                    if location:
                        location.panorama_id = None
                    db.delete(panorama)
                elif request.action == "publish":
                    panorama.status = "published"
                db.commit()
                success_count += 1

                # 记录操作日志
                log = OperationLog(
                    operator=current_user.username,
                    action=f"批量{request.action}",
                    target=f"全景图数据{data_id}",
                    operation_time=datetime.now(),
                    ip_address="192.168.1.1",
                    result="成功",
                    details=f"批量操作: {request.action}"
                )
                db.add(log)

        except Exception as e:
            failed_count += 1
            print(f"操作数据 {data_id} 失败: {e}")

    db.commit()

    return BaseResponse(
        msg=f"批量操作完成，成功: {success_count}，失败: {failed_count}",
        data={"success": success_count, "failed": failed_count}
    )


# ========== 数据上传接口 ==========
@app.post("/api/manager/data/upload", response_model=BaseResponse)
async def upload_panorama_data(
        panorama_file: UploadFile = File(...),
        thumbnail_file: UploadFile = File(...),
        location_id: int = Form(None),
        location_name: str = Form(None),
        description: str = Form(None),
        shoot_time: str = Form(...),
        longitude: float = Form(...),
        latitude: float = Form(...),
        address: str = Form(None),
        preview_files: Optional[List[UploadFile]] = File(None),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        # 上传全景图
        panorama_data = await panorama_file.read()
        panorama_image = ImageStorage(
            filename=panorama_file.filename,
            file_data=panorama_data,
            file_size=len(panorama_data),
            mime_type=panorama_file.content_type,
            image_type='panorama',
            created_by=current_user.user_id
        )
        db.add(panorama_image)
        db.flush()  # 获取ID

        # 上传缩略图
        thumbnail_data = await thumbnail_file.read()
        thumbnail_image = ImageStorage(
            filename=thumbnail_file.filename,
            file_data=thumbnail_data,
            file_size=len(thumbnail_data),
            mime_type=thumbnail_file.content_type,
            image_type='thumbnail',
            created_by=current_user.user_id
        )
        db.add(thumbnail_image)
        db.flush()  # 获取ID

        # 创建新地点或使用现有地点
        location = None
        if location_id:
            location = db.query(Location).filter(Location.location_id == location_id).first()
        elif location_name:
            location = Location(
                name=location_name,
                longitude=longitude,
                latitude=latitude,
                address=address,
                description=description
            )
            db.add(location)
            db.flush()

        # 创建全景图记录
        panorama = Panorama(
            panorama_image_id=panorama_image.image_id,
            thumbnail_image_id=thumbnail_image.image_id,
            description=description,
            shoot_time=datetime.strptime(shoot_time, "%Y-%m-%d %H:%M:%S"),
            longitude=longitude,
            latitude=latitude,
            status="pending",
            created_by=current_user.user_id
        )
        db.add(panorama)
        db.flush()

        # 上传预览图
        preview_image_ids = []
        if preview_files:
            for i, preview_file in enumerate(preview_files):
                preview_data = await preview_file.read()
                preview_image = ImageStorage(
                    filename=preview_file.filename,
                    file_data=preview_data,
                    file_size=len(preview_data),
                    mime_type=preview_file.content_type,
                    image_type='preview',
                    created_by=current_user.user_id
                )
                db.add(preview_image)
                db.flush()
                preview_image_ids.append(preview_image.image_id)

                # 关联预览图
                panorama_preview = PanoramaPreviewImages(
                    panorama_id=panorama.panorama_id,
                    preview_image_id=preview_image.image_id,
                    sort_order=i
                )
                db.add(panorama_preview)

        # 如果提供了地点，自动关联全景图
        if location and not location.panorama_id:
            location.panorama_id = panorama.panorama_id

        db.commit()

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="数据上传",
            target=f"全景图数据{panorama.panorama_id}",
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details="上传新的全景图数据"
        )
        db.add(log)
        db.commit()

        return BaseResponse(
            msg="数据上传成功，等待审核",
            data={
                "id": panorama.panorama_id,
                "preview_count": len(preview_image_ids),
                "location_id": location.location_id if location else None
            }
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@app.put("/api/manager/data/{data_id}", response_model=BaseResponse)
async def update_panorama_data(
        data_id: int,
        request: PanoramaUpdateRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    panorama = db.query(Panorama).filter(Panorama.panorama_id == data_id).first()
    if not panorama:
        raise HTTPException(status_code=404, detail="数据不存在")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "shoot_time" and value:
            setattr(panorama, field, datetime.strptime(value, "%Y-%m-%d %H:%M:%S"))
        elif field == "metadata":
            setattr(panorama, "image_metadata", value)
        else:
            setattr(panorama, field, value)

    db.commit()

    # 记录操作日志
    log = OperationLog(
        operator=current_user.username,
        action="数据编辑",
        target=f"全景图数据{data_id}",
        operation_time=datetime.now(),
        ip_address="192.168.1.1",
        result="成功",
        details="编辑全景图数据信息"
    )
    db.add(log)
    db.commit()

    return BaseResponse(msg="数据更新成功", data={"id": data_id})


# ========== 用户管理接口 ==========
@app.post("/api/manager/users", response_model=BaseResponse)
async def create_user(
        request: UserCreateRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # 检查用户名和邮箱是否已存在
    existing_user = db.query(User).filter(
        or_(User.username == request.username, User.email == request.email)
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    # 创建新用户
    user = User(
        username=request.username,
        password=request.password,  # 实际应用中应该加密
        email=request.email,
        phone=request.phone,
        role=request.role,
        status=True,
        last_login_time=None
    )

    db.add(user)
    db.commit()

    # 记录操作日志
    log = OperationLog(
        operator=current_user.username,
        action="用户创建",
        target=request.username,
        operation_time=datetime.now(),
        ip_address="192.168.1.1",
        result="成功",
        details=f"创建新用户，角色: {request.role}"
    )
    db.add(log)
    db.commit()

    return BaseResponse(msg="用户创建成功", data={"id": user.user_id})


@app.delete("/api/manager/users/{user_id}", response_model=BaseResponse)
async def delete_user(
        user_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # 防止删除自己
    if user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="不能删除自己的账户")

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    username = user.username
    db.delete(user)
    db.commit()

    # 记录操作日志
    log = OperationLog(
        operator=current_user.username,
        action="用户删除",
        target=username,
        operation_time=datetime.now(),
        ip_address="192.168.1.1",
        result="成功",
        details="删除用户账户"
    )
    db.add(log)
    db.commit()

    return BaseResponse(msg="用户删除成功", data={"id": user_id})


@app.put("/api/manager/users/{user_id}/permissions", response_model=BaseResponse)
async def update_user_permissions(
        user_id: int,
        request: UserPermissionRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.role = request.role
    # 这里可以添加更细粒度的权限控制字段
    db.commit()

    # 记录操作日志
    log = OperationLog(
        operator=current_user.username,
        action="权限修改",
        target=user.username,
        operation_time=datetime.now(),
        ip_address="192.168.1.1",
        result="成功",
        details=f"修改用户权限，新角色: {request.role}"
    )
    db.add(log)
    db.commit()

    return BaseResponse(msg="权限更新成功", data={"id": user_id})


# ========== 图片管理接口 ==========
@app.post("/api/images/upload", response_model=ImageUploadResponse)
async def upload_image(
        file: UploadFile = File(...),
        image_type: str = Form(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    上传图片到数据库
    """
    try:
        # 验证文件类型
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg']
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="只支持JPEG和PNG格式的图片")

        # 读取文件数据
        file_data = await file.read()
        file_size = len(file_data)

        # 如果是缩略图，自动生成缩略版本
        if image_type == 'thumbnail':
            # 使用PIL生成缩略图
            image = Image.open(BytesIO(file_data))
            image.thumbnail((200, 200))
            thumb_io = BytesIO()
            image.save(thumb_io, format='JPEG')
            file_data = thumb_io.getvalue()
            file_size = len(file_data)

        # 保存到数据库
        image_storage = ImageStorage(
            filename=file.filename,
            file_data=file_data,
            file_size=file_size,
            mime_type=file.content_type,
            image_type=image_type,
            created_by=current_user.user_id
        )

        db.add(image_storage)
        db.commit()
        db.refresh(image_storage)

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="图片上传",
            target=file.filename,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"上传{image_type}类型图片，大小: {file_size}字节"
        )
        db.add(log)
        db.commit()

        image_info = ImageInfo(
            imageId=image_storage.image_id,
            filename=image_storage.filename,
            mimeType=image_storage.mime_type,
            fileSize=image_storage.file_size,
            imageType=image_storage.image_type,
            createdAt=image_storage.created_at.strftime("%Y-%m-%d %H:%M:%S")
        )

        return ImageUploadResponse(data=image_info)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"图片上传失败: {str(e)}")


@app.get("/api/images/{image_id}")
async def get_image(
        image_id: int,
        db: Session = Depends(get_db)
):
    """
    获取图片数据
    """
    image_storage = db.query(ImageStorage).filter(ImageStorage.image_id == image_id).first()
    if not image_storage:
        raise HTTPException(status_code=404, detail="图片不存在")

    return Response(
        content=image_storage.file_data,
        media_type=image_storage.mime_type
    )


@app.get("/api/images/{image_id}/base64")
async def get_image_base64(
        image_id: int,
        db: Session = Depends(get_db)
):
    """
    获取图片的base64编码
    """
    image_storage = db.query(ImageStorage).filter(ImageStorage.image_id == image_id).first()
    if not image_storage:
        raise HTTPException(status_code=404, detail="图片不存在")

    base64_data = base64.b64encode(image_storage.file_data).decode('utf-8')
    data_url = f"data:{image_storage.mime_type};base64,{base64_data}"

    return BaseResponse(data={"data_url": data_url})


@app.get("/api/panorama/locations/{location_id}", response_model=BaseResponse)
async def get_location_detail(
    location_id: int,
    db: Session = Depends(get_db)
):
    """
    获取单个地点详情
    """
    try:
        location = db.query(Location).filter(Location.location_id == location_id).first()
        if not location:
            return BaseResponse(code="404", msg="地点不存在")

        location_info = {
            "id": location.location_id,
            "name": location.name,
            "longitude": location.longitude,
            "latitude": location.latitude,
            "rating": float(location.rating) if location.rating else None,
            "category": location.category,
            "description": location.description,
            "address": location.address
        }

        # 如果有全景图关联
        if location.panorama_id:
            panorama = db.query(Panorama).filter(
                Panorama.panorama_id == location.panorama_id
            ).first()

            if panorama:
                # 获取全景图和缩略图URL
                panorama_image_url = f"/api/images/{panorama.panorama_image_id}"
                thumbnail_url = f"/api/images/{panorama.thumbnail_image_id}"

                location_info["panorama"] = {
                    "id": panorama.panorama_id,
                    "panorama_image": panorama_image_url,
                    "thumbnail": thumbnail_url,
                    "description": panorama.description,
                    "shoot_time": panorama.shoot_time.strftime(
                        "%Y-%m-%d %H:%M:%S") if panorama.shoot_time else None,
                    "longitude": float(panorama.longitude) if panorama.longitude else None,
                    "latitude": float(panorama.latitude) if panorama.latitude else None,
                    "status": panorama.status
                }

                # 获取预览图
                preview_images = db.query(PanoramaPreviewImages, ImageStorage).join(
                    ImageStorage,
                    PanoramaPreviewImages.preview_image_id == ImageStorage.image_id
                ).filter(
                    PanoramaPreviewImages.panorama_id == panorama.panorama_id
                ).order_by(PanoramaPreviewImages.sort_order).all()

                preview_urls = []
                for preview, image_storage in preview_images:
                    preview_urls.append(f"/api/images/{image_storage.image_id}")

                location_info["preview_images"] = preview_urls

        return BaseResponse(data=location_info)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取地点详情失败: {str(e)}")


# ========== 预览图管理接口 ==========
@app.post("/api/panorama/{panorama_id}/add-preview", response_model=BaseResponse)
async def add_panorama_preview(
        panorama_id: int,
        preview_image_ids: List[int],
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    为全景图添加预览图
    """
    try:
        panorama = db.query(Panorama).filter(Panorama.panorama_id == panorama_id).first()
        if not panorama:
            return BaseResponse(code="404", msg="全景图不存在")

        # 获取当前最大的排序值
        max_sort = db.query(func.max(PanoramaPreviewImages.sort_order)).filter(
            PanoramaPreviewImages.panorama_id == panorama_id
        ).scalar() or 0

        added_count = 0
        for i, image_id in enumerate(preview_image_ids, max_sort + 1):
            # 验证图片是否存在
            image_storage = db.query(ImageStorage).filter(
                ImageStorage.image_id == image_id
            ).first()
            if image_storage:
                panorama_preview = PanoramaPreviewImages(
                    panorama_id=panorama_id,
                    preview_image_id=image_id,
                    sort_order=i
                )
                db.add(panorama_preview)
                added_count += 1

        db.commit()

        return BaseResponse(
            msg=f"成功添加 {added_count} 张预览图",
            data={
                "panorama_id": panorama_id,
                "added_count": added_count
            }
        )
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"添加预览图失败: {str(e)}")


@app.delete("/api/panorama/{panorama_id}/remove-preview", response_model=BaseResponse)
async def remove_panorama_preview(
        panorama_id: int,
        preview_image_ids: List[int],
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    移除全景图的预览图
    """
    try:
        panorama = db.query(Panorama).filter(Panorama.panorama_id == panorama_id).first()
        if not panorama:
            return BaseResponse(code="404", msg="全景图不存在")

        removed_count = 0
        for image_id in preview_image_ids:
            result = db.query(PanoramaPreviewImages).filter(
                PanoramaPreviewImages.panorama_id == panorama_id,
                PanoramaPreviewImages.preview_image_id == image_id
            ).delete(synchronize_session=False)
            removed_count += result

        db.commit()

        # 重新排序
        previews = db.query(PanoramaPreviewImages).filter(
            PanoramaPreviewImages.panorama_id == panorama_id
        ).order_by(PanoramaPreviewImages.sort_order).all()

        for i, preview in enumerate(previews):
            preview.sort_order = i + 1

        db.commit()

        return BaseResponse(
            msg=f"成功移除 {removed_count} 张预览图",
            data={
                "panorama_id": panorama_id,
                "removed_count": removed_count
            }
        )
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"移除预览图失败: {str(e)}")


@app.put("/api/panorama/{panorama_id}/reorder-previews", response_model=BaseResponse)
async def reorder_panorama_previews(
        panorama_id: int,
        preview_order: List[int],  # 图片ID的排序列表
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    重新排序全景图的预览图
    """
    try:
        panorama = db.query(Panorama).filter(Panorama.panorama_id == panorama_id).first()
        if not panorama:
            return BaseResponse(code="404", msg="全景图不存在")

        # 更新排序
        for i, image_id in enumerate(preview_order, 1):
            preview = db.query(PanoramaPreviewImages).filter(
                PanoramaPreviewImages.panorama_id == panorama_id,
                PanoramaPreviewImages.preview_image_id == image_id
            ).first()
            if preview:
                preview.sort_order = i

        db.commit()

        return BaseResponse(
            msg="预览图排序更新成功",
            data={
                "panorama_id": panorama_id,
                "preview_count": len(preview_order)
            }
        )
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"更新预览图排序失败: {str(e)}")


# ========== 检查接口 ==========
@app.get("/api/panorama/locations/{location_id}/delete-check", response_model=BaseResponse)
async def check_location_deletion(
        location_id: int,
        db: Session = Depends(get_db)
):
    """
    检查地点删除的影响
    """
    try:
        location = db.query(Location).filter(Location.location_id == location_id).first()
        if not location:
            return BaseResponse(code="404", msg="地点不存在")

        return BaseResponse(data={
            "location": {
                "id": location.location_id,
                "name": location.name,
                "created_at": location.created_at.strftime("%Y-%m-%d %H:%M:%S") if location.created_at else None
            },
            "affected_data": {
                "has_panorama": location.panorama_id is not None,
                "panorama_id": location.panorama_id
            },
            "warning": location.panorama_id is not None,
            "message": "删除此地点将解除与全景图的关联，但不会删除全景图本身。"
        })
    except Exception as e:
        return BaseResponse(code="500", msg=f"检查删除影响失败: {str(e)}")


# ========== 预览图相关接口 ==========
@app.get("/api/panorama/{panorama_id}/previews", response_model=BaseResponse)
async def get_panorama_previews(
    panorama_id: int,
    db: Session = Depends(get_db)
):
    """
    获取全景图的预览图片
    """
    try:
        # 获取预览图关联
        previews = db.query(PanoramaPreviewImages, ImageStorage).join(
            ImageStorage,
            PanoramaPreviewImages.preview_image_id == ImageStorage.image_id
        ).filter(
            PanoramaPreviewImages.panorama_id == panorama_id
        ).order_by(PanoramaPreviewImages.sort_order).all()

        preview_urls = []
        for preview, image_storage in previews:
            preview_urls.append(f"/api/images/{image_storage.image_id}")

        return BaseResponse(data=preview_urls)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取预览图片失败: {str(e)}")


@app.get("/api/images/{image_id}/info", response_model=BaseResponse)
async def get_image_info(
    image_id: int,
    db: Session = Depends(get_db)
):
    """
    获取图片详细信息
    """
    try:
        image_storage = db.query(ImageStorage).filter(ImageStorage.image_id == image_id).first()
        if not image_storage:
            return BaseResponse(code="404", msg="图片不存在")

        image_info = {
            "imageId": image_storage.image_id,
            "filename": image_storage.filename,
            "mimeType": image_storage.mime_type,
            "fileSize": image_storage.file_size,
            "imageType": image_storage.image_type,
            "createdAt": image_storage.created_at.strftime("%Y-%m-%d %H:%M:%S") if image_storage.created_at else None
        }

        return BaseResponse(data=image_info)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取图片信息失败: {str(e)}")


# ========== 时间机器预览接口 ==========
@app.get("/api/panorama/timemachine/previews/{panorama_id}", response_model=BaseResponse)
async def get_timemachine_previews(
    panorama_id: int,
    db: Session = Depends(get_db)
):
    """
    获取时间机器数据的预览图片（备用接口）
    """
    try:
        # 查找关联的时间机器数据
        time_machine_data = db.query(TimeMachineData).filter(
            TimeMachineData.panorama_id == panorama_id
        ).first()

        if not time_machine_data or not time_machine_data.image_ids:
            return BaseResponse(data=[])

        # 获取图片URL列表
        preview_urls = []
        for image_id in time_machine_data.image_ids:
            preview_urls.append(f"/api/images/{image_id}")

        return BaseResponse(data=preview_urls)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取时间机器预览失败: {str(e)}")


# ========== 新增收藏/浏览统计接口 ==========

@app.get("/api/shop/analytics/stats", response_model=BaseResponse)
async def get_analytics_stats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取收藏和浏览的统计数据
    """
    try:
        # 模拟数据，实际项目中应该从数据库统计
        import random
        from datetime import datetime, timedelta

        # 生成模拟数据
        stats = {
            "favoriteTotal": random.randint(1000, 5000),
            "favoritesToday": random.randint(10, 100),
            "viewsTotal": random.randint(5000, 20000),
            "viewsToday": random.randint(100, 500),
            "weeklyFavorites": [random.randint(5, 50) for _ in range(7)],
            "weeklyViews": [random.randint(50, 200) for _ in range(7)]
        }

        return BaseResponse(data=stats)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取统计数据失败: {str(e)}")


@app.get("/api/shop/analytics/trends", response_model=BaseResponse)
async def get_analytics_trends(
        timeRange: str = Query("today"),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取收藏和浏览趋势数据
    """
    try:
        import random
        from datetime import datetime, timedelta

        # 根据时间范围生成数据
        if timeRange == "today":
            points = 24  # 24小时
            data = []
            for i in range(points):
                hour = (datetime.now() - timedelta(hours=23 - i)).strftime("%H:00")
                data.append({
                    "time": hour,
                    "favorites": random.randint(0, 20),
                    "views": random.randint(0, 100)
                })
        elif timeRange == "7d":
            points = 7  # 7天
            data = []
            for i in range(points):
                date = (datetime.now() - timedelta(days=6 - i)).strftime("%m-%d")
                data.append({
                    "date": date,
                    "favorites": random.randint(10, 50),
                    "views": random.randint(50, 200)
                })
        elif timeRange == "30d":
            points = 30  # 30天
            data = []
            for i in range(points):
                date = (datetime.now() - timedelta(days=29 - i)).strftime("%m-%d")
                data.append({
                    "date": date,
                    "favorites": random.randint(5, 30),
                    "views": random.randint(30, 150)
                })
        else:
            data = []

        return BaseResponse(data=data)
    except Exception as e:
        # 返回模拟数据作为备选
        mock_data = [
            {"date": "01-10", "favorites": 12, "views": 85},
            {"date": "01-11", "favorites": 8, "views": 92},
            {"date": "01-12", "favorites": 15, "views": 120},
            {"date": "01-13", "favorites": 20, "views": 150},
            {"date": "01-14", "favorites": 18, "views": 135},
            {"date": "01-15", "favorites": 25, "views": 180},
            {"date": "01-16", "favorites": 22, "views": 165}
        ]
        return BaseResponse(data=mock_data)


# ========== 商铺管理接口 ==========

@app.get("/api/shop/list", response_model=BaseResponse)
async def get_shop_list(
        page: int = Query(1, ge=1),
        pageSize: int = Query(10, ge=1),
        keyword: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取商铺列表
    """
    try:
        query = db.query(Shop)

        # 搜索过滤
        if keyword:
            keyword_lower = keyword.lower()
            query = query.filter(
                or_(
                    Shop.username.ilike(f"%{keyword}%"),
                    Shop.email.ilike(f"%{keyword}%"),
                    Shop.province.ilike(f"%{keyword}%"),
                    Shop.city.ilike(f"%{keyword}%"),
                    Shop.district.ilike(f"%{keyword}%")
                )
            )

        # 计算总数
        total = query.count()

        # 分页查询
        shops = query.order_by(Shop.created_at.desc()) \
            .offset((page - 1) * pageSize) \
            .limit(pageSize) \
            .all()

        shop_list = []
        for shop in shops:
            # 获取角色标签
            role_map = {
                "admin": "饭店",
                "advanced": "商超",
                "user": "酒店"
            }

            # 确保 audit_status 有默认值
            audit_status = shop.audit_status or 'pending'

            shop_list.append({
                "id": shop.shop_id,
                "username": shop.username,
                "email": shop.email,  # 这里实际是地点
                "province": shop.province,
                "city": shop.city,
                "district": shop.district,
                "size": shop.size,
                "role": shop.role,
                "roleText": role_map.get(shop.role, "未知"),
                "status": shop.status,  # 显示状态
                "audit_status": audit_status,  # 审核状态
                "auditStatus": audit_status,   # 兼容前端两种字段名
                "lastLoginTime": shop.last_login_time.strftime("%Y-%m-%d %H:%M:%S") if shop.last_login_time else "从未更新"
            })

        return BaseResponse(data={
            "list": shop_list,
            "total": total,
            "page": page,
            "pageSize": pageSize
        })
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取商铺列表失败: {str(e)}")




@app.post("/api/shop", response_model=BaseResponse)
async def create_shop(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建新商铺
    """
    try:
        # 检查商铺名是否已存在
        existing_shop = db.query(Shop).filter(
            Shop.username == request.get("username")
        ).first()

        if existing_shop:
            return BaseResponse(code="400", msg="商铺名已存在")

        # 创建新商铺
        shop = Shop(
            username=request.get("username"),
            email=request.get("email"),  # 这里实际是地点
            province=request.get("province"),
            city=request.get("city"),
            district=request.get("district"),
            size=request.get("size", "small"),
            role=request.get("role", "admin"),
            status=True,  # 默认激活
            audit_status="pending",  # 默认待审核
            last_login_time=datetime.now()
        )

        db.add(shop)
        db.commit()
        db.refresh(shop)

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="商铺创建",
            target=shop.username,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"创建新商铺，类型: {shop.role}，规模: {shop.size}，审核状态: 待审核"
        )
        db.add(log)
        db.commit()

        return BaseResponse(msg="商铺创建成功，等待审核", data={"id": shop.shop_id})
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"创建商铺失败: {str(e)}")


@app.put("/api/shop/{shop_id}", response_model=BaseResponse)
async def update_shop(
        shop_id: int,
        request: dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    更新商铺信息
    """
    try:
        shop = db.query(Shop).filter(Shop.shop_id == shop_id).first()
        if not shop:
            return BaseResponse(code="404", msg="商铺不存在")

        # 更新字段
        update_fields = ["email", "province", "city", "district", "role", "size"]  # 新增size
        for field in update_fields:
            if field in request:
                setattr(shop, field, request[field])

        shop.updated_at = datetime.now()
        db.commit()

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="商铺更新",
            target=shop.username,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"更新商铺信息，规模: {shop.size}"
        )
        db.add(log)
        db.commit()

        return BaseResponse(msg="商铺更新成功")
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"更新商铺失败: {str(e)}")


@app.put("/api/shop/{shop_id}/status", response_model=BaseResponse)
async def update_shop_status(
        shop_id: int,
        status: bool = Query(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    更新商铺显示状态
    """
    try:
        shop = db.query(Shop).filter(Shop.shop_id == shop_id).first()
        if not shop:
            return BaseResponse(code="404", msg="商铺不存在")

        shop.status = status
        shop.updated_at = datetime.now()
        db.commit()

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="商铺状态修改",
            target=shop.username,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"将商铺状态修改为: {'显示' if status else '隐藏'}"
        )
        db.add(log)
        db.commit()

        return BaseResponse(msg=f"商铺已{'显示' if status else '隐藏'}")
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"更新商铺状态失败: {str(e)}")


@app.delete("/api/shop/{shop_id}", response_model=BaseResponse)
async def delete_shop(
        shop_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    删除商铺
    """
    try:
        shop = db.query(Shop).filter(Shop.shop_id == shop_id).first()
        if not shop:
            return BaseResponse(code="404", msg="商铺不存在")

        shop_name = shop.username
        db.delete(shop)
        db.commit()

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="商铺删除",
            target=shop_name,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details="删除商铺"
        )
        db.add(log)
        db.commit()

        return BaseResponse(msg="商铺删除成功")
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"删除商铺失败: {str(e)}")


@app.get("/api/shop/analytics/stats", response_model=BaseResponse)
async def get_shop_analytics_stats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取商铺统计数据（收藏和浏览）
    """
    try:
        import random
        from datetime import datetime, timedelta

        # 生成模拟数据
        stats = {
            "favoriteTotal": random.randint(1000, 5000),
            "favoritesToday": random.randint(10, 100),
            "viewsTotal": random.randint(5000, 20000),
            "viewsToday": random.randint(100, 500),
            "weeklyFavorites": [random.randint(5, 50) for _ in range(7)],
            "weeklyViews": [random.randint(50, 200) for _ in range(7)]
        }

        return BaseResponse(data=stats)
    except Exception as e:
        # 如果出错，返回默认数据
        return BaseResponse(data={
            "favoriteTotal": 0,
            "favoritesToday": 0,
            "viewsTotal": 0,
            "viewsToday": 0,
            "weeklyFavorites": [0, 0, 0, 0, 0, 0, 0],
            "weeklyViews": [0, 0, 0, 0, 0, 0, 0]
        })

@app.get("/api/shop/{shop_id}", response_model=BaseResponse)
async def get_shop_detail(
        shop_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取单个商铺详情
    """
    try:
        shop = db.query(Shop).filter(Shop.shop_id == shop_id).first()
        if not shop:
            return BaseResponse(code="404", msg="商铺不存在")

        # 获取角色标签
        role_map = {
            "admin": "饭店",
            "advanced": "商超",
            "user": "酒店"
        }

        shop_detail = {
            "id": shop.shop_id,
            "username": shop.username,
            "email": shop.email,  # 这里实际是地点
            "province": shop.province,
            "city": shop.city,
            "district": shop.district,
            "size": shop.size,  # 返回规模信息
            "role": shop.role,
            "roleText": role_map.get(shop.role, "未知"),
            "status": shop.status,
            "createdAt": shop.created_at.strftime("%Y-%m-%d %H:%M:%S") if shop.created_at else None,
            "updatedAt": shop.updated_at.strftime("%Y-%m-%d %H:%M:%S") if shop.updated_at else None,
            "lastLoginTime": shop.last_login_time.strftime("%Y-%m-%d %H:%M:%S") if shop.last_login_time else "从未更新"
        }

        return BaseResponse(data=shop_detail)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取商铺详情失败: {str(e)}")


# 在 main.py 中添加以下代码

# ========== 政府执法端接口 ==========

# 政府用户认证依赖
async def get_current_gov_user(token: str = Query(...), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="未授权")

    # 简化处理，实际应该验证token
    user = db.query(GovernmentUser).filter(GovernmentUser.gov_user_id == 1).first()  # 临时方案

    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或token无效")

    return user


@app.post("/api/government/login", response_model=GovernmentLoginResponse)
async def government_login(request: GovernmentLoginRequest, db: Session = Depends(get_db)):
    """政府执法人员登录"""
    user = db.query(GovernmentUser).filter(
        GovernmentUser.username == request.username,
        GovernmentUser.password == request.password,
        GovernmentUser.status == True
    ).first()

    if user:
        user.last_login_time = datetime.now()
        db.commit()

        user_info = GovernmentUserInfo(
            userId=user.gov_user_id,
            username=user.username,
            email=user.email,
            phone=user.phone or "",
            department=user.department,
            position=user.position or "",
            role=user.role,
            permissions=user.permissions,
            token=generate_guid()
        )
        return GovernmentLoginResponse(data=user_info)
    else:
        return GovernmentLoginResponse(code="400", msg="用户名或密码错误", data=None)


@app.get("/api/government/panoramas/all", response_model=BaseResponse)
async def get_all_panoramas_gov(
        zoom_level: Optional[int] = Query(None, description="地图缩放级别"),
        bounds: Optional[str] = Query(None, description="地图边界 minLng,minLat,maxLng,maxLat"),
        current_user: GovernmentUser = Depends(get_current_gov_user),
        db: Session = Depends(get_db)
):
    """
    政府端：获取所有全景数据（支持地图范围筛选）
    """
    try:
        query = db.query(Panorama).filter(Panorama.status == "published")

        # 如果提供了地图边界，进行空间筛选
        if bounds:
            try:
                bounds_list = [float(x.strip()) for x in bounds.split(',')]
                if len(bounds_list) == 4:
                    min_lng, min_lat, max_lng, max_lat = bounds_list
                    query = query.filter(
                        Panorama.longitude.between(min_lng, max_lng),
                        Panorama.latitude.between(min_lat, max_lat)
                    )
            except:
                pass

        panoramas_data = query.all()

        result = []
        for panorama in panoramas_data:
            # 获取地点信息
            location = db.query(Location).filter(Location.panorama_id == panorama.panorama_id).first()

            # 获取图片URL
            panorama_image_url = f"/api/images/{panorama.panorama_image_id}"
            thumbnail_url = f"/api/images/{panorama.thumbnail_image_id}"

            # 坐标转换
            gcj_lng, gcj_lat = wgs84_to_gcj02(panorama.longitude, panorama.latitude)

            panorama_info = {
                "id": panorama.panorama_id,
                "panorama_image": panorama_image_url,
                "thumbnail": thumbnail_url,
                "description": panorama.description,
                "shoot_time": panorama.shoot_time.strftime("%Y-%m-%d %H:%M:%S") if panorama.shoot_time else None,
                "longitude": gcj_lng,
                "latitude": gcj_lat,
                "original_longitude": panorama.longitude,
                "original_latitude": panorama.latitude,
                "status": panorama.status,
                "is_used": location is not None,
                "location_info": {
                    "id": location.location_id if location else None,
                    "name": location.name if location else None,
                    "address": location.address if location else None
                } if location else None,
                "metadata": panorama.image_metadata or {}
            }

            result.append(panorama_info)

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="查看全景数据",
            target="所有全景图",
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"政府用户查看全景数据，数量: {len(result)}"
        )
        db.add(log)
        db.commit()

        return BaseResponse(data=result)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取全景数据失败: {str(e)}")


@app.post("/api/government/tasks", response_model=BaseResponse)
async def create_law_enforcement_task(
        request: LawEnforcementTaskCreate,
        current_user: GovernmentUser = Depends(get_current_gov_user),
        db: Session = Depends(get_db)
):
    """
    创建执法任务（在地图上标点发布）
    """
    try:
        # 生成任务编号
        today = datetime.now().strftime("%Y%m%d")
        task_count = db.query(LawEnforcementTask).filter(
            func.date(LawEnforcementTask.created_at) == datetime.now().date()
        ).count() + 1

        task_code = f"TASK-{today}-{str(task_count).zfill(3)}"

        # 解析截止时间
        deadline_dt = None
        if request.deadline:
            try:
                deadline_dt = datetime.fromisoformat(request.deadline.replace('Z', '+00:00'))
            except:
                deadline_dt = datetime.strptime(request.deadline, "%Y-%m-%d %H:%M:%S")

        # 创建任务
        task = LawEnforcementTask(
            task_code=task_code,
            title=request.title,
            description=request.description,
            task_type=request.task_type,
            priority=request.priority,
            longitude=request.longitude,
            latitude=request.latitude,
            address=request.address,
            assigned_to=request.assigned_to,
            assigned_by=current_user.gov_user_id if request.assigned_to else None,
            deadline=deadline_dt,
            created_by=current_user.gov_user_id,
            attachments=request.attachments or []
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        # 记录任务历史
        history = TaskHistory(
            task_id=task.task_id,
            action="create",
            description=f"创建任务: {request.title}",
            performed_by=current_user.gov_user_id,
            old_status=None,
            new_status="pending"
        )
        db.add(history)

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="创建执法任务",
            target=task_code,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"创建{request.task_type}类型任务，优先级: {request.priority}"
        )
        db.add(log)
        db.commit()

        return BaseResponse(
            msg="任务创建成功",
            data={
                "task_id": task.task_id,
                "task_code": task.task_code,
                "title": task.title
            }
        )
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"创建任务失败: {str(e)}")


@app.get("/api/government/tasks", response_model=BaseResponse)
async def get_law_enforcement_tasks(
        status: Optional[str] = Query(None),
        task_type: Optional[str] = Query(None),
        priority: Optional[str] = Query(None),
        assigned_to: Optional[int] = Query(None),
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
        keyword: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        pageSize: int = Query(10, ge=1),
        current_user: GovernmentUser = Depends(get_current_gov_user),
        db: Session = Depends(get_db)
):
    """
    获取执法任务列表（支持多种筛选条件）
    """
    try:
        query = db.query(LawEnforcementTask)

        # 应用筛选条件
        if status:
            query = query.filter(LawEnforcementTask.status == status)
        if task_type:
            query = query.filter(LawEnforcementTask.task_type == task_type)
        if priority:
            query = query.filter(LawEnforcementTask.priority == priority)
        if assigned_to:
            query = query.filter(LawEnforcementTask.assigned_to == assigned_to)

        # 日期范围筛选
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(LawEnforcementTask.created_at >= start_dt)
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(LawEnforcementTask.created_at < end_dt)

        # 关键词搜索
        if keyword:
            query = query.filter(
                or_(
                    LawEnforcementTask.title.like(f"%{keyword}%"),
                    LawEnforcementTask.description.like(f"%{keyword}%"),
                    LawEnforcementTask.task_code.like(f"%{keyword}%")
                )
            )

        # 计算总数
        total = query.count()

        # 分页查询
        tasks = query.order_by(LawEnforcementTask.created_at.desc()) \
            .offset((page - 1) * pageSize) \
            .limit(pageSize) \
            .all()

        result = []
        for task in tasks:
            # 获取指派人和创建人信息
            assigned_user = None
            if task.assigned_to:
                assigned_user = db.query(GovernmentUser).filter(
                    GovernmentUser.gov_user_id == task.assigned_to
                ).first()

            created_user = db.query(GovernmentUser).filter(
                GovernmentUser.gov_user_id == task.created_by
            ).first()

            # 获取附件URL
            attachment_urls = []
            if task.attachments:
                for img_id in task.attachments:
                    attachment_urls.append(f"/api/images/{img_id}")

            task_info = {
                "id": task.task_id,
                "task_code": task.task_code,
                "title": task.title,
                "description": task.description,
                "task_type": task.task_type,
                "priority": task.priority,
                "status": task.status,
                "longitude": task.longitude,
                "latitude": task.latitude,
                "address": task.address,
                "assigned_to": {
                    "id": assigned_user.gov_user_id if assigned_user else None,
                    "name": assigned_user.username if assigned_user else None,
                    "department": assigned_user.department if assigned_user else None
                } if assigned_user else None,
                "created_by": {
                    "id": created_user.gov_user_id if created_user else None,
                    "name": created_user.username if created_user else None
                } if created_user else None,
                "deadline": task.deadline.strftime("%Y-%m-%d %H:%M:%S") if task.deadline else None,
                "completion_time": task.completion_time.strftime("%Y-%m-%d %H:%M:%S") if task.completion_time else None,
                "attachments": attachment_urls,
                "remarks": task.remarks,
                "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
                "updated_at": task.updated_at.strftime("%Y-%m-%d %H:%M:%S") if task.updated_at else None
            }

            result.append(task_info)

        return BaseResponse(data={
            "list": result,
            "total": total,
            "page": page,
            "pageSize": pageSize
        })
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取任务列表失败: {str(e)}")


@app.get("/api/government/tasks/map", response_model=BaseResponse)
async def get_tasks_for_map(
        min_longitude: float = Query(...),
        min_latitude: float = Query(...),
        max_longitude: float = Query(...),
        max_latitude: float = Query(...),
        status: Optional[str] = Query(None),
        task_type: Optional[str] = Query(None),
        current_user: GovernmentUser = Depends(get_current_gov_user),
        db: Session = Depends(get_db)
):
    """
    获取地图范围内的任务点（用于地图展示）
    """
    try:
        query = db.query(LawEnforcementTask).filter(
            LawEnforcementTask.longitude.between(min_longitude, max_longitude),
            LawEnforcementTask.latitude.between(min_latitude, max_latitude)
        )

        if status:
            query = query.filter(LawEnforcementTask.status == status)
        if task_type:
            query = query.filter(LawEnforcementTask.task_type == task_type)

        tasks = query.all()

        result = []
        for task in tasks:
            # 获取执行人信息
            assigned_user = None
            if task.assigned_to:
                assigned_user = db.query(GovernmentUser).filter(
                    GovernmentUser.gov_user_id == task.assigned_to
                ).first()

            # 坐标转换
            gcj_lng, gcj_lat = wgs84_to_gcj02(task.longitude, task.latitude)

            task_point = {
                "id": task.task_id,
                "task_code": task.task_code,
                "title": task.title,
                "task_type": task.task_type,
                "priority": task.priority,
                "status": task.status,
                "longitude": gcj_lng,
                "latitude": gcj_lat,
                "original_longitude": task.longitude,
                "original_latitude": task.latitude,
                "address": task.address,
                "assigned_to": assigned_user.username if assigned_user else None,
                "deadline": task.deadline.strftime("%Y-%m-%d") if task.deadline else None,
                "created_at": task.created_at.strftime("%Y-%m-%d") if task.created_at else None
            }

            result.append(task_point)

        return BaseResponse(data=result)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取地图任务点失败: {str(e)}")


@app.get("/api/government/tasks/statistics", response_model=BaseResponse)
async def get_task_statistics(
        period: str = Query("month", description="统计周期: day/week/month/year"),
        department: Optional[str] = Query(None),
        current_user: GovernmentUser = Depends(get_current_gov_user),
        db: Session = Depends(get_db)
):
    """
    获取任务统计信息
    """
    try:
        # 计算日期范围
        end_date = datetime.now()
        if period == "day":
            start_date = end_date - timedelta(days=1)
        elif period == "week":
            start_date = end_date - timedelta(days=7)
        elif period == "year":
            start_date = end_date - timedelta(days=365)
        else:  # month
            start_date = end_date - timedelta(days=30)

        # 基础查询
        query = db.query(LawEnforcementTask).filter(
            LawEnforcementTask.created_at >= start_date
        )

        if department:
            # 需要关联用户表查询部门
            pass

        total_tasks = query.count()

        # 按状态统计
        pending_tasks = query.filter(LawEnforcementTask.status == "pending").count()
        in_progress_tasks = query.filter(LawEnforcementTask.status == "in_progress").count()
        completed_tasks = query.filter(LawEnforcementTask.status == "completed").count()

        # 按类型统计
        type_stats = {}
        task_types = db.query(LawEnforcementTask.task_type,
                              func.count(LawEnforcementTask.task_id)) \
            .filter(LawEnforcementTask.created_at >= start_date) \
            .group_by(LawEnforcementTask.task_type).all()

        for task_type, count in task_types:
            type_stats[task_type] = count

        # 按优先级统计
        priority_stats = {}
        priorities = db.query(LawEnforcementTask.priority,
                              func.count(LawEnforcementTask.task_id)) \
            .filter(LawEnforcementTask.created_at >= start_date) \
            .group_by(LawEnforcementTask.priority).all()

        for priority, count in priorities:
            priority_stats[priority] = count

        statistics = {
            "period": period,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "total": total_tasks,
            "pending": pending_tasks,
            "in_progress": in_progress_tasks,
            "completed": completed_tasks,
            "completion_rate": round(completed_tasks / total_tasks * 100, 2) if total_tasks > 0 else 0,
            "by_type": type_stats,
            "by_priority": priority_stats
        }

        return BaseResponse(data=statistics)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取统计信息失败: {str(e)}")


@app.get("/api/government/tasks/{task_id}", response_model=BaseResponse)
async def get_task_detail(
        task_id: int,
        current_user: GovernmentUser = Depends(get_current_gov_user),
        db: Session = Depends(get_db)
):
    """
    获取任务详情
    """
    try:
        task = db.query(LawEnforcementTask).filter(LawEnforcementTask.task_id == task_id).first()
        if not task:
            return BaseResponse(code="404", msg="任务不存在")

        # 获取相关人员信息
        assigned_user = None
        if task.assigned_to:
            assigned_user = db.query(GovernmentUser).filter(
                GovernmentUser.gov_user_id == task.assigned_to
            ).first()

        assigned_by_user = None
        if task.assigned_by:
            assigned_by_user = db.query(GovernmentUser).filter(
                GovernmentUser.gov_user_id == task.assigned_by
            ).first()

        created_user = db.query(GovernmentUser).filter(
            GovernmentUser.gov_user_id == task.created_by
        ).first()

        # 获取附件URL
        attachment_urls = []
        if task.attachments:
            for img_id in task.attachments:
                attachment_urls.append(f"/api/images/{img_id}")

        # 获取任务历史
        history = db.query(TaskHistory).filter(
            TaskHistory.task_id == task_id
        ).order_by(TaskHistory.performed_at.desc()).all()

        history_list = []
        for h in history:
            performer = db.query(GovernmentUser).filter(
                GovernmentUser.gov_user_id == h.performed_by
            ).first()

            history_list.append({
                "id": h.history_id,
                "action": h.action,
                "description": h.description,
                "performed_by": performer.username if performer else "未知",
                "performed_at": h.performed_at.strftime("%Y-%m-%d %H:%M:%S") if h.performed_at else None,
                "old_status": h.old_status,
                "new_status": h.new_status
            })

        # 获取评论
        comments = db.query(TaskComment).filter(
            TaskComment.task_id == task_id
        ).order_by(TaskComment.created_at.desc()).all()

        comment_list = []
        for c in comments:
            commenter = db.query(GovernmentUser).filter(
                GovernmentUser.gov_user_id == c.created_by
            ).first()

            comment_attachments = []
            if c.attachments:
                for img_id in c.attachments:
                    comment_attachments.append(f"/api/images/{img_id}")

            comment_list.append({
                "id": c.comment_id,
                "content": c.content,
                "comment_type": c.comment_type,
                "created_by": commenter.username if commenter else "未知",
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else None,
                "attachments": comment_attachments
            })

        task_detail = {
            "id": task.task_id,
            "task_code": task.task_code,
            "title": task.title,
            "description": task.description,
            "task_type": task.task_type,
            "priority": task.priority,
            "status": task.status,
            "longitude": task.longitude,
            "latitude": task.latitude,
            "address": task.address,
            "assigned_to": {
                "id": assigned_user.gov_user_id if assigned_user else None,
                "username": assigned_user.username if assigned_user else None,
                "department": assigned_user.department if assigned_user else None,
                "position": assigned_user.position if assigned_user else None
            } if assigned_user else None,
            "assigned_by": {
                "id": assigned_by_user.gov_user_id if assigned_by_user else None,
                "username": assigned_by_user.username if assigned_by_user else None
            } if assigned_by_user else None,
            "created_by": {
                "id": created_user.gov_user_id if created_user else None,
                "username": created_user.username if created_user else None,
                "department": created_user.department if created_user else None
            } if created_user else None,
            "deadline": task.deadline.strftime("%Y-%m-%d %H:%M:%S") if task.deadline else None,
            "completion_time": task.completion_time.strftime("%Y-%m-%d %H:%M:%S") if task.completion_time else None,
            "attachments": attachment_urls,
            "remarks": task.remarks,
            "history": history_list,
            "comments": comment_list,
            "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
            "updated_at": task.updated_at.strftime("%Y-%m-%d %H:%M:%S") if task.updated_at else None
        }

        return BaseResponse(data=task_detail)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取任务详情失败: {str(e)}")


@app.put("/api/government/tasks/{task_id}", response_model=BaseResponse)
async def update_task(
        task_id: int,
        request: LawEnforcementTaskUpdate,
        current_user: GovernmentUser = Depends(get_current_gov_user),
        db: Session = Depends(get_db)
):
    """
    更新任务信息
    """
    try:
        task = db.query(LawEnforcementTask).filter(LawEnforcementTask.task_id == task_id).first()
        if not task:
            return BaseResponse(code="404", msg="任务不存在")

        # 记录旧状态
        old_status = task.status

        # 更新字段
        update_fields = ["title", "description", "priority", "status", "assigned_to", "deadline", "remarks"]
        for field in update_fields:
            if getattr(request, field) is not None:
                setattr(task, field, getattr(request, field))

        # 如果指派了执行人，记录指派人
        if request.assigned_to and request.assigned_to != task.assigned_to:
            task.assigned_by = current_user.gov_user_id

        # 如果任务状态变为完成，记录完成时间
        if request.status == "completed" and old_status != "completed":
            task.completion_time = datetime.now()

        task.updated_at = datetime.now()
        db.commit()

        # 记录历史
        history = TaskHistory(
            task_id=task.task_id,
            action="update",
            description=f"更新任务信息",
            performed_by=current_user.gov_user_id,
            old_status=old_status,
            new_status=task.status,
            metadata={"updated_fields": update_fields}
        )
        db.add(history)

        # 记录操作日志
        log = OperationLog(
            operator=current_user.username,
            action="更新执法任务",
            target=task.task_code,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",
            result="成功",
            details=f"更新任务状态: {old_status} -> {task.status}"
        )
        db.add(log)
        db.commit()

        return BaseResponse(msg="任务更新成功")
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"更新任务失败: {str(e)}")


@app.post("/api/government/tasks/{task_id}/comments", response_model=BaseResponse)
async def add_task_comment(
        task_id: int,
        request: TaskCommentCreate,
        current_user: GovernmentUser = Depends(get_current_gov_user),
        db: Session = Depends(get_db)
):
    """
    添加任务评论
    """
    try:
        task = db.query(LawEnforcementTask).filter(LawEnforcementTask.task_id == task_id).first()
        if not task:
            return BaseResponse(code="404", msg="任务不存在")

        comment = TaskComment(
            task_id=task_id,
            content=request.content,
            comment_type=request.comment_type,
            created_by=current_user.gov_user_id,
            attachments=request.attachments or []
        )

        db.add(comment)

        # 记录历史
        history = TaskHistory(
            task_id=task_id,
            action="comment",
            description=f"添加{request.comment_type}: {request.content[:50]}...",
            performed_by=current_user.gov_user_id
        )
        db.add(history)

        db.commit()

        return BaseResponse(msg="评论添加成功")
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"添加评论失败: {str(e)}")


@app.get("/api/government/users", response_model=BaseResponse)
async def get_government_users(
        department: Optional[str] = Query(None),
        role: Optional[str] = Query(None),
        current_user: GovernmentUser = Depends(get_current_gov_user),
        db: Session = Depends(get_db)
):
    """
    获取政府执法人员列表（用于指派任务）
    """
    try:
        query = db.query(GovernmentUser).filter(GovernmentUser.status == True)

        if department:
            query = query.filter(GovernmentUser.department == department)
        if role:
            query = query.filter(GovernmentUser.role == role)

        users = query.order_by(GovernmentUser.department, GovernmentUser.username).all()

        user_list = []
        for user in users:
            # 统计用户的任务数
            assigned_tasks = db.query(LawEnforcementTask).filter(
                LawEnforcementTask.assigned_to == user.gov_user_id,
                LawEnforcementTask.status.in_(["pending", "assigned", "in_progress"])
            ).count()

            user_info = {
                "id": user.gov_user_id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
                "department": user.department,
                "position": user.position,
                "role": user.role,
                "assigned_tasks": assigned_tasks,
                "last_login": user.last_login_time.strftime("%Y-%m-%d %H:%M:%S") if user.last_login_time else None
            }

            user_list.append(user_info)

        return BaseResponse(data=user_list)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取用户列表失败: {str(e)}")


@app.get("/api/government/dashboard", response_model=BaseResponse)
async def get_government_dashboard(
        current_user: GovernmentUser = Depends(get_current_gov_user),
        db: Session = Depends(get_db)
):
    """
    政府执法端仪表板数据
    """
    try:
        # 任务统计
        total_tasks = db.query(LawEnforcementTask).count()
        pending_tasks = db.query(LawEnforcementTask).filter(
            LawEnforcementTask.status == "pending"
        ).count()
        urgent_tasks = db.query(LawEnforcementTask).filter(
            LawEnforcementTask.priority == "urgent",
            LawEnforcementTask.status.in_(["pending", "assigned", "in_progress"])
        ).count()

        # 最近7天任务趋势
        seven_days_ago = datetime.now() - timedelta(days=7)
        daily_tasks = []
        for i in range(7):
            date = seven_days_ago + timedelta(days=i)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            count = db.query(LawEnforcementTask).filter(
                LawEnforcementTask.created_at >= day_start,
                LawEnforcementTask.created_at < day_end
            ).count()

            daily_tasks.append({
                "date": day_start.strftime("%m-%d"),
                "count": count
            })

        # 各部门任务分布
        dept_tasks = []
        departments = db.query(GovernmentUser.department).distinct().all()
        for dept, in departments:
            if dept:
                count = db.query(LawEnforcementTask).join(
                    GovernmentUser,
                    LawEnforcementTask.assigned_to == GovernmentUser.gov_user_id
                ).filter(
                    GovernmentUser.department == dept
                ).count()

                dept_tasks.append({
                    "department": dept,
                    "count": count
                })

        # 待办事项（当前用户的未完成任务）
        my_pending_tasks = db.query(LawEnforcementTask).filter(
            LawEnforcementTask.assigned_to == current_user.gov_user_id,
            LawEnforcementTask.status.in_(["pending", "assigned", "in_progress"])
        ).order_by(
            case(
                (LawEnforcementTask.priority == "urgent", 1),
                (LawEnforcementTask.priority == "high", 2),
                (LawEnforcementTask.priority == "medium", 3),
                else_=4
            ),
            LawEnforcementTask.deadline.asc()
        ).limit(5).all()

        pending_list = []
        for task in my_pending_tasks:
            pending_list.append({
                "id": task.task_id,
                "task_code": task.task_code,
                "title": task.title,
                "priority": task.priority,
                "deadline": task.deadline.strftime("%Y-%m-%d") if task.deadline else None,
                "status": task.status
            })

        dashboard_data = {
            "task_stats": {
                "total": total_tasks,
                "pending": pending_tasks,
                "urgent": urgent_tasks,
                "completion_rate": round((total_tasks - pending_tasks) / total_tasks * 100, 2) if total_tasks > 0 else 0
            },
            "daily_trends": daily_tasks,
            "department_distribution": dept_tasks,
            "my_pending_tasks": pending_list,
            "system_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return BaseResponse(data=dashboard_data)
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取仪表板数据失败: {str(e)}")


# ========== 商铺审核管理接口 ==========

@app.get("/api/admin/shop-audit/list", response_model=BaseResponse)
async def get_shop_audit_list(
        page: int = Query(1, ge=1),
        pageSize: int = Query(10, ge=1),
        keyword: Optional[str] = None,
        status: Optional[str] = None,  # pending, approved, rejected
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取商铺审核列表（管理员专用）
    """
    try:
        # 检查是否为管理员
        if current_user.role not in ['admin']:
            return BaseResponse(code="403", msg="权限不足")

        query = db.query(Shop)

        # 关键词搜索
        if keyword:
            keyword_lower = keyword.lower()
            query = query.filter(
                or_(
                    Shop.username.ilike(f"%{keyword}%"),
                    Shop.email.ilike(f"%{keyword}%"),
                    Shop.province.ilike(f"%{keyword}%"),
                    Shop.city.ilike(f"%{keyword}%"),
                    Shop.district.ilike(f"%{keyword}%")
                )
            )

        # 审核状态筛选
        if status:
            if status == 'pending':
                # 未审核：audit_status 为 None 或空字符串
                query = query.filter(or_(
                    Shop.audit_status == None,
                    Shop.audit_status == '',
                    Shop.audit_status == 'pending'
                ))
            else:
                query = query.filter(Shop.audit_status == status)

        # 计算总数
        total = query.count()

        # 分页查询
        shops = query.order_by(Shop.created_at.desc()) \
            .offset((page - 1) * pageSize) \
            .limit(pageSize) \
            .all()

        # 统计信息
        stats_query = db.query(
            func.count(case((or_(
                Shop.audit_status == None,
                Shop.audit_status == '',
                Shop.audit_status == 'pending'
            ), 1))).label("pending_count"),
            func.count(case((Shop.audit_status == 'approved', 1))).label("approved_count"),
            func.count(case((Shop.audit_status == 'rejected', 1))).label("rejected_count"),
            func.count().label("total_count")
        )

        stats_result = stats_query.first()
        stats = {
            "pendingCount": stats_result.pending_count or 0,
            "approvedCount": stats_result.approved_count or 0,
            "rejectedCount": stats_result.rejected_count or 0,
            "totalCount": stats_result.total_count or 0
        }

        # 获取创建人信息（这里假设创建人就是店铺本身，实际项目中可能有单独的创建人字段）
        shop_list = []
        for shop in shops:
            # 获取创建人信息（这里简化处理，实际项目中可能需要关联用户表）
            creator_name = "系统管理员"  # 默认值

            # 如果有创建人ID，可以查询用户表获取用户名
            if hasattr(shop, 'created_by') and shop.created_by:
                creator = db.query(User).filter(User.user_id == shop.created_by).first()
                if creator:
                    creator_name = creator.username

            # 处理审核状态
            audit_status = shop.audit_status
            if audit_status is None or audit_status == '':
                audit_status = 'pending'

            shop_info = {
                "id": shop.shop_id,
                "username": shop.username,
                "email": shop.email,  # 这里实际是地点
                "province": shop.province,
                "city": shop.city,
                "district": shop.district,
                "size": shop.size,
                "role": shop.role,
                "auditStatus": audit_status,
                "creatorName": creator_name,
                "createdAt": shop.created_at.strftime("%Y-%m-%d %H:%M:%S") if shop.created_at else None,
                "updatedAt": shop.updated_at.strftime("%Y-%m-%d %H:%M:%S") if shop.updated_at else None
            }

            shop_list.append(shop_info)

        return BaseResponse(data={
            "list": shop_list,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "stats": stats
        })
    except Exception as e:
        return BaseResponse(code="500", msg=f"获取店铺审核列表失败: {str(e)}")


@app.post("/api/admin/shop-audit/{shop_id}/audit", response_model=BaseResponse)
async def audit_shop(
        shop_id: int,
        request: dict,  # 包含 action 和 remark
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    审核单个店铺
    """
    try:
        # 检查是否为管理员
        if current_user.role not in ['admin']:
            return BaseResponse(code="403", msg="权限不足")

        shop = db.query(Shop).filter(Shop.shop_id == shop_id).first()
        if not shop:
            return BaseResponse(code="404", msg="店铺不存在")

        action = request.get("action")  # approve 或 reject
        remark = request.get("remark", "")

        if action not in ["approve", "reject"]:
            return BaseResponse(code="400", msg="无效的操作类型")

        # 更新审核状态
        new_status = "approved" if action == "approve" else "rejected"
        shop.audit_status = new_status
        shop.updated_at = datetime.now()

        # 记录审核日志
        log = OperationLog(
            operator=current_user.username,
            action="店铺审核",
            target=shop.username,
            operation_time=datetime.now(),
            ip_address="192.168.1.1",  # 实际项目中应从请求中获取
            result="成功",
            details=f"审核操作: {action}, 状态: {new_status}, 备注: {remark}"
        )
        db.add(log)

        db.commit()

        return BaseResponse(
            msg=f"店铺审核{'通过' if action == 'approve' else '拒绝'}成功",
            data={
                "id": shop_id,
                "auditStatus": new_status
            }
        )
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"审核操作失败: {str(e)}")


@app.post("/api/admin/shop-audit/batch-audit", response_model=BaseResponse)
async def batch_audit_shop(
        request: dict,  # 包含 shopIds 和 action
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    批量审核店铺
    """
    try:
        # 检查是否为管理员
        if current_user.role not in ['admin']:
            return BaseResponse(code="403", msg="权限不足")

        shop_ids = request.get("shopIds", [])
        action = request.get("action")  # approve 或 reject

        if not shop_ids:
            return BaseResponse(code="400", msg="请选择要操作的店铺")

        if action not in ["approve", "reject"]:
            return BaseResponse(code="400", msg="无效的操作类型")

        new_status = "approved" if action == "approve" else "rejected"
        success_count = 0
        failed_ids = []

        for shop_id in shop_ids:
            try:
                shop = db.query(Shop).filter(Shop.shop_id == shop_id).first()
                if shop:
                    shop.audit_status = new_status
                    shop.updated_at = datetime.now()
                    success_count += 1

                    # 记录审核日志
                    log = OperationLog(
                        operator=current_user.username,
                        action="批量店铺审核",
                        target=shop.username,
                        operation_time=datetime.now(),
                        ip_address="192.168.1.1",
                        result="成功",
                        details=f"批量审核操作: {action}, 状态: {new_status}"
                    )
                    db.add(log)
                else:
                    failed_ids.append(shop_id)
            except Exception as e:
                print(f"审核店铺 {shop_id} 失败: {e}")
                failed_ids.append(shop_id)

        db.commit()

        return BaseResponse(
            msg=f"批量审核完成，成功: {success_count}，失败: {len(failed_ids)}",
            data={
                "successCount": success_count,
                "failedIds": failed_ids
            }
        )
    except Exception as e:
        db.rollback()
        return BaseResponse(code="500", msg=f"批量审核失败: {str(e)}")



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
import os
import json
from app.core import get_db_dependency, get_current_user

router = APIRouter(prefix="/api/images", tags=["图片标注"])


class AnnotationCreate(BaseModel):
    category_id: int
    x_center: float
    y_center: float
    width: float
    height: float


class AnnotationResponse(BaseModel):
    id: int
    image_id: int
    category_id: int
    x_center: float
    y_center: float
    width: float
    height: float
    created_at: datetime


class ImageResponse(BaseModel):
    id: int
    dataset_id: int
    filename: str
    width: Optional[int]
    height: Optional[int]
    status: str
    annotations: List[AnnotationResponse] = []


class SaveAnnotationsRequest(BaseModel):
    annotations: List[AnnotationCreate]
    skip: bool = False


@router.get("/next/{dataset_id}")
async def get_next_image(
    dataset_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """获取下一张待标注图片"""
    with conn.cursor() as cursor:
        # 检查数据集
        cursor.execute("SELECT id FROM datasets WHERE id = %s AND is_active = TRUE", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在或未激活")

        # 优先返回当前用户已分配但未完成的图片
        cursor.execute(
            "SELECT * FROM images WHERE dataset_id = %s AND assigned_to = %s AND status = 'assigned'",
            (dataset_id, current_user['id'])
        )
        image = cursor.fetchone()

        if not image:
            # 获取一张新的待标注图片
            cursor.execute(
                "SELECT * FROM images WHERE dataset_id = %s AND status = 'pending' LIMIT 1",
                (dataset_id,)
            )
            image = cursor.fetchone()

            if image:
                # 分配给当前用户
                cursor.execute(
                    "UPDATE images SET assigned_to = %s, assigned_at = NOW(), status = 'assigned' WHERE id = %s",
                    (current_user['id'], image['id'])
                )
                image['status'] = 'assigned'
                image['assigned_to'] = current_user['id']

        if not image:
            return None

        # 获取标注
        cursor.execute("SELECT * FROM annotations WHERE image_id = %s", (image['id'],))
        annotations = cursor.fetchall()

    return {
        **image,
        "annotations": annotations
    }


@router.get("/{image_id}")
async def get_image(
    image_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """获取图片详情和标注"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM images WHERE id = %s", (image_id,))
        image = cursor.fetchone()

        if not image:
            raise HTTPException(status_code=404, detail="图片不存在")

        cursor.execute("SELECT * FROM annotations WHERE image_id = %s", (image_id,))
        annotations = cursor.fetchall()

    return {
        **image,
        "annotations": annotations
    }


@router.get("/{image_id}/file")
async def get_image_file(
    image_id: int,
    conn = Depends(get_db_dependency)
):
    """获取图片文件（内网使用，无需认证）"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT file_path FROM images WHERE id = %s", (image_id,))
        image = cursor.fetchone()

    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")

    if not os.path.exists(image['file_path']):
        raise HTTPException(status_code=404, detail="图片文件不存在")

    return FileResponse(image['file_path'])


@router.post("/{image_id}/annotations")
async def create_annotation(
    image_id: int,
    annotation_data: AnnotationCreate,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """创建标注"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT dataset_id FROM images WHERE id = %s", (image_id,))
        image = cursor.fetchone()
        if not image:
            raise HTTPException(status_code=404, detail="图片不存在")

        # 验证类别
        cursor.execute(
            "SELECT id FROM categories WHERE id = %s AND dataset_id = %s",
            (annotation_data.category_id, image['dataset_id'])
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=400, detail="无效的类别")

        cursor.execute(
            """INSERT INTO annotations (image_id, category_id, x_center, y_center, width, height, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (image_id, annotation_data.category_id, annotation_data.x_center, annotation_data.y_center,
             annotation_data.width, annotation_data.height, current_user['id'])
        )
        annotation_id = cursor.lastrowid

        # 记录历史
        cursor.execute(
            "INSERT INTO annotation_history (image_id, user_id, action, annotation_data) VALUES (%s, %s, %s, %s)",
            (image_id, current_user['id'], 'create', json.dumps({
                "category_id": annotation_data.category_id,
                "x_center": annotation_data.x_center,
                "y_center": annotation_data.y_center,
                "width": annotation_data.width,
                "height": annotation_data.height
            }))
        )

        cursor.execute("SELECT * FROM annotations WHERE id = %s", (annotation_id,))
        annotation = cursor.fetchone()

    return annotation


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """删除标注"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM annotations WHERE id = %s", (annotation_id,))
        annotation = cursor.fetchone()
        if not annotation:
            raise HTTPException(status_code=404, detail="标注不存在")

        # 记录历史
        cursor.execute(
            "INSERT INTO annotation_history (image_id, user_id, action, annotation_data) VALUES (%s, %s, %s, %s)",
            (annotation['image_id'], current_user['id'], 'delete', json.dumps({
                "annotation_id": annotation_id,
                "category_id": annotation['category_id'],
                "x_center": annotation['x_center'],
                "y_center": annotation['y_center'],
                "width": annotation['width'],
                "height": annotation['height']
            }))
        )

        cursor.execute("DELETE FROM annotations WHERE id = %s", (annotation_id,))

    return {"message": "删除成功"}


@router.post("/{image_id}/save")
async def save_annotations(
    image_id: int,
    data: SaveAnnotationsRequest,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """保存图片的所有标注并完成"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM images WHERE id = %s", (image_id,))
        image = cursor.fetchone()
        if not image:
            raise HTTPException(status_code=404, detail="图片不存在")

        # 删除旧标注
        cursor.execute("DELETE FROM annotations WHERE image_id = %s", (image_id,))

        annotation_count = 0
        if not data.skip:
            # 创建新标注
            for ann_data in data.annotations:
                cursor.execute(
                    """INSERT INTO annotations (image_id, category_id, x_center, y_center, width, height, created_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (image_id, ann_data.category_id, ann_data.x_center, ann_data.y_center,
                     ann_data.width, ann_data.height, current_user['id'])
                )
                annotation_count += 1

        # 更新图片状态
        new_status = 'skipped' if data.skip else 'labeled'
        cursor.execute(
            "UPDATE images SET status = %s, labeled_by = %s, labeled_at = NOW() WHERE id = %s",
            (new_status, current_user['id'], image_id)
        )

        # 更新数据集统计
        cursor.execute(
            "SELECT COUNT(*) as count FROM images WHERE dataset_id = %s AND status = 'labeled'",
            (image['dataset_id'],)
        )
        labeled = cursor.fetchone()['count']
        cursor.execute(
            "UPDATE datasets SET labeled_images = %s WHERE id = %s",
            (labeled, image['dataset_id'])
        )

        # 更新工作量统计
        today = date.today()
        cursor.execute(
            "SELECT id FROM work_statistics WHERE user_id = %s AND dataset_id = %s AND date = %s",
            (current_user['id'], image['dataset_id'], today)
        )
        stats = cursor.fetchone()

        if stats:
            cursor.execute(
                "UPDATE work_statistics SET images_labeled = images_labeled + 1, annotations_created = annotations_created + %s WHERE id = %s",
                (annotation_count, stats['id'])
            )
        else:
            cursor.execute(
                "INSERT INTO work_statistics (user_id, dataset_id, date, images_labeled, annotations_created) VALUES (%s, %s, %s, %s, %s)",
                (current_user['id'], image['dataset_id'], today, 1, annotation_count)
            )

    return {"message": "保存成功", "status": new_status}


@router.get("/{image_id}/history")
async def get_annotation_history(
    image_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """获取标注历史 (用于撤销)"""
    with conn.cursor() as cursor:
        cursor.execute(
            """SELECT id, action, annotation_data, created_at FROM annotation_history
               WHERE image_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 50""",
            (image_id, current_user['id'])
        )
        history = cursor.fetchall()

    return [
        {
            "id": h['id'],
            "action": h['action'],
            "data": json.loads(h['annotation_data']) if isinstance(h['annotation_data'], str) else h['annotation_data'],
            "created_at": h['created_at']
        }
        for h in history
    ]


@router.get("/dataset/{dataset_id}/progress")
async def get_dataset_progress(
    dataset_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """获取数据集标注进度"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在")

        cursor.execute("SELECT COUNT(*) as count FROM images WHERE dataset_id = %s", (dataset_id,))
        total = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM images WHERE dataset_id = %s AND status = 'labeled'", (dataset_id,))
        labeled = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM images WHERE dataset_id = %s AND status = 'skipped'", (dataset_id,))
        skipped = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM images WHERE dataset_id = %s AND status = 'pending'", (dataset_id,))
        pending = cursor.fetchone()['count']

    return {
        "total": total,
        "labeled": labeled,
        "skipped": skipped,
        "pending": pending,
        "progress": round(labeled / total * 100, 2) if total > 0 else 0
    }

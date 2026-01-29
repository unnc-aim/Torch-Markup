from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.core import get_db_dependency, get_current_admin, get_current_user

router = APIRouter(prefix="/api/categories", tags=["类别"])


class CategoryCreate(BaseModel):
    dataset_id: int
    name: str
    shortcut_key: Optional[str] = None
    color: Optional[str] = "#FF0000"
    sort_order: Optional[int] = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    shortcut_key: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


class CategoryResponse(BaseModel):
    id: int
    dataset_id: int
    name: str
    shortcut_key: Optional[str]
    color: str
    sort_order: int
    created_at: datetime


@router.get("/dataset/{dataset_id}", response_model=List[CategoryResponse])
async def list_categories(
    dataset_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """获取数据集的类别列表"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在")

        cursor.execute(
            "SELECT * FROM categories WHERE dataset_id = %s ORDER BY sort_order",
            (dataset_id,)
        )
        categories = cursor.fetchall()

    return categories


@router.post("", response_model=CategoryResponse)
async def create_category(
    category_data: CategoryCreate,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """创建类别"""
    with conn.cursor() as cursor:
        # 检查数据集是否存在
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (category_data.dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在")

        # 检查类别名是否重复
        cursor.execute(
            "SELECT id FROM categories WHERE dataset_id = %s AND name = %s",
            (category_data.dataset_id, category_data.name)
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="类别名已存在")

        # 检查快捷键是否重复
        if category_data.shortcut_key:
            cursor.execute(
                "SELECT id FROM categories WHERE dataset_id = %s AND shortcut_key = %s",
                (category_data.dataset_id, category_data.shortcut_key)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="快捷键已被使用")

        cursor.execute(
            "INSERT INTO categories (dataset_id, name, shortcut_key, color, sort_order) VALUES (%s, %s, %s, %s, %s)",
            (category_data.dataset_id, category_data.name, category_data.shortcut_key, category_data.color, category_data.sort_order)
        )
        category_id = cursor.lastrowid

        cursor.execute("SELECT * FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()

    return category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """更新类别"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()
        if not category:
            raise HTTPException(status_code=404, detail="类别不存在")

        updates = []
        params = []

        if category_data.name is not None:
            # 检查名称是否重复
            cursor.execute(
                "SELECT id FROM categories WHERE dataset_id = %s AND name = %s AND id != %s",
                (category['dataset_id'], category_data.name, category_id)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="类别名已存在")
            updates.append("name = %s")
            params.append(category_data.name)

        if category_data.shortcut_key is not None:
            if category_data.shortcut_key:
                cursor.execute(
                    "SELECT id FROM categories WHERE dataset_id = %s AND shortcut_key = %s AND id != %s",
                    (category['dataset_id'], category_data.shortcut_key, category_id)
                )
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="快捷键已被使用")
            updates.append("shortcut_key = %s")
            params.append(category_data.shortcut_key)

        if category_data.color is not None:
            updates.append("color = %s")
            params.append(category_data.color)

        if category_data.sort_order is not None:
            updates.append("sort_order = %s")
            params.append(category_data.sort_order)

        if updates:
            params.append(category_id)
            cursor.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id = %s", params)

        cursor.execute("SELECT * FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()

    return category


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """删除类别"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM categories WHERE id = %s", (category_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="类别不存在")

        cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))

    return {"message": "删除成功"}


@router.post("/batch", response_model=List[CategoryResponse])
async def batch_create_categories(
    categories: List[CategoryCreate],
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """批量创建类别"""
    if not categories:
        raise HTTPException(status_code=400, detail="类别列表不能为空")

    dataset_id = categories[0].dataset_id

    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在")

        created_ids = []
        for cat_data in categories:
            if cat_data.dataset_id != dataset_id:
                raise HTTPException(status_code=400, detail="所有类别必须属于同一数据集")

            cursor.execute(
                "INSERT INTO categories (dataset_id, name, shortcut_key, color, sort_order) VALUES (%s, %s, %s, %s, %s)",
                (cat_data.dataset_id, cat_data.name, cat_data.shortcut_key, cat_data.color, cat_data.sort_order)
            )
            created_ids.append(cursor.lastrowid)

        cursor.execute(
            f"SELECT * FROM categories WHERE id IN ({','.join(['%s'] * len(created_ids))})",
            created_ids
        )
        created = cursor.fetchall()

    return created


class ImportFromDatasetRequest(BaseModel):
    source_dataset_id: int


@router.post("/import-from-dataset/{dataset_id}")
async def import_from_dataset(
    dataset_id: int,
    data: ImportFromDatasetRequest,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """从其他数据集导入类别"""
    with conn.cursor() as cursor:
        # 检查目标数据集是否存在
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="目标数据集不存在")

        # 检查源数据集是否存在
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (data.source_dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="源数据集不存在")

        # 获取源数据集的类别
        cursor.execute(
            "SELECT name, shortcut_key, color, sort_order FROM categories WHERE dataset_id = %s ORDER BY sort_order",
            (data.source_dataset_id,)
        )
        source_categories = cursor.fetchall()

        if not source_categories:
            raise HTTPException(status_code=400, detail="源数据集没有类别")

        # 获取目标数据集已有的类别名
        cursor.execute(
            "SELECT name FROM categories WHERE dataset_id = %s",
            (dataset_id,)
        )
        existing_names = {row['name'] for row in cursor.fetchall()}

        # 获取目标数据集已用的快捷键
        cursor.execute(
            "SELECT shortcut_key FROM categories WHERE dataset_id = %s AND shortcut_key IS NOT NULL",
            (dataset_id,)
        )
        existing_keys = {row['shortcut_key'] for row in cursor.fetchall()}

        imported = 0
        skipped = 0
        for cat in source_categories:
            if cat['name'] in existing_names:
                skipped += 1
                continue

            # 检查快捷键是否已被使用
            shortcut_key = cat['shortcut_key']
            if shortcut_key and shortcut_key in existing_keys:
                shortcut_key = None  # 清除冲突的快捷键

            cursor.execute(
                """INSERT INTO categories (dataset_id, name, shortcut_key, color, sort_order)
                   VALUES (%s, %s, %s, %s, %s)""",
                (dataset_id, cat['name'], shortcut_key, cat['color'], cat['sort_order'])
            )
            imported += 1

            if shortcut_key:
                existing_keys.add(shortcut_key)
            existing_names.add(cat['name'])

    return {
        "message": f"成功导入 {imported} 个类别，跳过 {skipped} 个已存在的类别",
        "imported": imported,
        "skipped": skipped
    }

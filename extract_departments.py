"""
从JSON文件中提取科室数据 - 修复版
"""

import json
import os
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Location

# 楼层Z值映射
FLOOR_Z = {1: 0, 2: 1, 3: 2, 4: 3}
FLOOR_NAME = {1: "一楼", 2: "二楼", 3: "三楼", 4: "四楼"}

# 科室名称映射（根据你图片中的科室）
DEPARTMENT_NAMES_1F = [
    "放射科", "门诊药房", "门诊挂号收费", "门诊预约", "神经外科",
    "治疗换药室", "内分泌科门诊", "疼痛门诊", "血管外科", "外科门诊手术室",
    "骨科门诊", "普通外科门诊", "烧伤整形外科", "泌尿外科门诊", "碎石室", "感染科"
]

DEPARTMENT_NAMES_2F = [
    "普通内科", "心理咨询", "神经内科", "心内科", "营养科",
    "胸外科", "血液科", "呼吸科", "风湿免疫", "耳鼻喉门诊",
    "挂号收费处", "噪音评估", "语言矫治", "平衡功能评定处", "国诊门诊室", "彩超室"
]

DEPARTMENT_NAMES_3F = [
    "挂号收费处", "口腔科第一诊室", "口腔科第二诊室", "口腔科第三诊室",
    "激光室", "造影室", "口腔科门诊手术室", "眼科门诊手术室",
    "眼镜车间", "配镜室", "检查室", "针灸科", "按摩科", "门诊中药房"
]

DEPARTMENT_NAMES_4F = [
    "中医诊室", "中医普通门诊", "面部治疗室", "女性门诊",
    "激光室", "皮肤治疗室", "皮肤科门诊", "挂号收费处",
    "皮肤外科", "妇产科彩超室", "计划生育手术室", "宫腔镜室",
    "产科诊室", "新生儿复诊室", "生殖医学门诊", "妇科门诊"
]

# 各楼层科室名称列表
FLOOR_DEPARTMENTS = {
    1: DEPARTMENT_NAMES_1F,
    2: DEPARTMENT_NAMES_2F,
    3: DEPARTMENT_NAMES_3F,
    4: DEPARTMENT_NAMES_4F
}

def extract_departments_from_json(json_file, floor):
    """从JSON文件提取科室数据"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        departments = []
        name_list = FLOOR_DEPARTMENTS.get(floor, [])
        
        # 从obstacles中提取所有物体
        for i, obs in enumerate(data.get("obstacles", [])):
            material = obs.get("material", "")
            center = obs.get("center", [0, 0])
            
            # 如果是科室（乱码"绉戝"实际上是"科室"）
            if "绉戝" in material or material in ["科室", "诊室"]:
                # 使用对应的科室名称
                if i < len(name_list):
                    dept_name = name_list[i]
                else:
                    dept_name = f"科室_{floor}F_{i+1}"
                
                departments.append({
                    "name": dept_name,
                    "type": "department",
                    "x": center[0],
                    "y": center[1],
                    "z": FLOOR_Z[floor],
                    "floor": floor,
                    "is_accessible": True
                })
                print(f"  发现: {dept_name} ({center[0]:.2f}, {center[1]:.2f})")
        
        return departments
    except Exception as e:
        print(f"  解析文件 {json_file} 失败: {e}")
        return []

def import_departments():
    """导入所有科室数据"""
    db = SessionLocal()
    
    json_files = [
        ("hospital_floor_data/m1F_paths.json", 1),
        ("hospital_floor_data/m2F_paths.json", 2),
        ("hospital_floor_data/m3F_paths.json", 3),
        ("hospital_floor_data/m4F_paths.json", 4)
    ]
    
    total_departments = 0
    
    for json_file, floor in json_files:
        if os.path.exists(json_file):
            print(f"\n正在提取 {FLOOR_NAME[floor]} 科室...")
            departments = extract_departments_from_json(json_file, floor)
            
            for dept in departments:
                # 直接添加，不检查重复
                location = Location(**dept)
                db.add(location)
                total_departments += 1
            
            db.commit()
            print(f"  ✅ 添加了 {len(departments)} 个科室")
        else:
            print(f"文件不存在: {json_file}")
    
    print(f"\n🎉 成功添加 {total_departments} 个科室")
    db.close()

if __name__ == "__main__":
    import_departments()
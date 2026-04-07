"""
验证路径规划是否正确
"""
import requests
import json

BASE_URL = "http://113.54.243.19:8000/api/v1"

test_cases = [
    {"start": 25, "end": 26, "desc": "放射科 → 门诊药房（同层）"},
    {"start": 1, "end": 19, "desc": "1楼厕所 → 4楼厕所（跨层）"},
    {"start": 5, "end": 14, "desc": "1楼电梯 → 3楼电梯（垂直）"},
    {"start": 25, "end": 162, "desc": "最远距离测试"},
]

for test in test_cases:
    print(f"\n📌 测试: {test['desc']}")
    response = requests.post(
        f"{BASE_URL}/plan",
        json={
            "start_id": test["start"],
            "end_id": test["end"],
            "user_type": "normal"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"  ✅ 成功! 距离: {data['total_distance']:.2f}米, 时间: {data['estimated_time']}秒")
        print(f"  路径点数量: {len(data['path'])}")
        print(f"  楼层变化: {data['floor_changes']}次")
        
        # 显示前3个点和后3个点
        print("  路径预览:")
        for i, point in enumerate(data['path'][:3]):
            print(f"    {i+1}. {point['description']}")
        if len(data['path']) > 6:
            print("    ...")
        for point in data['path'][-3:]:
            print(f"    {point['description']}")
    else:
        print(f"  ❌ 失败: {response.status_code}")
import sqlite3
import math

conn = sqlite3.connect('hospital_guide.db')
cur = conn.cursor()

# 获取所有道路点（path_node 类型的点）
cur.execute('SELECT id, x, y, floor FROM locations WHERE type = "path_node"')
path_nodes = cur.fetchall()

# 获取所有科室（department 类型的点）
cur.execute('SELECT id, x, y, floor FROM locations WHERE type = "department"')
departments = cur.fetchall()

print(f'道路点数量: {len(path_nodes)}')
print(f'科室数量: {len(departments)}')

# 清空旧路径（只保留道路点之间的连接）
cur.execute('DELETE FROM paths WHERE start_id IN (SELECT id FROM locations WHERE type = "department") OR end_id IN (SELECT id FROM locations WHERE type = "department")')
print('已清空科室相关旧路径')

# 为每个科室找到最近的道路点并连接
connected = 0
for dept in departments:
    dept_id, dept_x, dept_y, dept_floor = dept
    min_dist = float('inf')
    best_node = None
    for node in path_nodes:
        node_id, node_x, node_y, node_floor = node
        if node_floor != dept_floor:
            continue
        dist = math.hypot(dept_x - node_x, dept_y - node_y)
        if dist < min_dist:
            min_dist = dist
            best_node = node_id
    if best_node and min_dist < 10:
        cur.execute('INSERT INTO paths (start_id, end_id, distance, type) VALUES (?, ?, ?, ?)', (dept_id, best_node, min_dist, 'corridor'))
        cur.execute('INSERT INTO paths (start_id, end_id, distance, type) VALUES (?, ?, ?, ?)', (best_node, dept_id, min_dist, 'corridor'))
        connected += 1
        if connected <= 10:
            print(f'  连接: {dept_id} -> 道路点 {best_node} (距离 {min_dist:.2f}m)')

conn.commit()
conn.close()

print(f'✅ 完成！共连接 {connected} 个科室到最近道路点')
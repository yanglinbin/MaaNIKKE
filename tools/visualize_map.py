#!/usr/bin/env python3
"""
地图可视化工具

根据 map.py 中的 MapNavigator 逻辑生成可视化地图图形。

依赖:
    pip install networkx matplotlib

使用:
    python tools/visualize_map.py
    
输出:
    - map_graph.png: 地图拓扑图
    - map_analysis.txt: 文本分析报告
"""

import json
import os
import sys
from typing import Dict, List, Tuple
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MapVisualizer:
    """地图可视化器：根据 MapNavigator 逻辑生成图形"""

    # 节点颜色配置
    COLORS = {
        "home": "#FF6B6B",          # 主页 - 红色
        "return_home": "#4ECDC4",   # 有 return_home 的节点 - 青色
        "normal": "#F38181",        # 普通节点 - 粉红色
        "generic": "#FFE66D",       # 通用返回节点 - 黄色
        "included_level_1": "#A8E6CF",  # 一级 include 子节点 - 浅绿色
        "included_level_2": "#FFD3B6",  # 二级 include 子节点 - 浅橙色
        "included_level_3": "#FFAAA5",  # 三级 include 子节点 - 浅珊瑚色
        "included_level_4+": "#D4A5A5", # 四级及以上 - 浅棕色
    }

    # 边的颜色配置
    EDGE_COLOR_NORMAL = "#3498DB"     # 手动定义的边 - 蓝色
    EDGE_COLOR_INCLUDE = "#9B59B6"    # 自动生成的边 - 紫色（return_home + include）

    def __init__(self, map_file_path: str):
        """初始化可视化器
        
        Args:
            map_file_path: map.json 文件路径
        """
        self.map_file_path = map_file_path
        self.map_data = self._load_map_data()
        self.navigator = self._create_navigator()
        self.graph = nx.DiGraph()

    def _load_map_data(self) -> Dict:
        """加载地图数据"""
        print(f"加载地图数据: {self.map_file_path}")
        with open(self.map_file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _create_navigator(self):
        """创建 MapNavigator 实例（模拟）"""
        # 由于无法直接导入 MapNavigator（依赖 MAA），我们手动复制核心逻辑
        return MapNavigatorSimulator(self.map_data)

    def build_graph(self):
        """构建 NetworkX 图"""
        print("构建图结构...")
        
        # 添加所有节点
        all_nodes = self.navigator.get_all_map_nodes()
        for node_name in all_nodes:
            node_type = self._get_node_type(node_name)
            self.graph.add_node(node_name, node_type=node_type)
        
        # 添加通用返回节点
        if "->上一级" in self.map_data or "->返回" in self.map_data:
            self.graph.add_node("->上一级", node_type="generic")
        if "->map主页" in self.map_data:
            self.graph.add_node("->map主页", node_type="generic")
        
        # 添加边（使用 navigator 的图结构）
        nav_graph = self.navigator.graph
        for from_node, edges in nav_graph.items():
            for to_node, weight in edges:
                # 获取边的类型和权重
                edge_type = self._get_edge_type(from_node, to_node)
                time_seconds = weight / 1000.0
                
                # 判断是否为自动添加的边（return_home）
                is_auto = self._is_auto_edge(from_node, to_node)
                
                self.graph.add_edge(
                    from_node, 
                    to_node, 
                    edge_type=edge_type,
                    weight=time_seconds,
                    is_auto=is_auto  # 标记是否为自动边
                )
        
        print(f"图构建完成: {self.graph.number_of_nodes()} 个节点, {self.graph.number_of_edges()} 条边")

    def _get_node_type(self, node_name: str) -> str:
        """获取节点类型（支持多层嵌套识别）"""
        if node_name == "map主页":
            return "home"
        elif node_name.startswith("->"):
            return "generic"
        
        # 检查嵌套层级
        ancestors = self.navigator.get_all_ancestors(node_name)
        if ancestors:
            # 是被 include 的节点，根据层级深度返回不同类型
            level = len(ancestors)
            if level == 1:
                return "included_level_1"
            elif level == 2:
                return "included_level_2"
            elif level == 3:
                return "included_level_3"
            else:
                return "included_level_4+"
        
        # 不是被 include 的节点，检查是否有 return_home
        if self.map_data.get(node_name, {}).get("return_home", False):
            return "return_home"
        else:
            return "normal"

    def _get_edge_type(self, from_node: str, to_node: str) -> str:
        """获取边的类型（cutscene 类型）"""
        action_data = self.navigator.get_action_data(from_node, to_node)
        if action_data is None:
            return "auto"  # 自动添加的边
        
        cutscene = action_data.get("cutscene", "normal")
        return cutscene

    def _is_auto_edge(self, from_node: str, to_node: str) -> bool:
        """判断边是否为自动添加的（return_home）
        
        自动边包括：
        1. return_home 节点自动添加的返回边（到来源节点和主页）
        2. include_node 子节点继承的外部边
        3. 同层级导航的自动边
        
        手动边：
        1. 直接在 path_list 中定义的边
        """
        # 检查是否在原始的 path_list 中定义
        from_data = self.map_data.get(from_node, {})
        path_info = from_data.get("path", {})
        path_list = path_info.get("path_list", [])
        
        for path_item in path_list:
            target_nodes = path_item.get("next_map", path_item.get("back_map", []))
            if to_node in target_nodes:
                # 在 path_list 中找到，是手动边
                return False
        
        # 不在 path_list 中，检查是否为自动边
        # 1. 如果 from_node 有 return_home=true，并且 to_node 是来源节点或主页，则是自动边
        if from_data.get("return_home", False):
            # 检查是否是返回主页
            if to_node == "map主页":
                return True
            
            # 检查是否是返回来源节点
            parent = self.navigator.included_by.get(from_node)
            if to_node == parent:
                return True
            
            # 检查是否是通过 path_list 导航到 from_node 的节点
            for other_node, other_data in self.map_data.items():
                if not other_node.startswith("map"):
                    continue
                if other_node == from_node:
                    continue
                
                other_path_info = other_data.get("path", {})
                other_path_list = other_path_info.get("path_list", [])
                
                for path_item in other_path_list:
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    if from_node in target_nodes and to_node == other_node:
                        # from_node 是从 to_node 导航过来的，这是自动反向边
                        return True
        
        # 2. 如果 from_node 是 include_node 子节点，检查是否继承自父节点
        parent = self.navigator.included_by.get(from_node)
        if parent:
            parent_data = self.map_data.get(parent, {})
            parent_path_info = parent_data.get("path", {})
            parent_path_list = parent_path_info.get("path_list", [])
            
            # 检查父节点的 path_list
            for path_item in parent_path_list:
                target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                
                # 检查是否是同层级导航（兄弟节点之间）
                siblings = parent_data.get("include_node", [])
                if to_node in siblings and to_node != from_node:
                    # 同层级导航，是自动边
                    return True
                
                # 检查是否是继承的外部边
                if to_node in target_nodes and to_node not in siblings:
                    # 继承自父节点的外部边
                    return True
            
            # 检查是否继承了祖先的 return_home 边
            ancestors = self.navigator.get_all_ancestors(from_node)
            for ancestor in ancestors:
                ancestor_data = self.map_data.get(ancestor, {})
                if ancestor_data.get("return_home", False):
                    # 祖先有 return_home，会自动添加两条边：
                    # 1. 到 map主页（已在上面处理）
                    # 2. 到祖先的导航父节点
                    
                    # 检查 to_node 是否为祖先的导航父节点
                    # 导航父节点 = 其 path_list 中有到祖先的边的节点
                    for other_node, other_data in self.map_data.items():
                        if not other_node.startswith("map"):
                            continue
                        
                        other_path_list = other_data.get("path", {}).get("path_list", [])
                        for path_item in other_path_list:
                            target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                            if ancestor in target_nodes and other_node == to_node:
                                # to_node 的 path_list 中有到祖先的边
                                # from_node 继承了祖先的 return_home 边
                                return True  # 继承的 return_home 边，是自动边
        
        # 默认返回 False（手动边）
        return False

    def visualize(self, output_file: str = "map_graph.png", layout: str = "hierarchical", 
                  show_auto_edges: bool = False, hide_covered_edges: bool = True):
        """生成可视化图形
        
        Args:
            output_file: 输出文件路径
            layout: 布局算法 (hierarchical, spring, kamada_kawai, circular, shell)
            show_auto_edges: 是否显示自动添加的边（return_home）
            hide_covered_edges: 是否隐藏被覆盖的边（自动边如果能通过手动边达到，则隐藏）
        """
        print(f"生成可视化图形 (布局: {layout}, 显示自动边: {show_auto_edges})...")
        
        # 保存当前的 show_auto_edges 设置，供布局算法使用
        self._show_auto_edges = show_auto_edges
        
        # 创建图形（增加尺寸以减少拥挤）
        fig, ax = plt.subplots(1, 1, figsize=(30, 20))
        
        # 选择布局算法
        if layout == "hierarchical":
            # 使用自定义层级布局
            pos = self._hierarchical_layout()
        elif layout == "spring":
            pos = nx.spring_layout(self.graph, k=2, iterations=50, seed=42)
        elif layout == "kamada_kawai":
            pos = nx.kamada_kawai_layout(self.graph)
        elif layout == "circular":
            pos = nx.circular_layout(self.graph)
        elif layout == "shell":
            # 按层级排列
            shells = self._create_shells()
            pos = nx.shell_layout(self.graph, shells)
        else:
            pos = self._hierarchical_layout()
        
        # 绘制节点（按类型分组）
        for node_type, color in self.COLORS.items():
            nodes = [n for n, d in self.graph.nodes(data=True) 
                     if d.get("node_type") == node_type]
            if nodes:
                nx.draw_networkx_nodes(
                    self.graph, pos, 
                    nodelist=nodes,
                    node_color=color,
                    node_size=2000,
                    alpha=0.9,
                    ax=ax
                )
        
        # 绘制边（按类型分组，可选择是否显示自动边）
        # 使用无箭头的边，然后在中间添加箭头标记
        import numpy as np
        
        # 首先收集所有可见的边（用于正确判断双向边）
        visible_edges = set()
        for u, v, d in self.graph.edges(data=True):
            is_auto = d.get("is_auto", False)
            
            # 判断是否应该显示
            should_show = False
            if not is_auto:
                # 手动边始终显示
                should_show = True
            elif show_auto_edges:
                # 自动边：如果 show_auto_edges=True
                if hide_covered_edges:
                    # 检查是否被手动边覆盖
                    if not self._is_covered_by_manual_path(u, v):
                        should_show = True
                else:
                    should_show = True
            
            if should_show:
                visible_edges.add((u, v))
        
        print(f"  可见边数: {len(visible_edges)}")
        
        # 统计边的类型
        bidirectional_pairs = set()
        unidirectional_count = 0
        
        for u, v in visible_edges:
            if (v, u) in visible_edges:
                # 双向边，只统计一次
                pair = tuple(sorted([u, v]))
                bidirectional_pairs.add(pair)
            else:
                unidirectional_count += 1
        
        print(f"  边类型统计: 单向边={unidirectional_count}, 双向边对={len(bidirectional_pairs)}")
        
        # 绘制所有可见边（统一颜色）
        for u, v, d in self.graph.edges(data=True):
            if not (show_auto_edges or not d.get("is_auto", False)):
                continue  # 跳过自动边（如果不显示）
            
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            
            # 计算方向向量
            dx = x2 - x1
            dy = y2 - y1
            length = np.sqrt(dx**2 + dy**2)
            
            if length == 0:
                continue
            
            # 单位方向向量
            ux = dx / length
            uy = dy / length
            
            # 垂直单位向量
            perp_x = -uy
            perp_y = ux
            
            # 检测是否为双向边（只检测可见边中的反向边）
            is_bidirectional = (v, u) in visible_edges
            
            # 固定间隔偏移：双向边使用固定间隔，避免距离远时曲率过大
            fixed_offset = 0.3  # 固定间隔（单位）
            offset = fixed_offset if is_bidirectional else 0.0
            
            # 判断是否为 include 内部的边
            is_include_edge = self._is_include_edge(u, v)
            
            # 选择颜色
            edge_color = self.EDGE_COLOR_INCLUDE if is_include_edge else self.EDGE_COLOR_NORMAL
            
            # 计算弧线的控制点（简单二次贝塞尔曲线）
            ctrl_x = (x1 + x2) / 2 + perp_x * offset
            ctrl_y = (y1 + y2) / 2 + perp_y * offset
            
            # 绘制曲线（使用多段线近似）
            t_values = np.linspace(0, 1, 50)
            curve_x = (1 - t_values)**2 * x1 + 2 * (1 - t_values) * t_values * ctrl_x + t_values**2 * x2
            curve_y = (1 - t_values)**2 * y1 + 2 * (1 - t_values) * t_values * ctrl_y + t_values**2 * y2
            
            ax.plot(curve_x, curve_y, color=edge_color, linewidth=2, alpha=0.7, zorder=1)
            
            # 在中点（t=0.5）绘制箭头
            t = 0.5
            mid_x = (1 - t)**2 * x1 + 2 * (1 - t) * t * ctrl_x + t**2 * x2
            mid_y = (1 - t)**2 * y1 + 2 * (1 - t) * t * ctrl_y + t**2 * y2
            
            # 计算中点的切线方向（贝塞尔曲线的导数）
            tangent_x = 2 * (1 - t) * (ctrl_x - x1) + 2 * t * (x2 - ctrl_x)
            tangent_y = 2 * (1 - t) * (ctrl_y - y1) + 2 * t * (y2 - ctrl_y)
            tangent_length = np.sqrt(tangent_x**2 + tangent_y**2)
            
            if tangent_length > 0:
                # 归一化切线向量
                tangent_x /= tangent_length
                tangent_y /= tangent_length
                
                # 绘制箭头（在中点，沿切线方向）
                arrow_length = 0.05
                ax.annotate(
                    '',
                    xy=(mid_x + tangent_x * arrow_length * 0.5, 
                        mid_y + tangent_y * arrow_length * 0.5),
                    xytext=(mid_x - tangent_x * arrow_length * 0.5, 
                            mid_y - tangent_y * arrow_length * 0.5),
                    arrowprops=dict(
                        arrowstyle='-|>',
                        color=edge_color,
                        alpha=0.7,
                        lw=2.5,
                        shrinkA=0,
                        shrinkB=0,
                        mutation_scale=15,
                    ),
                    zorder=2
                )
                
                # 在箭头旁边显示时间（所有边都显示）
                time_text = f"{d['weight']:.1f}s"
                # 计算标签位置（稍微偏移，避免与箭头重叠）
                label_offset = 0.15
                label_x = mid_x + perp_x * label_offset
                label_y = mid_y + perp_y * label_offset
                
                ax.text(
                    label_x, label_y,
                    time_text,
                    fontsize=6,
                    fontfamily='Microsoft YaHei',
                    ha='center',
                    va='center',
                    bbox=dict(
                        boxstyle='round,pad=0.2',
                        facecolor='white',
                        edgecolor=edge_color,
                        alpha=0.8,
                        linewidth=0.5
                    ),
                    zorder=3
                )
        
        # 绘制节点标签（去掉 map 前缀，更简洁）
        labels = {}
        for node in self.graph.nodes():
            if node.startswith("map"):
                labels[node] = node.replace("map", "")
            elif node.startswith("->"):
                labels[node] = node  # 通用节点保留完整名称
            else:
                labels[node] = node
        
        nx.draw_networkx_labels(
            self.graph, pos,
            labels=labels,
            font_size=9,
            font_family='Microsoft YaHei',  # 支持中文
            font_weight='bold',
            ax=ax
        )
        
        # 添加图例
        self._add_legend(ax)
        
        # 设置标题
        ax.set_title("MaaNIKKE 地图导航拓扑图", fontsize=20, fontweight='bold', 
                    fontfamily='Microsoft YaHei', pad=20)
        ax.axis('off')
        
        # 保存图形
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ 图形已保存: {output_file}")
        
        # 显示图形（可选）
        # plt.show()
        plt.close()

    def _hierarchical_layout(self) -> Dict:
        """创建层级布局
        
        使用 BFS 从主页开始，按父节点顺序排列子节点（减少交叉）
        """
        home_node = "map主页"
        
        # 第一步：使用 BFS 计算每个节点的层级和父节点
        layers = {}
        node_parents = {}  # 记录每个节点的父节点（用于排序）
        visited = {home_node}
        queue = [(home_node, 0, None)]  # (节点, 层级, 父节点)
        
        while queue:
            node, level, parent = queue.pop(0)
            layers[node] = level
            if parent is not None:
                node_parents[node] = parent
            
            # 遍历邻居（按字母顺序，保持稳定性）
            neighbors = sorted(self.graph.neighbors(node))
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, level + 1, node))
        
        # 处理未访问的节点（孤立节点和通用返回节点）
        max_level = max(layers.values()) if layers else 0
        for node in self.graph.nodes():
            if node not in layers:
                if node.startswith("->"):
                    layers[node] = -1
                else:
                    layers[node] = max_level + 1
        
        # 第二步：按层级组织节点
        level_nodes = {}
        for node, level in layers.items():
            if level not in level_nodes:
                level_nodes[level] = []
            level_nodes[level].append(node)
        
        # 第三步：为每层节点排序（从第三层开始按父节点顺序）
        print(f"  使用父节点顺序布局...")
        sorted_levels = sorted(level_nodes.keys())
        
        pos = {}
        y_spacing = 2.0
        
        for level in sorted_levels:
            nodes = level_nodes[level]
            
            if level <= 1:
                # 第0层（通用返回节点）和第1层（主页）：简单排序
                sorted_nodes = sorted(nodes)
            elif level == 2:
                # 第2层：从主页直达的节点，使用广度优先顺序
                sorted_nodes = nodes  # 保持 BFS 顺序
            else:
                # 第3层及以后：按父节点的位置顺序排列
                sorted_nodes = self._sort_by_parent_position(nodes, node_parents, pos)
            
            level_nodes[level] = sorted_nodes
            self._layout_level(level, sorted_nodes, pos, y_spacing)
        
        return pos
    
    def _layout_level(self, level: int, nodes: List[str], pos: Dict, y_spacing: float):
        """为某一层级的节点计算位置
        
        Args:
            level: 层级编号
            nodes: 该层级的节点列表（已排序）
            pos: 位置字典（会被修改）
            y_spacing: 层级间距
        """
        num_nodes = len(nodes)
        
        # 计算 x 坐标（均匀分布，增加间距）
        if num_nodes == 1:
            x_positions = [0]
        else:
            # 根据节点数量调整宽度，增加节点间距减少交叉
            width = max(12, num_nodes * 2.0)  # 增加节点间距
            x_positions = [i * width / (num_nodes - 1) - width / 2 
                          for i in range(num_nodes)]
        
        # 设置位置
        y = -level * y_spacing
        for i, node in enumerate(nodes):
            pos[node] = (x_positions[i], y)

    def _sort_by_parent_position(self, nodes: List[str], node_parents: Dict, pos: Dict) -> List[str]:
        """按父节点的位置顺序排列节点
        
        Args:
            nodes: 待排序的节点列表
            node_parents: 节点到父节点的映射
            pos: 已有的节点位置
        
        Returns:
            排序后的节点列表
        """
        # 为每个节点计算排序键
        node_keys = []
        
        for node in nodes:
            parent = node_parents.get(node)
            
            if parent and parent in pos:
                # 有父节点且父节点已布局：使用父节点的 x 位置
                parent_x = pos[parent][0]
                
                # 同一个父节点的多个子节点：添加次要排序键（节点名称）
                sort_key = (parent_x, node)
            else:
                # 没有父节点或父节点未布局：使用一个大值，放在最后
                sort_key = (float('inf'), node)
            
            node_keys.append((node, sort_key))
        
        # 按排序键排序
        node_keys.sort(key=lambda x: x[1])
        
        return [node for node, _ in node_keys]
    
    def _sort_nodes_by_parent(self, nodes: List[str], existing_pos: Dict) -> List[str]:
        """根据父节点位置对节点排序，使得子节点靠近父节点，并减少边的交叉
        
        使用重心法（barycenter method）：计算每个节点连接的已布局节点的加权平均位置
        
        Args:
            nodes: 待排序的节点列表
            existing_pos: 已有的节点位置
        
        Returns:
            排序后的节点列表
        """
        if len(nodes) <= 1:
            return nodes
        
        # 计算每个节点的"重心位置"（加权平均）
        node_scores = []
        
        # 获取 show_auto_edges 设置，默认 False
        show_auto_edges = getattr(self, '_show_auto_edges', False)
        
        for node in nodes:
            connected_positions = []
            weights = []
            
            # 1. include_node 父节点（高权重）
            parent = self.navigator.included_by.get(node)
            if parent and parent in existing_pos:
                connected_positions.append(existing_pos[parent][0])
                weights.append(3.0)  # 父节点权重最高
            
            # 2. 前驱节点（指向此节点的边，只考虑可见边）
            for predecessor in self.graph.predecessors(node):
                if predecessor in existing_pos:
                    # 检查边是否可见
                    edge_data = self.graph.get_edge_data(predecessor, node)
                    if edge_data:
                        is_auto = edge_data.get('is_auto', False)
                        if show_auto_edges or not is_auto:
                            connected_positions.append(existing_pos[predecessor][0])
                            weights.append(2.0)  # 前驱节点中等权重
            
            # 3. 后继节点（此节点指向的边，只考虑可见边）
            for successor in self.graph.successors(node):
                if successor in existing_pos:
                    # 检查边是否可见
                    edge_data = self.graph.get_edge_data(node, successor)
                    if edge_data:
                        is_auto = edge_data.get('is_auto', False)
                        if show_auto_edges or not is_auto:
                            connected_positions.append(existing_pos[successor][0])
                            weights.append(1.0)  # 后继节点较低权重
            
            # 计算加权平均作为期望位置（重心法）
            if connected_positions:
                weighted_sum = sum(pos * weight for pos, weight in zip(connected_positions, weights))
                total_weight = sum(weights)
                score = weighted_sum / total_weight
            else:
                # 没有连接的节点，使用节点名称的哈希值（保持稳定排序）
                score = hash(node) % 1000
            
            node_scores.append((node, score))
        
        # 按期望位置排序
        node_scores.sort(key=lambda x: x[1])
        
        return [node for node, _ in node_scores]

    def _create_shells(self) -> List[List[str]]:
        """创建 shell 布局的层级"""
        shells = []
        
        # 第一层：主页
        shells.append(["map主页"])
        
        # 第二层：从主页直达的节点
        layer2 = []
        for neighbor in self.graph.neighbors("map主页"):
            if not neighbor.startswith("->"):
                layer2.append(neighbor)
        if layer2:
            shells.append(layer2)
        
        # 第三层：其他节点
        visited = set(shells[0])
        if len(shells) > 1:
            visited.update(shells[1])
        layer3 = [n for n in self.graph.nodes() 
                  if n not in visited and not n.startswith("->")]
        if layer3:
            shells.append(layer3)
        
        # 最后一层：通用返回节点
        generics = [n for n in self.graph.nodes() if n.startswith("->")]
        if generics:
            shells.append(generics)
        
        return shells

    def _is_covered_by_manual_path(self, from_node: str, to_node: str) -> bool:
        """检查一条边是否被手动边路径覆盖
        
        判断从 from_node 到 to_node 是否存在只通过手动边的路径。
        如果存在，则直接的自动边被"覆盖"，可以隐藏。
        
        Args:
            from_node: 起始节点
            to_node: 目标节点
        
        Returns:
            True 如果存在手动边路径（自动边被覆盖）
            False 如果不存在手动边路径（自动边不被覆盖，应该显示）
        """
        # 使用 BFS 查找只通过手动边的路径
        from collections import deque
        
        visited = set()
        queue = deque([from_node])
        visited.add(from_node)
        
        while queue:
            current = queue.popleft()
            
            # 检查所有出边
            for neighbor in self.graph.successors(current):
                if neighbor == to_node:
                    # 找到了目标节点，检查这条边是否为手动边
                    edge_data = self.graph[current][neighbor]
                    if not edge_data.get("is_auto", False):
                        # 通过手动边到达目标，路径存在
                        return True
                
                # 如果还没访问过，且通过手动边可达
                if neighbor not in visited:
                    edge_data = self.graph[current][neighbor]
                    if not edge_data.get("is_auto", False):
                        # 这是手动边，继续搜索
                        visited.add(neighbor)
                        queue.append(neighbor)
        
        # 没有找到只通过手动边的路径
        return False
    
    def _is_include_edge(self, from_node: str, to_node: str) -> bool:
        """判断边是否为自动生成的边（返回 True 则显示为紫色）
        
        注意：函数名虽然叫 _is_include_edge，但实际判断的是所有自动边，
        不仅仅是 include 内部的边，也包括 return_home 自动边。
        
        判断原则：
        1. 优先检查边是否在 path_list 中手动定义
           → 如果是手动定义的，返回 False（🔵 蓝色，手动导航）
        2. 检查是否为 return_home 自动边
           → 如果是，返回 True（🟣 紫色，return_home 自动导航）
        3. 检查是否为 include 树内部的自动边或继承边
           → 如果是，返回 True（🟣 紫色，include 自动/继承导航）
        4. 否则返回 False（🔵 蓝色，普通外部导航）
        
        自动边的类型（🟣 紫色）：
        - return_home 自动边：map拦截战 → map方舟（拦截战有 return_home: true）
        - include 子→父：map普通礼包 → map付费商店（return_home 自动添加）
        - include 兄弟导航：map普通商店 ↔ map竞技场商店（自动继承）
        - include 继承边：map每日 → map主页（继承自付费商店）
        
        手动边的类型（🔵 蓝色）：
        - 直接在 path_list 中定义的边：map主页 → map付费商店
        
        Args:
            from_node: 起始节点
            to_node: 目标节点
        
        Returns:
            True 如果边是自动生成的（🟣 紫色）
            False 如果边是手动定义的（🔵 蓝色）
        """
        # ============================================================
        # 第一步：检查是否为手动定义的边（优先级最高）
        # ============================================================
        from_data = self.map_data.get(from_node, {})
        path_info = from_data.get("path", {})
        path_list = path_info.get("path_list", [])
        
        for path_item in path_list:
            target_nodes = path_item.get("next_map", path_item.get("back_map", []))
            if to_node in target_nodes:
                # 在 path_list 中找到，是手动定义的边
                # 即使目标是 include_node 子节点，也显示为蓝色
                return False  # 🔵 蓝色（手动定义）
        
        # ============================================================
        # 第二步：检查是否为 return_home 自动边
        # ============================================================
        # 如果 from_node 有 return_home: true，并且存在某个节点的 path_list 中
        # 有到 from_node 的边，那么 from_node → 那个节点 的边是 return_home 自动边
        if from_data.get("return_home", False):
            # 检查是否到 map主页
            if to_node == "map主页":
                return True  # 🟣 紫色（return_home 自动边）
            
            # 检查是否有节点的 path_list 中有到 from_node 的边
            # 如果有，那个节点就是 from_node 的导航父节点
            for node_name, node_data in self.map_data.items():
                node_path_list = node_data.get("path", {}).get("path_list", [])
                for path_item in node_path_list:
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    if from_node in target_nodes and node_name == to_node:
                        # node_name 的 path_list 中有到 from_node 的边
                        # 并且 to_node == node_name
                        # 说明这是 return_home 自动添加的返回边
                        return True  # 🟣 紫色（return_home 自动边）
        
        # ============================================================
        # 第三步：检查是否为 include 树内部的自动边
        # ============================================================
        
        # 1. 检查是否为父→子关系
        from_children = self.map_data.get(from_node, {}).get("include_node", [])
        if to_node in from_children:
            # from_node 包含 to_node，且不是手动定义
            # 理论上不应该出现这种情况，因为父→子必须手动定义
            # 但如果出现了，标记为紫色
            return True  # 🟣 紫色（自动边，异常情况）
        
        # 2. 检查是否为子→父关系
        # 注意：根据新的设计，include 子节点的 return_home 不会生成指向 include 父节点的边
        # 因为 include 子节点是父节点页面内的内容，会直接继承父节点的外部边
        # 所以这段代码理论上不会被执行，但保留用于兼容性
        to_children = self.map_data.get(to_node, {}).get("include_node", [])
        if from_node in to_children:
            # to_node 包含 from_node，说明是子→父
            # 但这种边现在不应该存在于图中（已在构建时排除）
            return True  # 🟣 紫色（兼容性代码，不应执行到）
        
        # 3. 检查是否为兄弟节点关系
        from_parent = self.navigator.included_by.get(from_node)
        to_parent = self.navigator.included_by.get(to_node)
        
        if from_parent and to_parent and from_parent == to_parent:
            # 两个节点有共同父节点，是兄弟关系
            # 且不是手动定义的（已经在第一步排除）
            # 这是自动继承的兄弟导航
            return True  # 🟣 紫色（自动继承的兄弟导航）
        
        # 4. 检查是否为继承边（include 子节点继承父节点的外部边）
        # 例如：map普通礼包 → map主页（从 map付费商店 继承）
        from_ancestors = self.navigator.get_all_ancestors(from_node)
        if from_ancestors:
            # from_node 是某个节点的 include 子节点
            # 检查其任何祖先是否有到 to_node 的边
            for ancestor in from_ancestors:
                ancestor_data = self.map_data.get(ancestor, {})
                ancestor_path_list = ancestor_data.get("path", {}).get("path_list", [])
                
                # 检查祖先的手动边
                for path_item in ancestor_path_list:
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    if to_node in target_nodes:
                        # 祖先有到 to_node 的手动边，from_node 继承了这条边
                        return True  # 🟣 紫色（继承边）
                
                # 检查祖先的 return_home 自动边
                if ancestor_data.get("return_home", False):
                    # 祖先有 return_home，会自动添加两条边：
                    # 1. 到 map主页
                    # 2. 到祖先的导航父节点
                    if to_node == "map主页":
                        # from_node 继承了到 map主页 的边
                        return True  # 🟣 紫色（继承的自动边）
                    
                    # 检查 to_node 是否为祖先的导航父节点
                    # 导航父节点 = 其 path_list 中有到祖先的边的节点
                    for node_name, node_data in self.map_data.items():
                        node_path_list = node_data.get("path", {}).get("path_list", [])
                        for path_item in node_path_list:
                            target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                            if ancestor in target_nodes and node_name == to_node:
                                # to_node 的 path_list 中有到祖先的边
                                # 说明 to_node 是祖先的导航父节点
                                # from_node 继承了祖先的 return_home 边
                                return True  # 🟣 紫色（继承的 return_home 边）
        
        # 5. 检查是否为跨层级的 include 树内部导航
        # 例如：孙节点 → 祖父节点，或同一树中的堂兄弟
        to_ancestors = self.navigator.get_all_ancestors(to_node)
        
        # 如果 to_node 是 from_node 的祖先（子→祖先）
        if to_node in from_ancestors:
            return True  # 🟣 紫色（return_home 自动添加）
        
        # 如果 from_node 是 to_node 的祖先（父→后代）
        if from_node in to_ancestors:
            return True  # 🟣 紫色（继承的外部边）
        
        # 如果两个节点有共同祖先（但不是直接兄弟）
        # 例如：堂兄弟节点，或通过多层继承的边
        common_ancestors = set(from_ancestors) & set(to_ancestors)
        if common_ancestors:
            # 有共同祖先，且不是手动定义的（已经在第一步排除）
            # 这是自动继承的边（例如子节点继承父节点的外部边）
            return True  # 🟣 紫色（自动继承的边）
        
        # ============================================================
        # 第三步：不满足以上条件，返回 False（普通外部导航）
        # ============================================================
        return False  # 🔵 蓝色（普通外部导航）
    
    def _draw_hierarchy_boxes(self, ax, pos):
        """绘制 include_node 层级关系的框
        
        Args:
            ax: matplotlib 轴对象
            pos: 节点位置字典
        """
        import matplotlib.patches as patches
        
        # 遍历所有有 include_node 的父节点
        for parent_node, node_data in self.map_data.items():
            if not parent_node.startswith("map"):
                continue
            
            children = node_data.get("include_node", [])
            if not children or parent_node not in pos:
                continue
            
            # 收集父节点和所有子节点的位置
            nodes_in_group = [parent_node]
            for child in children:
                if child in pos:
                    nodes_in_group.append(child)
            
            if len(nodes_in_group) <= 1:
                continue
            
            # 计算包围框
            x_coords = [pos[node][0] for node in nodes_in_group]
            y_coords = [pos[node][1] for node in nodes_in_group]
            
            min_x = min(x_coords)
            max_x = max(x_coords)
            min_y = min(y_coords)
            max_y = max(y_coords)
            
            # 添加边距（更小的边距，避免框住其他元素）
            node_radius = 0.25  # 基于 node_size=2000 的估算
            padding = 0.15  # 减小额外边距
            margin = node_radius + padding
            
            # 如果只有一行节点（y坐标相同），使用更小的垂直边距
            if max_y == min_y:
                vertical_margin = margin * 0.7
            else:
                vertical_margin = margin
            
            box_x = min_x - margin
            box_y = min_y - vertical_margin
            box_width = (max_x - min_x) + 2 * margin
            box_height = (max_y - min_y) + 2 * vertical_margin
            
            # 绘制矩形框
            rect = patches.FancyBboxPatch(
                (box_x, box_y),
                box_width,
                box_height,
                boxstyle="round,pad=0.05",
                linewidth=2,
                edgecolor='#95E1D3',  # 使用浅青色
                facecolor='none',
                linestyle='--',
                alpha=0.6,
                zorder=0
            )
            ax.add_patch(rect)
            
            # 添加父节点名称标签（在框的外部上方，避免遮挡）
            parent_label = parent_node.replace("map", "")
            label_y = box_y + box_height + 0.15  # 放在框外上方
            ax.text(
                box_x + box_width / 2,  # 水平居中
                label_y,
                f"【{parent_label}】",
                fontsize=7,
                fontfamily='Microsoft YaHei',
                color='#2C3E50',
                alpha=0.8,
                ha='center',  # 水平居中对齐
                va='bottom',  # 垂直底部对齐
                bbox=dict(
                    boxstyle='round,pad=0.2',
                    facecolor='#E8F8F5',
                    edgecolor='#95E1D3',
                    alpha=0.9,
                    linewidth=1
                ),
                zorder=3  # 确保标签在最上层
            )
    
    def _add_legend(self, ax):
        """添加图例"""
        # 节点类型图例
        node_patches = [
            mpatches.Patch(color=self.COLORS["home"], label="主页节点"),
            mpatches.Patch(color=self.COLORS["return_home"], label="return_home 节点"),
            mpatches.Patch(color=self.COLORS["normal"], label="普通节点"),
            mpatches.Patch(color=self.COLORS["generic"], label="通用返回节点"),
        ]
        
        # Include 嵌套层级图例
        include_patches = [
            mpatches.Patch(color=self.COLORS["included_level_1"], label="一级 include 子节点"),
            mpatches.Patch(color=self.COLORS["included_level_2"], label="二级 include 子节点"),
            mpatches.Patch(color=self.COLORS["included_level_3"], label="三级 include 子节点"),
            mpatches.Patch(color=self.COLORS["included_level_4+"], label="四级+ include 子节点"),
        ]
        
        # 边类型图例
        edge_patches = [
            mpatches.Patch(color=self.EDGE_COLOR_NORMAL, label="手动定义的边"),
            mpatches.Patch(color=self.EDGE_COLOR_INCLUDE, label="自动生成的边 (return_home + include)"),
        ]
        
        # 合并图例（分组显示）
        all_patches = (
            node_patches + 
            [mpatches.Patch(color='white', label='')] + 
            include_patches + 
            [mpatches.Patch(color='white', label='')] + 
            edge_patches
        )
        
        ax.legend(
            handles=all_patches,
            loc='upper left',
            fontsize=9,
            frameon=True,
            fancybox=True,
            shadow=True,
            prop={'family': 'Microsoft YaHei'}
        )

    def generate_analysis(self, output_file: str = "map_analysis.txt"):
        """生成文本分析报告"""
        print("生成分析报告...")
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("MaaNIKKE 地图导航分析报告\n")
            f.write("=" * 80 + "\n\n")
            
            # 基本统计
            f.write("【基本统计】\n")
            f.write(f"  总节点数: {self.graph.number_of_nodes()}\n")
            f.write(f"  总边数: {self.graph.number_of_edges()}\n")
            f.write(f"  平均度数: {sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes():.2f}\n\n")
            
            # 层级结构分析
            f.write("【层级结构】\n")
            layers = self._calculate_layers()
            for level in sorted(layers.keys()):
                nodes = layers[level]
                if level == -1:
                    f.write(f"  第 -1 层（通用返回节点）: {len(nodes)} 个\n")
                elif level == 0:
                    f.write(f"  第 0 层（主页）: {len(nodes)} 个\n")
                else:
                    f.write(f"  第 {level} 层: {len(nodes)} 个\n")
                for node in sorted(nodes):
                    f.write(f"    - {node}\n")
            f.write("\n")
            
            # 节点类型统计
            f.write("【节点类型统计】\n")
            node_types = {}
            for node, data in self.graph.nodes(data=True):
                node_type = data.get("node_type", "unknown")
                node_types[node_type] = node_types.get(node_type, 0) + 1
            for node_type, count in sorted(node_types.items()):
                f.write(f"  {node_type}: {count}\n")
            f.write("\n")
            
            # 边类型统计
            f.write("【边类型统计】\n")
            edge_types = {}
            for u, v, data in self.graph.edges(data=True):
                edge_type = data.get("edge_type", "unknown")
                edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
            for edge_type, count in sorted(edge_types.items()):
                f.write(f"  {edge_type}: {count}\n")
            f.write("\n")
            
            # include_node 层级关系
            f.write("【include_node 层级关系】\n")
            for parent, children in self.navigator.hierarchy.items():
                if children["children"]:
                    f.write(f"  {parent}:\n")
                    for child in children["children"]:
                        f.write(f"    └── {child}\n")
            f.write("\n")
            
            # include_node 嵌套层级统计
            f.write("【include_node 嵌套层级统计】\n")
            level_stats = {}
            all_nodes = [n for n in self.graph.nodes() if n.startswith("map")]
            
            for node in all_nodes:
                ancestors = self.navigator.get_all_ancestors(node)
                level = len(ancestors)
                
                if level > 0:
                    if level not in level_stats:
                        level_stats[level] = []
                    level_stats[level].append(node)
            
            if level_stats:
                for level in sorted(level_stats.keys()):
                    nodes = level_stats[level]
                    f.write(f"  {level} 级嵌套 ({len(nodes)} 个节点):\n")
                    for node in sorted(nodes):
                        ancestors = self.navigator.get_all_ancestors(node)
                        path = " -> ".join(reversed(ancestors)) + f" -> {node}"
                        f.write(f"    - {path}\n")
            else:
                f.write("  (无嵌套节点)\n")
            f.write("\n")
            
            # return_home 节点
            f.write("【return_home 节点】\n")
            return_home_nodes = [
                node for node, data in self.map_data.items()
                if data.get("return_home", False)
            ]
            for node in sorted(return_home_nodes):
                f.write(f"  ✓ {node}\n")
            f.write("\n")
            
            # 节点连接性分析
            f.write("【节点连接性分析】\n")
            f.write(f"  最大出度节点:\n")
            out_degrees = sorted(self.graph.out_degree(), key=lambda x: x[1], reverse=True)[:5]
            for node, degree in out_degrees:
                f.write(f"    {node}: {degree} 条出边\n")
            
            f.write(f"  最大入度节点:\n")
            in_degrees = sorted(self.graph.in_degree(), key=lambda x: x[1], reverse=True)[:5]
            for node, degree in in_degrees:
                f.write(f"    {node}: {degree} 条入边\n")
            f.write("\n")
            
            # 路径分析（从主页到各节点）
            f.write("【从主页到各节点的最短路径】\n")
            home_node = "map主页"
            all_nodes = [n for n in self.graph.nodes() if n != home_node and n.startswith("map")]
            
            for target in sorted(all_nodes):
                try:
                    path = nx.shortest_path(self.graph, home_node, target, weight='weight')
                    total_time = nx.shortest_path_length(self.graph, home_node, target, weight='weight')
                    f.write(f"  {home_node} -> {target}:\n")
                    f.write(f"    路径: {' -> '.join(path)}\n")
                    f.write(f"    预计耗时: {total_time:.1f}s ({len(path)-1} 步)\n")
                except nx.NetworkXNoPath:
                    f.write(f"  {home_node} -> {target}: 无路径\n")
            
            f.write("\n")
            f.write("=" * 80 + "\n")
        
        print(f"✅ 分析报告已保存: {output_file}")

    def _calculate_layers(self) -> Dict[int, List[str]]:
        """计算每个节点的层级
        
        Returns:
            {层级: [节点列表]} 的字典
        """
        home_node = "map主页"
        
        # 使用 BFS 计算每个节点的层级
        layers_dict = {}
        visited = {home_node}
        queue = [(home_node, 0)]
        
        while queue:
            node, level = queue.pop(0)
            layers_dict[node] = level
            
            # 遍历邻居
            for neighbor in self.graph.neighbors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, level + 1))
        
        # 处理未访问的节点（孤立节点和通用返回节点）
        max_level = max(layers_dict.values()) if layers_dict else 0
        for node in self.graph.nodes():
            if node not in layers_dict:
                if node.startswith("->"):
                    # 通用返回节点放在最顶层
                    layers_dict[node] = -1
                else:
                    # 孤立节点放在最底层
                    layers_dict[node] = max_level + 1
        
        # 转换为 {层级: [节点列表]} 格式
        layers = {}
        for node, level in layers_dict.items():
            if level not in layers:
                layers[level] = []
            layers[level].append(node)
        
        return layers

    def find_isolated_nodes(self) -> List[str]:
        """查找孤立节点（无法从主页到达）"""
        home_node = "map主页"
        reachable = set(nx.descendants(self.graph, home_node))
        reachable.add(home_node)
        
        all_nodes = set(n for n in self.graph.nodes() if n.startswith("map"))
        isolated = all_nodes - reachable
        
        return list(isolated)


class MapNavigatorSimulator:
    """MapNavigator 模拟器（不依赖 MAA 框架）"""
    
    CUTSCENE_TIME = {
        "cutscene": 4000,
        "special": 3000,
        "normal": 2000,
        "none": 1000,
    }
    
    DEFAULT_CUTSCENE = "normal"
    DEFAULT_TIME_MULTIPLIER = 1.0

    def __init__(self, map_data: Dict):
        self.map_data = map_data
        self.info_nodes = self._collect_info_nodes()
        self.hierarchy = self._build_hierarchy()
        self.included_by = self._build_include_relationship()
        self.path_actions = self._build_path_actions()
        self.graph = self._build_graph()

    def _collect_info_nodes(self) -> List[str]:
        all_map_nodes = []
        for node_name, node_data in self.map_data.items():
            if node_name.startswith(("__", "test")):
                continue
            if node_name.startswith("map") and "recognition" in node_data:
                all_map_nodes.append(node_name)
        
        included_nodes = set()
        for node_name, node_data in self.map_data.items():
            include_list = node_data.get("include_node", [])
            included_nodes.update(include_list)
        
        info_nodes = [node for node in all_map_nodes if node not in included_nodes]
        return info_nodes

    def get_all_map_nodes(self) -> List[str]:
        """获取所有 map 节点（包括被包含的）"""
        all_nodes = []
        for node_name, node_data in self.map_data.items():
            if node_name.startswith(("__", "test")):
                continue
            if node_name.startswith("map") and "recognition" in node_data:
                all_nodes.append(node_name)
        return all_nodes

    def _build_hierarchy(self) -> Dict[str, Dict]:
        hierarchy = {}
        all_map_nodes = self.get_all_map_nodes()

        for node_name in all_map_nodes:
            hierarchy[node_name] = {"children": [], "parent": None}

        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue
            
            include_list = node_data.get("include_node", [])
            for child_node in include_list:
                if child_node in hierarchy:
                    if child_node not in hierarchy[node_name]["children"]:
                        hierarchy[node_name]["children"].append(child_node)
                    if hierarchy[child_node]["parent"] is None:
                        hierarchy[child_node]["parent"] = node_name

        return hierarchy

    def _build_include_relationship(self) -> Dict[str, str]:
        included_by = {}
        all_map_nodes = self.get_all_map_nodes()

        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue

            include_nodes = node_data.get("include_node", [])
            if not include_nodes:
                continue

            for included_node in include_nodes:
                if included_node in all_map_nodes:
                    included_by[included_node] = node_name

        return included_by

    def _build_path_actions(self) -> Dict[str, Dict]:
        path_actions = {}
        all_map_nodes = self.get_all_map_nodes()
        home_node = "map主页"
        
        # 第一步：从 path_list 中提取
        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue
            
            path_info = node_data.get("path", {})
            path_list = path_info.get("path_list", [])
            
            for path_item in path_list:
                target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                
                path_config = {"action": path_item.get("action", {})}
                
                if "recognition" in path_item:
                    path_config["recognition"] = path_item["recognition"]
                
                if "cutscene" in path_item:
                    path_config["cutscene"] = path_item["cutscene"]
                if "time_multiplier" in path_item:
                    path_config["time_multiplier"] = path_item["time_multiplier"]
                
                for target_node in target_nodes:
                    key = f"{node_name}->{target_node}"
                    path_actions[key] = path_config
        
        # 第1.5步：同层级导航
        for parent_node, node_data in self.map_data.items():
            if not parent_node.startswith("map"):
                continue
            
            children = node_data.get("include_node", [])
            if not children:
                continue
            
            path_info = node_data.get("path", {})
            path_list = path_info.get("path_list", [])
            
            for child_node in children:
                if child_node not in all_map_nodes:
                    continue
                
                for path_item in path_list:
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    
                    path_config = {"action": path_item.get("action", {})}
                    if "recognition" in path_item:
                        path_config["recognition"] = path_item["recognition"]
                    if "cutscene" in path_item:
                        path_config["cutscene"] = path_item["cutscene"]
                    if "time_multiplier" in path_item:
                        path_config["time_multiplier"] = path_item["time_multiplier"]
                    
                    for target_node in target_nodes:
                        if target_node in children and target_node != child_node:
                            sibling_key = f"{child_node}->{target_node}"
                            if sibling_key not in path_actions:
                                path_actions[sibling_key] = path_config
        
        # 第二步：通用返回节点
        generic_return_config = None
        generic_home_config = None
        
        for key_name in ["->上一级", "->返回"]:
            if key_name in self.map_data:
                node_data = self.map_data[key_name]
                generic_return_config = {"action": node_data.get("action", {})}
                if "recognition" in node_data:
                    generic_return_config["recognition"] = node_data["recognition"]
                if "cutscene" in node_data:
                    generic_return_config["cutscene"] = node_data["cutscene"]
                if "time_multiplier" in node_data:
                    generic_return_config["time_multiplier"] = node_data["time_multiplier"]
                break
        
        if "->map主页" in self.map_data:
            node_data = self.map_data["->map主页"]
            generic_home_config = {"action": node_data.get("action", {})}
            if "recognition" in node_data:
                generic_home_config["recognition"] = node_data["recognition"]
            if "cutscene" in node_data:
                generic_home_config["cutscene"] = node_data["cutscene"]
            if "time_multiplier" in node_data:
                generic_home_config["time_multiplier"] = node_data["time_multiplier"]
        
        # 第三步：return_home
        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue
            
            if not node_data.get("return_home", False):
                continue
            
            source_nodes = []
            
            include_parent = self.get_parent_node(node_name)
            if include_parent:
                source_nodes.append(include_parent)
            
            for other_node, other_data in self.map_data.items():
                if not other_node.startswith("map"):
                    continue
                if other_node == node_name:
                    continue
                
                path_info = other_data.get("path", {})
                path_list = path_info.get("path_list", [])
                
                for path_item in path_list:
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    if node_name in target_nodes:
                        if other_node not in source_nodes:
                            source_nodes.append(other_node)
                        break
            
            for source_node in source_nodes:
                if source_node not in all_map_nodes:
                    continue
                
                source_key = f"{node_name}->{source_node}"
                if source_key not in path_actions:
                    if generic_return_config:
                        path_actions[source_key] = generic_return_config
                    else:
                        path_actions[source_key] = {"action": {"type": "DoNothing", "param": {}}}
            
            if home_node in all_map_nodes and node_name != home_node:
                home_key = f"{node_name}->{home_node}"
                if home_key not in path_actions:
                    if generic_home_config:
                        path_actions[home_key] = generic_home_config
                    else:
                        path_actions[home_key] = {"action": {"type": "DoNothing", "param": {}}}
        
        return path_actions

    def get_parent_node(self, child_node: str):
        return self.hierarchy.get(child_node, {}).get("parent")
    
    def get_all_ancestors(self, node: str):
        """获取节点的所有祖先节点（从直接父节点到根节点）"""
        ancestors = []
        current = node
        visited = set()
        
        while current not in visited:
            visited.add(current)
            parent = self.get_parent_node(current)
            if parent is None:
                break
            ancestors.append(parent)
            current = parent
        
        return ancestors

    def get_action_data(self, from_node: str, to_node: str):
        key = f"{from_node}->{to_node}"
        
        if key in self.path_actions:
            return self.path_actions[key]
        
        # 依次尝试所有祖先的配置（支持多层嵌套）
        ancestors = self.get_all_ancestors(from_node)
        for ancestor in ancestors:
            ancestor_key = f"{ancestor}->{to_node}"
            if ancestor_key in self.path_actions:
                return self.path_actions[ancestor_key]
        
        return None

    def _build_graph(self) -> Dict[str, List[Tuple[str, float]]]:
        graph = {}
        all_map_nodes = self.get_all_map_nodes()
        home_node = "map主页"

        for node_name in all_map_nodes:
            graph[node_name] = []

        # 第一步：基础边
        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue

            path_info = node_data.get("path", {})
            path_list = path_info.get("path_list", [])

            for path_item in path_list:
                target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                if not target_nodes:
                    continue

                cutscene_type = path_item.get("cutscene", self.DEFAULT_CUTSCENE)
                time_multiplier = path_item.get("time_multiplier", self.DEFAULT_TIME_MULTIPLIER)
                
                base_time = self.CUTSCENE_TIME.get(cutscene_type, 1500)
                weight = base_time * time_multiplier

                for target_node in target_nodes:
                    if target_node in all_map_nodes:
                        existing_edge = next(
                            (edge for edge in graph[node_name] if edge[0] == target_node), 
                            None
                        )
                        if existing_edge is None:
                            graph[node_name].append((target_node, weight))

        # 第二步：return_home
        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue

            if not node_data.get("return_home", False):
                continue

            default_weight = self.CUTSCENE_TIME["normal"] * self.DEFAULT_TIME_MULTIPLIER
            
            source_nodes = []
            
            # 注意：include 子节点不需要返回到 include 父节点的边
            # 因为 include 子节点是父节点页面内的内容，会直接继承父节点的外部边
            # 所以不将 include_parent 添加到 source_nodes
            
            # 查找所有通过 path_list 导航到当前节点的节点（导航父节点）
            for other_node, other_data in self.map_data.items():
                if not other_node.startswith("map"):
                    continue
                if other_node == node_name:
                    continue
                
                path_info = other_data.get("path", {})
                path_list = path_info.get("path_list", [])
                
                for path_item in path_list:
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    if node_name in target_nodes:
                        # 找到了导航父节点
                        # 但要排除 include 父节点（因为 include 子节点不需要返回边）
                        include_parent = self.get_parent_node(node_name)
                        if other_node != include_parent:
                            if other_node not in source_nodes:
                                source_nodes.append(other_node)
                        break
            
            # 添加返回边
            for source_node in source_nodes:
                if source_node not in all_map_nodes:
                    continue
                
                has_edge = any(edge[0] == source_node for edge in graph[node_name])
                if not has_edge:
                    graph[node_name].append((source_node, default_weight))
            
            # 添加返回主页的边
            has_home_path = any(edge[0] == home_node for edge in graph[node_name])
            if not has_home_path and home_node in all_map_nodes and node_name != home_node:
                graph[node_name].append((home_node, default_weight))

        # 第三步：同层级导航
        for parent_node, node_data in self.map_data.items():
            if not parent_node.startswith("map"):
                continue
            
            children = node_data.get("include_node", [])
            if not children:
                continue
            
            path_info = node_data.get("path", {})
            path_list = path_info.get("path_list", [])
            
            for child_node in children:
                if child_node not in all_map_nodes:
                    continue
                
                for path_item in path_list:
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    cutscene_type = path_item.get("cutscene", self.DEFAULT_CUTSCENE)
                    time_multiplier = path_item.get("time_multiplier", self.DEFAULT_TIME_MULTIPLIER)
                    
                    base_time = self.CUTSCENE_TIME.get(cutscene_type, 1500)
                    weight = base_time * time_multiplier
                    
                    for target_node in target_nodes:
                        if target_node in children and target_node != child_node:
                            has_edge = any(edge[0] == target_node for edge in graph[child_node])
                            if not has_edge:
                                graph[child_node].append((target_node, weight))
        
        # 第3.2步：子节点继承所有祖先的外部边（支持多层嵌套）
        for node_name in all_map_nodes:
            # 获取该节点的所有祖先（从近到远）
            ancestors = self.get_all_ancestors(node_name)
            if not ancestors:
                continue  # 没有祖先，跳过
            
            # 收集同一 include 树中的所有节点（用于判断内部导航）
            root_ancestor = ancestors[-1]  # 最远的祖先（根节点）
            
            # 递归收集根节点及其所有后代
            def collect_tree_nodes(parent):
                """递归收集父节点及其所有后代"""
                nodes = set([parent])
                children = self.map_data.get(parent, {}).get("include_node", [])
                for child in children:
                    if child in all_map_nodes:
                        nodes.add(child)
                        nodes.update(collect_tree_nodes(child))
                return nodes
            
            tree_nodes = collect_tree_nodes(root_ancestor)
            
            # 从每个祖先继承外部出边
            for ancestor in ancestors:
                ancestor_edges = graph.get(ancestor, [])
                
                for target_node, weight in ancestor_edges:
                    # 排除内部导航：只有目标节点不在同一 include 树中时才继承
                    if target_node in tree_nodes:
                        continue  # 跳过到同树节点的边（内部导航）
                    
                    # 检查是否已经有到该目标的边
                    has_edge = any(edge[0] == target_node for edge in graph[node_name])
                    if not has_edge:
                        graph[node_name].append((target_node, weight))

        return graph


def main():
    """主函数"""
    # 查找地图文件
    possible_paths = [
        "./assets/resource/base/pipeline/map.json",
        "./resource/base/pipeline/map.json",
    ]
    
    map_file = None
    for path in possible_paths:
        if os.path.exists(path):
            map_file = path
            break
    
    if map_file is None:
        print("❌ 错误: 未找到 map.json 文件")
        print("尝试的路径:")
        for path in possible_paths:
            print(f"  - {path}")
        return
    
    print("=" * 80)
    print("MaaNIKKE 地图可视化工具")
    print("=" * 80)
    print()
    
    # 创建可视化器
    visualizer = MapVisualizer(map_file)
    
    # 构建图
    visualizer.build_graph()
    
    # 检查孤立节点
    isolated = visualizer.find_isolated_nodes()
    if isolated:
        print(f"⚠️  发现孤立节点（无法从主页到达）: {isolated}")
    else:
        print("✅ 所有节点均可从主页到达")
    
    print()
    
    # 生成可视化图形（使用层级布局，不显示自动边）
    visualizer.visualize("map_graph.png", layout="hierarchical", show_auto_edges=False, hide_covered_edges=True)
    
    # 生成分析报告
    visualizer.generate_analysis("map_analysis.txt")
    
    print()
    print("=" * 80)
    print("✅ 完成！生成的文件:")
    print("  - map_graph.png: 地图拓扑图")
    print("  - map_analysis.txt: 分析报告")
    print("=" * 80)


if __name__ == "__main__":
    main()


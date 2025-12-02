import json
import time
import os
import heapq
from typing import Dict, List, Optional, Tuple
from collections import deque

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..utils import (
    check_interrupt_and_raise,
    interruptible_sleep,
    is_recognition_success,
    get_fresh_screenshot,
    TaskInterruptedException,
    parse_custom_param,
)


class MapNavigator:
    """地图导航器：负责管理地图结构和路径查找
    
    边的分类逻辑（方案B：语义化判断）：
    ==================================================
    在地图导航系统中，边分为两类：
    
    1. 手动定义的边（外部导航）：
       - 在节点的 path_list 中明确定义的 next_map/back_map
       - 例如：map付费商店 → map普通礼包（父→子，手动定义）
       - 例如：map普通礼包 → map每日（兄弟，手动定义）
       - 这些边表示真正的页面跳转或用户操作
    
    2. 自动生成的边（include 内部导航）：
       - return_home 自动添加的返回边（子→父、子→主页）
       - include_node 子节点自动继承的父节点外部边
       - 同层级兄弟节点之间的自动导航
       - 例如：map普通礼包 → map付费商店（return_home 自动添加）
       - 这些边由系统自动生成，用于简化配置
    
    注意：
    - 即使目标节点在 include_node 列表中，如果在 path_list 中手动定义，
      也算作"外部导航"（蓝色），而不是"内部导航"（紫色）
    - 这样可以正确区分同一 UI 界面中打开的不同窗口
    """

    # 默认图权重（固定值，用于寻路算法）
    DEFAULT_EDGE_WEIGHT = 1.0  # 每步的默认权重

    def __init__(self, map_data: Dict):
        """初始化地图导航器"""
        self.map_data = map_data
        self.info_nodes = self._collect_info_nodes()
        self.hierarchy = self._build_hierarchy()  # 构建层级关系
        self.included_by = self._build_include_relationship()  # 构建包含关系
        self.path_actions = self._build_path_actions()  # 构建路径动作映射
        self.graph = self._build_graph()

    def _collect_info_nodes(self) -> List[str]:
        """收集所有 map 节点（排除被 include_node 包含的节点）
        
        被包含的节点不参与第一级地图定位检测
        """
        # 第一步：收集所有 map 节点
        all_map_nodes = []
        for node_name, node_data in self.map_data.items():
            if node_name.startswith(("__", "test")):
                continue
            if node_name.startswith("map") and "recognition" in node_data:
                all_map_nodes.append(node_name)
        
        # 第二步：找出所有被包含的节点
        included_nodes = set()
        for node_name, node_data in self.map_data.items():
            include_list = node_data.get("include_node", [])
            included_nodes.update(include_list)
        
        # 第三步：排除被包含的节点
        info_nodes = [node for node in all_map_nodes if node not in included_nodes]
        
        return info_nodes

    def get_info_nodes(self) -> List[str]:
        """获取所有信息节点"""
        return self.info_nodes

    def _get_all_map_nodes(self) -> List[str]:
        """获取所有 map 节点（包括被包含的）"""
        all_nodes = []
        for node_name, node_data in self.map_data.items():
            if node_name.startswith(("__", "test")):
                continue
            if node_name.startswith("map") and "recognition" in node_data:
                all_nodes.append(node_name)
        return all_nodes

    def _build_hierarchy(self) -> Dict[str, Dict]:
        """从 include_node 构建层级关系
        
        返回 {节点名: {"children": [...], "parent": ...}} 的字典。
        """
        hierarchy = {}
        
        # 获取所有 map 节点（包括被包含的）
        all_map_nodes = self._get_all_map_nodes()

        # 初始化所有节点
        for node_name in all_map_nodes:
            hierarchy[node_name] = {"children": [], "parent": None}

        # 从 include_node 字段构建层级关系
        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue
                
            include_list = node_data.get("include_node", [])
            for child_node in include_list:
                if child_node in hierarchy:
                    # 设置父子关系
                    if child_node not in hierarchy[node_name]["children"]:
                        hierarchy[node_name]["children"].append(child_node)
                    if hierarchy[child_node]["parent"] is None:
                        hierarchy[child_node]["parent"] = node_name

        return hierarchy

    def _build_include_relationship(self) -> Dict[str, str]:
        """构建包含关系映射
        
        从 include_node 字段构建子节点到父节点的映射。
        被包含的节点不参与第一级地图定位检测。
        """
        included_by = {}
        all_map_nodes = self._get_all_map_nodes()

        # 遍历所有节点
        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue

            # 检查是否有 include_node 字段
            include_nodes = node_data.get("include_node", [])
            if not include_nodes:
                continue

            # 为每个被包含的节点记录包含关系
            for included_node in include_nodes:
                if included_node in all_map_nodes:
                    included_by[included_node] = node_name
                    print(
                        f"[MapNavigator] 包含关系: {included_node} 被包含于 {node_name}"
                    )

        return included_by

    def _build_path_actions(self) -> Dict[str, Dict]:
        """构建路径动作映射
        
        从 path.path_list 提取动作配置，支持通用返回节点和条件导航。
        返回 {"from->to": {action, recognition?}} 的字典。
        """
        path_actions = {}
        all_map_nodes = self._get_all_map_nodes()
        home_node = "map主页"
        
        # 第一步：从 path_list 中提取动作和识别配置
        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue
            
            # 获取路径列表
            path_info = node_data.get("path", {})
            path_list = path_info.get("path_list", [])
            
            for path_item in path_list:
                # 获取目标节点
                target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                
                # 构建路径配置（包含 action、可选的 recognition 和 action_delay）
                path_config = {"action": path_item.get("action", {})}
                
                # 如果有 recognition 字段，也保存（用于条件导航）
                if "recognition" in path_item:
                    path_config["recognition"] = path_item["recognition"]
                
                # 如果有 action_delay 字段，也保存（用于慢速转移）
                if "action_delay" in path_item:
                    path_config["action_delay"] = path_item["action_delay"]
                
                # 为每个目标节点创建映射
                for target_node in target_nodes:
                    key = f"{node_name}->{target_node}"
                    path_actions[key] = path_config
        
        # 第1.5步：为 include_node 的兄弟节点添加同层级导航配置
        for parent_node, node_data in self.map_data.items():
            if not parent_node.startswith("map"):
                continue
            
            # 获取该节点包含的子节点
            children = node_data.get("include_node", [])
            if not children:
                continue
            
            # 获取父节点的 path_list
            path_info = node_data.get("path", {})
            path_list = path_info.get("path_list", [])
            
            # 为每个子节点添加到兄弟节点的路径配置
            for child_node in children:
                if child_node not in all_map_nodes:
                    continue
                
                # 遍历父节点的 path_list
                for path_item in path_list:
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    
                    # 构建路径配置
                    path_config = {"action": path_item.get("action", {})}
                    if "recognition" in path_item:
                        path_config["recognition"] = path_item["recognition"]
                    if "action_delay" in path_item:
                        path_config["action_delay"] = path_item["action_delay"]
                    
                    for target_node in target_nodes:
                        # 只为兄弟节点添加配置
                        if target_node in children and target_node != child_node:
                            sibling_key = f"{child_node}->{target_node}"
                            if sibling_key not in path_actions:
                                path_actions[sibling_key] = path_config
                                print(f"[MapNavigator] 同层级导航配置: {sibling_key}")
        
        # 第二步：提取通用返回节点的完整配置
        generic_return_config = None  # 通用返回按钮配置
        generic_home_config = None    # 通用返回主页按钮配置
        
        # 查找 "->上一级" 或 "->返回"
        for key_name in ["->上一级", "->返回"]:
            if key_name in self.map_data:
                node_data = self.map_data[key_name]
                generic_return_config = {"action": node_data.get("action", {})}
                if "recognition" in node_data:
                    generic_return_config["recognition"] = node_data["recognition"]
                print(f"[MapNavigator] 找到通用返回节点: {key_name}")
                break
        
        # 查找 "->map主页"
        if "->map主页" in self.map_data:
            node_data = self.map_data["->map主页"]
            generic_home_config = {"action": node_data.get("action", {})}
            if "recognition" in node_data:
                generic_home_config["recognition"] = node_data["recognition"]
            print(f"[MapNavigator] 找到通用返回主页节点: ->map主页")
        
        # 第三步：为 return_home=true 的节点创建返回配置（如果未定义）
        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue
            
            # 检查是否有 return_home=true
            if not node_data.get("return_home", False):
                continue
            
            # 1. 查找所有指向当前节点的来源节点
            source_nodes = []
            
            # 1.1 检查 include_node 包含关系
            include_parent = self.get_parent_node(node_name)
            if include_parent:
                source_nodes.append(include_parent)
            
            # 1.2 检查 path_list 导航关系
            for other_node, other_data in self.map_data.items():
                if not other_node.startswith("map"):
                    continue
                if other_node == node_name:
                    continue
                
                # 检查该节点的 path_list
                path_info = other_data.get("path", {})
                path_list = path_info.get("path_list", [])
                
                for path_item in path_list:
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    if node_name in target_nodes:
                        if other_node not in source_nodes:
                            source_nodes.append(other_node)
                        break
            
            # 2. 为每个来源节点添加反向边配置（如果未定义）
            for source_node in source_nodes:
                if source_node not in all_map_nodes:
                    continue
                
                source_key = f"{node_name}->{source_node}"
                if source_key not in path_actions:
                    if generic_return_config:
                        path_actions[source_key] = generic_return_config
                        print(f"[MapNavigator] 使用通用返回配置: {source_key}")
                    else:
                        # 如果没有通用返回节点，使用 DoNothing
                        path_actions[source_key] = {"action": {"type": "DoNothing", "param": {}}}
                        print(f"[MapNavigator] 警告: {source_key} 使用 DoNothing（未找到通用返回节点）")
            
            # 3. 添加返回主页的配置（如果未定义）
            if home_node in all_map_nodes and node_name != home_node:
                home_key = f"{node_name}->{home_node}"
                if home_key not in path_actions:
                    if generic_home_config:
                        path_actions[home_key] = generic_home_config
                        print(f"[MapNavigator] 使用通用返回主页配置: {home_key}")
                    else:
                        # 如果没有通用返回主页节点，使用 DoNothing
                        path_actions[home_key] = {"action": {"type": "DoNothing", "param": {}}}
                        print(f"[MapNavigator] 警告: {home_key} 使用 DoNothing（未找到通用返回主页节点）")
        
        return path_actions

    def get_including_node(self, node_name: str) -> Optional[str]:
        """获取包含指定节点的节点

        Args:
            node_name: 节点名称

        Returns:
            包含该节点的节点名称，如果不存在返回 None
        """
        return self.included_by.get(node_name)

    def get_map_nodes(self) -> List[str]:
        """获取所有 map 类型节点（不包括被包含的）"""
        return self.info_nodes

    def get_children_nodes(self, parent_node: str) -> List[str]:
        """获取指定节点的所有子节点"""
        return self.hierarchy.get(parent_node, {}).get("children", [])

    def get_parent_node(self, child_node: str) -> Optional[str]:
        """获取指定节点的父节点"""
        return self.hierarchy.get(child_node, {}).get("parent")
    
    def get_root_parent_node(self, node: str) -> str:
        """获取节点的根父节点（最顶层祖先）
        
        递归向上查找，直到找到没有父节点的根节点。
        
        Args:
            node: 节点名称
        
        Returns:
            根父节点名称，如果节点本身没有父节点则返回自身
        """
        current = node
        visited = set()  # 防止循环引用
        
        while current not in visited:
            visited.add(current)
            parent = self.get_parent_node(current)
            if parent is None:
                return current
            current = parent
        
        # 如果检测到循环，返回当前节点
        print(f"[MapNavigator] 警告: 检测到循环 include_node 关系: {visited}")
        return node
    
    def get_all_ancestors(self, node: str) -> List[str]:
        """获取节点的所有祖先节点（从直接父节点到根节点）
        
        Args:
            node: 节点名称
        
        Returns:
            祖先节点列表，按从近到远排序（[直接父节点, 祖父节点, ...]）
        """
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
    
    def is_in_same_include_tree(self, node1: str, node2: str) -> bool:
        """判断两个节点是否在同一个 include 层级树中
        
        Args:
            node1: 第一个节点
            node2: 第二个节点
        
        Returns:
            True 如果两个节点有共同的根祖先（通过 include_node 关系）
        """
        root1 = self.get_root_parent_node(node1)
        root2 = self.get_root_parent_node(node2)
        return root1 == root2
    
    def collect_tree_nodes(self, root_node: str) -> set:
        """递归收集根节点及其所有 include 子节点（完整的 include 树）
        
        Args:
            root_node: 根节点名称
        
        Returns:
            包含根节点及其所有后代的集合
        """
        nodes = {root_node}
        children = self.map_data.get(root_node, {}).get("include_node", [])
        
        for child in children:
            if child.startswith("map"):  # 只处理 map 节点
                nodes.add(child)
                # 递归收集子节点的后代
                nodes.update(self.collect_tree_nodes(child))
        
        return nodes

    def _build_graph(self) -> Dict[str, List[Tuple[str, float]]]:
        """构建加权地图邻接表
        
        子节点继承父节点的所有外部出边（不包括内部导航）。
        返回 {from_node: [(to_node, weight), ...]}，权重为毫秒时间。
        """
        graph = {}
        all_map_nodes = self._get_all_map_nodes()
        home_node = "map主页"

        # 初始化所有节点
        for node_name in all_map_nodes:
            graph[node_name] = []

        # 第一步：从每个节点的 path.path_list 构建边
        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue

            # 获取路径列表
            path_info = node_data.get("path", {})
            path_list = path_info.get("path_list", [])

            for path_item in path_list:
                # 获取目标节点（next_map 或 back_map）
                target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                if not target_nodes:
                    continue

                # 使用固定权重（简化寻路算法）
                weight = self.DEFAULT_EDGE_WEIGHT

                # 添加边
                for target_node in target_nodes:
                    if target_node in all_map_nodes:
                        # 检查是否已存在该边
                        existing_edge = next(
                            (edge for edge in graph[node_name] if edge[0] == target_node), 
                            None
                        )
                        if existing_edge is None:
                            graph[node_name].append((target_node, weight))

        # 第二步：处理 return_home=true 的节点
        # 自动添加反向边（返回来源节点）和返回主页边
        for node_name, node_data in self.map_data.items():
            if not node_name.startswith("map"):
                continue

            # 检查是否有 return_home=true
            if not node_data.get("return_home", False):
                continue

            # 使用固定权重
            default_weight = self.DEFAULT_EDGE_WEIGHT
            
            # 1. 查找所有指向当前节点的来源节点（反向边）
            # 注意：include 子节点不需要返回到 include 父节点的边
            # 原因：include 子节点是父节点页面内的内容（同 UI 界面），
            #      会直接继承父节点的外部边，无需显式返回
            source_nodes = []
            
            # 获取 include 父节点（用于后续排除）
            include_parent = self.get_parent_node(node_name)
            
            # 检查 path_list 导航关系：遍历所有节点，找到指向当前节点的
            for other_node, other_data in self.map_data.items():
                if not other_node.startswith("map"):
                    continue
                if other_node == node_name:
                    continue
                
                # 检查该节点的 path_list
                path_info = other_data.get("path", {})
                path_list = path_info.get("path_list", [])
                
                for path_item in path_list:
                    # 检查 next_map 或 back_map 是否包含当前节点
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    if node_name in target_nodes:
                        # 找到了指向当前节点的来源
                        # 但要排除 include 父节点（因为 include 子节点不需要返回边）
                        if other_node != include_parent:
                            if other_node not in source_nodes:
                                source_nodes.append(other_node)
                        break
            
            # 2. 为每个来源节点添加反向边（如果未定义）
            for source_node in source_nodes:
                if source_node not in all_map_nodes:
                    continue
                
                # 检查是否已有边
                has_edge = any(edge[0] == source_node for edge in graph[node_name])
                if not has_edge:
                    graph[node_name].append((source_node, default_weight))
                    print(f"[MapNavigator] 自动添加反向边: {node_name} -> {source_node}")
            
            # 3. 添加到主页的边（如果未定义）
            has_home_path = any(edge[0] == home_node for edge in graph[node_name])
            if not has_home_path and home_node in all_map_nodes and node_name != home_node:
                graph[node_name].append((home_node, default_weight))
                print(f"[MapNavigator] 自动添加返回主页边: {node_name} -> {home_node}")

        # 第三步：处理 include_node 的层级导航
        # 3.1 为同层级兄弟节点添加导航边（基于父节点的 path_list）
        for parent_node, node_data in self.map_data.items():
            if not parent_node.startswith("map"):
                continue
            
            # 获取该节点包含的子节点
            children = node_data.get("include_node", [])
            if not children:
                continue
            
            # 获取父节点的 path_list
            path_info = node_data.get("path", {})
            path_list = path_info.get("path_list", [])
            
            # 为每个子节点添加到兄弟节点的边（同层级导航）
            for child_node in children:
                if child_node not in all_map_nodes:
                    continue
                
                # 遍历父节点的 path_list，找到到兄弟节点的路径
                for path_item in path_list:
                    target_nodes = path_item.get("next_map", path_item.get("back_map", []))
                    
                    # 使用固定权重
                    weight = self.DEFAULT_EDGE_WEIGHT
                    
                    for target_node in target_nodes:
                        # 只添加到兄弟节点的边（同层级）
                        if target_node in children and target_node != child_node:
                            # 检查是否已有边
                            has_edge = any(edge[0] == target_node for edge in graph[child_node])
                            if not has_edge:
                                graph[child_node].append((target_node, weight))
                                print(f"[MapNavigator] 同层级导航: {child_node} -> {target_node}")
        
        # 3.2 子节点继承所有祖先的外部出边（支持多层嵌套）
        # 优化：缓存每个根节点的 tree_nodes，避免重复计算
        tree_nodes_cache = {}
        
        for node_name in all_map_nodes:
            # 获取该节点的所有祖先（从近到远）
            ancestors = self.get_all_ancestors(node_name)
            if not ancestors:
                continue  # 没有祖先，跳过
            
            # 收集同一 include 树中的所有节点（用于判断内部导航）
            root_ancestor = ancestors[-1]  # 最远的祖先（根节点）
            
            # 使用缓存避免重复计算
            if root_ancestor not in tree_nodes_cache:
                tree_nodes_cache[root_ancestor] = self.collect_tree_nodes(root_ancestor)
            tree_nodes = tree_nodes_cache[root_ancestor]
            
            # 优化：使用 set 加速边的查找
            existing_targets = {edge[0] for edge in graph[node_name]}
            
            # 从每个祖先继承外部出边
            for ancestor in ancestors:
                ancestor_edges = graph.get(ancestor, [])
                
                for target_node, weight in ancestor_edges:
                    # 排除内部导航：只有目标节点不在同一 include 树中时才继承
                    if target_node in tree_nodes:
                        continue  # 跳过到同树节点的边（内部导航）
                    
                    # 优化：使用 set 检查是否已经有到该目标的边（O(1) vs O(n)）
                    if target_node not in existing_targets:
                        graph[node_name].append((target_node, weight))
                        existing_targets.add(target_node)  # 更新已存在的目标集合
                        print(f"[MapNavigator] 子节点继承祖先外部出边: {node_name} -> {target_node} (从 {ancestor})")

        return graph

    def find_path(self, start: str, end: str) -> Optional[List[str]]:
        """使用 Dijkstra 算法查找时间最短的路径"""
        if start not in self.graph or end not in self.graph:
            return None

        if start == end:
            return [start]

        # Dijkstra 算法
        # 优先队列：(累计权重, 当前节点, 路径)
        heap = [(0, start, [start])]
        # 记录到达每个节点的最小权重
        visited = {start: 0}

        while heap:
            current_weight, current_node, path = heapq.heappop(heap)

            # 如果已经找到更优路径，跳过
            if current_weight > visited.get(current_node, float('inf')):
                continue

            # 到达终点
            if current_node == end:
                total_time = current_weight / 1000.0  # 转换为秒
                print(f"[MapNavigator] 找到最优路径: {' -> '.join(path)} (预计耗时: {total_time:.1f}s)")
                return path

            # 遍历邻居
            for neighbor, weight in self.graph.get(current_node, []):
                new_weight = current_weight + weight
                
                # 如果找到更优路径
                if new_weight < visited.get(neighbor, float('inf')):
                    visited[neighbor] = new_weight
                    new_path = path + [neighbor]
                    heapq.heappush(heap, (new_weight, neighbor, new_path))

        return None

    def _find_path_item(self, from_node: str, to_node: str) -> Optional[Dict]:
        """从节点的 path_list 中查找到目标节点的路径项
        
        Args:
            from_node: 起始节点
            to_node: 目标节点
            
        Returns:
            路径项字典，如果不存在返回 None
        """
        node_data = self.map_data.get(from_node, {})
        path_info = node_data.get("path", {})
        path_list = path_info.get("path_list", [])
        
        for path_item in path_list:
            # 检查 next_map 或 back_map 是否包含目标节点
            target_nodes = path_item.get("next_map", path_item.get("back_map", []))
            if to_node in target_nodes:
                return path_item
        
        return None
    
    def get_move_action_name(self, from_node: str, to_node: str) -> Optional[str]:
        """获取移动动作键，格式为 "from_node->to_node" """
        key = f"{from_node}->{to_node}"
        
        # 直接检查路径是否存在
        if key in self.path_actions:
            return key
        
        # 如果是子节点，检查父节点是否有这条路径
        parent_node = self.get_including_node(from_node)
        if parent_node:
            parent_key = f"{parent_node}->{to_node}"
            if parent_key in self.path_actions:
                # 返回子节点的键，但实际动作会使用父节点的
                return key
    
    def get_action_delay(self, from_node: str, to_node: str) -> float:
        """获取指定路径的动作延迟（秒）
        
        Args:
            from_node: 起始节点
            to_node: 目标节点
        
        Returns:
            延迟时间（秒），如果未配置则返回 0
        """
        key = f"{from_node}->{to_node}"
        
        # 直接检查路径
        if key in self.path_actions:
            delay_ms = self.path_actions[key].get("action_delay", 0)
            return delay_ms / 1000.0  # 转换为秒
        
        # 检查父节点的路径
        parent_node = self.get_including_node(from_node)
        if parent_node:
            parent_key = f"{parent_node}->{to_node}"
            if parent_key in self.path_actions:
                delay_ms = self.path_actions[parent_key].get("action_delay", 0)
                return delay_ms / 1000.0
        
        return 0.0  # 默认无延迟
    
    def get_action_data(self, from_node: str, to_node: str) -> Optional[Dict]:
        """获取路径配置数据，子节点可继承所有祖先的配置（支持多层嵌套）"""
        key = f"{from_node}->{to_node}"
        
        # 先尝试直接查找
        if key in self.path_actions:
            return self.path_actions[key]
        
        # 如果 from_node 是被包含的子节点，依次尝试所有祖先的配置
        ancestors = self.get_all_ancestors(from_node)
        for ancestor in ancestors:
            ancestor_key = f"{ancestor}->{to_node}"
            if ancestor_key in self.path_actions:
                print(f"[MapNavigator] 子节点使用祖先配置: {from_node} -> {to_node} (使用 {ancestor} 的配置)")
                return self.path_actions[ancestor_key]
        
        return None

@AgentServer.custom_action("map_movement")
class map_movement(CustomAction):
    """
    地图移动自定义动作：自动寻路并执行移动

    参数格式:
    {
        "move_destination": "目标节点名称",              # 必需
        "current_location": "当前节点名称",             # 可选，不提供则自动检测
        "verify_arrival": true/false,                  # 可选，是否验证到达（默认true）
        "detection_timeout": 15                        # 可选，自动检测超时时间/秒（默认15）
    }

    说明:
    - 自动检测采用轮询策略：每轮对所有节点各识别一次，提高检测效率
    - 智能检测模式（verify_arrival=true）：
      * 执行动作后同时检测起点和终点
      * 检测到起点自动重新执行动作
      * 检测到终点立即继续
      * 自动重试，无需配置
    - 每步移动超时时间从节点的 recognition.timeout 获取（默认15秒）
    """

    # 常量定义
    STOP_CHECK_INTERVAL = 0.1  # 停止信号检查间隔（秒）
    DETECTION_ROUND_DELAY = 0.5  # 检测轮次间隔（秒）
    DEFAULT_HOME_NODE = "map主页"  # 默认主页节点名称
    DEFAULT_DETECTION_TIMEOUT = 15  # 默认检测超时（秒）
    DEFAULT_STEP_TIMEOUT = 15  # 默认单步移动超时（秒）

    # 类变量：缓存
    _navigator: Optional[MapNavigator] = None
    _map_data: Optional[Dict] = None
    _map_file_path = None  # 将在首次加载时确定

    @classmethod
    def _find_map_file(cls) -> str:
        """查找地图配置文件路径
        
        支持两种路径结构：
        1. 开发环境: ./assets/resource/base/pipeline/map.json
        2. 发布版本: ./resource/base/pipeline/map.json
        
        Returns:
            地图文件路径
        
        Raises:
            FileNotFoundError: 如果两种路径都不存在
        """
        # 可能的路径列表（按优先级排序）
        possible_paths = [
            "./assets/resource/base/pipeline/map.json",  # 开发环境
            "./resource/base/pipeline/map.json",         # 发布版本
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                print(f"[map_movement] 找到地图配置: {path}")
                return path
        
        # 如果都不存在，抛出异常并列出尝试的路径
        error_msg = (
            f"未找到地图配置文件！已尝试以下路径：\n"
            + "\n".join(f"  - {p}" for p in possible_paths)
        )
        raise FileNotFoundError(error_msg)

    @classmethod
    def _load_map_navigator(cls) -> MapNavigator:
        """加载或获取缓存的地图导航器"""
        if cls._navigator is None:
            # 首次加载时查找文件路径
            if cls._map_file_path is None:
                cls._map_file_path = cls._find_map_file()
            
            with open(cls._map_file_path, "r", encoding="utf-8") as f:
                cls._map_data = json.load(f)
            cls._navigator = MapNavigator(cls._map_data)
        return cls._navigator

    @classmethod
    def _get_map_data(cls) -> Dict:
        """获取地图数据"""
        if cls._map_data is None:
            cls._load_map_navigator()
        return cls._map_data

    def _is_directhit(self, node_name: str) -> bool:
        """检查节点是否使用 DirectHit 识别"""
        node_data = self._get_map_data().get(node_name, {})
        return node_data.get("recognition", {}).get("type", "DirectHit") == "DirectHit"

    def _detect_current_location(
        self, context: Context, timeout: Optional[int] = None
    ) -> Optional[str]:
        """自动检测当前位置

        策略：循环轮询所有节点，每个节点只识别一次，然后快速切换到下一个节点
        使用 context.run_recognition 直接调用识别，避免 run_task 的重试机制

        Args:
            context: MAA上下文
            timeout: 总超时时间（秒），None 则使用默认值

        Returns:
            检测到的节点名称，未检测到返回 None
        """
        timeout = timeout or self.DEFAULT_DETECTION_TIMEOUT
        print(f"[map_movement] 开始自动检测当前位置 (超时: {timeout}s)...")

        # 获取有效的检测节点
        valid_nodes = self._get_valid_detection_nodes()
        if not valid_nodes:
            print("[map_movement] 没有可用于检测的节点")
            return None

        print(f"[map_movement] 待检测节点数: {len(valid_nodes)}")

        start_time = time.time()
        round_count = 0

        # 循环检测：每轮对所有节点各检测一次
        while time.time() - start_time < timeout:
            # 循环入口检查中断
            check_interrupt_and_raise(context, "检测当前位置")
            
            round_count += 1
            print(f"[map_movement] 第 {round_count} 轮检测...")

            # 执行本轮检测
            detected_node = self._detect_round(
                context, valid_nodes, start_time, round_count
            )
            if detected_node:
                return detected_node

            # 本轮未检测到，等待后进入下一轮
            if not interruptible_sleep(context, self.DETECTION_ROUND_DELAY):
                return None

        elapsed = time.time() - start_time
        print(
            f"[map_movement] 未能检测到当前位置 (共{round_count}轮, 耗时: {elapsed:.1f}s)"
        )
        return None

    def _get_valid_detection_nodes(self) -> List[str]:
        """获取所有可用于检测的节点（过滤掉 DirectHit 节点和被包含的节点）
        
        返回的节点列表已按名称排序，用于第一级地图定位。
        被 include_node 包含的节点不会出现在此列表中。
        """
        navigator = self._load_map_navigator()
        info_nodes = navigator.get_info_nodes()  # 已排除被包含的节点
        valid_nodes = [node for node in info_nodes if not self._is_directhit(node)]

        # 按名称排序
        return sorted(valid_nodes)

    def _detect_round(
        self, context: Context, nodes: List[str], start_time: float, round_num: int
    ) -> Optional[str]:
        """执行一轮检测（分层策略）

        策略：
        1. 先检测第一级 map 节点（不包括被 include_node 包含的）
        2. 如果找到 map，递归检测该 map 下通过 include_node 包含的子节点
        3. 返回最精确（最深层级）的节点

        注意：每轮开始时截取新截图，同一轮内的所有识别使用同一张截图

        Args:
            context: MAA上下文
            nodes: 待检测的节点列表（第一级 map 节点）
            start_time: 开始时间
            round_num: 当前轮次

        Returns:
            检测到的节点名称，未检测到返回 None
        """
        # 每轮开始时主动刷新截图，保证画面最新
        try:
            image = get_fresh_screenshot(context)
        except Exception as e:
            print(f"[map_movement] 获取截图失败: {e}")
            return None

        navigator = self._load_map_navigator()

        # 第一步：检测 map 节点（使用本轮截图）
        detected_map = None
        for node_name in nodes:
            if not node_name.startswith("map"):
                break  # nodes 已排序，遇到非 map 节点就停止

            try:
                reco_detail = context.run_recognition(node_name, image)
                if is_recognition_success(reco_detail):
                    detected_map = node_name
                    print(f"[map_movement] 检测到 MAP: {detected_map}")
                    break
            except Exception:
                continue

        if not detected_map:
            # 没检测到任何 map，返回 None
            return None

        # 第二步：递归检测子节点（使用同一张截图）
        detected_node = self._detect_children_recursive(
            context, image, navigator, detected_map, start_time, round_num
        )

        return detected_node

    def _detect_children_recursive(
        self,
        context: Context,
        image,
        navigator: MapNavigator,
        parent_node: str,
        start_time: float,
        round_num: int,
    ) -> str:
        """递归检测子节点，返回最深层级的匹配节点

        通过 include_node 字段定义的层级关系进行递归检测。
        支持多层嵌套：map -> map -> map ...

        注意：使用同一轮的截图进行识别，保证同一轮内的一致性

        Args:
            context: MAA上下文
            image: 本轮的截图
            navigator: 地图导航器
            parent_node: 父节点（map 类型）
            start_time: 开始时间
            round_num: 当前轮次

        Returns:
            最深层级的匹配节点名称
        """
        children = navigator.get_children_nodes(parent_node)
        if not children:
            # 没有子节点，返回父节点
            return parent_node

        # 检测所有子节点（使用本轮截图）
        for child_name in children:
            # 跳过 DirectHit 节点
            if self._is_directhit(child_name):
                continue

            try:
                reco_detail = context.run_recognition(child_name, image)
                if is_recognition_success(reco_detail):
                    # 找到匹配的子节点，递归检测其子节点（使用同一张截图）
                    deepest_node = self._detect_children_recursive(
                        context, image, navigator, child_name, start_time, round_num
                    )

                    # 打印检测路径
                    if deepest_node == child_name:
                        elapsed = time.time() - start_time
                        print(
                            f"[map_movement] 检测成功: 当前位置为 {deepest_node} "
                            f"(父节点: {parent_node}, 第{round_num}轮, 耗时: {elapsed:.1f}s)"
                        )
                    else:
                        elapsed = time.time() - start_time
                        print(
                            f"[map_movement] 检测成功: 当前位置为 {deepest_node} "
                            f"(路径: {parent_node} -> {child_name} -> {deepest_node}, "
                            f"第{round_num}轮, 耗时: {elapsed:.1f}s)"
                        )

                    return deepest_node
            except Exception:
                continue

        # 没检测到任何子节点，返回父节点
        elapsed = time.time() - start_time
        print(
            f"[map_movement] 检测成功: 当前位置为 {parent_node} "
            f"(无子节点匹配, 第{round_num}轮, 耗时: {elapsed:.1f}s)"
        )
        return parent_node

    def _verify_arrival(self, context: Context, target_node: str) -> bool:
        """验证是否成功到达目标节点
        
        使用 run_recognition 而不是 run_task，这样可以：
        1. 自己控制重试逻辑
        2. 在每次重试前检查中断信号
        3. 快速响应停止请求

        Args:
            context: MAA上下文
            target_node: 目标节点
        """
        if self._is_directhit(target_node):
            return True

        print(f"[map_movement] 验证到达: {target_node}")
        start_time = time.time()
        
        # 从 recognition.timeout 获取超时设置（默认5秒）
        node_data = self._get_map_data().get(target_node, {})
        recognition_config = node_data.get("recognition", {})
        timeout_ms = recognition_config.get("timeout", 5000)
        timeout = timeout_ms / 1000.0  # 转换为秒
        
        retry_interval = 0.5  # 重试间隔（秒）
        
        end_time = start_time + timeout
        
        try:
            while time.time() < end_time:
                # 循环入口检查中断
                check_interrupt_and_raise(context, "验证到达")
                
                # 获取新截图并识别
                try:
                    image = get_fresh_screenshot(context)
                    reco_detail = context.run_recognition(target_node, image)
                    
                    if is_recognition_success(reco_detail):
                        elapsed = time.time() - start_time
                        print(f"[map_movement] 验证成功: {target_node} (耗时: {elapsed:.1f}s)")
                        return True
                except Exception as e:
                    # 识别异常，继续重试
                    pass
                
                # 检查是否还有时间继续重试
                if time.time() + retry_interval >= end_time:
                    break
                
                # 等待后重试（interruptible_sleep 内部会检查中断）
                interruptible_sleep(context, retry_interval)
        
        except Exception as e:
            print(f"[map_movement] 验证异常: {str(e)}")

        elapsed = time.time() - start_time
        print(f"[map_movement] 验证失败: {target_node} (耗时: {elapsed:.1f}s)")
        return False

    def run(
        self, context: Context, argv: CustomAction.RunArg
    ) -> CustomAction.RunResult:
        """执行地图移动

        Args:
            context: MAA上下文
            argv: 自定义动作参数

        Returns:
            执行结果
        """
        try:
            # 检查中断
            check_interrupt_and_raise(context, "map_movement.run()")
            
            # 解析参数
            params = parse_custom_param(argv.custom_action_param)
            
            destination = params.get("move_destination")
            current_location = params.get("current_location")
            verify_arrival = params.get("verify_arrival", True)
            detection_timeout = params.get(
                "detection_timeout", self.DEFAULT_DETECTION_TIMEOUT
            )

            # 验证目标节点
            if not destination:
                print("[map_movement] 错误: 未指定目标节点")
                return CustomAction.RunResult(success=False)

            print(f"[map_movement] 目标: {destination}")

            # 确定起点
            current_location = self._determine_start_location(
                context, current_location, detection_timeout
            )
            if not current_location:
                print("[map_movement] 错误: 无法确定起点")
                return CustomAction.RunResult(success=False)

            print(f"[map_movement] 起点: {current_location}")

            # 检查是否已在目标位置
            if current_location == destination:
                print("[map_movement] 已在目标位置")
                return CustomAction.RunResult(success=True)

            # 查找路径
            navigator = self._load_map_navigator()
            path = navigator.find_path(current_location, destination)
            if path is None:
                print(
                    f"[map_movement] 错误: 找不到路径 ({current_location} -> {destination})"
                )
                return CustomAction.RunResult(success=False)

            print(f"[map_movement] 路径: {' -> '.join(path)} ({len(path) - 1}步)")

            # 执行移动
            if not self._execute_path(
                context, navigator, path, verify_arrival
            ):
                return CustomAction.RunResult(success=False)

            print(f"[map_movement] 已到达: {destination}")
            return CustomAction.RunResult(success=True)

        except TaskInterruptedException:
            # 中断信号：返回 False 让任务自然结束
            print("[map_movement] 检测到中断信号，任务终止")
            return CustomAction.RunResult(success=False)
        except Exception as e:
            print(f"[map_movement] 异常: {str(e)}")
            import traceback

            traceback.print_exc()
            return CustomAction.RunResult(success=False)


    def _determine_start_location(
        self, context: Context, provided_location: Optional[str], detection_timeout: int
    ) -> Optional[str]:
        """确定起始位置（优先级：用户提供 > 自动检测 > 默认主页）"""
        # 1. 用户提供的位置
        if provided_location:
            return provided_location

        # 2. 自动检测当前位置
        detected_location = self._detect_current_location(context, detection_timeout)
        if detected_location:
            return detected_location

        # 3. 检测失败，使用默认主页作为起点
        print(f"[map_movement] 检测失败，使用默认起点: {self.DEFAULT_HOME_NODE}")
        return self.DEFAULT_HOME_NODE

    def _execute_path(
        self,
        context: Context,
        navigator: MapNavigator,
        path: List[str],
        verify_arrival: bool,
    ) -> bool:
        """执行路径移动

        Args:
            context: MAA上下文
            navigator: 地图导航器
            path: 移动路径
            verify_arrival: 是否验证到达

        Returns:
            是否成功
        """
        for i in range(len(path) - 1):
            # 循环入口检查中断
            check_interrupt_and_raise(context, "执行路径移动")
            
            from_node = path[i]
            to_node = path[i + 1]

            # 执行单步移动
            if not self._execute_single_move(
                context,
                navigator,
                from_node,
                to_node,
                i + 1,
                verify_arrival,
            ):
                return False

        return True

    def _execute_single_move(
        self,
        context: Context,
        navigator: MapNavigator,
        from_node: str,
        to_node: str,
        step_num: int,
        verify_arrival: bool,
    ) -> bool:
        """执行单步移动（智能检测版）
        
        新逻辑：
        1. 执行动作后同时检测起点和终点
        2. 检测到起点 → 动作失败，重新执行
        3. 检测到终点 → 到达目标，继续
        4. 都检测不到 → 过场动画中，继续等待
        5. 超时则失败

        Args:
            context: MAA上下文
            navigator: 地图导航器
            from_node: 起始节点
            to_node: 目标节点
            step_num: 步骤编号
            verify_arrival: 是否验证到达

        Returns:
            是否成功
        """
        action_name = navigator.get_move_action_name(from_node, to_node)
        if action_name is None:
            print(f"[map_movement] 错误: 找不到移动动作 {from_node}->{to_node}")
            return False

        print(f"[map_movement] 步骤 {step_num}: {from_node} -> {to_node}")

        # 如果不需要验证到达，仅执行动作
        if not verify_arrival:
            return self._execute_action_only(
                context, navigator, action_name, from_node, to_node
            )
        
        # 使用智能检测逻辑（默认）
        return self._execute_move_with_smart_detection(
            context, navigator, action_name, from_node, to_node
        )

    def _execute_move_with_smart_detection(
        self,
        context: Context,
        navigator: MapNavigator,
        action_name: str,
        from_node: str,
        to_node: str,
    ) -> bool:
        """执行移动并智能检测（起点/终点同步检测）
        
        新逻辑：
        1. 执行动作
        2. 如果配置了 action_delay，等待指定时间（避免重复点击）
        3. 循环检测起点和终点：
           - 检测到起点 → 动作失败，重新执行
           - 检测到终点 → 到达目标，返回成功
           - 都检测不到 → 过场动画中，继续等待
        4. 超时则返回失败
        
        Args:
            context: MAA上下文
            navigator: 地图导航器
            action_name: 动作键
            from_node: 起始节点
            to_node: 目标节点
        
        Returns:
            是否成功
        """
        # 获取超时设置（从终点节点获取，默认15秒）
        to_node_data = self._get_map_data().get(to_node, {})
        recognition_config = to_node_data.get("recognition", {})
        timeout_ms = recognition_config.get("timeout", self.DEFAULT_STEP_TIMEOUT * 1000)  # 默认15秒
        timeout = timeout_ms / 1000.0
        
        # 获取动作延迟配置（用于慢速转移）
        action_delay = navigator.get_action_delay(from_node, to_node)
        
        retry_interval = 0.3  # 检测间隔（秒）
        start_time = time.time()
        end_time = start_time + timeout
        action_executed = False  # 标记动作是否已执行过
        
        if action_delay > 0:
            print(f"[map_movement] 智能检测模式: {from_node} -> {to_node} (超时: {timeout}s, 动作延迟: {action_delay}s)")
        else:
            print(f"[map_movement] 智能检测模式: {from_node} -> {to_node} (超时: {timeout}s)")
        
        while time.time() < end_time:
            # 检查中断
            check_interrupt_and_raise(context, "智能检测移动")
            
            # 如果动作还没执行，先执行动作
            if not action_executed:
                if not self._execute_action_only(context, navigator, action_name, from_node, to_node):
                    return False
                action_executed = True
                
                # 如果配置了动作延迟，等待指定时间再开始检测
                # 这用于处理慢速转移的情况，避免过早检测导致重复点击
                if action_delay > 0:
                    print(f"[map_movement] 动作已执行，等待 {action_delay}s 后开始检测...")
                    if not interruptible_sleep(context, action_delay):
                        return False  # 中断
                else:
                    print(f"[map_movement] 动作已执行，开始检测...")
            
            # 获取新截图
            try:
                image = get_fresh_screenshot(context)
            except Exception as e:
                print(f"[map_movement] 截图异常: {e}")
                interruptible_sleep(context, retry_interval)
                continue
            
            # 1. 优先检测终点（到达目标）
            if not self._is_directhit(to_node):
                try:
                    reco_detail = context.run_recognition(to_node, image)
                    if is_recognition_success(reco_detail):
                        elapsed = time.time() - start_time
                        print(f"[map_movement] 检测到终点: {to_node} (耗时: {elapsed:.1f}s)")
                        return True
                except Exception:
                    pass
            
            # 2. 检测起点（动作失败，需要重试）
            if not self._is_directhit(from_node):
                try:
                    reco_detail = context.run_recognition(from_node, image)
                    if is_recognition_success(reco_detail):
                        elapsed = time.time() - start_time
                        print(f"[map_movement] 检测到起点: {from_node}，动作可能失败，重新执行 (耗时: {elapsed:.1f}s)")
                        # 重新执行动作
                        if not self._execute_action_only(context, navigator, action_name, from_node, to_node):
                            return False
                        
                        # 如果配置了动作延迟，等待后再继续检测
                        if action_delay > 0:
                            print(f"[map_movement] 动作已重新执行，等待 {action_delay}s 后继续检测...")
                            if not interruptible_sleep(context, action_delay):
                                return False  # 中断
                        else:
                            print(f"[map_movement] 动作已重新执行，继续检测...")
                        continue
                except Exception:
                    pass
            
            # 3. 都检测不到 → 过场动画中，继续等待
            # （不打印日志，避免刷屏）
            
            # 检查是否还有时间继续
            if time.time() + retry_interval >= end_time:
                break
            
            # 等待后继续检测
            interruptible_sleep(context, retry_interval)
        
        # 超时失败
        elapsed = time.time() - start_time
        print(f"[map_movement] 移动超时: {from_node} -> {to_node} (耗时: {elapsed:.1f}s)")
        return False
    
    def _execute_action_only(
        self,
        context: Context,
        navigator: MapNavigator,
        action_name: str,
        from_node: str,
        to_node: str,
    ) -> bool:
        """仅执行动作，不等待过场
        
        Args:
            context: MAA上下文
            navigator: 地图导航器
            action_name: 动作键
            from_node: 起始节点
            to_node: 目标节点
        
        Returns:
            是否成功
        """
        # 获取路径配置
        path_config = navigator.get_action_data(from_node, to_node)
        if path_config is None:
            print(f"[map_movement] 错误: 未找到路径配置 ({from_node}->{to_node})")
            return False
        
        # 创建临时节点
        temp_node_name = f"__temp_move_{from_node}_to_{to_node}"
        temp_node_data = {"next": []}
        
        # 配置 recognition
        if "recognition" in path_config:
            temp_node_data["recognition"] = path_config["recognition"]
        else:
            temp_node_data["recognition"] = {"type": "DirectHit", "param": {}}
        
        # 配置 action
        temp_node_data["action"] = path_config.get("action", {})
        
        # 注入并执行
        context.override_pipeline({temp_node_name: temp_node_data})
        
        if not context.run_task(temp_node_name):
            print(f"[map_movement] 错误: 动作执行失败 ({from_node}->{to_node})")
            return False
        
        return True

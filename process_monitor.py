#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生图流程监控器 - 后台进程监控和执行流程捕获
监控ComfyUI后台执行过程，捕获完整的生图流程，并支持模拟验证
"""

import os
import sys
import json
import time
import requests
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import subprocess
import traceback

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class ExecutionFlowCapture:
    """执行流程捕获器"""
    
    def __init__(self, comfyui_port=8187):
        self.comfyui_url = f"http://127.0.0.1:{comfyui_port}"
        self.capture_dir = "captured_flows"
        os.makedirs(self.capture_dir, exist_ok=True)
        
        # 捕获的数据
        self.api_calls = []  # API调用记录
        self.execution_steps = []  # 执行步骤记录
        self.workflow_data = None  # 工作流数据
        self.monitoring = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """开始监控"""
        self.monitoring = True
        self.api_calls = []
        self.execution_steps = []
        
        logger.info("=" * 60)
        logger.info("🔍 开始监控后台执行流程")
        logger.info("=" * 60)
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        
        logger.info("⏹️ 停止监控")
        
    def _monitor_loop(self):
        """监控循环"""
        last_queue_check = 0
        last_history_check = {}
        
        while self.monitoring:
            try:
                current_time = time.time()
                
                # 1. 监控队列状态
                if current_time - last_queue_check > 1:
                    self._check_queue()
                    last_queue_check = current_time
                
                # 2. 监控历史记录（捕获执行细节）
                self._check_history(last_history_check)
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                
    def _check_queue(self):
        """检查队列状态"""
        try:
            response = requests.get(f"{self.comfyui_url}/queue", timeout=2)
            if response.status_code == 200:
                queue_data = response.json()
                
                # 记录队列变化
                running = queue_data.get('queue_running', [])
                pending = queue_data.get('queue_pending', [])
                
                if running:
                    for item in running:
                        prompt_id = item[1]
                        self._log_execution_step(
                            "QUEUE_RUNNING",
                            {"prompt_id": prompt_id, "status": "executing"}
                        )
                        
        except requests.exceptions.RequestException:
            pass  # 忽略网络错误
            
    def _check_history(self, last_check: dict):
        """检查执行历史"""
        try:
            response = requests.get(f"{self.comfyui_url}/history", timeout=2)
            if response.status_code == 200:
                history_data = response.json()
                
                # 检查新的执行记录
                for prompt_id, data in history_data.items():
                    if prompt_id not in last_check:
                        self._process_execution_history(prompt_id, data)
                        last_check[prompt_id] = data
                        
        except requests.exceptions.RequestException:
            pass
            
    def _process_execution_history(self, prompt_id: str, history_data: dict):
        """处理执行历史"""
        logger.info(f"📊 捕获到执行记录: {prompt_id[:8]}...")
        
        # 提取工作流
        prompt = history_data.get('prompt', [])
        if len(prompt) >= 3:
            workflow = prompt[2]
            self.workflow_data = workflow
            
            self._log_execution_step(
                "WORKFLOW_CAPTURED",
                {
                    "prompt_id": prompt_id,
                    "workflow": workflow,
                    "node_count": len(workflow) if isinstance(workflow, dict) else 0
                }
            )
            
        # 提取输出信息
        outputs = history_data.get('outputs', {})
        if outputs:
            self._log_execution_step(
                "OUTPUTS_GENERATED",
                {
                    "prompt_id": prompt_id,
                    "outputs": outputs
                }
            )
            
    def _log_execution_step(self, step_type: str, data: dict):
        """记录执行步骤"""
        step = {
            "timestamp": datetime.now().isoformat(),
            "type": step_type,
            "data": data
        }
        self.execution_steps.append(step)
        
        # 控制台输出
        if step_type == "WORKFLOW_CAPTURED":
            logger.info(f"  ✓ 捕获工作流 (节点数: {data.get('node_count', 0)})")
        elif step_type == "OUTPUTS_GENERATED":
            logger.info(f"  ✓ 生成完成")
            
    def capture_api_call(self, method: str, endpoint: str, data: Any = None, response: Any = None):
        """捕获API调用"""
        call = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "endpoint": endpoint,
            "request_data": data,
            "response_data": response
        }
        self.api_calls.append(call)
        
        logger.info(f"📡 API调用: {method} {endpoint}")
        
    def save_capture(self) -> str:
        """保存捕获的流程"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"flow_capture_{timestamp}.json"
        filepath = os.path.join(self.capture_dir, filename)
        
        capture_data = {
            "captured_at": datetime.now().isoformat(),
            "workflow": self.workflow_data,
            "execution_steps": self.execution_steps,
            "api_calls": self.api_calls,
            "summary": {
                "total_steps": len(self.execution_steps),
                "total_api_calls": len(self.api_calls),
                "has_workflow": self.workflow_data is not None
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(capture_data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"💾 流程已保存: {filepath}")
        return filepath


class FlowSimulator:
    """流程模拟器 - 重放捕获的流程进行验证"""
    
    def __init__(self, comfyui_port=8187):
        self.comfyui_url = f"http://127.0.0.1:{comfyui_port}"
        
    def load_captured_flow(self, filepath: str) -> dict:
        """加载捕获的流程"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    def simulate_flow(self, flow_data: dict, dry_run: bool = False) -> bool:
        """模拟执行流程
        
        Args:
            flow_data: 捕获的流程数据
            dry_run: 如果为True，只验证不实际执行
            
        Returns:
            是否验证成功
        """
        logger.info("=" * 60)
        logger.info("🔄 开始模拟执行流程")
        logger.info("=" * 60)
        
        workflow = flow_data.get('workflow')
        if not workflow:
            logger.error("❌ 流程数据中没有工作流")
            return False
            
        logger.info(f"📋 工作流节点数: {len(workflow)}")
        
        # 1. 验证工作流结构
        if not self._validate_workflow(workflow):
            logger.error("❌ 工作流结构验证失败")
            return False
            
        logger.info("✓ 工作流结构验证通过")
        
        # 2. 分析节点依赖
        node_graph = self._analyze_node_dependencies(workflow)
        logger.info(f"✓ 节点依赖分析完成 (共{len(node_graph)}个节点)")
        
        # 3. 如果不是dry_run，实际执行
        if not dry_run:
            success = self._execute_workflow(workflow)
            if success:
                logger.info("✅ 流程执行成功")
            else:
                logger.error("❌ 流程执行失败")
            return success
        else:
            logger.info("✓ 验证模式 - 跳过实际执行")
            return True
            
    def _validate_workflow(self, workflow: dict) -> bool:
        """验证工作流结构"""
        if not isinstance(workflow, dict):
            return False
            
        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                logger.error(f"节点 {node_id} 格式错误")
                return False
                
            # 检查必要字段
            if 'class_type' not in node_data:
                logger.error(f"节点 {node_id} 缺少 class_type")
                return False
                
        return True
        
    def _analyze_node_dependencies(self, workflow: dict) -> dict:
        """分析节点依赖关系"""
        node_graph = {}
        
        for node_id, node_data in workflow.items():
            dependencies = []
            
            # 分析输入中的依赖
            inputs = node_data.get('inputs', {})
            for input_name, input_value in inputs.items():
                if isinstance(input_value, list) and len(input_value) >= 1:
                    # [node_id, output_index] 格式
                    if isinstance(input_value[0], str):
                        dependencies.append(input_value[0])
                        
            node_graph[node_id] = {
                "class_type": node_data.get('class_type'),
                "dependencies": dependencies
            }
            
            logger.info(f"  节点 {node_id}: {node_data.get('class_type')} (依赖: {len(dependencies)}个)")
            
        return node_graph
        
    def _execute_workflow(self, workflow: dict) -> bool:
        """执行工作流"""
        try:
            logger.info("📤 提交工作流到ComfyUI...")
            
            response = requests.post(
                f"{self.comfyui_url}/prompt",
                json={"prompt": workflow},
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"提交失败: HTTP {response.status_code}")
                return False
                
            result = response.json()
            prompt_id = result.get('prompt_id')
            
            if not prompt_id:
                logger.error("未获取到prompt_id")
                return False
                
            logger.info(f"✓ 提交成功 (ID: {prompt_id[:8]}...)")
            
            # 等待执行完成
            return self._wait_for_completion(prompt_id)
            
        except Exception as e:
            logger.error(f"执行错误: {e}")
            traceback.print_exc()
            return False
            
    def _wait_for_completion(self, prompt_id: str, timeout: int = 300) -> bool:
        """等待执行完成"""
        start_time = time.time()
        last_log_time = start_time
        
        logger.info("⏳ 等待执行完成...")
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.comfyui_url}/history/{prompt_id}", timeout=5)
                if response.status_code == 200:
                    history = response.json()
                    if prompt_id in history:
                        logger.info("✓ 执行完成")
                        
                        # 显示输出信息
                        outputs = history[prompt_id].get('outputs', {})
                        if outputs:
                            logger.info(f"✓ 生成了 {len(outputs)} 个输出")
                        return True
                        
                # 每5秒输出一次等待信息
                current_time = time.time()
                if current_time - last_log_time >= 5:
                    elapsed = int(current_time - start_time)
                    logger.info(f"  等待中... ({elapsed}秒)")
                    last_log_time = current_time
                    
            except:
                pass
                
            time.sleep(2)
            
        logger.error("❌ 执行超时")
        return False


class ProcessMonitor:
    """主监控器 - 整合所有功能"""
    
    def __init__(self, comfyui_port=8187):
        self.port = comfyui_port
        self.capture = ExecutionFlowCapture(comfyui_port)
        self.simulator = FlowSimulator(comfyui_port)
        
    def monitor_and_capture(self, duration: int = 60):
        """监控并捕获流程
        
        Args:
            duration: 监控时长（秒），0表示手动停止
        """
        logger.info("=" * 60)
        logger.info("🎯 后台进程监控系统")
        logger.info("=" * 60)
        logger.info(f"ComfyUI端口: {self.port}")
        logger.info(f"监控时长: {'手动停止' if duration == 0 else f'{duration}秒'}")
        logger.info("")
        
        # 开始监控
        self.capture.start_monitoring()
        
        try:
            if duration == 0:
                logger.info("提示: 请在原界面完成生图操作，然后按 Ctrl+C 停止监控")
                while True:
                    time.sleep(1)
            else:
                logger.info(f"提示: 将监控 {duration} 秒，请在此期间完成生图操作")
                for i in range(duration):
                    time.sleep(1)
                    if (i + 1) % 10 == 0:
                        logger.info(f"  已监控 {i+1}/{duration} 秒...")
                        
        except KeyboardInterrupt:
            logger.info("\n⏹️ 用户中断监控")
            
        finally:
            # 停止监控
            self.capture.stop_monitoring()
            
            # 保存捕获结果
            if self.capture.execution_steps or self.capture.workflow_data:
                filepath = self.capture.save_capture()
                
                logger.info("")
                logger.info("=" * 60)
                logger.info("📊 捕获摘要")
                logger.info("=" * 60)
                logger.info(f"执行步骤: {len(self.capture.execution_steps)} 个")
                logger.info(f"API调用: {len(self.capture.api_calls)} 次")
                logger.info(f"工作流: {'已捕获' if self.capture.workflow_data else '未捕获'}")
                logger.info(f"保存位置: {filepath}")
                
                return filepath
            else:
                logger.warning("⚠️ 未捕获到任何执行流程")
                return None
                
    def verify_captured_flow(self, filepath: str, dry_run: bool = True):
        """验证捕获的流程
        
        Args:
            filepath: 捕获文件路径
            dry_run: 是否只验证不执行
        """
        logger.info("")
        logger.info("=" * 60)
        logger.info("🔍 验证捕获的流程")
        logger.info("=" * 60)
        
        # 加载流程
        flow_data = self.simulator.load_captured_flow(filepath)
        
        logger.info(f"文件: {filepath}")
        logger.info(f"捕获时间: {flow_data.get('captured_at')}")
        logger.info(f"执行步骤: {flow_data.get('summary', {}).get('total_steps')} 个")
        logger.info("")
        
        # 模拟执行
        success = self.simulator.simulate_flow(flow_data, dry_run=dry_run)
        
        logger.info("")
        if success:
            logger.info("✅ 验证通过 - 流程可以正确重放")
        else:
            logger.error("❌ 验证失败 - 流程存在问题")
            
        return success


def main():
    """主函数 - 命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='生图流程监控和验证工具')
    parser.add_argument('--port', type=int, default=8187, help='ComfyUI端口号')
    parser.add_argument('--duration', type=int, default=0, help='监控时长（秒），0表示手动停止')
    parser.add_argument('--verify', type=str, help='验证指定的捕获文件')
    parser.add_argument('--execute', action='store_true', help='实际执行（而不是只验证）')
    
    args = parser.parse_args()
    
    monitor = ProcessMonitor(args.port)
    
    if args.verify:
        # 验证模式
        monitor.verify_captured_flow(args.verify, dry_run=not args.execute)
    else:
        # 监控模式
        captured_file = monitor.monitor_and_capture(args.duration)
        
        # 如果捕获成功，自动验证
        if captured_file:
            logger.info("")
            input("按回车键开始验证捕获的流程...")
            monitor.verify_captured_flow(captured_file, dry_run=True)


if __name__ == "__main__":
    main()

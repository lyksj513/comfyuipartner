#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
猫仔ComfyUI伴侣 V3
此作品由lovelycateman/www.52pojie.cn开源，禁止商用
增强版：支持端口探测、配置保存/加载、单图处理模式、多种融合模式
"""

import os
import sys
import time
import json
import random
import requests
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
from pathlib import Path
import subprocess

# 导入核心监控模块
from process_monitor import ExecutionFlowCapture, FlowSimulator


class IntegratedGUI_V3:
    """监控 + 批量处理 一体化界面 V2"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🐱 猫仔ComfyUI伴侣")
        self.root.geometry("1100x900")
        
        # 核心组件
        self.port = 8187  # 默认端口
        self.comfyui_url = f"http://127.0.0.1:{self.port}"
        self.capture = None
        self.simulator = None
        
        # 状态变量
        self.is_monitoring = False
        self.captured_workflow = None
        self.current_batch_folder = None
        self.processing_thread = None
        self.is_processing = False
        self.paused = False
        self.stopped = False
        
        # 失败任务记录
        self.failed_tasks = []
        
        # 日志文件
        self.log_file = None
        self.log_file_path = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置界面"""
        # ===== 顶部标题和版权声明 =====
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        title_label = ttk.Label(
            header_frame,
            text="🐱 猫仔ComfyUI伴侣",
            font=("Microsoft YaHei UI", 16, "bold"),
            foreground="#2c3e50"
        )
        title_label.pack()
        
        copyright_label = ttk.Label(
            header_frame,
            text="此作品由lovelycateman/www.52pojie.cn开源，禁止商用",
            font=("Microsoft YaHei UI", 9),
            foreground="#7f8c8d"
        )
        copyright_label.pack(pady=(2, 0))
        
        # 分隔线
        separator = ttk.Separator(self.root, orient='horizontal')
        separator.pack(fill=tk.X, padx=10, pady=5)
        
        # ===== 第零部分：端口选择 =====
        port_section = ttk.LabelFrame(self.root, text="🔌 第零步：选择ComfyUI端口", padding=10)
        port_section.pack(fill=tk.X, padx=10, pady=5)
        
        port_frame = ttk.Frame(port_section)
        port_frame.pack(fill=tk.X)
        
        ttk.Label(port_frame, text="端口:").pack(side=tk.LEFT, padx=5)
        
        self.port_var = tk.StringVar(value="8187")
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, width=15)
        self.port_combo['values'] = ['8187', '8188', '8189']
        self.port_combo.pack(side=tk.LEFT, padx=5)
        
        self.detect_btn = ttk.Button(
            port_frame,
            text="🔍 探测可用端口",
            command=self.detect_ports,
            width=15
        )
        self.detect_btn.pack(side=tk.LEFT, padx=5)
        
        self.confirm_port_btn = ttk.Button(
            port_frame,
            text="✅ 确认端口",
            command=self.confirm_port,
            width=15
        )
        self.confirm_port_btn.pack(side=tk.LEFT, padx=5)
        
        self.port_status = ttk.Label(port_frame, text="⚪ 未确认", foreground="gray")
        self.port_status.pack(side=tk.LEFT, padx=20)
        
        # ===== 第一部分：监控捕获或加载 =====
        monitor_section = ttk.LabelFrame(self.root, text="📡 第一步：监控捕获流程 或 加载已保存的配置", padding=10)
        monitor_section.pack(fill=tk.X, padx=10, pady=5)
        
        # 监控控制
        control_frame = ttk.Frame(monitor_section)
        control_frame.pack(fill=tk.X)
        
        self.start_monitor_btn = ttk.Button(
            control_frame,
            text="▶️ 开始监控",
            command=self.start_monitoring,
            width=15,
            state=tk.DISABLED
        )
        self.start_monitor_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_monitor_btn = ttk.Button(
            control_frame,
            text="⏹️ 停止监控",
            command=self.stop_monitoring,
            state=tk.DISABLED,
            width=15
        )
        self.stop_monitor_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_workflow_btn = ttk.Button(
            control_frame,
            text="💾 保存配置",
            command=self.save_workflow,
            state=tk.DISABLED,
            width=15
        )
        self.save_workflow_btn.pack(side=tk.LEFT, padx=5)
        
        self.load_workflow_btn = ttk.Button(
            control_frame,
            text="📂 加载配置",
            command=self.load_workflow,
            width=15,
            state=tk.DISABLED
        )
        self.load_workflow_btn.pack(side=tk.LEFT, padx=5)
        
        self.monitor_status = ttk.Label(control_frame, text="⚪ 未监控")
        self.monitor_status.pack(side=tk.LEFT, padx=20)
        
        # 捕获状态
        status_frame = ttk.Frame(monitor_section)
        status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(status_frame, text="工作流状态:").pack(side=tk.LEFT, padx=5)
        self.workflow_status = ttk.Label(status_frame, text="❌ 未就绪", foreground="red")
        self.workflow_status.pack(side=tk.LEFT)
        
        self.workflow_name_var = tk.StringVar()
        ttk.Label(status_frame, textvariable=self.workflow_name_var, foreground="blue").pack(side=tk.LEFT, padx=10)
        
        # 自定义输出路径
        output_path_frame = ttk.Frame(monitor_section)
        output_path_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(output_path_frame, text="📁 输出路径:").pack(side=tk.LEFT, padx=5)
        self.custom_output_path = tk.StringVar(value="生成结果")
        self.output_path_entry = ttk.Entry(output_path_frame, textvariable=self.custom_output_path, width=60)
        self.output_path_entry.pack(side=tk.LEFT, padx=5)
        self.output_path_btn = ttk.Button(output_path_frame, text="选择文件夹", command=self.select_output_folder, width=12)
        self.output_path_btn.pack(side=tk.LEFT, padx=5)
        
        # ===== 第二部分：批量模式选择 =====
        batch_section = ttk.LabelFrame(self.root, text="🎯 第二步：选择批量模式", padding=10)
        batch_section.pack(fill=tk.X, padx=10, pady=5)
        
        self.mode_var = tk.StringVar(value="original")
        
        # 批量生成模式
        original_frame = ttk.Frame(batch_section)
        original_frame.pack(fill=tk.X, pady=5)
        
        self.original_radio = ttk.Radiobutton(
            original_frame,
            text="批量生成",
            variable=self.mode_var,
            value="original",
            state=tk.DISABLED
        )
        self.original_radio.pack(side=tk.LEFT)
        
        ttk.Label(original_frame, text="生成数量:", foreground="gray").pack(side=tk.LEFT, padx=(20, 5))
        self.original_repeat_entry = ttk.Entry(original_frame, width=5, state=tk.DISABLED)
        self.original_repeat_entry.insert(0, "5")
        self.original_repeat_entry.pack(side=tk.LEFT)
        ttk.Label(original_frame, text="次 (不改参数/图片/种子,纯重复,comfyui通用)", foreground="gray", font=("", 8)).pack(side=tk.LEFT, padx=5)
        
        # 单图处理模式
        single_frame = ttk.Frame(batch_section)
        single_frame.pack(fill=tk.X, pady=5)
        
        self.single_radio = ttk.Radiobutton(
            single_frame,
            text="单图处理模式",
            variable=self.mode_var,
            value="single",
            state=tk.DISABLED
        )
        self.single_radio.pack(side=tk.LEFT)
        
        self.single_image_var = tk.StringVar()
        self.single_image_entry = ttk.Entry(single_frame, textvariable=self.single_image_var, width=35, state=tk.DISABLED)
        self.single_image_entry.pack(side=tk.LEFT, padx=(20, 5))
        
        self.single_select_btn = ttk.Button(single_frame, text="选择图片", command=self.select_single_image, state=tk.DISABLED)
        self.single_select_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(single_frame, text="生成数量:").pack(side=tk.LEFT, padx=(10, 5))
        self.single_repeat_entry = ttk.Entry(single_frame, width=5, state=tk.DISABLED)
        self.single_repeat_entry.insert(0, "1")
        self.single_repeat_entry.pack(side=tk.LEFT)
        ttk.Label(single_frame, text="次").pack(side=tk.LEFT)
        
        # 文件夹批处理模式
        folder_frame = ttk.Frame(batch_section)
        folder_frame.pack(fill=tk.X, pady=5)
        
        self.folder_radio = ttk.Radiobutton(
            folder_frame,
            text="文件夹批处理",
            variable=self.mode_var,
            value="folder",
            state=tk.DISABLED
        )
        self.folder_radio.pack(side=tk.LEFT)
        
        self.folder_path = tk.StringVar()
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_path, width=35, state=tk.DISABLED)
        self.folder_entry.pack(side=tk.LEFT, padx=(20, 5))
        
        self.folder_btn = ttk.Button(folder_frame, text="选择文件夹", command=self.select_folder, state=tk.DISABLED)
        self.folder_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(folder_frame, text="每张生成:").pack(side=tk.LEFT, padx=(10, 5))
        self.folder_repeat_entry = ttk.Entry(folder_frame, width=5, state=tk.DISABLED)
        self.folder_repeat_entry.insert(0, "1")
        self.folder_repeat_entry.pack(side=tk.LEFT)
        ttk.Label(folder_frame, text="次").pack(side=tk.LEFT)
        
        # V3新增：双图融合模式
        dual_frame = ttk.Frame(batch_section)
        dual_frame.pack(fill=tk.X, pady=5)
        
        self.dual_radio = ttk.Radiobutton(
            dual_frame,
            text="双图融合",
            variable=self.mode_var,
            value="dual_fusion",
            state=tk.DISABLED
        )
        self.dual_radio.pack(side=tk.LEFT)
        
        self.dual_image_a_var = tk.StringVar()
        ttk.Label(dual_frame, text="图片1:").pack(side=tk.LEFT, padx=(20, 5))
        self.dual_image_a_entry = ttk.Entry(dual_frame, textvariable=self.dual_image_a_var, width=20, state=tk.DISABLED)
        self.dual_image_a_entry.pack(side=tk.LEFT, padx=2)
        self.dual_a_btn = ttk.Button(dual_frame, text="选择", command=lambda: self.select_fusion_image('A'), state=tk.DISABLED, width=8)
        self.dual_a_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(dual_frame, text="图片2:").pack(side=tk.LEFT, padx=(10, 5))
        self.dual_image_b_var = tk.StringVar()
        self.dual_image_b_entry = ttk.Entry(dual_frame, textvariable=self.dual_image_b_var, width=20, state=tk.DISABLED)
        self.dual_image_b_entry.pack(side=tk.LEFT, padx=2)
        self.dual_b_btn = ttk.Button(dual_frame, text="选择", command=lambda: self.select_fusion_image('B'), state=tk.DISABLED, width=8)
        self.dual_b_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(dual_frame, text="生成:").pack(side=tk.LEFT, padx=(10, 5))
        self.dual_repeat_entry = ttk.Entry(dual_frame, width=5, state=tk.DISABLED)
        self.dual_repeat_entry.insert(0, "1")
        self.dual_repeat_entry.pack(side=tk.LEFT)
        ttk.Label(dual_frame, text="次").pack(side=tk.LEFT)
        
        # V3新增：单图+文件夹融合
        sf_fusion_frame = ttk.Frame(batch_section)
        sf_fusion_frame.pack(fill=tk.X, pady=5)
        
        self.sf_fusion_radio = ttk.Radiobutton(
            sf_fusion_frame,
            text="单图+文件夹融合",
            variable=self.mode_var,
            value="single_folder_fusion",
            state=tk.DISABLED
        )
        self.sf_fusion_radio.pack(side=tk.LEFT)
        
        self.sf_image_var = tk.StringVar()
        ttk.Label(sf_fusion_frame, text="单图:").pack(side=tk.LEFT, padx=(20, 5))
        self.sf_image_entry = ttk.Entry(sf_fusion_frame, textvariable=self.sf_image_var, width=25, state=tk.DISABLED)
        self.sf_image_entry.pack(side=tk.LEFT, padx=2)
        self.sf_image_btn = ttk.Button(sf_fusion_frame, text="选择图片", command=self.select_sf_image, state=tk.DISABLED, width=10)
        self.sf_image_btn.pack(side=tk.LEFT, padx=2)
        
        self.sf_folder_var = tk.StringVar()
        ttk.Label(sf_fusion_frame, text="文件夹:").pack(side=tk.LEFT, padx=(10, 5))
        self.sf_folder_entry = ttk.Entry(sf_fusion_frame, textvariable=self.sf_folder_var, width=25, state=tk.DISABLED)
        self.sf_folder_entry.pack(side=tk.LEFT, padx=2)
        self.sf_folder_btn = ttk.Button(sf_fusion_frame, text="选择文件夹", command=self.select_sf_folder, state=tk.DISABLED, width=10)
        self.sf_folder_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(sf_fusion_frame, text="每组:").pack(side=tk.LEFT, padx=(10, 5))
        self.sf_repeat_entry = ttk.Entry(sf_fusion_frame, width=5, state=tk.DISABLED)
        self.sf_repeat_entry.insert(0, "1")
        self.sf_repeat_entry.pack(side=tk.LEFT)
        ttk.Label(sf_fusion_frame, text="次").pack(side=tk.LEFT)
        
        # V3新增：文件夹交叉融合
        fc_fusion_frame = ttk.Frame(batch_section)
        fc_fusion_frame.pack(fill=tk.X, pady=5)
        
        self.fc_fusion_radio = ttk.Radiobutton(
            fc_fusion_frame,
            text="文件夹交叉融合",
            variable=self.mode_var,
            value="folder_cross_fusion",
            state=tk.DISABLED
        )
        self.fc_fusion_radio.pack(side=tk.LEFT)
        
        self.fc_folder_a_var = tk.StringVar()
        ttk.Label(fc_fusion_frame, text="文件夹1:").pack(side=tk.LEFT, padx=(20, 5))
        self.fc_folder_a_entry = ttk.Entry(fc_fusion_frame, textvariable=self.fc_folder_a_var, width=30, state=tk.DISABLED)
        self.fc_folder_a_entry.pack(side=tk.LEFT, padx=2)
        self.fc_folder_a_btn = ttk.Button(fc_fusion_frame, text="选择", command=lambda: self.select_fc_folder('A'), state=tk.DISABLED, width=8)
        self.fc_folder_a_btn.pack(side=tk.LEFT, padx=2)
        
        self.fc_folder_b_var = tk.StringVar()
        ttk.Label(fc_fusion_frame, text="文件夹2:").pack(side=tk.LEFT, padx=(10, 5))
        self.fc_folder_b_entry = ttk.Entry(fc_fusion_frame, textvariable=self.fc_folder_b_var, width=30, state=tk.DISABLED)
        self.fc_folder_b_entry.pack(side=tk.LEFT, padx=2)
        self.fc_folder_b_btn = ttk.Button(fc_fusion_frame, text="选择", command=lambda: self.select_fc_folder('B'), state=tk.DISABLED, width=8)
        self.fc_folder_b_btn.pack(side=tk.LEFT, padx=2)
        
        # ===== 第三部分：执行控制 =====
        exec_section = ttk.LabelFrame(self.root, text="▶️ 第三步：开始批量执行", padding=10)
        exec_section.pack(fill=tk.X, padx=10, pady=5)
        
        exec_control_frame = ttk.Frame(exec_section)
        exec_control_frame.pack(fill=tk.X)
        
        self.start_batch_btn = ttk.Button(
            exec_control_frame,
            text="▶️ 开始批量",
            command=self.start_batch,
            state=tk.DISABLED,
            width=15
        )
        self.start_batch_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = ttk.Button(
            exec_control_frame,
            text="⏸️ 暂停",
            command=self.toggle_pause,
            state=tk.DISABLED,
            width=15
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(
            exec_control_frame,
            text="⏹️ 停止",
            command=self.stop_batch,
            state=tk.DISABLED,
            width=15
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.open_folder_btn = ttk.Button(
            exec_control_frame,
            text="📁 打开结果文件夹",
            command=self.open_result_folder,
            state=tk.DISABLED
        )
        self.open_folder_btn.pack(side=tk.RIGHT, padx=5)
        
        # 进度显示
        progress_frame = ttk.Frame(exec_section)
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X)
        
        self.progress_label = ttk.Label(progress_frame, text="等待开始...")
        self.progress_label.pack(anchor=tk.W, pady=2)
        
        # ===== 日志区域 =====
        log_frame = ttk.LabelFrame(self.root, text="📝 执行日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=12,
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 配置日志颜色
        self.log_text.tag_config("info", foreground="black")
        self.log_text.tag_config("success", foreground="green")
        self.log_text.tag_config("warning", foreground="orange")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("header", foreground="blue", font=("Consolas", 9, "bold"))
        
        # 初始化日志
        self.log("✨ 流程监控 + 批量执行 一体化工具 V3 已启动", "success")
        self.log("", "info")
        self.log("📋 使用步骤:", "header")
        self.log("  0️⃣ 点击'探测可用端口'，选择ComfyUI端口，点击'确认端口'", "info")
        self.log("  1️⃣ 监控模式：点击'开始监控'，在ComfyUI完成一次生图，点击'停止监控'，然后'保存配置'", "info")
        self.log("  1️⃣ 加载模式：直接点击'加载配置'，选择之前保存的配置文件", "info")
        self.log("  2️⃣ 选择批量模式：单图处理（处理指定图片N次）或 文件夹批处理", "info")
        self.log("  3️⃣ 点击'开始批量'执行", "info")
        self.log("", "info")
        
    def log(self, message, level="info"):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_message, level)
        self.log_text.see(tk.END)
        
        # 同时写入日志文件
        if self.log_file:
            try:
                self.log_file.write(log_message)
                self.log_file.flush()
            except:
                pass
    
    def detect_ports(self):
        """探测可用的ComfyUI端口"""
        self.log("🔍 开始探测ComfyUI端口...", "info")
        available_ports = []
        
        for port in range(8187, 8200):
            try:
                url = f"http://127.0.0.1:{port}/system_stats"
                response = requests.get(url, timeout=1)
                if response.status_code == 200:
                    available_ports.append(str(port))
                    self.log(f"  ✓ 发现端口 {port}", "success")
            except:
                pass
        
        if available_ports:
            self.port_combo['values'] = available_ports
            self.port_var.set(available_ports[0])
            self.log(f"✅ 发现 {len(available_ports)} 个可用端口", "success")
        else:
            self.log("❌ 未发现可用的ComfyUI端口，请确保ComfyUI正在运行", "error")
            
    def confirm_port(self):
        """确认选择的端口"""
        try:
            self.port = int(self.port_var.get())
            self.comfyui_url = f"http://127.0.0.1:{self.port}"
            
            # 测试连接
            response = requests.get(f"{self.comfyui_url}/system_stats", timeout=2)
            if response.status_code == 200:
                self.capture = ExecutionFlowCapture(self.port)
                self.simulator = FlowSimulator(self.port)
                
                self.port_status.config(text=f"✅ 端口 {self.port}", foreground="green")
                self.log(f"✅ 已连接到 ComfyUI 端口 {self.port}", "success")
                
                # 启用功能
                self.start_monitor_btn.config(state=tk.NORMAL)
                self.load_workflow_btn.config(state=tk.NORMAL)
                self.detect_btn.config(state=tk.DISABLED)
                self.confirm_port_btn.config(state=tk.DISABLED)
                self.port_combo.config(state=tk.DISABLED)
            else:
                raise Exception("无法连接")
        except Exception as e:
            messagebox.showerror("错误", f"无法连接到端口 {self.port_var.get()}\n{e}")
            self.log(f"❌ 连接失败: {e}", "error")
    
    def start_monitoring(self):
        """开始监控"""
        if self.is_monitoring or not self.capture:
            return
            
        self.is_monitoring = True
        self.start_monitor_btn.config(state=tk.DISABLED)
        self.stop_monitor_btn.config(state=tk.NORMAL)
        self.monitor_status.config(text="🟢 监控中...", foreground="green")
        
        self.log("=" * 60, "header")
        self.log("🔍 开始监控后台执行流程", "header")
        self.log("=" * 60, "header")
        self.log("提示: 现在请在原界面完成一次完整的生图操作", "info")
        self.log("", "info")
        
        # 重置数据
        self.capture.api_calls = []
        self.capture.execution_steps = []
        self.capture.workflow_data = None
        self.captured_workflow = None
        
        # 启动监控
        threading.Thread(target=self._monitoring_loop, daemon=True).start()
        self._update_monitor_status()
        
    # V3新增：融合模式UI控制函数
    def select_fusion_image(self, image_type):
        """选择融合图片A或B"""
        filepath = filedialog.askopenfilename(
            title=f"选择图片{image_type}",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.webp *.bmp"), ("所有文件", "*.*")]
        )
        if filepath:
            if image_type == 'A':
                self.dual_image_a_var.set(os.path.basename(filepath))
                self.dual_image_a_path = filepath
            else:
                self.dual_image_b_var.set(os.path.basename(filepath))
                self.dual_image_b_path = filepath
    
    def select_sf_image(self):
        """选择单图+文件夹融合的单图"""
        filepath = filedialog.askopenfilename(
            title="选择单张图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.webp *.bmp"), ("所有文件", "*.*")]
        )
        if filepath:
            self.sf_image_var.set(os.path.basename(filepath))
            self.sf_image_path = filepath
    
    def select_sf_folder(self):
        """选择单图+文件夹融合的文件夹"""
        folderpath = filedialog.askdirectory(title="选择图片文件夹")
        if folderpath:
            self.sf_folder_var.set(os.path.basename(folderpath))
            self.sf_folder_path = folderpath
    
    def select_fc_folder(self, folder_type):
        """选择文件夹交叉融合的文件夹A或B"""
        folderpath = filedialog.askdirectory(title=f"选择文件夹{folder_type}")
        if folderpath:
            if folder_type == 'A':
                self.fc_folder_a_var.set(os.path.basename(folderpath))
                self.fc_folder_a_path = folderpath
            else:
                self.fc_folder_b_var.set(os.path.basename(folderpath))
                self.fc_folder_b_path = folderpath
    
    def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            return
            
        self.is_monitoring = False
        self.capture.monitoring = False
        
        self.start_monitor_btn.config(state=tk.NORMAL)
        self.stop_monitor_btn.config(state=tk.DISABLED)
        self.monitor_status.config(text="⚪ 未监控", foreground="black")
        
        self.log("", "info")
        self.log("⏹️ 停止监控", "warning")
        
        # 检查是否捕获到工作流
        if self.capture.workflow_data:
            self.captured_workflow = self.capture.workflow_data
            self.workflow_status.config(text="✅ 已捕获工作流", foreground="green")
            self.workflow_name_var.set("(新捕获)")
            
            node_count = len(self.captured_workflow) if isinstance(self.captured_workflow, dict) else 0
            self.log("", "info")
            self.log("✅ 成功捕获工作流！", "success")
            self.log(f"  节点数量: {node_count}", "info")
            self.log("  请点击'保存配置'保存到本地，或直接选择批量模式处理", "info")
            self.log("", "info")
            
            # 启用功能
            self.save_workflow_btn.config(state=tk.NORMAL)
            self.enable_batch_controls()
            
            messagebox.showinfo(
                "捕获成功",
                f"✅ 已成功捕获完整的生图流程！\n\n"
                f"节点数量: {node_count}\n\n"
                f"建议点击'保存配置'保存，以便下次直接加载使用。"
            )
        else:
            self.log("⚠️ 未捕获到工作流，请确保在监控期间完成了生图操作", "warning")
    
    def save_workflow(self):
        """保存工作流配置"""
        if not self.captured_workflow:
            messagebox.showwarning("警告", "没有可保存的工作流")
            return
        
        filename = filedialog.asksaveasfilename(
            title="保存工作流配置",
            initialdir="saved_workflows",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        
        if filename:
            try:
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump({
                        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "port": self.port,
                        "workflow": self.captured_workflow,
                        "node_count": len(self.captured_workflow) if isinstance(self.captured_workflow, dict) else 0,
                        "metadata": {
                            "tool": "integrated_monitor_batch_v3",
                            "version": "3.0"
                        }
                    }, f, indent=2, ensure_ascii=False)
                
                self.workflow_name_var.set(f"({os.path.basename(filename)})")
                self.log(f"💾 配置已保存: {filename}", "success")
                messagebox.showinfo("成功", f"配置已保存到:\n{filename}")
            except Exception as e:
                self.log(f"❌ 保存失败: {e}", "error")
                messagebox.showerror("错误", f"保存失败:\n{e}")
    
    def load_workflow(self):
        """加载工作流配置"""
        filename = filedialog.askopenfilename(
            title="加载工作流配置",
            initialdir="saved_workflows",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                self.captured_workflow = data.get("workflow")
                if self.captured_workflow:
                    self.workflow_status.config(text="✅ 已加载配置", foreground="green")
                    self.workflow_name_var.set(f"({os.path.basename(filename)})")
                    
                    node_count = data.get("node_count", 0)
                    saved_at = data.get("saved_at", "未知")
                    
                    self.log(f"📂 配置已加载: {os.path.basename(filename)}", "success")
                    self.log(f"  保存时间: {saved_at}", "info")
                    self.log(f"  节点数量: {node_count}", "info")
                    
                    self.save_workflow_btn.config(state=tk.NORMAL)
                    self.enable_batch_controls()
                    
                    messagebox.showinfo("成功", f"配置已加载！\n\n节点数量: {node_count}\n保存时间: {saved_at}")
                else:
                    raise Exception("配置文件格式错误")
            except Exception as e:
                self.log(f"❌ 加载失败: {e}", "error")
                messagebox.showerror("错误", f"加载失败:\n{e}")
    
    def _monitoring_loop(self):
        """监控循环"""
        self.capture.monitoring = True
        last_history_check = {}
        
        while self.is_monitoring:
            try:
                self.capture._check_queue()
                self.capture._check_history(last_history_check)
                time.sleep(0.5)
            except Exception as e:
                self.root.after(0, lambda: self.log(f"监控错误: {e}", "error"))
                
    def _update_monitor_status(self):
        """更新监控状态"""
        if self.is_monitoring:
            if self.capture.workflow_data and not self.captured_workflow:
                node_count = len(self.capture.workflow_data) if isinstance(self.capture.workflow_data, dict) else 0
                self.log(f"✓ 捕获到工作流 (节点数: {node_count})", "success")
            self.root.after(500, self._update_monitor_status)
            
    def enable_batch_controls(self):
        """启用批量控制"""
        self.original_radio.config(state=tk.NORMAL)
        self.original_repeat_entry.config(state=tk.NORMAL)
        
        self.single_radio.config(state=tk.NORMAL)
        self.single_image_entry.config(state=tk.NORMAL)
        self.single_select_btn.config(state=tk.NORMAL)
        self.single_repeat_entry.config(state=tk.NORMAL)
        
        self.folder_radio.config(state=tk.NORMAL)
        self.folder_entry.config(state=tk.NORMAL)
        self.folder_btn.config(state=tk.NORMAL)
        self.folder_repeat_entry.config(state=tk.NORMAL)
        
        # V3新增：启用融合模式
        self.dual_radio.config(state=tk.NORMAL)
        self.sf_fusion_radio.config(state=tk.NORMAL)
        self.fc_fusion_radio.config(state=tk.NORMAL)
        self.dual_a_btn.config(state=tk.NORMAL)
        self.dual_b_btn.config(state=tk.NORMAL)
        self.sf_image_btn.config(state=tk.NORMAL)
        self.sf_folder_btn.config(state=tk.NORMAL)
        self.fc_folder_a_btn.config(state=tk.NORMAL)
        self.fc_folder_b_btn.config(state=tk.NORMAL)
        self.dual_repeat_entry.config(state=tk.NORMAL)
        self.sf_repeat_entry.config(state=tk.NORMAL)
        self.dual_image_a_entry.config(state=tk.NORMAL)
        self.dual_image_b_entry.config(state=tk.NORMAL)
        self.sf_image_entry.config(state=tk.NORMAL)
        self.sf_folder_entry.config(state=tk.NORMAL)
        self.fc_folder_a_entry.config(state=tk.NORMAL)
        self.fc_folder_b_entry.config(state=tk.NORMAL)
        
        self.start_batch_btn.config(state=tk.NORMAL)
    
    def select_single_image(self):
        """选择单张图片"""
        filename = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[
                ("图片文件", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("所有文件", "*.*")
            ]
        )
        if filename:
            self.single_image_var.set(filename)
        
    def select_folder(self):
        """选择文件夹"""
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)
    
    def select_output_folder(self):
        """选择自定义输出路径"""
        folder = filedialog.askdirectory(title="选择输出路径")
        if folder:
            self.custom_output_path.set(folder)
            
    def start_batch(self):
        """开始批量处理"""
        if not self.captured_workflow:
            messagebox.showwarning("警告", "请先监控并捕获流程，或加载已保存的配置")
            return
            
        mode = self.mode_var.get()
        
        if mode == "original":
            try:
                repeat_count = int(self.original_repeat_entry.get())
                if repeat_count <= 0:
                    messagebox.showerror("错误", "执行次数必须大于0")
                    return
            except ValueError:
                messagebox.showerror("错误", "请输入有效的执行次数")
                return
            
            # 提示用户
            result = messagebox.showinfo(
                "���量生成模式",
                f"⚠️ 批量生成模式说明：\n\n"
                f"此模式会将当前workflow完全不变地重复执行 {repeat_count} 次。\n\n"
                f"所有参数（图片、提示词、种子等）都与原workflow相同。\n"
                f"仅生成数量增加，适用于多图融合、复杂流程等场景。\n\n"
                f"确定继续？"
            )
            
            self.start_batch_processing("批量生成", lambda: self.batch_generate(repeat_count))
            
        elif mode == "single":
            image_path = self.single_image_var.get()
            if not image_path or not os.path.exists(image_path):
                messagebox.showerror("错误", "请选择有效的图片文件")
                return
                
            try:
                repeat_count = int(self.single_repeat_entry.get())
                if repeat_count <= 0:
                    messagebox.showerror("错误", "处理次数必须大于0")
                    return
            except ValueError:
                messagebox.showerror("错误", "请输入有效的处理次数")
                return
                
            self.start_batch_processing("单图处理", lambda: self.batch_single(image_path, repeat_count))
            
        elif mode == "folder":
            folder = self.folder_path.get()
            if not folder or not os.path.exists(folder):
                messagebox.showerror("错误", "请选择有效的文件夹")
                return
                
            try:
                repeat_per_image = int(self.folder_repeat_entry.get())
                if repeat_per_image <= 0:
                    messagebox.showerror("错误", "每张重复次数必须大于0")
                    return
            except ValueError:
                messagebox.showerror("错误", "请输入有效的重复次数")
                return
                
            self.start_batch_processing("文件夹批处理", lambda: self.batch_folder(folder, repeat_per_image))
            
        elif mode == "dual_fusion":
            # 双图融合模式
            if not hasattr(self, 'dual_image_a_path') or not hasattr(self, 'dual_image_b_path'):
                messagebox.showerror("错误", "请选择图片A和图片B")
                return
            
            if not os.path.exists(self.dual_image_a_path) or not os.path.exists(self.dual_image_b_path):
                messagebox.showerror("错误", "请选择有效的图片文件")
                return
            
            try:
                repeat_count = int(self.dual_repeat_entry.get())
                if repeat_count <= 0:
                    messagebox.showerror("错误", "生成次数必须大于0")
                    return
            except ValueError:
                messagebox.showerror("错误", "请输入有效的生成次数")
                return
            
            # 验证workflow是否支持融合
            if not self.validate_fusion_workflow(self.captured_workflow):
                return
            
            self.start_batch_processing("双图融合", lambda: self.batch_dual_fusion(
                self.dual_image_a_path, self.dual_image_b_path, repeat_count))
            
        elif mode == "single_folder_fusion":
            # 单图+文件夹融合模式
            if not hasattr(self, 'sf_image_path') or not hasattr(self, 'sf_folder_path'):
                messagebox.showerror("错误", "请选择单图和文件夹")
                return
            
            if not os.path.exists(self.sf_image_path) or not os.path.exists(self.sf_folder_path):
                messagebox.showerror("错误", "请选择有效的文件和文件夹")
                return
            
            try:
                repeat_per_pair = int(self.sf_repeat_entry.get())
                if repeat_per_pair <= 0:
                    messagebox.showerror("错误", "每组生成次数必须大于0")
                    return
            except ValueError:
                messagebox.showerror("错误", "请输入有效的生成次数")
                return
            
            # 验证workflow是否支持融合
            if not self.validate_fusion_workflow(self.captured_workflow):
                return
            
            self.start_batch_processing("单图+文件夹融合", lambda: self.batch_single_folder_fusion(
                self.sf_image_path, self.sf_folder_path, repeat_per_pair))
            
        elif mode == "folder_cross_fusion":
            # 文件夹交叉融合模式
            if not hasattr(self, 'fc_folder_a_path') or not hasattr(self, 'fc_folder_b_path'):
                messagebox.showerror("错误", "请选择文件夹A和文件夹B")
                return
            
            if not os.path.exists(self.fc_folder_a_path) or not os.path.exists(self.fc_folder_b_path):
                messagebox.showerror("错误", "请选择有效的文件夹")
                return
            
            # 验证workflow是否支持融合
            if not self.validate_fusion_workflow(self.captured_workflow):
                return
            
            self.start_batch_processing("文件夹交叉融合", lambda: self.batch_folder_cross_fusion(
                self.fc_folder_a_path, self.fc_folder_b_path))
            
    def start_batch_processing(self, mode_name, process_func):
        """启动批量处理"""
        self.stopped = False
        self.paused = False
        self.is_processing = True
        
        # 创建结果文件夹（使用自定义输出路径）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_output_path = self.custom_output_path.get() or "生成结果"
        self.current_batch_folder = os.path.join(base_output_path, f"{mode_name}_{timestamp}")
        os.makedirs(self.current_batch_folder, exist_ok=True)
        
        # 创建日志文件
        self.log_file_path = os.path.join(self.current_batch_folder, "执行日志.txt")
        try:
            self.log_file = open(self.log_file_path, "w", encoding="utf-8")
            self.log_file.write("=" * 80 + "\n")
            self.log_file.write(f"流程监控 + 批量执行 一体化工具 V3 - 执行日志\n")
            self.log_file.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.log_file.write(f"ComfyUI端口: {self.port}\n")
            self.log_file.write(f"批量模式: {mode_name}\n")
            self.log_file.write("=" * 80 + "\n\n")
            self.log_file.flush()
        except Exception as e:
            self.log(f"⚠️ 无法创建日志文件: {e}", "warning")
        
        # 保存使用的workflow到结果文件夹
        if self.captured_workflow:
            try:
                workflow_file = os.path.join(self.current_batch_folder, "使用的workflow.json")
                with open(workflow_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "workflow": self.captured_workflow,
                        "batch_mode": mode_name,
                        "port": self.port,
                        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }, f, indent=2, ensure_ascii=False)
                self.log(f"💾 工作流已保存到结果文件夹", "info")
            except Exception as e:
                self.log(f"⚠️ 保存工作流失败: {e}", "warning")
        
        # 更新按钮状态
        self.start_batch_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.open_folder_btn.config(state=tk.NORMAL)
        
        # 启动处理线程
        self.processing_thread = threading.Thread(target=process_func, daemon=True)
        self.processing_thread.start()
    
    def batch_generate(self, repeat_count):
        """批量生成模式 - 每次随机种子独立生成"""
        self.root.after(0, lambda: self.log(f"📁 结果将保存至: {self.current_batch_folder}", "info"))
        self.root.after(0, lambda: self.log(f"开始批量生成模式 - 执行 {repeat_count} 次", "info"))
        self.root.after(0, lambda: self.log("✨ 每次使用不同的随机种子，确保独立生成", "info"))
        self.root.after(0, lambda: self.log("", "info"))

        success_count = 0
        fail_count = 0
        self.failed_tasks = []  # 重置失败任务列表

        for i in range(repeat_count):
            if self.stopped:
                self.root.after(0, lambda: self.log("❌ 已停止", "warning"))
                break

            while self.paused:
                time.sleep(0.5)
                if self.stopped:
                    break

            if self.stopped:
                break

            progress = (i / repeat_count) * 100
            self.root.after(0, lambda p=progress: self.progress_var.set(p))
            self.root.after(0, lambda i=i, n=repeat_count: self.progress_label.config(text=f"正在执行第 {i+1}/{n} 次"))

            self.root.after(0, lambda i=i, n=repeat_count: self.log(f"第 {i+1}/{n} 次:", "info"))

            # ✨ 关键修改：每次都更新随机种子，确保独立生成
            workflow = self.update_seed(self.captured_workflow)
            
            # 提交任务
            success, prompt_id = self.queue_prompt(workflow)
            
            if success:
                self.root.after(0, lambda: self.log(f"  ✓ 任务已提交，等待生成...", "info"))
                if self.wait_for_completion(prompt_id):
                    self.root.after(0, lambda: self.log(f"  ✅ 生成完成", "success"))
                    success_count += 1
                else:
                    if not self.stopped:
                        self.root.after(0, lambda i=i: self.log(f"  ❌ 生成超时", "error"))
                        self.failed_tasks.append((i+1, "original", None))  # 记录失败任务
                        fail_count += 1
            else:
                self.root.after(0, lambda i=i: self.log(f"  ❌ 提交失败", "error"))
                self.failed_tasks.append((i+1, "original", None))  # 记录失败任务
                fail_count += 1
                
            if i < repeat_count - 1 and not self.stopped:
                time.sleep(2)
                
        self.finish_batch_processing(success_count, fail_count)
    
    def batch_single(self, image_path, repeat_count):
        """单图处理模式"""
        filename = os.path.basename(image_path)
        
        self.root.after(0, lambda: self.log(f"📁 结果将保存至: {self.current_batch_folder}", "info"))
        self.root.after(0, lambda: self.log(f"开始单图处理模式", "info"))
        self.root.after(0, lambda: self.log(f"  图片: {filename}", "info"))
        self.root.after(0, lambda: self.log(f"  生成数量: {repeat_count}", "info"))
        self.root.after(0, lambda: self.log("", "info"))
        
        # 上传图片到ComfyUI
        self.root.after(0, lambda: self.log("📤 上传图片到ComfyUI...", "info"))
        upload_success = self.upload_image(image_path)
        if not upload_success:
            self.root.after(0, lambda: self.log(f"❌ 上传图片失败，无法继续", "error"))
            self.finish_batch_processing(0, repeat_count)
            return
        
        self.root.after(0, lambda: self.log("✅ 图片上传成功", "success"))
        self.root.after(0, lambda: self.log("", "info"))
        
        success_count = 0
        fail_count = 0
        
        for i in range(repeat_count):
            if self.stopped:
                self.root.after(0, lambda: self.log("❌ 已停止", "warning"))
                break
                
            while self.paused:
                time.sleep(0.5)
                if self.stopped:
                    break
                    
            if self.stopped:
                break
                
            progress = (i / repeat_count) * 100
            self.root.after(0, lambda p=progress: self.progress_var.set(p))
            self.root.after(0, lambda i=i, n=repeat_count: self.progress_label.config(text=f"正在处理第 {i+1}/{n} 次"))
            
            self.root.after(0, lambda i=i, n=repeat_count: self.log(f"第 {i+1}/{n} 次:", "info"))
            
            # 更新图片和种子
            workflow = self.update_image(self.captured_workflow, filename)
            workflow = self.update_seed(workflow)
            
            # 提交任务
            success, prompt_id = self.queue_prompt(workflow)
            
            if success:
                self.root.after(0, lambda: self.log(f"  ✓ 任务已提交，等待生成...", "info"))
                if self.wait_for_completion(prompt_id):
                    self.root.after(0, lambda: self.log(f"  ✅ 生成完成", "success"))
                    success_count += 1
                else:
                    if not self.stopped:
                        self.root.after(0, lambda: self.log(f"  ❌ 生成超时", "error"))
                        fail_count += 1
            else:
                self.root.after(0, lambda: self.log(f"  ❌ 提交失败", "error"))
                fail_count += 1
                
            if i < repeat_count - 1 and not self.stopped:
                time.sleep(2)
                
        self.finish_batch_processing(success_count, fail_count)
        
    def batch_folder(self, folder_path, repeat_per_image):
        """文件夹批处理模式"""
        self.root.after(0, lambda: self.log(f"📁 结果将保存至: {self.current_batch_folder}", "info"))
        
        # 扫描图片
        supported_formats = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
        image_files = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in sorted(files):
                if Path(file).suffix.lower() in supported_formats:
                    image_files.append(os.path.join(root, file))
                    
        if not image_files:
            self.root.after(0, lambda: self.log("❌ 文件夹中没有找到图像文件", "error"))
            self.finish_batch_processing(0, 0)
            return
            
        self.root.after(0, lambda: self.log(f"✓ 找到 {len(image_files)} 张图像", "info"))
        self.root.after(0, lambda: self.log(f"✓ 每张图片重复 {repeat_per_image} 次", "info"))
        self.root.after(0, lambda: self.log("", "info"))
        
        total_tasks = len(image_files) * repeat_per_image
        current_task = 0
        success_count = 0
        fail_count = 0
        
        for img_idx, img_path in enumerate(image_files):
            if self.stopped:
                break
                
            filename = os.path.basename(img_path)
            self.root.after(0, lambda fn=filename, idx=img_idx, total=len(image_files):
                          self.log(f"图片 {idx+1}/{total}: {fn}", "info"))
            
            # 上传图片到ComfyUI
            upload_success = self.upload_image(img_path)
            if not upload_success:
                self.root.after(0, lambda fn=filename: self.log(f"  ⚠️ 上传图片失败: {fn}，跳过此图片", "error"))
                fail_count += repeat_per_image
                continue
                          
            for repeat_idx in range(repeat_per_image):
                if self.stopped:
                    break
                    
                while self.paused:
                    time.sleep(0.5)
                    if self.stopped:
                        break
                        
                if self.stopped:
                    break
                    
                current_task += 1
                progress = (current_task / total_tasks) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                self.root.after(0, lambda ct=current_task, tt=total_tasks, ri=repeat_idx, rpt=repeat_per_image:
                              self.progress_label.config(text=f"总进度 {ct}/{tt} | 重复 {ri+1}/{rpt}"))
                              
                # 更新图片和种子
                workflow = self.update_image(self.captured_workflow, filename)
                workflow = self.update_seed(workflow)
                
                # 提交任务
                success, prompt_id = self.queue_prompt(workflow)
                
                if success:
                    if self.wait_for_completion(prompt_id):
                        self.root.after(0, lambda: self.log(f"  ✅ 完成", "success"))
                        success_count += 1
                    else:
                        if not self.stopped:
                            self.root.after(0, lambda: self.log(f"  ❌ 超时", "error"))
                            fail_count += 1
                else:
                    self.root.after(0, lambda: self.log(f"  ❌ 失败", "error"))
                    fail_count += 1
                    
                if not self.stopped:
                    time.sleep(2)
                    
        self.finish_batch_processing(success_count, fail_count)
    
    def batch_dual_fusion(self, image_a_path, image_b_path, repeat_count):
        """双图融合模式"""
        self.root.after(0, lambda: self.log(f"📁 结果将保存至: {self.current_batch_folder}", "info"))
        self.root.after(0, lambda: self.log(f"开始双图融合模式", "info"))
        self.root.after(0, lambda: self.log(f"  图片A: {os.path.basename(image_a_path)}", "info"))
        self.root.after(0, lambda: self.log(f"  图片B: {os.path.basename(image_b_path)}", "info"))
        self.root.after(0, lambda: self.log(f"  生成数量: {repeat_count}", "info"))
        self.root.after(0, lambda: self.log("", "info"))
        
        # 上传两张图片
        self.root.after(0, lambda: self.log("📤 上传图片到ComfyUI...", "info"))
        if not self.upload_image(image_a_path):
            self.root.after(0, lambda: self.log(f"❌ 上传图片A失败", "error"))
            self.finish_batch_processing(0, repeat_count)
            return
        if not self.upload_image(image_b_path):
            self.root.after(0, lambda: self.log(f"❌ 上传图片B失败", "error"))
            self.finish_batch_processing(0, repeat_count)
            return
        
        self.root.after(0, lambda: self.log("✅ 图片上传成功", "success"))
        self.root.after(0, lambda: self.log("", "info"))
        
        success_count = 0
        fail_count = 0
        
        for i in range(repeat_count):
            if self.stopped:
                self.root.after(0, lambda: self.log("❌ 已停止", "warning"))
                break
            
            while self.paused:
                time.sleep(0.5)
                if self.stopped:
                    break
            
            if self.stopped:
                break
            
            progress = (i / repeat_count) * 100
            self.root.after(0, lambda p=progress: self.progress_var.set(p))
            self.root.after(0, lambda i=i, n=repeat_count: self.progress_label.config(text=f"正在融合 {i+1}/{n}"))
            
            self.root.after(0, lambda i=i, n=repeat_count: self.log(f"第 {i+1}/{n} 次:", "info"))
            
            # 更新双图和种子
            workflow = self.update_dual_images(
                self.captured_workflow,
                os.path.basename(image_a_path),
                os.path.basename(image_b_path)
            )
            workflow = self.update_seed(workflow)
            
            # 提交任务
            success, prompt_id = self.queue_prompt(workflow)
            
            if success:
                self.root.after(0, lambda: self.log(f"  ✓ 任务已提交，等待生成...", "info"))
                if self.wait_for_completion(prompt_id):
                    self.root.after(0, lambda: self.log(f"  ✅ 融合完成", "success"))
                    success_count += 1
                else:
                    if not self.stopped:
                        self.root.after(0, lambda: self.log(f"  ❌ 生成超时", "error"))
                        fail_count += 1
            else:
                self.root.after(0, lambda: self.log(f"  ❌ 提交失败", "error"))
                fail_count += 1
            
            if i < repeat_count - 1 and not self.stopped:
                time.sleep(2)
        
        self.finish_batch_processing(success_count, fail_count)
    
    def batch_single_folder_fusion(self, single_image_path, folder_path, repeat_per_pair):
        """单图+文件夹融合模式"""
        self.root.after(0, lambda: self.log(f"📁 结果将保存至: {self.current_batch_folder}", "info"))
        self.root.after(0, lambda: self.log(f"开始单图+文件夹融合模式", "info"))
        self.root.after(0, lambda: self.log(f"  单图: {os.path.basename(single_image_path)}", "info"))
        self.root.after(0, lambda: self.log(f"  文件夹: {os.path.basename(folder_path)}", "info"))
        self.root.after(0, lambda: self.log("", "info"))
        
        # 扫描文件夹中的图片
        folder_images = self.scan_images(folder_path)
        if not folder_images:
            self.root.after(0, lambda: self.log("❌ 文件夹中没有找到图像文件", "error"))
            self.finish_batch_processing(0, 0)
            return
        
        self.root.after(0, lambda: self.log(f"✓ 找到 {len(folder_images)} 张图像", "info"))
        self.root.after(0, lambda: self.log(f"✓ 每组融合 {repeat_per_pair} 次", "info"))
        self.root.after(0, lambda: self.log("", "info"))
        
        # 上传单图
        self.root.after(0, lambda: self.log("📤 上传单图到ComfyUI...", "info"))
        if not self.upload_image(single_image_path):
            self.root.after(0, lambda: self.log(f"❌ 上传单图失败", "error"))
            self.finish_batch_processing(0, len(folder_images) * repeat_per_pair)
            return
        
        total_tasks = len(folder_images) * repeat_per_pair
        current_task = 0
        success_count = 0
        fail_count = 0
        
        for img_idx, folder_img_path in enumerate(folder_images):
            if self.stopped:
                break
            
            folder_img_name = os.path.basename(folder_img_path)
            self.root.after(0, lambda fn=folder_img_name, idx=img_idx, total=len(folder_images):
                          self.log(f"文件夹图片 {idx+1}/{total}: {fn}", "info"))
            
            # 上传文件夹图片
            if not self.upload_image(folder_img_path):
                self.root.after(0, lambda fn=folder_img_name: self.log(f"  ⚠️ 上传失败，跳过", "error"))
                fail_count += repeat_per_pair
                continue
            
            for repeat_idx in range(repeat_per_pair):
                if self.stopped:
                    break
                
                while self.paused:
                    time.sleep(0.5)
                    if self.stopped:
                        break
                
                if self.stopped:
                    break
                
                current_task += 1
                progress = (current_task / total_tasks) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                self.root.after(0, lambda ct=current_task, tt=total_tasks:
                              self.progress_label.config(text=f"总进度 {ct}/{tt}"))
                
                # 更新双图和种子
                workflow = self.update_dual_images(
                    self.captured_workflow,
                    os.path.basename(single_image_path),
                    folder_img_name
                )
                workflow = self.update_seed(workflow)
                
                # 提交任务
                success, prompt_id = self.queue_prompt(workflow)
                
                if success:
                    if self.wait_for_completion(prompt_id):
                        self.root.after(0, lambda: self.log(f"  ✅ 完成", "success"))
                        success_count += 1
                    else:
                        if not self.stopped:
                            self.root.after(0, lambda: self.log(f"  ❌ 超时", "error"))
                            fail_count += 1
                else:
                    self.root.after(0, lambda: self.log(f"  ❌ 失败", "error"))
                    fail_count += 1
                
                if not self.stopped:
                    time.sleep(2)
        
        self.finish_batch_processing(success_count, fail_count)
    
    def batch_folder_cross_fusion(self, folder_a_path, folder_b_path):
        """文件夹交叉融合模式"""
        self.root.after(0, lambda: self.log(f"📁 结果将保存至: {self.current_batch_folder}", "info"))
        self.root.after(0, lambda: self.log(f"开始文件夹交叉融合模式", "info"))
        self.root.after(0, lambda: self.log(f"  文件夹A: {os.path.basename(folder_a_path)}", "info"))
        self.root.after(0, lambda: self.log(f"  文件夹B: {os.path.basename(folder_b_path)}", "info"))
        self.root.after(0, lambda: self.log("", "info"))
        
        # 扫描两个文件夹
        images_a = self.scan_images(folder_a_path)
        images_b = self.scan_images(folder_b_path)
        
        if not images_a or not images_b:
            self.root.after(0, lambda: self.log("❌ 至少一个文件夹中没有找到图像文件", "error"))
            self.finish_batch_processing(0, 0)
            return
        
        self.root.after(0, lambda: self.log(f"✓ 文件夹A: {len(images_a)} 张图像", "info"))
        self.root.after(0, lambda: self.log(f"✓ 文件夹B: {len(images_b)} 张图像", "info"))
        self.root.after(0, lambda: self.log(f"✓ 总共将生成: {len(images_a) * len(images_b)} 张融合图", "info"))
        self.root.after(0, lambda: self.log("", "info"))
        
        total_tasks = len(images_a) * len(images_b)
        current_task = 0
        success_count = 0
        fail_count = 0
        
        for a_idx, img_a_path in enumerate(images_a):
            if self.stopped:
                break
            
            img_a_name = os.path.basename(img_a_path)
            
            # 上传图片A
            if not self.upload_image(img_a_path):
                self.root.after(0, lambda fn=img_a_name: self.log(f"⚠️ 上传图片A失败: {fn}，跳过", "error"))
                fail_count += len(images_b)
                continue
            
            for b_idx, img_b_path in enumerate(images_b):
                if self.stopped:
                    break
                
                while self.paused:
                    time.sleep(0.5)
                    if self.stopped:
                        break
                
                if self.stopped:
                    break
                
                img_b_name = os.path.basename(img_b_path)
                current_task += 1
                progress = (current_task / total_tasks) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                self.root.after(0, lambda ct=current_task, tt=total_tasks, an=img_a_name, bn=img_b_name:
                              self.progress_label.config(text=f"进度 {ct}/{tt} | {an} × {bn}"))
                
                self.root.after(0, lambda ct=current_task, tt=total_tasks, an=img_a_name, bn=img_b_name:
                              self.log(f"[{ct}/{tt}] {an} × {bn}", "info"))
                
                # 上传图片B
                if not self.upload_image(img_b_path):
                    self.root.after(0, lambda bn=img_b_name: self.log(f"  ⚠️ 上传图片B失败: {bn}，跳过", "error"))
                    fail_count += 1
                    continue
                
                # 更新双图和种子
                workflow = self.update_dual_images(
                    self.captured_workflow,
                    img_a_name,
                    img_b_name
                )
                workflow = self.update_seed(workflow)
                
                # 提交任务
                success, prompt_id = self.queue_prompt(workflow)
                
                if success:
                    if self.wait_for_completion(prompt_id):
                        self.root.after(0, lambda: self.log(f"  ✅ 完成", "success"))
                        success_count += 1
                    else:
                        if not self.stopped:
                            self.root.after(0, lambda: self.log(f"  ❌ 超时", "error"))
                            fail_count += 1
                else:
                    self.root.after(0, lambda: self.log(f"  ❌ 失败", "error"))
                    fail_count += 1
                
                if not self.stopped:
                    time.sleep(2)
        
        self.finish_batch_processing(success_count, fail_count)
        
    def finish_batch_processing(self, success_count, fail_count):
        """完成批量处理"""
        self.is_processing = False
        
        self.root.after(0, lambda: self.progress_var.set(100))
        self.root.after(0, lambda: self.log("", "info"))
        self.root.after(0, lambda: self.log("=" * 60, "header"))
        self.root.after(0, lambda: self.log("批量处理完成！", "header"))
        self.root.after(0, lambda: self.log("=" * 60, "header"))
        self.root.after(0, lambda: self.log(f"✅ 成功: {success_count} 次", "success"))
        self.root.after(0, lambda: self.log(f"❌ 失败: {fail_count} 次", "error" if fail_count > 0 else "info"))
        self.root.after(0, lambda: self.log(f"📁 结果保存在: {self.current_batch_folder}", "info"))
        
        # 关闭日志文件
        if self.log_file:
            try:
                self.log_file.write("\n" + "=" * 80 + "\n")
                self.log_file.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.log_file.write(f"成功: {success_count} 次\n")
                self.log_file.write(f"失败: {fail_count} 次\n")
                self.log_file.write("=" * 80 + "\n")
                self.log_file.close()
                self.log_file = None
                self.root.after(0, lambda: self.log(f"📝 日志已保存: {self.log_file_path}", "info"))
            except:
                pass
        
        self.root.after(0, lambda: self.start_batch_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.pause_btn.config(state=tk.DISABLED, text="⏸️ 暂停"))
        self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
        
        # 显示完成对话框
        self.root.after(100, lambda: self.show_completion_dialog(success_count, fail_count))
    
    def show_completion_dialog(self, success_count, fail_count):
        """显示完成对话框，询问是否重试失败任务"""
        if fail_count > 0:
            # 有失败任务，询问是否重试
            response = messagebox.askyesno(
                "任务完成",
                f"✅ 批量处理完成！\n\n"
                f"成功: {success_count} 次\n"
                f"失败: {fail_count} 次\n\n"
                f"是否对失败的 {fail_count} 个任务发起补录？"
            )
            
            if response:
                # 用户选择重试
                self.retry_failed_tasks()
            else:
                # 用户选择不重试
                messagebox.showinfo(
                    "流程结束",
                    f"处理完成！\n\n"
                    f"成功: {success_count} 次\n"
                    f"失败: {fail_count} 次\n\n"
                    f"结果已保存到:\n{self.current_batch_folder}"
                )
        else:
            # 全部成功
            messagebox.showinfo(
                "任务完成",
                f"🎉 批量处理全部成功！\n\n"
                f"成功: {success_count} 次\n"
                f"失败: 0 次\n\n"
                f"结果已保存到:\n{self.current_batch_folder}"
            )
    
    def retry_failed_tasks(self):
        """重试失败的任务"""
        if not self.failed_tasks:
            return
        
        self.log("", "info")
        self.log("=" * 60, "header")
        self.log(f"开始补录失败任务 - 共 {len(self.failed_tasks)} 个", "header")
        self.log("=" * 60, "header")
        
        # 重新启动处理
        self.stopped = False
        self.paused = False
        self.is_processing = True
        
        self.start_batch_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        
        # 启动补录线程
        threading.Thread(target=self._retry_failed_tasks_thread, daemon=True).start()
    
    def _retry_failed_tasks_thread(self):
        """补录失败任务的线程"""
        success_count = 0
        fail_count = 0
        total = len(self.failed_tasks)
        retry_failed = []
        
        for idx, (task_num, task_type, task_data) in enumerate(self.failed_tasks):
            if self.stopped:
                self.root.after(0, lambda: self.log("❌ 补录已停止", "warning"))
                break
            
            while self.paused:
                time.sleep(0.5)
                if self.stopped:
                    break
            
            if self.stopped:
                break
            
            progress = ((idx + 1) / total) * 100
            self.root.after(0, lambda p=progress: self.progress_var.set(p))
            self.root.after(0, lambda i=idx, t=total, tn=task_num:
                          self.progress_label.config(text=f"补录进度 {i+1}/{t} | 任务#{tn}"))
            
            self.root.after(0, lambda tn=task_num, i=idx, t=total:
                          self.log(f"补录 {i+1}/{t} - 原任务#{tn}:", "info"))
            
            # 使用原workflow
            workflow = self.captured_workflow
            
            # 提交任务
            success, prompt_id = self.queue_prompt(workflow)
            
            if success:
                if self.wait_for_completion(prompt_id):
                    self.root.after(0, lambda: self.log(f"  ✅ 补录成功", "success"))
                    success_count += 1
                else:
                    if not self.stopped:
                        self.root.after(0, lambda: self.log(f"  ❌ 补录失败", "error"))
                        retry_failed.append((task_num, task_type, task_data))
                        fail_count += 1
            else:
                self.root.after(0, lambda: self.log(f"  ❌ 提交失败", "error"))
                retry_failed.append((task_num, task_type, task_data))
                fail_count += 1
            
            if idx < total - 1 and not self.stopped:
                time.sleep(2)
        
        self.failed_tasks = retry_failed
        
        # 补录完成
        self.root.after(0, lambda: self.progress_var.set(100))
        self.root.after(0, lambda: self.log("", "info"))
        self.root.after(0, lambda: self.log("=" * 60, "header"))
        self.root.after(0, lambda: self.log("补录处理完成！", "header"))
        self.root.after(0, lambda: self.log("=" * 60, "header"))
        self.root.after(0, lambda sc=success_count: self.log(f"✅ 成功: {sc} 次", "success"))
        self.root.after(0, lambda fc=fail_count: self.log(f"❌ 失败: {fc} 次", "error" if fc > 0 else "info"))
        
        self.root.after(0, lambda: self.start_batch_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.pause_btn.config(state=tk.DISABLED, text="⏸️ 暂停"))
        self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
        self.is_processing = False
        
        # 显示最终结果
        if fail_count > 0:
            self.root.after(100, lambda sc=success_count, fc=fail_count:
                          messagebox.showwarning(
                              "补录完成",
                              f"补录完成！\n\n"
                              f"成功: {sc} 次\n"
                              f"失败: {fc} 次\n\n"
                              f"仍有 {fc} 个任务失败，请检查日志。"
                          ))
        else:
            self.root.after(100, lambda sc=success_count:
                          messagebox.showinfo(
                              "补录完成",
                              f"🎉 补录全部成功！\n\n"
                              f"成功: {sc} 次\n"
                              f"失败: 0 次"
                          ))
        
    def toggle_pause(self):
        """暂停/继续"""
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.config(text="▶️ 继续")
            self.log("⏸️ 已暂停", "warning")
        else:
            self.pause_btn.config(text="⏸️ 暂停")
            self.log("▶️ 继续执行", "info")
            
    def stop_batch(self):
        """停止批量"""
        self.stopped = True
        self.log("⏹�� 正在停止...", "warning")
        
    def open_result_folder(self):
        """打开结果文件夹"""
        if self.current_batch_folder and os.path.exists(self.current_batch_folder):
            subprocess.Popen(f'explorer "{self.current_batch_folder}"')
        else:
            if os.path.exists("生成结果"):
                subprocess.Popen(f'explorer "生成结果"')
                
    # ===== 工具函数 =====
    
    def extract_prompt_preview(self, workflow):
        """从工作流中提取提示词预览（前200字符）"""
        if not workflow:
            return "(未捕获工作流)"
        
        prompts = []
        
        try:
            # 遍历所有节点，查找包含text的节点
            for node_id, node_data in workflow.items():
                if isinstance(node_data, dict) and 'inputs' in node_data:
                    inputs = node_data['inputs']
                    
                    # 查找text字段（正面提示词）
                    if 'text' in inputs and isinstance(inputs['text'], str):
                        text = inputs['text'].strip()
                        if text and len(text) > 10:  # 过滤太短的文本
                            prompts.append(('正面', text))
                    
                    # 查找negative字段（负面提示词）
                    if 'negative' in inputs and isinstance(inputs['negative'], str):
                        text = inputs['negative'].strip()
                        if text and len(text) > 10:
                            prompts.append(('负面', text))
            
            if not prompts:
                return "(未检测到提示词)"
            
            # 组合提示词，只取第一个正面提示词
            result = ""
            for prompt_type, prompt_text in prompts:
                if prompt_type == '正面':
                    # 只显示前200字符
                    preview = prompt_text[:200]
                    if len(prompt_text) > 200:
                        preview += "..."
                    result = f"{preview}"
                    break
            
            return result if result else "(未检测到正面提示词)"
            
        except Exception as e:
            return f"(提取失败: {str(e)})"
    
    def update_seed(self, workflow):
        """更新随机种子"""
        workflow_copy = json.loads(json.dumps(workflow))
        seed = random.randint(0, 2**32 - 1)
        
        for node_id, node_data in workflow_copy.items():
            if isinstance(node_data, dict) and 'inputs' in node_data and 'seed' in node_data['inputs']:
                node_data['inputs']['seed'] = seed
                
        return workflow_copy
    
    def validate_fusion_workflow(self, workflow):
        """验证workflow是否支持融合（需要至少2个LoadImage节点）"""
        load_image_count = 0
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and node_data.get('class_type') == 'LoadImage':
                load_image_count += 1
        
        if load_image_count < 2:
            messagebox.showwarning(
                "工作流不支持融合",
                f"当前工作流只有{load_image_count}个图片输入节点\n"
                f"融合功能需要至少2个LoadImage节点\n\n"
                f"请在ComfyUI中创建包含2个图片输入的融合工作流"
            )
            return False
        return True
    
    def update_dual_images(self, workflow, image_a_filename, image_b_filename):
        """更新workflow中的两个图片节点"""
        workflow_copy = json.loads(json.dumps(workflow))
        load_image_nodes = []
        
        # 找到所有LoadImage节点
        for node_id, node_data in workflow_copy.items():
            if isinstance(node_data, dict) and node_data.get('class_type') == 'LoadImage':
                load_image_nodes.append(node_id)
        
        # 更新前两个LoadImage节点
        if len(load_image_nodes) >= 2:
            workflow_copy[load_image_nodes[0]]['inputs']['image'] = image_a_filename
            workflow_copy[load_image_nodes[1]]['inputs']['image'] = image_b_filename
        
        return workflow_copy
    
    def scan_images(self, folder_path):
        """扫描文件夹中的所有图片"""
        supported_formats = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
        images = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in sorted(files):
                if Path(file).suffix.lower() in supported_formats:
                    images.append(os.path.join(root, file))
        
        return images
        
    def upload_image(self, image_path):
        """上传图片到ComfyUI服务器"""
        try:
            filename = os.path.basename(image_path)
            
            # 读取图片文件
            with open(image_path, 'rb') as f:
                files = {
                    'image': (filename, f, 'image/' + Path(image_path).suffix[1:])
                }
                
                # 上传到ComfyUI
                response = requests.post(
                    f"{self.comfyui_url}/upload/image",
                    files=files
                )
                
                if response.status_code == 200:
                    if self.log_file:
                        self.log_file.write(f"[SUCCESS] 图片已上传: {filename}\n")
                        self.log_file.flush()
                    return True
                else:
                    if self.log_file:
                        self.log_file.write(f"[ERROR] 上传图片失败 {filename}: HTTP {response.status_code}\n")
                        self.log_file.write(f"[ERROR] Response: {response.text}\n")
                        self.log_file.flush()
                    return False
                    
        except Exception as e:
            if self.log_file:
                self.log_file.write(f"[ERROR] 上传图片异常 {image_path}: {e}\n")
                import traceback
                self.log_file.write(f"[ERROR] Traceback:\n{traceback.format_exc()}\n")
                self.log_file.flush()
            return False
    
    def update_image(self, workflow, image_filename):
        """更新输入图像"""
        workflow_copy = json.loads(json.dumps(workflow))
        
        for node_id, node_data in workflow_copy.items():
            if isinstance(node_data, dict):
                if node_data.get('class_type') == 'LoadImage':
                    if 'inputs' in node_data and 'image' in node_data['inputs']:
                        node_data['inputs']['image'] = image_filename
                        break
                        
        return workflow_copy
        
    def queue_prompt(self, workflow):
        """提交工作流"""
        try:
            response = requests.post(f"{self.comfyui_url}/prompt", json={"prompt": workflow})
            if response.status_code == 200:
                result = response.json()
                return True, result.get('prompt_id', '')
            else:
                error_msg = f"提交失败: HTTP {response.status_code}"
                if self.log_file:
                    self.log_file.write(f"[ERROR] {error_msg}\n")
                    self.log_file.write(f"[ERROR] Response: {response.text}\n")
                    self.log_file.flush()
                return False, error_msg
        except Exception as e:
            error_msg = f"连接失败: {str(e)}"
            if self.log_file:
                self.log_file.write(f"[ERROR] {error_msg}\n")
                import traceback
                self.log_file.write(f"[ERROR] Traceback:\n{traceback.format_exc()}\n")
                self.log_file.flush()
            return False, error_msg
            
    def wait_for_completion(self, prompt_id, timeout=600):
        """等待生成完成并下载图片"""
        start_time = time.time()
        check_interval = 3  # 每3秒检查一次
        
        while time.time() - start_time < timeout:
            if self.stopped:
                if self.log_file:
                    self.log_file.write(f"[INFO] 用户停止任务: {prompt_id}\n")
                    self.log_file.flush()
                return False
                
            try:
                response = requests.get(f"{self.comfyui_url}/history/{prompt_id}", timeout=10)
                if response.status_code == 200:
                    history = response.json()
                    if prompt_id in history:
                        # 检查任务状态
                        prompt_info = history[prompt_id]
                        status = prompt_info.get('status', {})
                        
                        # 检查是否完成
                        if status.get('completed', False):
                            # 等待额外2秒，确保outputs已更新
                            time.sleep(2)
                            
                            # 重新获取history，确保outputs是最新的
                            response = requests.get(f"{self.comfyui_url}/history/{prompt_id}", timeout=10)
                            if response.status_code == 200:
                                history = response.json()
                                prompt_info = history.get(prompt_id, {})
                            
                            # 下载生成的图片
                            outputs = prompt_info.get('outputs', {})
                            downloaded = False
                            
                            # 调试：记录outputs结构
                            if self.log_file:
                                self.log_file.write(f"[DEBUG] Outputs结构: {json.dumps(outputs, ensure_ascii=False, indent=2)}\n")
                                self.log_file.flush()
                            
                            # ⚠️ 如果outputs为空，检查是否有错误信息
                            if not outputs or len(outputs) == 0:
                                # 检查status中是否有错误信息
                                status_messages = status.get('messages', [])
                                if status_messages:
                                    if self.log_file:
                                        self.log_file.write(f"[ERROR] 任务虽完成但outputs为空，发现错误: {status_messages}\n")
                                        self.log_file.flush()
                                    return False
                                
                                # 没有明确错误，但outputs为空，可能是workflow问题
                                if self.log_file:
                                    self.log_file.write(f"[WARNING] 任务完成但outputs为空，workflow可能有问题\n")
                                    self.log_file.write(f"[WARNING] 请检查: 1) workflow是否有SaveImage节点 2) 节点连接是否正确\n")
                                    self.log_file.flush()
                                # 返回False，因为没有实际生成
                                return False
                            
                            # 尝试从outputs中查找图片
                            for node_id, node_output in outputs.items():
                                if isinstance(node_output, dict) and 'images' in node_output:
                                    for image_info in node_output['images']:
                                        filename = image_info.get('filename')
                                        subfolder = image_info.get('subfolder', '')
                                        image_type = image_info.get('type', 'output')
                                        
                                        if filename:
                                            # 构建下载URL
                                            download_url = f"{self.comfyui_url}/view"
                                            params = {
                                                'filename': filename,
                                                'type': image_type,
                                                'subfolder': subfolder
                                            }
                                            
                                            # 下载图片
                                            try:
                                                img_response = requests.get(download_url, params=params, timeout=30)
                                                if img_response.status_code == 200:
                                                    # 保存到结果文件夹
                                                    save_path = os.path.join(self.current_batch_folder, filename)
                                                    with open(save_path, 'wb') as f:
                                                        f.write(img_response.content)
                                                    downloaded = True
                                                    
                                                    if self.log_file:
                                                        self.log_file.write(f"[SUCCESS] 图片已保存: {filename}\n")
                                                        self.log_file.flush()
                                                else:
                                                    if self.log_file:
                                                        self.log_file.write(f"[ERROR] 下载图片失败 {filename}: HTTP {img_response.status_code}\n")
                                                        self.log_file.flush()
                                            except Exception as e:
                                                if self.log_file:
                                                    self.log_file.write(f"[ERROR] 下载图片异常 {filename}: {e}\n")
                                                    self.log_file.flush()
                            
                            return downloaded
                        
                        # 检查是否有错误
                        elif status.get('status_str') == 'error':
                            error_msg = status.get('messages', [])
                            if self.log_file:
                                self.log_file.write(f"[ERROR] 任务执行失败 {prompt_id}: {error_msg}\n")
                                self.log_file.flush()
                            return False
                        
                        # 任务还在执行中，继续等待
                        else:
                            elapsed = int(time.time() - start_time)
                            if self.log_file and elapsed % 30 == 0:  # 每30秒记录一次
                                self.log_file.write(f"[INFO] 等待任务完成... 已等待{elapsed}秒: {prompt_id}\n")
                                self.log_file.flush()
                            
            except requests.exceptions.Timeout:
                if self.log_file:
                    self.log_file.write(f"[WARNING] 检查任务状态超时，继续重试: {prompt_id}\n")
                    self.log_file.flush()
            except Exception as e:
                if self.log_file:
                    self.log_file.write(f"[ERROR] 检查任务状态时出错: {e}\n")
                    import traceback
                    self.log_file.write(f"[ERROR] Traceback:\n{traceback.format_exc()}\n")
                    self.log_file.flush()
                
            time.sleep(check_interval)
        
        # 超时
        elapsed = int(time.time() - start_time)
        if self.log_file:
            self.log_file.write(f"[ERROR] 任务超时 {prompt_id}: 等待了{elapsed}秒仍未完成\n")
            self.log_file.flush()
        return False


def main():
    # 创建必要的目录
    os.makedirs("saved_workflows", exist_ok=True)
    os.makedirs("生成结果", exist_ok=True)
    
    root = tk.Tk()
    app = IntegratedGUI_V3(root)
    root.mainloop()


if __name__ == "__main__":
    main()

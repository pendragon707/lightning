import sys
import os
from pathlib import Path
import shutil
import argparse
from datetime import datetime
import traceback
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import queue

import pyvista as pv
import numpy as np

from src import find_accessible_surface, find_accessible_surface_parallel, load_step, get_accessible_mesh
from src import plot_mesh_with_projections, get_2d_mask, plot_mesh_mask, draw_sphere
from src import get_step_units
from src import AppConfig

class WorkerThread(threading.Thread):
    """Worker thread for running calculations without freezing the UI"""
    
    def __init__(self, task_type, params, progress_callback, finished_callback):
        super().__init__()
        self.task_type = task_type
        self.params = params
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.daemon = True
        
    def run(self):
        try:
            if self.task_type == "mask":
                self.calculate_mask()
            elif self.task_type == "plots":
                self.generate_plots()
            elif self.task_type == "show":
                self.show_plot()
        except Exception as e:
            self.finished_callback(False, f"Ошибка: {str(e)}\n{traceback.format_exc()}")
    
    def calculate_mask(self):
        self.progress_callback("Начало расчета маски...")
        
        # Prepare output directory
        out_path = Path(os.getcwd()) / "out" / self.params['outdir']
        out_path.mkdir(parents=True, exist_ok=True)
        
        self.progress_callback(f"Загружается модель (*.obj): {self.params['obj']}")
        self.progress_callback(f"Используется радиус сферы: {self.params['radius']}")

        rotation_angles = {
            'X': self.params['rotate_x'],
            'Y': self.params['rotate_y'],
            'Z': self.params['rotate_z']
        }
        
        # Calculate mask
        if self.params['paral']:
            result, centers = find_accessible_surface_parallel(
                self.params['obj'], 
                sphere_radius=self.params['radius'],
                rotation_angles=rotation_angles,
                rotation_order=self.params['rotation_order']
            )
        else:
            result, centers = find_accessible_surface(
                self.params['obj'], 
                sphere_radius=self.params['radius'],
                rotation_angles=rotation_angles,
                rotation_order=self.params['rotation_order']
            )

        accessible_mesh = get_accessible_mesh(result)
        
        # Save result
        save_path = out_path / "accessible_fragment.obj"
        accessible_mesh.save(save_path)
        self.progress_callback(f"Маска сохранена в: {save_path}")

        # Save original files
        save_obj_path = out_path / Path(self.params['obj']).name
        print(save_obj_path)
        shutil.copy(self.params['obj'], save_obj_path)

        save_stp_path = out_path / Path(self.params['stp']).name
        print(save_stp_path)
        shutil.copy(self.params['stp'], save_stp_path)        
        
        # Generate plots if requested
        if self.params['plots']:  
            self.progress_callback("Генерация графиков...")      
            draw_sphere(self.params['obj'], self.params['radius'], centers[3], out_dir=out_path)
            
            shape = load_step(self.params['stp'])
            plot_mesh_with_projections(accessible_mesh, shape, out_dir=out_path)
            plot_mesh_mask(result, accessible_mesh, out_dir=out_path)
            get_2d_mask(accessible_mesh, out_dir=out_path)
            self.progress_callback(f"Графики сохранены в: {out_path}")
        
        self.finished_callback(True, str(out_path))
    
    def generate_plots(self):
        self.progress_callback("Начало генерации графиков...")
        
        # Prepare output directory
        out_path = Path(os.getcwd()) / "out" / self.params['outdir']
        out_path.mkdir(parents=True, exist_ok=True)
        
        self.progress_callback(f"Загружается модель (*.obj): {self.params['obj']}")
        mesh = pv.read(self.params['obj'])     

        self.progress_callback(f"Загружается маска: {self.params['mask']}")
        mesh_mask = pv.read(self.params['mask'])

        rotation_angles = {
            'X': self.params['rotate_x'],
            'Y': self.params['rotate_y'],
            'Z': self.params['rotate_z']
        }

        # Apply rotations in selected order
        for axis in self.params['rotation_order']:
            if axis == 'X':
                mesh = mesh.rotate_x(rotation_angles['X'], inplace=False)
                mesh_mask = mesh_mask.rotate_x(rotation_angles['X'], inplace=False)
            elif axis == 'Y':
                mesh = mesh.rotate_y(rotation_angles['Y'], inplace=False)
                mesh_mask = mesh_mask.rotate_y(rotation_angles['Y'], inplace=False)
            elif axis == 'Z':
                mesh = mesh.rotate_z(rotation_angles['Z'], inplace=False)
                mesh_mask = mesh_mask.rotate_z(rotation_angles['Z'], inplace=False)
        
        self.progress_callback(f"Загружается модель (*.stp): {self.params['stp']}")
        shape = load_step(self.params['stp'])
        
        self.progress_callback("Генерация графиков...")
        plot_mesh_with_projections(mesh_mask, shape, out_dir=out_path)
        plot_mesh_mask(mesh, mesh_mask, out_dir=out_path)
        get_2d_mask(mesh_mask, out_dir=out_path)
        
        self.progress_callback(f"Графики сохранены в: {out_path}")
        print(type(out_path))
        self.finished_callback(True, str(out_path))  

    def show_plot(self):          
        self.progress_callback("Начало генерации графиков...")

        self.progress_callback(f"Загружается модель (*.obj): {self.params['obj']}")
        mesh = pv.read(self.params['obj'])

        rotation_angles = {
            'X': self.params['rotate_x'],
            'Y': self.params['rotate_y'],
            'Z': self.params['rotate_z']
        }

        # Apply rotations in selected order
        for axis in self.params['rotation_order']:
            if axis == 'X':
                mesh = mesh.rotate_x(rotation_angles['X'], inplace=False)                
            elif axis == 'Y':
                mesh = mesh.rotate_y(rotation_angles['Y'], inplace=False)                
            elif axis == 'Z':
                mesh = mesh.rotate_z(rotation_angles['Z'], inplace=False)                

        if 'mask' in self.params:
            self.progress_callback(f"Загружена маска из: {self.params['mask']}")
            mesh_mask = pv.read(self.params['mask'])

            # Apply rotations in selected order
            for axis in self.params['rotation_order']:
                if axis == 'X':                   
                    mesh_mask = mesh_mask.rotate_x(rotation_angles['X'], inplace=False)
                elif axis == 'Y':                    
                    mesh_mask = mesh_mask.rotate_y(rotation_angles['Y'], inplace=False)
                elif axis == 'Z':                    
                    mesh_mask = mesh_mask.rotate_z(rotation_angles['Z'], inplace=False)                

            self.progress_callback("Генерация графиков...")        
            plot_mesh_mask(mesh, mesh_mask, save=False)
        else:
            self.progress_callback("Генерация графиков...")        
            plot_mesh_mask(mesh, save=False)

        self.progress_callback(f"Графики построены")
        self.finished_callback(True, "")          


class MainWindow:
    def __init__(self, config_file: Optional[str] = None):        
        if config_file and os.path.exists(config_file):
            self.config = AppConfig.load_from_file(config_file)
        else:
            self.config = AppConfig()

        # Define default settings directory
        self.settings_dir = Path("settings")
        self.settings_dir.mkdir(exist_ok=True)  # Create directory if it doesn't exist

        self.root = tk.Tk()
        self.root.title("Расчет молниеопасных зон")
        self.root.geometry("500x600")

        self.create_menu_bar()
        
        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel for controls
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        
        # Create notebook (tab widget)
        self.mode_notebook = ttk.Notebook(left_panel)
        self.mode_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create tabs
        self.mask_tab = ttk.Frame(self.mode_notebook)
        self.plots_tab = ttk.Frame(self.mode_notebook)
        self.mode_notebook.add(self.mask_tab, text="Расчет молниеопасных зон")
        self.mode_notebook.add(self.plots_tab, text="Построение графиков")
        
        # Initialize variables
        self.mask_obj_path = tk.StringVar(value=self.config.mask_obj_path)
        self.mask_stp_path = tk.StringVar(value=self.config.mask_stp_path)
        self.radius_input = tk.StringVar(value=self.config.radius_input)
        self.mask_outdir = tk.StringVar(value=self.config.mask_outdir)
        
        self.plots_obj_path = tk.StringVar(value=self.config.plots_obj_path)
        self.plots_stp_path = tk.StringVar(value=self.config.plots_stp_path)
        self.mask_path = tk.StringVar(value=self.config.mask_path)
        self.plots_outdir = tk.StringVar(value=self.config.plots_outdir)

        self.units_list = self.config.units_list
        self.units_var = tk.StringVar(value=self.config.units_var)

        self.rotation_order = tk.StringVar(value=self.config.rotation_order)
        self.rotate_x = tk.DoubleVar(value=self.config.rotate_x)
        self.rotate_y = tk.DoubleVar(value=self.config.rotate_y)
        self.rotate_z = tk.DoubleVar(value=self.config.rotate_z)

        # Setup tabs
        self.setup_mask_tab()
        self.setup_plots_tab()      
        
        # Buttons
        button_frame = ttk.Frame(left_panel)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.show_button = ttk.Button(button_frame, text="Просмотр", command=self.show_task)
        self.show_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.run_button = ttk.Button(button_frame, text="Запустить", command=self.run_task)
        self.run_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Progress display
        self.progress_text = tk.Text(left_panel, height=10, wrap=tk.WORD)
        self.progress_text.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar for progress text
        scrollbar = ttk.Scrollbar(self.progress_text, command=self.progress_text.yview)
        self.progress_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(left_panel, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))
        
        # Worker thread
        self.worker = None
        self.message_queue = queue.Queue()
        
        # Start checking the queue
        self.check_queue()
        
        # Bind mask_path change
        self.mask_path.trace_add('write', self.update_mask_path)        

    def update_units_from_stp(self):
        """Update the units combobox based on the current STP file."""
        stp_path = self.mask_stp_path.get()
        print("update_units_from_stp ", stp_path)
        
        if not stp_path or not os.path.exists(stp_path):
            # If file doesn't exist, set default
            self.units_var.set("millimetre")
            return
            
        try:
            step_units = get_step_units(stp_path)
            print("update_units_from_stp ", step_units)
            if step_units and step_units in self.units_list:
                self.units_var.set(step_units)
            else:
                # If unknown unit, set to millimetre (OCC default)
                self.units_var.set("millimetre")
        except Exception as e:
            print(f"Error reading STP units: {e}")
            self.units_var.set("millimetre")        

    def setup_mask_tab(self):
        # Create scrollable frame
        canvas = tk.Canvas(self.mask_tab)
        scrollbar = ttk.Scrollbar(self.mask_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # OBJ file
        obj_frame = ttk.Frame(scrollable_frame)
        obj_frame.pack(fill=tk.X, pady=5)
        ttk.Label(obj_frame, text="Модель (*.obj):").pack(side=tk.LEFT)
        obj_entry = ttk.Entry(obj_frame, textvariable=self.mask_obj_path)
        obj_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(obj_frame, text="Найти", 
                  command=lambda: self.browse_file(self.mask_obj_path, "OBJ files (*.obj)")).pack(side=tk.RIGHT)
        
        # Warning label for OBJ
        self.obj_warning = ttk.Label(scrollable_frame, text="", foreground="red")
        self.obj_warning.pack(fill=tk.X, pady=(0, 5), padx=20)

        # STP file
        stp_frame = ttk.Frame(scrollable_frame)
        stp_frame.pack(fill=tk.X, pady=5)
        ttk.Label(stp_frame, text="Модель (*.stp):").pack(side=tk.LEFT)
        stp_entry = ttk.Entry(stp_frame, textvariable=self.mask_stp_path)
        stp_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(stp_frame, text="Найти",
                  command=lambda: self.browse_file(self.mask_stp_path, "STEP files (*.stp)")).pack(side=tk.RIGHT)
        
        # Warning label for STP
        self.stp_warning = ttk.Label(scrollable_frame, text="", foreground="red")
        self.stp_warning.pack(fill=tk.X, pady=(0, 5), padx=20)

        #  Validate initial files
        self.validate_file_exists(self.mask_obj_path, self.obj_warning, "OBJ file")
        self.validate_file_exists(self.mask_stp_path, self.stp_warning, "STP file")
        self.setup_file_validation()

        # Radius
        radius_frame = ttk.Frame(scrollable_frame)
        radius_frame.pack(fill=tk.X, pady=5)
        ttk.Label(radius_frame, text="Радиус сферы (м):").pack(side=tk.LEFT)
        radius_entry = ttk.Entry(radius_frame, textvariable=self.radius_input)
        radius_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Единицы измерения
        units_frame = ttk.Frame(scrollable_frame)
        units_frame.pack(fill=tk.X, pady=5)        
        tk.Label(units_frame, text="Единицы измерения модели:").pack(side=tk.LEFT)              

        self.combobox = ttk.Combobox(
            units_frame,
            textvariable=self.units_var,
            values=self.units_list,
            width=20
        )    
        self.combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.update_units_from_stp()
        
        # Output directory
        outdir_frame = ttk.Frame(scrollable_frame)
        outdir_frame.pack(fill=tk.X, pady=5)
        ttk.Label(outdir_frame, text="Директория сохранения:").pack(side=tk.LEFT)
        outdir_entry = ttk.Entry(outdir_frame, textvariable=self.mask_outdir)
        outdir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Options
        self.paral_var = tk.BooleanVar(value=True)
        paral_checkbox = ttk.Checkbutton(scrollable_frame, text="Включить параллельность",
                                         variable=self.paral_var)
        paral_checkbox.pack(anchor=tk.W, pady=5)

        self.plots_var = tk.BooleanVar(value=True)
        plots_checkbox = ttk.Checkbutton(scrollable_frame, text="Построение графиков",
                                         variable=self.plots_var)
        plots_checkbox.pack(anchor=tk.W, pady=5)    

        # Создаем фрейм для углов поворота
        rotation_frame = ttk.LabelFrame(scrollable_frame, text="Поворот модели", padding=5)
        rotation_frame.pack(anchor=tk.W, pady=5, fill=tk.X)

        # Add order selection (from Option 1)
        order_frame = ttk.Frame(rotation_frame)
        order_frame.pack(anchor=tk.W, pady=5)
        ttk.Label(order_frame, text="Rotation Order:").pack(side=tk.LEFT, padx=(0, 10))
        orders = ["XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"]
        order_combo = ttk.Combobox(order_frame, textvariable=self.rotation_order, 
                                   values=orders, state="readonly", width=8)
        order_combo.pack(side=tk.LEFT)
        # order_combo.bind('<<ComboboxSelected>>', lambda e: self.on_rotation_changed())

        # Строка для оси X
        x_frame = ttk.Frame(rotation_frame)
        x_frame.pack(anchor=tk.W, pady=2)
        ttk.Label(x_frame, text="X:").pack(side=tk.LEFT, padx=(0, 5))
        x_entry = ttk.Entry(x_frame, textvariable=self.rotate_x, width=10)
        x_entry.pack(side=tk.LEFT)
        ttk.Label(x_frame, text="°").pack(side=tk.LEFT, padx=(0, 10))

        # Строка для оси Y
        y_frame = ttk.Frame(rotation_frame)
        y_frame.pack(anchor=tk.W, pady=2)
        ttk.Label(y_frame, text="Y:").pack(side=tk.LEFT, padx=(0, 5))
        y_entry = ttk.Entry(y_frame, textvariable=self.rotate_y, width=10)
        y_entry.pack(side=tk.LEFT)
        ttk.Label(y_frame, text="°").pack(side=tk.LEFT, padx=(0, 10))

        # Строка для оси Z
        z_frame = ttk.Frame(rotation_frame)
        z_frame.pack(anchor=tk.W, pady=2)
        ttk.Label(z_frame, text="Z:").pack(side=tk.LEFT, padx=(0, 5))
        z_entry = ttk.Entry(z_frame, textvariable=self.rotate_z, width=10)
        z_entry.pack(side=tk.LEFT)
        ttk.Label(z_frame, text="°").pack(side=tk.LEFT, padx=(0, 10))       
    
    def setup_plots_tab(self):
        # Create scrollable frame
        canvas = tk.Canvas(self.plots_tab)
        scrollbar = ttk.Scrollbar(self.plots_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # OBJ file
        obj_frame = ttk.Frame(scrollable_frame)
        obj_frame.pack(fill=tk.X, pady=5)
        ttk.Label(obj_frame, text="Модель (*.obj):").pack(side=tk.LEFT)
        obj_entry = ttk.Entry(obj_frame, textvariable=self.plots_obj_path)
        obj_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(obj_frame, text="Найти",
                  command=lambda: self.browse_file(self.plots_obj_path, "OBJ files (*.obj)")).pack(side=tk.RIGHT)
        
        # STP file
        stp_frame = ttk.Frame(scrollable_frame)
        stp_frame.pack(fill=tk.X, pady=5)
        ttk.Label(stp_frame, text="Модель (*.stp):").pack(side=tk.LEFT)
        stp_entry = ttk.Entry(stp_frame, textvariable=self.plots_stp_path)
        stp_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(stp_frame, text="Найти",
                  command=lambda: self.browse_file(self.plots_stp_path, "STEP files (*.stp)")).pack(side=tk.RIGHT)
        
        # Mask file
        mask_frame = ttk.Frame(scrollable_frame)
        mask_frame.pack(fill=tk.X, pady=5)
        ttk.Label(mask_frame, text="Маска молниеопасных зон:").pack(side=tk.LEFT)
        mask_entry = ttk.Entry(mask_frame, textvariable=self.mask_path)
        mask_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(mask_frame, text="Найти",
                  command=lambda: self.browse_file(self.mask_path, "OBJ files (*.obj)")).pack(side=tk.RIGHT)
        
        # Output directory
        outdir_frame = ttk.Frame(scrollable_frame)
        outdir_frame.pack(fill=tk.X, pady=5)
        ttk.Label(outdir_frame, text="Директория сохранения:").pack(side=tk.LEFT)
        outdir_entry = ttk.Entry(outdir_frame, textvariable=self.plots_outdir)
        outdir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Создаем фрейм для углов поворота
        rotation_frame = ttk.LabelFrame(scrollable_frame, text="Поворот модели", padding=5)
        rotation_frame.pack(anchor=tk.W, pady=5, fill=tk.X)

        # Add order selection (from Option 1)
        order_frame = ttk.Frame(rotation_frame)
        order_frame.pack(anchor=tk.W, pady=5)
        ttk.Label(order_frame, text="Rotation Order:").pack(side=tk.LEFT, padx=(0, 10))
        orders = ["XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"]
        order_combo = ttk.Combobox(order_frame, textvariable=self.rotation_order, 
                                   values=orders, state="readonly", width=8)
        order_combo.pack(side=tk.LEFT)

        # Строка для оси X
        x_frame = ttk.Frame(rotation_frame)
        x_frame.pack(anchor=tk.W, pady=2)
        ttk.Label(x_frame, text="X:").pack(side=tk.LEFT, padx=(0, 5))
        x_entry = ttk.Entry(x_frame, textvariable=self.rotate_x, width=10)
        x_entry.pack(side=tk.LEFT)
        ttk.Label(x_frame, text="°").pack(side=tk.LEFT, padx=(0, 10))

        # Строка для оси Y
        y_frame = ttk.Frame(rotation_frame)
        y_frame.pack(anchor=tk.W, pady=2)
        ttk.Label(y_frame, text="Y:").pack(side=tk.LEFT, padx=(0, 5))
        y_entry = ttk.Entry(y_frame, textvariable=self.rotate_y, width=10)
        y_entry.pack(side=tk.LEFT)
        ttk.Label(y_frame, text="°").pack(side=tk.LEFT, padx=(0, 10))

        # Строка для оси Z
        z_frame = ttk.Frame(rotation_frame)
        z_frame.pack(anchor=tk.W, pady=2)
        ttk.Label(z_frame, text="Z:").pack(side=tk.LEFT, padx=(0, 5))
        z_entry = ttk.Entry(z_frame, textvariable=self.rotate_z, width=10)
        z_entry.pack(side=tk.LEFT)
        ttk.Label(z_frame, text="°").pack(side=tk.LEFT, padx=(0, 10))    

    def update_mask_path(self, *args):
        self.plots_outdir.set(str(Path(self.mask_path.get()).parent))
    
    def browse_file(self, string_var, file_filter):
        file_path = filedialog.askopenfilename(title="Выбрать файл", filetypes=[(file_filter, "*.*")])
        if file_path:
            string_var.set(file_path)

        #  Validate initial files
        self.validate_file_exists(self.mask_obj_path, self.obj_warning, "OBJ file")
        self.validate_file_exists(self.mask_stp_path, self.stp_warning, "STP file")            
    
    def setup_file_validation(self):
        """Set up trace to validate files when paths are edited"""
        # Trace both OBJ and STP paths
        self.mask_obj_path.trace('w', self.on_obj_path_changed)
        self.mask_stp_path.trace('w', self.on_stp_path_changed)

    def on_obj_path_changed(self, *args):
        """Called when OBJ path is edited"""
        self.validate_file_exists(self.mask_obj_path, self.obj_warning, "OBJ file")

    def on_stp_path_changed(self, *args):
        """Called when STP path is edited"""
        self.validate_file_exists(self.mask_stp_path, self.stp_warning, "STP file")
        self.update_units_from_stp()

    def update_progress(self, message):
        self.message_queue.put(("progress", message))
    
    def task_finished(self, success, result):
        self.message_queue.put(("finished", (success, result)))
    
    def check_queue(self):
        try:
            while True:
                msg_type, msg_data = self.message_queue.get_nowait()
                
                if msg_type == "progress":
                    self.progress_text.insert(tk.END, msg_data + "\n")
                    self.progress_text.see(tk.END)
                    self.root.update_idletasks()
                
                elif msg_type == "finished":
                    success, result = msg_data
                    self.run_button.config(state=tk.NORMAL)
                    self.show_button.config(state=tk.NORMAL)
                    self.progress_bar.stop()
                    
                    if success:
                        self.progress_text.insert(tk.END, f"Задача выполнена успешно! Результат сохранён в: {result}\n")
                        self.progress_text.see(tk.END)
                        if result:
                            messagebox.showinfo("Успех", f"Задача выполнена успешно!\nРезультат сохранён в: {result}")
                    else:
                        self.progress_text.insert(tk.END, f"Задача не выполнена: {result}\n")
                        self.progress_text.see(tk.END)
                        messagebox.showerror("Ошибка", f"Задача не выполнена:\n{result}")
                    
                    self.worker = None
        
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)
    
    def show_task(self):
        self.show_button.config(state=tk.DISABLED)
        self.run_button.config(state=tk.DISABLED)
        self.progress_bar.start()
        self.update_progress("Инициализация...")
        
        # Get parameters based on active tab
        current_tab = self.mode_notebook.index(self.mode_notebook.select())

        radius_value = float(self.radius_input.get())
        radius_in_meters = self.convert_to_meters(radius_value)        
        
        if current_tab == 0:  # Mask tab
            params = {
                'obj': self.mask_obj_path.get(),
                'stp': self.mask_stp_path.get(),
                'radius': radius_in_meters,
                'paral': self.paral_var.get(),
                'plots': self.plots_var.get(),                
                'rotate_x': self.rotate_x.get(),
                'rotate_y': self.rotate_y.get(),
                'rotate_z': self.rotate_z.get(),
                'rotation_order': self.rotation_order.get(),
                'outdir': self.mask_outdir.get()
            }
            task_type = "show"
        else:  # Plots tab
            params = {
                'obj': self.plots_obj_path.get(),
                'stp': self.plots_stp_path.get(),
                'mask': self.mask_path.get(),
                'rotate_x': self.rotate_x.get(),
                'rotate_y': self.rotate_y.get(),
                'rotate_z': self.rotate_z.get(),
                'rotation_order': self.rotation_order.get(),
                'outdir': self.plots_outdir.get()
            }
            task_type = "show"
        
        self.worker = WorkerThread(task_type, params, self.update_progress, self.task_finished)
        self.worker.start()
    
    def run_task(self):
        # Disable buttons during execution
        self.run_button.config(state=tk.DISABLED)
        self.show_button.config(state=tk.DISABLED)
        self.progress_bar.start()
        self.update_progress("Инициализация...")
        
        # Get parameters based on active tab
        current_tab = self.mode_notebook.index(self.mode_notebook.select())

        radius_value = float(self.radius_input.get())
        radius_in_meters = self.convert_to_meters(radius_value)

        print("radius_value ", radius_value)
        print("radius_in_meters ", radius_in_meters)
        
        if current_tab == 0:  # Mask tab
            params = {
                'obj': self.mask_obj_path.get(),
                'stp': self.mask_stp_path.get(),
                'radius': radius_in_meters,
                'paral': self.paral_var.get(),
                'plots': self.plots_var.get(),                
                'rotate_x': self.rotate_x.get(),
                'rotate_y': self.rotate_y.get(),
                'rotate_z': self.rotate_z.get(),
                'rotation_order': self.rotation_order.get(),
                'outdir': self.mask_outdir.get()
            }
            task_type = "mask"
        else:  # Plots tab
            params = {
                'obj': self.plots_obj_path.get(),
                'stp': self.plots_stp_path.get(),
                'mask': self.mask_path.get(),                
                'rotate_x': self.rotate_x.get(),
                'rotate_y': self.rotate_y.get(),
                'rotate_z': self.rotate_z.get(),
                'rotation_order': self.rotation_order.get(),
                'outdir': self.plots_outdir.get()
            }
            task_type = "plots"
        
        # Start worker thread
        self.worker = WorkerThread(task_type, params, self.update_progress, self.task_finished)
        self.worker.start()

    def convert_to_meters(self, value):
        """Convert a value from self.units to meters."""
        unit = self.units_var.get()
        
        conversion_factors = {
            'metre': 1.0,
            'centimetre': 100,
            'millimetre': 1000,
            'inches': 39.37
        }
        
        if unit in conversion_factors:
            return value * conversion_factors[unit]
        else:
            # Default to millimetre if unknown (OCC default)
            print(f"Unknown unit '{unit}', defaulting to millimetre")
            return value * 1000

    def validate_file_exists(self, path_var, warning_label, file_type="file"):
        """Check if file exists and update warning label accordingly""" 
        file_path = path_var.get()
        if not file_path:
            warning_label.config(text=f"⚠️ {file_type} путь не указан!", foreground="red")
            return False
        elif not Path(file_path).exists():
            warning_label.config(text=f"⚠️ {file_type} не найден!", foreground="red")
            return False
        else:
            # Hide the label when file exists
            warning_label.config(text="")
            return True

    def create_menu_bar(self):
        """Create the menu bar with File dropdown"""
        # Create menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Create File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        
        # Add File menu items
        file_menu.add_command(label="Сохранить настройки", 
                              command=self.save_config, 
                              accelerator="Ctrl+S")
        file_menu.add_command(label="Загрузить настройки", 
                              command=self.load_config,
                              accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Выйти", 
                              command=self.root.quit,
                              accelerator="Ctrl+Q")
        
        # Create Help menu (optional)
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)
        
        # Bind keyboard shortcuts
        self.root.bind('<Control-s>', lambda e: self.save_config())
        self.root.bind('<Control-o>', lambda e: self.load_config())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "О программе",
            "Расчет молниеопасных зон\n\n"
            "Версия: 1.0\n"
        )

    def save_config(self):
        """Save current configuration to JSON file in settings directory"""
        # Generate default filename with timestamp
        default_filename = f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        default_path = self.settings_dir / default_filename
        
        filepath = filedialog.asksaveasfilename(
            title="Сохранить конфигурацию",
            initialdir=str(self.settings_dir),
            initialfile=default_filename,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            try:
                # Update config with current values
                self.update_config_from_gui()
                self.config.save_to_file(filepath)
                messagebox.showinfo("Успех", f"Конфигурация сохранена в:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить конфигурацию:\n{str(e)}")
    
    def load_config(self):
        """Load configuration from JSON file in settings directory"""
        filepath = filedialog.askopenfilename(
            title="Загрузить конфигурацию",
            initialdir=str(self.settings_dir),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            try:
                # Load config from file
                new_config = AppConfig.load_from_file(filepath)
                self.config = new_config
                
                # Update GUI with loaded config
                self.update_gui_from_config()
                messagebox.showinfo("Успех", f"Конфигурация загружена из:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить конфигурацию:\n{str(e)}")
    
    def update_config_from_gui(self):
        """Update config object with current GUI values"""
        self.config.mask_obj_path = self.mask_obj_path.get()
        self.config.mask_stp_path = self.mask_stp_path.get()
        self.config.radius_input = self.radius_input.get()
        self.config.mask_outdir = self.mask_outdir.get()
        self.config.plots_obj_path = self.plots_obj_path.get()
        self.config.plots_stp_path = self.plots_stp_path.get()
        self.config.mask_path = self.mask_path.get()
        self.config.plots_outdir = self.plots_outdir.get()
        self.config.units_var = self.units_var.get()
        self.config.rotation_order = self.rotation_order.get()
        self.config.rotate_x = self.rotate_x.get()
        self.config.rotate_y = self.rotate_y.get()
        self.config.rotate_z = self.rotate_z.get()
        self.config.paral_var = self.paral_var.get()
        self.config.plots_var = self.plots_var.get()
    
    def update_gui_from_config(self):
        """Update GUI with values from config object"""
        self.mask_obj_path.set(self.config.mask_obj_path)
        self.mask_stp_path.set(self.config.mask_stp_path)
        self.radius_input.set(self.config.radius_input)
        self.mask_outdir.set(self.config.mask_outdir)
        self.plots_obj_path.set(self.config.plots_obj_path)
        self.plots_stp_path.set(self.config.plots_stp_path)
        self.mask_path.set(self.config.mask_path)
        self.plots_outdir.set(self.config.plots_outdir)
        self.units_var.set(self.config.units_var)
        self.rotation_order.set(self.config.rotation_order)
        self.rotate_x.set(self.config.rotate_x)
        self.rotate_y.set(self.config.rotate_y)
        self.rotate_z.set(self.config.rotate_z)
        self.paral_var.set(self.config.paral_var)
        self.plots_var.set(self.config.plots_var)
        
        # Trigger validation after updating
        self.validate_file_exists(self.mask_obj_path, self.obj_warning, "OBJ file")
        self.validate_file_exists(self.mask_stp_path, self.stp_warning, "STP file")
        self.update_units_from_stp()

    def run(self):
        self.root.mainloop()


def main():
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
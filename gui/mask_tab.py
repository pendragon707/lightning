# mask_tab.py
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from .tab_configs import TabConfig

from src import get_step_units

class MaskTabConfig(TabConfig):
    """Configuration for the Mask tab"""
    
    def __init__(self, parent, config):
        super().__init__(parent, config, "mask")
        self.mask_obj_path = tk.StringVar(value=config.mask_obj_path)
        self.mask_stp_path = tk.StringVar(value=config.mask_stp_path)
        self.radius_input = tk.StringVar(value=config.radius_input)
        self.mask_outdir = tk.StringVar(value=config.mask_outdir)
        self.units_var = tk.StringVar(value=config.units_var)
        self.mask_rotation_order = tk.StringVar(value=config.mask_rotation_order)
        self.mask_rotate_x = tk.DoubleVar(value=config.mask_rotate_x)
        self.mask_rotate_y = tk.DoubleVar(value=config.mask_rotate_y)
        self.mask_rotate_z = tk.DoubleVar(value=config.mask_rotate_z)
        self.paral_var = tk.BooleanVar(value=config.paral_var)
        self.plots_var = tk.BooleanVar(value=config.plots_var)
        
        # Warning labels
        self.obj_warning = None
        self.stp_warning = None
        
    def setup(self, notebook):
        """Setup the mask tab UI"""
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="Расчет молниеопасных зон")
        
        scrollable_frame = self.create_scrollable_frame()
        
        # OBJ file
        self.create_file_input(
            scrollable_frame, "Модель (*.obj):", 
            self.mask_obj_path, "OBJ files (*.obj)", "obj_warning", "OBJ file"
        )
        
        # STP file
        self.create_file_input(
            scrollable_frame, "Модель (*.stp):", 
            self.mask_stp_path, "STEP files (*.stp)", "stp_warning", "STP file"
        )
        
        # Radius
        radius_frame = ttk.Frame(scrollable_frame)
        radius_frame.pack(fill=tk.X, pady=5)
        ttk.Label(radius_frame, text="Радиус сферы (м):").pack(side=tk.LEFT)
        radius_entry = ttk.Entry(radius_frame, textvariable=self.radius_input)
        radius_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Units
        units_frame = ttk.Frame(scrollable_frame)
        units_frame.pack(fill=tk.X, pady=5)
        tk.Label(units_frame, text="Единицы измерения модели:").pack(side=tk.LEFT)
        self.combobox = ttk.Combobox(
            units_frame,
            textvariable=self.units_var,
            values=self.config.units_list,
            width=20
        )
        self.combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Output directory
        outdir_frame = ttk.Frame(scrollable_frame)
        outdir_frame.pack(fill=tk.X, pady=5)
        ttk.Label(outdir_frame, text="Директория сохранения:").pack(side=tk.LEFT)
        outdir_entry = ttk.Entry(outdir_frame, textvariable=self.mask_outdir)
        outdir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Options
        paral_checkbox = ttk.Checkbutton(
            scrollable_frame, text="Включить параллельность",
            variable=self.paral_var
        )
        paral_checkbox.pack(anchor=tk.W, pady=5)
        
        plots_checkbox = ttk.Checkbutton(
            scrollable_frame, text="Построение графиков",
            variable=self.plots_var
        )
        plots_checkbox.pack(anchor=tk.W, pady=5)
        
        # Rotation controls
        self.create_rotation_controls(
            scrollable_frame, 
            self.mask_rotation_order, 
            self.mask_rotate_x, 
            self.mask_rotate_y, 
            self.mask_rotate_z
        )
        
        # Validate initial files
        self.validate_files()
        
        return self.frame

    def get_params(self):
        """Get parameters for task execution"""

        params = {
            'obj': self.mask_obj_path.get(),
            'radius': float(self.radius_input.get()),
            'paral': self.paral_var.get(),
            'plots': self.plots_var.get(),
            'rotate_x': self.mask_rotate_x.get(),
            'rotate_y': self.mask_rotate_y.get(),
            'rotate_z': self.mask_rotate_z.get(),
            'rotation_order': self.mask_rotation_order.get(),
            'outdir': self.mask_outdir.get()
        }

        stp_path = self.mask_stp_path.get()
        if stp_path and Path(stp_path).exists():
            params['stp'] = stp_path
        else:
            print("STP файл не найден или не указан")
            # params['stp'] = None

        return params

    
    def update_config(self, config):
        """Update config with current values"""
        config.mask_obj_path = self.mask_obj_path.get()
        config.mask_stp_path = self.mask_stp_path.get()
        config.radius_input = self.radius_input.get()
        config.mask_outdir = self.mask_outdir.get()
        config.units_var = self.units_var.get()
        config.mask_rotation_order = self.mask_rotation_order.get()
        config.mask_rotate_x = self.mask_rotate_x.get()
        config.mask_rotate_y = self.mask_rotate_y.get()
        config.mask_rotate_z = self.mask_rotate_z.get()
        config.paral_var = self.paral_var.get()
        config.plots_var = self.plots_var.get()
        return config
    
    def load_from_config(self, config):
        """Load values from config"""
        self.mask_obj_path.set(config.mask_obj_path)
        self.mask_stp_path.set(config.mask_stp_path)
        self.radius_input.set(config.radius_input)
        self.mask_outdir.set(config.mask_outdir)
        self.units_var.set(config.units_var)
        self.mask_rotation_order.set(config.mask_rotation_order)
        self.mask_rotate_x.set(config.mask_rotate_x)
        self.mask_rotate_y.set(config.mask_rotate_y)
        self.mask_rotate_z.set(config.mask_rotate_z)
        self.paral_var.set(config.paral_var)
        self.plots_var.set(config.plots_var)
        self.validate_files()

if __name__ == "__main__":
    pass        
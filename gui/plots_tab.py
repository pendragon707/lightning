# plots_tab.py
import tkinter as tk
from tkinter import ttk
from .tab_configs import TabConfig

from pathlib import Path

class PlotsTabConfig(TabConfig):
    """Configuration for the Plots tab"""
    
    def __init__(self, parent, config):
        super().__init__(parent, config, "plots")
        self.plots_obj_path = tk.StringVar(value=config.plots_obj_path)
        self.plots_stp_path = tk.StringVar(value=config.plots_stp_path)
        self.mask_path = tk.StringVar(value=config.mask_path)
        self.plots_outdir = tk.StringVar(value=config.plots_outdir)
        self.rotation_order = tk.StringVar(value=config.rotation_order)
        self.rotate_x = tk.DoubleVar(value=config.rotate_x)
        self.rotate_y = tk.DoubleVar(value=config.rotate_y)
        self.rotate_z = tk.DoubleVar(value=config.rotate_z)
        
        # Warning labels
        self.obj_warning = None
        self.stp_warning = None
        self.mask_warning = None
    
    def setup(self, notebook):
        """Setup the plots tab UI"""
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="Построение графиков")
        
        scrollable_frame = self.create_scrollable_frame()
        
        # OBJ file
        self.create_file_input(
            scrollable_frame, "Модель (*.obj):", 
            self.plots_obj_path, "OBJ files (*.obj)", "obj_warning", "OBJ file"
        )
        
        # STP file
        self.create_file_input(
            scrollable_frame, "Модель (*.stp):", 
            self.plots_stp_path, "STEP files (*.stp)", "stp_warning", "STP file"
        )
        
        # Mask file
        self.create_file_input(
            scrollable_frame, "Маска молниеопасных зон:", 
            self.mask_path, "OBJ files (*.obj)", "mask_warning", "Mask file"
        )
        
        # Output directory
        outdir_frame = ttk.Frame(scrollable_frame)
        outdir_frame.pack(fill=tk.X, pady=5)
        ttk.Label(outdir_frame, text="Директория сохранения:").pack(side=tk.LEFT)
        outdir_entry = ttk.Entry(outdir_frame, textvariable=self.plots_outdir)
        outdir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Rotation controls
        self.create_rotation_controls(
            scrollable_frame, self.rotation_order, 
            self.rotate_x, self.rotate_y, self.rotate_z
        )

        # Set up mask path update
        self.mask_path.trace('w', self._on_mask_path_changed)        
        
        # Validate initial files
        self.validate_files()
        
        return self.frame
    
    def _on_mask_path_changed(self, *args):
        """Update output directory when mask path changes"""
        mask_file = self.mask_path.get()
        if mask_file and Path(mask_file).exists():
            self.plots_outdir.set(str(Path(mask_file).parent))
        
        # Also validate the mask file
        if 'mask_warning' in self.file_vars:
            var, warning, file_type = self.file_vars['mask_warning']
            self.validate_file_exists(var, warning, file_type)

    def get_params(self):
        """Get parameters for task execution"""
        return {
            'obj': self.plots_obj_path.get(),
            'stp': self.plots_stp_path.get(),
            'mask': self.mask_path.get(),
            'rotate_x': self.rotate_x.get(),
            'rotate_y': self.rotate_y.get(),
            'rotate_z': self.rotate_z.get(),
            'rotation_order': self.rotation_order.get(),
            'outdir': self.plots_outdir.get()
        }
    
    def update_config(self, config):
        """Update config with current values"""
        config.plots_obj_path = self.plots_obj_path.get()
        config.plots_stp_path = self.plots_stp_path.get()
        config.mask_path = self.mask_path.get()
        config.plots_outdir = self.plots_outdir.get()
        config.rotation_order = self.rotation_order.get()
        config.rotate_x = self.rotate_x.get()
        config.rotate_y = self.rotate_y.get()
        config.rotate_z = self.rotate_z.get()
        return config
    
    def load_from_config(self, config):
        """Load values from config"""
        self.plots_obj_path.set(config.plots_obj_path)
        self.plots_stp_path.set(config.plots_stp_path)
        self.mask_path.set(config.mask_path)
        self.plots_outdir.set(config.plots_outdir)
        self.rotation_order.set(config.rotation_order)
        self.rotate_x.set(config.rotate_x)
        self.rotate_y.set(config.rotate_y)
        self.rotate_z.set(config.rotate_z)
        self.validate_files()
        
        # Auto-update output directory based on mask path
        self.plots_outdir.set(str(Path(self.mask_path.get()).parent))
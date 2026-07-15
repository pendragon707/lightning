# tab_configs.py
from abc import ABC, abstractmethod
import tkinter as tk
from tkinter import ttk
from pathlib import Path

class TabConfig(ABC):
    """Base class for tab configuration"""
    
    def __init__(self, parent, config, tab_name):
        self.parent = parent
        self.config = config
        self.tab_name = tab_name
        self.frame = None
        self.warnings = {}
        self.file_vars = {}
        
    @abstractmethod
    def setup(self, notebook):
        """Setup the tab UI"""
        pass
    
    @abstractmethod
    def get_params(self):
        """Get parameters for task execution"""
        pass
    
    @abstractmethod
    def update_config(self, config):
        """Update config with current values"""
        pass
    
    @abstractmethod
    def load_from_config(self, config):
        """Load values from config"""
        pass
    
    def create_scrollable_frame(self):
        """Create a scrollable frame for the tab"""
        canvas = tk.Canvas(self.frame)
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        return scrollable_frame
    
    def create_file_input(self, parent, label_text, var, file_filter, warning_key=None, file_type="file"):
        """Create a file input with label, entry, and browse button"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(frame, text=label_text).pack(side=tk.LEFT)
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(frame, text="Найти",
                  command=lambda: self.browse_file(var, file_filter)).pack(side=tk.RIGHT)
        
        if warning_key:            
            warning = ttk.Label(parent, text="", foreground="red")
            warning.pack(fill=tk.X, pady=(0, 5), padx=20)
            self.warnings[warning_key] = (warning, var)
            self.file_vars[warning_key] = (var, warning, file_type)
            
            # Set up trace for validation
            var.trace('w', lambda *args, v=var, w=warning, ft=file_type: 
                     self._on_file_path_changed(v, w, ft))

        return frame
    
    def _on_file_path_changed(self, var, warning, file_type):
        """Called when a file path is edited"""
        self.validate_file_exists(var, warning, file_type)
        # Override this method in subclasses for additional behavior
        self.on_file_changed(var, warning, file_type)
    
    def on_file_changed(self, var, warning, file_type):
        """Hook for subclasses to add additional behavior when file changes"""
        pass

    def create_rotation_controls(self, parent, rotation_order, rotate_x, rotate_y, rotate_z):
        """Create rotation controls"""
        rotation_frame = ttk.LabelFrame(parent, text="Поворот модели", padding=5)
        rotation_frame.pack(anchor=tk.W, pady=5, fill=tk.X)
        
        # Rotation order
        order_frame = ttk.Frame(rotation_frame)
        order_frame.pack(anchor=tk.W, pady=5)
        ttk.Label(order_frame, text="Rotation Order:").pack(side=tk.LEFT, padx=(0, 10))
        orders = ["XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"]
        order_combo = ttk.Combobox(order_frame, textvariable=rotation_order, 
                                   values=orders, state="readonly", width=8)
        order_combo.pack(side=tk.LEFT)
        
        # Rotation axes
        for axis, var in [("X", rotate_x), ("Y", rotate_y), ("Z", rotate_z)]:
            axis_frame = ttk.Frame(rotation_frame)
            axis_frame.pack(anchor=tk.W, pady=2)
            ttk.Label(axis_frame, text=f"{axis}:").pack(side=tk.LEFT, padx=(0, 5))
            entry = ttk.Entry(axis_frame, textvariable=var, width=10)
            entry.pack(side=tk.LEFT)
            ttk.Label(axis_frame, text="°").pack(side=tk.LEFT, padx=(0, 10))
        
        return rotation_frame
    
    def browse_file(self, string_var, file_filter):
        """Browse for a file"""
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="Выбрать файл", 
            filetypes=[(file_filter, "*.*")]
        )
        if file_path:
            string_var.set(file_path)
            self.validate_files()
    
    def validate_files(self):
        """Validate all files in the tab"""
        for key, (var, warning, file_type) in self.file_vars.items():
            self.validate_file_exists(var, warning, file_type)

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
            warning_label.config(text="")
            return True

if __name__ == "__main__":
    pass            
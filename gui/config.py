# config.py
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

@dataclass
class AppConfig:
    # Mask tab defaults
    mask_obj_path: str = "objects/T.obj"
    mask_stp_path: str = ""
    radius_input: str = "50"
    mask_outdir: str = None  # Will be set in __post_init__
    
    # Plots tab defaults
    plots_obj_path: str = "out/base/base.obj"
    plots_stp_path: str = "out/base/base.stp"
    mask_path: str = "out/base/accessible_fragment.obj"
    plots_outdir: str = None  # Will be set in __post_init__
    
    # Units and rotation
    units_list: tuple = ('metre', 'centimetre', 'millimetre', 'inches')
    units_var: str = "millimetre"
    rotation_order: str = "XYZ"
    rotate_x: float = 0.0
    rotate_y: float = 0.0
    rotate_z: float = 0.0
    
    # Checkboxes
    paral_var: bool = True
    plots_var: bool = True
    
    # Window settings
    window_title: str = "Расчет молниеопасных зон"
    window_geometry: str = "500x600"
    
    def __post_init__(self):
        if self.mask_outdir is None:
            self.mask_outdir = datetime.now().strftime("%Y-%m-%d-%H-%M")
        if self.plots_outdir is None:
            self.plots_outdir = str(Path(self.mask_path).parent)
    
    def to_dict(self):
        """Convert config to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        """Create config from dictionary"""
        return cls(**data)
    
    def save_to_file(self, filepath: str):
        """Save configuration to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, filepath: str):
        """Load configuration from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
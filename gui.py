# gui_main.py
import sys
import os
from pathlib import Path
from datetime import datetime
import traceback

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                               QFileDialog, QCheckBox, QGroupBox, QTabWidget,
                               QScrollArea, QMessageBox, QProgressBar)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont

import pyvista as pv
import numpy as np
from pathlib import Path
import argparse

from src import find_accessible_surface, load_step, get_accessible_mesh
from src import plot_mesh_with_projections, get_2d_mask, plot_mesh_mask

class WorkerThread(QThread):
    """Worker thread for running calculations without freezing the UI"""
    progress = Signal(str)
    finished = Signal(bool, str)
    
    def __init__(self, task_type, params):
        super().__init__()
        self.task_type = task_type
        self.params = params
        
    def run(self):
        try:
            if self.task_type == "mask":
                self.calculate_mask()
            elif self.task_type == "plots":
                self.generate_plots()
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}\n{traceback.format_exc()}")
    
    def calculate_mask(self):
        self.progress.emit("Starting mask calculation...")
        
        # Prepare output directory
        out_path = Path(os.getcwd()) / "out" / self.params['outdir']
        out_path.mkdir(parents=True, exist_ok=True)
        
        self.progress.emit(f"Loading OBJ file: {self.params['obj']}")
        self.progress.emit(f"Using sphere radius: {self.params['radius']}")
        
        # Calculate mask
        result, centers = find_accessible_surface(
            self.params['obj'], 
            sphere_radius=self.params['radius'], 
            render=self.params['draw'], 
            out_dir=out_path
        )
        
        self.progress.emit("Getting accessible mesh...")
        accessible_mesh = get_accessible_mesh(result)
        
        # Save result
        save_path = out_path / "accessible_fragment.obj"
        accessible_mesh.save(save_path)
        self.progress.emit(f"Saved mask to: {save_path}")
        
        # Generate plots if requested
        if self.params['plots']:
            self.progress.emit("Generating plots...")
            shape = load_step(self.params['stp'])
            plot_mesh_with_projections(accessible_mesh, shape, out_dir=out_path)
            plot_mesh_mask(result, accessible_mesh, out_dir=out_path)
            get_2d_mask(accessible_mesh, out_dir=out_path)
            self.progress.emit(f"Plots saved to: {out_path}")
        
        self.finished.emit(True, out_path)
    
    def generate_plots(self):
        self.progress.emit("Starting plot generation...")
        
        # Prepare output directory
        out_path = Path(os.getcwd()) / "out" / self.params['outdir']
        out_path.mkdir(parents=True, exist_ok=True)
        
        self.progress.emit(f"Loading mesh from: {self.params['obj']}")
        mesh = pv.read(self.params['obj'])
        
        self.progress.emit(f"Loading mask from: {self.params['mask']}")
        mesh_mask = pv.read(self.params['mask'])
        
        self.progress.emit(f"Loading STEP file: {self.params['stp']}")
        shape = load_step(self.params['stp'])
        
        self.progress.emit("Generating plots...")
        plot_mesh_with_projections(mesh_mask, shape, out_dir=out_path)
        plot_mesh_mask(mesh, mesh_mask, out_dir=out_path)
        get_2d_mask(mesh_mask, out_dir=out_path)
        
        self.progress.emit(f"Plots saved to: {out_path}")
        self.finished.emit(True, out_path)


# class ImageDisplayWidget(QWidget):
#     """Widget for displaying generated plot images"""
#     def __init__(self):
#         super().__init__()
#         layout = QVBoxLayout()
        
#         # Create scroll area for images
#         scroll_area = QScrollArea()
#         scroll_area.setWidgetResizable(True)
#         scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
#         scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
#         self.image_container = QWidget()
#         self.image_layout = QVBoxLayout(self.image_container)
#         scroll_area.setWidget(self.image_container)
        
#         layout.addWidget(scroll_area)
#         self.setLayout(layout)
    
#     def load_images_from_directory(self, directory):
#         """Load all PNG images from a directory"""
#         # Clear existing images
#         for i in reversed(range(self.image_layout.count())): 
#             self.image_layout.itemAt(i).widget().setParent(None)
        
#         # Find all PNG files
#         png_files = list(Path(directory).glob("*.png"))
        
#         if not png_files:
#             no_image_label = QLabel("No plot images found in output directory")
#             no_image_label.setAlignment(Qt.AlignCenter)
#             self.image_layout.addWidget(no_image_label)
#             return
        
#         # Add each image to the display
#         for png_file in png_files:
#             frame = QWidget()
#             frame_layout = QVBoxLayout(frame)
            
#             # Image label
#             image_label = QLabel()
#             pixmap = QPixmap(str(png_file))
            
#             # Scale image to fit while maintaining aspect ratio
#             scaled_pixmap = pixmap.scaled(800, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
#             image_label.setPixmap(scaled_pixmap)
#             image_label.setAlignment(Qt.AlignCenter)
            
#             # Filename label
#             name_label = QLabel(png_file.name)
#             name_label.setAlignment(Qt.AlignCenter)
#             name_label.setFont(QFont("Arial", 10))
            
#             frame_layout.addWidget(name_label)
#             frame_layout.addWidget(image_label)
            
#             self.image_layout.addWidget(frame)
            
#             # Add separator
#             separator = QLabel("─" * 100)
#             separator.setAlignment(Qt.AlignCenter)
#             self.image_layout.addWidget(separator)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Mask Calculator and Plot Generator")
        self.setGeometry(100, 100, 400, 400)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel for controls
        left_panel = QWidget()
        left_panel.setMaximumWidth(400)
        left_layout = QVBoxLayout(left_panel)
        
        # Create tab widget for Mask and Plots modes
        self.mode_tabs = QTabWidget()
        self.mask_tab = QWidget()
        self.plots_tab = QWidget()
        self.mode_tabs.addTab(self.mask_tab, "Calculate 3D Mask")
        self.mode_tabs.addTab(self.plots_tab, "Generate Plots")
        
        # Setup mask tab
        self.setup_mask_tab()
        
        # Setup plots tab
        self.setup_plots_tab()
        
        left_layout.addWidget(self.mode_tabs)
        
        # Add Run button
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_task)
        self.run_button.setMinimumHeight(40)
        left_layout.addWidget(self.run_button)
        
        # Add progress display
        self.progress_text = QLabel("Ready")
        self.progress_text.setWordWrap(True)
        self.progress_text.setMaximumHeight(100)
        left_layout.addWidget(self.progress_text)
        
        # # Right panel for image display
        # right_panel = QWidget()
        # right_layout = QVBoxLayout(right_panel)
        
        # Image display widget
        # self.image_display = ImageDisplayWidget()
        # right_layout.addWidget(self.image_display)
        
        # Add panels to main layout
        main_layout.addWidget(left_panel)
        # main_layout.addWidget(right_panel, 1)
        
        # Worker thread
        self.worker = None
        
        # Timer for checking output directory
        # self.check_timer = QTimer()
        # self.check_timer.timeout.connect(self.check_output_directory)
        self.current_output_dir = None
    
    def setup_mask_tab(self):
        layout = QVBoxLayout(self.mask_tab)
        
        # OBJ file
        obj_layout = QHBoxLayout()
        obj_layout.addWidget(QLabel("OBJ File:"))
        self.mask_obj_path = QLineEdit("objects/obt_LG.obj")
        obj_layout.addWidget(self.mask_obj_path)
        obj_btn = QPushButton("Browse")
        obj_btn.clicked.connect(lambda: self.browse_file(self.mask_obj_path, "OBJ files (*.obj)"))
        obj_layout.addWidget(obj_btn)
        layout.addLayout(obj_layout)
        
        # STP file
        stp_layout = QHBoxLayout()
        stp_layout.addWidget(QLabel("STP File:"))
        self.mask_stp_path = QLineEdit("objects/obt_LG.stp")
        stp_layout.addWidget(self.mask_stp_path)
        stp_btn = QPushButton("Browse")
        stp_btn.clicked.connect(lambda: self.browse_file(self.mask_stp_path, "STEP files (*.stp)"))
        stp_layout.addWidget(stp_btn)
        layout.addLayout(stp_layout)
        
        # Radius
        radius_layout = QHBoxLayout()
        radius_layout.addWidget(QLabel("Sphere Radius:"))
        self.radius_input = QLineEdit("50000")
        radius_layout.addWidget(self.radius_input)
        layout.addLayout(radius_layout)
        
        # Output directory
        outdir_layout = QHBoxLayout()
        outdir_layout.addWidget(QLabel("Output Directory:"))
        self.mask_outdir = QLineEdit(datetime.now().strftime("%Y-%m-%d-%H-%M"))
        outdir_layout.addWidget(self.mask_outdir)
        layout.addLayout(outdir_layout)
        
        # Options
        self.draw_checkbox = QCheckBox("Draw sphere during calculation")
        layout.addWidget(self.draw_checkbox)
        
        self.plots_checkbox = QCheckBox("Generate plots automatically")
        self.plots_checkbox.setChecked(True)
        layout.addWidget(self.plots_checkbox)
        
        layout.addStretch()
    
    def setup_plots_tab(self):
        layout = QVBoxLayout(self.plots_tab)
        
        # OBJ file
        obj_layout = QHBoxLayout()
        obj_layout.addWidget(QLabel("OBJ File:"))
        self.plots_obj_path = QLineEdit("objects/base.obj")
        obj_layout.addWidget(self.plots_obj_path)
        obj_btn = QPushButton("Browse")
        obj_btn.clicked.connect(lambda: self.browse_file(self.plots_obj_path, "OBJ files (*.obj)"))
        obj_layout.addWidget(obj_btn)
        layout.addLayout(obj_layout)
        
        # STP file
        stp_layout = QHBoxLayout()
        stp_layout.addWidget(QLabel("STP File:"))
        self.plots_stp_path = QLineEdit("objects/base.stp")
        stp_layout.addWidget(self.plots_stp_path)
        stp_btn = QPushButton("Browse")
        stp_btn.clicked.connect(lambda: self.browse_file(self.plots_stp_path, "STEP files (*.stp)"))
        stp_layout.addWidget(stp_btn)
        layout.addLayout(stp_layout)
        
        # Mask file
        mask_layout = QHBoxLayout()
        mask_layout.addWidget(QLabel("Mask File:"))
        self.mask_path = QLineEdit("")
        mask_layout.addWidget(self.mask_path)
        mask_btn = QPushButton("Browse")
        mask_btn.clicked.connect(lambda: self.browse_file(self.mask_path, "OBJ files (*.obj)"))
        mask_layout.addWidget(mask_btn)
        layout.addLayout(mask_layout)
        
        # Output directory
        outdir_layout = QHBoxLayout()
        outdir_layout.addWidget(QLabel("Output Directory:"))
        self.plots_outdir = QLineEdit(datetime.now().strftime("%Y-%m-%d-%H-%M"))
        outdir_layout.addWidget(self.plots_outdir)
        layout.addLayout(outdir_layout)
        
        layout.addStretch()
    
    def browse_file(self, line_edit, file_filter):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", file_filter)
        if file_path:
            line_edit.setText(file_path)
    
    def browse_directory(self, line_edit):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            line_edit.setText(directory)
    
    def run_task(self):
        # Disable run button during execution
        self.run_button.setEnabled(False)
        self.progress_text.setText("Initializing...")
        
        # Clear existing images
        # self.image_display.image_layout.clear()
        
        # Get parameters based on active tab
        current_tab = self.mode_tabs.currentIndex()
        
        if current_tab == 0:  # Mask tab
            params = {
                'obj': self.mask_obj_path.text(),
                'stp': self.mask_stp_path.text(),
                'radius': float(self.radius_input.text()),
                'draw': self.draw_checkbox.isChecked(),
                'plots': self.plots_checkbox.isChecked(),
                'outdir': self.mask_outdir.text()
            }
            task_type = "mask"
        else:  # Plots tab
            params = {
                'obj': self.plots_obj_path.text(),
                'stp': self.plots_stp_path.text(),
                'mask': self.mask_path.text(),
                'outdir': self.plots_outdir.text()
            }
            task_type = "plots"
        
        # Start worker thread
        self.worker = WorkerThread(task_type, params)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()
    
    def update_progress(self, message):
        self.progress_text.setText(message)
        QApplication.processEvents()
    
    def task_finished(self, success, result):
        self.run_button.setEnabled(True)
        
        if success:
            self.progress_text.setText(f"Task completed successfully! Output saved to: {result}")
            self.current_output_dir = result
            self.check_output_directory()
            QMessageBox.information(self, "Success", f"Task completed successfully!\nOutput saved to: {result}")
        else:
            self.progress_text.setText(f"Task failed: {result}")
            QMessageBox.critical(self, "Error", f"Task failed:\n{result}")
        
        self.worker = None
    
    # def check_output_directory(self):
    #     """Check if output directory exists and load images"""
    #     if self.current_output_dir and Path(self.current_output_dir).exists():
    #         self.image_display.load_images_from_directory(self.current_output_dir)


def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
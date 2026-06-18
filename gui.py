# gui_main.py
import sys
import os
from pathlib import Path
import shutil

import argparse
from datetime import datetime
import traceback

import pyvista as pv
import numpy as np

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                               QFileDialog, QCheckBox, QGroupBox, QTabWidget,
                               QScrollArea, QMessageBox, QProgressBar)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont

from src import find_accessible_surface, find_accessible_surface_parallel, load_step, get_accessible_mesh
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
            elif self.task_type == "show":
                self.show_plot()
        except Exception as e:
            self.finished.emit(False, f"Ошибка: {str(e)}\n{traceback.format_exc()}")
    
    def calculate_mask(self):
        self.progress.emit("Начало расчета маски...")
        
        # Prepare output directory
        out_path = Path(os.getcwd()) / "out" / self.params['outdir']
        out_path.mkdir(parents=True, exist_ok=True)
        
        self.progress.emit(f"Загружается модель (*.obj): {self.params['obj']}")
        self.progress.emit(f"Используется радиус сферы: {self.params['radius']}")
        
        # Calculate mask
        if self.params['paral']:
            result, centers = find_accessible_surface_parallel(
                self.params['obj'], 
                sphere_radius=self.params['radius'], 
                render=self.params['draw'], 
                out_dir=out_path
            )            
        else:
            result, centers = find_accessible_surface(
                self.params['obj'], 
                sphere_radius=self.params['radius'], 
                render=self.params['draw'], 
                out_dir=out_path
            )
                
        accessible_mesh = get_accessible_mesh(result)
        
        # Save result
        save_path = out_path / "accessible_fragment.obj"
        accessible_mesh.save(save_path)
        self.progress.emit(f"Маска сохранена в: {save_path}")

        # Save original files
        save_obj_path = out_path / Path(self.params['obj']).name
        print(save_obj_path)
        shutil.copy(self.params['obj'], save_obj_path)

        save_stp_path = out_path / Path(self.params['stp']).name
        print(save_stp_path)
        shutil.copy(self.params['stp'], save_stp_path)        
        
        # Generate plots if requested
        if self.params['plots']:
            self.progress.emit("Генерация графиков...")
            shape = load_step(self.params['stp'])
            plot_mesh_with_projections(accessible_mesh, shape, out_dir=out_path)
            plot_mesh_mask(result, accessible_mesh, out_dir=out_path)
            get_2d_mask(accessible_mesh, out_dir=out_path)
            self.progress.emit(f"Графики сохранены в: { out_path}")
        
        self.finished.emit(True, str(out_path))
    
    def generate_plots(self):
        self.progress.emit("Начало генерации графиков...")
        
        # Prepare output directory
        out_path = Path(os.getcwd()) / "out" / self.params['outdir']
        out_path.mkdir(parents=True, exist_ok=True)
        
        self.progress.emit(f"Загружается модель (*.obj): {self.params['obj']}")
        mesh = pv.read(self.params['obj'])
        
        self.progress.emit(f"Загружается маска: {self.params['mask']}")
        mesh_mask = pv.read(self.params['mask'])
        
        self.progress.emit(f"Загружается модель (*.stp): {self.params['stp']}")
        shape = load_step(self.params['stp'])
        
        self.progress.emit("Генерация графиков...")
        plot_mesh_with_projections(mesh_mask, shape, out_dir=out_path)
        plot_mesh_mask(mesh, mesh_mask, out_dir=out_path)
        get_2d_mask(mesh_mask, out_dir=out_path)
        
        self.progress.emit(f"Графики сохранены в: {out_path}")
        print(type(out_path))
        self.finished.emit(True, str(out_path))  

    def show_plot(self):          
        self.progress.emit("Начало генерации графиков...")

        self.progress.emit(f"Загружается модель (*.obj): {self.params['obj']}")
        mesh = pv.read(self.params['obj'])
        
        if 'mask' in self.params:
            self.progress.emit(f"Загружена маска из: {self.params['mask']}")
            mesh_mask = pv.read(self.params['mask'])

            self.progress.emit("Генерация графиков...")        
            plot_mesh_mask(mesh, mesh_mask, save=False)
        else:
            self.progress.emit("Генерация графиков...")        
            plot_mesh_mask(mesh, save=False)

        self.progress.emit(f"Графики построены")
        self.finished.emit(True, "")          


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Расчет молниеопасных зон")
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
        self.mode_tabs.addTab(self.mask_tab, "Расчет молниеопасных зон")
        self.mode_tabs.addTab(self.plots_tab, "Построение графиков")

        self.plots_obj_path = QLineEdit("objects/base.obj")
        self.plots_stp_path = QLineEdit("objects/base.stp")
        self.mask_path = QLineEdit("out/base/accessible_fragment.obj")
        self.plots_outdir = QLineEdit( str(Path(self.mask_path.text()).parent) )

        self.mask_obj_path = QLineEdit("objects/obt_LG.obj")
        self.mask_stp_path = QLineEdit("objects/obt_LG.stp")
        self.radius_input = QLineEdit("50000")
        self.mask_outdir = QLineEdit(datetime.now().strftime("%Y-%m-%d-%H-%M"))
        
        # Setup mask tab
        self.setup_mask_tab()
        
        # Setup plots tab
        self.setup_plots_tab()
        
        left_layout.addWidget(self.mode_tabs)
        
        # Add Show button
        self.show_button = QPushButton("Просмотр")
        self.show_button.clicked.connect(self.show_task)
        self.show_button.setMinimumHeight(40)
        left_layout.addWidget(self.show_button)

        # Add Run button
        self.run_button = QPushButton("Запустить")
        self.run_button.clicked.connect(self.run_task)
        self.run_button.setMinimumHeight(40)
        left_layout.addWidget(self.run_button)
        
        # Add progress display
        self.progress_text = QLabel("Готово")
        self.progress_text.setWordWrap(True)
        self.progress_text.setMaximumHeight(100)
        left_layout.addWidget(self.progress_text)
        
        # Add panels to main layout
        main_layout.addWidget(left_panel)

        self.mask_path.textChanged.connect(self.update_mask_path)
        
        # Worker thread
        self.worker = None
        self.current_output_dir = None
    
    def setup_mask_tab(self):
        layout = QVBoxLayout(self.mask_tab)
        
        # OBJ file
        obj_layout = QHBoxLayout()
        obj_layout.addWidget(QLabel("Модель (*.obj):"))        
        obj_layout.addWidget(self.mask_obj_path)
        obj_btn = QPushButton("Найти")
        obj_btn.clicked.connect(lambda: self.browse_file(self.mask_obj_path, "OBJ files (*.obj)"))
        obj_layout.addWidget(obj_btn)
        layout.addLayout(obj_layout)
        
        # STP file
        stp_layout = QHBoxLayout()
        stp_layout.addWidget(QLabel("Модель (*.stp):"))        
        stp_layout.addWidget(self.mask_stp_path)
        stp_btn = QPushButton("Найти")
        stp_btn.clicked.connect(lambda: self.browse_file(self.mask_stp_path, "STEP files (*.stp)"))
        stp_layout.addWidget(stp_btn)
        layout.addLayout(stp_layout)
        
        # Radius
        radius_layout = QHBoxLayout()
        radius_layout.addWidget(QLabel("Радиус сферы:"))        
        radius_layout.addWidget(self.radius_input)
        layout.addLayout(radius_layout)
        
        # Output directory
        outdir_layout = QHBoxLayout()
        outdir_layout.addWidget(QLabel("Директория сохранения:"))
        
        outdir_layout.addWidget(self.mask_outdir)
        layout.addLayout(outdir_layout)
        
        # Options
        self.paral_checkbox = QCheckBox("Включить параллельность")
        layout.addWidget(self.paral_checkbox)

        self.draw_checkbox = QCheckBox("Отобразить сферу")
        layout.addWidget(self.draw_checkbox)
        
        self.plots_checkbox = QCheckBox("Построение графиков")
        self.plots_checkbox.setChecked(True)
        layout.addWidget(self.plots_checkbox)
        
        layout.addStretch()
    
    def setup_plots_tab(self):
        layout = QVBoxLayout(self.plots_tab)
        
        # OBJ file
        obj_layout = QHBoxLayout()
        obj_layout.addWidget(QLabel("Модель (*.obj):"))        
        obj_layout.addWidget(self.plots_obj_path)
        obj_btn = QPushButton("Найти")
        obj_btn.clicked.connect(lambda: self.browse_file(self.plots_obj_path, "OBJ files (*.obj)"))
        obj_layout.addWidget(obj_btn)
        layout.addLayout(obj_layout)
        
        # STP file
        stp_layout = QHBoxLayout()
        stp_layout.addWidget(QLabel("Модель (*.stp):"))        
        stp_layout.addWidget(self.plots_stp_path)
        stp_btn = QPushButton("Найти")
        stp_btn.clicked.connect(lambda: self.browse_file(self.plots_stp_path, "STEP files (*.stp)"))
        stp_layout.addWidget(stp_btn)
        layout.addLayout(stp_layout)
        
        # Mask file
        mask_layout = QHBoxLayout()
        mask_layout.addWidget(QLabel("Маска молниеопасных зон:"))        
        mask_layout.addWidget(self.mask_path)
        mask_btn = QPushButton("Найти")
        mask_btn.clicked.connect(lambda: self.browse_file(self.mask_path, "OBJ files (*.obj)"))
        mask_layout.addWidget(mask_btn)
        layout.addLayout(mask_layout)
        
        # Output directory
        outdir_layout = QHBoxLayout()
        outdir_layout.addWidget(QLabel("Директория сохранения:"))
        
        outdir_layout.addWidget(self.plots_outdir)
        layout.addLayout(outdir_layout)
        
        layout.addStretch()            

    def update_mask_path(self):
        self.plots_outdir.setText( str(Path(self.mask_path.text()).parent) )
        
    
    def browse_file(self, line_edit, file_filter):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбрать файл", "", file_filter)
        if file_path:
            line_edit.setText(file_path)
    
    def browse_directory(self, line_edit):
        directory = QFileDialog.getExistingDirectory(self, "Выбрать директорию")
        if directory:
            line_edit.setText(directory)

    def show_task(self):
        self.show_button.setEnabled(False)
        self.progress_text.setText("Инициализация...")  

        # Get parameters based on active tab
        current_tab = self.mode_tabs.currentIndex()
        
        if current_tab == 0:  
            params = {
                'obj': self.mask_obj_path.text(),
                'stp': self.mask_stp_path.text(),
                'radius': float(self.radius_input.text()),
                'paral': self.paral_checkbox.isChecked(),
                'draw': self.draw_checkbox.isChecked(),
                'plots': self.plots_checkbox.isChecked(),
                'outdir': self.mask_outdir.text()
            }
            task_type = "show"
        else:                
            params = {
                'obj': self.plots_obj_path.text(),
                'stp': self.plots_stp_path.text(),
                'mask': self.mask_path.text(),
                'outdir': self.plots_outdir.text()
            }
            task_type = "show"

        self.worker = WorkerThread(task_type, params)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.show_task_finished)
        self.worker.start()        

            
    def run_task(self):
        # Disable run button during execution
        self.run_button.setEnabled(False)
        self.progress_text.setText("Инициализация...")                
        
        # Get parameters based on active tab
        current_tab = self.mode_tabs.currentIndex()
        
        if current_tab == 0:  # Mask tab
            params = {
                'obj': self.mask_obj_path.text(),
                'stp': self.mask_stp_path.text(),
                'radius': float(self.radius_input.text()),
                'paral': self.paral_checkbox.isChecked(),
                'draw': self.draw_checkbox.isChecked(),
                'plots': self.plots_checkbox.isChecked(),
                'outdir': self.mask_outdir.text()
            }
            task_type = "mask"
        else:                 # Plots tab
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
        print("message ", message)
        self.progress_text.setText(message)
        QApplication.processEvents()
    
    def task_finished(self, success, result):
        self.run_button.setEnabled(True)        
        
        if success:
            self.progress_text.setText(f"Задача выполнена успешно! Результат сохранён в: {result}")
            self.current_output_dir = result
            # self.check_output_directory()
            # QMessageBox.information(self, "Success", f"Задача выполнена успешно!\nРезультат сохранён в: {result}")
        else:
            self.progress_text.setText(f"Задача не выполнена: {result}")
            QMessageBox.critical(self, "Ошибка", f"Задача не выполнена:\n{result}")
        
        self.worker = None

    def show_task_finished(self, success, result):        
        self.show_button.setEnabled(True)
        
        if success:
            self.progress_text.setText(f"Задача выполнена успешно!")
            self.current_output_dir = result
            # self.check_output_directory()
            # QMessageBox.information(self, "Success", f"Задача выполнена успешно!")
        else:
            self.progress_text.setText(f"Задача не выполнена: {result}")
            QMessageBox.critical(self, "Ошибка", f"Задача не выполнена:\n{result}")
        
        self.worker = None


def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
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

from src import find_accessible_surface, find_accessible_surface_parallel, get_accessible_mesh
from src import plot_mesh_with_projections, get_2d_mask, plot_mesh_mask, draw_sphere
from src import load_step, rotate_step_shape

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

        if 'stp' in self.params:
            save_stp_path = out_path / Path(self.params['stp']).name
            print(save_stp_path)
            shutil.copy(self.params['stp'], save_stp_path)        
        
        # Generate plots if requested
        if self.params['plots']:  
            self.progress_callback("Генерация графиков...")      
            draw_sphere(self.params['obj'], self.params['radius'], centers[3], out_dir=out_path)
                        
            plot_mesh_mask(result, accessible_mesh, out_dir=out_path)

            if 'stp' in self.params:
                shape = load_step(self.params['stp'])
                shape = rotate_step_shape(shape, rotation_angles, self.params['rotation_order'])

                plot_mesh_with_projections(accessible_mesh, shape, out_dir=out_path)
                get_2d_mask(accessible_mesh, out_dir=out_path)
            else:
                plot_mesh_with_projections(accessible_mesh, out_dir=out_path)
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
        shape = rotate_step_shape(shape, rotation_angles, self.params['rotation_order'])
        
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

if __name__ == "__main__":
    pass        
import sys
import os
from pathlib import Path
import shutil
import argparse
from datetime import datetime
import traceback

import wx
import wx.lib.mixins.listctrl as listmix
import pyvista as pv
import numpy as np

from src import find_accessible_surface, load_step, get_accessible_mesh
from src import plot_mesh_with_projections, get_2d_mask, plot_mesh_mask

import threading
from queue import Queue
import wx.lib.newevent

# Create custom events for thread communication
ProgressEvent, EVT_PROGRESS = wx.lib.newevent.NewEvent()
FinishedEvent, EVT_FINISHED = wx.lib.newevent.NewEvent()

class WorkerThread(threading.Thread):
    """Worker thread for running calculations without freezing the UI"""
    
    def __init__(self, task_type, params, progress_queue, finished_queue):
        super().__init__()
        self.task_type = task_type
        self.params = params
        self.progress_queue = progress_queue
        self.finished_queue = finished_queue
        
    def run(self):
        try:
            if self.task_type == "mask":
                self.calculate_mask()
            elif self.task_type == "plots":
                self.generate_plots()
            elif self.task_type == "show":
                self.show_plot()
        except Exception as e:
            self.finished_queue.put((False, f"Ошибка: {str(e)}\n{traceback.format_exc()}"))
    
    def calculate_mask(self):
        self.progress_queue.put("Начало расчета маски...")
        
        # Prepare output directory
        out_path = Path(os.getcwd()) / "out" / self.params['outdir']
        out_path.mkdir(parents=True, exist_ok=True)
        
        self.progress_queue.put(f"Загружается модель (*.obj): {self.params['obj']}")
        self.progress_queue.put(f"Используется радиус сферы: {self.params['radius']}")
        
        # Calculate mask
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
        self.progress_queue.put(f"Маска сохранена в: {save_path}")

        # Save original files
        save_obj_path = out_path / Path(self.params['obj']).name
        print(save_obj_path)
        shutil.copy(self.params['obj'], save_obj_path)

        save_stp_path = out_path / Path(self.params['stp']).name
        print(save_stp_path)
        shutil.copy(self.params['stp'], save_stp_path)        
        
        # Generate plots if requested
        if self.params['plots']:
            self.progress_queue.put("Генерация графиков...")
            shape = load_step(self.params['stp'])
            plot_mesh_with_projections(accessible_mesh, shape, out_dir=out_path)
            plot_mesh_mask(result, accessible_mesh, out_dir=out_path)
            get_2d_mask(accessible_mesh, out_dir=out_path)
            self.progress_queue.put(f"Графики сохранены в: {out_path}")
        
        self.finished_queue.put((True, str(out_path)))
    
    def generate_plots(self):
        self.progress_queue.put("Начало генерации графиков...")
        
        # Prepare output directory
        out_path = Path(os.getcwd()) / "out" / self.params['outdir']
        out_path.mkdir(parents=True, exist_ok=True)
        
        self.progress_queue.put(f"Загружается модель (*.obj): {self.params['obj']}")
        mesh = pv.read(self.params['obj'])
        
        self.progress_queue.put(f"Загружается маска: {self.params['mask']}")
        mesh_mask = pv.read(self.params['mask'])
        
        self.progress_queue.put(f"Загружается модель (*.stp): {self.params['stp']}")
        shape = load_step(self.params['stp'])
        
        self.progress_queue.put("Генерация графиков...")
        plot_mesh_with_projections(mesh_mask, shape, out_dir=out_path)
        plot_mesh_mask(mesh, mesh_mask, out_dir=out_path)
        get_2d_mask(mesh_mask, out_dir=out_path)
        
        self.progress_queue.put(f"Графики сохранены в: {out_path}")
        print(type(out_path))
        self.finished_queue.put((True, str(out_path)))  

    def show_plot(self):          
        self.progress_queue.put("Начало генерации графиков...")

        self.progress_queue.put(f"Загружается модель (*.obj): {self.params['obj']}")
        mesh = pv.read(self.params['obj'])
        
        if 'mask' in self.params:
            self.progress_queue.put(f"Загружена маска из: {self.params['mask']}")
            mesh_mask = pv.read(self.params['mask'])

            self.progress_queue.put("Генерация графиков...")        
            plot_mesh_mask(mesh, mesh_mask, save=False)
        else:
            self.progress_queue.put("Генерация графиков...")        
            plot_mesh_mask(mesh, save=False)

        self.progress_queue.put(f"Графики построены")
        self.finished_queue.put((True, ""))


class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Расчет молниеопасных зон", size=(400, 600))
        
        # Create panel and main sizer
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Left panel for controls
        left_panel = wx.Panel(panel)
        left_panel.SetMaxSize(wx.Size(400, -1))
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create notebook for tabs
        self.notebook = wx.Notebook(left_panel)
        
        # Create tabs
        self.mask_tab = wx.Panel(self.notebook)
        self.plots_tab = wx.Panel(self.notebook)
        
        self.notebook.AddPage(self.mask_tab, "Расчет молниеопасных зон")
        self.notebook.AddPage(self.plots_tab, "Построение графиков")
        
        # Initialize controls
        self.plots_obj_path = wx.TextCtrl(self.plots_tab, value="objects/base.obj")
        self.plots_stp_path = wx.TextCtrl(self.plots_tab, value="objects/base.stp")
        self.mask_path = wx.TextCtrl(self.plots_tab, value="out/base/accessible_fragment.obj")
        self.plots_outdir = wx.TextCtrl(self.plots_tab, value=str(Path(self.mask_path.GetValue()).parent))

        self.mask_obj_path = wx.TextCtrl(self.mask_tab, value="objects/obt_LG.obj")
        self.mask_stp_path = wx.TextCtrl(self.mask_tab, value="objects/obt_LG.stp")
        self.radius_input = wx.TextCtrl(self.mask_tab, value="50000")
        self.mask_outdir = wx.TextCtrl(self.mask_tab, value=datetime.now().strftime("%Y-%m-%d-%H-%M"))
        
        # Setup tabs
        self.setup_mask_tab()
        self.setup_plots_tab()
        
        left_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        
        # Add Show button
        self.show_button = wx.Button(left_panel, label="Просмотр", size=(-1, 40))
        self.show_button.Bind(wx.EVT_BUTTON, self.on_show_task)
        left_sizer.Add(self.show_button, 0, wx.EXPAND | wx.ALL, 5)

        # Add Run button
        self.run_button = wx.Button(left_panel, label="Запустить", size=(-1, 40))
        self.run_button.Bind(wx.EVT_BUTTON, self.on_run_task)
        left_sizer.Add(self.run_button, 0, wx.EXPAND | wx.ALL, 5)
        
        # Add progress display
        self.progress_text = wx.StaticText(left_panel, label="Готово", style=wx.ST_NO_AUTORESIZE)
        self.progress_text.Wrap(380)
        left_sizer.Add(self.progress_text, 0, wx.EXPAND | wx.ALL, 5)
        
        # Add progress bar
        self.progress_bar = wx.Gauge(left_panel, range=100, style=wx.GA_HORIZONTAL)
        self.progress_bar.Hide()
        left_sizer.Add(self.progress_bar, 0, wx.EXPAND | wx.ALL, 5)
        
        left_panel.SetSizer(left_sizer)
        
        # Add panels to main sizer
        main_sizer.Add(left_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Right panel for visualization (optional)
        right_panel = wx.Panel(panel)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        right_panel.SetSizer(right_sizer)
        main_sizer.Add(right_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        panel.SetSizer(main_sizer)
        
        # Thread communication
        self.progress_queue = Queue()
        self.finished_queue = Queue()
        self.worker = None
        self.current_output_dir = None
        
        # Bind events
        self.Bind(EVT_PROGRESS, self.on_progress)
        self.Bind(EVT_FINISHED, self.on_finished)
        
        # Timer for checking queues
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.check_queues)
        self.timer.Start(100)  # Check every 100ms
        
        # Bind mask path change event
        self.mask_path.Bind(wx.EVT_TEXT, self.on_mask_path_change)
    
    def setup_mask_tab(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # OBJ file
        obj_sizer = wx.BoxSizer(wx.HORIZONTAL)
        obj_sizer.Add(wx.StaticText(self.mask_tab, label="Модель (*.obj):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        obj_sizer.Add(self.mask_obj_path, 1, wx.EXPAND)
        obj_btn = wx.Button(self.mask_tab, label="Найти", size=(70, -1))
        obj_btn.Bind(wx.EVT_BUTTON, lambda evt: self.browse_file(self.mask_obj_path, "OBJ files (*.obj)|*.obj"))
        obj_sizer.Add(obj_btn, 0, wx.LEFT, 5)
        sizer.Add(obj_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # STP file
        stp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        stp_sizer.Add(wx.StaticText(self.mask_tab, label="Модель (*.stp):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        stp_sizer.Add(self.mask_stp_path, 1, wx.EXPAND)
        stp_btn = wx.Button(self.mask_tab, label="Найти", size=(70, -1))
        stp_btn.Bind(wx.EVT_BUTTON, lambda evt: self.browse_file(self.mask_stp_path, "STEP files (*.stp)|*.stp"))
        stp_sizer.Add(stp_btn, 0, wx.LEFT, 5)
        sizer.Add(stp_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Radius
        radius_sizer = wx.BoxSizer(wx.HORIZONTAL)
        radius_sizer.Add(wx.StaticText(self.mask_tab, label="Радиус сферы:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        radius_sizer.Add(self.radius_input, 1, wx.EXPAND)
        sizer.Add(radius_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Output directory
        outdir_sizer = wx.BoxSizer(wx.HORIZONTAL)
        outdir_sizer.Add(wx.StaticText(self.mask_tab, label="Директория сохранения:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        outdir_sizer.Add(self.mask_outdir, 1, wx.EXPAND)
        sizer.Add(outdir_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Options
        self.draw_checkbox = wx.CheckBox(self.mask_tab, label="Отобразить сферу")
        sizer.Add(self.draw_checkbox, 0, wx.ALL, 5)
        
        self.plots_checkbox = wx.CheckBox(self.mask_tab, label="Построение графиков")
        self.plots_checkbox.SetValue(True)
        sizer.Add(self.plots_checkbox, 0, wx.ALL, 5)
        
        sizer.AddStretchSpacer()
        self.mask_tab.SetSizer(sizer)
    
    def setup_plots_tab(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # OBJ file
        obj_sizer = wx.BoxSizer(wx.HORIZONTAL)
        obj_sizer.Add(wx.StaticText(self.plots_tab, label="Модель (*.obj):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        obj_sizer.Add(self.plots_obj_path, 1, wx.EXPAND)
        obj_btn = wx.Button(self.plots_tab, label="Найти", size=(70, -1))
        obj_btn.Bind(wx.EVT_BUTTON, lambda evt: self.browse_file(self.plots_obj_path, "OBJ files (*.obj)|*.obj"))
        obj_sizer.Add(obj_btn, 0, wx.LEFT, 5)
        sizer.Add(obj_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # STP file
        stp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        stp_sizer.Add(wx.StaticText(self.plots_tab, label="Модель (*.stp):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        stp_sizer.Add(self.plots_stp_path, 1, wx.EXPAND)
        stp_btn = wx.Button(self.plots_tab, label="Найти", size=(70, -1))
        stp_btn.Bind(wx.EVT_BUTTON, lambda evt: self.browse_file(self.plots_stp_path, "STEP files (*.stp)|*.stp"))
        stp_sizer.Add(stp_btn, 0, wx.LEFT, 5)
        sizer.Add(stp_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Mask file
        mask_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mask_sizer.Add(wx.StaticText(self.plots_tab, label="Маска молниеопасных зон:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        mask_sizer.Add(self.mask_path, 1, wx.EXPAND)
        mask_btn = wx.Button(self.plots_tab, label="Найти", size=(70, -1))
        mask_btn.Bind(wx.EVT_BUTTON, lambda evt: self.browse_file(self.mask_path, "OBJ files (*.obj)|*.obj"))
        mask_sizer.Add(mask_btn, 0, wx.LEFT, 5)
        sizer.Add(mask_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Output directory
        outdir_sizer = wx.BoxSizer(wx.HORIZONTAL)
        outdir_sizer.Add(wx.StaticText(self.plots_tab, label="Директория сохранения:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        outdir_sizer.Add(self.plots_outdir, 1, wx.EXPAND)
        sizer.Add(outdir_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        sizer.AddStretchSpacer()
        self.plots_tab.SetSizer(sizer)
    
    def on_mask_path_change(self, event):
        self.plots_outdir.SetValue(str(Path(self.mask_path.GetValue()).parent))
    
    def browse_file(self, text_ctrl, file_filter):
        with wx.FileDialog(self, "Выбрать файл", wildcard=file_filter,
                          style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            pathname = fileDialog.GetPath()
            text_ctrl.SetValue(pathname)
    
    def browse_directory(self, text_ctrl):
        with wx.DirDialog(self, "Выбрать директорию", style=wx.DD_DEFAULT_STYLE) as dirDialog:
            if dirDialog.ShowModal() == wx.ID_CANCEL:
                return
            pathname = dirDialog.GetPath()
            text_ctrl.SetValue(pathname)
    
    def on_show_task(self, event):
        self.show_button.Enable(False)
        self.progress_text.SetLabel("Инициализация...")
        self.progress_bar.Show()
        self.progress_bar.SetValue(0)
        
        # Get parameters based on active tab
        current_tab = self.notebook.GetSelection()
        
        if current_tab == 0:  # Mask tab
            params = {
                'obj': self.mask_obj_path.GetValue(),
                'stp': self.mask_stp_path.GetValue(),
                'radius': float(self.radius_input.GetValue()),
                'draw': self.draw_checkbox.GetValue(),
                'plots': self.plots_checkbox.GetValue(),
                'outdir': self.mask_outdir.GetValue()
            }
            task_type = "show"
        else:  # Plots tab
            params = {
                'obj': self.plots_obj_path.GetValue(),
                'stp': self.plots_stp_path.GetValue(),
                'mask': self.mask_path.GetValue(),
                'outdir': self.plots_outdir.GetValue()
            }
            task_type = "show"
        
        self.start_worker(task_type, params)
    
    def on_run_task(self, event):
        # Disable run button during execution
        self.run_button.Enable(False)
        self.progress_text.SetLabel("Инициализация...")
        self.progress_bar.Show()
        self.progress_bar.SetValue(0)
        
        # Get parameters based on active tab
        current_tab = self.notebook.GetSelection()
        
        if current_tab == 0:  # Mask tab
            params = {
                'obj': self.mask_obj_path.GetValue(),
                'stp': self.mask_stp_path.GetValue(),
                'radius': float(self.radius_input.GetValue()),
                'draw': self.draw_checkbox.GetValue(),
                'plots': self.plots_checkbox.GetValue(),
                'outdir': self.mask_outdir.GetValue()
            }
            task_type = "mask"
        else:  # Plots tab
            params = {
                'obj': self.plots_obj_path.GetValue(),
                'stp': self.plots_stp_path.GetValue(),
                'mask': self.mask_path.GetValue(),
                'outdir': self.plots_outdir.GetValue()
            }
            task_type = "plots"
        
        self.start_worker(task_type, params)
    
    def start_worker(self, task_type, params):
        # Clear queues
        while not self.progress_queue.empty():
            self.progress_queue.get()
        while not self.finished_queue.empty():
            self.finished_queue.get()
        
        # Start worker thread
        self.worker = WorkerThread(task_type, params, self.progress_queue, self.finished_queue)
        self.worker.start()
    
    def check_queues(self, event):
        # Check for progress updates
        while not self.progress_queue.empty():
            try:
                message = self.progress_queue.get_nowait()
                wx.PostEvent(self, ProgressEvent(message=message))
            except:
                break
        
        # Check for finished updates
        while not self.finished_queue.empty():
            try:
                success, result = self.finished_queue.get_nowait()
                wx.PostEvent(self, FinishedEvent(success=success, result=result))
            except:
                break
    
    def on_progress(self, event):
        print("message", event.message)
        self.progress_text.SetLabel(event.message)
        # Update progress bar (increment by 10% for visual feedback)
        current_value = self.progress_bar.GetValue()
        if current_value < 100:
            self.progress_bar.SetValue(min(current_value + 10, 100))
        self.Layout()
    
    def on_finished(self, event):
        if event.success:
            self.progress_text.SetLabel(f"Задача выполнена успешно! Результат сохранён в: {event.result}")
            self.current_output_dir = event.result
            
            # Show success dialog
            wx.MessageBox(f"Задача выполнена успешно!\nРезультат сохранён в: {event.result}", 
                         "Успех", wx.OK | wx.ICON_INFORMATION)
        else:
            self.progress_text.SetLabel(f"Задача не выполнена: {event.result}")
            self.progress_bar.Hide()
            
            # Show error dialog
            wx.MessageBox(f"Задача не выполнена:\n{event.result}", 
                         "Ошибка", wx.OK | wx.ICON_ERROR)
        
        self.run_button.Enable(True)
        self.show_button.Enable(True)
        self.progress_bar.Hide()
        self.worker = None


class MainApp(wx.App):
    def OnInit(self):
        self.frame = MainFrame()
        self.frame.Show(True)
        return True


def main():
    app = MainApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
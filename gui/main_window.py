# main_window.py
import os
import queue
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from gui import MaskTabConfig
from gui import PlotsTabConfig
from gui import AppConfig
from gui import WorkerThread
            
from src import get_step_units

class MainWindow:
    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.settings_dir = Path("settings")
        self.settings_dir.mkdir(exist_ok=True)
        
        self.root = tk.Tk()
        self.root.title("Расчет молниеопасных зон")
        self.root.geometry("500x600")
        
        self._setup_ui()
        self._setup_worker()
        
    def _load_config(self, config_file):
        """Load configuration from file or create default"""
        if config_file and os.path.exists(config_file):
            return AppConfig.load_from_file(config_file)
        return AppConfig()
    
    def _setup_ui(self):
        """Setup the main UI"""
        self.create_menu_bar()
        
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        
        # Create notebook
        self.mode_notebook = ttk.Notebook(left_panel)
        self.mode_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Setup tabs
        self.tabs = {}
        self._setup_tabs()
        
        # Setup buttons
        self._setup_buttons(left_panel)
        
        # Setup progress display
        self._setup_progress_display(left_panel)
        
        # Bind events
        self._bind_events()
    
    def _setup_tabs(self):
        """Setup all tabs"""
        self.mask_tab = MaskTabConfig(self.root, self.config)
        self.mask_tab.setup(self.mode_notebook)
        self.tabs['mask'] = self.mask_tab
        
        self.plots_tab = PlotsTabConfig(self.root, self.config)
        self.plots_tab.setup(self.mode_notebook)
        self.tabs['plots'] = self.plots_tab
        
        # Bind units update
        self.mask_tab.mask_stp_path.trace('w', self._on_stp_path_changed)
        self.mask_tab.combobox.bind('<<ComboboxSelected>>', self._on_units_changed)
    
    def _setup_buttons(self, parent):
        """Setup action buttons"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.show_button = ttk.Button(
            button_frame, text="Просмотр", command=self.show_task
        )
        self.show_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.run_button = ttk.Button(
            button_frame, text="Запустить", command=self.run_task
        )
        self.run_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def _setup_progress_display(self, parent):
        """Setup progress display widgets"""
        self.progress_text = tk.Text(parent, height=10, wrap=tk.WORD)
        self.progress_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(
            self.progress_text, command=self.progress_text.yview
        )
        self.progress_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.progress_bar = ttk.Progressbar(parent, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))
    
    def _setup_worker(self):
        """Setup worker thread and message queue"""
        self.worker = None
        self.message_queue = queue.Queue()
        self._check_queue()
    
    def _bind_events(self):
        """Bind all events"""
        self.mask_tab.mask_stp_path.trace('w', self._on_stp_path_changed)
    
    def _on_stp_path_changed(self, *args):
        """Update units when STP file changes"""
        stp_path = self.mask_tab.mask_stp_path.get()
        if stp_path and os.path.exists(stp_path):
            try:
                step_units = get_step_units(stp_path)
                if step_units and step_units in self.config.units_list:
                    self.mask_tab.units_var.set(step_units)
                else:
                    self.mask_tab.units_var.set("millimetre")
            except Exception as e:
                print(f"Error reading STP units: {e}")
                self.mask_tab.units_var.set("millimetre")
    
    def _on_units_changed(self, *args):
        """Handle units selection change"""
        # Update config when units change
        self.mask_tab.update_config(self.config)
    
    def _get_active_tab(self):
        """Get the active tab configuration"""
        current_index = self.mode_notebook.index(self.mode_notebook.select())
        if current_index == 0:
            return self.mask_tab, "mask"
        else:
            return self.plots_tab, "plots"
    
    def _get_task_params(self, tab, task_type):
        """Get task parameters based on tab and task type"""
        params = tab.get_params()
        
        # Convert radius for mask tab
        if task_type in ["mask", "show"] and hasattr(tab, 'radius_input'):
            radius_value = float(params['radius'])
            params['radius'] = self._convert_to_meters(radius_value)
        
        return params
    
    def _convert_to_meters(self, value):
        """Convert value from current units to meters"""
        unit = self.mask_tab.units_var.get()
        conversion_factors = {
            'metre': 1.0,
            'centimetre': 100,
            'millimetre': 1000,
            'inches': 39.37
        }
        return value * conversion_factors.get(unit, 1000)
    
    def show_task(self):
        self._start_task("show")
    
    def run_task(self):
        self._start_task("mask" if self._get_active_tab()[1] == "mask" else "plots")
    
    def _start_task(self, task_type):
        """Start a task with the given type"""
        self.show_button.config(state=tk.DISABLED)
        self.run_button.config(state=tk.DISABLED)
        self.progress_bar.start()
        self._update_progress("Инициализация...")
        
        tab, tab_name = self._get_active_tab()
        params = self._get_task_params(tab, task_type)
        
        # Update task_type based on tab if needed
        if task_type == "show":
            # Show task uses same params but different worker logic
            pass
        
        self.worker = WorkerThread(
            task_type, params, 
            self._update_progress, 
            self._task_finished
        )
        self.worker.start()
    
    def _update_progress(self, message):
        """Update progress text"""
        self.message_queue.put(("progress", message))
    
    def _task_finished(self, success, result):
        """Handle task completion"""
        self.message_queue.put(("finished", (success, result)))
    
    def _check_queue(self):
        """Check message queue for updates"""
        try:
            while True:
                msg_type, msg_data = self.message_queue.get_nowait()
                
                if msg_type == "progress":
                    self.progress_text.insert(tk.END, msg_data + "\n")
                    self.progress_text.see(tk.END)
                    self.root.update_idletasks()
                
                elif msg_type == "finished":
                    success, result = msg_data
                    self.show_button.config(state=tk.NORMAL)
                    self.run_button.config(state=tk.NORMAL)
                    self.progress_bar.stop()
                    
                    if success:
                        self.progress_text.insert(
                            tk.END, 
                            f"Задача выполнена успешно! Результат сохранён в: {result}\n"
                        )
                        self.progress_text.see(tk.END)
                        if result:
                            messagebox.showinfo(
                                "Успех", 
                                f"Задача выполнена успешно!\nРезультат сохранён в: {result}"
                            )
                    else:
                        self.progress_text.insert(
                            tk.END, 
                            f"Задача не выполнена: {result}\n"
                        )
                        self.progress_text.see(tk.END)
                        messagebox.showerror("Ошибка", f"Задача не выполнена:\n{result}")
                    
                    self.worker = None
        
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._check_queue)
    
    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Сохранить настройки", command=self.save_config, accelerator="Ctrl+S")
        file_menu.add_command(label="Загрузить настройки", command=self.load_config, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Выйти", command=self.root.quit, accelerator="Ctrl+Q")
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)
        
        # Keyboard shortcuts
        self.root.bind('<Control-s>', lambda e: self.save_config())
        self.root.bind('<Control-o>', lambda e: self.load_config())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
    
    def show_about(self):
        messagebox.showinfo(
            "О программе",
            "Расчет молниеопасных зон\n\nВерсия: 1.0\n"
        )
    
    def save_config(self):
        """Save configuration"""
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
                # Update config from all tabs
                for tab in self.tabs.values():
                    tab.update_config(self.config)
                self.config.save_to_file(filepath)
                # messagebox.showinfo("Успех", f"Конфигурация сохранена в:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить конфигурацию:\n{str(e)}")
    
    def load_config(self):
        """Load configuration"""
        filepath = filedialog.askopenfilename(
            title="Загрузить конфигурацию",
            initialdir=str(self.settings_dir),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            try:
                self.config = AppConfig.load_from_file(filepath)
                for tab in self.tabs.values():
                    tab.load_from_config(self.config)
                # messagebox.showinfo("Успех", f"Конфигурация загружена из:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить конфигурацию:\n{str(e)}")
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    pass        
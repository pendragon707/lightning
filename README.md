Export to exe:

```bash
pyinstaller --onefile --add-data "objects:objects" --add-data "src:src" --add-data "out:out" main.py
```

gui:
```bash
pyinstaller --onefile --add-data "objects:objects" --add-data "src:src" --add-data "out:out" gui.py
```

Start gui:
```bash
conda activate occ
python gui.py
```

Модель нужно поверхнуть YXZ, Y=90, X=270

reqs:

```
# first create an environment
conda create --name=pyoccenv python=3.12
conda activate pyoccenv
conda install -c conda-forge pythonocc-core=7.9.3
conda install -c conda-forge open3d
pip install pyvista 
pip install trimesh
pip install scipy
```


pyinstaller --onedir --add-data "objects:objects" --add-data "src:src" --add-data "gui:gui" --add-data "out:out" --add-data "settings:settings" main.py
pyinstaller main.spec

    hiddenimports=[
		'tkinter.ttk',         # <--- ADD THIS
        'tkinter.filedialog',  # <--- Recommended to add this too
        'tkinter.messagebox',  # <--- Recommended to add this too
		'numpy', 
        'scipy', 
        'pyvista',
		'trimesh',
		'open3d',
        'OCC',
        'OCC.Core',
        'OCC.Core.STEPControl',
        'OCC.Core.IFSelect',
        'OCC.Core.TopAbs',
        'OCC.Core.TopLoc',
        'OCC.Core.TopTools',
        'OCC.Core.gp',
        'OCC.Core.BRepBuilderAPI',
        'OCC.Core.BRepTools',
        'OCC.Core.Bnd',
        'OCC.Core.BRepBndLib',
        'OCC.Core.BRepMesh',
        'OCC.Core.BRepPrimAPI',
        'OCC.Core.TopExp',
        'OCC.Core.TopExp_Explorer',
        'OCC.Core.ShapeAnalysis',
        'OCC.Core.ShapeFix',
        'OCC.Core.StlAPI',
        'OCC.Core.UnitsAPI',
        'OCC.Core.Message',
		'OCC.Core.GCPnts',
	],
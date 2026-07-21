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
```
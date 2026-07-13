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


reqs:

```
conda install pythonocc-core
conda install -c conda-forge wxpython
```

```
conda create -n open3d_env python=3.12
conda activate open3d_env
conda install -c conda-forge open3d
```

Модель нужно поверхнуть YXZ, Y=90, X=270
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
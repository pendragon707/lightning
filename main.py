from gui import MainWindow
import multiprocessing

def main():
    multiprocessing.freeze_support()
    app = MainWindow()
    app.run()

if __name__ == "__main__":
    main()
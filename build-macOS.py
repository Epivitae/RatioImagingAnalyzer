/opt/homebrew/bin/python3 -m PyInstaller \
    --noconfirm \
    --onedir \
    --windowed \
    --clean \
    --name "RIA_Liya" \
    --icon "/Users/a1234/Downloads/app.icns" \
    --add-data "assets:assets" \
    --hidden-import "cv2" \
    --hidden-import "numpy" \
    --hidden-import "matplotlib" \
    --hidden-import "tkinter" \
    --hidden-import "PIL" \
    --hidden-import "tifffile" \
    main.py
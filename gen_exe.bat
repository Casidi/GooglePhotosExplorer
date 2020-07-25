pyinstaller --hidden-import pkg_resources.py2_warn -F -w google_photos_gui.py --icon=google-photos.ico
cp google-photos.ico dist/
cp photos_api_secret.json dist/
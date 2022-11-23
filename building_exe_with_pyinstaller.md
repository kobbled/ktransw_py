1. copy `ktransw_py` repo to a temporary location
2. build ktransw
```
pyinstaller --onefile ./bin/ktransw.py
```
3. build kcdictw
```
pyinstaller --onefile ./bin/kcdictw.py
```
4. extract the `.exe` files from the `./dist` folder.
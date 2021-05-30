# xapkInstaller
小米安装xapk需要关闭MIUI优化，但是这样会导致软件的权限设置被重置，被搞烦了，所以就有了这个。。  

环境配置：  

- `*.xapk` : [`adb`](https://dl.google.com/android/repository/platform-tools-latest-windows.zip?hl=zh-cn)   
  - `xapk_version==1 `  
    - `*.apk` ：[`aapt(非必要)`](https://dl.androidaapt.com/aapt-windows.zip)  
    - `*.obb`  
  - `xapk_version==2 `  
- `*.apk` 需要 [`adb`](https://dl.google.com/android/repository/platform-tools-latest-windows.zip?hl=zh-cn), [`aapt(非必要)`](https://dl.androidaapt.com/aapt-windows.zip)  
- `*.aab => *.apks` 需要 `java`, [`bundletool.jar`](https://github.com/google/bundletool/releases)  
- `*.apks` 需要 `java`, [`bundletool.jar`](https://github.com/google/bundletool/releases)  

使用以下语句进行编译：  
```powershell
pyinstaller -F xapkInstaller.py -n xapkInstaller4win.exe
```
或下载已编译好的[最新版本](https://github.com/adhu2018/xapkInstaller/releases/latest)。  

使用方法：  
- 直接拖拽（推荐）：将需要安装的一个或多个文件（夹）拖向xapkInstaller即可。  
- 命令行：xapkInstaller后添加需要安装的文件（夹），添加多个时使用空格隔开。  

文件夹指xapk的解压文件夹。  

经过将近一个月的迭代更新，现已支持各种常见的安装包格式(`aab`, `apk`, `apks`, `xapk`)！  

如果你有见过其他格式的安装包或者在使用过程中出现了问题，请[提交issues](https://github.com/adhu2018/xapkInstaller/issues/new)。  

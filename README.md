# xapkInstaller
小米安装xapk需要关闭MIUI优化，但是这样会导致软件的权限设置被重置，被搞烦了，所以就有了这个。。  

使用以下语句进行编译：
```powershell
pyinstaller -F xapkInstaller.py -n xapkInstaller4win.exe
```

使用方法：
- 直接拖拽（推荐）：将需要安装的一个或多个文件（夹）拖向xapkInstaller即可。
- 命令行：xapkInstaller后添加需要安装的文件（夹），添加多个时使用空格隔开。

文件夹指xapk的解压文件夹。

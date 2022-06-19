# xapkInstaller
小米安装xapk需要关闭MIUI优化，但是这样会导致软件的权限设置被重置，被搞烦了，所以就有了这个。。  

身在福中不知福。。 [SAI](https://github.com/Aefyr/SAI) 是支持 [Shizuku](https://github.com/RikkaApps/Shizuku) 模式的，本项目将停止维护。  

环境配置：  

- `*.xapk` : [`adb`](https://dl.google.com/android/repository/platform-tools-latest-windows.zip?hl=zh-cn)   
  - `xapk_version==1 `  
    - `*.apk` ：[`aapt(非必要)`](https://dl.androidaapt.com/aapt-windows.zip)  
    - `*.obb`  
  - `xapk_version==2 `  
- `*.apk` 需要 `adb`, `aapt(非必要)`  
- `*.aab => *.apks` 需要 `java`, [`bundletool.jar`](https://github.com/google/bundletool/releases)  
- `*.apkm` 需要 `adb`  
- `*.apks` 需要 `java`, `bundletool.jar`  

编译：Windows下直接运行`build.bat`，需要python环境。  
或下载[已编译版本](https://github.com/adhu2018/xapkInstaller/releases/latest)。  

使用方法：  
- 设置默认打开方式（推荐）：选中安装包，右键，打开方式，选择其他应用，找到xapkInstaller。下次直接双击安装包就行了。  
- 命令行：xapkInstaller后添加需要安装的文件（夹），添加多个时使用空格隔开。  

文件夹指xapk的解压文件夹。  

支持的安装包格式：

- [x] `aab` 
- [x] `apk ` 
- [x] `apkm` 
- [x] `apks ` 
- [x] `xapk` 

不支持各种增量更新包。  

如果你有见过其他格式的安装包或者在使用过程中出现了问题，请[提交issues](https://github.com/adhu2018/xapkInstaller/issues/new)。  

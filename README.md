# xapkInstaller

### 简介

小米安装xapk需要关闭MIUI优化，但是这样会导致软件的权限设置被重置，被搞烦了，所以就有了这个。。  

> 推荐：[Termux](https://github.com/termux/termux-app) 可通过 `pkg install android-tools` 安装adb。粗略尝试了一下，可以正常使用本项目

> 推荐：[SAI](https://github.com/Aefyr/SAI) 支持 [Shizuku](https://github.com/RikkaApps/Shizuku) 模式，可以在手机上完成整个安装流程

### 使用环境

- `*.xapk` : [`adb`](https://dl.google.com/android/repository/platform-tools-latest-windows.zip?hl=zh-cn)   
  - `xapk_version==1`  
    - `*.apk` ：[`aapt(非必要)`](https://dl.androidaapt.com/aapt-windows.zip)  
    - `*.obb`  
  - `xapk_version==2`  
- `*.apk` : `adb`, `aapt(非必要)`  
- `*.aab => *.apks` : `java`, [`bundletool.jar`](https://github.com/google/bundletool/releases)  
- `*.apkm` : `adb`  
- `*.apks`  
  - 标准apks(以下二选一)  
    - `adb`  
    - `java`, `bundletool.jar`  
  - 由SAI生成的apks  
    - `adb`   

### 编译

- 本地编译：Windows下直接运行`build.bat`，需要 python 3.11 环境。  
- 在线编译： [Actions](https://github.com/adhu2018/xapkInstaller/actions) 。

或下载[已编译版本](https://github.com/adhu2018/xapkInstaller/releases/latest)。  

> `Releases` 中由 `github-actions` 发布的版本为 [actions](https://github.com/adhu2018/xapkInstaller/actions) 自动编译发布，有问题请[反馈](https://github.com/adhu2018/xapkInstaller/issues/new)，如果还有后续版本，将会以这种形式发布。

### 使用

- 设置默认打开方式（推荐）：选中安装包，右键，打开方式，选择其他应用，找到xapkInstaller。下次直接双击安装包就行了。  
- 命令行：xapkInstaller后添加需要安装的文件（夹），添加多个时使用空格隔开。  

文件夹指xapk的解压文件夹。  

### 适用范围

支持的安装包格式：

- [x] `aab` 
- [x] `apk ` 
- [x] `apkm` 
- [x] `apks ` 
- [x] `xapk` 

不支持各种增量更新包。  

### 反馈

如果你有见过其他格式的安装包或者在使用过程中出现了问题，请[提交issues](https://github.com/adhu2018/xapkInstaller/issues/new)。使用了 logging 记录运行日志，反馈时可选择附上对应日志，**安装文件路径可能会包含敏感信息**，如果有，请先进行处理！  

import json
import os
import shutil
import subprocess
import sys
import traceback


def unpack(file_path):
    """解压xapk文件"""
    (dir_path, name_suffix) = os.path.split(file_path)
    (name, suffix) = os.path.splitext(name_suffix)
    unpack_path = os.path.join(dir_path, name)
    shutil.unpack_archive(file_path, unpack_path, "zip")
    return unpack_path

def uninstall_xapk(file_path):
    package_name = read_manifest("manifest.json")["package_name"]
    uninstall = ["adb", "uninstall", package_name]
    print(uninstall)
    return subprocess.call(uninstall, shell=True)

def install_apk(file_path):
    """安装apk文件"""
    print(install)
    return subprocess.call(["adb", "install", "-rtd", file_path], shell=True)
    
def read_manifest(manifest_path):
    with open(manifest_path, "r", encoding="utf8") as f:
        data = f.read()
    return json.loads(data)

def install_xapk(file_path):
    """安装xapk文件"""
    os.chdir(file_path)
    split_apks = read_manifest("manifest.json")["split_apks"]
    install = ["adb", "install-multiple", "-rtd"]
    other_language = ["config.ar", "config.de", "config.en", "config.es", "config.fr", 
        "config.hi", "config.in", "config.it", "config.ja", "config.ko",
        "config.my", "config.pt", "config.ru", "config.th", "config.tr", 
        "config.vi"]
    other_dpi = ["config.tvdpi"]
    other = ["extra_icu", "feedv2", "vr"]  # Google Chrome
    
    v8a = v7a = xhdpi = xxhdpi = xxxhdpi = t = None
    for i in split_apks:
        if i["id"]=="config.arm64_v8a": v8a = i["file"]
        elif i["id"]=="config.armeabi_v7a": v7a = i["file"]
        elif i["id"]=="config.xhdpi": xhdpi = i["file"]
        elif i["id"]=="config.xxhdpi": xxhdpi = i["file"]
        elif i["id"]=="config.xxxhdpi": xxxhdpi = i["file"]
        elif i["id"] in other_language: pass
        elif i["id"] in other_dpi: pass
        elif i["id"] in other: pass
        else: install.append(i["file"])
    
    if v7a: t = v7a
    if v8a: t = v8a
    if t: install.append(t)
    
    t = None
    if xxxhdpi: t = xxhdpi
    if xxhdpi: t = xxhdpi
    if xhdpi: t = xhdpi
    if t: install.append(t)
    
    print(install)
    return subprocess.call(install, shell=True)


if __name__ == "__main__":
    app = sys.argv[1]
    try:
        if app.endswith(".apk"):
            install_apk(app)
        elif app.endswith(".xapk"):
            unzip_path = unpack(app)
            install_xapk(unzip_path)
        elif os.path.isdir(app):
            if install_xapk(app):
                if input("安装失败！将尝试卸载后再安装，是否继续？(yes/no)").lower()=="yes":
                    uninstall_xapk(app)
                    install_xapk(app)
                else:
                    print("安装已取消！")
        elif app.endswith(".apks"):
            print("apks因为没有遇到过，暂时没有适配，请提供文件进行适配！")
        else:
            print(f"{app!r}不是`apk/xapk`安装包或者`xapk`安装包的解压路径！")
    except Exception as err:
        exc_type, exc_value, exc_obj = sys.exc_info()
        traceback.print_tb(exc_obj)
        print(f"{err!r}")
    os.system("pause")

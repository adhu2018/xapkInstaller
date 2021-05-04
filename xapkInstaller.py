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

def install_apk(file_path):
    """安装apk文件"""
    subprocess.call(["adb", "install", "-r", file_path], shell=True)
    
def read_manifest(manifest_path):
    with open(manifest_path, "r", encoding="utf8") as f:
        data = f.read()
    return json.loads(data)

def install_xapk(file_path):
    """安装xapk文件"""
    pass


if __name__ == "__main__":
    app = sys.argv[1]
    try:
        if app.endswith(".apk"):
            install_apk(app)
        elif app.endswith(".xapk"):
            unzip_path = unpack(app)
            install_xapk(unzip_path)
        elif os.path.isdir(app):
            install_xapk(app)
        elif app.endswith(".apks"):
            print("apks因为没有遇到过，暂时没有适配，请提供文件进行适配！")
        else:
            print(f"{app!r}不是`xapk`安装包！")
    except Exception as err:
        exc_type, exc_value, exc_obj = sys.exc_info()
        traceback.print_tb(exc_obj)
        print(f"{err!r}")
    os.system("pause")

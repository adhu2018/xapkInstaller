# -*- coding: utf-8 -*-
import chardet
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback


tostr = lambda bytes_: bytes_.decode(chardet.detect(bytes_)["encoding"])

def md5(*_str):
    if len(_str) > 0:
        t = _str[0]
        if type(t) is not str:
            t = str(t)
        encode_type = "utf-8"
        if len(_str) > 1:
            encode_type = _str[1]
        m = hashlib.md5()
        try:
            t = t.encode(encode_type)
        except LookupError:
            t = t.encode("utf-8")
        m.update(t)
        return m.hexdigest()
    else:
        print("缺少参数！")
        return False

class Device:
    def __init__(self):
        self._sdk = None
    
    @property
    def abi(self):
        return os.popen("adb shell getprop ro.product.cpu.abi").read().strip()
    
    @property
    def abilist(self):
        return os.popen("adb shell getprop ro.product.cpu.abilist").read().strip().split(",")
    
    @property
    def locale(self):
        return os.popen("adb shell getprop ro.product.locale").read().strip()
    
    @property
    def sdk(self):
        if not self._sdk: self.getsdk()
        return self._sdk
    
    def getsdk(self):
        self._sdk = os.popen("adb shell getprop ro.build.version.sdk").read().strip()
        if not self._sdk:
            self._sdk = os.popen("adb shell getprop ro.product.build.version.sdk").read().strip()
        if not self._sdk:
            self._sdk = os.popen("adb shell getprop ro.system.build.version.sdk").read().strip()
        if not self._sdk:
            self._sdk = os.popen("adb shell getprop ro.system_ext.build.version.sdk").read().strip()
        self._sdk = int(self._sdk)
        return self._sdk


def unpack(file_path):
    """解压xapk文件"""
    dir_path, name_suffix = os.path.split(file_path)
    name, suffix = os.path.splitext(name_suffix)
    unpack_path = os.path.join(dir_path, name)
    shutil.unpack_archive(file_path, unpack_path, "zip")
    os.chdir(unpack_path)
    return unpack_path

def uninstall_xapk(file_path):
    package_name = read_manifest("manifest.json")["package_name"]
    uninstall = ["adb", "uninstall", package_name]
    # 卸载应用时尝试保留应用数据和缓存数据，但是这样处理后只能先安装相同包名的软件再正常卸载才能清除数据！！
    # uninstall = ["adb", "shell", "pm", "uninstall", "-k", package_name]
    return subprocess.run(uninstall, shell=True)

def install_apk(file_path, abc="-rtd"):
    """安装apk文件"""
    name_suffix, run = dump(file_path)
    for line in tostr(run.stdout).split("\n"):
        if "sdkVersion:" in line:
            min_sdk_version = int(line.strip().split("'")[1])
        elif "targetSdkVersion:" in line:
            target_sdk_version = int(line.strip().split("'")[1])
        elif "native-code:" in line: native_code = line
    
    device = Device()
    if device.sdk < min_sdk_version:
        print("安卓版本过低！")
        return None, 0
    
    try:
        if device.sdk > target_sdk_version:
            print("安卓版本过高！可能存在兼容性问题！")
            # return None, 0
    except:
        pass
    
    abilist = device.abilist
    
    try:
        def findabi(native_code):
            for i in abilist:
                if i in native_code: return True
            return False
        if native_code and not findabi(native_code):
            print(f"{native_code}\n应用程序二进制接口(abi)不匹配！该手机支持的abi列表为：{abilist}")
            return None, 0
    except UnboundLocalError:
        pass
    
    install = ["adb", "install", abc, name_suffix]
    status = subprocess.call(install, shell=True)
    if status:  # No argument expected after "-rtd"
        install_apk(file_path, "-r")
    return install, status

def install_apks(file_path):
    # java -jar bundletool.jar install-apks --apks=test.apks
    # https://github.com/google/bundletool/releases
    print("apks因为没有遇到过，暂时没有适配，请提供文件进行适配！")
    
def read_manifest(manifest_path):
    with open(manifest_path, "rb") as f:
        data = f.read()
    return json.loads(tostr(data))

def install_xapk(file_path):
    """安装xapk文件"""
    os.chdir(file_path)
    if not os.path.isfile("manifest.json"):
        print(f"{file_path!r}不是`xapk`安装包的解压路径！")
        sys.exit(1)
    manifest = read_manifest("manifest.json")
    if manifest["xapk_version"]==2:
        split_apks = manifest["split_apks"]
        
        device = Device()
        if device.sdk < int(manifest["min_sdk_version"]):
            print("安卓版本过低！")
            return None, 0
        
        if device.sdk > int(manifest["target_sdk_version"]):
            print("安卓版本过高！可能存在兼容性问题！")
            # return None, 0
        
        install = ["adb", "install-multiple", "-rtd"]
        other_language = ["config.ar", "config.de", "config.en", "config.es", "config.fr", 
            "config.hi", "config.in", "config.it", "config.ja", "config.ko",
            "config.my", "config.pt", "config.ru", "config.th", "config.tr", 
            "config.vi", "config.zh"]
        other = ["extra_icu", "feedv2", "vr"]  # Google Chrome
        
        config = {}
        for i in split_apks:
            if i["id"]==f"config.{device.abi.replace('-', '_')}": config["abi"] = i["file"]
            elif i["id"]==f"config.{device.locale.split('-')[0]}": config["locale"] = i["file"]
            elif i["id"]=="config.arm64_v8a": config["arm64-v8a"] = i["file"]
            elif i["id"]=="config.armeabi_v7a": config["armeabi-v7a"] = i["file"]
            elif i["id"]=="config.xhdpi": config["xhdpi"] = i["file"]
            elif i["id"]=="config.xxhdpi": config["xxhdpi"] = i["file"]
            elif i["id"]=="config.xxxhdpi": config["xxxhdpi"] = i["file"]
            elif i["id"]=="config.tvdpi": config["tvdpi"] = i["file"]
            elif i["id"] in other_language: pass
            elif i["id"] in other: pass
            else: install.append(i["file"])
        
        if config.get("abi"):
            install.append(config["abi"])
        else:
            for i in device.abilist:
                if config.get(i):
                    install.append(config[i])
                    break
        for i in ["xhdpi", "xxhdpi", "xxxhdpi", "tvdpi"]:
            if config.get(i):
                install.append(config[i])
                break
        if config.get("locale"): install.append(config["locale"])
        
        return install, subprocess.call(install, shell=True)
    elif manifest["xapk_version"]==1:
        install, _ = install_apk(manifest["package_name"]+".apk")
        expansions = manifest["expansions"]
        for i in expansions:
            if i["install_location"]=="EXTERNAL_STORAGE":
                push = ["adb", "push", i["file"], "/storage/emulated/0/"+i["install_path"]]
                return [install, push], subprocess.call(push, shell=True)
            else:
                raise Exception("未知错误！")

def dump(file_path):
    _, name_suffix = os.path.split(file_path)
    if " " in name_suffix:
        copy = ["copy", name_suffix, name_suffix.replace(" ", "")]
        subprocess.run(copy, shell=True)
        name_suffix = copy[2]
    cmd = ["aapt", "dump", "badging", name_suffix]
    run = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run.stderr: print(tostr(run.stderr))
    if run.stdout: print(tostr(run.stdout))
    if run.returncode:
        os.system("pause")
        sys.exit(1)
    return name_suffix, run

def check(root, del_path):
    run = subprocess.run("adb devices", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    devices = len(tostr(run.stdout).strip().split("\n")[1:])
    
    if run.returncode: print(run.stderr)
    elif devices==0: print("手机未连接电脑！")
    elif devices==1: return
    elif devices>1: print("设备过多！")
    
    del_exit(root, del_path)
    
def delPath(path):
    if not os.path.exists(path): return
    print(f"delete    {path}")
    if os.path.isfile(path): return os.remove(path)
    return shutil.rmtree(path)

def del_exit(root, del_path):
    os.chdir(root)
    for i in del_path: delPath(i)
    os.system("pause")
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv)<2:
        print("缺少参数！")
        print("xapkInstaller <apk路径|xapk路径|xapk解压路径>")
        print("例如：")
        print("    xapkInstaller abc.apk")
        print("    xapkInstaller abc.xapk")
        print("    xapkInstaller ./abc/")
        os.system("pause")
        sys.exit(0)
    
    root, _ = os.path.split(sys.argv[0])
    _, name_suffix = os.path.split(sys.argv[1])
    del_path = [os.path.join(root, name_suffix)]
    copy = ["copy", sys.argv[1], del_path[0]]
    print(copy)
    if copy[1]==copy[2]:
        del del_path[0]
    else:
        if os.path.exists(copy[2]):
            delPath(copy[2])
        if os.path.isfile(copy[1]):
            subprocess.run(copy, shell=True)
        else:
            shutil.copytree(copy[1], copy[2])
    
    check(root, del_path)
    
    try:
        if copy[2].endswith(".apk"):
            install_apk(copy[2])
        elif copy[2].endswith(".xapk"):
            del_path.append(unpack(copy[2]))
        elif copy[2].endswith(".apks"):
            install_apks(copy[2])
        elif copy[2].endswith(".aab"):
            print("生成apks文件比较麻烦，暂时不考虑适配！")
            sys.exit(1)
        elif os.path.isfile(copy[2]):
            print(f"{copy[2]!r}不是`apk/xapk/apks`安装包！")
            sys.exit(1)
        
        if os.path.isdir(del_path[-1]):
            os.chdir(del_path[-1])
            install, status = install_xapk(del_path[-1])
            if status:
                if input("安装失败！将尝试卸载后再安装，会导致数据丢失！是否继续？(yes/no)").lower()=="yes":
                    uninstall_xapk(del_path[-1])
                    if len(install)==2:
                        subprocess.run(install[0], shell=True)
                        subprocess.run(install[1], shell=True)
                    else:
                        subprocess.run(install, shell=True)
                else:
                    print("安装已取消！")
                    sys.exit(1)
    except Exception as err:
        exc_type, exc_value, exc_obj = sys.exc_info()
        traceback.print_tb(exc_obj)
        print(f"{err!r}")
    finally:
        del_exit(root, del_path)

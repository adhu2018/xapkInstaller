# -*- coding: utf-8 -*-
import chardet
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
import xml.dom.minidom as minidom
from axmlparserpy import axmlprinter


tostr = lambda bytes_: bytes_.decode(chardet.detect(bytes_)["encoding"])

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

def check(root, del_path):
    run = subprocess.run("adb devices", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    devices = len(tostr(run.stdout).strip().split("\n")[1:])
    
    if run.returncode: print(run.stderr)
    elif devices==0: print("安装失败：手机未连接电脑！")
    elif devices==1: return
    elif devices>1: print("安装失败：设备过多！暂不支持多设备情况下进行安装！")
    
    sys.exit(1)

def delPath(path):
    if not os.path.exists(path): return
    print(f"删除    {path}")
    if os.path.isfile(path): return os.remove(path)
    return shutil.rmtree(path)

def dump(file_path, del_path):
    cmd = ["aapt", "dump", "badging", file_path]
    run = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run.stderr: print(tostr(run.stderr))
    if run.stdout: print(tostr(run.stdout))
    if run.returncode: return dump_py(file_path, del_path)
    manifest = {}
    manifest["native_code"] = []
    for line in tostr(run.stdout).split("\n"):
        if "sdkVersion:" in line:
            manifest["min_sdk_version"] = int(line.strip().split("'")[1])
        elif "targetSdkVersion:" in line:
            manifest["target_sdk_version"] = int(line.strip().split("'")[1])
        elif "native-code:" in line: manifest["native_code"].append(line.split("'")[1])
        elif "package: name=" in line: manifest["package_name"] = line.split("'")[1]
    return manifest

def dump_py(file_path, del_path):
    unpack_path = unpack(file_path)
    del_path.append(unpack_path)
    with open(os.path.join(unpack_path, "AndroidManifest.xml"), "rb") as f:
        data = f.read()
    ap = axmlprinter.AXMLPrinter(data)
    buff = minidom.parseString(ap.getBuff())
    manifest = {}
    manifest["package_name"] = buff.getElementsByTagName("manifest")[0].getAttribute("package")
    manifest["min_sdk_version"] = int(buff.getElementsByTagName("uses-sdk")[0].getAttribute("android:minSdkVersion"))
    try:
        manifest["target_sdk_version"] = int(buff.getElementsByTagName("uses-sdk")[0].getAttribute("android:targetSdkVersion"))
    except:
        pass
    try:
        manifest["native_code"] = os.listdir(os.path.join(unpack_path, "lib"))
    except:
        pass
    return manifest

def install_apk(file_path, del_path, abc="-rtd"):
    """安装apk文件"""
    _, name_suffix = os.path.split(file_path)
    manifest = dump(name_suffix, del_path)
    
    device = Device()
    if device.sdk < manifest["min_sdk_version"]:
        print("安装失败：安卓版本过低！")
        sys.exit(1)
    
    try:
        if device.sdk > manifest["target_sdk_version"]:
            print("警告：安卓版本过高！可能存在兼容性问题！")
    except:
        pass
    
    abilist = device.abilist
    
    try:
        def findabi(native_code):
            for i in abilist:
                if i in native_code: return True
            return False
        if manifest.get("native_code") and not findabi(manifest["native_code"]):
            print(f"安装失败：{manifest['native_code']}\n应用程序二进制接口(abi)不匹配！该手机支持的abi列表为：{abilist}")
            sys.exit(1)
    except UnboundLocalError:
        pass
    
    install = ["adb", "install", abc, name_suffix]
    status = subprocess.call(install, shell=True)
    if status:
        # No argument expected after "-rtd"
        if abc=="-rtd": return install_apk(file_path, del_path, "-r")
        elif abc=="-r":
            uninstall = ["adb", "shell", "pm", "uninstall", "-k", manifest["package_name"]]
            subprocess.run(uninstall, shell=True)
            return install_apk(file_path, del_path, "")
        else:
            sys.exit(1)
    return install, status

def install_apks(file_path):
    # java -jar bundletool.jar install-apks --apks=test.apks
    # https://github.com/google/bundletool/releases
    print("安装失败：apks因为没有遇到过，暂时没有适配，请提供文件进行适配！")

def install_xapk(file_path, del_path):
    """安装xapk文件"""
    os.chdir(file_path)
    if not os.path.isfile("manifest.json"):
        print(f"安装失败：路径中没有`manifest.json`。{file_path!r}不是`xapk`安装包的解压路径！")
        sys.exit(1)
    manifest = read_manifest("manifest.json")
    if manifest["xapk_version"]==2:
        split_apks = manifest["split_apks"]
        
        device = Device()
        if device.sdk < int(manifest["min_sdk_version"]):
            print("安装失败：安卓版本过低！")
            sys.exit(1)
        
        if device.sdk > int(manifest["target_sdk_version"]):
            print("警告：安卓版本过高！可能存在兼容性问题！")
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
        install, _ = install_apk(manifest["package_name"]+".apk", del_path)
        expansions = manifest["expansions"]
        for i in expansions:
            if i["install_location"]=="EXTERNAL_STORAGE":
                push = ["adb", "push", i["file"], "/storage/emulated/0/"+i["install_path"]]
                return [install, push], subprocess.call(push, shell=True)
            else:
                raise Exception("安装失败：未知错误！请提供文件进行适配！")

def main(root, one):
    _, name_suffix = os.path.split(one)
    name_suffix = name_suffix.rsplit(".", 1)
    new_path = md5(name_suffix[0])
    if len(name_suffix)>1:
        new_path += f".{name_suffix[1]}"
    del_path = [os.path.join(root, new_path)]
    copy = [one, del_path[0]]
    print(f"正在复制 `{one}` 到 `{del_path[0]}`")
    if os.path.exists(copy[1]):
        delPath(copy[1])
    if os.path.isfile(copy[0]):
        shutil.copyfile(copy[0], copy[1])
    else:
        shutil.copytree(copy[0], copy[1])
    
    try:
        check(root, del_path)
        if copy[1].endswith(".apk"):
            if not install_apk(copy[1], del_path)[0]: sys.exit(1)
        elif copy[1].endswith(".xapk"):
            del_path.append(unpack(copy[1]))
            os.chdir(del_path[-1])
        elif copy[1].endswith(".apks"):
            install_apks(copy[1])
        elif copy[1].endswith(".aab"):
            print("生成apks文件比较麻烦，暂时不考虑适配！")
            sys.exit(1)
        elif os.path.isfile(copy[1]):
            print(f"{copy[1]!r}不是`apk/xapk/apks`安装包！")
            sys.exit(1)
        
        if os.path.isdir(del_path[-1]):
            os.chdir(del_path[-1])
            install, status = install_xapk(del_path[-1], del_path)
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
        return True
    except SystemExit:
        return False
    except Exception:
        traceback.print_exc(limit=2, file=sys.stdout)
        return False
    finally:
        os.chdir(root)
        for i in del_path: delPath(i)

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

def read_manifest(manifest_path):
    with open(manifest_path, "rb") as f:
        data = f.read()
    return json.loads(tostr(data))

def uninstall_xapk(file_path):
    package_name = read_manifest("manifest.json")["package_name"]
    # uninstall = ["adb", "uninstall", package_name]
    # 卸载应用时尝试保留应用数据和缓存数据，但是这样处理后只能先安装相同包名的软件再正常卸载才能清除数据！！
    uninstall = ["adb", "shell", "pm", "uninstall", "-k", package_name]
    return subprocess.run(uninstall, shell=True)

def unpack(file_path):
    """解压文件"""
    print("文件越大，解压越慢，请耐心等待...")
    dir_path, name_suffix = os.path.split(file_path)
    name, suffix = os.path.splitext(name_suffix)
    unpack_path = os.path.join(dir_path, name)
    shutil.unpack_archive(file_path, unpack_path, "zip")
    return unpack_path


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
    if not root: root = os.getcwd()
    _len_ = len(sys.argv[1:])
    success = 0
    try:
        for i, one in enumerate(sys.argv[1:]):
            print(f"正在安装第{i+1}/{_len_}个...")
            if main(root, one): success += 1
    except Exception:
        traceback.print_exc(limit=2, file=sys.stdout)
    finally:
        print(f"共{_len_}个，成功安装了{success}个。")
        os.system("pause")
        sys.exit(0)
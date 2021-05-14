import json
import os
import shutil
import subprocess
import sys
import traceback


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
    for line in run.stdout.split("\n"):
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
    with open(manifest_path, "r", encoding="utf8") as f:
        data = f.read()
    return json.loads(data)

def install_xapk(file_path):
    """安装xapk文件"""
    os.chdir(file_path)
    if not os.path.isfile("manifest.json"):
        print(f"{file_path!r}不是`xapk`安装包的解压路径！")
        os.system("pause")
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
        
        if not config.get("abi"):
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
        install, status = install_apk(manifest["package_name"]+".apk")
        expansions = manifest["expansions"]
        for i in expansions:
            if i["install_location"]=="EXTERNAL_STORAGE":
                push = ["adb", "push", i["file"], "/storage/emulated/0/"+i["install_path"]]
                return [install, push], subprocess.call(push, shell=True)
            else:
                raise Exception("未知错误！")

def dump(file_path):
    if os.path.isabs(file_path):
        dir_path, name_suffix = os.path.split(file_path)
        os.chdir(dir_path)
    else:
        name_suffix = file_path
    if " " in name_suffix:
        copy = ["copy", name_suffix, name_suffix.replace(" ", "")]
        subprocess.run(copy, shell=True)
        name_suffix = copy[2]
    cmd = ["aapt", "dump", "badging", name_suffix]
    run = subprocess.run(cmd, shell=True, encoding="utf8", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run.returncode:
        print(run.stderr)
        os.system("pause")
        sys.exit(1)
    return name_suffix, run

def check():
    run = subprocess.run("adb devices", shell=True, encoding="utf8", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    devices = len(run.stdout.strip().split("\n")[1:])
    
    if run.returncode: print(run.stderr)
    elif devices==0: print("手机未连接电脑！")
    elif devices==1: return
    elif devices>1: print("设备过多！")
    
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
    
    check()
    
    app = sys.argv[1]
    try:
        if app.endswith(".apk"):
            install_apk(app)
        elif app.endswith(".xapk"):
            app = unpack(app)
        elif app.endswith(".apks"):
            install_apks(app)
        elif app.endswith(".aab"):
            print("生成apks文件比较麻烦，暂时不考虑适配！")
        elif os.path.isfile(app):
            print(f"{app!r}不是`apk/xapk/apks`安装包！")
        
        if os.path.isdir(app):
            install, status = install_xapk(app)
            if status:
                if input("安装失败！将尝试卸载后再安装，会导致数据丢失！是否继续？(yes/no)").lower()=="yes":
                    uninstall_xapk(app)
                    if len(install)==2:
                        subprocess.run(install[0], shell=True)
                        subprocess.run(install[1], shell=True)
                    else:
                        subprocess.run(install, shell=True)
                else:
                    print("安装已取消！")
    except Exception as err:
        exc_type, exc_value, exc_obj = sys.exc_info()
        traceback.print_tb(exc_obj)
        print(f"{err!r}")
    os.system("pause")

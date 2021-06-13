# -*- coding: utf-8 -*-
# Python 自带
import hashlib, json, os, shutil, subprocess, sys, traceback, zipfile
import xml.dom.minidom as minidom
# 第三方替代
try:
    import regex as re
except ImportError:
    import re
# 第三方
import chardet
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
        _sdk = os.popen("adb shell getprop ro.build.version.sdk").read().strip()
        if not _sdk: _sdk = os.popen("adb shell getprop ro.product.build.version.sdk").read().strip()
        if not _sdk: _sdk = os.popen("adb shell getprop ro.system.build.version.sdk").read().strip()
        if not _sdk: _sdk = os.popen("adb shell getprop ro.system_ext.build.version.sdk").read().strip()
        self._sdk = int(_sdk)
        return self._sdk

def check(root, del_path):
    subprocess.call("adb kill-server", shell=True)
    run = subprocess.run("adb devices", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    devices = len(tostr(run.stdout).strip().split("\n")[1:])
    
    # TODO 多设备安装
    # adb -s <device-id/ip:port> shell xxx
    if run.returncode: sys.exit(run.stderr)
    elif devices==0: sys.exit("安装失败：手机未连接电脑！")
    elif devices==1: return
    elif devices>1: sys.exit("安装失败：设备过多！暂不支持多设备情况下进行安装！")

def delPath(path):
    if not os.path.exists(path): return
    print(f"删除    {path}")
    if os.path.isfile(path): return os.remove(path)
    return shutil.rmtree(path)

def dump(file_path, del_path):
    run, msg = run_msg(["aapt", "dump", "badging", file_path])
    if msg: print(msg)
    if run.returncode: return dump_py(file_path, del_path)
    manifest = {}
    manifest["native_code"] = []
    for line in msg.split("\n"):
        if "sdkVersion:" in line: manifest["min_sdk_version"] = int(line.strip().split("'")[1])
        elif "targetSdkVersion:" in line: manifest["target_sdk_version"] = int(line.strip().split("'")[1])
        elif "native-code:" in line: manifest["native_code"].extend(re.findall(r"'([^,']+)'",line))
        elif "package: name=" in line: manifest["package_name"] = line.split("'")[1]
    return manifest

def dump_py(file_path, del_path):
    print("未配置aapt或aapt存在错误！")
    del_path.append(get_unpack_path(file_path))
    zip_file = zipfile.ZipFile(file_path)
    upfile = "AndroidManifest.xml"
    zip_file.extract(upfile, os.path.join(del_path[-1], upfile))
    with open(os.path.join(del_path[-1], upfile), "rb") as f: data = f.read()
    ap = axmlprinter.AXMLPrinter(data)
    buff = minidom.parseString(ap.getBuff())
    manifest = {}
    manifest["package_name"] = buff.getElementsByTagName("manifest")[0].getAttribute("package")
    manifest["min_sdk_version"] = int(buff.getElementsByTagName("uses-sdk")[0].getAttribute("android:minSdkVersion"))
    try:
        manifest["target_sdk_version"] = int(buff.getElementsByTagName("uses-sdk")[0].getAttribute("android:targetSdkVersion"))
    except:
        pass
    file_list = zip_file.namelist()
    native_code = []
    for i in file_list:
        if i.startswith("lib/"): native_code.append(i.split("/")[1])
    manifest["native_code"] = list(set(native_code))
    return manifest

def get_unpack_path(file_path):
    """获取文件解压路径"""
    dir_path, name_suffix = os.path.split(file_path)
    name, suffix = os.path.splitext(name_suffix)
    unpack_path = os.path.join(dir_path, name)
    return unpack_path

def install_aab(file_path, del_path):
    """正式版是需要签名的，配置起来比较麻烦，这里只能安装debug版的"""
    print(install_aab.__doc__)
    _, name_suffix = os.path.split(file_path)
    name = name_suffix.rsplit(".", 1)[0]
    del_path.append(name+".apks")
    if os.path.exists(del_path[-1]): delPath(del_path[-1])
    build = ["java", "-jar", "bundletool.jar", "build-apks",\
        "--connected-device", "--bundle="+name_suffix, "--output="+del_path[-1]]
    sign = {}
    sign["ks"] = ""  # `/path/to/keystore.jks`
    sign["ks-pass"] = ""  # `pass:password` or `file:/path/to/keystore.pwd`
    sign["ks-key-alias"] = ""  # `alias`
    sign["key-pass"] = ""  # `pass:password` or `file:/path/to/key.pwd`
    if sign["ks"] and sign["ks-pass"] and sign["ks-key-alias"] and sign["key-pass"]:
        for i in sign: build.append(f"--{i}={sign[i]}")
    status = subprocess.call(build, shell=True)
    if status: sys.exit("bundletool 可在 https://github.com/google/bundletool/releases 下载，下载后重命名为bundletool.jar并将其放置在xapkInstaller同一文件夹即可。")
    return install_apks(del_path[-1])

def install_apk(file_path, del_path, root, abc="-rtd"):
    """安装apk文件"""
    _, name_suffix = os.path.split(file_path)
    manifest = dump(name_suffix, del_path)
    
    device = Device()
    if device.sdk < manifest["min_sdk_version"]: sys.exit("安装失败：安卓版本过低！")
    
    try:
        if device.sdk > manifest["target_sdk_version"]: print("警告：安卓版本过高！可能存在兼容性问题！")
    except:
        pass
    
    abilist = device.abilist
    
    try:
        def findabi(native_code):
            for i in abilist:
                if i in native_code: return True
            return False
        if manifest.get("native_code") and not findabi(manifest["native_code"]):
            sys.exit(f"安装失败：{manifest['native_code']}\n应用程序二进制接口(abi)不匹配！该手机支持的abi列表为：{abilist}")
    except UnboundLocalError:
        pass
    
    install = ["adb", "install", abc, name_suffix]
    status = subprocess.call(install, shell=True)
    if status:
        # No argument expected after "-rtd"
        if abc=="-rtd": return install_apk(file_path, del_path, root, "-r")
        elif abc=="-r":
            pull_path = uninstall(manifest["package_name"], root)
            install, status = install_apk(file_path, del_path, root, "")
            if status:
                msg = "安装失败！自动恢复旧版本功能未完成，请手动操作！\n"\
                    + f"旧版安装包路径：{pull_path}\n"
                sys.exit(msg)
        else:
            sys.exit(1)
    return install, status

def install_apks(file_path):
    _, name_suffix = os.path.split(file_path)
    install = ["java", "-jar", "bundletool.jar", "install-apks", "--apks="+name_suffix]
    status = subprocess.call(install, shell=True)
    if status: sys.exit("bundletool 可在 https://github.com/google/bundletool/releases 下载，下载后重命名为bundletool.jar并将其放置在xapkInstaller同一文件夹即可。")
    return install, status

def install_xapk(file_path, del_path, root):
    """安装xapk文件"""
    os.chdir(file_path)
    if not os.path.isfile("manifest.json"):
        sys.exit(f"安装失败：路径中没有`manifest.json`。{file_path!r}不是`xapk`安装包的解压路径！")
    manifest = read_manifest("manifest.json")
    if not manifest.get("expansions"):
        split_apks = manifest["split_apks"]
        
        device = Device()
        if device.sdk < int(manifest["min_sdk_version"]): sys.exit("安装失败：安卓版本过低！")
        if device.sdk > int(manifest["target_sdk_version"]): print("警告：安卓版本过高！可能存在兼容性问题！")
        
        install = ["adb", "install-multiple", "-rtd"]
        other_language = ["config.ar", "config.de", "config.en", "config.es", "config.fr", 
            "config.hi", "config.in", "config.it", "config.ja", "config.ko",
            "config.my", "config.pt", "config.ru", "config.th", "config.tr", 
            "config.vi", "config.zh"]
        other = ["extra_icu", "feedv2", "vr"]  # Google Chrome
        
        config = {}
        # mips, mips64, armeabi, armeabi-v7a, arm64-v8a, x86, x86_64
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
        
        if config.get("abi"): install.append(config["abi"])
        else:
            for i in device.abilist:
                if config.get(i): install.append(config[i]); break
        for i in ["xhdpi", "xxhdpi", "xxxhdpi", "tvdpi"]:
            if config.get(i): install.append(config[i]); break
        if config.get("locale"): install.append(config["locale"])
        
        return install, subprocess.run(install, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        install, _ = install_apk(manifest["package_name"]+".apk", del_path, root)
        expansions = manifest["expansions"]
        for i in expansions:
            if i["install_location"]=="EXTERNAL_STORAGE":
                push = ["adb", "push", i["file"], "/storage/emulated/0/"+i["install_path"]]
                return [install, push], subprocess.run(push, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else: sys.exit(1)

def main(root, one):
    os.chdir(root)
    _, name_suffix = os.path.split(one)
    name_suffix = name_suffix.rsplit(".", 1)
    new_path = md5(name_suffix[0])
    if len(name_suffix)>1: new_path += f".{name_suffix[1]}"
    del_path = [os.path.join(root, new_path)]
    copy = [one, del_path[0]]
    print(f"正在复制 `{one}` 到 `{del_path[0]}`")
    if os.path.exists(copy[1]): delPath(copy[1])
    if os.path.isfile(copy[0]): shutil.copyfile(copy[0], copy[1])
    else: shutil.copytree(copy[0], copy[1])
    
    try:
        check(root, del_path)
        if copy[1].endswith(".apk"):
            if not install_apk(copy[1], del_path, root)[0]: sys.exit(1)
        elif copy[1].endswith(".xapk"):
            del_path.append(unpack(copy[1]))
            os.chdir(del_path[-1])
        elif copy[1].endswith(".apks"): install_apks(copy[1])
        elif copy[1].endswith(".aab"): install_aab(copy[1], del_path)
        elif os.path.isfile(copy[1]): sys.exit(f"{copy[1]!r}不是`apk/xapk/apks`安装包！")
        
        if os.path.isdir(del_path[-1]):
            os.chdir(del_path[-1])
            install, run = install_xapk(del_path[-1], del_path, root)
            if run.returncode:
                err = tostr(run.stderr)
                if "INSTALL_FAILED_VERSION_DOWNGRADE" in err: print("警告：降级安装？请确保文件无误！")
                elif "INSTALL_FAILED_USER_RESTRICTED: Install canceled by user" in err: sys.exit("用户取消安装或未确认安装！初次安装需要手动确认！！")
                else: print(err)
                if input("安装失败！将尝试保留数据卸载重装，可能需要较多时间，是否继续？(yes/no)").lower() in ["yes", "y"]:
                    package_name = read_manifest(os.path.join(del_path[-1], "manifest.json"))["package_name"]
                    pull_path = uninstall(package_name, root)
                    msg = "安装失败！自动恢复旧版本功能未完成，请手动操作！\n"\
                        + f"旧版安装包路径：{pull_path}\n"
                    if len(install)==2:
                        run = subprocess.run(install[0], shell=True)
                        if run.returncode: sys.exit(msg)
                        run = subprocess.run(install[1], shell=True)
                        if run.returncode: sys.exit(msg)
                    else:
                        run = subprocess.run(install, shell=True)
                        if run.returncode: sys.exit(msg)
                else: sys.exit("用户取消安装！")
        return True
    except SystemExit as err:
        if err.code==1: print("错误    安装失败：未知错误！请提供文件进行适配！")
        else: print(f"错误    {err.code}")
        return False
    except Exception:
        traceback.print_exc(limit=2, file=sys.stdout)
        return False
    finally:
        os.chdir(root)
        for i in del_path: delPath(i)

def md5(*_str):
    if len(_str) <= 0: sys.exit("缺少参数！")
    t = _str[0]
    if type(t) is not str: t = str(t)
    encode_type = "utf-8"
    if len(_str) > 1: encode_type = _str[1]
    m = hashlib.md5()
    try:
        t = t.encode(encode_type)
    except LookupError:
        t = t.encode("utf-8")
    m.update(t)
    return m.hexdigest()

def pull_apk(root, package):
    run, msg = run_msg(["adb", "shell", "pm", "path", package])
    if run.returncode: sys.exit(msg)
    else:
        dir_path = os.path.join(root, package)
        if os.path.exists(dir_path): delPath(dir_path)
        os.mkdir(dir_path)
        for i in tostr(run.stdout).strip().split("\n"):
            run, msg = run_msg(["adb", "pull", i[8:], dir_path])
            if run.returncode: sys.exit(msg)
        cmd = ["adb", "pull", "/storage/emulated/0/Android/obb/"+package, dir_path]
        run, msg = run_msg(cmd)
        if run.returncode and "No such file or directory" not in msg: sys.exit(msg)
        return dir_path

def read_manifest(manifest_path):
    with open(manifest_path, "rb") as f: data = f.read()
    return json.loads(tostr(data))

def run_msg(cmd):
    run = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run.stderr: return run, tostr(run.stderr)
    if run.stdout: return run, tostr(run.stdout)
    return run, ""

def uninstall(package_name, root):
    # TODO 安装失败后自动重装旧版本
    if not pull_apk(package_name, root): return False
    # cmd = ["adb", "uninstall", package_name]
    # 卸载应用时尝试保留应用数据和缓存数据，但是这样处理后只能先安装相同包名的软件再正常卸载才能清除数据！！
    cmd = ["adb", "shell", "pm", "uninstall", "-k", package_name]
    return subprocess.run(cmd, shell=True)

def unpack(file_path):
    """解压文件"""
    unpack_path = get_unpack_path(file_path)
    print("文件越大，解压越慢，请耐心等待...")
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
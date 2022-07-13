# -*- coding: utf-8 -*-
import os
import shutil
import subprocess
import sys
from axmlparserpy.axmlprinter import AXMLPrinter
from chardet import detect
from defusedxml.minidom import parseString
from hashlib import md5 as _md5
from json import load as json_load
from re import findall as re_findall
from shlex import split as shlex_split
from traceback import print_exc
from yaml import safe_load
from zipfile import ZipFile


_abi = ["armeabi_v7a", "arm64_v8a", "armeabi", "x86_64", "x86", "mips64", "mips"]
_language = ["ar", "bn", "de", "en", "et", "es", "fr", "hi", "in", "it",
             "ja", "ko", "ms", "my", "nl", "pt", "ru", "sv", "th", "tl",
             "tr", "vi", "zh"]


def tostr(bytes_):
    return bytes_.decode(detect(bytes_)["encoding"])


class Device:
    def __init__(self, device):
        self._abi = None
        self._abilist = None
        self._dpi = None
        self._drawable = None
        self._locale = None
        self._sdk = None
        self.device = device

    @property
    def abi(self) -> str:
        if not self._abi:
            self.getabi()
        return self._abi

    def getabi(self) -> str:
        self._abi = run_msg(f"adb -s {self.device} shell getprop ro.product.cpu.abi")[1].strip()
        return self._abi

    @property
    def abilist(self) -> list:
        if not self._abilist:
            self.getabilist()
        return self._abilist

    def getabilist(self) -> str:
        self._abilist = run_msg(f"adb -s {self.device} shell getprop ro.product.cpu.abilist")[1].strip().split(",")
        return self._abilist

    @property
    def dpi(self) -> int:
        if not self._dpi:
            self.getdpi()
        return self._dpi

    def getdpi(self) -> int:
        _, _dpi = run_msg(f"adb -s {self.device} shell dumpsys window displays")
        for i in _dpi.strip().split("\n"):
            if i.find("dpi") >= 0:
                for j in i.strip().split(" "):
                    if j.endswith("dpi"):
                        self._dpi = int(j[:-3])
        return self._dpi

    @property
    def drawable(self) -> list:
        if not self._drawable:
            self.getdrawable()
        return self._drawable

    def getdrawable(self) -> list:
        _dpi = int((self.dpi+39)/40)
        if 0 <= _dpi <= 3:
            self._drawable = ["ldpi"]
        elif 3 < _dpi <= 4:
            self._drawable = ["mdpi"]
        elif 4 < _dpi <= 6:
            self._drawable = ["tvdpi", "hdpi"]
        elif 6 < _dpi <= 8:
            self._drawable = ["xhdpi"]
        elif 8 < _dpi <= 12:
            self._drawable = ["xxhdpi"]
        elif 12 < _dpi <= 16:
            self._drawable = ["xxxhdpi"]
        return self._drawable

    @property
    def locale(self) -> str:
        if not self._locale:
            self.getlocale()
        return self._locale

    def getlocale(self) -> str:
        self._locale = run_msg(f"adb -s {self.device} shell getprop ro.product.locale")[1].strip()
        return self._locale

    @property
    def sdk(self) -> int:
        if not self._sdk:
            self.getsdk()
        return self._sdk

    def getsdk(self) -> int:
        __sdk = ["ro.build.version.sdk", "ro.product.build.version.sdk",
                 "ro.system.build.version.sdk", "ro.system_ext.build.version.sdk"]
        for i in __sdk:
            _sdk = run_msg(f"adb -s {self.device} shell getprop {i}")[1].strip()
            if _sdk:
                self._sdk = int(_sdk)
                return self._sdk


def check() -> list:
    run = run_msg("adb devices")[0]
    _devices = tostr(run.stdout).strip().split("\n")[1:]
    devices = []
    for i in _devices:
        if i.split("\t")[1] != "offline":
            devices.append(i.split("\t")[0])

    # adb -s <device-id/ip:port> shell xxx
    if run.returncode:
        sys.exit(run.stderr)
    elif len(devices) == 0:
        sys.exit("安装失败：手机未连接电脑！")
    elif len(devices) == 1:
        pass
    elif len(devices) > 1:
        if input("检测到1个以上的设备，是否进行多设备安装？(y/N)").lower() != "y":
            sys.exit("用户取消安装！")
    return devices


def checkVersionCode(device: str, package_name: str, fileVersionCode: int, versionCode: int = -1) -> None:
    if type(device) is not str:
        device = device.device
    if type(fileVersionCode) is not int:
        fileVersionCode = int(fileVersionCode)
    msg = run_msg(["adb", "-s", device, "shell", "pm", "dump", package_name])[1]
    for i in msg.split("\n"):
        if "versionCode" in i:
            versionCode = int(i.strip().split("=")[1].split(" ")[0])
    if versionCode == -1:
        input("警告：首次安装需要在手机上点击允许安装！按回车继续...")
    if fileVersionCode < versionCode:
        if input("警告：降级安装？请确保文件无误！(y/N)").lower() != "y":
            sys.exit("降级安装，用户取消安装。")
    elif fileVersionCode == versionCode:
        if input("警告：版本一致！请确保文件无误！(y/N)").lower() != "y":
            sys.exit("版本一致，用户取消安装。")


def config_abi(config, install, abilist):
    if config.get("abi"):
        install.append(config["abi"])
    else:
        for i in abilist:
            i = i.replace('-', '_')
            if config.get(i):
                install.append(config[i])
                break
    return config, install


def config_drawable(config, install):
    if config.get("drawable"):
        install.append(config["drawable"])
    else:
        _drawableList = ["xxxhdpi", "xxhdpi", "xhdpi", "hdpi", "tvdpi", "mdpi", "ldpi", "nodpi"]
        for i in _drawableList:
            if config.get(i):
                install.append(config[i])
                break
    return config, install


def config_locale(config, install):
    if config.get("locale"):
        install.append(config["locale"])
    elif config.get("language"):
        # 如果自动匹配语言不成功，就添加列表中第一个语言
        print(f"找不到设备语言一致的语言包，将安装`{config['language'][0]}`语言包。")
        install.append(config["language"][0])
    else:
        print("找不到任意一种语言包！！")
    return config, install


def delPath(path):
    if not os.path.exists(path):
        return
    print(f"删除    {path}")
    if os.path.isfile(path):
        return os.remove(path)
    return shutil.rmtree(path)


def dump(file_path, del_path) -> dict:
    run, msg = run_msg(["aapt", "dump", "badging", file_path])
    if msg:
        print(msg)
    if run.returncode:
        print("未配置aapt或aapt存在错误！")
        return dump_py(file_path, del_path)
    manifest = {}
    manifest["native_code"] = []
    for line in msg.split("\n"):
        if "sdkVersion:" in line:
            manifest["min_sdk_version"] = int(line.strip().split("'")[1])
        elif "targetSdkVersion:" in line:
            manifest["target_sdk_version"] = int(line.strip().split("'")[1])
        elif "native-code:" in line:
            manifest["native_code"].extend(re_findall(r"'([^,']+)'", line))
        elif "package: name=" in line:
            line = line.strip().split("'")
            manifest["package_name"] = line[1]
            manifest["versionCode"] = int(line[3])
    return manifest


def dump_py(file_path, del_path) -> dict:
    del_path.append(os.path.join(os.getcwd(), get_unpack_path(file_path)))
    zip_file = ZipFile(file_path)
    upfile = "AndroidManifest.xml"
    zip_file.extract(upfile, del_path[-1])
    with open(os.path.join(del_path[-1], upfile), "rb") as f:
        data = f.read()
    ap = AXMLPrinter(data)
    buff = parseString(ap.getBuff())
    manifest = {}
    _manifest = buff.getElementsByTagName("manifest")[0]
    uses_sdk = buff.getElementsByTagName("uses-sdk")[0]
    manifest["package_name"] = _manifest.getAttribute("package")
    manifest["versionCode"] = int(_manifest.getAttribute("android:versionCode"))
    manifest["min_sdk_version"] = int(uses_sdk.getAttribute("android:minSdkVersion"))
    try:
        manifest["target_sdk_version"] = int(uses_sdk.getAttribute("android:targetSdkVersion"))
    except ValueError:
        print("`targetSdkVersion` no found.")
    file_list = zip_file.namelist()
    native_code = []
    for i in file_list:
        if i.startswith("lib/"):
            native_code.append(i.split("/")[1])
    manifest["native_code"] = list(set(native_code))
    return manifest


def findabi(native_code, abilist) -> bool:
    for i in abilist:
        if i in native_code:
            return True
    return False


def get_unpack_path(file_path) -> str:
    """获取文件解压路径"""
    dir_path, name_suffix = os.path.split(file_path)
    name, suffix = os.path.splitext(name_suffix)
    unpack_path = os.path.join(dir_path, name)
    return unpack_path


def install_aab(device, file_path, del_path, root):
    """正式版是需要签名的，配置好才能安装"""
    print(install_aab.__doc__)
    _, name_suffix = os.path.split(file_path)
    name = name_suffix.rsplit(".", 1)[0]
    del_path.append(name+".apks")
    if os.path.exists(del_path[-1]):
        delPath(del_path[-1])
    build = ["java", "-jar", "bundletool.jar", "build-apks",
             "--connected-device", "--bundle="+name_suffix,
             "--output="+del_path[-1]]
    sign = read_config("./config.yaml")
    """
    sign = {}
    sign["ks"] = ""  # `/path/to/keystore.jks`
    sign["ks-pass"] = ""  # `pass:password` or `file:/path/to/keystore.pwd`
    sign["ks-key-alias"] = ""  # `alias`
    sign["key-pass"] = ""  # `pass:password` or `file:/path/to/key.pwd`
    """
    if sign["ks"] and sign["ks-pass"] and sign["ks-key-alias"] and sign["key-pass"]:
        for i in sign:
            build.append(f"--{i}={sign[i]}")
    run = run_msg(build)[0]
    if run.returncode:
        sys.exit("bundletool 可在 "
                 "https://github.com/google/bundletool/releases"
                 " 下载，下载后重命名为bundletool.jar"
                 "并将其放置在xapkInstaller同一文件夹即可。")
    return install_apks(del_path[-1])


def install_apk(device, file_path, del_path, root, abc="-rtd"):
    """安装apk文件"""
    _, name_suffix = os.path.split(file_path)
    manifest = dump(name_suffix, del_path)
    print(manifest)
    checkVersionCode(device, manifest["package_name"], manifest["versionCode"])
    if type(device) is not Device:
        device = Device(device)
    if device.sdk < manifest["min_sdk_version"]:
        sys.exit("安装失败：安卓版本过低！")

    try:
        if device.sdk > manifest["target_sdk_version"]:
            print("警告：安卓版本过高！可能存在兼容性问题！")
    except KeyError:
        print("`manifest['target_sdk_version']` no found.")

    abilist = device.abilist

    try:
        if manifest.get("native_code") and not findabi(manifest["native_code"], abilist):
            sys.exit(f"安装失败：{manifest['native_code']}\n应用程序二进制接口(abi)不匹配！该手机支持的abi列表为：{abilist}")
    except UnboundLocalError:
        pass

    install = ["adb", "-s", device.device, "install", abc, name_suffix]
    run, msg = run_msg(install)
    if run.returncode:
        if abc == "-rtd" and "argument expected" in msg:
            print('No argument expected after "-rtd"')
            print("正在修改安装参数重新安装，请等待...")
            return install_apk(device, file_path, del_path, root, "-r")
        elif abc == "-r":
            if uninstall(device, manifest["package_name"], root):
                return install_apk(device, file_path, del_path, root, "")
            else:
                sys.exit("备份文件时出现错误")
        else:
            sys.exit(1)
    elif "INSTALL_FAILED_TEST_ONLY" in msg:
        print('INSTALL_FAILED_TEST_ONLY')
        print("正在修改安装参数重新安装，请等待...")
        return install_apk(device, file_path, del_path, root, "-t")
    return install, run


def install_apkm(device, file_path, del_path, root):
    _, name_suffix = os.path.split(file_path)
    del_path.append(os.path.join(os.getcwd(), get_unpack_path(file_path)))
    zip_file = ZipFile(file_path)
    upfile = "info.json"
    zip_file.extract(upfile, del_path[-1])
    info = read_json(os.path.join(del_path[-1], upfile))
    file_list = zip_file.namelist()
    if type(device) is not Device:
        device = Device(device)
    if device.sdk < int(info["min_api"]):
        sys.exit("安装失败：安卓版本过低！")
    checkVersionCode(device, info["pname"], info["versioncode"])
    install = ["adb", "-s", device.device, "install-multiple", "-rtd"]
    abi = [f"split_config.{i}.apk" for i in _abi]
    language = [f"split_config.{i}.apk" for i in _language]

    config = {}
    config["language"] = []
    # mips, mips64, armeabi, armeabi-v7a, arm64-v8a, x86, x86_64
    for i in file_list:
        if i == f"split_config.{device.abi.replace('-', '_')}.apk":
            config["abi"] = i
        for d in device.drawable:
            if i == f"split_config.{d}.apk":
                config["drawable"] = i
        if i == f"split_config.{device.locale.split('-')[0]}.apk":
            config["locale"] = i
        elif i in abi:
            config[i.split(".")[1]] = i
        elif i.find("dpi.apk") >= 0:
            config[i.split(".")[1]] = i
        elif i in language:
            config["language"].append(i)
        elif i.endswith(".apk"):
            install.append(i)
    print(config)
    config, install = config_locale(config_drawable(config_abi(config, install, device.abilist)))
    for i in install[5:]:
        zip_file.extract(i, del_path[-1])
    os.chdir(del_path[-1])
    return install, run_msg(install)[0]


def install_apks(device, file_path, del_path, root):
    os.chdir(root)
    _, name_suffix = os.path.split(file_path)
    install = ["java", "-jar", "bundletool.jar", "install-apks", "--apks="+name_suffix]
    run, msg = run_msg(install)
    if run.returncode:
        if '[SCREEN_DENSITY]' in msg:
            sys.exit("Missing APKs for [SCREEN_DENSITY] dimensions in the module 'base' for the provided device.")
        else:
            sys.exit("bundletool 可在 "
                     "https://github.com/google/bundletool/releases"
                     " 下载，下载后重命名为bundletool.jar"
                     "并将其放置在xapkInstaller同一文件夹即可。")
    return install, run


def install_multiple_base(device, file_list, del_path, root):
    """备用"""
    def _abandon(device, SESSION_ID):
        # pm install-abandon SESSION_ID
        # 中止安装
        run, msg = run_msg(["adb", "-s", device, "shell", "pm", "install-abandon", SESSION_ID])
        if msg:
            print(msg)

    def _commit(device, SESSION_ID):
        # pm install-commit SESSION_ID
        run, msg = run_msg(["adb", "-s", device, "shell", "pm", "install-commit", SESSION_ID])
        if run.returncode:
            _abandon(SESSION_ID)
            sys.exit(msg)
        else:
            print(msg)
        return run

    def _create(device, info) -> str:
        # pm install-create
        run, msg = run_msg(["adb", "-s", device, "shell", "pm", "install-create"])
        if run.returncode:
            sys.exit(msg)
        else:
            # Success: created install session [1234567890]
            print(msg)
            return msg.strip()[:-1].split("[")[1]

    def _del(device, info):
        for i in info:
            run, msg = run_msg(["adb", "-s", device, "shell", "rm", i["path"]])
            if run.returncode:
                sys.exit(msg)

    def _push(device, file_list) -> list:
        info = []
        for f in file_list:
            info.append({"name": "_".join(f.rsplit(".")[:-1]), "path": "/data/local/tmp/"+f})
            run, msg = run_msg(["adb", "-s", device, "push", f, info[-1]["path"]])
            if run.returncode:
                sys.exit(msg)
        return info

    def _write(device, SESSION_ID, info):
        index = 0
        for i in info:
            # pm install-write SESSION_ID SPLIT_NAME PATH
            run, msg = run_msg(["adb", "-s", device, "shell", "pm", "install-write",
                                SESSION_ID, i["name"], i["path"]])
            if run.returncode:
                _abandon(SESSION_ID)
                sys.exit(msg)
            index += 1

    if type(device) is not str:
        device = device.device
    info = _push(device, file_list)
    SESSION_ID = _create(device, info)
    _write(device, SESSION_ID, info)
    run = _commit(device, SESSION_ID)
    _del(device, info)
    return info, run


def install_xapk(device, file_path, del_path, root):
    """安装xapk文件"""
    os.chdir(file_path)
    print("开始安装...")
    if not os.path.isfile("manifest.json"):
        sys.exit(f"安装失败：路径中没有`manifest.json`。{file_path!r}不是`xapk`安装包的解压路径！")
    manifest = read_json("manifest.json")
    checkVersionCode(device, manifest["package_name"], manifest["version_code"])
    if type(device) is not Device:
        device = Device(device)
    if not manifest.get("expansions"):
        split_apks = manifest["split_apks"]

        if device.sdk < int(manifest["min_sdk_version"]):
            sys.exit("安装失败：安卓版本过低！")
        if device.sdk > int(manifest["target_sdk_version"]):
            print("警告：安卓版本过高！可能存在兼容性问题！")

        install = ["adb", "-s", device.device, "install-multiple", "-rtd"]
        abi = [f"config.{i}" for i in _abi]
        language = [f"config.{i}" for i in _language]
        other = ["extra_icu", "feedv2", "vr", "chime"]  # Google Chrome

        config = {}
        config["language"] = []
        # mips, mips64, armeabi, armeabi-v7a, arm64-v8a, x86, x86_64
        for i in split_apks:
            if i["id"] == f"config.{device.abi.replace('-', '_')}":
                config["abi"] = i["file"]
            for d in device.drawable:
                if i == f"split_config.{d}.apk":
                    config["drawable"] = i
            if i["id"] == f"config.{device.locale.split('-')[0]}":
                config["locale"] = i["file"]
            elif i["id"] in abi:
                config[i["id"].split(".")[1]] = i["file"]
            elif i["id"].endswith("dpi"):
                config[i["id"].split(".")[1]] = i["file"]
            elif i["id"] in language:
                config["language"].append(i["file"])
            elif i["id"] in other:
                pass
            else:
                install.append(i["file"])
        print(config)
        config, install = config_abi(config, install, device.abilist)
        config, install = config_drawable(config, install)
        config, install = config_locale(config, install)
        return install, run_msg(install)[0]
    else:
        install = install_apk(device, manifest["package_name"]+".apk", del_path, root)[0]
        expansions = manifest["expansions"]
        for i in expansions:
            if i["install_location"] == "EXTERNAL_STORAGE":
                push = ["adb", "-s", device.device, "push", i["file"], "/storage/emulated/0/"+i["install_path"]]
                return [install, push], run_msg(push)[0]
            else:
                sys.exit(1)


# device, file_path, del_path, root[, abc] -> (list, subprocess.CompletedProcess)
installSuffix = [".aab", ".apk", ".apkm", ".apks", ".xapk"]
installSelector = {}
installSelector[".aab"] = install_aab
installSelector[".apk"] = install_apk
installSelector[".apkm"] = install_apkm
installSelector[".apks"] = install_apks
installSelector[".xapk"] = install_xapk


def main(root, one) -> bool:
    os.chdir(root)
    _, name_suffix = os.path.split(one)
    name_suffix = name_suffix.rsplit(".", 1)
    new_path = md5(name_suffix[0])
    if len(name_suffix) > 1:
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
        devices = check()
        suffix = os.path.splitext(os.path.split(copy[1])[1])[1]

        for device in devices:
            if copy[1].endswith(".xapk"):
                del_path.append(unpack(copy[1]))
                os.chdir(del_path[-1])
            elif suffix in installSuffix:
                install, run = installSelector[suffix](device, copy[1], del_path, root)
                if run.returncode:
                    err = tostr(run.stderr)
                    printerr(err)
                    sys.exit(err)
            elif os.path.isfile(copy[1]):
                sys.exit(f"{copy[1]!r}不是`{'/'.join(installSuffix)}`安装包！")

            if os.path.isdir(del_path[-1]) and os.path.exists(os.path.join(del_path[-1], "manifest.json")):
                os.chdir(del_path[-1])
                install, run = install_xapk(device, del_path[-1], del_path, root)
                if run.returncode:
                    printerr(tostr(run.stderr))
                    try:
                        print("使用备用方案")
                        _, run = install_multiple_base(device, del_path[-1], del_path, root)
                        if not run.returncode:
                            return True
                    except Exception:
                        pass
                    if input("安装失败！将尝试保留数据卸载重装，可能需要较多时间，是否继续？(y/N)").lower() == 'y':
                        package_name = read_json(os.path.join(del_path[-1], "manifest.json"))["package_name"]
                        if uninstall(device, package_name, root):
                            for i in install:
                                run, msg = run_msg(i)
                                if run.returncode:
                                    sys.exit(msg)
                        else:
                            sys.exit("备份文件时出现错误")
                    else:
                        sys.exit("用户取消安装！")
        return True
    except SystemExit as err:
        if err.code == 1:
            print("错误    安装失败：未知错误！请提供文件进行适配！")
        else:
            print(f"错误    {err.code}")
        return False
    except Exception:
        print_exc(file=sys.stdout)
        return False
    finally:
        os.chdir(root)
        for i in del_path:
            delPath(i)


def md5(*_str) -> str:
    if len(_str) <= 0:
        sys.exit("缺少参数！")
    t = _str[0]
    if type(t) is not str:
        t = str(t)
    encode_type = "utf-8"
    if len(_str) > 1:
        encode_type = _str[1]
    m = _md5()
    try:
        t = t.encode(encode_type)
    except LookupError:
        t = t.encode("utf-8")
    m.update(t)
    return m.hexdigest()


def pause():
    input("按回车键继续...")
    sys.exit(0)


def printerr(err: str) -> None:
    if "INSTALL_FAILED_VERSION_DOWNGRADE" in err:
        print("警告：降级安装？请确保文件无误！")
    elif "INSTALL_FAILED_USER_RESTRICTED: Install canceled by user" in err:
        sys.exit("用户取消安装或未确认安装！初次安装需要手动确认！！")
    elif "INSTALL_FAILED_ALREADY_EXISTS" in err:
        sys.exit("已安装包名和版本号一致的应用！！")
    else:
        print(err)


def pull_apk(device, package, root) -> str:
    print("正在备份安装包...")
    if type(device) is not str:
        device = device.device
    run, msg = run_msg(["adb", "-s", device, "shell", "pm", "path", package])
    if run.returncode:
        sys.exit(msg)
    else:
        dir_path = os.path.join(root, package)
        if os.path.exists(dir_path):
            delPath(dir_path)
        os.mkdir(dir_path)
        try:
            for i in tostr(run.stdout).strip().split("\n"):
                run, msg = run_msg(["adb", "-s", device, "pull", i[8:].strip(), dir_path])
                if run.returncode:
                    sys.exit(msg)
        except TypeError:
            sys.exit(1)
        cmd = ["adb", "-s", device, "pull", "/storage/emulated/0/Android/obb/"+package, dir_path]
        run, msg = run_msg(cmd)
        if run.returncode and "No such file or directory" not in msg and "does not exist" not in msg:
            sys.exit(msg)
        return dir_path


def read_config(yaml_file) -> dict:
    with open(yaml_file, "rb") as f:
        data = f.read()
    return safe_load(tostr(data))


def read_json(file) -> dict:
    with open(file) as f:
        return json_load(f)


def restore(device, dir_path):
    print("开始恢复...")
    if type(device) is not str:
        device = device.device
    os.chdir(dir_path)
    all = os.listdir(dir_path)
    obb = False
    for i in all:
        if i.endswith(".obb"):
            obb = True
            break
    if obb:
        for i in all:
            if i.endswith(".apk"):
                install_apk(device, os.path.join(dir_path, i))
            elif i.endswith(".obb"):
                push = ["adb", "-s", device, "push", os.path.join(dir_path, i),
                        "/storage/emulated/0/Android/obb/"+os.path.split(dir_path)[-1]]
                run_msg(push)
    else:
        if len(all) == 0:
            sys.exit("备份文件夹为空！")
        elif len(all) == 1:
            main(root, all[0])
        elif len(all) > 1:
            install = ["adb", "-s", device, "install-multiple", "-rtd"]
            install.extend(all)
            run_msg(install)
    os.chdir(root)


def run_msg(cmd):
    print(cmd)
    if type(cmd) is str:
        cmd = shlex_split(cmd)
    run = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run.stderr:
        return run, tostr(run.stderr)
    if run.stdout:
        return run, tostr(run.stdout)
    return run, ""


def uninstall(device, package_name, root):
    if type(device) is not str:
        device = device.device
    dir_path = pull_apk(device, package_name, root)
    if not dir_path:  # 备份文件时出现错误
        return False
    # cmd = ["adb", "uninstall", package_name]
    # 卸载应用时尝试保留应用数据和缓存数据，但是这样处理后只能先安装相同包名的软件再正常卸载才能清除数据！！
    cmd = ["adb", "-s", device, "shell", "pm", "uninstall", "-k", package_name]
    print("开始卸载...")
    run, msg = run_msg(cmd)
    try:
        if run.returncode:
            restore(device, dir_path, root)
    except Exception:
        sys.exit(f"恢复时出现未知错误！请尝试手动操作并反馈该问题！旧版安装包路径：{dir_path}")
    return run


def unpack(file_path) -> str:
    """解压文件"""
    unpack_path = get_unpack_path(file_path)
    print("文件越大，解压越慢，请耐心等待...")
    shutil.unpack_archive(file_path, unpack_path, "zip")
    return unpack_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("缺少参数！")
        print("xapkInstaller <filepath or dirpath>")
        print("例如：")
        print("    xapkInstaller abc.aab")
        print("    xapkInstaller abc.apk")
        print("    xapkInstaller ./abc/")
        print("    xapkInstaller abc.apkm abc.apks abc.xapk ./abc/")
        pause()
    root = os.path.split(sys.argv[0])[0]
    if not root:
        root = os.getcwd()
    _len_ = len(sys.argv[1:])
    success = 0
    try:
        for i, one in enumerate(sys.argv[1:]):
            print(f"正在安装第{i+1}/{_len_}个...")
            if main(root, one):
                success += 1
    except Exception:
        print_exc(file=sys.stdout)
    finally:
        print(f"共{_len_}个，成功安装了{success}个。")
        pause()

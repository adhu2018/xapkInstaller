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

    # ===================================================
    def _abandon(self, SESSION_ID):
        '''????????????'''
        # pm install-abandon SESSION_ID
        run, msg = run_msg(["adb", "-s", self.device, "shell", "pm", "install-abandon", SESSION_ID])
        if msg:
            print(msg)

    def _commit(self, SESSION_ID):
        # pm install-commit SESSION_ID
        run, msg = run_msg(["adb", "-s", self.device, "shell", "pm", "install-commit", SESSION_ID])
        if run.returncode:
            self._abandon(SESSION_ID)
            sys.exit(msg)
        else:
            print(msg)
        return run

    def _create(self) -> str:
        # pm install-create
        run, msg = run_msg(["adb", "-s", self.device, "shell", "pm", "install-create"])
        if run.returncode:
            sys.exit(msg)
        else:
            # Success: created install session [1234567890]
            print(msg)
            return msg.strip()[:-1].split("[")[1]

    def _del(self, info):
        for i in info:
            run, msg = run_msg(["adb", "-s", self.device, "shell", "rm", i["path"]])
            if run.returncode:
                sys.exit(msg)

    def _push(self, file_list) -> list:
        info = []
        for f in file_list:
            info.append({"name": "_".join(f.rsplit(".")[:-1]), "path": "/data/local/tmp/"+f})
            run, msg = run_msg(["adb", "-s", self.device, "push", f, info[-1]["path"]])
            if run.returncode:
                sys.exit(msg)
        return info

    def _write(self, SESSION_ID, info):
        index = 0
        for i in info:
            # pm install-write SESSION_ID SPLIT_NAME PATH
            run, msg = run_msg(["adb", "-s", self.device, "shell", "pm", "install-write",
                                SESSION_ID, i["name"], i["path"]])
            if run.returncode:
                self._abandon(SESSION_ID)
                sys.exit(msg)
            index += 1


def build_apkm_config(device, file_list, install):
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
    return config, install


def build_xapk_config(device, split_apks, install):
    abi = [f"config.{i}" for i in _abi]
    language = [f"config.{i}" for i in _language]
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
        else:
            install.append(i["file"])
    print(config)
    return config, install


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
        sys.exit("???????????????????????????????????????")
    elif len(devices) == 1:
        pass
    elif len(devices) > 1:
        if input("?????????1???????????????????????????????????????????????????(y/N)").lower() != "y":
            sys.exit("?????????????????????")
    return devices


def check_by_manifest(device, manifest):
    if type(device) is not Device:
        device = Device(device)
    if device.sdk < manifest["min_sdk_version"]:
        sys.exit("????????????????????????????????????")

    try:
        if device.sdk > manifest["target_sdk_version"]:
            print("????????????????????????????????????????????????????????????")
    except KeyError:
        print("`manifest['target_sdk_version']` no found.")

    abilist = device.abilist

    try:
        if manifest.get("native_code") and not findabi(manifest["native_code"], abilist):
            sys.exit(f"???????????????{manifest['native_code']}\n???????????????????????????(abi)??????????????????????????????abi????????????{abilist}")
    except UnboundLocalError:
        pass


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
        input("???????????????????????????????????????????????????????????????????????????...")
    if fileVersionCode < versionCode:
        if input("????????????????????????????????????????????????(y/N)").lower() != "y":
            sys.exit("????????????????????????????????????")
    elif fileVersionCode == versionCode:
        if input("????????????????????????????????????????????????(y/N)").lower() != "y":
            sys.exit("????????????????????????????????????")


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
        # ?????????????????????????????????????????????????????????????????????
        print(f"???????????????????????????????????????????????????`{config['language'][0]}`????????????")
        install.append(config["language"][0])
    else:
        print("????????????????????????????????????")
    return config, install


def copy_files(copy):
    print(f"???????????? `{copy[0]}` ??? `{copy[1]}`")
    if os.path.exists(copy[1]):
        delPath(copy[1])
    if os.path.isfile(copy[0]):
        shutil.copyfile(copy[0], copy[1])
    else:
        shutil.copytree(copy[0], copy[1])


def delPath(path):
    if not os.path.exists(path):
        return
    print(f"??????    {path}")
    if os.path.isfile(path):
        return os.remove(path)
    return shutil.rmtree(path)


def dump(file_path, del_path) -> dict:
    run, msg = run_msg(["aapt", "dump", "badging", file_path])
    if msg:
        print(msg)
    if run.returncode:
        print("?????????aapt???aapt???????????????")
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
    """????????????????????????"""
    dir_path, name_suffix = os.path.split(file_path)
    name, suffix = os.path.splitext(name_suffix)
    unpack_path = os.path.join(dir_path, name)
    return unpack_path


def install_aab(device, file_path, del_path, root):
    """???????????????????????????????????????????????????"""
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
        sys.exit("bundletool ?????? "
                 "https://github.com/google/bundletool/releases"
                 " ??????????????????????????????bundletool.jar"
                 "??????????????????xapkInstaller????????????????????????")
    return install_apks(del_path[-1])


def install_apk(device, file_path, del_path, root, abc="-rtd"):
    """??????apk??????"""
    _, name_suffix = os.path.split(file_path)
    manifest = dump(name_suffix, del_path)
    print(manifest)
    checkVersionCode(device, manifest["package_name"], manifest["versionCode"])
    device = check_by_manifest(device, manifest)

    install = ["adb", "-s", device.device, "install", abc, name_suffix]
    run, msg = run_msg(install)
    if run.returncode:
        if abc == "-rtd" and "argument expected" in msg:
            print('No argument expected after "-rtd"')
            print("????????????????????????????????????????????????...")
            return install_apk(device, file_path, del_path, root, "-r")
        elif abc == "-r":
            if uninstall(device, manifest["package_name"], root):
                return install_apk(device, file_path, del_path, root, "")
            else:
                sys.exit("???????????????????????????")
        else:
            sys.exit(1)
    elif "INSTALL_FAILED_TEST_ONLY" in msg:
        print('INSTALL_FAILED_TEST_ONLY')
        print("????????????????????????????????????????????????...")
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
        sys.exit("????????????????????????????????????")
    checkVersionCode(device, info["pname"], info["versioncode"])
    install = ["adb", "-s", device.device, "install-multiple", "-rtd"]
    config, install = build_apkm_config(device, file_list, install)
    config, install = config_abi(config, install, device.abilist)
    config, install = config_drawable(config, install)
    config, install = config_locale(config, install)
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
            sys.exit("bundletool ?????? "
                     "https://github.com/google/bundletool/releases"
                     " ??????????????????????????????bundletool.jar"
                     "??????????????????xapkInstaller????????????????????????")
    return install, run


def install_base(device, file_list):
    """??????"""
    if type(device) is not Device:
        device = Device(device)
    SESSION_ID = device._create()
    info = device._push(file_list)
    device._write(SESSION_ID, info)
    run = device._commit(SESSION_ID)
    device._del(info)
    return info, run


def install_xapk(device, file_path, del_path, root):
    """??????xapk??????"""
    os.chdir(file_path)
    print("????????????...")
    if not os.path.isfile("manifest.json"):
        sys.exit(f"??????????????????????????????`manifest.json`???{file_path!r}??????`xapk`???????????????????????????")
    manifest = read_json("manifest.json")
    checkVersionCode(device, manifest["package_name"], manifest["version_code"])
    if type(device) is not Device:
        device = Device(device)
    if not manifest.get("expansions"):
        split_apks = manifest["split_apks"]

        if device.sdk < int(manifest["min_sdk_version"]):
            sys.exit("????????????????????????????????????")
        if device.sdk > int(manifest["target_sdk_version"]):
            print("????????????????????????????????????????????????????????????")

        install = ["adb", "-s", device.device, "install-multiple", "-rtd"]
        config, install = build_xapk_config(device, split_apks, install)
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
    copy_files(copy)

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
                sys.exit(f"{copy[1]!r}??????`{'/'.join(installSuffix)}`????????????")

            if os.path.isdir(del_path[-1]) and os.path.exists(os.path.join(del_path[-1], "manifest.json")):
                os.chdir(del_path[-1])
                install, run = install_xapk(device, del_path[-1], del_path, root)
                if run.returncode:
                    printerr(tostr(run.stderr))
                    try:
                        print("??????????????????")
                        _, run = install_base(device, install[5:])
                        if not run.returncode:
                            return True
                    except Exception as err:
                        print(err)
                    if input("?????????????????????????????????????????????????????????????????????????????????????????????(y/N)").lower() == 'y':
                        package_name = read_json(os.path.join(del_path[-1], "manifest.json"))["package_name"]
                        if uninstall(device, package_name, root):
                            for i in install:
                                run, msg = run_msg(i)
                                if run.returncode:
                                    sys.exit(msg)
                        else:
                            sys.exit("???????????????????????????")
                    else:
                        sys.exit("?????????????????????")
        return True
    except SystemExit as err:
        if err.code == 1:
            print("??????    ????????????????????????????????????????????????????????????")
        else:
            print(f"??????    {err.code}")
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
        sys.exit("???????????????")
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
    input("??????????????????...")
    sys.exit(0)


def printerr(err: str) -> None:
    if "INSTALL_FAILED_VERSION_DOWNGRADE" in err:
        print("????????????????????????????????????????????????")
    elif "INSTALL_FAILED_USER_RESTRICTED: Install canceled by user" in err:
        sys.exit("???????????????????????????????????????????????????????????????????????????")
    elif "INSTALL_FAILED_ALREADY_EXISTS" in err:
        sys.exit("????????????????????????????????????????????????")
    else:
        print(err)


def pull_apk(device, package, root) -> str:
    print("?????????????????????...")
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
    print("????????????...")
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
            sys.exit("????????????????????????")
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
    if not dir_path:  # ???????????????????????????
        return False
    # cmd = ["adb", "uninstall", package_name]
    # ?????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????
    cmd = ["adb", "-s", device, "shell", "pm", "uninstall", "-k", package_name]
    print("????????????...")
    run, msg = run_msg(cmd)
    try:
        if run.returncode:
            restore(device, dir_path, root)
    except Exception:
        sys.exit(f"????????????????????????????????????????????????????????????????????????????????????????????????{dir_path}")
    return run


def unpack(file_path) -> str:
    """????????????"""
    unpack_path = get_unpack_path(file_path)
    print("?????????????????????????????????????????????...")
    shutil.unpack_archive(file_path, unpack_path, "zip")
    return unpack_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("???????????????")
        print("xapkInstaller <filepath or dirpath>")
        print("?????????")
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
            print(f"???????????????{i+1}/{_len_}???...")
            if main(root, one):
                success += 1
    except Exception:
        print_exc(file=sys.stdout)
    finally:
        print(f"???{_len_}?????????????????????{success}??????")
        pause()

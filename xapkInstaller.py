#! /usr/bin/python3
# coding: utf-8
import logging
import os
import shutil
import subprocess
import sys
from axmlparserpy.axmlprinter import AXMLPrinter
from chardet import detect
from defusedxml.minidom import parseString
from hashlib import md5 as _md5
from json import load as json_load
from pathlib import Path
from re import findall as re_findall
from shlex import split as shlex_split
from typing import Any, List, NoReturn, Tuple, Union
from yaml import safe_load
from zipfile import ZipFile


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

handler1 = logging.FileHandler("log.txt", encoding="utf-8")
handler1.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(funcName)s - line %(lineno)d - %(levelname)s: %(message)s")
handler1.setFormatter(formatter)

handler2 = logging.StreamHandler()
handler2.setLevel(logging.INFO)

log.addHandler(handler1)
log.addHandler(handler2)


_abi = ["armeabi_v7a", "arm64_v8a", "armeabi", "x86_64", "x86", "mips64", "mips"]
_language = ["ar", "bn", "de", "en", "et", "es", "fr", "hi", "in", "it",
             "ja", "ko", "ms", "my", "nl", "pt", "ru", "sv", "th", "tl",
             "tr", "vi", "zh"]
info_msg = {
    "bundletool": "bundletool 可在 "
                  "https://github.com/google/bundletool/releases"
                  " 下载，下载后重命名为 bundletool.jar "
                  "并将其放置在 xapkInstaller 同一文件夹即可。",
    "sdktoolow": "安装失败：安卓版本过低！"
}


def tostr(bytes_: bytes) -> str:
    encoding = detect(bytes_)["encoding"]
    if not encoding:
        encoding = "utf-8"
    try:
        return bytes_.decode(encoding)
    except UnicodeDecodeError:
        return bytes_.decode("utf-8")


class Device:
    __slots__ = ["ADB", "_abi", "_abilist", "_dpi", "_drawable", "_locale", "_sdk", "device"]

    def __init__(self, device: str = ""):
        self.ADB: str = "adb"
        self._abi = None
        self._abilist = None
        self._dpi = -1
        self._drawable = [""]
        self._locale = None
        self._sdk = 0
        self.device = device  # 连接多个设备时使用

    @property
    def abi(self) -> str:
        if not self._abi:
            self._abi = self.shell(["getprop", "ro.product.cpu.abi"])[1].strip()
        return self._abi

    @property
    def abilist(self) -> list:
        if not self._abilist:
            self._abilist = self.shell(["getprop", "ro.product.cpu.abilist"])[1].strip().split(",")
        return self._abilist

    @property
    def dpi(self) -> int:
        if not self._dpi:
            self.getdpi()
        return self._dpi

    def getdpi(self) -> int:
        _dpi = self.shell(["dumpsys", "window", "displays"])[1]
        for i in _dpi.strip().split("\n"):
            if i.find("dpi") >= 0:
                for j in i.strip().split(" "):
                    if j.endswith("dpi"):
                        self._dpi = int(j[:-3])
        return self._dpi

    @property
    def drawable(self) -> List[str]:
        if not self._drawable:
            self.getdrawable()
        return self._drawable

    def getdrawable(self) -> List[str]:
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
            self._locale = self.shell(["getprop", "ro.product.locale"])[1].strip().split("-")[0]
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
            _sdk = self.shell(["getprop", i])[1].strip()
            if _sdk:
                try:
                    self._sdk = int(_sdk)
                except ValueError as err:
                    # 设备断开连接 error: closed
                    sys.exit("设备断开连接")
        return self._sdk

    # ===================================================
    def adb(self, cmd: list):
        c = [self.ADB]
        if self.device:
            c.extend(["-s", self.device])
        c.extend(cmd)
        return run_msg(c)

    def shell(self, cmd: list):
        c = ["shell"]
        c.extend(cmd)
        return self.adb(c)

    # ===================================================
    def _abandon(self, SESSION_ID: str):
        """中止安装"""
        run, msg = self.shell(["pm", "install-abandon", SESSION_ID])
        if msg:
            log.info(msg)

    def _commit(self, SESSION_ID: str):
        run, msg = self.shell(["pm", "install-commit", SESSION_ID])
        if run.returncode:
            self._abandon(SESSION_ID)
            sys.exit(msg)
        else:
            log.info(msg)
        return run

    def _create(self) -> str:
        run, msg = self.shell(["pm", "install-create"])
        if run.returncode:
            sys.exit(msg)
        log.info(msg)  # Success: created install session [1234567890]
        return msg.strip()[:-1].split("[")[1]

    def _del(self, info):
        for i in info:
            run, msg = self.shell(["rm", i["path"]])
            if run.returncode:
                sys.exit(msg)

    def _push(self, file_list: list) -> List[dict]:
        info = []
        for f in file_list:
            info.append({"name": "_".join(f.rsplit(".")[:-1]), "path": "/data/local/tmp/"+f})
            run, msg = self.adb(["push", f, info[-1]["path"]])
            if run.returncode:
                sys.exit(msg)
        return info

    def _write(self, SESSION_ID: str, info: list):
        index = 0
        for i in info:
            # pm install-write SESSION_ID SPLIT_NAME PATH
            run, msg = self.shell(["pm", "install-write",
                                   SESSION_ID, i["name"], i["path"]])
            if run.returncode:
                self._abandon(SESSION_ID)
                sys.exit(msg)
            index += 1


def build_apkm_config(device: Device, file_list: List[str], install: List[str]) -> Tuple[dict, List[str]]:
    abi = [f"split_config.{i}.apk" for i in _abi]
    language = [f"split_config.{i}.apk" for i in _language]
    config: dict[str, Any] = {"language": []}
    for i in file_list:
        if i == f"split_config.{device.abi.replace('-', '_')}.apk":
            config["abi"] = i
        for d in device.drawable:
            if i == f"split_config.{d}.apk":
                config["drawable"] = i
        if i == f"split_config.{device.locale}.apk":
            config["language"].insert(0, i)
        elif (i in abi) or (i.find("dpi.apk") >= 0):
            config[i.split(".")[1]] = i
        elif i in language:
            config["language"].append(i)
        elif i.endswith(".apk"):
            install.append(i)
    log.info(config)
    return config, install


def build_xapk_config(device: Device, split_apks: List[dict[str,str]], install: List[str]) -> Tuple[dict[str, List[str]|str|dict[str,str]], List[str]]:
    abi = [f"config.{i}" for i in _abi]
    language = [f"config.{i}" for i in _language]
    config: dict[str, List[str]|str|dict[str,str]] = {"language": []}
    log.info(f"config.{device.abi.replace('-', '_')}")
    for i in split_apks:
        if i["id"] == f"config.{device.abi.replace('-', '_')}":
            config["abi"] = i["file"]  #  最佳的一个
        for d in device.drawable:
            if i["file"] == f"split_config.{d}.apk":
                config["drawable"] = i
        if i["id"] == f"config.{device.locale}":
            config["language"].insert(0, i["file"])
        elif (i["id"] in abi) or i["id"].endswith("dpi"):
            config[i["id"].split(".")[1]] = i["file"]
        elif i["id"] in language:
            config["language"].append(i["file"])
        else:
            install.append(i["file"])
    log.info(config)
    return config, install


def check(ADB=None) -> List[str]:
    if not ADB:
        ADB = check_sth("adb")
    run, msg = run_msg([ADB, "devices"])
    _devices = msg.strip().split("\n")[1:]
    if _devices == ["* daemon started successfully"]:
        log.info("初次启动adb服务")
        run, msg = run_msg([ADB, "devices"])
        _devices = msg.strip().split("\n")[1:]
    devices = []
    for i in _devices:
        if i.split("\t")[1] != "offline":
            devices.append(i.split("\t")[0])

    # adb -s <device-id/ip:port> shell xxx
    if run.returncode:
        log.error(msg)
    elif len(devices) == 0:
        log.error("手机未连接电脑！")
    elif len(devices) == 1:
        pass
    elif len(devices) > 1:
        log.info("检测到1个以上的设备，将进行多设备安装")
    return devices


def check_sth(key: str, conf="config.yaml"):
    if key not in ["adb", "java", "aapt", "bundletool"]:
        return ""
    conf = read_yaml(conf)
    path: str = conf.get(key, key)
    if not os.path.exists(path):
        # 配置文件有误或为空时，使用系统环境中的adb
        try:
            if key in ["adb", "java"]:
                run, msg = run_msg([key, "--version"])
            elif key in ["aapt"]:
                run, msg = run_msg([key, "v"])
            elif key in ["bundletool"]:
                run, msg = run_msg([check_sth("java"), "-jar", key+".jar", "version"])
        except FileNotFoundError:
            run = None
        if run and (run.returncode == 0):
            log.info(f"check_sth({key!r})")
            log.info(msg.strip())
            return key
        log.error(f"未配置{key}")
        return ""
    return path


def check_by_manifest(device: Device, manifest: dict) -> None:
    if device.sdk < manifest["min_sdk_version"]:
        sys.exit(info_msg["sdktoolow"])
    else:
        try:
            if device.sdk > manifest["target_sdk_version"]:
                log.warning("警告：安卓版本过高！可能存在兼容性问题！")
        except KeyError:
            log.warning("`manifest['target_sdk_version']` no found.")

    abilist = device.abilist

    try:
        if manifest.get("native_code") and not findabi(manifest["native_code"], abilist):
            sys.exit(f"安装失败：{manifest['native_code']}\n应用程序二进制接口(abi)不匹配！该手机支持的abi列表为：{abilist}")
    except UnboundLocalError:
        log.exception("Failed in check_by_manifest->findabi.")


def checkVersion(device: Device, package_name: str, fileVersionCode: int, versionCode: int = -1, abi: str = "") -> None:
    msg = device.shell(["pm", "dump", package_name])[1]
    for i in msg.split("\n"):
        if "versionCode" in i:
            versionCode = int(i.strip().split("=")[1].split(" ")[0])
            if versionCode == -1:
                input("警告：首次安装需要在手机上点击允许安装！按回车继续...")
            elif fileVersionCode < versionCode:
                if input("警告：降级安装？请确保文件无误！(y/N)").lower() != "y":
                    sys.exit("降级安装，用户取消安装。")
            elif fileVersionCode == versionCode:
                if input("警告：版本一致！请确保文件无误！(y/N)").lower() != "y":
                    sys.exit("版本一致，用户取消安装。")
        elif "primaryCpuAbi" in i:
            primaryCpuAbi = i.strip().split("=")[1]
            if (primaryCpuAbi == "arm64-v8a" and abi) and (primaryCpuAbi not in abi):
                if input("警告：从64位变更到32位？请确保文件无误！(y/N)").lower() != "y":
                    sys.exit("用户取消安装。")


def config_abi(config: dict, install: List[str], abilist: List[str]):
    if config.get("abi"):
        install.append(config["abi"])
    else:
        for i in abilist:
            i = i.replace("-", "_")
            if config.get(i):
                install.append(config[i])
                break
    return config, install


def config_drawable(config: dict, install: List[str]):
    if config.get("drawable"):
        install.append(config["drawable"])
    else:
        _drawableList = ["xxxhdpi", "xxhdpi", "xhdpi", "hdpi", "tvdpi", "mdpi", "ldpi", "nodpi"]
        for i in _drawableList:
            if config.get(i):
                install.append(config[i])
                break
    return config, install


def config_language(config: dict, install: List[str]):
    if config.get("language"):
        # 如果有设备语言一致的语言包，会优先安装
        install.append(config["language"][0])
    else:
        log.warning("找不到任意一种语言包！！")
    return config, install


def copy_files(copy: List[Path]):
    log.info("copy_files start")
    if os.path.exists(copy[1]):
        delPath(copy[1])
    log.info(f"正在复制 `{copy[0]}` 到 `{copy[1]}`")
    if os.path.isfile(copy[0]):
        shutil.copyfile(copy[0], copy[1])
    else:
        shutil.copytree(copy[0], copy[1])
    log.info("copy_files end")


def delPath(path: Path):
    if not os.path.exists(path):
        log.info(f"文件(夹)不存在 {path!r}")
        return
    if os.path.isfile(path):
        log.info(f"删除文件 {path!r}")
        return os.remove(path)
    log.info(f"删除文件夹 {path!r}")
    return shutil.rmtree(path)


def dump(file: Path, del_path: List[Path]) -> dict:
    run, msg = run_msg(["aapt", "dump", "badging", str(file)])
    if msg:
        log.info(msg)
    if run.returncode:
        log.warning("未配置aapt或aapt存在错误！")
        return dump_py(file, del_path)
    manifest: dict[str, List|int|str] = {"native_code": []}
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
            try:
                manifest["versionCode"] = int(line[3])
            except ValueError:
                log.error(f"err in dump: ValueError: line[3]: {line[3]!r}")
                manifest["versionCode"] = 0
    return manifest


def dump_py(file_path: Path, del_path: List[Path]) -> dict:
    _path = os.path.join(os.getcwd(), get_unpack_path(file_path))
    del_path.append(Path(_path).resolve())
    zip_file = ZipFile(file_path)
    upfile = "AndroidManifest.xml"
    zip_file.extract(upfile, del_path[-1])
    with open(os.path.join(del_path[-1], upfile), "rb") as f:
        data = f.read()
    ap = AXMLPrinter(data)
    buff = parseString(tostr(ap.getBuff()))
    manifest = {}
    _manifest = buff.getElementsByTagName("manifest")[0]
    uses_sdk = buff.getElementsByTagName("uses-sdk")[0]
    manifest["package_name"] = _manifest.getAttribute("package")
    manifest["versionCode"] = int(_manifest.getAttribute("android:versionCode"))
    manifest["min_sdk_version"] = int(uses_sdk.getAttribute("android:minSdkVersion"))
    try:
        manifest["target_sdk_version"] = int(uses_sdk.getAttribute("android:targetSdkVersion"))
    except ValueError:
        log.warning("`targetSdkVersion` no found.")
    file_list = zip_file.namelist()
    native_code = []
    for i in file_list:
        if i.startswith("lib/"):
            native_code.append(i.split("/")[1])
    manifest["native_code"] = list(set(native_code))
    return manifest


def findabi(native_code: List[str], abilist: List[str]) -> bool:
    for i in abilist:
        if i in native_code:
            return True
    return False


def get_unpack_path(file: Path) -> str:
    """获取文件解压路径"""
    dir_path, name_suffix = os.path.split(file)
    name = os.path.splitext(name_suffix)[0]
    unpack_path = os.path.join(dir_path, name)
    return unpack_path


def install_aab(device: Device, file: str, del_path: List[Path], root: Path) -> Tuple[List[str], bool]:
    """正式版是需要签名的，配置好才能安装"""
    log.info(install_aab.__doc__)
    name_suffix = os.path.split(file)[1]
    name = name_suffix.rsplit(".", 1)[0]
    del_path.append(Path(name+".apks").resolve())
    if os.path.exists(del_path[-1]):
        delPath(del_path[-1])
    build = ["java", "-jar", "bundletool.jar", "build-apks",
             "--connected-device", "--bundle="+name_suffix,
             "--output="+str(del_path[-1])]
    sign = read_yaml("./config.yaml")
    if sign.get("ks") and sign.get("ks-pass") and sign.get("ks-key-alias") and sign.get("key-pass"):
        for i in sign:
            if i in ["ks", "ks-pass", "ks-key-alias", "key-pass"]:
                build.append(f"--{i}={sign[i]}")
    run, msg = run_msg(build)
    if run.returncode:
        if "failed to deserialize resources.pb" in msg:
            log.error("请升级bundletool.jar！")
            sys.exit(info_msg["bundletool"])
        else:
            sys.exit(msg)
    return install_apks(device, del_path[-1], del_path, root)


def install_apk(device: Device, file: Path, del_path: List[Path], root: Path, abc: str = "-rtd") -> Tuple[List[str], bool]:
    """安装apk文件"""
    name_suffix: str = os.path.split(file)[1]
    manifest = dump(Path(name_suffix), del_path)
    log.info(manifest)
    checkVersion(device, manifest["package_name"], int(manifest["versionCode"]), manifest["native_code"])
    check_by_manifest(device, manifest)

    install = ["install", abc, name_suffix]
    run, msg = device.adb(install)
    if run.returncode:
        if abc == "-rtd":
            if "argument expected" in msg:
                log.error("No argument expected after '-rtd'")
            else:  # WSA
                log.error(f"{msg!r}")
            log.info("正在修改安装参数重新安装，请等待...")
            return install_apk(device, file, del_path, root, "-r")
        elif abc == "-r":
            if uninstall(device, manifest["package_name"], root):
                return install_apk(device, file, del_path, root, "")
        elif "INSTALL_FAILED_TEST_ONLY" in msg:
            log.error("INSTALL_FAILED_TEST_ONLY")
            log.info("正在修改安装参数重新安装，请等待...")
            return install_apk(device, file, del_path, root, "-t")
        else:
            sys.exit(1)
    return install, True


def install_apkm(device: Device, file: Path, del_path: List[str], root: str) -> Tuple[List[str], bool]:
    del_path.append(os.path.join(os.getcwd(), get_unpack_path(file)))
    zip_file = ZipFile(file)
    upfile = "info.json"
    zip_file.extract(upfile, del_path[-1])
    info = read_json(os.path.join(del_path[-1], upfile))
    file_list = zip_file.namelist()
    if device.sdk < int(info["min_api"]):
        sys.exit(info_msg["sdktoolow"])
    checkVersion(device, info["pname"], info["versioncode"], info["arches"])
    install = ["install-multiple", "-rtd"]
    config, install = build_apkm_config(device, file_list, install)
    config, install = config_abi(config, install, device.abilist)
    config, install = config_drawable(config, install)
    config, install = config_language(config, install)
    for i in install[5:]:
        zip_file.extract(i, del_path[-1])
    os.chdir(del_path[-1])
    return install_multiple(device, install)


def install_apks(device: Device, file: Path, del_path: List[Path], root: Path) -> Tuple[List[str], bool]:
    os.chdir(root)
    zip_file = ZipFile(file)
    file_list = zip_file.namelist()
    if "toc.pb" not in file_list:
        if "meta.sai_v2.json" in file_list:  # SAI v2
            return install_apks_sai(device, file, del_path, version=2)
        elif "meta.sai_v1.json" in file_list:  # SAI v1
            return install_apks_sai(device, file, del_path, version=1)
        else:  # unknow
            return [], False
    try:
        install, status = install_apks_java(file)
        if status:
            return install, status
    except FileNotFoundError:
        pass
    log.warning("没有配置java环境或存在错误，将尝试直接解析文件")
    return install_apks_py(device, file, del_path)


def install_apks_java(file: Path) -> Tuple[List[str], bool]:
    name_suffix: str = os.path.split(file)[1]
    install = ["java", "-jar", "bundletool.jar", "install-apks", "--apks="+name_suffix]
    run, msg = run_msg(install)
    if run.returncode:
        if "[SCREEN_DENSITY]" in msg:
            sys.exit("Missing APKs for [SCREEN_DENSITY] dimensions in the module 'base' for the provided device.")
        else:
            sys.exit(info_msg["bundletool"])
    return install, True


def install_apks_py(device: Device, file: Path, del_path: List[Path]) -> Tuple[List[str], bool]:
    zip_file = ZipFile(file)
    file_list = zip_file.namelist()
    _path = os.path.join(os.getcwd(), get_unpack_path(file))
    del_path.append(Path(_path).resolve())
    if device.sdk < 21:
        log.warning("当前安卓版本不支持多apk模式安装，希望apks里有适合的standalone文件")
        for i in file_list:
            f = None
            if f"standalone-{device.abi}_{device.dpi}.apk" in i:
                f = zip_file.extract(i, del_path[-1])
            else:
                for a in device.abilist:
                    for d in device.drawable:
                        if f"standalone-{a}_{d}.apk" in i:
                            f = zip_file.extract(i, del_path[-1])
            if f:
                return install_apk(device, Path(f), del_path, Path.cwd())
            log.error("看来没有...")
            sys.exit("没有适合的standalone文件")
    install = ["install-multiple", ""]
    for i in file_list:
        if i.startswith("splits/"):
            install.append(zip_file.extract(i, del_path[-1]))
    return install_multiple(device, install)


def install_apks_sai(device: Device, file: Path, del_path: List[Path], version: int) -> Tuple[List[str], bool]:
    """用于安装SAI生成的apks文件"""
    _path = os.path.join(os.getcwd(), get_unpack_path(file))
    del_path.append(Path(_path).resolve())
    zip_file = ZipFile(file)
    file_list = zip_file.namelist()
    for i in ["meta.sai_v2.json", "meta.sai_v1.json", "icon.png"]:
        try:
            file_list.remove(i)
        except ValueError:
            pass
    install = [""]
    if version == 2:
        upfile = "meta.sai_v2.json"
        zip_file.extract(upfile, del_path[-1])
        data = read_json(os.path.join(del_path[-1], upfile))
        checkVersion(device, data["package"], data["version_code"])

        if data.get("split_apk"):
            install = ["install-multiple", ""]
            install.extend(file_list)
            return install_multiple(device, install)
        else:
            install = ["install", "", file_list[0]]
            run, msg = device.adb(install)
            if run.returncode:
                log.error(msg)
                return install, False
            return install, True
    elif version == 1:
        log.error("未完成")
        return install, False
    else:
        log.error("未知情况")
        return install, False


def install_base(device: Device, file_list: List[str]) -> Tuple[List[dict], bool]:
    """备用"""
    SESSION_ID = device._create()
    info = device._push(file_list)
    device._write(SESSION_ID, info)
    run = device._commit(SESSION_ID)
    device._del(info)
    if run.returncode:
        return info, False
    return info, True


def install_multiple(device: Device, install: List[str]) -> Tuple[List[str], bool]:
    """install-multiple"""
    run = device.adb(install)[0]
    if run.returncode:
        if install[1] == "-rtd":
            install[1] = "-r"
            log.info("正在修改安装参数重新安装，请等待...")
            return install_multiple(device, install)
        elif install[1] == "r":
            install[1] = ""
            log.info("正在修改安装参数重新安装，请等待...")
            return install_multiple(device, install)
        elif install[1] == "":
            print_err(tostr(run.stderr))
            try:
                log.info("使用备用方案")
                _, returncode = install_base(device, install[2:])
                if not returncode:
                    return install, True
            except Exception:
                log.exception("Failed in install_multiple->install_base.")
    return install, False


def install_xapk(device: Device, file: Path, del_path: List[Path], root: Path) -> Union[Tuple[List[Union[str, List[str]]], bool], None]:
    """安装xapk文件"""
    log.info("开始安装...")
    if not os.path.isfile("manifest.json"):
        sys.exit(f"安装失败：路径中没有`manifest.json`。{file!r}不是`xapk`安装包的解压路径！")
    manifest = read_json("manifest.json")
    if not manifest.get("expansions"):
        split_apks: List[dict[str, str]] = manifest["split_apks"]

        if device.sdk < int(manifest["min_sdk_version"]):
            sys.exit(info_msg["sdktoolow"])
        elif device.sdk > int(manifest["target_sdk_version"]):
            log.info("警告：安卓版本过高！可能存在兼容性问题！")

        install = ["install-multiple", "-rtd"]
        config, install = build_xapk_config(device, split_apks, install)
        if not manifest.get("version_code"):
            manifest["version_code"] = 0
        checkVersion(device, manifest["package_name"], int(manifest["version_code"]), abi=config.get("abi"))
        config, install = config_abi(config, install, device.abilist)
        config, install = config_drawable(config, install)
        config, install = config_language(config, install)
        return install_multiple(device, install)
    else:
        install = install_apk(device, manifest["package_name"]+".apk", del_path, root)[0]
        expansions = manifest["expansions"]
        for i in expansions:
            if i["install_location"] == "EXTERNAL_STORAGE":
                push: List[str] = ["push", i["file"], "/storage/emulated/0/"+i["install_path"]]
                if device.adb(push)[0].returncode:
                    return [install, push], False
                return [install, push], True
            else:
                sys.exit(1)


# device: Device, file: str, del_path: List[str], root: str[, abc: str] -> Tuple[List[Union[str, List[str]]], bool]
installSuffix = [".aab", ".apk", ".apkm", ".apks", ".xapk"]
installSelector = {".aab": install_aab, ".apk": install_apk, ".apkm": install_apkm, ".apks": install_apks,
                   ".xapk": install_xapk}


def main(root: Path, one: Path) -> bool:
    os.chdir(root)
    name_suffix = os.path.split(one)[1]
    name_suffix = name_suffix.rsplit(".", 1)
    new_path = md5(name_suffix[0])  # md5 用处：避免莫名其妙的文件名导致意料之外的问题
    if len(name_suffix) > 1:
        new_path += f".{name_suffix[1]}"
    _path = os.path.join(root, new_path)
    del_path = [Path(_path).resolve()]
    copy = [Path(one).resolve(), del_path[0]]
    copy_files(copy)

    try:
        ADB: str = check_sth("adb")
        devices = check(ADB)
        if len(devices) == 0:
            sys.exit("安装失败：手机未连接电脑！")
        suffix = os.path.splitext(os.path.split(copy[1])[1])[1]

        for device in devices:
            device = Device(device)
            device.ADB = ADB
            if str(copy[1]).endswith(".xapk"):
                del_path.append(unpack(copy[1]))
            elif suffix in installSuffix:
                return installSelector[suffix](device, copy[1], del_path, root)[1]
            elif os.path.isfile(copy[1]):
                sys.exit(f"{copy[1]!r}不是`{'/'.join(installSuffix)}`安装包！")

            if os.path.isdir(del_path[-1]) and os.path.exists(os.path.join(del_path[-1], "manifest.json")):
                os.chdir(del_path[-1])
                install, status = install_xapk(device, del_path[-1], del_path, root)
                if status:
                    if input("安装失败！将尝试保留数据卸载重装，可能需要较多时间，是否继续？(y/N)").lower() == "y":
                        package_name: str = read_json(os.path.join(del_path[-1], "manifest.json"))["package_name"]
                        if uninstall(device, package_name, root):
                            if type(install[0][0]) is list:
                                for i in install:
                                    run, msg = run_msg(i)
                                    if run.returncode:
                                        sys.exit(msg)
                            else:
                                run, msg = run_msg(install)
                                if run.returncode:
                                    sys.exit(msg)
                    else:
                        sys.exit("用户取消安装！")
        return True
    except SystemExit as err:
        if err.code == 1:
            log.error("错误    安装失败：未知错误！请提供文件进行适配！")
        elif err.code != 0:
            log.error(err)
        return False
    except Exception:
        log.exception("Failed in main.")
        return False
    finally:
        os.chdir(root)
        for i in del_path:
            delPath(i)


def md5(_str: str, encoding="utf-8") -> str:
    m = _md5()
    _bytes = _str.encode(encoding)
    m.update(_bytes)
    return m.hexdigest()


def pause() -> NoReturn:
    input("按回车键继续...")
    log.info("正常退出")
    sys.exit(0)


def print_err(err: str):
    if "INSTALL_FAILED_VERSION_DOWNGRADE" in err:
        log.warning("警告：降级安装？请确保文件无误！")
    elif "INSTALL_FAILED_USER_RESTRICTED: Install canceled by user" in err:
        sys.exit("用户取消安装或未确认安装！初次安装需要手动确认！！")
    elif "INSTALL_FAILED_ALREADY_EXISTS" in err:
        sys.exit("已安装包名和版本号一致的应用！！")
    else:
        log.error(err)


def pull_apk(device: Device, package: str, root: Path) -> Path:
    log.info("正在备份安装包...")
    run, msg = device.shell(["pm", "path", package])
    if run.returncode:
        sys.exit(msg)
    else:
        dir_path = Path(os.path.join(root, package)).resolve()
        if os.path.exists(dir_path):
            delPath(dir_path)
        os.mkdir(dir_path)
        try:
            for i in tostr(run.stdout).strip().split("\n"):
                run, msg = device.adb(["pull", i[8:].strip(), dir_path])
                if run.returncode:
                    sys.exit(msg)
        except TypeError:
            log.exception("Failed in pull_apk.")
            sys.exit(1)
        cmd = ["pull", "/storage/emulated/0/Android/obb/"+package, dir_path]
        run, msg = device.adb(cmd)
        if run.returncode and ("No such file or directory" not in msg) and ("does not exist" not in msg):
            sys.exit(msg)
        return dir_path


def read_yaml(file) -> dict:
    if not os.path.exists(file):
        return {}
    with open(file, "rb") as f:
        data = f.read()
    return safe_load(tostr(data))


def read_json(file) -> dict:
    with open(file, "rb") as f:
        return json_load(f)


def restore(device: Device, dir_path: Path, root: Path):
    log.info("开始恢复...")
    os.chdir(dir_path)
    all_file = os.listdir(dir_path)
    obb = False
    for i in all_file:
        if i.endswith(".obb"):
            obb = True
            break
    if obb:
        for i in all_file:
            _path = os.path.join(dir_path, i)
            if i.endswith(".apk"):
                install_apk(device, Path(_path).resolve(), [], root)
            elif i.endswith(".obb"):
                push = ["push", _path,
                        "/storage/emulated/0/Android/obb/"+os.path.split(dir_path)[-1]]
                device.adb(push)
    else:
        if len(all_file) == 0:
            sys.exit("备份文件夹为空！")
        elif len(all_file) == 1:
            main(root, Path(all_file[0]).resolve())
        elif len(all_file) > 1:
            install = ["install-multiple", "-rtd"]
            install.extend(all_file)
            install_multiple(device, install)
    os.chdir(root)


def run_msg(cmd: Union[str, List[str]]):
    log.info(cmd)
    if type(cmd) is str:
        cmd = shlex_split(cmd)
    run = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run.stderr:
        return run, tostr(run.stderr)
    if run.stdout:
        return run, tostr(run.stdout)
    return run, str()


def uninstall(device: Device, package_name: str, root: Path):
    dir_path = pull_apk(device, package_name, root)
    if not dir_path:
        sys.exit("备份文件时出现错误")
    # adb uninstall package_name
    # 卸载应用时尝试保留应用数据和缓存数据，但是这样处理后只能先安装相同包名的软件再正常卸载才能清除数据！！
    log.info("开始卸载...")
    run = device.shell(["pm", "uninstall", "-k", package_name])[0]
    try:
        if run.returncode:
            restore(device, dir_path, root)
    except Exception:
        log.exception("Failed in uninstall->restore.")
        sys.exit(f"恢复时出现未知错误！请尝试手动操作并反馈该问题！旧版安装包路径：{dir_path}")
    return run


def unpack(file: Path) -> Path:
    """解压文件"""
    unpack_path = get_unpack_path(file)
    log.info("文件越大，解压越慢，请耐心等待...")
    shutil.unpack_archive(file, unpack_path, "zip")
    return Path(unpack_path).resolve()


if __name__ == "__main__":
    argv = sys.argv
    if len(argv) < 2 or (len(argv) == 2 and "-l" in argv):
        print("缺少参数！")
        print("xapkInstaller <filepath or dirpath>")
        print("例如：")
        print("    xapkInstaller abc.aab")
        print("    xapkInstaller abc.apk")
        print("    xapkInstaller ./abc/")
        print("    xapkInstaller abc.apkm abc.apks abc.xapk ./abc/")
        pause()

    if "-l" in argv:
        argv.remove("-l")
    else:
        logging.disable(logging.DEBUG)
        logging.disable(logging.INFO)
        logging.disable(logging.WARNING)
        """
        logging.disable(logging.ERROR)
        logging.disable(logging.CRITICAL)
        """

    rootdir = os.path.split(argv[0])[0]
    if not rootdir:
        rootdir = os.getcwd()
    rootdir = Path(rootdir).resolve()
    _len_ = len(argv[1:])
    success = 0
    try:
        for _i, _one in enumerate(argv[1:]):
            log.info(f"正在安装第{_i+1}/{_len_}个...")
            log.info(str(_one)+" start")
            if main(rootdir, Path(_one).resolve()):
                success += 1
                log.info(str(_one)+" end")
    except Exception:
        log.exception("Failed in unknow err.")
        log.info("error end")
    finally:
        log.info(f"共{_len_}个，成功安装了{success}个。")
        pause()

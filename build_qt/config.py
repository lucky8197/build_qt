
import json
import questionary
import os
from typing import Dict
import platform
import subprocess
from build_qt.utils import detect_platform, download_component, extract_archive
from build_qt.ohos_sdk_downloader import OhosSdkDownloader

class Config:
    def __init__(self, config_path: str):
        self.root_path = os.path.abspath(os.path.dirname(config_path))

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.init_user_config()
        user_config_path = os.path.join(self.root_path, 'configure.json.user')
        with open(user_config_path, 'r', encoding='utf-8') as f:
            self.user_config = json.load(f)

        self.perl_path = self.get_perl_path()
        self.mingw_path = self.get_mingw_path()
        self.ohos_sdk_path = self.get_ohos_sdk_path()
        plat = detect_platform()
        self.ohos_sdk_downloader = OhosSdkDownloader(os_type=plat['osType'], os_arch=plat['osArch'], support_version=self.ohos_support_version())

    def init_user_config(self):
        user_config_path = os.path.join(self.root_path, 'configure.json.user')
        if not os.path.isfile(user_config_path):
            questionary.print("用户配置文件 {} 不存在，开始配置。".format(user_config_path), style="bold italic fg:darkred")
            answers = questionary.prompt([
                {
                    "type": "path",          # 提示类型（输入、选择、确认等）
                    "name": "working-directory",      # 存储结果的键名
                    "message": "请输入工作目录：",  # 显示给用户的提示信息
                    "default": self.get_working_dir(),    # 默认值
                },
                {
                    "type": "path",
                    "name": "perl",
                    "message": "请配置perl路径（默认则自动下载）：",
                    "default": self.perl_path()
                },
                {
                    "type": "path",
                    "name": "mingw",
                    "message": "请配置mingw路径（默认则自动下载）：",
                    "default": self.mingw_path()
                },
                {
                    "type": "path",
                    "name": "ohos_sdk",
                    "message": "请配置OpenHarmony SDK路径（默认则自动下载）：",
                    "default": self.ohos_sdk_path()
                },
                {
                    "type": "select",
                    "name": "ohos_version",
                    "message": "请选择OpenHarmony SDK版本：",
                    "choices": self.ohos_sdk_downloader.get_supported_versions(),
                    "default": str(self.ohos_version())
                },
                {
                    "type": "select",
                    "name": "build_qt_tag",
                    "message": "请选择要编译的 Qt 版本：",
                    "choices": [
                        "v5.15.12-lts-lgpl",
                        "v5.15.16-lts-lgpl",
                        "v6.5.6-lts-lgpl"
                    ],
                    "default": self.tag()
                }
            ])
            print("用户配置：", answers)
            if answers == {}:
                print("🛑 用户取消操作，程序退出。")
                exit()   # 手动退出
            else:
                self.save_usr_config(answers)
                print("用户配置已保存到 {}".format(user_config_path))

    def dev_env_check(self):
        system = platform.system()
        need_perl = True
        need_mingw = True
        need_ohos_sdk = True
        if system == "Windows":
            if self.perl_path and os.path.isdir(self.perl_path):
                result = subprocess.run([os.path.join(self.perl_path, "perl"), "-v"], capture_output=True, text=True)
                if result.returncode == 0:
                    print("perl 版本信息：")
                    print(result.stdout)
                    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + self.perl_path
                    need_perl = False
                else:
                    print("perl 执行失败")
            if self.mingw_path and os.path.isdir(self.mingw_path):
                result = subprocess.run([os.path.join(self.mingw_path, "mingw32-make"), "--version"], capture_output=True, text=True)
                if result.returncode == 0:
                    print("mingw32-make 版本信息：")
                    print(result.stdout)
                    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + self.mingw_path
                    need_mingw = False
                else:
                    print("mingw32-make 执行失败")
        else:
            print("当前系统不是 Windows，跳过环境变量设置和命令检查。")
            return
        if self.ohos_sdk_path and os.path.isdir(self.ohos_sdk_path):
            # 检查 native\oh-uni-package.json 是否存在
            package_json_path = os.path.join(self.ohos_sdk_path, 'native', 'oh-uni-package.json')
            print("OHOS SDK 路径：", package_json_path)
            if os.path.isfile(package_json_path):
                # 尝试读取 JSON 文件，检查是否能正确解析
                try:
                    import json
                    with open(package_json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    print("OHOS SDK 配置内容：")
                    print(json.dumps(data, indent=2))
                    os.environ["OHOS_SDK_PATH"] = self.ohos_sdk_path
                    need_ohos_sdk = False
                except Exception as e:
                    print("警告: 无法解析 {}，文件可能损坏或格式不正确。错误: {}".format(package_json_path, e))
        temp_dir = os.path.join(self.get_working_dir(), '.temp')
        if need_perl:
            perl_url = self.config["dependencies"]["perl"]["url"]
            perl_checksum = ('sha256', self.config["dependencies"]["perl"]["sha256"])
            print("正在下载并安装 Perl...")
            zip_path = download_component(perl_url, os.path.join(temp_dir, 'perl5.7z'), perl_checksum)
            perl_extracted_path = os.path.join(self.get_working_dir(), 'perl')
            extract_archive(zip_path, perl_extracted_path)
            if os.path.isdir(perl_extracted_path):
                self.perl_path = os.path.join(perl_extracted_path, 'bin')

        if need_mingw:
            mingw_url = self.config["dependencies"]["mingw"]["url"]
            mingw_checksum = ('sha256', self.config["dependencies"]["mingw"]["sha256"])
            print("正在下载并安装 MinGW...")
            zip_path = download_component(mingw_url, os.path.join(temp_dir, 'mingw64-x86_64-8.1.0-release-posix-seh-rt_v6-rev0.7z'), mingw_checksum)
            mingw_extracted_path = os.path.join(self.get_working_dir(), 'mingw')
            extract_archive(zip_path, mingw_extracted_path)
            if os.path.isdir(mingw_extracted_path):
                self.mingw_path = os.path.join(mingw_extracted_path, 'bin')

        if need_ohos_sdk:
            api_version = self.ohos_version()
            print("正在下载并安装 OpenHarmony SDK...")
            saved = self.ohos_sdk_downloader.download_component_by_name(api_version=api_version, component_name='native', dest_dir=temp_dir)
            extract_archive(saved, self.ohos_sdk_path)

        if need_perl or need_mingw or need_ohos_sdk:
            self.dev_env_check()

    def get_working_dir(self):
        working_dir = self.config["config"]["working-directory"]
        if "${pwd}" in working_dir:
            working_dir = working_dir.replace("${pwd}", self.root_path)
        working_dir = os.path.abspath(os.path.expanduser(working_dir))
        return working_dir
    
    def get_perl_path(self):
        _perl_path = perl_path = self.user_config.get("config", self.config.get("config")).get("perl", self.config["config"]["perl"])
        if "${pwd}" in _perl_path:
            _perl_path = _perl_path.replace("${pwd}", self.root_path)
        _perl_path = os.path.abspath(os.path.expanduser(_perl_path))
        return _perl_path

    def get_mingw_path(self):
        _mingw_path = self.config["config"]["mingw"]
        if "${pwd}" in _mingw_path:
            _mingw_path = _mingw_path.replace("${pwd}", self.root_path)
        _mingw_path = os.path.abspath(os.path.expanduser(_mingw_path))
        return _mingw_path
    
    def get_ohos_sdk_path(self):
        _ohos_sdk_path = self.config["config"]["ohos_sdk"]
        if "${pwd}" in _ohos_sdk_path:
            _ohos_sdk_path = _ohos_sdk_path.replace("${pwd}", self.root_path)
        if "${ohos_version}" in _ohos_sdk_path:
            _ohos_sdk_path = _ohos_sdk_path.replace("${ohos_version}", str(self.ohos_version()))
        _ohos_sdk_path = os.path.abspath(os.path.expanduser(_ohos_sdk_path))
        return _ohos_sdk_path

    def ohos_support_version(self):
        return self.config["dependencies"]["ohos_sdk"]["support_version"]
    
    def ohos_version(self):
        return self.config["config"]["ohos_version"]
    
    def qt_repo(self):
        return self.config["repositories"]["qt_repo"]["url"]

    def qt_ohos_patch_repo(self):
        return self.config["repositories"]["qt-ohos-patch"]["url"]
    
    def tag(self):
        return self.config["config"]["build_qt_tag"]

    def build_type(self):
        return self.config["config"]["build_type"]

    def build_ohos_abi(self):
        return self.config["config"]["build_ohos_abi"]

    def get_config(self):
        return self.config
    
    def save_usr_config(self, usr_config: Dict):
        usr_config_path = os.path.join(self.root_path, 'configure.json.user')
        obj = {
            "config": usr_config
        }
        with open(usr_config_path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=4)

    def build_configure_options(self):
        options = self.config["qt-config"]
        result = []
        if options["license"] in ["opensource", "commercial"]:
            result.append("-{}".format(options['license']))
        if options["confirm-license"]:
            result.append("-confirm-license")
        host_platform = "win32-g++"
        if platform.system() == "Linux":
            host_platform = "linux-g++"
        elif platform.system() == "Darwin":
            host_platform = "macx-clang"
        result += ["-platform", host_platform]
        result += ["-xplatform", options["-xplatform"]]
        result += ["-opengl", options["-opengl"]]
        if options["-opengles3"]:
            result.append("-opengles3")
        if options["-no-dbus"]:
            result.append("-no-dbus")
        if options["-disable-rpath"]:
            result.append("-disable-rpath")
        for nomake in options["-nomake"]:
            result += ["-nomake", nomake]
        skips = self.config[self.tag()]["-skip"]
        for skip in skips:
            result += ["-skip", skip]
        result += ["-prefix", os.path.join(self.get_working_dir(), 'output', self.tag())]
        result += ["-{}".format(self.build_type())]
        result += ["-device-option", "OHOS_ARCH={}".format(self.build_ohos_abi())]
        result += ["-make-tool", "mingw32-make -j{}".format(32) if platform.system() == "Windows" else "make -j{}".format(32)]
        result += ["-verbose"]
        return result

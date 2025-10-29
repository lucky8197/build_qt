
import json
import questionary
import os
import sys
from typing import Dict
import platform
import subprocess
from build_qt.utils import detect_platform, download_component, extract_archive
from build_qt.ohos_sdk_downloader import OhosSdkDownloader

class Config:
    config = None
    user_config = None
    def __init__(self, config_path: str):
        self.root_path = os.path.abspath(os.path.dirname(config_path))

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.system = platform.system()
        self.make_tools = 'mingw32-make' if self.system == 'Windows' else 'make'
        plat = detect_platform()
        self.ohos_sdk_downloader = OhosSdkDownloader(os_type=plat['osType'], os_arch=plat['osArch'], support_version=self.ohos_support_version())
        if sys.stdout.isatty():
            self.init_user_config()
        else:
            self.save_usr_config(self.get_config())
        user_config_path = os.path.join(self.root_path, 'configure.json.user')
        with open(user_config_path, 'r', encoding='utf-8') as f:
            self.user_config = json.load(f)
        self.perl_path = self.get_perl_path()
        self.mingw_path = self.get_mingw_path()
        self.ohos_sdk_path = self.get_ohos_sdk_path()


    def init_user_config(self):
        user_config_path = os.path.join(self.root_path, 'configure.json.user')
        if not os.path.isfile(user_config_path):
            questionary.print('用户配置文件 {} 不存在，开始配置。'.format(user_config_path), style='bold fg:ansiyellow')
            answers = questionary.prompt([
                {
                    'type': 'path',
                    'name': 'working_dir',
                    'message': '请输入工作目录：',
                    'default': self.get_working_dir(),
                },
                {
                    'type': 'path',
                    'name': 'perl',
                    'message': '请配置perl路径（默认则自动下载）：',
                    'default': self.get_perl_path(),
                    'when': platform.system() != 'Windows'
                },
                {
                    'type': 'path',
                    'name': 'mingw',
                    'message': '请配置mingw路径（默认则自动下载）：',
                    'default': self.get_mingw_path(),
                    'when': platform.system() != 'Windows'
                },
                {
                    'type': 'path',
                    'name': 'ohos_sdk',
                    'message': '请配置OpenHarmony SDK路径（默认则自动下载）：',
                    'default': self.get_ohos_sdk_path()
                },
                {
                    'type': 'select',
                    'name': 'ohos_version',
                    'message': '请选择OpenHarmony SDK版本：',
                    'choices': self.ohos_sdk_downloader.get_supported_versions(),
                    'default': str(self.ohos_version())
                },
                {
                    'type': 'select',
                    'name': 'build_qt_tag',
                    'message': '请选择要编译的 Qt 版本：',
                    'choices': self.supported_qt_tags(),
                    'default': self.tag()
                },
                {
                    'type': 'select',
                    'name': 'build_type',
                    'message': '请选择构建类型（Release/Debug）：',
                    'choices': ['release', 'debug'],
                    'default': self.build_type()
                },
                {
                    'type': 'select',
                    'name': 'build_ohos_abi',
                    'message': '请选择OpenHarmony目标架构：',
                    'choices': ['arm64-v8a', 'armeabi-v7a', 'x86_64'],
                    'default': self.build_ohos_abi()
                },
                {
                    'type': 'text',
                    'name': 'clone_depth',
                    'message': '请输入克隆深度（建议值1，0为完整克隆）：',
                    'default': str(self.clone_depth()),
                },
                {
                    'type': 'text',
                    'name': 'jobs',
                    'message': '请输入编译并行任务数（建议值为CPU核心数）：',
                    'default': str(self.build_jobs()),
                }
            ])
            print('用户配置：', answers)
            if answers == {}:
                print('用户取消操作，程序退出。')
                exit()   # 手动退出
            else:
                self.save_usr_config(answers)
                print('用户配置已保存到 {}'.format(user_config_path))

    def dev_env_check(self):
        need_perl = True
        need_mingw = True
        need_ohos_sdk = True
        if self.system == 'Windows':
            os.environ['PATH'] = 'C:\\Windows\\System32' + os.pathsep + 'C:\\Windows'
            if self.perl_path and os.path.isdir(self.perl_path):
                cmd = [os.path.join(self.perl_path, 'perl'), '-e', 'print sprintf("%vd",$^V);']
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        print('perl 版本信息 {}'.format(result.stdout.strip()))
                        os.environ['PATH'] = os.environ.get('PATH', '') + os.pathsep + self.perl_path
                        need_perl = False
                except Exception as e:
                    print('执行 {} 失败：{}'.format(cmd, e))
            if self.mingw_path and os.path.isdir(self.mingw_path):
                cmd = [os.path.join(self.mingw_path, self.make_tools), '--version']
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        print('{} 版本信息 {}'.format(self.make_tools, result.stdout[0:result.stdout.find('\n')].strip()))
                        os.environ['PATH'] = os.environ.get('PATH', '') + os.pathsep + self.mingw_path
                        need_mingw = False
                except Exception as e:
                    print('执行 {} 失败：{}'.format(cmd, e))
        else:
            cmd = None
            try:
                cmd = ['perl', '-e', 'print sprintf("%vd",$^V);']
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print('perl 版本信息')
                    print(result.stdout)
                    need_perl = False
                cmd = [self.make_tools, '--version']
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print('{} 版本信息'.format(self.make_tools))
                    print(result.stdout)
                    need_mingw = False
            except Exception as e:
                print('执行 {} 失败：{}'.format(cmd, e))

                if self.system == 'Linux':
                    print('请执行 sudo apt-get update && sudo apt-get install build-essential 以安装编译工具')
                if self.system == 'Darwin':
                    print('请从 App Store 安装最新的 Xcode 以安装编译工具')
                exit(1)
        if self.ohos_sdk_path and os.path.isdir(self.ohos_sdk_path):
            # 检查 native\oh-uni-package.json 是否存在
            package_json_path = os.path.join(self.ohos_sdk_path, 'native', 'oh-uni-package.json')
            if os.path.isfile(package_json_path):
                # 尝试读取 JSON 文件，检查是否能正确解析
                try:
                    with open(package_json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print('OHOS SDK 版本信息 {}  {}'.format(data.get('apiVersion'), data.get('version')))
                        os.environ['OHOS_SDK_PATH'] = self.ohos_sdk_path
                        need_ohos_sdk = False
                except Exception as e:
                    print('警告: 无法解析 {}，文件可能损坏或格式不正确。错误: {}'.format(package_json_path, e))
        temp_dir = os.path.join(self.get_working_dir(), '.temp')
        if need_perl and self.system == 'Windows':
            perl_url = self.get_depends().get('perl').get('url')
            perl_checksum = ('sha256', self.get_depends().get('perl').get('sha256'))
            download_path = os.path.join(temp_dir, 'perl5.7z')
            print('正在下载并安装 Perl...')
            zip_path = download_component(perl_url, download_path, perl_checksum)
            perl_extracted_path = os.path.join(self.get_working_dir(), 'perl')
            extract_archive(zip_path, perl_extracted_path)
            if os.path.isdir(perl_extracted_path):
                self.perl_path = os.path.join(perl_extracted_path, 'bin')

        if need_mingw and self.system == 'Windows':
            mingw_url = self.get_depends().get('mingw').get('url')
            mingw_checksum = ('sha256', self.get_depends().get('mingw').get('sha256'))
            download_path = os.path.join(temp_dir, 'mingw64-x86_64-8.1.0-release-posix-seh-rt_v6-rev0.7z')
            print('正在下载并安装 MinGW...')
            zip_path = download_component(mingw_url, download_path, mingw_checksum)
            mingw_extracted_path = os.path.join(self.get_working_dir(), 'mingw')
            extract_archive(zip_path, mingw_extracted_path)
            if os.path.isdir(mingw_extracted_path):
                self.mingw_path = os.path.join(mingw_extracted_path, 'bin')

        if need_ohos_sdk:
            api_version = self.ohos_version()
            print('正在下载并安装 OpenHarmony SDK...')
            saved = self.ohos_sdk_downloader.download_component_by_name(api_version=api_version,
                                                                        component_name='native',
                                                                        dest_dir=temp_dir)
            extract_archive(saved, self.ohos_sdk_path)

        if need_perl or need_mingw or need_ohos_sdk:
            self.dev_env_check()

    def get_working_dir(self):
        working_dir = self.get_config_value('working_dir')
        if '${pwd}' in working_dir:
            working_dir = working_dir.replace('${pwd}', self.root_path)
        working_dir = os.path.abspath(os.path.expanduser(working_dir))
        return working_dir

    def get_output_path(self):
        return os.path.join(self.get_working_dir(), 'output')

    def get_perl_path(self):
        _perl_path = self.get_config_value('perl')
        if '${pwd}' in _perl_path:
            _perl_path = _perl_path.replace('${pwd}', self.root_path)
        _perl_path = os.path.abspath(os.path.expanduser(_perl_path))
        return _perl_path

    def get_mingw_path(self):
        _mingw_path = self.get_config_value('mingw')
        if '${pwd}' in _mingw_path:
            _mingw_path = _mingw_path.replace('${pwd}', self.root_path)
        _mingw_path = os.path.abspath(os.path.expanduser(_mingw_path))
        return _mingw_path
    
    def get_ohos_sdk_path(self):
        _ohos_sdk_path = self.get_config_value('ohos_sdk')
        if '${pwd}' in _ohos_sdk_path:
            _ohos_sdk_path = _ohos_sdk_path.replace('${pwd}', self.root_path)
        if '${ohos_version}' in _ohos_sdk_path:
            _ohos_sdk_path = _ohos_sdk_path.replace('${ohos_version}', str(self.ohos_version()))
        _ohos_sdk_path = os.path.abspath(os.path.expanduser(_ohos_sdk_path))
        return _ohos_sdk_path

    def ohos_support_version(self):
        return self.get_depends().get('ohos_sdk').get('support_version')

    def supported_qt_tags(self):
        return self.config.get('supported-qt-tags')

    def ohos_version(self):
        return self.get_config_value('ohos_version')
    
    def qt_repo(self):
        return self.get_repos().get('qt_repo').get('url')

    def qt_ohos_patch_repo(self):
        return self.get_repos().get('qt-ohos-patch').get('url')
    
    def tag(self):
        return self.get_config_value('build_qt_tag')

    def ohqt_tag(self):
        return self.get_config_value('build_ohqt_tag')

    def qt_version(self):
        return self.tag().replace('v', '').replace('-lts-lgpl', '')

    def build_type(self):
        return self.get_config_value('build_type')

    def build_prefix(self):
        return os.path.join(self.get_output_path(), 'Qt{}-ohos{}-{}'.format(self.qt_version(),
                                                                            self.ohos_version(),
                                                                            self.build_ohos_abi()))

    def build_ohos_abi(self):
        return self.get_config_value('build_ohos_abi')

    def clone_depth(self):
        return int(self.get_config_value('clone_depth'))

    def build_jobs(self):
        jobs = int(self.get_config_value('jobs'))
        if jobs <= os.cpu_count():
            return jobs
        return os.cpu_count()

    def get_repos(self):
        return self.config.get('repositories', {})

    def get_depends(self):
        return self.config.get('dependencies', {})

    def get_config(self):
        return self.config.get('config')

    def get_user_config(self):
        if self.user_config is None:
            return self.get_config()
        return self.user_config.get('config', self.get_config())

    def get_config_value(self, key):
        return self.get_user_config().get(key, self.get_config().get(key))

    def save_usr_config(self, usr_config: Dict):
        usr_config_path = os.path.join(self.root_path, 'configure.json.user')
        obj = {
            'config': usr_config
        }
        with open(usr_config_path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=4)

    def build_configure_options(self):
        options = self.config['qt-config']
        result = []
        if options['license'] in ['opensource', 'commercial']:
            result.append('-{}'.format(options['license']))
        if options['confirm-license']:
            result.append('-confirm-license')
        host_platform = 'win32-g++'
        if platform.system() == 'Linux':
            host_platform = 'linux-g++'
        elif platform.system() == 'Darwin':
            host_platform = 'macx-clang'
        result += ['-platform', host_platform]
        result += ['-xplatform', options['-xplatform']]
        result += ['-opengl', options['-opengl']]
        if options['-opengles3']:
            result.append('-opengles3')
        if options['-no-dbus']:
            result.append('-no-dbus')
        if options['-disable-rpath']:
            result.append('-disable-rpath')
        for nomake in options['-nomake']:
            result += ['-nomake', nomake]
        skips = self.config[self.tag()]['-skip']
        for skip in skips:
            result += ['-skip', skip]
        result += ['-prefix', self.build_prefix()]
        result += ['-{}'.format(self.build_type())]
        result += ['-device-option', 'OHOS_ARCH={}'.format(self.build_ohos_abi())]
        result += ['-make-tool', '{} -j{}'.format(self.make_tools, self.build_jobs())]
        if self.get_config_value('verbose'):
            result += ['-verbose']
        return result

import platform
import os
import subprocess
from .utils import create_archive
from .config import Config
import shutil

class QtBuild:
    def __init__(self, source_dir: str, config: Config):
        self.source_dir = source_dir
        self.config = config
        self.build_dir = os.path.join(self.source_dir, 'build', config.build_type())
        self.system = platform.system()
        self.make_tools = 'mingw32-make' if self.system == 'Windows' else 'make'
        self.rmdir_cmd = ['rmdir', '/S', '/Q'] if self.system == 'Windows' else ['rm', '-rf']
        self.rmdir_cmd += self.build_dir
        self.supported_systems = ['Windows', 'Linux', 'Darwin']
        if self.system not in self.supported_systems:
            raise EnvironmentError('Unsupported system: {}'.format(self.system))
        if not os.path.exists(self.build_dir):
            os.makedirs(self.build_dir)
    
    def configure(self):
        configure_script = os.path.join(self.source_dir, 'configure.bat' if self.system == 'Windows' else 'configure')
        cmd = [configure_script] + self.config.build_configure_options()
        print('配置命令：', ' '.join(cmd))
        result = subprocess.run(cmd, cwd=self.build_dir, check=True)
        if result.returncode == 0:
            print('配置成功')
        else:
            print('配置失败')

    def build(self, jobs: int = 4):
        make_cmd = [self.make_tools, '-j{}'.format(jobs)]
        print('构建命令：', ' '.join(make_cmd))
        result = subprocess.run(make_cmd, cwd=self.build_dir, check=True)
        if result.returncode == 0:
            print('构建成功')
        else:
            print('构建失败')

    def install(self):
        install_cmd = [self.make_tools, 'install']
        print('安装命令: ', install_cmd)
        result = subprocess.run(install_cmd, cwd=self.build_dir, check=True)
        if result.returncode == 0:
            print('安装成功')
        else:
            print('安装失败')
        if self.system == 'Windows':
            dll_deps = ['libstdc++-6.dll', 'libgcc_s_seh-1.dll', 'libwinpthread-1.dll']
            for dll_dep in dll_deps:
                src_dll = os.path.join(self.config.get_mingw_path(), dll_dep)
                if os.path.exists(src_dll):
                    shutil.copy(src_dll, os.path.join(self.config.build_prefix(), 'bin'))
                    print('已复制依赖 DLL: {}'.format(dll_dep))
                else:
                    print('未找到依赖 DLL: {}'.format(dll_dep))

    def clean(self):
        if os.path.exists(self.build_dir):
            print('正在删除构建目录: {}'.format(self.build_dir))
            result = subprocess.run(self.rmdir_cmd, check=True)
            if result.returncode == 0:
                print('构建目录已删除')
            else:
                print('删除构建目录失败')
        else:
            print('构建目录不存在，无需删除')

    def pack(self):
        prefix = self.config.build_prefix()
        if not prefix:
            raise ValueError('安装路径未设置，无法打包')
        suffix = 'zip' if self.system == 'Windows' else 'tar.gz'
        package_name = 'Qt{}_OHOS{}_{}_{}.{}'.format(
            self.config.qt_version(),
            self.config.ohos_version(),
            self.config.build_ohos_abi(),
            self.system.lower(),
            suffix
        )
        package_name = os.path.join(self.config.get_output_path(), package_name)
        create_archive(prefix, package_name, _format=suffix)

    def print_build_info(self):
        print('构建信息:')
        print('  系统: {}'.format(self.system))
        print('  源码目录: {}'.format(self.source_dir))
        print('  构建目录: {}'.format(self.build_dir))
        print('  安装目录: {}'.format(self.config.build_prefix()))
        print('  Qt 版本: {}'.format(self.config.qt_version()))
        print('  OHOS 版本: {}'.format(self.config.ohos_version()))
        print('  OHOS ABI: {}'.format(self.config.build_ohos_abi()))
        print('  构建类型: {}'.format(self.config.build_type()))
        print('  使用的 make 工具: {}'.format(self.make_tools))
        print('  支持的系统: {}'.format(', '.join(self.supported_systems)))
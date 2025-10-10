import platform
import os
import subprocess

class QtBuild:
    def __init__(self, source_dir: str, perl_path: str, make_path: str, ohos_sdk: str):
        self.source_dir = source_dir
        self.build_dir = os.path.join(self.source_dir, 'build')
        self.system = platform.system()
        self.make_tools = "mingw32-make" if self.system == "Windows" else "make"
        self.supported_systems = ["Windows", "Linux", "Darwin"]
        if self.system not in self.supported_systems:
            raise EnvironmentError("Unsupported system: {}".format(self.system))
        if self.system == "Windows":
            os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + perl_path
            os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + make_path
            print("当前系统是 Windows")
        elif self.system == "Linux":
            print("当前系统是 Linux")
        elif self.system == "Darwin":
            print("当前系统是 macOS")
        else:
            print("当前系统是 {}，可能不受支持".format(self.system))
            return
        os.environ["OHOS_SDK_PATH"] = ohos_sdk
        result = subprocess.run(["perl", "-v"], capture_output=True, text=True)
        if result.returncode == 0:
            print("perl 版本信息：")
            print(result.stdout)
        else:
            print("perl 执行失败")

        result = subprocess.run([self.make_tools, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("当前系统是 {}，版本信息：".format(self.make_tools))
            print(result.stdout)
        else:
            print("{} 执行失败".format(self.make_tools))
        if not os.path.exists(self.build_dir):
            os.makedirs(self.build_dir)
    
    def configure(self, options: list):
        configure_script = os.path.join(self.source_dir, 'configure.bat' if self.system == "Windows" else 'configure')
        cmd = [configure_script] + options
        print("配置命令：", ' '.join(cmd))
        result = subprocess.run(cmd, cwd=self.build_dir, check=True)
        if result.returncode == 0:
            print("配置成功")
        else:
            print("配置失败")

    def build(self, jobs: int = 4):
        make_cmd = [self.make_tools, "-j{}".format(jobs)]
        print("构建命令：", ' '.join(make_cmd))
        result = subprocess.run(make_cmd, cwd=self.build_dir, check=True)
        if result.returncode == 0:
            print("构建成功")
        else:
            print("构建失败")

    def install(self):
        install_cmd = [self.make_tools, "install"]
        print("安装命令: ", install_cmd)
        result = subprocess.run(install_cmd, cwd=self.build_dir, check=True)
        if result.returncode == 0:
            print("安装成功")
        else:
            print("安装失败")

    def clean(self):
        if os.path.exists(self.build_dir):
            print("正在删除构建目录: {}".format(self.build_dir))
            result = subprocess.run(["rm", "-rf", self.build_dir] if self.system != "Windows" else ["rmdir", "/S", "/Q", self.build_dir], check=True)
            if result.returncode == 0:
                print("构建目录已删除")
            else:
                print("删除构建目录失败")
        else:
            print("构建目录不存在，无需删除")

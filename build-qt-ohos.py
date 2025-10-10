import os
from build_qt.qt_repo import QtRepo, QtRepoError
from build_qt.qt_build import QtBuild
from build_qt.config import Config

if __name__ == '__main__':

    config = Config(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'configure.json'))
    # 开发环境检查
    config.dev_env_check()

    qt_dir = os.path.join(config.get_working_dir(), 'qt5')

    depth = 1
    repo = QtRepo(qt_dir)
    try:
        # Qt源码克隆，url: {config.qt_repo()}, 深度为 {depth}, 分支/标签为 {config.tag()}
        repo.clone(config.qt_repo(), depth=depth, branch=config.tag())

        # Qt OHOS补丁仓库克隆，url: {config.qt_ohos_patch_repo()}, 深度为 {depth}
        repo.clone_patch_repo(config.qt_ohos_patch_repo(), depth=depth)

        # 应用补丁
        repo.apply_patches()
    except QtRepoError as e:
        print('QtRepoError:', e)
        exit(1)
    except Exception as e:
        print('Error:', e)
        exit(1)

    # Qt编译
    qtBuild = QtBuild(qt_dir, config.get_perl_path(), config.get_mingw_path(), config.get_ohos_sdk_path())
    try:
        # 配置
        qtBuild.configure(config.build_configure_options())
        # 构建
        qtBuild.build(jobs=32)
        # 安装
        qtBuild.install()
    except Exception as e:
        print('Error during configuration:', e)

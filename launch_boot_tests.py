#!/home/pzx/pzx/boot-tests/venv/bin/python

#This is a job lauch script for boot tests

import os
import sys
from uuid import UUID
from itertools import starmap
from itertools import product

from gem5art.artifact.artifact import Artifact
from gem5art.run import gem5Run
from gem5art.tasks.tasks import run_gem5_instance

import multiprocessing as mp

packer = Artifact.registerArtifact(
    command = '''wget https://releases.hashicorp.com/packer/1.4.3/packer_1.4.3_linux_amd64.zip;
    unzip packer_1.4.3_linux_amd64.zip;
    ''',
    typ = 'binary',
    name = 'packer',
    path = 'disk-image/packer',
    cwd = 'disk-image',
    documentation = 'Program to build disk images. Download sometime in Sep/16 from hashicorp.'
)

experiments_repo = Artifact.registerArtifact(
    command = 'git clone git@github.com:hustpzx/boot_tests.git',
    typ = 'git repo',
    name = 'boot_tests',
    path = './',
    cwd = '../',
    documentation = 'main experiments repo to run full system boot tests with gem5 20.1'
)

gem5_repo = Artifact.registerArtifact(
    command = 'git clone git@github.com:gem5/gem5.git',
    typ = 'git repo',
    name = 'gem5',
    path =  'gem5/',
    cwd = './',
    documentation = 'cloned gem5 from github and checked out v20.1.0.0'
)

gem5_binary = Artifact.registerArtifact(
    command = '''cd gem5;
    git checkout v20.1.0.0;
    scons build/X86/gem5.opt -j8
    ''',
    typ = 'gem5 binary',
    name = 'gem5',
    cwd = 'gem5/',
    path =  'gem5/build/X86/gem5.opt',
    inputs = [gem5_repo,],
    documentation = 'gem5 binary based on v20.1.0.0'
)

m5_binary = Artifact.registerArtifact(
    command = 'scons build/x86/out/m5',
    typ = 'binary',
    name = 'm5',
    path = 'gem5/util/m5/build/x86/out/m5',
    cwd = 'gem5/util/m5',
    inputs = [gem5_repo,],
    documentation = 'm5 utility'
)

disk_image = Artifact.registerArtifact(
    command = './packer build boot-exit/boot-exit.json',
    typ = 'disk image',
    name = 'boot-disk',
    cwd = 'disk-image',
    path = 'disk-image/boot-exit/boot-exit-image/boot-exit',
    inputs = [packer, experiments_repo, m5_binary,],
    documentation = 'Ubuntu with m5 utility installed and root auto login'
)

gem5_binary_MESI_Two_Level = Artifact.registerArtifact(
    command = '''cd gem5;
    git checkout v20.1.0.0;
    scons build/X86_MESI_Two_Level/gem5.opt --default=X86 PROTOCOL=MESI_Two_Level SLICC_HTML=True -j8
    ''',
    typ = 'gem5 binary',
    name = 'gem5',
    cwd = 'gem5/',
    path =  'gem5/build/X86_MESI_Two_Level/gem5.opt',
    inputs = [gem5_repo,],
    documentation = 'gem5 binary based on v20.1.0.0'
)

gem5_binary_MOESI_CMP_directory = Artifact.registerArtifact(
    command = '''cd gem5;
    git checkout v20.1.0.0;
    scons build/MOESI_CMP_directory/gem5.opt --default=X86 PROTOCOL=MOESI_CMP_directory -j8
    ''',
    typ = 'gem5 binary',
    name = 'gem5',
    cwd = 'gem5/',
    path =  'gem5/build/MOESI_CMP_directory/gem5.opt',
    inputs = [gem5_repo,],
    documentation = 'gem5 binary based on v20.1.0.0'
)

linux_repo = Artifact.registerArtifact(
    command = 'git clone  https://mirrors.tuna.tsinghua.edu.cn/git/linux-stable.git',
    typ = 'git repo',
    name = 'linux-stable',
    path =  'linux/linux-stable/',
    cwd = './linux/',
    documentation = 'linux kernel source code repo from Sept.17-2021'
)

linuxes = ['5.2.3', '4.19.83']#, '4.14.134', '4.9.186', '4.4.186']
linux_binaries = {
    version: Artifact.registerArtifact(
                name = f'vmlinux-{version}',
                typ = 'kernel',
                path = f'linux/vmlinux-{version}',
                cwd = 'linux/',
                command = f'''cd linux/linux-stable;
                git checkout v{version};
                cp ../../linux-configs/config.{version} .config;
                make -j8;
                mv vmlinux ../vmlinux-{version};
                ''',
                inputs = [experiments_repo, linux_repo,],
                documentation = f"Kernel binary for {version} with simple "
                                 "config file",
            )
    for version in linuxes
}

if __name__ == "__main__":
    boot_types = ['init']
    num_cpus = ['1']#, '2'], '4', '8']
    cpu_types = ['kvm']#, 'atomic'], 'simple', 'o3']
    mem_types = ['MI_example']#, 'MESI_Two_Level'], 'MOESI_CMP_directory']

    def createRun(linux, boot_type, cpu, num_cpu, mem):

        if mem == 'MESI_Two_Level':
            binary_gem5 = 'gem5/build/X86_MESI_Two_Level/gem5.opt'
            artifact_gem5 = gem5_binary_MESI_Two_Level
        elif mem == 'MOESI_CMP_directory':
            binary_gem5 = 'gem5/build/MOESI_CMP_directory/gem5.opt'
            artifact_gem5 = gem5_binary_MOESI_CMP_directory
        else:
            binary_gem5 = 'gem5/build/X86/gem5.opt'
            artifact_gem5 = gem5_binary
        
        return gem5Run.createFSRun(
            'boot experiments with gem5 20.1',
            binary_gem5,
            'configs/run_exit.py',
            'results/run_exit/vmlinux-{}/boot-exit/{}/{}/{}/{}'.
                format(linux, cpu, mem, num_cpu, boot_type),
            artifact_gem5, gem5_repo, experiments_repo,
            os.path.join('linux', 'vmlinux'+'-'+linux),
            'disk-image/boot-exit/boot-exit-image/boot-exit',
            linux_binaries[linux], disk_image,
            cpu, mem, num_cpu, boot_type,
            timeout = 10*60*60 # 10 hours
        )



    # For the cross product of tests, create a run object
    runs = starmap(createRun, product(linuxes, boot_types, cpu_types, num_cpus, mem_types))
    # Run all of these experiments in parallel
    for run in runs:
        run_gem5_instance.apply_async((run, os.getcwd(),))
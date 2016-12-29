import os
import re
import subprocess


KB = 1
MB = 1000
GB = 1000000


class CommandException(Exception):
    pass


def command(cmd):
    process = subprocess.Popen(cmd, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            )

    stdout, stderr = process.communicate()

    if stderr:
        raise CommandException(stderr)

    return stdout


def create_regular_file(filename, size):
    command("truncate {} -s {}K".format(filename, size))


def loop_device_create(filename):
    return command("losetup -f {} --show".format(filename)).strip()


def loop_device_find(filename):
    """Returns list of loop devices attach to specified file
    """
    output = command("losetup -j {}".format(filename))

    return [line.split(":")[0] for line in output.splitlines()]


def loop_device_list():
    """Returns list of all attached loop devices

    The returned list is a list of tuples. The first element is the device name
    and the second element is the file that it is attached to.

    """
    output = command("losetup -a")
    pattern = re.compile("([^:]+):.*\(([^)]+)\)")

    return [pattern.match(line).groups() for line in output.splitlines()]


def loop_device_destroy(device):
    """Destroys the specified loop device
    """
    command("losetup -d {}".format(device))


def loop_device_mount(device, fmt, path):
    command("mount -t {} {} {}".format(fmt, device, path))


def loop_device_unmount(device):
    command("umount {}".format(device))


def loop_device_format_type(device):
    output = command("blkid {}".format(device))
    match = re.match('.*TYPE="([^"]+)".*', output)
    return match.group(1) if match is not None else None


def loop_device_format(device, fmt):
    command("mkfs -q -t {} {}".format(fmt, device))


def loop_device_is_mounted(device):
    for line in command("mount").splitlines():
        name, _ = line.split(" ", 1)
        if name == device:
            return True

    return False


class LoopDevice(object):
    def __init__(self, filename):
        self._filename = filename
        self._device = loop_device_create(filename)

    @property
    def device(self):
        return self._device

    @property
    def filename(self):
        return self._filename

    @property
    def mounted(self):
        return loop_device_is_mounted(self.device)

    @property
    def type(self):
        return loop_device_format_type(self._device)

    def mount(self, fmt, path):
        if not self.mounted:
            loop_device_mount(self.device, fmt, path)

    def unmount(self):
        if self.mounted:
            loop_device_unmount(self.device)

    def format(self, fmt):
        loop_device_format(self.device, fmt)


class FileSystem(object):
    def __init__(self, filename, mountpoint, fmt):
        self._device = LoopDevice(filename)

        if self._device.type is None:
            self._device.format(fmt)
        else:
            assert self._device.type == fmt

        self._mountpoint = mountpoint

    def __enter__(self):
        if not self.device.mounted:
            self.mount()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unmount()
        return False

    @property
    def mountpoint(self):
        return self._mountpoint

    @property
    def device(self):
        return self._device

    @property
    def format(self):
        return self.device.type

    def mount(self):
        self.device.mount(self.format, self.mountpoint)

    def unmount(self):
        self.device.unmount()

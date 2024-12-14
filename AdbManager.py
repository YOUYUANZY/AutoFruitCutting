import subprocess
import threading
import time
from typing import Optional

import adbutils
import cv2
import numpy as np
import pygetwindow as gw
import win32con
import win32gui
from PIL import Image

from utils.utils import line_intersect_rect


class adbManager:
    def __init__(self, port, package_name):
        self.port = port  # 检测端口
        self.package_name = package_name  # 检测应用包名
        self.device_serial = f"127.0.0.1:{port}"  # 指定目标设备序列号
        self.scrcpy_window: Optional[scrcpyWindow] = None
        self.scrcpy_process = None
        self.adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
        self.device = self.adb.device(serial=self.device_serial)
        self.swipe_event = threading.Event()

    def swipe(self, sx, sy, ex, ey, dur):
        """模拟滑动操作"""
        try:
            self.device.shell(f"input swipe {sx} {sy} {ex} {ey} {int(dur * 1000)}")
        except adbutils.errors.AdbError as e:
            print(f"滑动失败: {e}")

    def connect(self):
        """连接端口"""
        try:
            print(f"尝试链接模拟器端口 {self.port}...")
            result = subprocess.run(['adb', 'connect', self.device_serial], stdout=subprocess.PIPE, text=True)
            if 'connected' in result.stdout.lower() or 'already connected' in result.stdout.lower():
                print(f"成功链接模拟器端口 {self.port}.")
                return True
            else:
                print(f"模拟器端口链接失败 {self.port}. 输出: {result.stdout.strip()}")
                return False
        except Exception as e:
            print(f"链接模拟器错误: {e}")
            return False

    @staticmethod
    def connected_devices():
        """列出所有已连接的设备"""
        try:
            result = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE, text=True)
            devices = result.stdout.strip().split('\n')
            return [line.split('\t')[0] for line in devices[1:] if 'device' in line]
        except Exception as e:
            print(f"列出设备错误: {e}")
            return []

    def is_running(self, package_name=None, device_serial=None):
        """检测特定包名的应用是否在指定设备上运行"""
        if package_name is None:
            package_name = self.package_name
        if device_serial is None:
            device_serial = self.device_serial
        try:
            result = subprocess.run(['adb', '-s', device_serial, 'shell', 'dumpsys', 'activity', 'activities'],
                                    stdout=subprocess.PIPE, text=True)
            if package_name in result.stdout:
                print(f"应用 {package_name} 在设备 {device_serial}上运行.")
                return True
            else:
                print(f"应用 {package_name} 不在设备 {device_serial}上运行.")
                return False
        except Exception as e:
            print(f"应用查询失败: {e}")
            return False

    def capture_screen(self, device_serial=None):
        """使用ADB从设备截屏，并直接加载到内存"""
        if device_serial is None:
            device_serial = self.device_serial
        try:
            result = subprocess.run(['adb', '-s', device_serial, 'exec-out', 'screencap', '-p'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            image_data = np.frombuffer(result.stdout, np.uint8)
            image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
            image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            return image
        except Exception as e:
            print(f"捕捉屏幕失败: {e}")
            return None

    def get_resolution(self, device_serial=None):
        """获取设备的原始分辨率。"""
        if device_serial is None:
            device_serial = self.device_serial
        try:
            output = subprocess.check_output(
                ['adb', "-s", device_serial, "shell", "wm", "size"]
            ).decode()
            size_str = output.split(":")[1].strip()
            height, width = map(int, size_str.split("x"))
            return width, height
        except Exception as e:
            print(f"获取分辨率失败: {e}")
            return None, None

    def start_ScrcpyProcess(self, param):
        """启动Scrcpy进程获取屏幕窗口视频流"""
        self.scrcpy_process = subprocess.Popen(param)

        self.get_scrcpyWindow()

    def get_scrcpyWindow(self):
        """获得scrcpy窗口"""
        print(f"等待 scrcpy 窗口出现 (最多等待 {2} 秒)...")
        start_time = time.time()
        while time.time() - start_time < 2:
            try:
                scrcpy_window = gw.getWindowsWithTitle("SM-G9900")[0]
                break
            except IndexError:
                time.sleep(0.5)

        if scrcpy_window is None:
            print(f"在 {2} 秒内未找到 scrcpy 窗口，请检查 scrcpy 是否正常启动或设备是否连接。")
            self.scrcpy_process.terminate()
            exit()
        print("窗口已找到")
        w, h = self.get_resolution()
        self.scrcpy_window = scrcpyWindow(scrcpy_window, w, h)

    def end_ScrcpyProcess(self):
        self.scrcpy_process.terminate()


class scrcpyWindow:
    def __init__(self, window, sw, sh):
        self.window = window
        self.start_w = sw
        self.start_h = sh
        self.pre_w = sw
        self.pre_h = sh
        self.hwnd = self.window._hWnd

    def get_winRect(self):
        """获取窗口相对于屏幕的坐标。"""
        try:
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            return left, top, right, bottom
        except Exception as e:
            print(f"获取窗口坐标失败: {e}")
            return None, None, None, None

    def get_cilentRect(self):
        """获取窗口客户区相对于屏幕的坐标。"""
        try:
            # 获取窗口客户区相对于窗口的坐标
            client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(self.hwnd)
            # 将客户区坐标转换为屏幕坐标
            client_left, client_top = win32gui.ClientToScreen(self.hwnd, (client_left, client_top))
            client_right, client_bottom = win32gui.ClientToScreen(self.hwnd, (client_right, client_bottom))

            # 计算客户区相对于屏幕的坐标
            client_left_screen = client_left
            client_top_screen = client_top
            client_width = client_right - client_left
            client_height = client_bottom - client_top

            return client_left_screen, client_top_screen, client_width, client_height

        except Exception as e:
            print(f"获取客户区坐标失败: {e}")
            return None, None, None, None

    def resize_window(self, w, h):
        """重新设置窗口大小"""
        self.pre_w = w
        self.pre_h = h
        left, top, right, bottom = self.get_winRect()
        _, _, client_width, client_height = self.get_cilentRect()
        non_client_width = (right - left) - client_width
        non_client_height = (bottom - top) - client_height
        new_window_width = w + non_client_width
        new_window_height = h + non_client_height
        win32gui.SetWindowPos(self.hwnd, win32con.HWND_NOTOPMOST, left, top, new_window_width, new_window_height,
                              win32con.SWP_NOZORDER)

    def maintain_winRatio(self):
        """保持窗口比例"""
        _, _, client_width, client_height = self.get_cilentRect()

        wr = abs(client_width - self.pre_w) / self.pre_w
        hr = abs(client_height - self.pre_h) / self.pre_h

        if wr > hr:
            target_w = client_width
            target_h = int(client_width * (self.start_h / self.start_w))
        else:
            target_w = int(client_height * (self.start_w / self.start_h))
            target_h = client_height
        self.resize_window(target_w, target_h)

    def getPaths(self, boxes, num):
        """获取滑动路径简易版"""
        if not boxes:
            return None
        wr = self.start_w / self.pre_w
        hr = self.start_h / self.pre_h
        paths = []
        for i in range(min(num, len(boxes))):
            sx = int(boxes[i]['bbox'][0] * wr)
            sy = int(boxes[i]['bbox'][3] * hr) - 5
            ex = int(boxes[i]['bbox'][2] * wr)
            ey = int(boxes[i]['bbox'][1] * hr) - 5
            paths.append((sx, sy, ex, ey))
        return paths

    def getPaths2(self, boxes, num, pad=30, split=0.5, d_up=10, d_down=10):
        """获取滑动路径"""
        if not boxes:
            return None, None
        wr = self.start_w / self.pre_w
        hr = self.start_h / self.pre_h
        split_y = self.start_h * (1 - split)

        boxes_array = np.array([box['bbox'] for box in boxes])
        class_array = np.array([box['class'] for box in boxes])

        xA = ((boxes_array[:, 0] + boxes_array[:, 2]) / 2 * wr).astype(int)
        yA = ((boxes_array[:, 1] + boxes_array[:, 3]) / 2 * hr).astype(int)
        wA = ((boxes_array[:, 2] - boxes_array[:, 0]) / 2 * wr).astype(int)
        hA = ((boxes_array[:, 3] - boxes_array[:, 1]) / 2 * hr).astype(int)

        is_bomb = class_array == '炸弹'
        boom_boxes = np.column_stack([
            (boxes_array[is_bomb, 0] * wr - pad).astype(int),
            (boxes_array[is_bomb, 1] * hr - pad).astype(int),
            (boxes_array[is_bomb, 2] * wr + pad).astype(int),
            (boxes_array[is_bomb, 3] * hr + pad).astype(int)
        ])
        non_boom_indices = np.where(~is_bomb)[0]

        paths = []
        count = 0
        boom = len(boom_boxes)
        for i in non_boom_indices:
            x, y, w, h = xA[i], yA[i], wA[i], hA[i]
            delta = d_down if y > split_y else d_up
            p = (x - w, y + h + delta, x + w, y - h + delta)

            collision = False
            for boo in boom_boxes:
                if line_intersect_rect(p[0], p[1], p[2], p[3], boo[0], boo[1], boo[2], boo[3]):
                    collision = True
                    break

            if not collision:
                paths.append(p)
                count += 1
                if count == num:
                    break

        paths = [tuple(p) for p in paths]
        paths = sorted(paths, key=lambda path: -path[3])
        return paths, boom


class SwipeThread(threading.Thread):
    def __init__(self, adbM, s_time):
        super().__init__(daemon=True)
        self.adbM = adbM
        self.paths = []
        self.stop_event = threading.Event()
        self.current_path_index = 0
        self.is_swiping = False
        self.swipe_time = s_time

    def run(self):
        while not self.stop_event.is_set():
            if self.paths and self.current_path_index < len(self.paths):
                path = self.paths[self.current_path_index]
                self.is_swiping = True
                self.adbM.swipe(path[0], path[1], path[2], path[3], self.swipe_time)
                self.is_swiping = False
                self.current_path_index += 1
            else:
                time.sleep(0.02)  # 没有路径时休眠

    def update_paths(self, paths, boom):
        """更新滑动路径列表。"""
        while paths and not boom and self.is_swiping:
            time.sleep(0.01)
        self.paths = paths
        self.current_path_index = 0

    def stop(self):
        """设置停止事件, 终止线程。"""
        self.stop_event.set()

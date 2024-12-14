import math
import threading
import time

import cv2
import mss
import numpy as np
from PIL import Image

from AdbManager import adbManager, SwipeThread
from SeDetector import seDetector
from yolo import YOLO

# 系统控制参数
adbM = None  # adb管理类
PORT = 16384  # 模拟器端口
PACKAGE_NAME = "com.halfbrick.fruitninjafree"  # 应用包名
SCRCPY_PARAM = ["scrcpy-win64-v3.1/scrcpy.exe", "-m", "1280"]  # scrcpy启动参数
SWIPE_TIME = 0.02  # 滑动时间
BOX_LIMIT = 5  # 滑动box最大数量限制
BOOM_PAD = 40  # 炸弹的危险外延距离
SPLIT_RATE = 0.5  # 滑动偏移量改变的屏幕分割比例
BIAS_DOWN = 10  # 屏幕下方滑动偏移
BIAS_UP = 10  # 屏幕上方滑动偏移

seD = None  # 开始结束检测类
START_TEMPLATE_PATHS = [  # 开始模版路径
    "detect_img/start_0.jpg",
    "detect_img/start_1.jpg",
]
END_TEMPLATE_PATHS = [  # 结束模版路径
    "detect_img/end_1.jpg",
    "detect_img/end_2.jpg",
]
START_THRESHOLD = 0.8  # 开始模版置信阈值
END_THRESHOLD = 0.65  # 结束模板置信阈值

DEVICE_WIDTH = 1280  # 设备屏幕宽度
DEVICE_HEIGHT = 720  # 设备屏幕高度

yolo = YOLO()
DRAW_ENABLE = True


def init():
    """系统初始化，创建检测器，检查设备是否在线，应用是否运行"""
    global adbM, seD
    seD = seDetector(START_TEMPLATE_PATHS, END_TEMPLATE_PATHS, START_THRESHOLD, END_THRESHOLD, DEVICE_WIDTH,
                     DEVICE_HEIGHT)

    adbM = adbManager(port=PORT, package_name=PACKAGE_NAME)
    devices = adbM.connected_devices()

    if adbM.device_serial not in devices:
        adbM.connect()

    run = adbM.is_running()
    if not run:
        return False
    return True


def main():
    global adbM, yolo
    if init():
        # 启动scrcpy进程捕捉视频流
        adbM.start_ScrcpyProcess(SCRCPY_PARAM)

        yoloEnable = False
        
        # 维持屏幕比例
        def maintain_window():
            while True:
                if adbM.scrcpy_window:
                    adbM.scrcpy_window.maintain_winRatio()
                time.sleep(0.1)

        maintain_thread = threading.Thread(target=maintain_window, daemon=True)
        maintain_thread.start()

        swipe_thread = SwipeThread(adbM, SWIPE_TIME)
        swipe_thread.start()

        with mss.mss() as sct:
            while True:
                # 获取客户区相对于屏幕的坐标
                client_left, client_top, client_width, client_height = adbM.scrcpy_window.get_cilentRect()
                monitor = {
                    "top": client_top,
                    "left": client_left,
                    "width": client_width,
                    "height": client_height,
                    "mon": 0,
                }
                img = np.array(sct.grab(monitor))
                
                # 检测游戏开始/结束
                deResult = seD.matchTemplate(img, not yoloEnable)
                if deResult is not None:
                    if deResult == 1 and not yoloEnable:
                        print("yolo enable")
                        yoloEnable = True
                    elif deResult == 0 and yoloEnable:
                        print("yolo unenable")
                        yoloEnable = False

                if yoloEnable and img is not None:
                    # yolo目标检测
                    image = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                    image = Image.fromarray(image)
                    r_image, boxes = yolo.detect_image(image, drawEnable=DRAW_ENABLE)
                    # 标注图片显示
                    if DRAW_ENABLE:
                        r_image_cv = cv2.cvtColor(np.array(r_image), cv2.COLOR_RGB2BGR)
                        cv2.imshow('Live Screen', r_image_cv)
                    # 滑动路径计算
                    paths, boom = adbM.scrcpy_window.getPaths2(boxes, BOX_LIMIT, pad=BOOM_PAD, split=SPLIT_RATE,
                                                               d_down=BIAS_DOWN, d_up=BIAS_UP)
                    swipe_thread.update_paths(paths=paths, boom=boom)

                if cv2.waitKey(25) & 0xFF == ord("q"):
                    cv2.destroyAllWindows()
                    break
                    
        swipe_thread.stop()
        adbM.end_ScrcpyProcess()


if __name__ == "__main__":
    main()

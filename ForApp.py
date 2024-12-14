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

adbM = None
PORT = 16384
PACKAGE_NAME = "com.halfbrick.fruitninjafree"
SCRCPY_PARAM = ["scrcpy-win64-v3.1/scrcpy.exe", "-m", "1280"]
SWIPE_TIME = 0.02
BOX_LIMIT = 5
BOOM_PAD = 40
SPLIT_RATE = 0.5
BIAS_DOWN = 10
BIAS_UP = 10

seD = None
START_TEMPLATE_PATHS = [
    "detect_img/start_0.jpg",
    "detect_img/start_1.jpg",
]
END_TEMPLATE_PATHS = [
    "detect_img/end_1.jpg",
    "detect_img/end_2.jpg",
]
START_THRESHOLD = 0.8
END_THRESHOLD = 0.65

DEVICE_WIDTH = 1280
DEVICE_HEIGHT = 720

yolo = YOLO()
DRAW_ENABLE = False


def init():
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

                deResult = seD.matchTemplate(img, not yoloEnable)
                if deResult is not None:
                    if deResult == 1 and not yoloEnable:
                        print("yolo enable")
                        yoloEnable = True
                    elif deResult == 0 and yoloEnable:
                        print("yolo unenable")
                        yoloEnable = False

                if yoloEnable and img is not None:
                    image = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                    image = Image.fromarray(image)
                    r_image, boxes = yolo.detect_image(image, drawEnable=DRAW_ENABLE)
                    if DRAW_ENABLE:
                        r_image_cv = cv2.cvtColor(np.array(r_image), cv2.COLOR_RGB2BGR)
                        cv2.imshow('Live Screen', r_image_cv)

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

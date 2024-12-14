import cv2


class seDetector:
    def __init__(self, startPaths: list, endPaths: list, st, et, w, h):
        self.startPaths = startPaths
        self.endPaths = endPaths
        self.start = []
        self.end = []
        self.st = st
        self.et = et
        self.w = w
        self.h = h

        self.getTemplate()

    def getTemplate(self):
        """加载匹配模版"""
        for path in self.startPaths:
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            img = cv2.resize(img, (self.w, self.h), cv2.INTER_CUBIC)
            self.start.append(img)
        for path in self.endPaths:
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            img = cv2.resize(img, (self.w, self.h), cv2.INTER_CUBIC)
            self.end.append(img)

    def matchTemplate(self, img, start):
        """"匹配模版"""
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        gray_img = cv2.resize(gray_img, (self.w, self.h), cv2.INTER_CUBIC)
        if start:
            for s in self.start:
                result = cv2.matchTemplate(gray_img, s, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                if max_val > self.st:
                    print(f"检测到游戏开始，概率：{max_val}")
                    return 1
        else:
            for e in self.end:
                result = cv2.matchTemplate(gray_img, e, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                if max_val > self.et:
                    print(f"检测到游戏结束，概率：{max_val}")
                    return 0
        return None

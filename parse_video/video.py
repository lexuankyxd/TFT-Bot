from time import perf_counter_ns
import cv2
import numpy as np
import gc


class Video:
    def __init__(self, path: str):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames: int = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.current_frame = 0

    def getNextFrame(self, step: int = 1) -> np.ndarray | None:
        for _ in range(min(self.total_frames - self.current_frame - 1, step)):
            self.cap.grab()
        self.current_frame = min(self.total_frames - 1, self.current_frame + step)
        ret, frame = self.cap.retrieve()
        if ret:
            return frame
        return None

    def setFrameIndex(self, idx: int):
        self.current_frame = idx
        if idx < self.total_frames:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)


if __name__ == "__main__":
    v = Video("vids/a.mp4")

    # bar = tqdm.tqdm(total=v.total_frame)
    # while v.getNextFrame() is not None:
    #     bar.update(1)
